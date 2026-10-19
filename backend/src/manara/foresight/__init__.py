"""MANARA Foresight Engine (G06).

Public API:
* :class:`ForecastPolicyService` — methodology selection (Central Forecast Router)
* :class:`BaselineForecaster` — naive + seasonal naive baselines
* :class:`BacktestEngine` — historical replay with bitemporal leakage prevention
* :class:`ForecastRegistry` — immutable publication + revision tracking
* :func:`create_battery_cost_test_data` — synthetic test data for Scenario A
* :func:`create_leakage_test_data` — intentional leakage data for Scenario C
"""

from manara.foresight.engine import (
    BacktestEngine,
    BacktestResult,
    BaselineForecaster,
    DataPoint,
    EvidenceAssessment,
    ForecastMethod,
    ForecastPolicyService,
    ForecastRegistry,
    ForecastResult,
    create_battery_cost_test_data,
    create_leakage_test_data,
)

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
