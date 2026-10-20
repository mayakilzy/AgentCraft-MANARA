"""``/foresight`` API routes — Foresight Engine surface (G06).

Endpoints:
* ``POST   /foresight/assess``          — assess evidence and recommend method
* ``POST   /foresight/forecasts``        — create a draft forecast
* ``GET    /foresight/forecasts``        — list forecasts (tenant-scoped)
* ``POST   /foresight/forecasts/{id}/publish`` — publish (immutable)
* ``POST   /foresight/forecasts/{id}/revise`` — create a revision
* ``POST   /foresight/forecasts/{id}/try-modify`` — test immutability
* ``GET    /foresight/forecasts/{id}``    — fetch a forecast
* ``GET    /foresight/forecasts/{id}/backtests`` — list backtest history
* ``POST   /foresight/backtest``          — run a backtest with leakage check
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from manara.api.errors import NotFoundError, ValidationError
from manara.config import settings
from manara.db.foresight_models import BacktestResultRow, ForecastRow
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


@router.get(
    "/forecasts",
    summary="List forecasts (tenant-scoped)",
)
def list_forecasts(
    db: Session = Depends(get_db),
    investigation_id: str | None = Query(
        default=None,
        description="Optional filter by investigation_id",
    ),
    status: str | None = Query(
        default=None,
        description="Optional filter by status (draft|published|superseded)",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    """List forecasts for the current tenant (R-06 / G-list-3).

    Supports optional filtering by investigation_id and status. Returns
    persisted forecast summaries ordered by ``created_at`` DESC (newest
    first). Tenant isolation is enforced.

    The ``draft``, ``published``, and ``superseded`` status semantics are
    preserved verbatim from the persistence layer. No recalculation;
    no immutability bypass.
    """
    tenant_id = _resolve_tenant()
    stmt = select(ForecastRow).where(ForecastRow.tenant_id == tenant_id)
    if investigation_id:
        stmt = stmt.where(ForecastRow.investigation_id == investigation_id)
    if status:
        stmt = stmt.where(ForecastRow.status == status)
    stmt = stmt.order_by(ForecastRow.created_at.desc()).limit(limit).offset(offset)
    rows = list(db.execute(stmt).scalars())
    return [
        {
            "id": r.id,
            "status": r.status,
            "method": r.method,
            "target": r.target,
            "metric": r.metric,
            "unit": r.unit,
            "point_estimate": r.point_estimate,
            "cutoff_date": r.cutoff_date.isoformat() if r.cutoff_date else None,
            "issue_date": r.issue_date.isoformat() if r.issue_date else None,
            "investigation_id": r.investigation_id,
            "subsequent_revision_of": r.subsequent_revision_of,
            "superseded_by": r.superseded_by,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


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
        # R-03 (MANARA-UI-BACKEND-CLOSURE-01): expose the persisted
        # probability_distribution. Empty dict when method="insufficient_evidence"
        # (the engine refuses to fabricate probabilities in that case).
        # This is the actual stored value — no fabrication, no confidence
        # intervals invented client-side.
        "probability_distribution": row.probability_distribution or {},
    }


@router.get(
    "/forecasts/{forecast_id}/backtests",
    summary="List backtest history for a forecast (tenant-scoped)",
)
def list_backtests(
    forecast_id: str,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    """List backtest records for a forecast (R-07 / G-list-4).

    Returns persisted ``BacktestResultRow`` rows associated with the
    forecast. Tenant isolation is enforced. The parent forecast must
    belong to the current tenant (otherwise 404).

    The response preserves all available measurements:
    - ``mae``, ``rmse``, ``baseline_mae``, ``improvement_over_baseline``
    - ``leakage_detected``, ``data_cutoff_verified``
    - ``leaked_evidence_ids`` (where recorded)
    - ``data_points_used``

    Negative ``improvement_over_baseline`` values are preserved (they
    indicate the forecast performed WORSE than the baseline). No
    recalculation; this is a pure read of historical results.
    """
    tenant_id = _resolve_tenant()
    # Verify the parent forecast exists and belongs to the tenant.
    registry = ForecastRegistry(db)
    parent = registry.get_forecast(forecast_id, tenant_id=tenant_id)
    if parent is None:
        raise NotFoundError(f"forecast {forecast_id} not found")

    stmt = (
        select(BacktestResultRow)
        .where(
            BacktestResultRow.tenant_id == tenant_id,
            BacktestResultRow.forecast_id == forecast_id,
        )
        .order_by(BacktestResultRow.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = list(db.execute(stmt).scalars())
    return [
        {
            "id": r.id,
            "forecast_id": r.forecast_id,
            "leakage_detected": r.leakage_detected,
            "leaked_evidence_ids": r.leaked_evidence_ids,
            "mae": r.mae,
            "rmse": r.rmse,
            "baseline_mae": r.baseline_mae,
            "improvement_over_baseline": r.improvement_over_baseline,
            "data_points_used": r.data_points_used,
            "data_cutoff_verified": r.data_cutoff_verified,
            "notes": r.notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


__all__ = ["router"]
