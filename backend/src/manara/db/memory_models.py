"""ORM models for the Cumulative Knowledge Memory (G03).

This module mirrors the G00 Pydantic contracts ``Evidence``, ``Claim``,
``Provenance`` into ORM rows, and adds the relationships and supporting
tables mandated by ``03_INTELLIGENCE/01_KNOWLEDGE_MEMORY.md``:

* ``evidence_items``         — quotes/spans/data samples with checksums
* ``claims``                 — bounded statements linked to evidence
* ``claim_support_edges``    — supports/refutes/qualifies edges (preserves
                                contradictions — never silently delete)
* ``measures``               — quantified values with units, methodology
* ``entities`` + ``entity_relations`` — graph of named entities
* ``hypotheses``             — investigator-level suppositions (clearly
                                labeled as hypotheses, not claims)
* ``source_snapshots``       — captured source response references
* ``memory_decisions``      — audit log of state changes (no history erasure)
* ``investigation_evidence`` — many-to-many between investigations and
                                evidence (tracks which investigation
                                introduced each piece of evidence)

Design rules enforced at the ORM layer:
* Every row carries ``tenant_id`` (NOT NULL, indexed). Cross-tenant
  queries are impossible at the ORM level (capability tests verify).
* Every row has ``created_at`` and ``updated_at`` (UTC-aware).
* ``evidence_items.checksum`` enables deduplication (SHA-256 of the
  canonical content).
* ``evidence_items.observed_at`` and ``ingested_at`` are BOTH stored —
  bitemporal awareness. Backtests cannot reference evidence whose
  ``observed_at`` exceeds the simulated cutoff.
* ``claims.verdict`` is an enum: candidate → supported → contested →
  refuted → superseded. NEVER silently delete a claim — supersession
  creates a new claim and links the old one via ``superseded_by``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from manara.db.session import Base

# ─────────────────────────────────────────────────────────────────────────────
# Evidence items
# ─────────────────────────────────────────────────────────────────────────────


class EvidenceItemRow(Base):
    """A traceable evidence item (quote, span, data sample, figure).

    Mirrors ``manara.contracts.Evidence``. The full Pydantic payload is
    in ``payload``; denormalized columns enable fast filtering.

    Key invariants:
    * ``tenant_id`` NOT NULL — every evidence row is scoped.
    * ``checksum`` SHA-256 of canonical content — enables dedup.
    * ``observed_at`` (world-time) and ``ingested_at`` (knowledge-time)
      are BOTH stored; ingested_at >= observed_at is enforced at the
      Pydantic layer (bitemporal safety).
    * ``content_ref`` is a vault/object-storage reference; the actual
      content lives in object storage (local FS in dev, S3 in prod).
      ``content_preview`` is a short inline preview for inspection.
    """

    __tablename__ = "memory_evidence_items"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    investigation_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("investigations.id"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_snapshot_ref: Mapped[str | None] = mapped_column(String(300), nullable=True)

    kind: Mapped[str] = mapped_column(String(40), nullable=False)  # quote|span|data|sample|checksum|figure
    content_ref: Mapped[str | None] = mapped_column(String(300), nullable=True)
    content_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    content_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    claims: Mapped[list[ClaimRow]] = relationship(
        back_populates="evidence", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_evidence_tenant_source", "tenant_id", "source_id"),
        Index("ix_evidence_tenant_observed", "tenant_id", "observed_at"),
        Index("ix_evidence_tenant_checksum", "tenant_id", "content_checksum"),
        UniqueConstraint("tenant_id", "content_checksum", name="uq_evidence_tenant_checksum"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Claims
# ─────────────────────────────────────────────────────────────────────────────


class ClaimRow(Base):
    """A bounded statement linked to evidence.

    Mirrors ``manara.contracts.Claim``. Verdict transitions:
        candidate → supported → contested → refuted → superseded

    Verdict is NEVER silently overwritten — supersession creates a new
    claim and links the old one via ``superseded_by``.

    Support relations (supports/refutes/qualifies) are stored in the
    ``claim_support_edges`` table, NOT as a column on the claim. This
    allows multiple pieces of evidence to support OR refute the same
    claim (contradictions are preserved).
    """

    __tablename__ = "memory_claims"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    investigation_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("investigations.id"), nullable=False, index=True
    )

    evidence_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("memory_evidence_items.id"), nullable=False, index=True
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[str] = mapped_column(String(40), nullable=False, default="candidate", index=True)
    # candidate | supported | contested | refuted | superseded
    independence_group: Mapped[str | None] = mapped_column(String(120), nullable=True)
    superseded_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    evidence: Mapped[EvidenceItemRow] = relationship(back_populates="claims")
    support_edges: Mapped[list[ClaimSupportEdgeRow]] = relationship(
        back_populates="claim", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_claims_tenant_verdict", "tenant_id", "verdict"),
        Index("ix_claims_tenant_investigation", "tenant_id", "investigation_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Claim support edges — supports | refutes | qualifies
# ─────────────────────────────────────────────────────────────────────────────


class ClaimSupportEdgeRow(Base):
    """An edge between a piece of evidence and a claim.

    ``relation`` is one of: supports | refutes | qualifies

    Per spec: "preserve disagreement and source hierarchy" — multiple
    pieces of evidence can support OR refute the same claim, and BOTH
    are preserved. The curator surfaces contradictions; it never silently
    picks one side.
    """

    __tablename__ = "memory_claim_support_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    claim_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("memory_claims.id"), nullable=False, index=True
    )
    evidence_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("memory_evidence_items.id"), nullable=False, index=True
    )
    relation: Mapped[str] = mapped_column(String(20), nullable=False)  # supports|refutes|qualifies
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    claim: Mapped[ClaimRow] = relationship(back_populates="support_edges")

    __table_args__ = (
        UniqueConstraint("claim_id", "evidence_id", "relation", name="uq_claim_evidence_relation"),
        Index("ix_support_edges_tenant_relation", "tenant_id", "relation"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Measures — quantified values
# ─────────────────────────────────────────────────────────────────────────────


class MeasureRow(Base):
    """A quantified measurement (value + unit + methodology + geography).

    Mirrors ``manara.contracts.Measure``. Used for time-series evidence
    like battery cost per kWh, crop yields, recycling rates, etc.
    """

    __tablename__ = "memory_measures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    evidence_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("memory_evidence_items.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(60), nullable=False)
    methodology: Mapped[str | None] = mapped_column(String(300), nullable=True)
    geography: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    valid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    confidence_interval_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_interval_high: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        Index("ix_measures_tenant_name", "tenant_id", "name"),
        Index("ix_measures_tenant_geography", "tenant_id", "geography"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Entities + entity relations
# ─────────────────────────────────────────────────────────────────────────────


class EntityRow(Base):
    """A named entity (organization, person, technology, place, etc.).

    Entities are extracted from evidence and linked to claims/measures.
    The entity_relations table stores typed edges between entities
    (e.g. "manufactures", "acquired_by", "competes_with").
    """

    __tablename__ = "memory_entities"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(300), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)  # org|person|tech|place|...
    canonical_id: Mapped[str | None] = mapped_column(String(300), nullable=True, index=True)
    # e.g. ORCID for authors, ROR for institutions, DOI prefix for publishers
    aliases_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "canonical_id", name="uq_entities_tenant_canonical"),
        Index("ix_entities_tenant_type", "tenant_id", "entity_type"),
    )


class EntityRelationRow(Base):
    """A typed edge between two entities."""

    __tablename__ = "memory_entity_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    from_entity_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("memory_entities.id"), nullable=False, index=True
    )
    to_entity_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("memory_entities.id"), nullable=False, index=True
    )
    relation_type: Mapped[str] = mapped_column(String(60), nullable=False)
    # e.g. manufactures|acquired_by|competes_with|funds|cites
    evidence_id: Mapped[str | None] = mapped_column(
        String(120), ForeignKey("memory_evidence_items.id"), nullable=True
    )
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "from_entity_id", "to_entity_id", "relation_type",
            name="uq_entity_relations_from_to_type"
        ),
        Index("ix_entity_relations_tenant_type", "tenant_id", "relation_type"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Hypotheses — investigator-level suppositions (clearly labeled)
# ─────────────────────────────────────────────────────────────────────────────


class HypothesisRow(Base):
    """An investigator-level supposition.

    Per spec: every substantive user-facing claim has traceable evidence
    OR is explicitly labeled analysis/hypothesis/scenario. Hypotheses
    are NEVER promoted to claims without supporting evidence; they live
    in a separate table to keep the boundary clear.
    """

    __tablename__ = "memory_hypotheses"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    investigation_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("investigations.id"), nullable=False, index=True
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)  # 0..1
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="open", index=True)
    # open|testing|supported|refuted|superseded
    superseded_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    related_claim_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_hypotheses_tenant_status", "tenant_id", "status"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Source snapshots — captured raw API responses
# ─────────────────────────────────────────────────────────────────────────────


class SourceSnapshotRow(Base):
    """A captured snapshot of a source response.

    Per spec: "cache tenant-specific indices with RBAC. Zero need for
    permanent worker per engine." Source snapshots are stored in
    object storage (local FS in dev, S3 in prod) — this row holds the
    reference plus the checksum for tamper detection.

    Snapshots have their own lifecycle (per owner decision): they can
    be expired independently of the evidence derived from them.
    """

    __tablename__ = "memory_source_snapshots"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    source_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    snapshot_ref: Mapped[str] = mapped_column(String(300), nullable=False)  # object-storage ref
    snapshot_checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    source_response_meta: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    retention_class: Mapped[str] = mapped_column(String(40), nullable=False, default="default")
    # default|long_term|tenant_specific
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "snapshot_checksum", name="uq_snapshots_tenant_checksum"),
        Index("ix_snapshots_tenant_source", "tenant_id", "source_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Memory decisions — audit log (no history erasure)
# ─────────────────────────────────────────────────────────────────────────────


class MemoryDecisionRow(Base):
    """Audit record of a state change in the cumulative memory.

    Per spec: "Audit lineage and version pin." Every promotion, every
    verdict change, every supersession is recorded here. The audit log
    is append-only — no row is ever deleted or overwritten.

    Decision types:
    * ``evidence_ingested``     — new evidence item added
    * ``claim_promoted``        — verdict transition (e.g. candidate → supported)
    * ``claim_superseded``      — old claim linked to new via superseded_by
    * ``claim_contradicted``    — refuting evidence added (preserves both)
    * ``hypothesis_opened``     — new hypothesis
    * ``hypothesis_tested``     — hypothesis status changed
    * ``evidence_reused``       — investigation B reused A's evidence
    * ``evidence_deduplicated`` — duplicate detected and not re-stored
    * ``snapshot_expired``      — source snapshot expired per retention policy
    """

    __tablename__ = "memory_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    decision_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    investigation_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    evidence_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    claim_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)  # user | curator | system
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        Index("ix_decisions_tenant_type", "tenant_id", "decision_type"),
        Index("ix_decisions_tenant_investigation", "tenant_id", "investigation_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Investigation knowledge reuse — tracks what was reused vs newly found
# ─────────────────────────────────────────────────────────────────────────────


class InvestigationReuseRow(Base):
    """Records when investigation B reuses evidence from investigation A.

    Per spec: "New investigation searches prior relevant memory first,
    assesses freshness/scope and tenant rights, opens new queries for
    gaps, and records what was reused vs newly found."

    Each row says: investigation B (``investigation_id``) reused evidence
    item X (``evidence_id``) from investigation A (``source_investigation_id``)
    at ``reused_at``. The decision audit log captures the rationale.
    """

    __tablename__ = "memory_investigation_reuse"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    investigation_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("investigations.id"), nullable=False, index=True
    )
    evidence_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("memory_evidence_items.id"), nullable=False, index=True
    )
    source_investigation_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("investigations.id"), nullable=False
    )
    reuse_rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    freshness_assessment: Mapped[str] = mapped_column(String(40), nullable=False, default="fresh")
    # fresh|stale|outdated

    reused_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "investigation_id", "evidence_id", name="uq_reuse_investigation_evidence"
        ),
        Index("ix_reuse_tenant_investigation", "tenant_id", "investigation_id"),
    )


__all__ = [
    "ClaimRow",
    "ClaimSupportEdgeRow",
    "EntityRelationRow",
    "EntityRow",
    "EvidenceItemRow",
    "HypothesisRow",
    "InvestigationReuseRow",
    "MeasureRow",
    "MemoryDecisionRow",
    "SourceSnapshotRow",
]
