"""``/agents`` API routes — Agent Factory surface (G05).

Endpoints:
* ``GET    /agents/recipes``                    — list agent recipes
* ``GET    /agents/recipes/{id}``                 — fetch one recipe
* ``POST   /agents/recipes/seed-clinical``       — seed the clinical reviewer recipe
* ``POST   /agents/recipes/seed-generalist``      — seed the general analyst recipe
* ``POST   /agents/resolve``                      — generalist-vs-specialist resolver
* ``POST   /agents/sessions``                     — instantiate an ephemeral session
* ``POST   /agents/sessions/{id}/execute``        — execute the session
* ``POST   /agents/sessions/{id}/terminate``       — terminate the session
* ``POST   /agents/sessions/{id}/evaluate``        — record evaluation
* ``GET    /agents/sessions``                     — list sessions (tenant-scoped)
* ``GET    /agents/sessions/{id}``                 — fetch session details

Note (MANARA-UI-BACKEND-CLOSURE-01 / R-09):
The previously-advertised ``PATCH /agents/recipes/{id}/promote`` endpoint
is NOT implemented. Recipe state promotion is currently a direct DB
operation reserved for the owner. The misleading advertisement has been
removed from this docstring.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from manara.agents import (
    AgentRecipeRegistry,
    EphemeralAgentRuntime,
    GeneralistVsSpecialistResolver,
    create_clinical_prosthetics_reviewer_recipe,
    create_general_analyst_recipe,
)
from manara.api.errors import NotFoundError, ValidationError
from manara.config import settings
from manara.db.session import get_db

router = APIRouter(prefix="/agents", tags=["agents"])


def _resolve_tenant() -> str:
    return settings.default_tenant_id


class ResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_description: str = Field(..., min_length=10, max_length=1000)
    required_evidence_types: list[str] | None = None


class InstantiateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str = Field(..., min_length=1, max_length=120)
    investigation_id: str | None = None
    mold_id: str | None = None
    task_description: str = Field(..., min_length=10, max_length=1000)
    task_input: dict[str, Any] | None = None
    capability_allowed_tools: list[str] | None = None
    investigation_constraints: list[str] | None = None


class EvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: Literal["success", "partial", "failure", "inconclusive"]
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    improvement_over_generalist: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: str = Field(default="")
    criteria_results: dict[str, Any] | None = None
    evaluator: str = Field(default="system", max_length=120)


@router.get("/recipes", summary="List agent recipes (tenant-scoped)")
def list_recipes(
    db: Session = Depends(get_db),
    specialty: str | None = Query(default=None),
    state: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    tenant_id = _resolve_tenant()
    registry = AgentRecipeRegistry(db)
    rows = registry.list_recipes(tenant_id=tenant_id, specialty=specialty, state=state)
    return [
        {
            "id": r.id,
            "display_name": r.display_name,
            "role": r.role,
            "specialty": r.specialty,
            "state": r.state,
            "version": r.version,
            "allowed_tools": r.allowed_tools_json,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/recipes/{recipe_id}", summary="Fetch one recipe")
def get_recipe(recipe_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    registry = AgentRecipeRegistry(db)
    row = registry.get_recipe(recipe_id, tenant_id=tenant_id)
    if row is None:
        raise NotFoundError(f"recipe {recipe_id} not found")
    return row.payload


@router.post("/recipes/seed-clinical", status_code=201, summary="Seed the Clinical Prosthetics Reviewer recipe")
def seed_clinical(db: Session = Depends(get_db)) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    registry = AgentRecipeRegistry(db)
    recipe = create_clinical_prosthetics_reviewer_recipe(tenant_id=tenant_id)
    row = registry.save_recipe(recipe, tenant_id=tenant_id)
    return {"recipe_id": row.id, "state": row.state, "role": row.role}


@router.post("/recipes/seed-generalist", status_code=201, summary="Seed the General Analyst recipe")
def seed_generalist(db: Session = Depends(get_db)) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    registry = AgentRecipeRegistry(db)
    recipe = create_general_analyst_recipe(tenant_id=tenant_id)
    row = registry.save_recipe(recipe, tenant_id=tenant_id)
    return {"recipe_id": row.id, "state": row.state, "role": row.role}


@router.post("/resolve", summary="Generalist-vs-specialist resolver")
def resolve(req: ResolveRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    resolver = GeneralistVsSpecialistResolver(db)
    result = resolver.resolve(
        task_description=req.task_description,
        tenant_id=tenant_id,
        required_evidence_types=req.required_evidence_types,
    )
    return {
        "needs_specialist": result.needs_specialist,
        "reasoning": result.reasoning,
        "recommended_recipe_id": result.recommended_recipe_id,
        "recommended_specialty": result.recommended_specialty,
    }


@router.post("/sessions", status_code=201, summary="Instantiate an ephemeral agent session")
def instantiate_session(req: InstantiateRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    runtime = EphemeralAgentRuntime(db)
    try:
        session = runtime.instantiate(
            recipe_id=req.recipe_id,
            tenant_id=tenant_id,
            investigation_id=req.investigation_id,
            mold_id=req.mold_id,
            task_description=req.task_description,
            task_input=req.task_input,
            capability_allowed_tools=req.capability_allowed_tools,
            investigation_constraints=req.investigation_constraints,
        )
    except ValueError as e:
        raise ValidationError(str(e)) from e
    return {
        "session_id": session.id,
        "recipe_id": session.recipe_id,
        "status": session.status,
        "execution_mode": session.execution_mode,
        "granted_tools": session.granted_tools_json,
    }


@router.post("/sessions/{session_id}/execute", summary="Execute the agent session (calls LLM provider)")
def execute_session(session_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    runtime = EphemeralAgentRuntime(db)
    try:
        result = runtime.execute(session_id=session_id, tenant_id=tenant_id)
    except ValueError as e:
        raise ValidationError(str(e)) from e
    return {
        "session_id": result.session_id,
        "status": result.status,
        "is_mock": result.is_mock,
        "provider": result.provider_name,
        "model": result.model_name,
        "duration_ms": round(result.duration_ms, 2),
        "output": result.output[:500],
        "granted_tools": result.granted_tools,
        "error": result.error,
        # R-02 (MANARA-UI-BACKEND-CLOSURE-01): expose the persisted
        # tool_invocations[] audit trail. Each entry carries status ∈
        # {executed, denied_not_in_granted_set, not_implemented, error}.
        # Empty when no tool calls were made (e.g. mock without granted tools).
        # Never fabricated; never converts mock into live execution.
        "tool_invocations": getattr(result, "tool_invocations", []) or [],
    }


@router.post("/sessions/{session_id}/terminate", summary="Terminate the agent session")
def terminate_session(session_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    runtime = EphemeralAgentRuntime(db)
    ok = runtime.terminate(session_id=session_id, tenant_id=tenant_id)
    if not ok:
        raise NotFoundError(f"session {session_id} not found")
    return {"session_id": session_id, "terminated": True}


@router.post("/sessions/{session_id}/evaluate", summary="Record an evaluation for the session")
def evaluate_session(
    session_id: str,
    req: EvaluateRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    runtime = EphemeralAgentRuntime(db)
    try:
        eval_row = runtime.evaluate(
            session_id=session_id,
            tenant_id=tenant_id,
            outcome=req.outcome,
            quality_score=req.quality_score,
            improvement_over_generalist=req.improvement_over_generalist,
            notes=req.notes,
            criteria_results=req.criteria_results,
            evaluator=req.evaluator,
        )
    except ValueError as e:
        raise ValidationError(str(e)) from e
    return {
        "evaluation_id": eval_row.id,
        "session_id": eval_row.session_id,
        "outcome": eval_row.outcome,
        "quality_score": eval_row.quality_score,
    }


@router.get("/sessions", summary="List agent sessions (tenant-scoped)")
def list_sessions(
    db: Session = Depends(get_db),
    investigation_id: str | None = Query(
        default=None,
        description="Optional filter by investigation_id",
    ),
    recipe_id: str | None = Query(
        default=None,
        description="Optional filter by recipe_id",
    ),
    status: str | None = Query(
        default=None,
        description="Optional filter by status (instantiated|running|completed|failed|terminated)",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    """List agent sessions for the current tenant (R-08 / G-list-5).

    Supports optional filtering by investigation, recipe, and status.
    Returns persisted session summaries ordered by ``created_at`` DESC
    (newest first). Tenant isolation is enforced; sessions belonging to
    other tenants are never returned.

    This endpoint is read-only. It does NOT execute, instantiate, or
    terminate any session. It does NOT trigger LLM calls.
    """
    from manara.db.agent_models import AgentSessionRow

    tenant_id = _resolve_tenant()
    stmt = select(AgentSessionRow).where(AgentSessionRow.tenant_id == tenant_id)
    if investigation_id:
        stmt = stmt.where(AgentSessionRow.investigation_id == investigation_id)
    if recipe_id:
        stmt = stmt.where(AgentSessionRow.recipe_id == recipe_id)
    if status:
        stmt = stmt.where(AgentSessionRow.status == status)
    stmt = stmt.order_by(AgentSessionRow.started_at.desc()).limit(limit).offset(offset)
    rows = list(db.execute(stmt).scalars())
    return [
        {
            "id": r.id,
            "recipe_id": r.recipe_id,
            "investigation_id": r.investigation_id,
            "status": r.status,
            "execution_mode": r.execution_mode,
            "is_mock": r.execution_mode == "mock",
            "provider": r.provider_name,
            "model": r.model_name,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "duration_ms": r.duration_ms,
        }
        for r in rows
    ]


@router.get("/sessions/{session_id}", summary="Fetch session details (tenant-scoped)")
def get_session(session_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    from manara.db.agent_models import AgentSessionRow

    tenant_id = _resolve_tenant()
    row = db.get(AgentSessionRow, session_id)
    if row is None or row.tenant_id != tenant_id:
        raise NotFoundError(f"session {session_id} not found")
    return {
        "id": row.id,
        "recipe_id": row.recipe_id,
        "status": row.status,
        "execution_mode": row.execution_mode,
        "task_description": row.task_description,
        "output_summary": row.output_summary,
        "granted_tools": row.granted_tools_json,
        "is_mock": row.execution_mode == "mock",
        "provider": row.provider_name,
        "model": row.model_name,
        "started_at": row.started_at.isoformat(),
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "duration_ms": row.duration_ms,
        "error": row.error,
        # R-02 (MANARA-UI-BACKEND-CLOSURE-01): expose the persisted
        # tool_invocations[] from task_output_json. Each entry carries
        # status ∈ {executed, denied_not_in_granted_set, not_implemented, error}.
        # Empty array when no invocations were recorded (e.g. session
        # instantiated but not yet executed, or mock without granted tools).
        # The data is already in the DB; this is purely a response-shape
        # additive change. No mock→live conversion; no fabrication.
        "tool_invocations": (row.task_output_json or {}).get("tool_invocations", []),
    }


__all__ = ["router"]
