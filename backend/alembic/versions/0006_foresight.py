"""G06: Foresight Engine tables.

Revision ID: 0006_foresight
Revises: 0005_agents
Create Date: 2026-10-19
"""

from __future__ import annotations
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0006_foresight"
down_revision: Union[str, Sequence[str], None] = "0005_agents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "foresight_forecasts",
        sa.Column("id", sa.String(120), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("investigation_id", sa.String(120), nullable=True),
        sa.Column("target", sa.Text, nullable=False),
        sa.Column("metric", sa.String(200), nullable=False),
        sa.Column("unit", sa.String(60), nullable=False),
        sa.Column("horizon_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reference_region", sa.String(120), nullable=False),
        sa.Column("method", sa.String(60), nullable=False),
        sa.Column("method_version", sa.String(60), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("issue_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("subsequent_revision_of", sa.String(120), nullable=True),
        sa.Column("superseded_by", sa.String(120), nullable=True),
        sa.Column("input_dataset_hashes", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("cutoff_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("point_estimate", sa.Float, nullable=True),
        sa.Column("probability_distribution", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("scenarios", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("assumptions", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("sensitivity_notes", sa.Text, nullable=False, server_default=""),
        sa.Column("baseline_method", sa.String(60), nullable=True),
        sa.Column("baseline_value", sa.Float, nullable=True),
        sa.Column("baseline_mae", sa.Float, nullable=True),
        sa.Column("baseline_rmse", sa.Float, nullable=True),
        sa.Column("model_mae", sa.Float, nullable=True),
        sa.Column("model_rmse", sa.Float, nullable=True),
        sa.Column("n_cutoffs", sa.Integer, nullable=False, server_default="1"),
        sa.Column("leakage_check_passed", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("id", "tenant_id", name="uq_forecasts_id_tenant"),
    )
    op.create_index("ix_forecasts_tenant_id", "foresight_forecasts", ["tenant_id"])
    op.create_index("ix_forecasts_status", "foresight_forecasts", ["status"])
    op.create_index("ix_forecasts_method", "foresight_forecasts", ["method"])
    op.create_index("ix_forecasts_cutoff", "foresight_forecasts", ["cutoff_date"])
    op.create_index("ix_forecasts_tenant_status", "foresight_forecasts", ["tenant_id", "status"])
    op.create_index("ix_forecasts_tenant_method", "foresight_forecasts", ["tenant_id", "method"])
    op.create_index("ix_forecasts_subsequent_revision_of", "foresight_forecasts", ["subsequent_revision_of"])

    op.create_table(
        "foresight_forecast_outcomes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("forecast_id", sa.String(120), sa.ForeignKey("foresight_forecasts.id"), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_value", sa.Float, nullable=True),
        sa.Column("observed_label", sa.String(200), nullable=True),
        sa.Column("error", sa.Float, nullable=True),
        sa.Column("absolute_error", sa.Float, nullable=True),
        sa.Column("squared_error", sa.Float, nullable=True),
        sa.Column("correct", sa.Boolean, nullable=True),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_outcomes_tenant_id", "foresight_forecast_outcomes", ["tenant_id"])
    op.create_index("ix_outcomes_forecast_id", "foresight_forecast_outcomes", ["forecast_id"])

    op.create_table(
        "foresight_backtest_results",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("forecast_id", sa.String(120), sa.ForeignKey("foresight_forecasts.id"), nullable=False),
        sa.Column("cutoff_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("backtest_horizon_days", sa.Integer, nullable=False),
        sa.Column("n_cutoffs", sa.Integer, nullable=False, server_default="1"),
        sa.Column("leakage_detected", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("leaked_evidence_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("mae", sa.Float, nullable=True),
        sa.Column("rmse", sa.Float, nullable=True),
        sa.Column("baseline_mae", sa.Float, nullable=True),
        sa.Column("baseline_rmse", sa.Float, nullable=True),
        sa.Column("improvement_over_baseline", sa.Float, nullable=True),
        sa.Column("data_points_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("data_cutoff_verified", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_backtest_tenant_id", "foresight_backtest_results", ["tenant_id"])
    op.create_index("ix_backtest_forecast_id", "foresight_backtest_results", ["forecast_id"])
    op.create_index("ix_backtest_cutoff", "foresight_backtest_results", ["cutoff_date"])
    op.create_index("ix_backtest_tenant_cutoff", "foresight_backtest_results", ["tenant_id", "cutoff_date"])


def downgrade() -> None:
    op.drop_table("foresight_backtest_results")
    op.drop_table("foresight_forecast_outcomes")
    op.drop_table("foresight_forecasts")
