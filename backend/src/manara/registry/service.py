"""Capability Registry service — the "compounding asset".

This module implements the retrieval strategy mandated by
``01_ARCHITECTURE/02_CONTRACTS.md`` §Retrieval strategy:

    1. Fast metadata/tag/location/data-type/access-rights/readiness filtering.
    2. Hybrid full-text + embedding search only for candidates within
       authorization scope.
    3. Rerank candidate engine *use-case examples* and **negative use
       cases** against query and gap analysis.
    4. Validate current approved status and freshness; use engine or
       create candidate; report missing coverage.
    5. Evaluate retrieval using benchmark queries and correct/missing/
       unneeded engine precision/recall, not subjective LLM confidence.

The five-stage pipeline is exposed via ``CapabilityRegistry.search``.
Each stage is independently testable; the e2e acceptance test for G01
(prosthetics query) asserts that the pipeline returns the correct
engines with reasons and no phantom registry entries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from manara.contracts import CapabilityEvaluation, SearchCapability
from manara.db.registry_models import (
    ApprovalRow,
    CapabilityEmbeddingRow,
    CapabilityEvaluationRow,
    CapabilityRelationshipRow,
    CapabilityRow,
)
from manara.lifecycle import FoundryState
from manara.registry.converters import (
    capability_to_row,
    evaluation_to_row,
    row_to_capability,
)
from manara.registry.embeddings import (
    Embedder,
    Vector,
    build_combined_text,
    get_embedding_store,
)

# ─────────────────────────────────────────────────────────────────────────────
# Data classes for search results
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SearchStageTrace:
    """Per-stage trace of how many candidates survived.

    Used by ``/registry/search`` to return *reasons* — not just hits —
    so the frontend can show why an engine was selected or rejected.
    """

    stage: str
    candidates_in: int
    candidates_out: int
    notes: str = ""


@dataclass
class CapabilitySearchHit:
    """A single search hit with a score and the reasons it was selected."""

    capability: SearchCapability
    final_score: float
    stages: list[SearchStageTrace] = field(default_factory=list)
    matched_by: list[str] = field(default_factory=list)
    rejected_by_negative: list[str] = field(default_factory=list)
    text_similarity: float = 0.0
    semantic_similarity: float = 0.0
    negative_penalty: float = 0.0


@dataclass
class CapabilitySearchResult:
    """The full result of a registry search, including reasons."""

    query: str
    tenant_id: str
    requested_top_k: int
    stage_traces: list[SearchStageTrace]
    hits: list[CapabilitySearchHit]
    gaps: list[str]
    generated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "tenant_id": self.tenant_id,
            "requested_top_k": self.requested_top_k,
            "stage_traces": [
                {
                    "stage": s.stage,
                    "candidates_in": s.candidates_in,
                    "candidates_out": s.candidates_out,
                    "notes": s.notes,
                }
                for s in self.stage_traces
            ],
            "hits": [
                {
                    "capability_id": h.capability.id,
                    "display_name": h.capability.display_name,
                    "final_score": round(h.final_score, 4),
                    "matched_by": h.matched_by,
                    "rejected_by_negative": h.rejected_by_negative,
                    "text_similarity": round(h.text_similarity, 4),
                    "semantic_similarity": round(h.semantic_similarity, 4),
                    "negative_penalty": round(h.negative_penalty, 4),
                    "capability": h.capability.model_dump(mode="json"),
                }
                for h in self.hits
            ],
            "gaps": self.gaps,
            "generated_at": self.generated_at.isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# CapabilityRegistry — the service class
# ─────────────────────────────────────────────────────────────────────────────


class CapabilityRegistry:
    """The capability registry service.

    Wraps a SQLAlchemy session and exposes:
    * CRUD: create_capability, get_capability, list_capabilities,
      update_capability, delete_capability
    * Search: search(query, tenant_id, top_k, filters) → CapabilitySearchResult
    * Approval: promote(capability_id, reviewer, rationale) → ApprovalRow
    * Evaluation: add_evaluation(...)
    * Relationships: add_relationship(...)
    * Embeddings: reindex_embeddings(capability_id)
    """

    # Statuses that are visible to search. Per spec, only "approved"
    # engines should be returned in production searches, but for the G01
    # sandbox we also include "candidate" so we can demonstrate the
    # pipeline with seed cards before promotion.
    SEARCHABLE_STATUSES = (
        FoundryState.APPROVED.value,
        FoundryState.CANDIDATE.value,
        FoundryState.SANDBOX_TESTED.value,
        FoundryState.REVIEW_PENDING.value,
    )

    def __init__(self, db: Session) -> None:
        self.db = db
        self.embedder = Embedder.get()
        self.embedding_store = get_embedding_store()

    # ── CRUD ────────────────────────────────────────────────────────────────

    def create_capability(
        self, capability: SearchCapability, *, tenant_id: str
    ) -> CapabilityRow:
        """Insert a capability and generate its embeddings.

        Raises ``ValueError`` if a capability with the same ID already
        exists for this tenant.
        """
        existing = self.db.get(CapabilityRow, capability.id)
        if existing is not None and existing.tenant_id == tenant_id:
            raise ValueError(
                f"capability {capability.id!r} already exists for tenant {tenant_id!r}"
            )

        row = capability_to_row(capability, tenant_id=tenant_id)
        self.db.add(row)
        self.db.flush()
        self._generate_embeddings(row, capability)
        self.db.commit()
        return row

    def get_capability(self, capability_id: str, *, tenant_id: str) -> CapabilityRow | None:
        """Fetch a single capability by ID, scoped to the tenant."""
        stmt = select(CapabilityRow).where(
            CapabilityRow.id == capability_id,
            CapabilityRow.tenant_id == tenant_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_capabilities(
        self,
        *,
        tenant_id: str,
        domains: list[str] | None = None,
        statuses: list[str] | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[CapabilityRow]:
        """List capabilities with optional filters.

        Tenant scoping is always applied. Status defaults to SEARCHABLE_STATUSES.

        JSON-array "contains" filtering is done in Python (not SQL) for
        portability across SQLite and PostgreSQL. The SQL query filters by
        tenant + status; the domain/tag overlap is applied post-query.
        """
        stmt = select(CapabilityRow).where(CapabilityRow.tenant_id == tenant_id)
        if statuses:
            stmt = stmt.where(CapabilityRow.status.in_(statuses))
        else:
            stmt = stmt.where(CapabilityRow.status.in_(self.SEARCHABLE_STATUSES))
        stmt = stmt.order_by(CapabilityRow.updated_at.desc()).limit(limit * 5).offset(offset)
        rows = list(self.db.execute(stmt).scalars())

        # Post-query domain/tag overlap filter (works on both SQLite and PG)
        if domains:
            wanted_domains = set(domains)
            rows = [r for r in rows if wanted_domains & set(r.domains_json or [])]
        if tags:
            wanted_tags = set(tags)
            rows = [r for r in rows if wanted_tags & set(r.tags_json or [])]

        return rows[:limit]

    def delete_capability(self, capability_id: str, *, tenant_id: str) -> bool:
        """Delete a capability and its embeddings (cascade).

        Returns True if a row was deleted, False if not found.
        """
        row = self.get_capability(capability_id, tenant_id=tenant_id)
        if row is None:
            return False
        self.embedding_store.delete_for_capability(self.db, capability_id=capability_id)
        self.db.delete(row)
        self.db.commit()
        return True

    def reindex_embeddings(self, capability_id: str, *, tenant_id: str) -> int:
        """Regenerate all embeddings for a capability.

        Returns the number of embeddings stored.
        """
        row = self.get_capability(capability_id, tenant_id=tenant_id)
        if row is None:
            raise ValueError(f"capability {capability_id!r} not found for tenant")
        cap = row_to_capability(row)
        # Delete existing embeddings for this capability
        self.embedding_store.delete_for_capability(self.db, capability_id=capability_id)
        count = self._generate_embeddings(row, cap)
        self.db.commit()
        return count

    # ── Search ───────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        *,
        tenant_id: str,
        top_k: int = 10,
        domains: list[str] | None = None,
        tags: list[str] | None = None,
        languages: list[str] | None = None,
        min_semantic_similarity: float = 0.15,
        negative_penalty_weight: float = 0.5,
    ) -> CapabilitySearchResult:
        """Run the 5-stage retrieval pipeline.

        Stages:
            1. Filter: tenant + status + optional domain/tag/language filters.
            2. Hybrid: text similarity (keyword overlap) + semantic similarity
               (MiniLM cosine).
            3. Rerank by positive AND negative examples:
               - Positive match boosts score.
               - Negative match penalizes score (down-rank or filter).
            4. Validate: status is searchable; if not, skip.
            5. Return top_k with reasons.
        """
        stage_traces: list[SearchStageTrace] = []
        gaps: list[str] = []

        # ── Stage 1: Filter ──────────────────────────────────────────────────
        stmt = select(CapabilityRow).where(
            CapabilityRow.tenant_id == tenant_id,
            CapabilityRow.status.in_(self.SEARCHABLE_STATUSES),
        )
        if domains:
            stmt = stmt.where(CapabilityRow.domains_json.contains(domains))
        if tags:
            stmt = stmt.where(CapabilityRow.tags_json.contains(tags))
        if languages:
            # Any overlap with the capability's languages
            stmt = stmt.where(CapabilityRow.languages_json.contains(languages))

        rows_all = list(self.db.execute(stmt).scalars())
        stage_traces.append(SearchStageTrace(
            stage="1_filter",
            candidates_in=-1,  # unknown without a separate count
            candidates_out=len(rows_all),
            notes=f"tenant={tenant_id}, statuses={self.SEARCHABLE_STATUSES}, "
                  f"domains={domains}, tags={tags}, languages={languages}",
        ))

        if not rows_all:
            gaps.append(
                "No capabilities match the filter. Consider discovering a new "
                "source via the Foundry (G02)."
            )
            return CapabilitySearchResult(
                query=query,
                tenant_id=tenant_id,
                requested_top_k=top_k,
                stage_traces=stage_traces,
                hits=[],
                gaps=gaps,
                generated_at=datetime.now(UTC),
            )

        # ── Stage 2: Hybrid text + semantic similarity ──────────────────────
        query_vec = self.embedder.encode_one(query)
        hits: list[CapabilitySearchHit] = []

        for row in rows_all:
            cap = row_to_capability(row)
            # Text similarity: keyword overlap (ar + en) + tag overlap + synonym overlap
            text_sim = self._text_similarity(query, cap)
            # Semantic similarity: cosine between query embedding and the
            # capability's "combined" embedding
            semantic_sim = self._semantic_similarity(query_vec, row, tenant_id=tenant_id)

            matched_by: list[str] = []
            if text_sim > 0:
                matched_by.append(f"text_overlap={text_sim:.2f}")
            if semantic_sim >= min_semantic_similarity:
                matched_by.append(f"semantic={semantic_sim:.2f}")

            # Skip if neither text nor semantic matched
            if not matched_by:
                continue

            hits.append(CapabilitySearchHit(
                capability=cap,
                final_score=0.0,  # computed in stage 3
                matched_by=matched_by,
                text_similarity=text_sim,
                semantic_similarity=semantic_sim,
            ))

        stage_traces.append(SearchStageTrace(
            stage="2_hybrid",
            candidates_in=len(rows_all),
            candidates_out=len(hits),
            notes=f"text+semantic, min_semantic={min_semantic_similarity}",
        ))

        # ── Stage 3: Rerank with positive AND negative examples ──────────────
        if not hits:
            gaps.append(
                "No capabilities matched the query via text or semantic similarity. "
                "The query may be out of scope for the current registry, or the "
                "embedding model may need re-tuning."
            )
            return CapabilitySearchResult(
                query=query,
                tenant_id=tenant_id,
                requested_top_k=top_k,
                stage_traces=stage_traces,
                hits=[],
                gaps=gaps,
                generated_at=datetime.now(UTC),
            )

        # Compute positive-example match boost and negative-example penalty
        query_vec_norm = query_vec / (np.linalg.norm(query_vec) + 1e-12)
        for hit in hits:
            # Positive example similarity (max across all positive examples)
            pos_sims = self._example_similarities(
                query_vec_norm, hit.capability.id, tenant_id, kind="positive_example"
            )
            pos_boost = max(pos_sims) if pos_sims else 0.0
            if pos_boost >= 0.4:
                hit.matched_by.append(f"positive_example={pos_boost:.2f}")

            # Negative example similarity (max across all negative examples)
            neg_sims = self._example_similarities(
                query_vec_norm, hit.capability.id, tenant_id, kind="negative_example"
            )
            neg_penalty = max(neg_sims) if neg_sims else 0.0
            if neg_penalty >= 0.4:
                hit.rejected_by_negative.append(
                    f"negative_example={neg_penalty:.2f}"
                )

            # Final score: weighted combination
            #   base = max(text, semantic)  → ensures semantic OR text match counts
            #   positive boost + 0.15
            #   negative penalty * weight
            base = max(hit.text_similarity, hit.semantic_similarity)
            hit.negative_penalty = neg_penalty * negative_penalty_weight
            hit.final_score = (
                base
                + (pos_boost * 0.15)
                - hit.negative_penalty
            )

        # Sort by final score (descending)
        hits.sort(key=lambda h: h.final_score, reverse=True)
        stage_traces.append(SearchStageTrace(
            stage="3_rerank",
            candidates_in=len(hits),
            candidates_out=min(top_k, len(hits)),
            notes=f"positive_boost=0.15, negative_penalty_weight={negative_penalty_weight}",
        ))

        # ── Stage 4: Validate (already done via SEARCHABLE_STATUSES) ────────
        stage_traces.append(SearchStageTrace(
            stage="4_validate",
            candidates_in=len(hits),
            candidates_out=len(hits),
            notes="all candidates already filtered by SEARCHABLE_STATUSES in stage 1",
        ))

        # ── Stage 5: Return top_k with reasons ───────────────────────────────
        top_hits = hits[:top_k]
        stage_traces.append(SearchStageTrace(
            stage="5_return",
            candidates_in=len(hits),
            candidates_out=len(top_hits),
            notes=f"top_k={top_k}",
        ))

        # Gap analysis
        if not top_hits:
            gaps.append(
                "All candidates were filtered out by negative-example reranking. "
                "This is a signal that the available engines are NOT appropriate "
                "for this query."
            )
        elif len(top_hits) < top_k:
            gaps.append(
                f"Only {len(top_hits)} of {top_k} requested engines matched. "
                f"Coverage gap: consider discovering a new source (G02 Foundry)."
            )

        return CapabilitySearchResult(
            query=query,
            tenant_id=tenant_id,
            requested_top_k=top_k,
            stage_traces=stage_traces,
            hits=top_hits,
            gaps=gaps,
            generated_at=datetime.now(UTC),
        )

    # ── Approval ──────────────────────────────────────────────────────────────

    def promote(
        self,
        capability_id: str,
        *,
        tenant_id: str,
        reviewer: str,
        rationale: str,
        new_status: Literal["approved", "rejected", "reverted"] = "approved",
        test_matrix_ref: str | None = None,
    ) -> ApprovalRow:
        """Owner-approved promotion of a capability.

        Per spec: "Registry promotion is owner-approved, version-pinned,
        reversible; record test matrix and rights decision."
        """
        row = self.get_capability(capability_id, tenant_id=tenant_id)
        if row is None:
            raise ValueError(f"capability {capability_id!r} not found for tenant")

        previous_status = row.status
        if new_status == "approved":
            row.status = FoundryState.APPROVED.value
            row.approved_by = reviewer
            row.approved_at = datetime.now(UTC)
        elif new_status == "rejected":
            row.status = FoundryState.REJECTED.value
        elif new_status == "reverted":
            row.status = FoundryState.CANDIDATE.value
            row.approved_by = None
            row.approved_at = None
        else:
            raise ValueError(f"invalid new_status: {new_status!r}")

        approval = ApprovalRow(
            capability_id=capability_id,
            tenant_id=tenant_id,
            decision=new_status,
            reviewer=reviewer,
            rationale=rationale,
            new_status=row.status,
            previous_status=previous_status,
            test_matrix_ref=test_matrix_ref,
            decided_at=datetime.now(UTC),
        )
        self.db.add(approval)
        # Update the payload to reflect the new status
        cap = row_to_capability(row)
        cap.status = FoundryState(row.status)
        cap.approved_by = row.approved_by
        row.payload = cap.model_dump(mode="json")
        self.db.commit()
        return approval

    # ── Relationships ─────────────────────────────────────────────────────────

    def add_relationship(
        self,
        *,
        from_capability_id: str,
        to_capability_id: str,
        kind: Literal["complements", "specializes", "replaces", "conflicts_with"],
        tenant_id: str,
    ) -> CapabilityRelationshipRow:
        """Add a directed edge between two capabilities."""
        # Validate both exist
        a = self.get_capability(from_capability_id, tenant_id=tenant_id)
        b = self.get_capability(to_capability_id, tenant_id=tenant_id)
        if a is None or b is None:
            raise ValueError("one or both capability IDs not found")
        if from_capability_id == to_capability_id:
            raise ValueError("self-relationships are not allowed")

        edge = CapabilityRelationshipRow(
            tenant_id=tenant_id,
            from_capability_id=from_capability_id,
            to_capability_id=to_capability_id,
            kind=kind,
        )
        self.db.add(edge)
        self.db.commit()
        return edge

    # ── Evaluations ────────────────────────────────────────────────────────────

    def add_evaluation(
        self,
        capability_id: str,
        *,
        tenant_id: str,
        evaluation: CapabilityEvaluation,
    ) -> CapabilityEvaluationRow:
        row = evaluation_to_row(
            evaluation, capability_id=capability_id, tenant_id=tenant_id
        )
        self.db.add(row)
        self.db.commit()
        return row

    # ── Internals ─────────────────────────────────────────────────────────────

    def _generate_embeddings(
        self, row: CapabilityRow, cap: SearchCapability
    ) -> int:
        """Generate and store all embeddings for a capability.

        Kinds:
        * ``description``     — embedding of ``description_long``
        * ``positive_example`` — one embedding per positive example
        * ``negative_example`` — one embedding per negative example
        * ``combined``        — embedding of the combined text
          (used as the default for semantic search)
        """
        tenant_id = row.tenant_id
        count = 0

        # 1. Description embedding
        desc_vec = self.embedder.encode_one(cap.description_long)
        self.embedding_store.store_embedding(
            self.db,
            capability_id=row.id,
            tenant_id=tenant_id,
            kind="description",
            vector=desc_vec,
            source_text=cap.description_long,
        )
        count += 1

        # 2. Positive examples
        for i, ex in enumerate(cap.positive_examples):
            vec = self.embedder.encode_one(ex)
            self.embedding_store.store_embedding(
                self.db,
                capability_id=row.id,
                tenant_id=tenant_id,
                kind="positive_example",
                vector=vec,
                source_text=ex,
                example_index=i,
            )
            count += 1

        # 3. Negative examples
        for i, ex in enumerate(cap.negative_examples):
            vec = self.embedder.encode_one(ex)
            self.embedding_store.store_embedding(
                self.db,
                capability_id=row.id,
                tenant_id=tenant_id,
                kind="negative_example",
                vector=vec,
                source_text=ex,
                example_index=i,
            )
            count += 1

        # 4. Combined text (the canonical retrieval embedding)
        combined_text = build_combined_text(
            display_name=cap.display_name,
            description_long=cap.description_long,
            domains=cap.domains,
            tags=cap.tags,
            keywords_en=cap.keywords_en,
            keywords_ar=cap.keywords_ar,
            synonyms=cap.synonyms,
            positive_examples=cap.positive_examples,
        )
        combined_vec = self.embedder.encode_one(combined_text)
        self.embedding_store.store_embedding(
            self.db,
            capability_id=row.id,
            tenant_id=tenant_id,
            kind="combined",
            vector=combined_vec,
            source_text=combined_text,
        )
        count += 1

        return count

    def _text_similarity(self, query: str, cap: SearchCapability) -> float:
        """Token-overlap similarity between query and capability keywords/tags.

        Returns a float in [0, 1]. Uses a simple Jaccard-like measure on
        lowercased tokens. Multilingual: queries in Arabic will match
        Arabic keywords, English will match English.
        """
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return 0.0
        cap_tokens = set()
        for kw in cap.keywords_en + cap.keywords_ar + cap.synonyms + cap.tags:
            cap_tokens.update(self._tokenize(kw))
        # Also include display_name tokens
        cap_tokens.update(self._tokenize(cap.display_name))
        if not cap_tokens:
            return 0.0
        overlap = query_tokens & cap_tokens
        if not overlap:
            return 0.0
        # Jaccard-like, but weighted toward query coverage
        return len(overlap) / len(query_tokens)

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        """Tokenize text for keyword matching.

        Lowercases, splits on whitespace and punctuation. Preserves Arabic
        and English tokens equally.
        """
        import re

        # Match runs of letters/digits (Unicode-aware: \w matches Arabic too)
        tokens = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
        # Filter out very short tokens (length < 2) to reduce noise
        return {t for t in tokens if len(t) >= 2}

    def _semantic_similarity(
        self, query_vec: Vector, row: CapabilityRow, *, tenant_id: str
    ) -> float:
        """Cosine similarity between query and the capability's combined embedding."""
        results = self.embedding_store.search_similar(
            self.db,
            query_vector=query_vec,
            tenant_id=tenant_id,
            kind="combined",
            top_k=1,
            min_similarity=-1.0,  # we want the score even if low
        )
        # Find the result matching this capability
        for emb_row, sim in results:
            if emb_row.capability_id == row.id:
                return float(sim)
        # Fallback: compute directly from the stored vector
        stmt = select(CapabilityEmbeddingRow).where(
            CapabilityEmbeddingRow.capability_id == row.id,
            CapabilityEmbeddingRow.kind == "combined",
        )
        emb = self.db.execute(stmt).scalar_one_or_none()
        if emb is None:
            return 0.0
        v = np.array(emb.vector_json, dtype=np.float32)
        q = query_vec / (np.linalg.norm(query_vec) + 1e-12)
        v_norm = v / (np.linalg.norm(v) + 1e-12)
        return float(q @ v_norm)

    def _example_similarities(
        self, query_vec_norm: Vector, capability_id: str, tenant_id: str, *, kind: str
    ) -> list[float]:
        """Return cosine similarities between the (normalized) query vector and
        each stored example embedding of the given kind."""
        stmt = select(CapabilityEmbeddingRow).where(
            CapabilityEmbeddingRow.capability_id == capability_id,
            CapabilityEmbeddingRow.tenant_id == tenant_id,
            CapabilityEmbeddingRow.kind == kind,
        )
        rows = list(self.db.execute(stmt).scalars())
        if not rows:
            return []
        matrix = np.array([r.vector_json for r in rows], dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-12
        matrix_norm = matrix / norms
        sims = matrix_norm @ query_vec_norm
        return [float(s) for s in sims]


__all__ = [
    "CapabilityRegistry",
    "CapabilitySearchHit",
    "CapabilitySearchResult",
    "SearchStageTrace",
]
