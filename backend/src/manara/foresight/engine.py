"""Foresight Engine — forecasting policy, baselines, backtesting, immutability (G06).

Per owner (G06):
> "لا تُنشئ توقعات رقمية لمجرد أن المستخدم طلب أرقاماً."
> "اشترط بيانات مناسبة ومنهجية قابلة للتقييم، وإلا انتقل إلى سيناريوهات
> موصوفة أو تقرير عدم كفاية الأدلة."
> "لا تستخدم نسب احتمالية غير معايرة."

> "يجب ألا يرى الاختبار التاريخي أي بيانات أو وثائق لم تكن متاحة
> عند تاريخ المحاكاة."
> "لا تفترض أن observed_at وحده يحدد ما كان معروفاً وقتها."

The engine coordinates:
1. :class:`ForecastPolicyService` — selects methodology based on evidence
2. :class:`BaselineForecaster` — naive seasonal baseline for comparison
3. :class:`BacktestEngine` — historical replay with bitemporal leakage prevention
4. :class:`ForecastRegistry` — immutable publication + revision tracking
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

import numpy as np
from sqlalchemy.orm import Session

from manara.db.foresight_models import (
    BacktestResultRow,
    ForecastRow,
)
from manara.db.memory_models import EvidenceItemRow

# ─────────────────────────────────────────────────────────────────────────────
# Forecast policy — methodology selection
# ─────────────────────────────────────────────────────────────────────────────


ForecastMethod = Literal[
    "trend_ets", "arima", "naive_seasonal",
    "hierarchical_adoption", "calibrated_probability",
    "bayesian_update", "technology_readiness_scenario",
    "structured_expert_judgment", "insufficient_evidence", "domain_plugin",
]


@dataclass
class DataPoint:
    """A single data point in a time series."""

    timestamp: datetime
    value: float
    source_id: str
    published_at: datetime | None = None  # when the source published this data


@dataclass
class EvidenceAssessment:
    """Assessment of evidence availability for a forecast question."""

    has_time_series: bool
    data_points: list[DataPoint] = field(default_factory=list)
    data_points_before_cutoff: list[DataPoint] = field(default_factory=list)
    data_points_after_cutoff: list[DataPoint] = field(default_factory=list)
    has_contradictions: bool = False
    sufficient_for_quantitative: bool = False
    recommended_method: ForecastMethod = "insufficient_evidence"
    assessment_reasoning: str = ""


@dataclass
class ForecastResult:
    """Result of a forecast computation."""

    forecast_id: str
    method: ForecastMethod
    point_estimate: float | None
    baseline_value: float | None
    baseline_method: str | None
    assumptions: list[str]
    scenarios: list[dict[str, Any]]
    cutoff_date: datetime
    leakage_check_passed: bool
    is_published: bool = False
    error_message: str | None = None


@dataclass
class BacktestResult:
    """Result of a historical backtest."""

    cutoff_date: datetime
    backtest_horizon_days: int
    n_cutoffs: int
    leakage_detected: bool
    leaked_evidence_ids: list[str]
    mae: float | None
    rmse: float | None
    baseline_mae: float | None
    baseline_rmse: float | None
    improvement_over_baseline: float | None
    data_points_used: int
    data_cutoff_verified: bool
    notes: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# ForecastPolicyService — the Central Forecast Router
# ─────────────────────────────────────────────────────────────────────────────


class ForecastPolicyService:
    """Selects the appropriate forecasting methodology.

    Per owner (G06):
    > "الاستشراف ليس خوارزمية واحدة لكل المجالات."
    > "تختار المنظومة المنهجية بناءً على طبيعة السؤال والأدلة."

    Decision tree:
    1. If no time series data → insufficient_evidence
    2. If < 5 data points before cutoff → insufficient_evidence
    3. If data has clear seasonal pattern → naive_seasonal
    4. If data has clear trend → trend_ets
    5. Otherwise → naive_seasonal (simplest baseline)

    Per owner: "لا تُنشئ توقعات رقمية لمجرد أن المستخدم طلب أرقاماً."
    The policy NEVER fabricates data. If evidence is insufficient, it says so.
    """

    MIN_DATA_POINTS = 5

    def assess_evidence(
        self,
        *,
        data_points: list[DataPoint],
        cutoff_date: datetime,
        has_contradictions: bool = False,
    ) -> EvidenceAssessment:
        """Assess evidence and recommend a forecasting method.

        Per owner (G06):
        > "لا تفترض أن observed_at وحده يحدد ما كان معروفاً وقتها."

        We split data points by PUBLISHED_AT (when the data became available),
        NOT by observed_at (when the event happened). A study published in
        September about an event in June is NOT available at a July cutoff.
        """
        before_cutoff: list[DataPoint] = []
        after_cutoff: list[DataPoint] = []

        for dp in data_points:
            # Use published_at if available; fall back to timestamp
            availability = dp.published_at or dp.timestamp
            if availability <= cutoff_date:
                before_cutoff.append(dp)
            else:
                after_cutoff.append(dp)

        has_ts = len(before_cutoff) >= 2
        sufficient = len(before_cutoff) >= self.MIN_DATA_POINTS

        if not has_ts or not sufficient:
            return EvidenceAssessment(
                has_time_series=has_ts,
                data_points=data_points,
                data_points_before_cutoff=before_cutoff,
                data_points_after_cutoff=after_cutoff,
                has_contradictions=has_contradictions,
                sufficient_for_quantitative=False,
                recommended_method="insufficient_evidence",
                assessment_reasoning=(
                    f"Only {len(before_cutoff)} data point(s) available before "
                    f"cutoff {cutoff_date.isoformat()} (need ≥ {self.MIN_DATA_POINTS}). "
                    f"{len(after_cutoff)} point(s) were published AFTER the cutoff "
                    f"and are excluded. "
                    "Per owner: 'لا تُنشئ توقعات رقمية لمجرد أن المستخدم طلب أرقاماً.' "
                    "Method: insufficient_evidence. No fabricated probabilities."
                ),
            )

        # Check for trend vs seasonal
        values = [dp.value for dp in before_cutoff]
        has_trend = self._detect_trend(values)
        has_seasonal = self._detect_seasonality(values)

        if has_seasonal:
            method: ForecastMethod = "naive_seasonal"
            reasoning = "Seasonal pattern detected; using naive_seasonal baseline."
        elif has_trend:
            method = "trend_ets"
            reasoning = "Clear trend detected; using trend_ets."
        else:
            method = "naive_seasonal"
            reasoning = "No strong pattern; using naive_seasonal as simplest baseline."

        if has_contradictions:
            reasoning += (
                " NOTE: contradictions detected in evidence. Scenario-based "
                "assessment recommended alongside the quantitative forecast."
            )

        return EvidenceAssessment(
            has_time_series=True,
            data_points=data_points,
            data_points_before_cutoff=before_cutoff,
            data_points_after_cutoff=after_cutoff,
            has_contradictions=has_contradictions,
            sufficient_for_quantitative=True,
            recommended_method=method,
            assessment_reasoning=reasoning,
        )

    @staticmethod
    def _detect_trend(values: list[float]) -> bool:
        if len(values) < 3:
            return False
        x = np.arange(len(values))
        y = np.array(values)
        slope = np.polyfit(x, y, 1)[0]
        mean_val = np.mean(y) if np.mean(y) != 0 else 1.0
        relative_slope = abs(slope) / abs(mean_val) if mean_val != 0 else 0
        return relative_slope > 0.05

    @staticmethod
    def _detect_seasonality(values: list[float]) -> bool:
        if len(values) < 6:
            return False
        y = np.array(values)
        autocorr = np.correlate(y - y.mean(), y - y.mean(), mode="full")
        autocorr = autocorr[len(autocorr) // 2:]
        if len(autocorr) > 2 and autocorr[0] > 0:
            normalized = autocorr / autocorr[0]
            return len(normalized) > 2 and normalized[1] > 0.3
        return False


# ─────────────────────────────────────────────────────────────────────────────
# BaselineForecaster — simple, interpretable baselines
# ─────────────────────────────────────────────────────────────────────────────


class BaselineForecaster:
    """Simple baseline forecasters for comparison.

    Per spec: "Compare against naive and robust baselines, backtest
    across multiple historical cutoffs, measure MAE/RMSE for quantities."

    Two baselines:
    - Naive: last value is the forecast
    - Seasonal naive: last seasonal value is the forecast
    """

    @staticmethod
    def naive_forecast(data_points: list[DataPoint]) -> float:
        """Naive forecast: last observed value."""
        if not data_points:
            raise ValueError("no data points for naive forecast")
        return data_points[-1].value

    @staticmethod
    def seasonal_naive_forecast(
        data_points: list[DataPoint], seasonal_period: int = 2
    ) -> float:
        """Seasonal naive: value from one period ago."""
        if len(data_points) < seasonal_period:
            return BaselineForecaster.naive_forecast(data_points)
        return data_points[-seasonal_period].value

    @staticmethod
    def compute_mae(actual: list[float], predicted: list[float]) -> float:
        if not actual or not predicted:
            return float("inf")
        n = min(len(actual), len(predicted))
        errors = [abs(actual[i] - predicted[i]) for i in range(n)]
        result: float = sum(errors) / n
        return result

    @staticmethod
    def compute_rmse(actual: list[float], predicted: list[float]) -> float:
        if not actual or not predicted:
            return float("inf")
        n = min(len(actual), len(predicted))
        errors = [(actual[i] - predicted[i]) ** 2 for i in range(n)]
        result: float = (sum(errors) / n) ** 0.5
        return result


# ─────────────────────────────────────────────────────────────────────────────
# BacktestEngine — historical replay with bitemporal leakage prevention
# ─────────────────────────────────────────────────────────────────────────────


class BacktestEngine:
    """Historical backtesting with strict bitemporal leakage prevention.

    Per owner (G06):
    > "يجب ألا يرى الاختبار التاريخي أي بيانات أو وثائق لم تكن متاحة
    > عند تاريخ المحاكاة."
    > "لا تفترض أن observed_at وحده يحدد ما كان معروفاً وقتها."
    > "ميّز بين: تاريخ الحدث، تاريخ نشر المصدر، تاريخ إتاحته وجمعه."

    The engine checks:
    1. Each data point's `published_at` (when the data became available).
    2. If published_at is None, falls back to `timestamp` (the event time).
    3. Any data point with published_at > cutoff is LEAKAGE.
    4. The engine reports leaked evidence IDs and refuses to use them.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def run_backtest(
        self,
        *,
        all_data_points: list[DataPoint],
        cutoff_date: datetime,
        horizon_days: int = 30,
        tenant_id: str,
        forecast_id: str,
    ) -> BacktestResult:
        """Run a historical backtest at the given cutoff.

        Steps:
        1. Split data into before/after cutoff by PUBLISHED_AT.
        2. Check for leakage (any data with published_at > cutoff).
        3. If leakage detected: report it, mark as failed.
        4. Train on before-cutoff data only.
        5. Compare forecast against actual after-cutoff values.
        6. Compute MAE/RMSE for both model and baseline.
        """
        before: list[DataPoint] = []
        after: list[DataPoint] = []
        leaked: list[str] = []

        for dp in all_data_points:
            availability = dp.published_at or dp.timestamp
            if availability <= cutoff_date:
                before.append(dp)
            else:
                after.append(dp)
                # Check if this data point's EVENT happened before cutoff
                # but its PUBLICATION was after — this is the key leakage case.
                if dp.timestamp <= cutoff_date and dp.published_at and dp.published_at > cutoff_date:
                    leaked.append(
                        f"event@{dp.timestamp.isoformat()} "
                        f"published@{dp.published_at.isoformat()} "
                        f"(source={dp.source_id})"
                    )

        # ── Leakage check ───────────────────────────────────────────────────
        leakage_detected = len(leaked) > 0
        if leakage_detected:
            return BacktestResult(
                cutoff_date=cutoff_date,
                backtest_horizon_days=horizon_days,
                n_cutoffs=1,
                leakage_detected=True,
                leaked_evidence_ids=leaked,
                mae=None,
                rmse=None,
                baseline_mae=None,
                baseline_rmse=None,
                improvement_over_baseline=None,
                data_points_used=len(before),
                data_cutoff_verified=False,
                notes=(
                    f"LEAKAGE DETECTED: {len(leaked)} data point(s) have events "
                    f"before cutoff {cutoff_date.isoformat()} but were published "
                    f"AFTER the cutoff. These are excluded from the training set. "
                    f"Per owner: 'لا تفترض أن observed_at وحده يحدد ما كان معروفاً وقتها.' "
                    f"Backtest FAILED due to leakage."
                ),
            )

        # ── Train on before-cutoff data ────────────────────────────────────
        if len(before) < 2:
            return BacktestResult(
                cutoff_date=cutoff_date,
                backtest_horizon_days=horizon_days,
                n_cutoffs=1,
                leakage_detected=False,
                leaked_evidence_ids=[],
                mae=None,
                rmse=None,
                baseline_mae=None,
                baseline_rmse=None,
                improvement_over_baseline=None,
                data_points_used=len(before),
                data_cutoff_verified=True,
                notes="Insufficient data before cutoff for backtest.",
            )

        # Sort by timestamp
        before_sorted = sorted(before, key=lambda d: d.timestamp)
        after_sorted = sorted(after, key=lambda d: d.timestamp)

        # Model forecast: naive (last value)
        model_forecast = BaselineForecaster.naive_forecast(before_sorted)
        # Baseline: seasonal naive
        baseline_forecast = BaselineForecaster.seasonal_naive_forecast(before_sorted)

        # Actual values after cutoff
        actual_values = [dp.value for dp in after_sorted]
        if not actual_values:
            return BacktestResult(
                cutoff_date=cutoff_date,
                backtest_horizon_days=horizon_days,
                n_cutoffs=1,
                leakage_detected=False,
                leaked_evidence_ids=[],
                mae=None, rmse=None,
                baseline_mae=None, baseline_rmse=None,
                improvement_over_baseline=None,
                data_points_used=len(before),
                data_cutoff_verified=True,
                notes="No actual values after cutoff to evaluate against.",
            )

        # Compute errors
        model_preds = [model_forecast] * len(actual_values)
        baseline_preds = [baseline_forecast] * len(actual_values)

        mae = BaselineForecaster.compute_mae(actual_values, model_preds)
        rmse = BaselineForecaster.compute_rmse(actual_values, model_preds)
        b_mae = BaselineForecaster.compute_mae(actual_values, baseline_preds)
        b_rmse = BaselineForecaster.compute_rmse(actual_values, baseline_preds)

        improvement = (b_mae - mae) / b_mae if b_mae > 0 else 0.0

        # Persist the backtest result
        bt_row = BacktestResultRow(
            tenant_id=tenant_id,
            forecast_id=forecast_id,
            cutoff_date=cutoff_date,
            backtest_horizon_days=horizon_days,
            n_cutoffs=1,
            leakage_detected=False,
            leaked_evidence_ids=[],
            mae=mae,
            rmse=rmse,
            baseline_mae=b_mae,
            baseline_rmse=b_rmse,
            improvement_over_baseline=improvement,
            data_points_used=len(before),
            data_cutoff_verified=True,
            notes=f"Backtest passed. Model MAE={mae:.4f}, Baseline MAE={b_mae:.4f}.",
        )
        self.db.add(bt_row)
        self.db.commit()

        return BacktestResult(
            cutoff_date=cutoff_date,
            backtest_horizon_days=horizon_days,
            n_cutoffs=1,
            leakage_detected=False,
            leaked_evidence_ids=[],
            mae=mae,
            rmse=rmse,
            baseline_mae=b_mae,
            baseline_rmse=b_rmse,
            improvement_over_baseline=improvement,
            data_points_used=len(before),
            data_cutoff_verified=True,
            notes=f"Backtest passed. Model MAE={mae:.4f}, Baseline MAE={b_mae:.4f}.",
        )

    def check_evidence_leakage(
        self,
        *,
        evidence_ids: list[str],
        cutoff_date: datetime,
        tenant_id: str,
    ) -> tuple[bool, list[str]]:
        """Check if any evidence items were published AFTER the cutoff.

        Per owner (G06):
        > "نفذ اختبارات سلبية تُدخل دليلاً منشوراً بعد cutoff عمداً،
        > ويجب أن يرفضه المحرك."

        Returns (leakage_detected, leaked_evidence_ids).
        """
        if not evidence_ids:
            return False, []

        leaked: list[str] = []
        for eid in evidence_ids:
            row = self.db.get(EvidenceItemRow, eid)
            if row is None or row.tenant_id != tenant_id:
                continue
            # Check ingested_at (when MANARA learned of it) against cutoff.
            # Per owner: "لا تفترض أن observed_at وحده يحدد ما كان معروفاً وقتها."
            # The availability date is ingested_at (knowledge-time), NOT observed_at.
            availability = row.ingested_at
            if availability and availability.tzinfo is None:
                availability = availability.replace(tzinfo=UTC)
            cutoff_aware = cutoff_date if cutoff_date.tzinfo is not None else cutoff_date.replace(tzinfo=UTC)

            if availability and availability > cutoff_aware:
                leaked.append(eid)

        return len(leaked) > 0, leaked


