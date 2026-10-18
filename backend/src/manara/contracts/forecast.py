"""Forecast contract — immutable-at-publication forecast record.

Maps to ``03_INTELLIGENCE/02_FORECASTING.md``:
    Forecast record immutable at publication (issue date, horizon, metric,
    unit, reference region, input dataset hashes, model/method version,
    probability distribution when verified, baseline and evaluation
    protocol); subsequent revisions link to original as new entries. Track
    incorrect as well as correct outcomes. Source timestamps must be before
    cutoff in historical replay.

Critical: a published forecast MUST be immutable. Revisions create new
records that link back to the original via ``subsequent_revision_of``.
This is the audit contract that makes backtesting and outcome tracking
honest.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FORECAST_SCHEMA_VERSION = "1.0.0"


class ForecastBaseline(BaseModel):
    """A naive/robust baseline the forecast is compared against."""

    model_config = ConfigDict(extra="forbid")

    method: str = Field(..., description="Baseline method name, e.g. 'naive_seasonal'.")
    metric_value: float | None = Field(default=None)
    mae: float | None = Field(default=None, ge=0.0)
    rmse: float | None = Field(default=None, ge=0.0)
    brier_score: float | None = Field(default=None, ge=0.0, le=1.0)
    log_loss: float | None = Field(default=None)
    notes: str = Field(default="")


class ForecastEvaluation(BaseModel):
    """Backtesting/evaluation metadata."""

    model_config = ConfigDict(extra="forbid")

    cutoff_date: datetime
    backtest_horizon_days: int = Field(..., gt=0)
    n_cutoffs: int = Field(default=1, gt=0)
    leakage_check_passed: bool = Field(default=False)
    mae: float | None = Field(default=None, ge=0.0)
    rmse: float | None = Field(default=None, ge=0.0)
    brier_score: float | None = Field(default=None, ge=0.0, le=1.0)
    calibration_curve_summary: str | None = Field(default=None)


class ForecastOutcome(BaseModel):
    """Observed outcome (filled in later when horizon is reached)."""

    model_config = ConfigDict(extra="forbid")

    observed_at: datetime
    observed_value: float | None = None
    observed_label: str | None = None
    notes: str = Field(default="")
    correct: bool | None = None


class Forecast(BaseModel):
    """An immutable-at-publication forecast record.

    ``status == published`` enforces immutability: any later update must
    create a new Forecast record referencing the original via
    ``subsequent_revision_of``.

    Forecasts WITHOUT empirical basis are PROHIBITED. If evidence is
    insufficient, set ``method == 'insufficient_evidence'`` and leave
    ``probability_distribution`` empty.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    schema_version: str = Field(default=FORECAST_SCHEMA_VERSION)
    investigation_id: str = Field(..., description="Investigation this forecast belongs to.")
    tenant_id: str = Field(..., min_length=1)

    target: str = Field(..., min_length=10, description="Measurable outcome description.")
    metric: str = Field(..., min_length=1)
    unit: str = Field(..., min_length=1)
    horizon_end: datetime
    reference_region: str = Field(..., min_length=1)

    # Method selection (Central Forecast Router output)
    method: Literal[
        "trend_ets",
        "arima",
        "hierarchical_adoption",
        "calibrated_probability",
        "bayesian_update",
        "technology_readiness_scenario",
        "structured_expert_judgment",
        "insufficient_evidence",
        "domain_plugin",
    ]
    method_version: str = Field(..., min_length=1)

    # Immutability / publication
    status: Literal["draft", "published", "superseded"] = Field(default="draft")
    issue_date: datetime | None = Field(default=None, description="Publication date; required when status == published.")
    published_at: datetime | None = Field(default=None)
    subsequent_revision_of: str | None = Field(default=None, description="Original Forecast.id this revises.")
    superseded_by: str | None = Field(default=None)

    # Inputs (immutable snapshot)
    input_dataset_hashes: list[str] = Field(default_factory=list, description="SHA-256s of input datasets at cutoff.")
    cutoff_date: datetime | None = Field(default=None, description="Data cutoff; backtests MUST NOT see past this.")
    probability_distribution: dict[str, Any] = Field(
        default_factory=dict,
        description="Distribution parameters (only when method justifies a probability).",
    )
    scenarios: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Scenario pathways (conditional, not always numeric).",
    )
    assumptions: list[str] = Field(default_factory=list)
    sensitivity_notes: str = Field(default="")

    # Evaluation / outcomes
    baseline: ForecastBaseline | None = Field(default=None)
    evaluation: ForecastEvaluation | None = Field(default=None)
    outcome: ForecastOutcome | None = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _validate(self) -> Forecast:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")

        if self.status == "published":
            if not self.issue_date:
                raise ValueError("published forecast requires issue_date")
            if not self.published_at:
                # Promote to immutable snapshot timestamp
                self.published_at = self.issue_date
            # Immutability guard: cannot set outcome or change method on already-published record
            # (This validator cannot enforce true immutability across instances; that is the
            # repository's responsibility. We do enforce structural integrity.)
            if self.method == "insufficient_evidence" and self.probability_distribution:
                raise ValueError(
                    "insufficient_evidence forecasts MUST NOT carry a probability_distribution"
                )
            if self.cutoff_date is None:
                raise ValueError("published forecast requires cutoff_date for replay safety")

        if self.method == "insufficient_evidence":
            if self.probability_distribution:
                raise ValueError(
                    "insufficient_evidence forecasts MUST NOT carry a probability_distribution"
                )

        if self.subsequent_revision_of and self.subsequent_revision_of == self.id:
            raise ValueError("subsequent_revision_of must reference a different Forecast.id")

        # Leakage guard: cutoff must not be later than issue date
        if self.cutoff_date and self.issue_date and self.cutoff_date > self.issue_date:
            raise ValueError("cutoff_date must be <= issue_date (no future leakage)")

        return self


__all__ = [
    "FORECAST_SCHEMA_VERSION",
    "Forecast",
    "ForecastBaseline",
    "ForecastEvaluation",
    "ForecastOutcome",
]
