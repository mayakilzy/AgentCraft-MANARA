"""Tests for the Foresight Engine (G06).

The four canonical acceptance scenarios:

A. Battery Cost Forecast — quantitative forecast with baseline comparison
B. Insufficient Evidence — must return "insufficient_evidence", no fake %
C. Historical Leakage — evidence published after cutoff must be rejected
D. Immutable Forecast — published forecasts cannot be modified

Per owner (G06):
> "أهم اختبار بالنسبة لي هو أن نعطي منارة معلومة صحيحة تاريخياً لكنها
> لم تكن منشورة وقت التوقع، ثم نتأكد أنها ترفض استخدامها في حساب ذلك التوقع."
> "إذا نجحت المنظومة في القول 'لا أعرف' عندما تكون الأدلة غير كافية،
> فهذا ليس فشلاً؛ بل أحد أهم شروط الثقة فيها."
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime

os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", "/home/z/my-project/.models")
os.environ.setdefault("HF_HOME", "/home/z/my-project/.models/hf_cache")

import pytest
from sqlalchemy.orm import Session

from manara.db.session import Base
from manara.foresight import (
    BacktestEngine,
    BaselineForecaster,
    DataPoint,
    ForecastPolicyService,
    ForecastRegistry,
    create_battery_cost_test_data,
    create_leakage_test_data,
)


@pytest.fixture()
def db_session(engine) -> Iterator[Session]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture()
def policy():
    return ForecastPolicyService()


@pytest.fixture()
def backtest_engine(db_session):
    return BacktestEngine(db_session)


@pytest.fixture()
def registry(db_session):
    return ForecastRegistry(db_session)


# ─────────────────────────────────────────────────────────────────────────────
# Scenario A — Battery Cost Forecast (quantitative, with baseline)
# ─────────────────────────────────────────────────────────────────────────────


class TestScenarioABatteryCost:
    """Per owner (G06):
    > "استخدم سلسلة زمنية تاريخية مناسبة ومحددة المصدر، أو مجموعة بيانات
    > اختبار موسومة بوضوح، لبناء توقع قابل للقياس."
    """

    def test_sufficient_data_selects_quantitative_method(self, policy):
        data = create_battery_cost_test_data()
        cutoff = datetime(2020, 1, 1, tzinfo=UTC)
        result = policy.assess_evidence(data_points=data, cutoff_date=cutoff)
        assert result.sufficient_for_quantitative is True
        assert result.recommended_method != "insufficient_evidence"
        assert len(result.data_points_before_cutoff) >= 5

    def test_forecast_has_point_estimate_and_baseline(self, policy, registry, db_session):
        data = create_battery_cost_test_data()
        cutoff = datetime(2020, 1, 1, tzinfo=UTC)
        assessment = policy.assess_evidence(data_points=data, cutoff_date=cutoff)

        # Create a forecast based on the assessment
        before = assessment.data_points_before_cutoff
        baseline_value = BaselineForecaster.naive_forecast(before)

        row = registry.create_forecast(
            tenant_id="tenant_demo",
            target="Global average Li-ion battery pack cost per kWh by 2025",
            metric="cost_per_kwh",
            unit="USD/kWh",
            horizon_end=datetime(2025, 1, 1, tzinfo=UTC),
            reference_region="global",
            method=assessment.recommended_method,
            method_version="0.1.0",
            cutoff_date=cutoff,
            point_estimate=baseline_value,
            baseline_method="naive",
            baseline_value=baseline_value,
            assumptions=["Synthetic test data; not real-sourced values."],
        )
        assert row.status == "draft"
        assert row.point_estimate is not None
        assert row.baseline_value is not None

    def test_backtest_computes_mae_and_compares_to_baseline(self, policy, registry, backtest_engine, db_session):
        data = create_battery_cost_test_data()
        cutoff = datetime(2020, 1, 1, tzinfo=UTC)

        # Create a forecast to attach the backtest to
        row = registry.create_forecast(
            tenant_id="tenant_demo",
            target="Battery cost forecast",
            metric="cost_per_kwh",
            unit="USD/kWh",
            horizon_end=datetime(2025, 1, 1, tzinfo=UTC),
            reference_region="global",
            method="naive_seasonal",
            method_version="0.1.0",
            cutoff_date=cutoff,
        )

        result = backtest_engine.run_backtest(
            all_data_points=data,
            cutoff_date=cutoff,
            horizon_days=365,
            tenant_id="tenant_demo",
            forecast_id=row.id,
        )
        assert result.leakage_detected is False
        assert result.data_cutoff_verified is True
        assert result.mae is not None
        assert result.baseline_mae is not None
        # The model (naive) and baseline (seasonal naive) should both produce
        # finite error metrics.
        assert result.mae < float("inf")


# ─────────────────────────────────────────────────────────────────────────────
# Scenario B — Insufficient Evidence
# ─────────────────────────────────────────────────────────────────────────────


class TestScenarioBInsufficientEvidence:
    """Per owner (G06):
    > "اطلب توقعاً رقمياً لمجال لا تتوفر فيه أدلة كافية.
    > النتيجة الصحيحة: insufficient_evidence، دون أي نسب احتمالية مختلقة."
    """

    def test_no_data_returns_insufficient_evidence(self, policy):
        result = policy.assess_evidence(
            data_points=[],
            cutoff_date=datetime(2024, 1, 1, tzinfo=UTC),
        )
        assert result.recommended_method == "insufficient_evidence"
        assert result.sufficient_for_quantitative is False

    def test_too_few_data_points_returns_insufficient_evidence(self, policy):
        """Per owner: need ≥ 5 data points before cutoff."""
        data = [
            DataPoint(timestamp=datetime(2020, 1, 1, tzinfo=UTC), value=100.0, source_id="s1"),
            DataPoint(timestamp=datetime(2021, 1, 1, tzinfo=UTC), value=90.0, source_id="s2"),
        ]
        result = policy.assess_evidence(
            data_points=data,
            cutoff_date=datetime(2022, 1, 1, tzinfo=UTC),
        )
        assert result.recommended_method == "insufficient_evidence"
        assert "need" in result.assessment_reasoning.lower()

    def test_insufficient_evidence_forbids_probability_distribution(self, registry):
        """Per owner: 'لا تستخدم نسب احتمالية غير معايرة.'"""
        with pytest.raises(ValueError, match="insufficient_evidence"):
            registry.create_forecast(
                tenant_id="tenant_demo",
                target="Some target",
                metric="some_metric",
                unit="count",
                horizon_end=datetime(2025, 1, 1, tzinfo=UTC),
                reference_region="global",
                method="insufficient_evidence",
                method_version="0.1.0",
                cutoff_date=datetime(2024, 1, 1, tzinfo=UTC),
                probability_distribution={"mean": 42.0},  # FORBIDDEN
            )

    def test_insufficient_evidence_forecast_created_without_distribution(self, registry):
        row = registry.create_forecast(
            tenant_id="tenant_demo",
            target="Predict adoption of technology X by 2030",
            metric="adoption_rate",
            unit="percent",
            horizon_end=datetime(2030, 1, 1, tzinfo=UTC),
            reference_region="global",
            method="insufficient_evidence",
            method_version="0.1.0",
            cutoff_date=datetime(2024, 1, 1, tzinfo=UTC),
            assumptions=["No sufficient time-series data available for quantitative forecast."],
        )
        assert row.method == "insufficient_evidence"
        assert row.probability_distribution == {}
        assert row.point_estimate is None


# ─────────────────────────────────────────────────────────────────────────────
# Scenario C — Historical Leakage (THE KEY TEST)
# ─────────────────────────────────────────────────────────────────────────────


class TestScenarioCHistoricalLeakage:
    """THE KEY G06 ACCEPTANCE TEST.

    Per owner (G06):
    > "أهم اختبار بالنسبة لي هو أن نعطي منارة معلومة صحيحة تاريخياً لكنها
    > لم تكن منشورة وقت التوقع، ثم نتأكد أنها ترفض استخدامها في حساب
    > ذلك التوقع."
    > "أنشئ حالة تحتوي على دليل يتعلق بحدث قديم لكنه نُشر بعد تاريخ cutoff.
    > يجب أن يستبعده الاختبار التاريخي، حتى لو كان تاريخ الحدث نفسه سابقاً."
    """

    def test_leaked_data_is_detected_and_excluded(self, backtest_engine, registry, db_session):
        """Data with event BEFORE cutoff but publication AFTER cutoff = LEAKAGE."""
        data = create_leakage_test_data()
        # Cutoff is 2021-01-01
        # Legitimate: event 2018, published 2018 → before cutoff ✓
        # Legitimate: event 2019, published 2019 → before cutoff ✓
        # LEAKAGE: event 2020, published 2023 → event before cutoff BUT published after!

        cutoff = datetime(2021, 1, 1, tzinfo=UTC)

        row = registry.create_forecast(
            tenant_id="tenant_demo",
            target="Test forecast",
            metric="test_metric",
            unit="count",
            horizon_end=datetime(2022, 1, 1, tzinfo=UTC),
            reference_region="global",
            method="naive_seasonal",
            method_version="0.1.0",
            cutoff_date=cutoff,
        )

        result = backtest_engine.run_backtest(
            all_data_points=data,
            cutoff_date=cutoff,
            horizon_days=365,
            tenant_id="tenant_demo",
            forecast_id=row.id,
        )
        # Leakage MUST be detected
        assert result.leakage_detected is True, (
            "Leakage not detected! Data published after cutoff was not caught."
        )
        assert len(result.leaked_evidence_ids) > 0, (
            "Leaked evidence IDs not reported."
        )
        # The leaked evidence should mention the source_id
        leaked_str = str(result.leaked_evidence_ids)
        assert "leaked-2020-published-2023" in leaked_str, (
            f"Leaked source not in report: {leaked_str}"
        )
        # Data cutoff should NOT be verified (leakage found)
        assert result.data_cutoff_verified is False

    def test_no_leakage_when_all_data_published_before_cutoff(self, backtest_engine, registry, db_session):
        """When all data is published before cutoff, no leakage."""
        data = [
            DataPoint(
                timestamp=datetime(2018, 1, 1, tzinfo=UTC),
                value=100.0,
                source_id="s1",
                published_at=datetime(2018, 3, 1, tzinfo=UTC),
            ),
            DataPoint(
                timestamp=datetime(2019, 1, 1, tzinfo=UTC),
                value=90.0,
                source_id="s2",
                published_at=datetime(2019, 3, 1, tzinfo=UTC),
            ),
            DataPoint(
                timestamp=datetime(2020, 1, 1, tzinfo=UTC),
                value=80.0,
                source_id="s3",
                published_at=datetime(2020, 3, 1, tzinfo=UTC),
            ),
        ]
        cutoff = datetime(2021, 1, 1, tzinfo=UTC)

        row = registry.create_forecast(
            tenant_id="tenant_demo",
            target="Test forecast",
            metric="test_metric",
            unit="count",
            horizon_end=datetime(2022, 1, 1, tzinfo=UTC),
            reference_region="global",
            method="naive_seasonal",
            method_version="0.1.0",
            cutoff_date=cutoff,
        )

        result = backtest_engine.run_backtest(
            all_data_points=data,
            cutoff_date=cutoff,
            horizon_days=365,
            tenant_id="tenant_demo",
            forecast_id=row.id,
        )
        assert result.leakage_detected is False
        assert result.data_cutoff_verified is True

    def test_policy_splits_data_by_published_at_not_observed_at(self, policy):
        """Per owner: 'لا تفترض أن observed_at وحده يحدد ما كان معروفاً وقتها.'

        A study published in September about an event in June is NOT
        available at a July cutoff — even though the event happened before.
        """
        data = [
            DataPoint(
                timestamp=datetime(2020, 6, 1, tzinfo=UTC),  # event in June
                value=100.0,
                source_id="study-published-sept",
                published_at=datetime(2020, 9, 1, tzinfo=UTC),  # published in Sept!
            ),
        ]
        cutoff = datetime(2020, 7, 1, tzinfo=UTC)  # July cutoff

        result = policy.assess_evidence(data_points=data, cutoff_date=cutoff)
        # The data point's event was in June (before cutoff), but it was
        # published in September (after cutoff) → it should be AFTER cutoff.
        assert len(result.data_points_before_cutoff) == 0, (
            "Data published after cutoff was incorrectly included as 'before cutoff'"
        )
        assert len(result.data_points_after_cutoff) == 1, (
            "Data published after cutoff was not correctly classified as 'after'"
        )
        assert result.recommended_method == "insufficient_evidence", (
            "Should be insufficient_evidence because the only data point "
            "was published after the cutoff"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Scenario D — Immutable Forecast
# ─────────────────────────────────────────────────────────────────────────────


class TestScenarioDImmutableForecast:
    """Per owner (G06):
    > "انشر توقعاً ثم حاول تعديله. يجب رفض تعديل النسخة المنشورة،
    > مع السماح بإنشاء مراجعة جديدة مرتبطة بها."
    """

    def test_published_forecast_cannot_be_modified(self, registry, db_session):
        row = registry.create_forecast(
            tenant_id="tenant_demo",
            target="Test target",
            metric="test_metric",
            unit="count",
            horizon_end=datetime(2025, 1, 1, tzinfo=UTC),
            reference_region="global",
            method="naive_seasonal",
            method_version="0.1.0",
            cutoff_date=datetime(2024, 1, 1, tzinfo=UTC),
            point_estimate=100.0,
        )
        registry.publish_forecast(forecast_id=row.id, tenant_id="tenant_demo")

        # Attempt to modify the published forecast
        modified = registry.try_modify_published_forecast(
            forecast_id=row.id, tenant_id="tenant_demo", new_point_estimate=999.0
        )
        assert modified is False, (
            "Published forecast was modified! Immutability violated."
        )

        # Verify the original value is unchanged
        row_after = registry.get_forecast(row.id, tenant_id="tenant_demo")
        assert row_after.point_estimate == 100.0, (
            "Published forecast value was changed despite immutability."
        )

    def test_draft_forecast_can_be_modified(self, registry, db_session):
        row = registry.create_forecast(
            tenant_id="tenant_demo",
            target="Test target",
            metric="test_metric",
            unit="count",
            horizon_end=datetime(2025, 1, 1, tzinfo=UTC),
            reference_region="global",
            method="naive_seasonal",
            method_version="0.1.0",
            cutoff_date=datetime(2024, 1, 1, tzinfo=UTC),
            point_estimate=100.0,
        )
        # Draft CAN be modified
        modified = registry.try_modify_published_forecast(
            forecast_id=row.id, tenant_id="tenant_demo", new_point_estimate=200.0
        )
        assert modified is True
        row_after = registry.get_forecast(row.id, tenant_id="tenant_demo")
        assert row_after.point_estimate == 200.0

    def test_revision_creates_new_linked_forecast(self, registry, db_session):
        """Per owner: 'إنشاء مراجعات جديدة مرتبطة بالإصدارات الأصلية دون محو التاريخ.'"""
        # Create + publish
        original = registry.create_forecast(
            tenant_id="tenant_demo",
            target="Battery cost by 2025",
            metric="cost_per_kwh",
            unit="USD/kWh",
            horizon_end=datetime(2025, 1, 1, tzinfo=UTC),
            reference_region="global",
            method="naive_seasonal",
            method_version="0.1.0",
            cutoff_date=datetime(2024, 1, 1, tzinfo=UTC),
            point_estimate=140.0,
        )
        registry.publish_forecast(forecast_id=original.id, tenant_id="tenant_demo")

        # Revise
        revision = registry.revise_forecast(
            original_forecast_id=original.id,
            tenant_id="tenant_demo",
            new_point_estimate=135.0,
            rationale="Updated with new data from Q2 2024.",
        )
        assert revision.id != original.id
        assert revision.subsequent_revision_of == original.id

        # Original should be superseded
        original_after = registry.get_forecast(original.id, tenant_id="tenant_demo")
        assert original_after.status == "superseded"
        assert original_after.superseded_by == revision.id

    def test_revising_draft_forecast_fails(self, registry, db_session):
        """Only published forecasts can be revised."""
        draft = registry.create_forecast(
            tenant_id="tenant_demo",
            target="Test target",
            metric="test_metric",
            unit="count",
            horizon_end=datetime(2025, 1, 1, tzinfo=UTC),
            reference_region="global",
            method="naive_seasonal",
            method_version="0.1.0",
            cutoff_date=datetime(2024, 1, 1, tzinfo=UTC),
        )
        with pytest.raises(ValueError, match="not published"):
            registry.revise_forecast(
                original_forecast_id=draft.id,
                tenant_id="tenant_demo",
                new_point_estimate=200.0,
                rationale="Attempt to revise a draft.",
            )

    def test_publishing_requires_cutoff_date(self, registry, db_session):
        """Per owner: 'cutoff_date must be <= issue_date (no future leakage).'"""
        # Create WITHOUT cutoff_date — should fail at publish time
        row = registry.create_forecast(
            tenant_id="tenant_demo",
            target="Test target",
            metric="test_metric",
            unit="count",
            horizon_end=datetime(2025, 1, 1, tzinfo=UTC),
            reference_region="global",
            method="naive_seasonal",
            method_version="0.1.0",
            cutoff_date=datetime(2024, 1, 1, tzinfo=UTC),
        )
        # Manually null out cutoff_date to simulate a bad forecast
        row.cutoff_date = None
        db_session.commit()

        with pytest.raises(ValueError, match="cutoff_date"):
            registry.publish_forecast(forecast_id=row.id, tenant_id="tenant_demo")


# ─────────────────────────────────────────────────────────────────────────────
# Baseline forecaster tests
# ─────────────────────────────────────────────────────────────────────────────


class TestBaselineForecaster:
    def test_naive_forecast_returns_last_value(self):
        data = [
            DataPoint(timestamp=datetime(2020, 1, 1, tzinfo=UTC), value=100.0, source_id="s1"),
            DataPoint(timestamp=datetime(2021, 1, 1, tzinfo=UTC), value=90.0, source_id="s2"),
            DataPoint(timestamp=datetime(2022, 1, 1, tzinfo=UTC), value=80.0, source_id="s3"),
        ]
        assert BaselineForecaster.naive_forecast(data) == 80.0

    def test_mae_computation(self):
        mae = BaselineForecaster.compute_mae([100, 200, 300], [110, 190, 310])
        assert abs(mae - 10.0) < 0.01

    def test_rmse_computation(self):
        rmse = BaselineForecaster.compute_rmse([100, 200], [110, 190])
        assert abs(rmse - 10.0) < 0.01
