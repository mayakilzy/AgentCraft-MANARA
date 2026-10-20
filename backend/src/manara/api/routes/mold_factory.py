"""``/mold-factory`` API routes — Mold Factory surface (G04).

Endpoints:
* ``POST   /mold-factory/compose``                          — compose a temporary mold
* ``GET    /mold-factory/investigations``                    — list investigations (tenant-scoped)
* ``GET    /mold-factory/investigations/{id}``               — fetch one investigation (tenant-scoped)
* ``GET    /mold-factory/molds``                            — list mold recipes
* ``GET    /mold-factory/molds/{id}``                       — fetch one mold recipe
* ``PATCH  /mold-factory/molds/{id}/promote``              — owner-approved promotion (temporary → reusable → maintained)
* ``POST   /mold-factory/molds/{id}/archive``               — archive a mold
* ``GET    /mold-factory/molds/{id}/gaps``                  — list gap analyses for a mold
* ``POST   /mold-factory/investigations/{id}/workflow``      — create workflow row
* ``POST   /mold-factory/investigations/{id}/transition``    — attempt a state transition
* ``GET    /mold-factory/investigations/{id}/workflow``      — fetch workflow state + audit trail
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from manara.api.errors import NotFoundError, ValidationError
from manara.config import settings
from manara.contracts import Mold
from manara.db.mold_models import GapAnalysisRow, InvestigationWorkflowRow, MoldRecipeRow
from manara.db.models import InvestigationRow
from manara.db.session import get_db
from manara.lifecycle import MoldState
from manara.mold_factory import (
    InvestigationWorkflowService,
    MoldArchitect,
    WorkflowTransitionError,
)

router = APIRouter(prefix="/mold-factory", tags=["mold-factory"])


def _resolve_tenant() -> str:
    return settings.default_tenant_id


# ─────────────────────────────────────────────────────────────────────────────
# Request / response models
# ─────────────────────────────────────────────────────────────────────────────


class ComposeMoldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=10, max_length=1000)
    investigation_id: str | None = Field(default=None, max_length=120)
    domain_hint: str | None = Field(default=None, max_length=120)


class ComposeMoldResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    tenant_id: str
    investigation_id: str | None = None
    is_unknown_domain: bool
    detection_reasoning: str
    detected_needs: list[dict[str, Any]]
    coverage: list[dict[str, Any]]
    gaps: list[dict[str, Any]]
    mold_recipe_id: str
    mold: dict[str, Any]
    is_complete: bool
    is_catalog_complete: bool = False
    deliverable_type: str = "unknown"
    composition_notes: str
    composed_at: str


class PromoteMoldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_state: Literal["reusable", "maintained", "archived"]
    reviewer: str = Field(..., min_length=1, max_length=120)
    rationale: str = Field(..., min_length=10)


class ArchiveMoldRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rationale: str = Field(..., min_length=10)


class TransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_state: str = Field(..., min_length=1, max_length=60)
    actor: str = Field(default="system", max_length=120)
    rationale: str = Field(default="", max_length=1000)
    mold_id: str | None = Field(default=None, max_length=120)


class TransitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    investigation_id: str
    previous_state: str
    new_state: str
    transitioned: bool
    blocker: str | None = None


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/compose",
    response_model=ComposeMoldResponse,
    summary="Compose a temporary mold for a research query (G04 core)",
)
def compose_mold(
    req: ComposeMoldRequest,
    db: Session = Depends(get_db),
) -> ComposeMoldResponse:
    """Compose a temporary mold for the given query.

    Per owner (G09-R1):
    > "أنشئ InvestigationRow حقيقياً بمعرّف ثابت عند بدء التحقيق."

    The MoldArchitect is the SOLE owner of InvestigationRow creation.
    If investigation_id is not provided, the architect creates one
    automatically. The API layer does NOT duplicate this logic.
    """
    tenant_id = _resolve_tenant()
    architect = MoldArchitect(db)
    try:
        result = architect.compose_mold(
            req.query,
            tenant_id=tenant_id,
            investigation_id=req.investigation_id,
            domain_hint=req.domain_hint,
        )
    except Exception as e:
        raise ValidationError(f"mold composition failed: {e}") from e
    return ComposeMoldResponse(**result.to_dict())


@router.get(
    "/investigations",
    summary="List investigations (tenant-scoped)",
)
def list_investigations(
    db: Session = Depends(get_db),
    state: str | None = Query(
        default=None,
        description="Optional filter by workflow state (e.g. received, mold_ready, archived)",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, Any]]:
    """List investigations for the current tenant (R-04 / G-list-1).

    Returns persisted investigation summaries ordered by ``created_at``
    DESC (newest first). Tenant isolation is enforced; investigations
    belonging to other tenants are never returned.

    The ``state`` field reflects the actual ``InvestigationWorkflowRow.state``
    when a workflow row exists, otherwise ``None`` (the investigation was
    created but no workflow was initialized). The UI must handle ``None``
    gracefully — it does NOT mean the investigation is broken.

    Investigations without a workflow row are still returned. The join
    is a LEFT JOIN to avoid dropping them.

    The state values come from the ``InvestigationState`` enum
    (received, scoped, coverage_checked, building_capabilities,
    mold_ready, acquiring, normalizing, evidencing,
    forecasting_or_scenarios, drafting, verification,
    deliverable_ready, archived). The UI must verify the actual enum
    before hardcoding any state string.
    """
    tenant_id = _resolve_tenant()
    stmt = select(InvestigationRow).where(InvestigationRow.tenant_id == tenant_id)
    stmt = stmt.order_by(InvestigationRow.created_at.desc()).limit(limit).offset(offset)
    inv_rows = list(db.execute(stmt).scalars())

    if not inv_rows:
        return []

    # Fetch workflow states for these investigations in one query (avoid N+1).
    inv_ids = [r.id for r in inv_rows]
    wf_stmt = select(InvestigationWorkflowRow).where(
        InvestigationWorkflowRow.tenant_id == tenant_id,
        InvestigationWorkflowRow.investigation_id.in_(inv_ids),
    )
    if state:
        wf_stmt = wf_stmt.where(InvestigationWorkflowRow.state == state)
    wf_rows = list(db.execute(wf_stmt).scalars())
    wf_by_inv = {wf.investigation_id: wf for wf in wf_rows}

    # If a state filter was applied, only return investigations that HAVE a
    # matching workflow row.
    if state:
        return [
            {
                "id": inv.id,
                "topic": inv.topic,
                "state": wf_by_inv[inv.id].state if inv.id in wf_by_inv else None,
                "tenant_id": inv.tenant_id,
                "created_at": inv.created_at.isoformat(),
                "updated_at": inv.updated_at.isoformat(),
            }
            for inv in inv_rows
            if inv.id in wf_by_inv
        ]

    return [
        {
            "id": inv.id,
            "topic": inv.topic,
            "state": wf_by_inv[inv.id].state if inv.id in wf_by_inv else None,
            "tenant_id": inv.tenant_id,
            "created_at": inv.created_at.isoformat(),
            "updated_at": inv.updated_at.isoformat(),
        }
        for inv in inv_rows
    ]


@router.get(
    "/investigations/{investigation_id}",
    summary="Fetch one investigation (tenant-scoped)",
)
def get_investigation(
    investigation_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Fetch a single investigation by ID (R-05 / G-list-2).

    Primary acceptance requirement: an existing investigation must be
    recoverable after page reload WITHOUT invoking
    ``POST /mold-factory/compose`` again.

    Returns the persisted ``InvestigationRow`` identity, topic, payload,
    timestamps, and the workflow state when available.

    This endpoint does NOT regenerate the mold. The ``payload`` field
    contains what was persisted at compose time (the Investigation
    Pydantic contract serialized). For the full mold composition result
    (coverage[], gaps[], detected_needs[]), the UI should call
    ``GET /mold-factory/molds/{mold_id}`` and ``GET /mold-factory/molds/{mold_id}/gaps``.

    See C-03 in MANARA_FINAL_UI_BACKEND_GAP_CLOSURE.md for the
    Mold Blueprint reload integrity analysis: the per-need ``coverage[]``
    and ``detected_needs[]`` from the original compose response are NOT
    persisted as a single blob; they must be reconstructed from
    ``MoldRecipeRow.payload`` + ``GapAnalysisRow`` rows.

    Returns 404 if the investigation does not exist or belongs to a
    different tenant. Never creates a new investigation.
    """
    tenant_id = _resolve_tenant()
    row = db.get(InvestigationRow, investigation_id)
    if row is None or row.tenant_id != tenant_id:
        raise NotFoundError(f"investigation {investigation_id} not found for tenant")

    # Fetch the workflow row if it exists.
    wf_row = db.get(InvestigationWorkflowRow, investigation_id)
    workflow_state = wf_row.state if (wf_row and wf_row.tenant_id == tenant_id) else None
    mold_id = wf_row.mold_id if (wf_row and wf_row.tenant_id == tenant_id) else None
    blocker = wf_row.blocker if (wf_row and wf_row.tenant_id == tenant_id) else None

    return {
        "id": row.id,
        "topic": row.topic,
        "tenant_id": row.tenant_id,
        "user_id": row.user_id,
        "state": row.state,
        "payload": row.payload,
        "workflow_state": workflow_state,
        "mold_id": mold_id,
        "blocker": blocker,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


@router.get(
    "/molds",
    summary="List mold recipes (tenant-scoped)",
)
def list_molds(
    db: Session = Depends(get_db),
    state: str | None = Query(default=None),
    domain: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    tenant_id = _resolve_tenant()
    stmt = select(MoldRecipeRow).where(MoldRecipeRow.tenant_id == tenant_id)
    if state:
        stmt = stmt.where(MoldRecipeRow.state == state)
    if domain:
        stmt = stmt.where(MoldRecipeRow.domain == domain)
    stmt = stmt.order_by(MoldRecipeRow.updated_at.desc()).limit(limit)
    rows = list(db.execute(stmt).scalars())
    return [
        {
            "id": r.id,
            "display_name": r.display_name,
            "state": r.state,
            "domain": r.domain,
            "version": r.version,
            "origin": r.origin,
            "capability_ids": r.capability_ids_json,
            "last_piloted_at": r.last_piloted_at.isoformat() if r.last_piloted_at else None,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get(
    "/molds/{mold_id}",
    summary="Fetch one mold recipe (tenant-scoped)",
)
def get_mold(mold_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    row = db.get(MoldRecipeRow, mold_id)
    if row is None or row.tenant_id != tenant_id:
        raise NotFoundError(f"mold {mold_id} not found for tenant")
    return row.payload


@router.patch(
    "/molds/{mold_id}/promote",
    summary="Owner-approved promotion (temporary → reusable → maintained → archived)",
)
def promote_mold(
    mold_id: str,
    req: PromoteMoldRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    row = db.get(MoldRecipeRow, mold_id)
    if row is None or row.tenant_id != tenant_id:
        raise NotFoundError(f"mold {mold_id} not found for tenant")

    previous_state = row.state
    valid_transitions = {
        "temporary": {"reusable", "archived"},
        "reusable": {"maintained", "archived"},
        "maintained": {"archived"},
        "archived": set(),
    }
    allowed = valid_transitions.get(previous_state, set())
    if req.new_state not in allowed:
        raise ValidationError(
            f"illegal mold transition {previous_state} → {req.new_state}. "
            f"Allowed: {sorted(allowed)}"
        )

    row.state = req.new_state
    row.promoted_by = req.reviewer
    from datetime import UTC, datetime

    row.promoted_at = datetime.now(UTC)
    row.promotion_rationale = req.rationale
    if req.new_state == "archived":
        row.archived_at = datetime.now(UTC)
    elif req.new_state == "maintained":
        # Maintained molds must have been piloted
        if row.last_piloted_at is None:
            raise ValidationError(
                "cannot promote to maintained: mold has never been piloted"
            )

    # Update the payload
    mold = Mold.model_validate(row.payload)
    mold.state = MoldState(req.new_state)
    row.payload = mold.model_dump(mode="json")
    db.commit()

    return {
        "mold_id": mold_id,
        "previous_state": previous_state,
        "new_state": req.new_state,
        "promoted_by": req.reviewer,
        "promoted_at": row.promoted_at.isoformat(),
    }


@router.post(
    "/molds/{mold_id}/archive",
    summary="Archive a mold (preserves recipe + history; no active execution)",
)
def archive_mold(
    mold_id: str,
    req: ArchiveMoldRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    row = db.get(MoldRecipeRow, mold_id)
    if row is None or row.tenant_id != tenant_id:
        raise NotFoundError(f"mold {mold_id} not found for tenant")
    if row.state == "archived":
        raise ValidationError(f"mold {mold_id} already archived")

    from datetime import UTC, datetime

    previous_state = row.state
    row.state = "archived"
    row.archived_at = datetime.now(UTC)
    row.promotion_rationale = req.rationale

    mold = Mold.model_validate(row.payload)
    mold.state = MoldState.ARCHIVED
    row.payload = mold.model_dump(mode="json")
    db.commit()

    return {
        "mold_id": mold_id,
        "previous_state": previous_state,
        "new_state": "archived",
        "archived_at": row.archived_at.isoformat(),
    }


@router.get(
    "/molds/{mold_id}/gaps",
    summary="List gap analyses for a mold (the honestly-recorded missing capabilities)",
)
def list_gaps(mold_id: str, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    tenant_id = _resolve_tenant()
    row = db.get(MoldRecipeRow, mold_id)
    if row is None or row.tenant_id != tenant_id:
        raise NotFoundError(f"mold {mold_id} not found for tenant")
    stmt = select(GapAnalysisRow).where(
        GapAnalysisRow.tenant_id == tenant_id,
        GapAnalysisRow.mold_id == mold_id,
    ).order_by(GapAnalysisRow.created_at.desc())
    rows = list(db.execute(stmt).scalars())
    return [
        {
            "id": r.id,
            "need": r.need,
            "need_label": r.need_label,
            "status": r.status,
            "resolution_notes": r.resolution_notes,
            "candidate_capability_ids": r.candidate_capability_ids_json,
            "foundry_candidate_id": r.foundry_candidate_id,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


# ── Investigation workflow endpoints ─────────────────────────────────────────


@router.post(
    "/investigations/{investigation_id}/workflow",
    status_code=201,
    summary="Create a workflow row for an investigation (initial state=received)",
)
def create_workflow(
    investigation_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    service = InvestigationWorkflowService(db)
    try:
        row = service.create_workflow(
            investigation_id=investigation_id, tenant_id=tenant_id
        )
    except WorkflowTransitionError as e:
        raise ValidationError(str(e)) from e
    return {
        "investigation_id": row.investigation_id,
        "state": row.state,
        "mold_id": row.mold_id,
        "blocker": row.blocker,
    }


@router.post(
    "/investigations/{investigation_id}/transition",
    response_model=TransitionResponse,
    summary="Attempt a state transition (validates pre-conditions; records blocker on failure)",
)
def transition(
    investigation_id: str,
    req: TransitionRequest,
    db: Session = Depends(get_db),
) -> TransitionResponse:
    tenant_id = _resolve_tenant()
    service = InvestigationWorkflowService(db)
    try:
        result = service.transition(
            investigation_id=investigation_id,
            tenant_id=tenant_id,
            target_state=req.target_state,
            actor=req.actor,
            rationale=req.rationale,
            mold_id=req.mold_id,
        )
    except WorkflowTransitionError as e:
        raise ValidationError(str(e)) from e
    return TransitionResponse(
        investigation_id=result.investigation_id,
        previous_state=result.previous_state,
        new_state=result.new_state,
        transitioned=result.transitioned,
        blocker=result.blocker,
    )


@router.get(
    "/investigations/{investigation_id}/workflow",
    summary="Fetch workflow state + audit trail",
)
def get_workflow(investigation_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    service = InvestigationWorkflowService(db)
    row = service.get_workflow(investigation_id, tenant_id=tenant_id)
    if row is None:
        raise NotFoundError(
            f"workflow not found for investigation {investigation_id}"
        )
    return {
        "investigation_id": row.investigation_id,
        "state": row.state,
        "mold_id": row.mold_id,
        "blocker": row.blocker,
        "transitions": row.transitions_json,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


__all__ = ["router"]
