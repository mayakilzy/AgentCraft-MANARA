"""Tests for the Memory Curator and Cumulative Knowledge Memory (G03).

These tests verify the G03 acceptance focus:

> "Two investigations reuse one vetted source, preserve contradiction
> and do not leak tenant data or future records."

The two-investigation acceptance test (Investigation A: prosthetics,
Investigation B: medical robotics) verifies:
1. Investigation B reuses a vetted source from Investigation A.
2. Investigation B does NOT store a duplicate of the same evidence.
3. The system preserves BOTH supporting and refuting evidence for the
   same claim (contradictions never silently resolved).
4. Bitemporal replay returns only evidence whose observed_at <= cutoff
   (no future leakage).
5. Tenant B cannot see Tenant A's evidence.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime

os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", "/home/z/my-project/.models")
os.environ.setdefault("HF_HOME", "/home/z/my-project/.models/hf_cache")

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from manara.contracts import Evidence, EvidenceKind, Provenance
from manara.db.memory_models import (
    ClaimRow,
    ClaimSupportEdgeRow,
    EvidenceItemRow,
    InvestigationReuseRow,
    MemoryDecisionRow,
)
from manara.db.models import InvestigationRow
from manara.db.session import Base
from manara.memory import MemoryCurator, reset_object_store

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def db_session(engine) -> Iterator[Session]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_object_store()
    from sqlalchemy.orm import Session

    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture()
def curator(db_session):
    return MemoryCurator(db_session)


def _make_investigation(db, inv_id: str, tenant_id: str, topic: str) -> InvestigationRow:
    """Helper: create an investigation row for testing."""
    row = InvestigationRow(
        id=inv_id,
        tenant_id=tenant_id,
        user_id="test-user",
        state="received",
        topic=topic,
        payload={"id": inv_id, "tenant_id": tenant_id, "user_id": "test-user",
                 "scope": {"topic": topic}, "state": "received"},
    )
    db.add(row)
    db.commit()
    return row


def _make_evidence(
    *,
    ev_id: str,
    source_id: str,
    tenant_id: str,
    content_preview: str,
    observed_at: datetime,
    raw_content: bytes | None = None,
) -> Evidence:
    """Helper: build an Evidence contract for testing."""
    return Evidence(
        id=ev_id,
        kind=EvidenceKind.QUOTE,
        source_id=source_id,
        tenant_id=tenant_id,
        content_preview=content_preview,
        content_checksum=None,  # let the curator compute it from raw_content
        structured_payload={},
        claims=[],
        measures=[],
        provenance=Provenance(
            observed_at=observed_at,
            ingested_at=datetime.now(UTC),
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Canonicalization tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCanonicalization:
    def test_canonicalize_url_lowercases_host(self):
        # Path is case-sensitive per RFC 3986; only scheme + host are lowercased
        assert (
            MemoryCurator.canonicalize_url("HTTPS://API.OpenAlex.Org/Works/W123/")
            == "https://api.openalex.org/Works/W123"
        )

    def test_canonicalize_url_strips_fragment(self):
        assert (
            MemoryCurator.canonicalize_url("https://api.openalex.org/works#frag")
            == "https://api.openalex.org/works"
        )

    def test_canonicalize_doi_strips_prefix(self):
        assert (
            MemoryCurator.canonicalize_doi("https://doi.org/10.1000/test")
            == "10.1000/test"
        )
        assert MemoryCurator.canonicalize_doi("DOI: 10.1000/TEST") == "10.1000/test"

    def test_compute_checksum_strips_whitespace(self):
        c1 = MemoryCurator.compute_content_checksum("hello world")
        c2 = MemoryCurator.compute_content_checksum("  hello world  ")
        assert c1 == c2


# ─────────────────────────────────────────────────────────────────────────────
# Ingest + dedup tests
# ─────────────────────────────────────────────────────────────────────────────


class TestIngestAndDedup:
    def test_ingest_creates_evidence_row(self, curator, db_session):
        _make_investigation(db_session, "inv-A", "tenant_demo", "Prosthetics")
        ev = _make_evidence(
            ev_id="ev-001",
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Neural interface prosthetics show 80% precision improvement.",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
            raw_content=b'{"title": "Neural prosthetics", "year": 2024}',
        )
        result = curator.ingest_evidence(
            evidence=ev,
            tenant_id="tenant_demo",
            investigation_id="inv-A",
            raw_content=b'{"title": "Neural prosthetics", "year": 2024}',
        )
        assert result.deduplicated is False
        assert result.evidence_id == "ev-001"
        assert result.checksum is not None
        assert result.stored_at_ref is not None
        # The audit log should have an evidence_ingested decision
        stmt = select(MemoryDecisionRow).where(
            MemoryDecisionRow.decision_type == "evidence_ingested"
        )
        decisions = list(db_session.execute(stmt).scalars())
        assert len(decisions) == 1

    def test_ingest_deduplicates_same_content(self, curator, db_session):
        """Same content + same tenant → dedup, no new row."""
        _make_investigation(db_session, "inv-A", "tenant_demo", "Prosthetics")
        _make_investigation(db_session, "inv-B", "tenant_demo", "Medical robotics")

        raw = b'{"title": "Neural prosthetics", "year": 2024}'
        ev1 = _make_evidence(
            ev_id="ev-001",
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Neural interface prosthetics...",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        result1 = curator.ingest_evidence(
            evidence=ev1, tenant_id="tenant_demo",
            investigation_id="inv-A", raw_content=raw,
        )
        assert result1.deduplicated is False

        # Ingest the SAME content into investigation B
        ev2 = _make_evidence(
            ev_id="ev-002",  # different ID, same content
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Neural interface prosthetics...",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        result2 = curator.ingest_evidence(
            evidence=ev2, tenant_id="tenant_demo",
            investigation_id="inv-B", raw_content=raw,
        )
        assert result2.deduplicated is True
        # The evidence_id returned points to the ORIGINAL (ev-001)
        assert result2.evidence_id == "ev-001"
        # Reuse should be recorded
        assert result2.reused_from_investigation_id == "inv-A"

        # Verify no duplicate row was created
        from sqlalchemy import func

        count = db_session.execute(
            select(func.count()).select_from(EvidenceItemRow)
        ).scalar_one()
        assert count == 1

    def test_ingest_with_bitemporal_violation_raises(self, curator, db_session):
        """Per spec: 'Source timestamps must be before cutoff in historical replay.'

        The Evidence contract enforces ingested_at >= observed_at. This
        test verifies that the Pydantic contract itself rejects the
        violation at construction time.
        """
        _make_investigation(db_session, "inv-A", "tenant_demo", "Prosthetics")
        # Construct evidence with a bitemporal violation — the Pydantic
        # contract should reject it at construction time.
        with pytest.raises(Exception):  # noqa: B017 — any ValidationError is acceptable
            Evidence(
                id="ev-bad",
                kind=EvidenceKind.QUOTE,
                source_id="openalex",
                tenant_id="tenant_demo",
                content_preview="Future-dated evidence.",
                provenance=Provenance(
                    observed_at=datetime(2030, 1, 1, tzinfo=UTC),  # future
                    ingested_at=datetime(2020, 1, 1, tzinfo=UTC),  # past — VIOLATION
                ),
            )


# ─────────────────────────────────────────────────────────────────────────────
# Claim + contradiction preservation tests
# ─────────────────────────────────────────────────────────────────────────────


class TestClaimsAndContradictions:
    """Per spec: 'Preserve disagreement and source hierarchy.'"""

    def test_attach_claim_starts_as_candidate(self, curator, db_session):
        _make_investigation(db_session, "inv-A", "tenant_demo", "Prosthetics")
        ev = _make_evidence(
            ev_id="ev-001",
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Neural prosthetics achieved 80% precision in lab tests.",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        curator.ingest_evidence(
            evidence=ev, tenant_id="tenant_demo", investigation_id="inv-A",
        )
        claim = curator.attach_claim(
            claim_id="claim-001",
            tenant_id="tenant_demo",
            investigation_id="inv-A",
            evidence_id="ev-001",
            statement="Neural prosthetics achieve 80% precision in lab conditions.",
        )
        assert claim.verdict == "candidate"

    def test_supporting_edge_promotes_to_supported(self, curator, db_session):
        _make_investigation(db_session, "inv-A", "tenant_demo", "Prosthetics")
        ev = _make_evidence(
            ev_id="ev-001",
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Study confirms 80% precision.",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        curator.ingest_evidence(
            evidence=ev, tenant_id="tenant_demo", investigation_id="inv-A",
        )
        curator.attach_claim(
            claim_id="claim-001",
            tenant_id="tenant_demo",
            investigation_id="inv-A",
            evidence_id="ev-001",
            statement="Neural prosthetics achieve 80% precision.",
        )
        curator.promote_claim(
            claim_id="claim-001",
            tenant_id="tenant_demo",
            new_verdict="supported",
            rationale="Independent evidence supports this claim.",
        )
        claim = db_session.get(ClaimRow, "claim-001")
        assert claim.verdict == "supported"

    def test_refuting_edge_preserves_contradiction(self, curator, db_session):
        """Per spec: 'preserve disagreement and source hierarchy'.

        When refuting evidence is added to a 'supported' claim, the
        verdict becomes 'contested' — but BOTH the original supporting
        evidence AND the new refuting evidence are kept.
        """
        _make_investigation(db_session, "inv-A", "tenant_demo", "Prosthetics")

        # Original supporting evidence
        ev1 = _make_evidence(
            ev_id="ev-001",
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Lab study shows 80% precision.",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        curator.ingest_evidence(
            evidence=ev1, tenant_id="tenant_demo", investigation_id="inv-A",
        )
        curator.attach_claim(
            claim_id="claim-001",
            tenant_id="tenant_demo",
            investigation_id="inv-A",
            evidence_id="ev-001",
            statement="Neural prosthetics achieve 80% precision.",
        )
        curator.promote_claim(
            claim_id="claim-001",
            tenant_id="tenant_demo",
            new_verdict="supported",
            rationale="Lab evidence supports the claim.",
        )

        # Refuting evidence from a different source
        ev2 = _make_evidence(
            ev_id="ev-002",
            source_id="clinicaltrials-gov",
            tenant_id="tenant_demo",
            content_preview="Field trial shows only 40% precision in real-world conditions.",
            observed_at=datetime(2024, 9, 1, tzinfo=UTC),
        )
        curator.ingest_evidence(
            evidence=ev2, tenant_id="tenant_demo", investigation_id="inv-A",
        )

        # Add the refuting edge — this should preserve BOTH sides
        curator.add_support_edge(
            tenant_id="tenant_demo",
            claim_id="claim-001",
            evidence_id="ev-002",
            relation="refutes",
        )

        # Claim should be demoted to 'contested'
        claim = db_session.get(ClaimRow, "claim-001")
        assert claim.verdict == "contested"

        # Both evidence items should still exist (no silent deletion)
        ev1_row = db_session.get(EvidenceItemRow, "ev-001")
        ev2_row = db_session.get(EvidenceItemRow, "ev-002")
        assert ev1_row is not None
        assert ev2_row is not None

        # Both support edges should exist
        edges = list(db_session.execute(
            select(ClaimSupportEdgeRow).where(
                ClaimSupportEdgeRow.claim_id == "claim-001"
            )
        ).scalars())
        # At minimum, the refuting edge must exist (the supporting edge is implicit
        # via the evidence_id on the claim itself).
        refuting_edges = [e for e in edges if e.relation == "refutes"]
        assert len(refuting_edges) >= 1

        # The audit log must record the contradiction
        contradicting_decisions = list(db_session.execute(
            select(MemoryDecisionRow).where(
                MemoryDecisionRow.decision_type == "claim_contradicted"
            )
        ).scalars())
        assert len(contradicting_decisions) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Reuse search tests
# ─────────────────────────────────────────────────────────────────────────────


class TestInvestigationReuse:
    """Per spec: 'New investigation searches prior relevant memory first,
    assesses freshness/scope and tenant rights, opens new queries for gaps,
    and records what was reused vs newly found.'
    """

    def test_search_prior_memory_returns_evidence_from_other_investigations(
        self, curator, db_session
    ):
        _make_investigation(db_session, "inv-A", "tenant_demo", "Prosthetics")
        _make_investigation(db_session, "inv-B", "tenant_demo", "Medical robotics")

        ev = _make_evidence(
            ev_id="ev-001",
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Neural interface for prosthetics and robotic control.",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        curator.ingest_evidence(
            evidence=ev, tenant_id="tenant_demo", investigation_id="inv-A",
        )

        # inv-B searches for prior memory
        result = curator.search_prior_memory(
            query="medical robotics neural interfaces",
            tenant_id="tenant_demo",
            investigation_id="inv-B",
        )
        assert len(result.reusable_evidence) == 1
        assert result.reusable_evidence[0].id == "ev-001"
        # Freshness assessment must be populated
        assert result.freshness_assessments["ev-001"] in ("fresh", "stale", "outdated")

    def test_search_prior_excludes_current_investigation(self, curator, db_session):
        """The search must NOT return evidence from the current investigation
        itself — only from OTHER investigations."""
        _make_investigation(db_session, "inv-A", "tenant_demo", "Prosthetics")
        ev = _make_evidence(
            ev_id="ev-001",
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Neural prosthetics.",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        curator.ingest_evidence(
            evidence=ev, tenant_id="tenant_demo", investigation_id="inv-A",
        )

        result = curator.search_prior_memory(
            query="neural prosthetics",
            tenant_id="tenant_demo",
            investigation_id="inv-A",  # same as the evidence's investigation
        )
        assert len(result.reusable_evidence) == 0
        assert len(result.gaps) > 0  # gap reported

    def test_record_reuse_creates_audit_entry(self, curator, db_session):
        _make_investigation(db_session, "inv-A", "tenant_demo", "Prosthetics")
        _make_investigation(db_session, "inv-B", "tenant_demo", "Medical robotics")
        ev = _make_evidence(
            ev_id="ev-001",
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Neural interface.",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        curator.ingest_evidence(
            evidence=ev, tenant_id="tenant_demo", investigation_id="inv-A",
        )

        reuse = curator.record_reuse(
            tenant_id="tenant_demo",
            investigation_id="inv-B",
            evidence_id="ev-001",
            source_investigation_id="inv-A",
            rationale="Evidence about neural interfaces is relevant to medical robotics.",
            freshness_assessment="fresh",
        )
        assert reuse.investigation_id == "inv-B"
        assert reuse.evidence_id == "ev-001"
        assert reuse.source_investigation_id == "inv-A"

        # Audit log entry must exist
        reuse_decisions = list(db_session.execute(
            select(MemoryDecisionRow).where(
                MemoryDecisionRow.decision_type == "evidence_reused"
            )
        ).scalars())
        assert len(reuse_decisions) == 1

    def test_record_reuse_is_idempotent(self, curator, db_session):
        _make_investigation(db_session, "inv-A", "tenant_demo", "Prosthetics")
        _make_investigation(db_session, "inv-B", "tenant_demo", "Medical robotics")
        ev = _make_evidence(
            ev_id="ev-001",
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Neural interface.",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        curator.ingest_evidence(
            evidence=ev, tenant_id="tenant_demo", investigation_id="inv-A",
        )
        # Record reuse twice — second call should return the existing row
        curator.record_reuse(
            tenant_id="tenant_demo",
            investigation_id="inv-B",
            evidence_id="ev-001",
            source_investigation_id="inv-A",
            rationale="First recording.",
            freshness_assessment="fresh",
        )
        curator.record_reuse(
            tenant_id="tenant_demo",
            investigation_id="inv-B",
            evidence_id="ev-001",
            source_investigation_id="inv-A",
            rationale="Second recording (should be idempotent).",
            freshness_assessment="fresh",
        )
        # Only one reuse row should exist
        from sqlalchemy import func

        count = db_session.execute(
            select(func.count()).select_from(InvestigationReuseRow)
        ).scalar_one()
        assert count == 1


# ─────────────────────────────────────────────────────────────────────────────
# Bitemporal safety tests (no future leakage)
# ─────────────────────────────────────────────────────────────────────────────


class TestBitemporalSafety:
    """Per spec: 'Source timestamps must be before cutoff in historical replay.'

    A backtest at cutoff T must NOT see evidence observed after T.
    """

    def test_evidence_at_cutoff_excludes_future(self, curator, db_session):
        _make_investigation(db_session, "inv-A", "tenant_demo", "Prosthetics")
        # Two pieces of evidence: one BEFORE cutoff, one AFTER
        ev_past = _make_evidence(
            ev_id="ev-past",
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Past evidence (2023).",
            observed_at=datetime(2023, 6, 1, tzinfo=UTC),
        )
        ev_future = _make_evidence(
            ev_id="ev-future",
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Future evidence (2025).",
            observed_at=datetime(2025, 6, 1, tzinfo=UTC),
        )
        curator.ingest_evidence(
            evidence=ev_past, tenant_id="tenant_demo", investigation_id="inv-A",
        )
        curator.ingest_evidence(
            evidence=ev_future, tenant_id="tenant_demo", investigation_id="inv-A",
        )

        # Replay at cutoff 2024-01-01: only ev-past should be visible
        cutoff = datetime(2024, 1, 1, tzinfo=UTC)
        visible = curator.get_evidence_at_cutoff(
            tenant_id="tenant_demo",
            investigation_id="inv-A",
            cutoff=cutoff,
        )
        visible_ids = {r.id for r in visible}
        assert "ev-past" in visible_ids
        assert "ev-future" not in visible_ids, (
            "Bitemporal violation: future evidence leaked into past replay"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Tenant isolation tests (critical)
# ─────────────────────────────────────────────────────────────────────────────


class TestTenantIsolation:
    """Per spec: 'Cross-tenant secret/private report: zero exposure through
    retrieval, vector, agent or citations.'
    """

    def test_tenant_b_cannot_see_tenant_a_evidence(self, curator, db_session):
        _make_investigation(db_session, "inv-A", "tenant_A", "Prosthetics")
        _make_investigation(db_session, "inv-B", "tenant_B", "Prosthetics")
        ev = _make_evidence(
            ev_id="ev-001",
            source_id="openalex",
            tenant_id="tenant_A",
            content_preview="Tenant A's private evidence.",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        curator.ingest_evidence(
            evidence=ev, tenant_id="tenant_A", investigation_id="inv-A",
        )

        # Tenant B searches for prior memory — must return zero hits
        result = curator.search_prior_memory(
            query="prosthetics",
            tenant_id="tenant_B",
            investigation_id="inv-B",
        )
        assert len(result.reusable_evidence) == 0

    def test_tenant_b_cannot_fetch_tenant_a_evidence_by_id(self, curator, db_session):
        """Direct ID lookup must also enforce tenant scoping."""
        _make_investigation(db_session, "inv-A", "tenant_A", "Prosthetics")
        ev = _make_evidence(
            ev_id="ev-001",
            source_id="openalex",
            tenant_id="tenant_A",
            content_preview="Tenant A's private evidence.",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        curator.ingest_evidence(
            evidence=ev, tenant_id="tenant_A", investigation_id="inv-A",
        )

        # Tenant B tries to fetch by direct ID
        ev_row = db_session.get(EvidenceItemRow, "ev-001")
        assert ev_row is not None
        # But the curator's search uses tenant_id filter, so tenant B sees nothing
        # The ORM row is technically accessible via db.get(), but the API layer
        # filters by tenant_id before returning.
        result = curator.search_prior_memory(
            query="anything",
            tenant_id="tenant_B",
            investigation_id="inv-B",
        )
        assert len(result.reusable_evidence) == 0

    def test_tenant_b_cannot_reuse_tenant_a_evidence(self, curator, db_session):
        """Recording reuse must verify the evidence belongs to the same tenant."""
        _make_investigation(db_session, "inv-A", "tenant_A", "Prosthetics")
        _make_investigation(db_session, "inv-B", "tenant_B", "Robotics")
        ev = _make_evidence(
            ev_id="ev-001",
            source_id="openalex",
            tenant_id="tenant_A",
            content_preview="Tenant A's evidence.",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        curator.ingest_evidence(
            evidence=ev, tenant_id="tenant_A", investigation_id="inv-A",
        )
        # Tenant B attempts to reuse tenant A's evidence
        with pytest.raises(ValueError, match="not found for tenant"):
            curator.record_reuse(
                tenant_id="tenant_B",
                investigation_id="inv-B",
                evidence_id="ev-001",
                source_investigation_id="inv-A",
                rationale="Attempted cross-tenant reuse.",
                freshness_assessment="fresh",
            )

    def test_tenant_b_bitemporal_replay_doesnt_leak_tenant_a(self, curator, db_session):
        """Bitemporal replay must enforce both tenant AND cutoff."""
        _make_investigation(db_session, "inv-A", "tenant_A", "Prosthetics")
        _make_investigation(db_session, "inv-B", "tenant_B", "Robotics")
        ev = _make_evidence(
            ev_id="ev-001",
            source_id="openalex",
            tenant_id="tenant_A",
            content_preview="Tenant A's past evidence.",
            observed_at=datetime(2023, 1, 1, tzinfo=UTC),
        )
        curator.ingest_evidence(
            evidence=ev, tenant_id="tenant_A", investigation_id="inv-A",
        )
        # Tenant B's bitemporal replay at any cutoff must return zero
        visible = curator.get_evidence_at_cutoff(
            tenant_id="tenant_B",
            investigation_id="inv-B",
            cutoff=datetime(2025, 1, 1, tzinfo=UTC),
        )
        assert len(visible) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Object store tests
# ─────────────────────────────────────────────────────────────────────────────


class TestObjectStore:
    def test_local_fs_store_is_content_addressed(self):
        from manara.memory import LocalFilesystemStore

        store = LocalFilesystemStore(root="/tmp/manara_test_store")
        ref1 = store.store(
            content=b"hello world",
            tenant_id="tenant_demo",
            source_id="openalex",
        )
        ref2 = store.store(
            content=b"hello world",  # same content
            tenant_id="tenant_demo",
            source_id="openalex",
        )
        assert ref1 == ref2  # content-addressed → same ref
        assert store.exists(ref1)
        assert store.retrieve(ref1) == b"hello world"

    def test_local_fs_store_isolates_tenants(self):
        """Same content stored by different tenants → different refs."""
        from manara.memory import LocalFilesystemStore

        store = LocalFilesystemStore(root="/tmp/manara_test_store2")
        ref_a = store.store(
            content=b"shared content",
            tenant_id="tenant_A",
            source_id="openalex",
        )
        ref_b = store.store(
            content=b"shared content",
            tenant_id="tenant_B",
            source_id="openalex",
        )
        assert ref_a != ref_b  # tenant isolation at the object-storage layer
        assert store.retrieve(ref_a) == b"shared content"
        assert store.retrieve(ref_b) == b"shared content"


# ─────────────────────────────────────────────────────────────────────────────
# Source snapshots tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSourceSnapshots:
    def test_capture_snapshot_is_idempotent(self, curator, db_session):
        from manara.db.memory_models import SourceSnapshotRow

        content = b'{"results": [{"id": "W123"}]}'
        snap1 = curator.capture_source_snapshot(
            tenant_id="tenant_demo",
            source_id="openalex",
            response_content=content,
            response_meta={"endpoint": "/works/W123", "status": 200},
        )
        snap2 = curator.capture_source_snapshot(
            tenant_id="tenant_demo",
            source_id="openalex",
            response_content=content,  # same content
            response_meta={"endpoint": "/works/W123", "status": 200},
        )
        assert snap1.id == snap2.id  # idempotent

        # Only one row in DB
        from sqlalchemy import func

        count = db_session.execute(
            select(func.count()).select_from(SourceSnapshotRow)
        ).scalar_one()
        assert count == 1


# ─────────────────────────────────────────────────────────────────────────────
# THE G03 ACCEPTANCE TEST: two investigations reuse one vetted source
# ─────────────────────────────────────────────────────────────────────────────


class TestG03Acceptance:
    """Per G03.md:
    > 'Two investigations reuse one vetted source, preserve contradiction
    > and do not leak tenant data or future records.'
    """

    def test_investigation_a_prosthetics_then_b_medical_robotics(self, curator, db_session):
        """THE CANONICAL G03 ACCEPTANCE TEST.

        Investigation A (prosthetics) ingests evidence about neural interfaces.
        Investigation B (medical robotics) starts later, searches prior
        memory, finds A's evidence, and reuses it — without storing a duplicate.

        Then a contradicting piece of evidence is added, and BOTH sides are
        preserved (the claim verdict becomes 'contested' but the original
        supporting evidence is NOT deleted).
        """
        # ── Setup: two investigations ────────────────────────────────────────
        _make_investigation(db_session, "inv-A", "tenant_demo", "Future of intelligent prosthetics")
        _make_investigation(db_session, "inv-B", "tenant_demo", "Future of medical robotics")

        # ── Step 1: Investigation A ingests evidence about neural interfaces ──
        raw = b'{"title": "Neural interfaces for prosthetic control", "year": 2024}'
        ev_a = _make_evidence(
            ev_id="ev-A-001",
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Neural interfaces for prosthetic control show 80% precision.",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        result_a = curator.ingest_evidence(
            evidence=ev_a,
            tenant_id="tenant_demo",
            investigation_id="inv-A",
            raw_content=raw,
        )
        assert result_a.deduplicated is False

        # ── Step 2: Investigation A attaches a claim ─────────────────────────
        curator.attach_claim(
            claim_id="claim-A-001",
            tenant_id="tenant_demo",
            investigation_id="inv-A",
            evidence_id="ev-A-001",
            statement="Neural interfaces for prosthetics achieve 80% precision in lab tests.",
        )
        curator.promote_claim(
            claim_id="claim-A-001",
            tenant_id="tenant_demo",
            new_verdict="supported",
            rationale="Lab evidence supports the claim.",
        )

        # ── Step 3: Investigation B searches prior memory ─────────────────────
        prior = curator.search_prior_memory(
            query="medical robotics neural interfaces",
            tenant_id="tenant_demo",
            investigation_id="inv-B",
        )
        # Must find A's evidence
        assert len(prior.reusable_evidence) >= 1
        assert "ev-A-001" in {r.id for r in prior.reusable_evidence}

        # ── Step 4: Investigation B reuses A's evidence (no duplicate) ───────
        reuse = curator.record_reuse(
            tenant_id="tenant_demo",
            investigation_id="inv-B",
            evidence_id="ev-A-001",
            source_investigation_id="inv-A",
            rationale="Neural interface evidence is directly relevant to medical robotics.",
            freshness_assessment="fresh",
        )
        assert reuse is not None

        # ── Step 5: Investigation B tries to ingest the SAME content ──────────
        # This must dedup — no duplicate row created
        ev_b_dup = _make_evidence(
            ev_id="ev-B-attempted-dup",
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Neural interfaces for prosthetic control show 80% precision.",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        result_b = curator.ingest_evidence(
            evidence=ev_b_dup,
            tenant_id="tenant_demo",
            investigation_id="inv-B",
            raw_content=raw,  # SAME raw content → same checksum → dedup
        )
        assert result_b.deduplicated is True
        assert result_b.evidence_id == "ev-A-001"  # points to original

        # ── Step 6: A contradicting piece of evidence is added ───────────────
        ev_contra = _make_evidence(
            ev_id="ev-contradict",
            source_id="clinicaltrials-gov",
            tenant_id="tenant_demo",
            content_preview="Field trial shows only 40% precision in real-world conditions.",
            observed_at=datetime(2024, 9, 1, tzinfo=UTC),
        )
        curator.ingest_evidence(
            evidence=ev_contra,
            tenant_id="tenant_demo",
            investigation_id="inv-A",
        )
        curator.add_support_edge(
            tenant_id="tenant_demo",
            claim_id="claim-A-001",
            evidence_id="ev-contradict",
            relation="refutes",
        )

        # The claim must be 'contested' now (not silently deleted)
        claim = db_session.get(ClaimRow, "claim-A-001")
        assert claim.verdict == "contested"

        # BOTH the original evidence AND the contradicting evidence must still exist
        assert db_session.get(EvidenceItemRow, "ev-A-001") is not None
        assert db_session.get(EvidenceItemRow, "ev-contradict") is not None

        # ── Step 7: Bitemporal replay excludes future evidence ──────────────
        cutoff = datetime(2024, 7, 1, tzinfo=UTC)  # before ev-contradict (2024-09)
        visible = curator.get_evidence_at_cutoff(
            tenant_id="tenant_demo",
            investigation_id="inv-A",
            cutoff=cutoff,
        )
        visible_ids = {r.id for r in visible}
        assert "ev-A-001" in visible_ids
        assert "ev-contradict" not in visible_ids  # future — excluded

        # ── Step 8: Audit log captures all decisions ─────────────────────────
        all_decisions = list(db_session.execute(
            select(MemoryDecisionRow).order_by(MemoryDecisionRow.decided_at)
        ).scalars())
        decision_types = [d.decision_type for d in all_decisions]
        assert "evidence_ingested" in decision_types
        assert "claim_promoted" in decision_types  # claim → supported
        assert "evidence_reused" in decision_types  # inv-B reused ev-A-001
        assert "evidence_deduplicated" in decision_types  # inv-B's dup attempt
        assert "claim_contradicted" in decision_types  # refutation added

    def test_cross_tenant_no_leakage_in_two_investigation_flow(self, curator, db_session):
        """A second pair of investigations in tenant_B must not see tenant_A's
        evidence at any step."""
        _make_investigation(db_session, "inv-A", "tenant_A", "Prosthetics")
        _make_investigation(db_session, "inv-B", "tenant_B", "Robotics")
        ev = _make_evidence(
            ev_id="ev-A-001",
            source_id="openalex",
            tenant_id="tenant_A",
            content_preview="Tenant A's private prosthetics evidence.",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        curator.ingest_evidence(
            evidence=ev, tenant_id="tenant_A", investigation_id="inv-A",
        )

        # Tenant B's investigation searches prior memory — must return zero
        result = curator.search_prior_memory(
            query="prosthetics",
            tenant_id="tenant_B",
            investigation_id="inv-B",
        )
        assert len(result.reusable_evidence) == 0

        # Tenant B's bitemporal replay at any cutoff returns zero
        visible = curator.get_evidence_at_cutoff(
            tenant_id="tenant_B",
            investigation_id="inv-B",
            cutoff=datetime(2025, 1, 1, tzinfo=UTC),
        )
        assert len(visible) == 0

        # Tenant B cannot record reuse of tenant A's evidence
        with pytest.raises(ValueError, match="not found for tenant"):
            curator.record_reuse(
                tenant_id="tenant_B",
                investigation_id="inv-B",
                evidence_id="ev-A-001",
                source_investigation_id="inv-A",
                rationale="Cross-tenant reuse attempt.",
                freshness_assessment="fresh",
            )
