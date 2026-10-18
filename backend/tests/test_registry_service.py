"""Tests for the Capability Registry service and Embedder.

These tests require the MiniLM model. The model is loaded once per session
(cached as a process singleton via Embedder.get()).

Tests cover:
* Embedder basic functionality (encoding, dimensions, normalization)
* NumpyEmbeddingStore store/search/delete
* CapabilityRegistry CRUD (create, get, list, delete)
* CapabilityRegistry search pipeline (5 stages with traces)
* Negative-example reranker (the key G01 acceptance)
* Approval workflow (promote → approved, with audit)
* Relationships (graph edges)
* Tenant isolation (cross-tenant queries return zero results)
* Embedding reindex
"""

from __future__ import annotations

import os

# Set model cache BEFORE importing manara
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", "/home/z/my-project/.models")
os.environ.setdefault("HF_HOME", "/home/z/my-project/.models/hf_cache")

import numpy as np
import pytest
from sqlalchemy import select

from manara.db.registry_models import (
    CapabilityEmbeddingRow,
)
from manara.db.session import Base
from manara.lifecycle import FoundryState
from manara.registry import (
    EMBEDDING_DIM,
    SEED_CAPABILITIES,
    CapabilityRegistry,
    Embedder,
    reset_embedding_store,
)
from manara.registry.converters import row_to_capability
from manara.registry.seed_cards import (
    card_academic_publications,
    card_clinical_trials,
    card_patent_intelligence,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def embedder():
    """One Embedder instance per session (loads MiniLM once)."""
    return Embedder.get()


@pytest.fixture()
def db_session(engine):
    """Per-test DB session with a clean schema."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_embedding_store()
    from sqlalchemy.orm import Session

    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture()
def registry(db_session):
    return CapabilityRegistry(db_session)


@pytest.fixture()
def seeded_registry(registry):
    """Registry pre-loaded with all 8 seed cards."""
    for cap in SEED_CAPABILITIES:
        registry.create_capability(cap, tenant_id="tenant_demo")
    return registry


# ─────────────────────────────────────────────────────────────────────────────
# Embedder tests
# ─────────────────────────────────────────────────────────────────────────────


class TestEmbedder:
    def test_embedding_dimension_is_384(self, embedder):
        vec = embedder.encode_one("test sentence")
        assert vec.shape == (EMBEDDING_DIM,)
        assert vec.dtype == np.float32

    def test_embeddings_are_normalized(self, embedder):
        vecs = embedder.encode(["first sentence", "second sentence"])
        for v in vecs:
            assert abs(np.linalg.norm(v) - 1.0) < 1e-4

    def test_model_metadata_is_pinned(self, embedder):
        assert embedder.model_name == "paraphrase-multilingual-MiniLM-L12-v2"
        assert embedder.embedding_dim == 384
        assert embedder.model_version.startswith("v1-")

    def test_cross_domain_similarity_is_meaningful(self, embedder):
        """The core MiniLM property that enables MANARA's cross-domain search.

        'Future of intelligent prosthetics' should be more similar to
        'patent filings in robotics and biomedical engineering' than to
        'sodium-ion battery manufacturing'.
        """
        vecs = embedder.encode([
            "Future of intelligent prosthetics and neural interfaces",
            "Patent filings in robotics and biomedical engineering",
            "Sodium-ion battery manufacturing trends",
        ])
        # Normalize and compute cosine
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        normed = vecs / norms
        sim_prosthetics_patents = float(normed[0] @ normed[1])
        sim_prosthetics_battery = float(normed[0] @ normed[2])

        # This is the key assertion — the owner's acceptance criterion
        assert sim_prosthetics_patents > sim_prosthetics_battery, (
            f"prosthetics↔patents ({sim_prosthetics_patents:.3f}) should be > "
            f"prosthetics↔battery ({sim_prosthetics_battery:.3f})"
        )
        # And the prosthetics↔patents similarity should be non-trivial
        assert sim_prosthetics_patents > 0.3, (
            f"prosthetics↔patents similarity {sim_prosthetics_patents:.3f} too low; "
            "MiniLM may not be capturing cross-domain semantic proximity"
        )


# ─────────────────────────────────────────────────────────────────────────────
# CRUD tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCapabilityCRUD:
    def test_create_capability_generates_all_embeddings(self, registry):
        cap = card_academic_publications()
        registry.create_capability(cap, tenant_id="tenant_demo")

        # Expected embeddings: 1 description + N positive + M negative + 1 combined
        expected_count = 1 + len(cap.positive_examples) + len(cap.negative_examples) + 1
        stmt = select(CapabilityEmbeddingRow).where(
            CapabilityEmbeddingRow.capability_id == cap.id
        )
        rows = list(registry.db.execute(stmt).scalars())
        assert len(rows) == expected_count

        kinds = {r.kind for r in rows}
        assert kinds == {"description", "positive_example", "negative_example", "combined"}

    def test_get_capability_returns_pydantic_contract(self, registry):
        cap = card_academic_publications()
        registry.create_capability(cap, tenant_id="tenant_demo")

        row = registry.get_capability(cap.id, tenant_id="tenant_demo")
        assert row is not None
        restored = row_to_capability(row)
        assert restored.id == cap.id
        assert restored.positive_examples == cap.positive_examples
        assert restored.negative_examples == cap.negative_examples
        assert restored.status == FoundryState.CANDIDATE

    def test_list_capabilities_returns_only_searchable_statuses(self, seeded_registry):
        # All seed cards are in CANDIDATE state
        rows = seeded_registry.list_capabilities(tenant_id="tenant_demo")
        assert len(rows) == 8
        for r in rows:
            assert r.status in CapabilityRegistry.SEARCHABLE_STATUSES

    def test_list_capabilities_filters_by_domain(self, seeded_registry):
        rows = seeded_registry.list_capabilities(
            tenant_id="tenant_demo", domains=["medicine"]
        )
        # medicine should match clinical-trials (and academic-publications covers medicine)
        ids = {r.id for r in rows}
        assert "search.clinical-trials" in ids

    def test_delete_capability_cascades_to_embeddings(self, seeded_registry):
        cap_id = "search.academic-publications"
        # Verify embeddings exist before deletion
        stmt = select(CapabilityEmbeddingRow).where(
            CapabilityEmbeddingRow.capability_id == cap_id
        )
        before = list(seeded_registry.db.execute(stmt).scalars())
        assert len(before) > 0

        ok = seeded_registry.delete_capability(cap_id, tenant_id="tenant_demo")
        assert ok is True

        # Verify embeddings gone
        after = list(seeded_registry.db.execute(stmt).scalars())
        assert len(after) == 0

    def test_create_duplicate_raises_conflict(self, registry):
        cap = card_academic_publications()
        registry.create_capability(cap, tenant_id="tenant_demo")
        with pytest.raises(ValueError, match="already exists"):
            registry.create_capability(cap, tenant_id="tenant_demo")


# ─────────────────────────────────────────────────────────────────────────────
# Search pipeline tests — the heart of G01
# ─────────────────────────────────────────────────────────────────────────────


class TestSearchPipeline:
    """The 5-stage retrieval pipeline tests."""

    def test_prosthetics_query_returns_relevant_engines(self, seeded_registry):
        """THE OWNER'S ACCEPTANCE TEST.

        Query: 'Future of intelligent prosthetics and neural interfaces'
        Expected: returns academic-publications, patent-intelligence,
        clinical-trials, github-activity — even though NONE of these
        card display_names contains the word 'prosthetics'.

        This proves cross-domain semantic retrieval works.
        """
        result = seeded_registry.search(
            "Future of intelligent prosthetics and neural interfaces through 2035",
            tenant_id="tenant_demo",
            top_k=10,
        )

        # Must return hits
        assert len(result.hits) > 0, "No hits returned for prosthetics query"

        # Must include at least one of the relevant engines
        hit_ids = {h.capability.id for h in result.hits}
        expected_any = {
            "search.academic-publications",
            "search.patent-intelligence",
            "search.clinical-trials",
            "search.github-activity",
        }
        assert hit_ids & expected_any, (
            f"None of the relevant engines ({expected_any}) returned for "
            f"prosthetics query. Got: {hit_ids}"
        )

        # Each hit must carry reasons (matched_by or rejected_by_negative)
        for hit in result.hits:
            assert hit.matched_by, f"hit {hit.capability.id} has no matched_by reasons"

        # Stage traces must cover all 5 stages
        stages = [t.stage for t in result.stage_traces]
        assert "1_filter" in stages
        assert "2_hybrid" in stages
        assert "3_rerank" in stages
        assert "4_validate" in stages
        assert "5_return" in stages

    def test_battery_query_returns_energy_engine(self, seeded_registry):
        """A battery query should return the energy/EV engine."""
        result = seeded_registry.search(
            "Track Li-ion battery pack cost per kWh from 2015 to 2024",
            tenant_id="tenant_demo",
            top_k=5,
        )
        hit_ids = {h.capability.id for h in result.hits}
        assert "search.energy-ev-datasets" in hit_ids, (
            f"energy-ev-datasets missing from battery query results: {hit_ids}"
        )

    def test_irrelevant_query_returns_low_scores(self, seeded_registry):
        """A query about something with no matching engine should return hits
        with low scores and a coverage gap note."""
        result = seeded_registry.search(
            "How to bake sourdough bread at home",
            tenant_id="tenant_demo",
            top_k=10,
        )
        # Either no hits, OR all hits have low final_score
        if result.hits:
            for hit in result.hits:
                assert hit.final_score < 0.5, (
                    f"hit {hit.capability.id} has unexpectedly high score "
                    f"{hit.final_score:.3f} for irrelevant query"
                )

    def test_negative_examples_downrank_inappropriate_engine(self, seeded_registry):
        """The negative-example reranker must penalize engines whose negative
        examples match the query.

        Example: the patent-intelligence card has a negative example:
        'Prove a medical implant is safe based only on patent filing'.
        If the query is 'prove medical implant safety from patent filings',
        the patent-intelligence engine should be penalized.
        """
        result = seeded_registry.search(
            "prove medical implant safety from patent filings",
            tenant_id="tenant_demo",
            top_k=10,
        )
        # Find the patent-intelligence hit (if any)
        for hit in result.hits:
            if hit.capability.id == "search.patent-intelligence":
                # Either it has a rejected_by_negative entry, OR its score
                # is lower than it would be without the penalty
                assert hit.negative_penalty > 0, (
                    "patent-intelligence hit has zero negative_penalty despite "
                    "query matching a negative example"
                )

    def test_search_results_include_reasons(self, seeded_registry):
        """Every hit must carry 'matched_by' reasons (not just scores)."""
        result = seeded_registry.search(
            "Find clinical trials on neural interfaces",
            tenant_id="tenant_demo",
            top_k=5,
        )
        assert len(result.hits) > 0
        for hit in result.hits:
            assert len(hit.matched_by) > 0
            # Each matched_by entry is a human-readable string
            for reason in hit.matched_by:
                assert isinstance(reason, str)
                assert "=" in reason or "overlap" in reason

    def test_search_respects_top_k(self, seeded_registry):
        result = seeded_registry.search(
            "research publications",
            tenant_id="tenant_demo",
            top_k=3,
        )
        assert len(result.hits) <= 3

    def test_search_arabic_query_works(self, seeded_registry):
        """Multilingual: an Arabic query must match Arabic keywords."""
        result = seeded_registry.search(
            "براءات اختراع في مجال الروبوتات الطبية",
            tenant_id="tenant_demo",
            top_k=10,
        )
        assert len(result.hits) > 0
        # Patent intelligence card has Arabic keywords including "براءات"
        hit_ids = {h.capability.id for h in result.hits}
        assert "search.patent-intelligence" in hit_ids, (
            f"Arabic query about patents failed to retrieve patent-intelligence: {hit_ids}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Approval workflow tests
# ─────────────────────────────────────────────────────────────────────────────


class TestApprovalWorkflow:
    def test_promote_to_approved_records_reviewer(self, seeded_registry):
        approval = seeded_registry.promote(
            "search.academic-publications",
            tenant_id="tenant_demo",
            reviewer="ayman",
            rationale="Card has correct fields, multilingual keywords, and 30 positive examples.",
            new_status="approved",
            test_matrix_ref="tests/test_registry_service.py::TestCapabilityCRUD",
        )
        assert approval.decision == "approved"
        assert approval.reviewer == "ayman"
        assert approval.previous_status == "candidate"
        assert approval.new_status == "approved"

        # Verify the row was updated
        row = seeded_registry.get_capability(
            "search.academic-publications", tenant_id="tenant_demo"
        )
        assert row.status == "approved"
        assert row.approved_by == "ayman"
        assert row.approved_at is not None

    def test_promote_to_rejected_sets_status(self, seeded_registry):
        approval = seeded_registry.promote(
            "search.geopolitical-events",
            tenant_id="tenant_demo",
            reviewer="ayman",
            rationale="Insufficient negative examples for misuse.",
            new_status="rejected",
        )
        assert approval.decision == "rejected"
        row = seeded_registry.get_capability(
            "search.geopolitical-events", tenant_id="tenant_demo"
        )
        assert row.status == "rejected"

    def test_promote_nonexistent_raises(self, registry):
        with pytest.raises(ValueError, match="not found"):
            registry.promote(
                "search.does-not-exist",
                tenant_id="tenant_demo",
                reviewer="ayman",
                rationale="test",
            )


# ─────────────────────────────────────────────────────────────────────────────
# Relationship tests
# ─────────────────────────────────────────────────────────────────────────────


class TestRelationships:
    def test_add_complements_edge(self, seeded_registry):
        edge = seeded_registry.add_relationship(
            from_capability_id="search.academic-publications",
            to_capability_id="search.patent-intelligence",
            kind="complements",
            tenant_id="tenant_demo",
        )
        assert edge.kind == "complements"
        assert edge.from_capability_id == "search.academic-publications"
        assert edge.to_capability_id == "search.patent-intelligence"

    def test_self_relationship_rejected(self, seeded_registry):
        with pytest.raises(ValueError, match="self-relationships"):
            seeded_registry.add_relationship(
                from_capability_id="search.academic-publications",
                to_capability_id="search.academic-publications",
                kind="complements",
                tenant_id="tenant_demo",
            )

    def test_nonexistent_target_rejected(self, seeded_registry):
        with pytest.raises(ValueError, match="not found"):
            seeded_registry.add_relationship(
                from_capability_id="search.academic-publications",
                to_capability_id="search.does-not-exist",
                kind="complements",
                tenant_id="tenant_demo",
            )


# ─────────────────────────────────────────────────────────────────────────────
# Tenant isolation tests
# ─────────────────────────────────────────────────────────────────────────────


class TestTenantIsolation:
    """Per spec: 'cross-tenant secret/private report: zero exposure through
    retrieval, vector, agent or citations.'

    In G01 we ship single-tenant demo mode, but the registry MUST still
    respect tenant_id scoping so G03 can add authentication on top.
    """

    def test_tenant_a_cannot_see_tenant_b_capabilities(self, registry):
        """Insert a card as tenant_a, query as tenant_b → must return None."""
        cap = card_academic_publications()
        # Insert as tenant_a
        registry.create_capability(cap, tenant_id="tenant_a")

        # Query as tenant_b
        row = registry.get_capability(cap.id, tenant_id="tenant_b")
        assert row is None, "tenant_b should NOT see tenant_a's capability"

        # List as tenant_b
        rows = registry.list_capabilities(tenant_id="tenant_b")
        assert len(rows) == 0, "tenant_b list should be empty"

    def test_tenant_a_search_does_not_return_tenant_b_hits(self, registry):
        cap = card_patent_intelligence()
        registry.create_capability(cap, tenant_id="tenant_a")

        # Search as tenant_b
        result = registry.search(
            "patent intelligence",
            tenant_id="tenant_b",
            top_k=10,
        )
        assert len(result.hits) == 0, (
            "tenant_b search should not return tenant_a's capabilities"
        )

    def test_tenant_a_search_does_not_use_tenant_b_embeddings(self, registry):
        """Even if tenant_b's embeddings exist in the table, tenant_a's
        search must not consult them."""
        cap = card_clinical_trials()
        registry.create_capability(cap, tenant_id="tenant_a")

        # Search as tenant_b for clinical trials
        result = registry.search(
            "clinical trials on neural interfaces",
            tenant_id="tenant_b",
            top_k=10,
        )
        assert len(result.hits) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Embedding reindex tests
# ─────────────────────────────────────────────────────────────────────────────


class TestReindex:
    def test_reindex_regenerates_all_embeddings(self, seeded_registry):
        # Count embeddings before
        stmt = select(CapabilityEmbeddingRow).where(
            CapabilityEmbeddingRow.capability_id == "search.academic-publications"
        )
        before = len(list(seeded_registry.db.execute(stmt).scalars()))

        count = seeded_registry.reindex_embeddings(
            "search.academic-publications", tenant_id="tenant_demo"
        )
        assert count == before, "reindex should produce the same count of embeddings"

        after = len(list(seeded_registry.db.execute(stmt).scalars()))
        assert after == before


# ─────────────────────────────────────────────────────────────────────────────
# Seed card integrity tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSeedCards:
    def test_eight_seed_cards_present(self):
        assert len(SEED_CAPABILITIES) == 8

    def test_all_seed_cards_have_negative_examples(self):
        """Per spec: 'أمثلة الاستخدام الخاطئ إلزامية'."""
        for cap in SEED_CAPABILITIES:
            assert len(cap.negative_examples) >= 3, (
                f"{cap.id} has only {len(cap.negative_examples)} negative examples; "
                "spec requires at least 3"
            )

    def test_all_seed_cards_have_multilingual_keywords(self):
        """Per owner decision: 'كلمات مفتاحية بالعربية والإنجليزية'."""
        for cap in SEED_CAPABILITIES:
            assert len(cap.keywords_en) > 0, f"{cap.id} has no English keywords"
            assert len(cap.keywords_ar) > 0, f"{cap.id} has no Arabic keywords"

    def test_high_value_cards_have_at_least_15_positive_examples(self):
        """Per spec: '15–30 حالة متنوعة للبطاقات عالية القيمة'."""
        for cap in SEED_CAPABILITIES:
            assert len(cap.positive_examples) >= 15, (
                f"{cap.id} has only {len(cap.positive_examples)} positive examples; "
                "spec requires 15-30 for high-value cards"
            )

    def test_all_seed_cards_are_candidate_status(self):
        """Per spec: 'اعتماد بشري صريح قبل تحويل أي قدرة إلى Approved'."""
        for cap in SEED_CAPABILITIES:
            assert cap.status == FoundryState.CANDIDATE, (
                f"{cap.id} ships with status={cap.status}; should be CANDIDATE"
            )

    def test_all_seed_cards_have_empty_connector_ids(self):
        """Per spec: real connectors arrive in G02."""
        for cap in SEED_CAPABILITIES:
            assert cap.connector_ids == [], (
                f"{cap.id} has connector_ids={cap.connector_ids}; "
                "G01 seed cards must NOT reference real connectors"
            )

    def test_seed_card_ids_are_unique(self):
        ids = [c.id for c in SEED_CAPABILITIES]
        assert len(ids) == len(set(ids)), "duplicate capability IDs in seed"

    def test_seed_card_ids_match_search_prefix(self):
        for cap in SEED_CAPABILITIES:
            assert cap.id.startswith("search."), (
                f"{cap.id} doesn't follow search.<name> convention"
            )
