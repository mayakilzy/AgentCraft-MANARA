"""G03: cumulative knowledge memory tables.

Revision ID: 0003_memory
Revises: 0002_registry
Create Date: 2026-10-19

This migration creates the G03 cumulative memory tables:
* memory_evidence_items
* memory_claims
* memory_claim_support_edges
* memory_measures
* memory_entities
* memory_entity_relations
* memory_hypotheses
* memory_source_snapshots
* memory_decisions
* memory_investigation_reuse

Each table carries tenant_id (NOT NULL, indexed) for cross-tenant safety.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_memory"
down_revision: Union[str, Sequence[str], None] = "0002_registry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Evidence items ────────────────────────────────────────────────────────
    op.create_table(
        "memory_evidence_items",
        sa.Column("id", sa.String(120), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("investigation_id", sa.String(120),
                  sa.ForeignKey("investigations.id"), nullable=False),
        sa.Column("source_id", sa.String(120), nullable=False),
        sa.Column("source_snapshot_ref", sa.String(300), nullable=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("content_ref", sa.String(300), nullable=True),
        sa.Column("content_checksum", sa.String(64), nullable=True),
        sa.Column("content_preview", sa.Text, nullable=True),
        sa.Column("structured_payload", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "content_checksum", name="uq_evidence_tenant_checksum"),
    )
    op.create_index("ix_evidence_tenant_id", "memory_evidence_items", ["tenant_id"])
    op.create_index("ix_evidence_investigation_id", "memory_evidence_items", ["investigation_id"])
    op.create_index("ix_evidence_source_id", "memory_evidence_items", ["source_id"])
    op.create_index("ix_evidence_content_checksum", "memory_evidence_items", ["content_checksum"])
    op.create_index("ix_evidence_tenant_source", "memory_evidence_items", ["tenant_id", "source_id"])
    op.create_index("ix_evidence_tenant_observed", "memory_evidence_items", ["tenant_id", "observed_at"])
    op.create_index("ix_evidence_tenant_checksum", "memory_evidence_items", ["tenant_id", "content_checksum"])

    # ── Claims ───────────────────────────────────────────────────────────────
    op.create_table(
        "memory_claims",
        sa.Column("id", sa.String(120), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("investigation_id", sa.String(120),
                  sa.ForeignKey("investigations.id"), nullable=False),
        sa.Column("evidence_id", sa.String(120),
                  sa.ForeignKey("memory_evidence_items.id"), nullable=False),
        sa.Column("statement", sa.Text, nullable=False),
        sa.Column("verdict", sa.String(40), nullable=False, server_default="candidate"),
        sa.Column("independence_group", sa.String(120), nullable=True),
        sa.Column("superseded_by", sa.String(120), nullable=True),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("payload", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_claims_tenant_id", "memory_claims", ["tenant_id"])
    op.create_index("ix_claims_investigation_id", "memory_claims", ["investigation_id"])
    op.create_index("ix_claims_evidence_id", "memory_claims", ["evidence_id"])
    op.create_index("ix_claims_verdict", "memory_claims", ["verdict"])
    op.create_index("ix_claims_tenant_verdict", "memory_claims", ["tenant_id", "verdict"])
    op.create_index("ix_claims_tenant_investigation", "memory_claims", ["tenant_id", "investigation_id"])

    # ── Claim support edges ──────────────────────────────────────────────────
    op.create_table(
        "memory_claim_support_edges",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("claim_id", sa.String(120),
                  sa.ForeignKey("memory_claims.id"), nullable=False),
        sa.Column("evidence_id", sa.String(120),
                  sa.ForeignKey("memory_evidence_items.id"), nullable=False),
        sa.Column("relation", sa.String(20), nullable=False),
        sa.Column("weight", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("claim_id", "evidence_id", "relation",
                            name="uq_claim_evidence_relation"),
    )
    op.create_index("ix_support_edges_tenant_id", "memory_claim_support_edges", ["tenant_id"])
    op.create_index("ix_support_edges_claim_id", "memory_claim_support_edges", ["claim_id"])
    op.create_index("ix_support_edges_evidence_id", "memory_claim_support_edges", ["evidence_id"])
    op.create_index("ix_support_edges_tenant_relation", "memory_claim_support_edges", ["tenant_id", "relation"])

    # ── Measures ──────────────────────────────────────────────────────────────
    op.create_table(
        "memory_measures",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("evidence_id", sa.String(120),
                  sa.ForeignKey("memory_evidence_items.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("unit", sa.String(60), nullable=False),
        sa.Column("methodology", sa.String(300), nullable=True),
        sa.Column("geography", sa.String(120), nullable=True),
        sa.Column("valid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence_interval_low", sa.Float, nullable=True),
        sa.Column("confidence_interval_high", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_measures_tenant_id", "memory_measures", ["tenant_id"])
    op.create_index("ix_measures_evidence_id", "memory_measures", ["evidence_id"])
    op.create_index("ix_measures_geography", "memory_measures", ["geography"])
    op.create_index("ix_measures_tenant_name", "memory_measures", ["tenant_id", "name"])
    op.create_index("ix_measures_tenant_geography", "memory_measures", ["tenant_id", "geography"])

    # ── Entities ──────────────────────────────────────────────────────────────
    op.create_table(
        "memory_entities",
        sa.Column("id", sa.String(120), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("display_name", sa.String(300), nullable=False),
        sa.Column("entity_type", sa.String(60), nullable=False),
        sa.Column("canonical_id", sa.String(300), nullable=True),
        sa.Column("aliases_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("payload", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "canonical_id", name="uq_entities_tenant_canonical"),
    )
    op.create_index("ix_entities_tenant_id", "memory_entities", ["tenant_id"])
    op.create_index("ix_entities_canonical_id", "memory_entities", ["canonical_id"])
    op.create_index("ix_entities_tenant_type", "memory_entities", ["tenant_id", "entity_type"])

    # ── Entity relations ──────────────────────────────────────────────────────
    op.create_table(
        "memory_entity_relations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("from_entity_id", sa.String(120),
                  sa.ForeignKey("memory_entities.id"), nullable=False),
        sa.Column("to_entity_id", sa.String(120),
                  sa.ForeignKey("memory_entities.id"), nullable=False),
        sa.Column("relation_type", sa.String(60), nullable=False),
        sa.Column("evidence_id", sa.String(120),
                  sa.ForeignKey("memory_evidence_items.id"), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("from_entity_id", "to_entity_id", "relation_type",
                            name="uq_entity_relations_from_to_type"),
    )
    op.create_index("ix_entity_relations_tenant_id", "memory_entity_relations", ["tenant_id"])
    op.create_index("ix_entity_relations_from_id", "memory_entity_relations", ["from_entity_id"])
    op.create_index("ix_entity_relations_to_id", "memory_entity_relations", ["to_entity_id"])
    op.create_index("ix_entity_relations_tenant_type", "memory_entity_relations", ["tenant_id", "relation_type"])

    # ── Hypotheses ────────────────────────────────────────────────────────────
    op.create_table(
        "memory_hypotheses",
        sa.Column("id", sa.String(120), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("investigation_id", sa.String(120),
                  sa.ForeignKey("investigations.id"), nullable=False),
        sa.Column("statement", sa.Text, nullable=False),
        sa.Column("rationale", sa.Text, nullable=False, server_default=""),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("status", sa.String(40), nullable=False, server_default="open"),
        sa.Column("superseded_by", sa.String(120), nullable=True),
        sa.Column("related_claim_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_hypotheses_tenant_id", "memory_hypotheses", ["tenant_id"])
    op.create_index("ix_hypotheses_investigation_id", "memory_hypotheses", ["investigation_id"])
    op.create_index("ix_hypotheses_status", "memory_hypotheses", ["status"])
    op.create_index("ix_hypotheses_tenant_status", "memory_hypotheses", ["tenant_id", "status"])

    # ── Source snapshots ──────────────────────────────────────────────────────
    op.create_table(
        "memory_source_snapshots",
        sa.Column("id", sa.String(120), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("source_id", sa.String(120), nullable=False),
        sa.Column("snapshot_ref", sa.String(300), nullable=False),
        sa.Column("snapshot_checksum", sa.String(64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("source_response_meta", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("retention_class", sa.String(40), nullable=False, server_default="default"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "snapshot_checksum", name="uq_snapshots_tenant_checksum"),
    )
    op.create_index("ix_snapshots_tenant_id", "memory_source_snapshots", ["tenant_id"])
    op.create_index("ix_snapshots_source_id", "memory_source_snapshots", ["source_id"])
    op.create_index("ix_snapshots_checksum", "memory_source_snapshots", ["snapshot_checksum"])
    op.create_index("ix_snapshots_tenant_source", "memory_source_snapshots", ["tenant_id", "source_id"])

    # ── Memory decisions (audit log) ─────────────────────────────────────────
    op.create_table(
        "memory_decisions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("decision_type", sa.String(40), nullable=False),
        sa.Column("investigation_id", sa.String(120), nullable=True),
        sa.Column("evidence_id", sa.String(120), nullable=True),
        sa.Column("claim_id", sa.String(120), nullable=True),
        sa.Column("actor", sa.String(120), nullable=False),
        sa.Column("rationale", sa.Text, nullable=False, server_default=""),
        sa.Column("payload", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_decisions_tenant_id", "memory_decisions", ["tenant_id"])
    op.create_index("ix_decisions_decision_type", "memory_decisions", ["decision_type"])
    op.create_index("ix_decisions_investigation_id", "memory_decisions", ["investigation_id"])
    op.create_index("ix_decisions_evidence_id", "memory_decisions", ["evidence_id"])
    op.create_index("ix_decisions_claim_id", "memory_decisions", ["claim_id"])
    op.create_index("ix_decisions_tenant_type", "memory_decisions", ["tenant_id", "decision_type"])
    op.create_index("ix_decisions_tenant_investigation", "memory_decisions", ["tenant_id", "investigation_id"])

    # ── Investigation reuse ──────────────────────────────────────────────────
    op.create_table(
        "memory_investigation_reuse",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("investigation_id", sa.String(120),
                  sa.ForeignKey("investigations.id"), nullable=False),
        sa.Column("evidence_id", sa.String(120),
                  sa.ForeignKey("memory_evidence_items.id"), nullable=False),
        sa.Column("source_investigation_id", sa.String(120),
                  sa.ForeignKey("investigations.id"), nullable=False),
        sa.Column("reuse_rationale", sa.Text, nullable=False, server_default=""),
        sa.Column("freshness_assessment", sa.String(40), nullable=False, server_default="fresh"),
        sa.Column("reused_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("investigation_id", "evidence_id",
                            name="uq_reuse_investigation_evidence"),
    )
    op.create_index("ix_reuse_tenant_id", "memory_investigation_reuse", ["tenant_id"])
    op.create_index("ix_reuse_investigation_id", "memory_investigation_reuse", ["investigation_id"])
    op.create_index("ix_reuse_evidence_id", "memory_investigation_reuse", ["evidence_id"])
    op.create_index("ix_reuse_tenant_investigation", "memory_investigation_reuse", ["tenant_id", "investigation_id"])


def downgrade() -> None:
    op.drop_table("memory_investigation_reuse")
    op.drop_table("memory_decisions")
    op.drop_table("memory_source_snapshots")
    op.drop_table("memory_hypotheses")
    op.drop_table("memory_entity_relations")
    op.drop_table("memory_entities")
    op.drop_table("memory_measures")
    op.drop_table("memory_claim_support_edges")
    op.drop_table("memory_claims")
    op.drop_table("memory_evidence_items")