# ─────────────────────────────────────────────────────────────────────────────
# ForecastRegistry — immutable publication + revisions
# ─────────────────────────────────────────────────────────────────────────────


class ForecastRegistry:
    """Manages forecast records with immutable publication.

    Per owner (G06):
    > "حفظ نسخ التوقعات المنشورة بصورة غير قابلة للتعديل."
    > "إنشاء مراجعات جديدة مرتبطة بالإصدارات الأصلية دون محو التاريخ."

    Once a forecast is published (status='published'), it CANNOT be modified.
    Any update must create a new ForecastRow with subsequent_revision_of
    pointing to the original. The original's status becomes 'superseded'.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_forecast(
        self,
        *,
        tenant_id: str,
        target: str,
        metric: str,
        unit: str,
        horizon_end: datetime,
        reference_region: str,
        method: str,
        method_version: str,
        cutoff_date: datetime,
        point_estimate: float | None = None,
        probability_distribution: dict[str, Any] | None = None,
        scenarios: list[dict[str, Any]] | None = None,
        assumptions: list[str] | None = None,
        input_dataset_hashes: list[str] | None = None,
        baseline_method: str | None = None,
        baseline_value: float | None = None,
        investigation_id: str | None = None,
    ) -> ForecastRow:
        """Create a draft forecast (status='draft')."""
        forecast_id = f"fc-{secrets.token_hex(8)}"

        # Per owner: insufficient_evidence forbids probability_distribution
        if method == "insufficient_evidence" and probability_distribution:
            raise ValueError(
                "insufficient_evidence forecasts MUST NOT carry a "
                "probability_distribution. Per owner: 'لا تستخدم نسب "
                "احتمالية غير معايرة.'"
            )

        row = ForecastRow(
            id=forecast_id,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            target=target,
            metric=metric,
            unit=unit,
            horizon_end=horizon_end,
            reference_region=reference_region,
            method=method,
            method_version=method_version,
            status="draft",
            cutoff_date=cutoff_date,
            point_estimate=point_estimate,
            probability_distribution=probability_distribution or {},
            scenarios=scenarios or [],
            assumptions=assumptions or [],
            input_dataset_hashes=input_dataset_hashes or [],
            baseline_method=baseline_method,
            baseline_value=baseline_value,
            payload={
                "id": forecast_id,
                "method": method,
                "target": target,
                "metric": metric,
                "unit": unit,
                "cutoff_date": cutoff_date.isoformat(),
                "point_estimate": point_estimate,
                "status": "draft",
            },
        )
        self.db.add(row)
        self.db.commit()
        return row

    def publish_forecast(
        self,
        *,
        forecast_id: str,
        tenant_id: str,
        issue_date: datetime | None = None,
    ) -> ForecastRow:
        """Publish a forecast (status='published').

        Per owner: once published, the forecast is IMMUTABLE.
        """
        row = self.db.get(ForecastRow, forecast_id)
        if row is None or row.tenant_id != tenant_id:
            raise ValueError(f"forecast {forecast_id} not found for tenant")

        if row.status == "published":
            raise ValueError(
                f"forecast {forecast_id} is already published — IMMUTABLE. "
                "Create a revision instead."
            )

        # Per owner: published requires cutoff_date for replay safety
        if row.cutoff_date is None:
            raise ValueError("published forecast requires cutoff_date")

        # Per owner: cutoff must not be later than issue date (no future leakage)
        issue = issue_date or datetime.now(UTC)
        # SQLite may return naive datetimes; coerce to UTC-aware
        if row.cutoff_date is not None:
            cutoff = row.cutoff_date
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=UTC)
            issue_aware = issue if issue.tzinfo is not None else issue.replace(tzinfo=UTC)
            if cutoff > issue_aware:
                raise ValueError(
                    "cutoff_date must be <= issue_date (no future leakage)"
                )

        row.status = "published"
        row.issue_date = issue
        row.published_at = issue
        row.payload["status"] = "published"
        row.payload["issue_date"] = issue.isoformat()
        row.payload["published_at"] = issue.isoformat()
        self.db.commit()
        return row

    def revise_forecast(
        self,
        *,
        original_forecast_id: str,
        tenant_id: str,
        new_point_estimate: float | None = None,
        new_scenarios: list[dict[str, Any]] | None = None,
        new_assumptions: list[str] | None = None,
        rationale: str = "",
    ) -> ForecastRow:
        """Create a revision of a published forecast.

        Per owner:
        > "إنشاء مراجعات جديدة مرتبطة بالإصدارات الأصلية دون محو التاريخ."

        The original forecast's status becomes 'superseded'; a new forecast
        is created with subsequent_revision_of pointing to the original.
        """
        original = self.db.get(ForecastRow, original_forecast_id)
        if original is None or original.tenant_id != tenant_id:
            raise ValueError(f"forecast {original_forecast_id} not found")

        if original.status != "published":
            raise ValueError(
                f"forecast {original_forecast_id} is not published (status={original.status}). "
                "Only published forecasts can be revised."
            )

        # Mark original as superseded
        original.status = "superseded"

        # Create the revision
        revision_id = f"fc-{secrets.token_hex(8)}"
        revision = ForecastRow(
            id=revision_id,
            tenant_id=tenant_id,
            investigation_id=original.investigation_id,
            target=original.target,
            metric=original.metric,
            unit=original.unit,
            horizon_end=original.horizon_end,
            reference_region=original.reference_region,
            method=original.method,
            method_version=original.method_version,
            status="draft",  # revision starts as draft; must be published separately
            subsequent_revision_of=original_forecast_id,
            cutoff_date=original.cutoff_date,
            point_estimate=new_point_estimate or original.point_estimate,
            probability_distribution=original.probability_distribution,
            scenarios=new_scenarios or original.scenarios,
            assumptions=new_assumptions or original.assumptions,
            input_dataset_hashes=original.input_dataset_hashes,
            baseline_method=original.baseline_method,
            baseline_value=original.baseline_value,
            payload={
                "id": revision_id,
                "method": original.method,
                "target": original.target,
                "subsequent_revision_of": original_forecast_id,
                "revision_rationale": rationale,
                "status": "draft",
            },
        )

        # Link original to revision
        original.superseded_by = revision_id

        self.db.add(revision)
        self.db.commit()
        return revision

    def get_forecast(
        self, forecast_id: str, *, tenant_id: str
    ) -> ForecastRow | None:
        row = self.db.get(ForecastRow, forecast_id)
        if row is None or row.tenant_id != tenant_id:
            return None
        return row

    def try_modify_published_forecast(
        self,
        *,
        forecast_id: str,
        tenant_id: str,
        new_point_estimate: float,
    ) -> bool:
        """Attempt to modify a published forecast.

        Per owner (G06 Scenario D):
        > "انشر توقعاً ثم حاول تعديله. يجب رفض تعديل النسخة المنشورة."

        Returns False (modification rejected). The caller should use
        revise_forecast instead.
        """
        row = self.db.get(ForecastRow, forecast_id)
        if row is None or row.tenant_id != tenant_id:
            return False
        if row.status == "published":
            return False  # IMMUTABLE — modification rejected
        # If draft, modification is allowed
        row.point_estimate = new_point_estimate
        self.db.commit()
        return True


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: create synthetic test data for the battery cost scenario
# ─────────────────────────────────────────────────────────────────────────────


def create_battery_cost_test_data() -> list[DataPoint]:
    """Create synthetic battery cost test data for Scenario A.

    Per owner (G06):
    > "إذا لم توجد سلسلة زمنية موثوقة متاحة، لا تختلق بيانات حقيقية؛
    > استخدم بيانات اختبار اصطناعية معلونة بوضوح لإثبات المحرك."

    This data is SYNTHETIC — it approximates the real-world trend of
    Li-ion battery pack cost per kWh declining from ~$1200 in 2010 to
    ~$140 in 2023, but the exact numbers are illustrative, not sourced.
    """
    # Synthetic data: annual battery pack cost per kWh (USD)
    data = [
        (datetime(2010, 1, 1, tzinfo=UTC), 1200.0),
        (datetime(2011, 1, 1, tzinfo=UTC), 900.0),
        (datetime(2012, 1, 1, tzinfo=UTC), 700.0),
        (datetime(2013, 1, 1, tzinfo=UTC), 600.0),
        (datetime(2014, 1, 1, tzinfo=UTC), 540.0),
        (datetime(2015, 1, 1, tzinfo=UTC), 450.0),
        (datetime(2016, 1, 1, tzinfo=UTC), 380.0),
        (datetime(2017, 1, 1, tzinfo=UTC), 300.0),
        (datetime(2018, 1, 1, tzinfo=UTC), 250.0),
        (datetime(2019, 1, 1, tzinfo=UTC), 220.0),
        (datetime(2020, 1, 1, tzinfo=UTC), 180.0),
        (datetime(2021, 1, 1, tzinfo=UTC), 157.0),
        (datetime(2022, 1, 1, tzinfo=UTC), 151.0),
        (datetime(2023, 1, 1, tzinfo=UTC), 139.0),
    ]
    return [
        DataPoint(
            timestamp=ts,
            value=val,
            source_id="synthetic-battery-cost",
            published_at=ts,  # published the same year as the event
        )
        for ts, val in data
    ]


def create_leakage_test_data() -> list[DataPoint]:
    """Create test data with intentional leakage for Scenario C.

    Per owner (G06):
    > "أنشئ حالة تحتوي على دليل يتعلق بحدث قديم لكنه نُشر بعد تاريخ cutoff.
    > يجب أن يستبعده الاختبار التاريخي، حتى لو كان تاريخ الحدث نفسه سابقاً."
    """
    return [
        # Legitimate data: event in 2018, published in 2018
        DataPoint(
            timestamp=datetime(2018, 1, 1, tzinfo=UTC),
            value=250.0,
            source_id="legitimate-2018",
            published_at=datetime(2018, 3, 1, tzinfo=UTC),
        ),
        # Legitimate data: event in 2019, published in 2019
        DataPoint(
            timestamp=datetime(2019, 1, 1, tzinfo=UTC),
            value=220.0,
            source_id="legitimate-2019",
            published_at=datetime(2019, 3, 1, tzinfo=UTC),
        ),
        # LEAKAGE: event in 2020 (before cutoff), but published in 2023 (after cutoff)
        DataPoint(
            timestamp=datetime(2020, 1, 1, tzinfo=UTC),  # event before cutoff
            value=180.0,
            source_id="leaked-2020-published-2023",
            published_at=datetime(2023, 6, 1, tzinfo=UTC),  # published AFTER cutoff!
        ),
    ]


__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "BaselineForecaster",
    "DataPoint",
    "EvidenceAssessment",
    "ForecastMethod",
    "ForecastPolicyService",
    "ForecastRegistry",
    "ForecastResult",
    "create_battery_cost_test_data",
    "create_leakage_test_data",
]
