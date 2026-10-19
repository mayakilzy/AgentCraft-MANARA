"""``/foresight`` API routes — Foresight Engine surface (G06).

Endpoints:
* ``POST   /foresight/assess``          — assess evidence and recommend method
* ``POST   /foresight/forecasts``        — create a draft forecast
* ``POST   /foresight/forecasts/{id}/publish`` — publish (immutable)
* ``POST   /foresight/forecasts/{id}/revise`` — create a revision
* ``POST   /foresight/forecasts/{id}/try-modify`` — test immutability
* ``POST   /foresight/backtest``          — run a backtest with leakage check
* ``GET    /foresight/forecasts/{id}``    — fetch a forecast
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from manara.api.errors import NotFoundError, ValidationError
from manara.config import settings
from manara.db.session import get_db
from manara.foresight import (
    BacktestEngine,
    DataPoint,
    ForecastPolicyService,
    ForecastRegistry,
)

router = APIRouter(prefix="/foresight", tags=["foresight"])


def _resolve_tenant() -> str:
    return settings.default_tenant_id


class DataPointModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timestamp: str
    value: float
    source_id: str
    published_at: str | None = None


class AssessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_points: list[DataPointModel]
    cutoff_date: str
    has_contradictions: bool = False


class CreateForecastRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str = Field(..., min_length=10)
    metric: str = Field(..., min_length=1)
    unit: str = Field(..., min_length=1)
    horizon_end: str
    reference_region: str = Field(..., min_length=1)
    method: str
    method_version: str = Field(..., min_length=1)
    cutoff_date: str
    point_estimate: float | None = None
    probability_distribution: dict[str, Any] | None = None
    scenarios: list[dict[str, Any]] | None = None
    assumptions: list[str] | None = None
    input_dataset_hashes: list[str] | None = None
    baseline_method: str | None = None
    baseline_value: float | None = None
    investigation_id: str | None = None


class BacktestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    forecast_id: str
    data_points: list[DataPointModel]
    cutoff_date: str
    horizon_days: int = 30


@router.post("/assess", summary="Assess evidence and recommend forecasting method")
def assess_evidence(req: AssessRequest) -> dict[str, Any]:
    policy = ForecastPolicyService()
    dps = [
        DataPoint(
            timestamp=datetime.fromisoformat(dp.timestamp),
            value=dp.value,
            source_id=dp.source_id,
            published_at=datetime.fromisoformat(dp.published_at) if dp.published_at else None,
        )
        for dp in req.data_points
    ]
    cutoff = datetime.fromisoformat(req.cutoff_date)
    result = policy.assess_evidence(data_points=dps, cutoff_date=cutoff, has_contradictions=req.has_contradictions)
    return {
        "has_time_series": result.has_time_series,
        "sufficient_for_quantitative": result.sufficient_for_quantitative,
        "recommended_method": result.recommended_method,
        "assessment_reasoning": result.assessment_reasoning,
        "data_points_before_cutoff": len(result.data_points_before_cutoff),
        "data_points_after_cutoff": len(result.data_points_after_cutoff),
    }


@router.post("/forecasts", status_code=201, summary="Create a draft forecast")
def create_forecast(req: CreateForecastRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    registry = ForecastRegistry(db)
    try:
        row = registry.create_forecast(
            tenant_id=tenant_id,
            target=req.target,
            metric=req.metric,
            unit=req.unit,
            horizon_end=datetime.fromisoformat(req.horizon_end),
            reference_region=req.reference_region,
            method=req.method,
            method_version=req.method_version,
            cutoff_date=datetime.fromisoformat(req.cutoff_date),
            point_estimate=req.point_estimate,
            probability_distribution=req.probability_distribution,
            scenarios=req.scenarios,
            assumptions=req.assumptions,
            input_dataset_hashes=req.input_dataset_hashes,
            baseline_method=req.baseline_method,
            baseline_value=req.baseline_value,
            investigation_id=req.investigation_id,
        )
    except ValueError as e:
        raise ValidationError(str(e)) from e
    return {"forecast_id": row.id, "status": row.status, "method": row.method}


@router.post("/forecasts/{forecast_id}/publish", summary="Publish a forecast (immutable)")
def publish_forecast(forecast_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    registry = ForecastRegistry(db)
    try:
        row = registry.publish_forecast(forecast_id=forecast_id, tenant_id=tenant_id)
    except ValueError as e:
        raise ValidationError(str(e)) from e
    return {"forecast_id": row.id, "status": row.status, "published_at": row.published_at.isoformat() if row.published_at else None}


@router.post("/forecasts/{forecast_id}/revise", summary="Create a revision (original becomes superseded)")
def revise_forecast(
    forecast_id: str,
    req: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    registry = ForecastRegistry(db)
    try:
        revision = registry.revise_forecast(
            original_forecast_id=forecast_id,
            tenant_id=tenant_id,
            new_point_estimate=req.get("new_point_estimate"),
            new_scenarios=req.get("new_scenarios"),
            new_assumptions=req.get("new_assumptions"),
            rationale=req.get("rationale", ""),
        )
    except ValueError as e:
        raise ValidationError(str(e)) from e
    return {
        "revision_id": revision.id,
        "original_id": forecast_id,
        "status": revision.status,
        "subsequent_revision_of": revision.subsequent_revision_of,
    }


@router.post("/forecasts/{forecast_id}/try-modify", summary="Test immutability of published forecasts")
def try_modify_forecast(
    forecast_id: str,
    req: dict[str, Any],
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Per owner (G06 Scenario D): 'انشر توقعاً ثم حاول تعديله. يجب رفض
    تعديل النسخة المنشورة.'"""
    tenant_id = _resolve_tenant()
    registry = ForecastRegistry(db)
    new_value = req.get("new_point_estimate")
    if new_value is None:
        raise ValidationError("new_point_estimate is required")
    modified = registry.try_modify_published_forecast(
        forecast_id=forecast_id, tenant_id=tenant_id, new_point_estimate=float(new_value)
    )
    return {"forecast_id": forecast_id, "modification_accepted": modified}


