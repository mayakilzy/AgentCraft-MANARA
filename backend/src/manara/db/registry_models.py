"""ORM models for the MANARA Capability Registry (G01).

These models mirror the eight Pydantic contracts defined in G00. Each ORM
table stores the canonical Pydantic payload as JSON plus a set of indexed
columns for queryability (id, tenant_id, status, domain, etc.).

The ``embeddings`` table stores vector representations of capability
descriptions and example sentences. In PostgreSQL production this uses
``pgvector``; in SQLite dev/test, the vector is stored as a JSON array and
similarity is computed in-process via numpy. The Python ``EmbeddingStore``
abstraction hides this difference — see ``manara.registry.embeddings``.
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
# Sources — the "what" (provider/dataset/collection)
# ─────────────────────────────────────────────────────────────────────────────


class SourceRow(Base):
    """A canonical Source identity.

    Mirrors ``manara.contracts.Source``. The full Pydantic payload is
    serialized to JSON in ``payload``; indexed columns are extracted for
    fast filtering.
    """

    __tablename__ = "registry_sources"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    domains_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
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

    # Relationships
    connectors: Mapped[list[ConnectorRow]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_sources_tenant_status", "tenant_id", "status"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Connectors — the "how" (tested implementations)
# ─────────────────────────────────────────────────────────────────────────────


class ConnectorRow(Base):
    """A tested implementation of access/extraction against a Source.

    Mirrors ``manara.contracts.Connector``.
    """

    __tablename__ = "registry_connectors"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    source_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("registry_sources.id"), nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    implementation_sha: Mapped[str] = mapped_column(String(120), nullable=False)
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

    source: Mapped[SourceRow] = relationship(back_populates="connectors")

    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_connectors_id_tenant"),
        Index("ix_connectors_tenant_status", "tenant_id", "status"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Capabilities (engines) — the "why" (logical query plans)
# ─────────────────────────────────────────────────────────────────────────────


class CapabilityRow(Base):
    """A logical search capability / engine.

    Mirrors ``manara.contracts.SearchCapability``. This is the primary
    card surface that the Registry exposes; the embeddings table stores
    vector representations of its description and examples.
    """

    __tablename__ = "registry_capabilities"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    version: Mapped[str] = mapped_column(String(60), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False, default="1.0.0")

    # Denormalized for fast filtering
    domains_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    subdomains_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    tags_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    keywords_ar_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    keywords_en_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    languages_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    search_purposes_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    data_types_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    coverage_geographies_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Full text fields (for full-text search; in Postgres these become tsvector-friendly)
    description_long: Mapped[str] = mapped_column(Text, nullable=False)
    positive_examples_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    negative_examples_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    synonyms_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Connector linkage
    connector_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # License / rights
    source_license: Mapped[str] = mapped_column(String(120), nullable=False, default="review-required")
    data_reuse_rights: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    commercial_rights: Mapped[str] = mapped_column(String(60), nullable=False, default="unknown")

    # The full Pydantic payload (preserves fields not denormalized above)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Approval metadata
    approved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    evaluations: Mapped[list[CapabilityEvaluationRow]] = relationship(
        back_populates="capability", cascade="all, delete-orphan"
    )
    embeddings: Mapped[list[CapabilityEmbeddingRow]] = relationship(
        back_populates="capability", cascade="all, delete-orphan"
    )
    approvals: Mapped[list[ApprovalRow]] = relationship(
        back_populates="capability", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_capabilities_id_tenant"),
        Index("ix_capabilities_tenant_status", "tenant_id", "status"),
        Index("ix_capabilities_tenant_domains", "tenant_id", "domains_json"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Capability evaluations — dated live-sample evaluations
# ─────────────────────────────────────────────────────────────────────────────


class CapabilityEvaluationRow(Base):
    """A dated evaluation record for a capability.

    Mirrors ``manara.contracts.CapabilityEvaluation``.
    """

    __tablename__ = "registry_capability_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    capability_id: Mapped[str] = mapped_column(
        String(120),
        ForeignKey("registry_capabilities.id"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    evaluator: Mapped[str] = mapped_column(String(120), nullable=False)
    benchmark_query_set: Mapped[str] = mapped_column(String(200), nullable=False)
    precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    recall: Mapped[float | None] = mapped_column(Float, nullable=True)
    false_positive_misuse_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    capability: Mapped[CapabilityRow] = relationship(back_populates="evaluations")


# ─────────────────────────────────────────────────────────────────────────────
# Capability relationships (graph edges)
# ─────────────────────────────────────────────────────────────────────────────


class CapabilityRelationshipRow(Base):
    """An edge in the capability graph.

    Mirrors ``manara.contracts.CapabilityGraph``. Edge kinds:
    ``complements``, ``specializes``, ``replaces``, ``conflicts_with``.
    """

    __tablename__ = "registry_capability_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    from_capability_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("registry_capabilities.id"), nullable=False, index=True
    )
    to_capability_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("registry_capabilities.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "from_capability_id", "to_capability_id", "kind",
            name="uq_relationships_from_to_kind"
        ),
        Index("ix_relationships_tenant_kind", "tenant_id", "kind"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Approvals — audit trail of owner-approved promotions
# ─────────────────────────────────────────────────────────────────────────────


class ApprovalRow(Base):
    """Audit record for an owner-approved capability promotion.

    Per spec: ``Registry promotion is owner-approved, version-pinned,
    reversible; record test matrix and rights decision.``

    Each promotion creates ONE ApprovalRow. Reverts create another
    ApprovalRow with ``decision='rejected'`` referencing the original.
    """

    __tablename__ = "registry_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    capability_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("registry_capabilities.id"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)  # approved | rejected | reverted
    reviewer: Mapped[str] = mapped_column(String(120), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    new_status: Mapped[str] = mapped_column(String(60), nullable=False)
    previous_status: Mapped[str] = mapped_column(String(60), nullable=True)
    test_matrix_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    capability: Mapped[CapabilityRow] = relationship(back_populates="approvals")


# ─────────────────────────────────────────────────────────────────────────────
# Embeddings — vector representations for semantic retrieval
# ─────────────────────────────────────────────────────────────────────────────


class CapabilityEmbeddingRow(Base):
    """A vector embedding for a capability.

    Stores an embedding of either:
    * ``description_long`` (kind="description"),
    * a positive example (kind="positive_example", with ``example_index``),
    * a negative example (kind="negative_example", with ``example_index``),
    * combined text used for retrieval (kind="combined").

    In PostgreSQL production, ``vector_json`` is replaced by a ``pgvector``
    column. The Python ``EmbeddingStore`` handles both backends.
    """

    __tablename__ = "registry_capability_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    capability_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("registry_capabilities.id"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)  # description | positive_example | negative_example | combined
    example_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_version: Mapped[str] = mapped_column(String(60), nullable=False)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    vector_json: Mapped[list[float]] = mapped_column(JSON, nullable=False)  # 384 floats
    source_text: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    capability: Mapped[CapabilityRow] = relationship(back_populates="embeddings")

    __table_args__ = (
        Index("ix_embeddings_tenant_kind", "tenant_id", "kind"),
        Index("ix_embeddings_capability_kind", "capability_id", "kind"),
    )


__all__ = [
    "ApprovalRow",
    "CapabilityEmbeddingRow",
    "CapabilityEvaluationRow",
    "CapabilityRelationshipRow",
    "CapabilityRow",
    "ConnectorRow",
    "SourceRow",
]
