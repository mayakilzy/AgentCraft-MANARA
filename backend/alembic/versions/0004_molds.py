"""G04: Mold Factory tables.

Revision ID: 0004_molds
Revises: 0003_memory
Create Date: 2026-10-19

Creates 4 tables:
* mold_recipes          — stored mold recipes (G00 ``Mold`` contract materialized)
* mold_gap_analyses     — detected capability gaps during mold composition
* mold_reuse            — records when a mold is rehydrated for a new investigation
* investigation_workflows — enforces the G00 InvestigationState machine
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_molds"
down_revision: Union[str, Sequence[str], None] = "0003_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Mold recipes ──────────────────────────────────────────────────────────
    op.create_table(
        "mold_recipes",
        sa.Column("id", sa.String(120), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description_long", sa.Text, nullable=False),
        sa.Column("version", sa.String(60), nullable=False),
        sa.Column("schema_version", sa.String(40), nullable=False, server_default="1.0.0"),
        sa.Column("state", sa.String(40), nullable=False, server_default="temporary"),
        sa.Column("domain", sa.String(120), nullable=False),
        sa.Column("intent", sa.Text, nullable=False),
        sa.Column("sector", sa.String(120), nullable=True),
        sa.Column("geography_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("languages_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("deliverables_json", sa.JSON, nullable=False, server_default='["evidence_dossier"]'),
        sa.Column("capability_ids_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("agent_recipe_ids_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("composition_notes", sa.Text, nullable=False, server_default=""),
        sa.Column("plan_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("origin", sa.String(40), nullable=False, server_default="temporary_fresh"),
        sa.Column("promoted_by", sa.String(120), nullable=True),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("promotion_rationale", sa.Text, nullable=False, server_default=""),
        sa.Column("last_piloted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("id", "tenant_id", name="uq_mold_recipes_id_tenant"),
    )
    op.create_index("ix_mold_recipes_tenant_id", "mold_recipes", ["tenant_id"])
    op.create_index("ix_mold_recipes_state", "mold_recipes", ["state"])
    op.create_index("ix_mold_recipes_domain", "mold_recipes", ["domain"])
    op.create_index("ix_mold_recipes_tenant_state", "mold_recipes", ["tenant_id", "state"])
    op.create_index("ix_mold_recipes_tenant_domain", "mold_recipes", ["tenant_id", "domain"])

    # ── Gap analyses ──────────────────────────────────────────────────────────
    op.create_table(
        "mold_gap_analyses",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("mold_id", sa.String(120),
                  sa.ForeignKey("mold_recipes.id"), nullable=False),
        sa.Column("investigation_id", sa.String(120), nullable=True),
        sa.Column("need", sa.String(60), nullable=False),
        sa.Column("need_label", sa.String(200), nullable=False),
        sa.Column("candidate_capability_ids_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("status", sa.String(40), nullable=False, server_default="open"),
        sa.Column("resolution_notes", sa.Text, nullable=False, server_default=""),
        sa.Column("foundry_candidate_id", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_gap_tenant_id", "mold_gap_analyses", ["tenant_id"])
    op.create_index("ix_gap_mold_id", "mold_gap_analyses", ["mold_id"])
    op.create_index("ix_gap_status", "mold_gap_analyses", ["status"])
    op.create_index("ix_gap_tenant_status", "mold_gap_analyses", ["tenant_id", "status"])
    op.create_index("ix_gap_mold_need", "mold_gap_analyses", ["mold_id", "need"])

    # ── Mold reuse ─────────────────────────────────────────────────────────────
    op.create_table(
        "mold_reuse",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("mold_id", sa.String(120),
                  sa.ForeignKey("mold_recipes.id"), nullable=False),
        sa.Column("investigation_id", sa.String(120), nullable=False),
        sa.Column("reuse_rationale", sa.Text, nullable=False, server_default=""),
        sa.Column("modified_during_reuse", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("reused_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("mold_id", "investigation_id", name="uq_mold_reuse"),
    )
    op.create_index("ix_mold_reuse_tenant_id", "mold_reuse", ["tenant_id"])
    op.create_index("ix_mold_reuse_mold_id", "mold_reuse", ["mold_id"])
    op.create_index("ix_mold_reuse_investigation_id", "mold_reuse", ["investigation_id"])
    op.create_index("ix_mold_reuse_tenant_investigation", "mold_reuse", ["tenant_id", "investigation_id"])

    # ── Investigation workflows ───────────────────────────────────────────────
    op.create_table(
        "investigation_workflows",
        sa.Column("investigation_id", sa.String(120),
                  sa.ForeignKey("investigations.id"), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("state", sa.String(60), nullable=False, server_default="received"),
        sa.Column("mold_id", sa.String(120), nullable=True),
        sa.Column("transitions_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("blocker", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflow_tenant_id", "investigation_workflows", ["tenant_id"])
    op.create_index("ix_workflow_state", "investigation_workflows", ["state"])
    op.create_index("ix_workflow_tenant_state", "investigation_workflows", ["tenant_id", "state"])
    op.create_index("ix_workflow_mold_id", "investigation_workflows", ["mold_id"])


def downgrade() -> None:
    op.drop_table("investigation_workflows")
    op.drop_table("mold_reuse")
    op.drop_table("mold_gap_analyses")
    op.drop_table("mold_recipes")