@router.post("/backtest", summary="Run a backtest with bitemporal leakage check")
def run_backtest(req: BacktestRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    engine = BacktestEngine(db)
    dps = [
        DataPoint(
            timestamp=datetime.fromisoformat(dp.timestamp),
            value=dp.value,
            source_id=dp.source_id,
            published_at=datetime.fromisoformat(dp.published_at) if dp.published_at else None,
        )
        for dp in req.data_points
    ]
    cutoff = datetime.fromisoformat(req.cutoff_date)
    result = engine.run_backtest(
        all_data_points=dps,
        cutoff_date=cutoff,
        horizon_days=req.horizon_days,
        tenant_id=tenant_id,
        forecast_id=req.forecast_id,
    )
    return {
        "leakage_detected": result.leakage_detected,
        "leaked_evidence_ids": result.leaked_evidence_ids,
        "mae": result.mae,
        "rmse": result.rmse,
        "baseline_mae": result.baseline_mae,
        "improvement_over_baseline": result.improvement_over_baseline,
        "data_points_used": result.data_points_used,
        "data_cutoff_verified": result.data_cutoff_verified,
        "notes": result.notes,
    }


@router.get("/forecasts/{forecast_id}", summary="Fetch a forecast")
def get_forecast(forecast_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    registry = ForecastRegistry(db)
    row = registry.get_forecast(forecast_id, tenant_id=tenant_id)
    if row is None:
        raise NotFoundError(f"forecast {forecast_id} not found")
    return {
        "id": row.id,
        "status": row.status,
        "method": row.method,
        "target": row.target,
        "metric": row.metric,
        "unit": row.unit,
        "point_estimate": row.point_estimate,
        "cutoff_date": row.cutoff_date.isoformat() if row.cutoff_date else None,
        "issue_date": row.issue_date.isoformat() if row.issue_date else None,
        "subsequent_revision_of": row.subsequent_revision_of,
        "superseded_by": row.superseded_by,
        "assumptions": row.assumptions,
        "scenarios": row.scenarios,
    }


__all__ = ["router"]
