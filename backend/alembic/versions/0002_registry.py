"""G01: capability registry tables (sources, connectors, capabilities,
evaluations, relationships, approvals, embeddings).

Revision ID: 0002_registry
Revises: 0001_initial
Create Date: 2026-10-18

This migration creates the seven G01 tables. The ``vector_json`` column
stores embeddings as a JSON array; on PostgreSQL production, a follow-up
migration adds the ``pgvector`` extension and a vector column, and the
embedding store is switched to use it (see ``manara.registry.embeddings``).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_registry"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Sources ──────────────────────────────────────────────────────────────
    op.create_table(
        "registry_sources",
        sa.Column("id", sa.String(120), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(60), nullable=False),
        sa.Column("domains_json", sa.JSON, nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sources_tenant_id", "registry_sources", ["tenant_id"])
    op.create_index("ix_sources_status", "registry_sources", ["status"])
    op.create_index("ix_sources_tenant_status", "registry_sources", ["tenant_id", "status"])

    # ── Connectors ───────────────────────────────────────────────────────────
    op.create_table(
        "registry_connectors",
        sa.Column("id", sa.String(120), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("source_id", sa.String(120),
                  sa.ForeignKey("registry_sources.id"), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(60), nullable=False),
        sa.Column("implementation_sha", sa.String(120), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("id", "tenant_id", name="uq_connectors_id_tenant"),
    )
    op.create_index("ix_connectors_tenant_id", "registry_connectors", ["tenant_id"])
    op.create_index("ix_connectors_source_id", "registry_connectors", ["source_id"])
    op.create_index("ix_connectors_status", "registry_connectors", ["status"])
    op.create_index("ix_connectors_tenant_status", "registry_connectors", ["tenant_id", "status"])

    # ── Capabilities (engines) ───────────────────────────────────────────────
    op.create_table(
        "registry_capabilities",
        sa.Column("id", sa.String(120), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(60), nullable=False),
        sa.Column("version", sa.String(60), nullable=False),
        sa.Column("schema_version", sa.String(40), nullable=False, server_default="1.0.0"),
        # Denormalized for filtering
        sa.Column("domains_json", sa.JSON, nullable=False),
        sa.Column("subdomains_json", sa.JSON, nullable=False),
        sa.Column("tags_json", sa.JSON, nullable=False),
        sa.Column("keywords_ar_json", sa.JSON, nullable=False),
        sa.Column("keywords_en_json", sa.JSON, nullable=False),
        sa.Column("languages_json", sa.JSON, nullable=False),
        sa.Column("search_purposes_json", sa.JSON, nullable=False),
        sa.Column("data_types_json", sa.JSON, nullable=False),
        sa.Column("coverage_geographies_json", sa.JSON, nullable=False),
        # Text fields
        sa.Column("description_long", sa.Text, nullable=False),
        sa.Column("positive_examples_json", sa.JSON, nullable=False),
        sa.Column("negative_examples_json", sa.JSON, nullable=False),
        sa.Column("synonyms_json", sa.JSON, nullable=False),
        # Connector linkage
        sa.Column("connector_ids_json", sa.JSON, nullable=False),
        # License / rights
        sa.Column("source_license", sa.String(120), nullable=False, server_default="review-required"),
        sa.Column("data_reuse_rights", sa.String(40), nullable=False, server_default="unknown"),
        sa.Column("commercial_rights", sa.String(60), nullable=False, server_default="unknown"),
        # Full payload (Pydantic)
        sa.Column("payload", sa.JSON, nullable=False),
        # Approval metadata
        sa.Column("approved_by", sa.String(120), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("id", "tenant_id", name="uq_capabilities_id_tenant"),
    )
    op.create_index("ix_capabilities_tenant_id", "registry_capabilities", ["tenant_id"])
    op.create_index("ix_capabilities_status", "registry_capabilities", ["status"])
    op.create_index("ix_capabilities_tenant_status", "registry_capabilities", ["tenant_id", "status"])
    op.create_index("ix_capabilities_tenant_domains", "registry_capabilities", ["tenant_id", "domains_json"])

    # ── Capability evaluations ───────────────────────────────────────────────
    op.create_table(
        "registry_capability_evaluations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("capability_id", sa.String(120),
                  sa.ForeignKey("registry_capabilities.id"), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("evaluator", sa.String(120), nullable=False),
        sa.Column("benchmark_query_set", sa.String(200), nullable=False),
        sa.Column("precision", sa.Float, nullable=True),
        sa.Column("recall", sa.Float, nullable=True),
        sa.Column("false_positive_misuse_rate", sa.Float, nullable=True),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("payload", sa.JSON, nullable=False, server_default="{}"),
    )
    op.create_index("ix_evaluations_capability_id", "registry_capability_evaluations", ["capability_id"])
    op.create_index("ix_evaluations_tenant_id", "registry_capability_evaluations", ["tenant_id"])

    # ── Capability relationships (graph edges) ───────────────────────────────
    op.create_table(
        "registry_capability_relationships",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("from_capability_id", sa.String(120),
                  sa.ForeignKey("registry_capabilities.id"), nullable=False),
        sa.Column("to_capability_id", sa.String(120),
                  sa.ForeignKey("registry_capabilities.id"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.UniqueConstraint("from_capability_id", "to_capability_id", "kind",
                            name="uq_relationships_from_to_kind"),
    )
    op.create_index("ix_relationships_tenant_id", "registry_capability_relationships", ["tenant_id"])
    op.create_index("ix_relationships_from_id", "registry_capability_relationships", ["from_capability_id"])
    op.create_index("ix_relationships_to_id", "registry_capability_relationships", ["to_capability_id"])
    op.create_index("ix_relationships_tenant_kind", "registry_capability_relationships", ["tenant_id", "kind"])

    # ── Approvals ────────────────────────────────────────────────────────────
    op.create_table(
        "registry_approvals",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("capability_id", sa.String(120),
                  sa.ForeignKey("registry_capabilities.id"), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("decision", sa.String(40), nullable=False),
        sa.Column("reviewer", sa.String(120), nullable=False),
        sa.Column("rationale", sa.Text, nullable=False, server_default=""),
        sa.Column("new_status", sa.String(60), nullable=False),
        sa.Column("previous_status", sa.String(60), nullable=True),
        sa.Column("test_matrix_ref", sa.String(200), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False, server_default="{}"),
    )
    op.create_index("ix_approvals_capability_id", "registry_approvals", ["capability_id"])
    op.create_index("ix_approvals_tenant_id", "registry_approvals", ["tenant_id"])

    # ── Embeddings ───────────────────────────────────────────────────────────
    # NOTE: on PostgreSQL production, a follow-up migration will:
    #   1. CREATE EXTENSION IF NOT EXISTS vector;
    #   2. ADD COLUMN vector pgvector.vector(384)
    #   3. CREATE INDEX ON registry_capability_embeddings
    #        USING ivfflat (vector pgvector_cosine_ops) WITH (lists=100);
    # For now, vector_json stores the embedding as a JSON array of floats.
    op.create_table(
        "registry_capability_embeddings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("capability_id", sa.String(120),
                  sa.ForeignKey("registry_capabilities.id"), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("example_index", sa.Integer, nullable=True),
        sa.Column("model_name", sa.String(120), nullable=False),
        sa.Column("model_version", sa.String(60), nullable=False),
        sa.Column("embedding_dim", sa.Integer, nullable=False),
        sa.Column("vector_json", sa.JSON, nullable=False),
        sa.Column("source_text", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_embeddings_capability_id", "registry_capability_embeddings", ["capability_id"])
    op.create_index("ix_embeddings_tenant_id", "registry_capability_embeddings", ["tenant_id"])
    op.create_index("ix_embeddings_tenant_kind", "registry_capability_embeddings", ["tenant_id", "kind"])
    op.create_index("ix_embeddings_capability_kind", "registry_capability_embeddings", ["capability_id", "kind"])


def downgrade() -> None:
    op.drop_table("registry_capability_embeddings")
    op.drop_table("registry_approvals")
    op.drop_table("registry_capability_relationships")
    op.drop_table("registry_capability_evaluations")
    op.drop_table("registry_capabilities")
    op.drop_table("registry_connectors")
    op.drop_table("registry_sources")
