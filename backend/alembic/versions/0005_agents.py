"""G05: Agent Factory tables.

Revision ID: 0005_agents
Revises: 0004_molds
Create Date: 2026-10-19

Creates 3 tables: agent_recipes, agent_sessions, agent_evaluations.
"""

from __future__ import annotations
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0005_agents"
down_revision: Union[str, Sequence[str], None] = "0004_molds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_recipes",
        sa.Column("id", sa.String(120), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description_long", sa.Text, nullable=False),
        sa.Column("version", sa.String(60), nullable=False),
        sa.Column("schema_version", sa.String(40), nullable=False, server_default="1.0.0"),
        sa.Column("state", sa.String(40), nullable=False, server_default="on_demand"),
        sa.Column("role", sa.String(120), nullable=False),
        sa.Column("specialty", sa.String(120), nullable=False),
        sa.Column("keywords_en_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("keywords_ar_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("synonyms_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("positive_examples_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("negative_examples_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("required_skills_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("required_capability_ids_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("optional_capability_ids_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("allowed_tools_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("denied_tools_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("input_contract_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("output_contract_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("evidence_requirements_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("verification_criteria_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("evaluation_criteria_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("provider_requirements_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("memory_access_scope_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("user_prompt_template", sa.Text, nullable=True),
        sa.Column("promoted_by", sa.String(120), nullable=True),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("promotion_rationale", sa.Text, nullable=False, server_default=""),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("id", "tenant_id", name="uq_agent_recipes_id_tenant"),
    )
    op.create_index("ix_agent_recipes_tenant_id", "agent_recipes", ["tenant_id"])
    op.create_index("ix_agent_recipes_state", "agent_recipes", ["state"])
    op.create_index("ix_agent_recipes_specialty", "agent_recipes", ["specialty"])
    op.create_index("ix_agent_recipes_tenant_state", "agent_recipes", ["tenant_id", "state"])
    op.create_index("ix_agent_recipes_tenant_specialty", "agent_recipes", ["tenant_id", "specialty"])

    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.String(120), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("recipe_id", sa.String(120), sa.ForeignKey("agent_recipes.id"), nullable=False),
        sa.Column("investigation_id", sa.String(120), nullable=True),
        sa.Column("mold_id", sa.String(120), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="instantiated"),
        sa.Column("execution_mode", sa.String(40), nullable=False, server_default="mock"),
        sa.Column("task_description", sa.Text, nullable=False),
        sa.Column("task_input_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("task_output_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("output_summary", sa.Text, nullable=False, server_default=""),
        sa.Column("granted_tools_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("provider_name", sa.String(120), nullable=True),
        sa.Column("model_name", sa.String(120), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_sessions_tenant_id", "agent_sessions", ["tenant_id"])
    op.create_index("ix_agent_sessions_status", "agent_sessions", ["status"])
    op.create_index("ix_agent_sessions_recipe_id", "agent_sessions", ["recipe_id"])
    op.create_index("ix_agent_sessions_tenant_status", "agent_sessions", ["tenant_id", "status"])

    op.create_table(
        "agent_evaluations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(120), sa.ForeignKey("agent_sessions.id"), nullable=False),
        sa.Column("recipe_id", sa.String(120), sa.ForeignKey("agent_recipes.id"), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("outcome", sa.String(40), nullable=False),
        sa.Column("quality_score", sa.Float, nullable=True),
        sa.Column("improvement_over_generalist", sa.Float, nullable=True),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("criteria_results_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("evaluator", sa.String(120), nullable=False, server_default="system"),
    )
    op.create_index("ix_agent_evaluations_tenant_id", "agent_evaluations", ["tenant_id"])
    op.create_index("ix_agent_evaluations_session_id", "agent_evaluations", ["session_id"])
    op.create_index("ix_agent_evaluations_recipe_id", "agent_evaluations", ["recipe_id"])
    op.create_index("ix_agent_evaluations_tenant_recipe", "agent_evaluations", ["tenant_id", "recipe_id"])


def downgrade() -> None:
    op.drop_table("agent_evaluations")
    op.drop_table("agent_sessions")
    op.drop_table("agent_recipes")
