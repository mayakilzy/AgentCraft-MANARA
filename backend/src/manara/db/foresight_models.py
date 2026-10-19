"""ORM models for the Foresight Engine (G06).

Per ``03_INTELLIGENCE/02_FORECASTING.md``:
> "Forecast record immutable at publication (issue date, horizon, metric,
> unit, reference region, input dataset hashes, model/method version,
> probability distribution when verified, baseline and evaluation
> protocol); subsequent revisions link to original as new entries."

Three tables:
* ``forecasts``           — immutable-at-publication forecast records
* ``forecast_revisions``  — links revised forecasts to their originals
* ``forecast_outcomes``   — observed outcomes for evaluation
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
from sqlalchemy.orm import Mapped, mapped_column

from manara.db.session import Base


class ForecastRow(Base):
    """An immutable-at-publication forecast record.

    Per owner (G06):
    > "حفظ نسخ التوقعات المنشورة بصورة غير قابلة للتعديل."
    > "إنشاء مراجعات جديدة مرتبطة بالإصدارات الأصلية دون محو التاريخ."

    Once status='published', the row is IMMUTABLE. Any update must create
    a new ForecastRow with subsequent_revision_of pointing to the original.
    """

    __tablename__ = "foresight_forecasts"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    investigation_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)

    # Target and scope
    target: Mapped[str] = mapped_column(Text, nullable=False)
    metric: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(60), nullable=False)
    horizon_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reference_region: Mapped[str] = mapped_column(String(120), nullable=False)

    # Method selection (Central Forecast Router output)
    method: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    # trend_ets | arima | naive_seasonal | hierarchical_adoption |
    # calibrated_probability | bayesian_update |
    # technology_readiness_scenario | structured_expert_judgment |
    # insufficient_evidence | domain_plugin
    method_version: Mapped[str] = mapped_column(String(60), nullable=False)

    # Immutability / publication
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", index=True)
    # draft | published | superseded
    issue_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Revision tracking
    subsequent_revision_of: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    superseded_by: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Inputs (immutable snapshot at publication)
    input_dataset_hashes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    cutoff_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    # Per owner (G06):
    # > "تحديد تاريخ قطع المعرفة knowledge_cutoff."
    # > "لا تفترض أن observed_at وحده يحدد ما كان معروفاً وقتها."

    # Forecast output
    point_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    probability_distribution: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    scenarios: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    assumptions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    sensitivity_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Baseline
    baseline_method: Mapped[str | None] = mapped_column(String(60), nullable=True)
    baseline_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_mae: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_rmse: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Evaluation
    model_mae: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_rmse: Mapped[float | None] = mapped_column(Float, nullable=True)
    n_cutoffs: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    leakage_check_passed: Mapped[bool] = mapped_column(JSON, nullable=False, default=False)

    # Full Pydantic payload
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

    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_forecasts_id_tenant"),
        Index("ix_forecasts_tenant_status", "tenant_id", "status"),
        Index("ix_forecasts_tenant_method", "tenant_id", "method"),
        Index("ix_forecasts_cutoff", "cutoff_date"),
    )


class ForecastOutcomeRow(Base):
    """Observed outcome for a forecast (filled in when horizon is reached).

    Per spec: "Track incorrect as well as correct outcomes."
    """

    __tablename__ = "foresight_forecast_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    forecast_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("foresight_forecasts.id"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)

    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    observed_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    observed_label: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Evaluation
    error: Mapped[float | None] = mapped_column(Float, nullable=True)
    absolute_error: Mapped[float | None] = mapped_column(Float, nullable=True)
    squared_error: Mapped[float | None] = mapped_column(Float, nullable=True)
    correct: Mapped[bool | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class BacktestResultRow(Base):
    """Result of a historical backtest run.

    Per owner (G06):
    > "يجب ألا يرى الاختبار التاريخي أي بيانات أو وثائق لم تكن متاحة
    > عند تاريخ المحاكاة."

    Records the cutoff, the data used, the leakage check result, and
    the error metrics.
    """

    __tablename__ = "foresight_backtest_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    forecast_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("foresight_forecasts.id"), nullable=False, index=True
    )

    cutoff_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    backtest_horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    n_cutoffs: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Leakage check
    leakage_detected: Mapped[bool] = mapped_column(JSON, nullable=False, default=False)
    leaked_evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    # If leakage_detected=True, lists which evidence was published AFTER
    # the cutoff but was erroneously included.

    # Metrics
    mae: Mapped[float | None] = mapped_column(Float, nullable=True)
    rmse: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_mae: Mapped[float | None] = mapped_column(Float, nullable=True)
    baseline_rmse: Mapped[float | None] = mapped_column(Float, nullable=True)
    improvement_over_baseline: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Data used (hashes for reproducibility)
    data_points_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    data_cutoff_verified: Mapped[bool] = mapped_column(JSON, nullable=False, default=False)

    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        Index("ix_backtest_tenant_cutoff", "tenant_id", "cutoff_date"),
    )


__all__ = [
    "BacktestResultRow",
    "ForecastOutcomeRow",
    "ForecastRow",
]
