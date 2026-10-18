"""``/registry`` API routes — Capability Registry surface (G01).

Endpoints:
* ``GET    /registry/capabilities``           — list + filter
* ``GET    /registry/capabilities/{id}``      — fetch one card
* ``POST   /registry/capabilities``           — propose a new card (state=candidate)
* ``POST   /registry/capabilities/seed``      — load the 8 seed cards (dev helper)
* ``PATCH  /registry/capabilities/{id}/promote`` — owner-approved promotion
* ``DELETE /registry/capabilities/{id}``      — delete (with audit)
* ``GET    /registry/search?q=...``           — the 5-stage retrieval pipeline
* ``GET    /registry/capabilities/{id}/evaluations`` — evaluation history
* ``POST   /registry/capabilities/{id}/evaluations`` — add an evaluation
* ``GET    /registry/capabilities/{id}/relationships`` — graph edges
* ``POST   /registry/capabilities/{id}/relationships`` — add an edge
* ``POST   /registry/capabilities/{id}/reindex`` — regenerate embeddings
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from manara.api.errors import ConflictError, NotFoundError, ValidationError
from manara.config import settings
from manara.contracts import (
    CapabilityEvaluation,
    SearchCapability,
)
from manara.db.session import get_db
from manara.registry import SEED_CAPABILITIES, CapabilityRegistry
from manara.registry.converters import row_to_capability

router = APIRouter(prefix="/registry", tags=["registry"])


# ─────────────────────────────────────────────────────────────────────────────
# Request / response models
# ─────────────────────────────────────────────────────────────────────────────


class CapabilityListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capabilities: list[dict[str, Any]]
    total: int
    filters: dict[str, Any]


class PromoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer: str = Field(..., min_length=1, max_length=120)
    rationale: str = Field(..., min_length=10)
    decision: Literal["approved", "rejected", "reverted"] = "approved"
    test_matrix_ref: str | None = Field(default=None, max_length=200)


class PromoteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    previous_status: str
    new_status: str
    decision: str
    reviewer: str
    rationale: str
    decided_at: datetime


class EvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluator: str = Field(..., min_length=1, max_length=120)
    benchmark_query_set: str = Field(..., min_length=1, max_length=200)
    precision: float | None = Field(default=None, ge=0.0, le=1.0)
    recall: float | None = Field(default=None, ge=0.0, le=1.0)
    false_positive_misuse_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: str = Field(default="")


class RelationshipRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to_capability_id: str = Field(..., min_length=1, max_length=120)
    kind: Literal["complements", "specializes", "replaces", "conflicts_with"]


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    tenant_id: str
    requested_top_k: int
    stage_traces: list[dict[str, Any]]
    hits: list[dict[str, Any]]
    gaps: list[str]
    generated_at: str


class SeedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seeded: list[str]
    skipped: list[str]
    total_created: int


# ─────────────────────────────────────────────────────────────────────────────
# Tenant resolution
# ─────────────────────────────────────────────────────────────────────────────


def _resolve_tenant() -> str:
    """In G01 we still ship single-tenant demo mode; multi-tenant arrives
    in G03. The tenant_id is therefore the default tenant from settings.
    """
    return settings.default_tenant_id


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/capabilities",
    response_model=CapabilityListResponse,
    summary="List capabilities with optional filters",
)
def list_capabilities(
    db: Session = Depends(get_db),
    domains: list[str] | None = Query(default=None),
    tags: list[str] | None = Query(default=None),
    statuses: list[str] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> CapabilityListResponse:
    tenant_id = _resolve_tenant()
    reg = CapabilityRegistry(db)
    rows = reg.list_capabilities(
        tenant_id=tenant_id,
        domains=domains,
        tags=tags,
        statuses=statuses,
        limit=limit,
        offset=offset,
    )
    caps = [row_to_capability(r).model_dump(mode="json") for r in rows]
    return CapabilityListResponse(
        capabilities=caps,
        total=len(caps),
        filters={"domains": domains, "tags": tags, "statuses": statuses, "limit": limit, "offset": offset},
    )


@router.get(
    "/capabilities/{capability_id}",
    summary="Fetch a single capability card",
)
def get_capability(
    capability_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    reg = CapabilityRegistry(db)
    row = reg.get_capability(capability_id, tenant_id=tenant_id)
    if row is None:
        raise NotFoundError(f"capability {capability_id!r} not found")
    cap = row_to_capability(row)
    return cap.model_dump(mode="json")


@router.post(
    "/capabilities",
    status_code=status.HTTP_201_CREATED,
    summary="Propose a new capability card (state=candidate by default)",
)
def create_capability(
    cap: SearchCapability,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    reg = CapabilityRegistry(db)
    try:
        row = reg.create_capability(cap, tenant_id=tenant_id)
    except ValueError as e:
        raise ConflictError(str(e)) from e
    return row_to_capability(row).model_dump(mode="json")


@router.post(
    "/capabilities/seed",
    response_model=SeedResponse,
    summary="Load the 8 seed capability cards (dev helper, idempotent)",
)
def seed_capabilities(db: Session = Depends(get_db)) -> SeedResponse:
    tenant_id = _resolve_tenant()
    reg = CapabilityRegistry(db)
    seeded: list[str] = []
    skipped: list[str] = []
    for cap in SEED_CAPABILITIES:
        existing = reg.get_capability(cap.id, tenant_id=tenant_id)
        if existing is not None:
            skipped.append(cap.id)
            continue
        try:
            reg.create_capability(cap, tenant_id=tenant_id)
            seeded.append(cap.id)
        except ValueError:
            skipped.append(cap.id)
    return SeedResponse(seeded=seeded, skipped=skipped, total_created=len(seeded))


@router.patch(
    "/capabilities/{capability_id}/promote",
    response_model=PromoteResponse,
    summary="Owner-approved promotion of a capability",
)
def promote_capability(
    capability_id: str,
    req: PromoteRequest,
    db: Session = Depends(get_db),
) -> PromoteResponse:
    tenant_id = _resolve_tenant()
    reg = CapabilityRegistry(db)
    try:
        approval = reg.promote(
            capability_id,
            tenant_id=tenant_id,
            reviewer=req.reviewer,
            rationale=req.rationale,
            new_status=req.decision,
            test_matrix_ref=req.test_matrix_ref,
        )
    except ValueError as e:
        raise NotFoundError(str(e)) from e
    return PromoteResponse(
        capability_id=approval.capability_id,
        previous_status=approval.previous_status or "",
        new_status=approval.new_status,
        decision=approval.decision,
        reviewer=approval.reviewer,
        rationale=approval.rationale,
        decided_at=approval.decided_at,
    )


@router.delete(
    "/capabilities/{capability_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a capability (cascades to embeddings)",
)
def delete_capability(
    capability_id: str,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    tenant_id = _resolve_tenant()
    reg = CapabilityRegistry(db)
    ok = reg.delete_capability(capability_id, tenant_id=tenant_id)
    if not ok:
        raise NotFoundError(f"capability {capability_id!r} not found")
    return {"deleted": True}


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Run the 5-stage retrieval pipeline (text + semantic + negative rerank)",
)
def search_capabilities(
    q: str = Query(..., min_length=2, max_length=500, description="Natural-language query"),
    top_k: int = Query(default=10, ge=1, le=50),
    domains: list[str] | None = Query(default=None),
    tags: list[str] | None = Query(default=None),
    languages: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
) -> SearchResponse:
    tenant_id = _resolve_tenant()
    reg = CapabilityRegistry(db)
    result = reg.search(
        q,
        tenant_id=tenant_id,
        top_k=top_k,
        domains=domains,
        tags=tags,
        languages=languages,
    )
    return SearchResponse(**result.to_dict())


@router.get(
    "/capabilities/{capability_id}/evaluations",
    summary="List evaluation history for a capability",
)
def list_evaluations(
    capability_id: str,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    tenant_id = _resolve_tenant()
    from manara.db.registry_models import CapabilityEvaluationRow

    stmt = (
        select(CapabilityEvaluationRow)
        .where(
            CapabilityEvaluationRow.capability_id == capability_id,
            CapabilityEvaluationRow.tenant_id == tenant_id,
        )
        .order_by(CapabilityEvaluationRow.evaluated_at.desc())
    )
    rows = list(db.execute(stmt).scalars())
    return [
        {
            "id": r.id,
            "capability_id": r.capability_id,
            "evaluated_at": r.evaluated_at.isoformat(),
            "evaluator": r.evaluator,
            "benchmark_query_set": r.benchmark_query_set,
            "precision": r.precision,
            "recall": r.recall,
            "false_positive_misuse_rate": r.false_positive_misuse_rate,
            "notes": r.notes,
        }
        for r in rows
    ]


@router.post(
    "/capabilities/{capability_id}/evaluations",
    status_code=status.HTTP_201_CREATED,
    summary="Add an evaluation record for a capability",
)
def add_evaluation(
    capability_id: str,
    req: EvaluationRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    reg = CapabilityRegistry(db)
    # Verify the capability exists
    row = reg.get_capability(capability_id, tenant_id=tenant_id)
    if row is None:
        raise NotFoundError(f"capability {capability_id!r} not found")
    ev = CapabilityEvaluation(
        evaluator=req.evaluator,
        benchmark_query_set=req.benchmark_query_set,
        precision=req.precision,
        recall=req.recall,
        false_positive_misuse_rate=req.false_positive_misuse_rate,
        notes=req.notes,
    )
    eval_row = reg.add_evaluation(
        capability_id, tenant_id=tenant_id, evaluation=ev
    )
    return {
        "id": eval_row.id,
        "capability_id": eval_row.capability_id,
        "evaluated_at": eval_row.evaluated_at.isoformat(),
    }


@router.get(
    "/capabilities/{capability_id}/relationships",
    summary="List graph edges for a capability",
)
def list_relationships(
    capability_id: str,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    tenant_id = _resolve_tenant()
    from manara.db.registry_models import CapabilityRelationshipRow

    stmt = select(CapabilityRelationshipRow).where(
        CapabilityRelationshipRow.tenant_id == tenant_id,
        (CapabilityRelationshipRow.from_capability_id == capability_id)
        | (CapabilityRelationshipRow.to_capability_id == capability_id),
    )
    rows = list(db.execute(stmt).scalars())
    return [
        {
            "id": r.id,
            "from_capability_id": r.from_capability_id,
            "to_capability_id": r.to_capability_id,
            "kind": r.kind,
        }
        for r in rows
    ]


@router.post(
    "/capabilities/{capability_id}/relationships",
    status_code=status.HTTP_201_CREATED,
    summary="Add a graph edge between two capabilities",
)
def add_relationship(
    capability_id: str,
    req: RelationshipRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    reg = CapabilityRegistry(db)
    try:
        edge = reg.add_relationship(
            from_capability_id=capability_id,
            to_capability_id=req.to_capability_id,
            kind=req.kind,
            tenant_id=tenant_id,
        )
    except ValueError as e:
        raise ValidationError(str(e)) from e
    return {
        "id": edge.id,
        "from_capability_id": edge.from_capability_id,
        "to_capability_id": edge.to_capability_id,
        "kind": edge.kind,
    }


@router.post(
    "/capabilities/{capability_id}/reindex",
    summary="Regenerate embeddings for a capability (e.g. after a model upgrade)",
)
def reindex_embeddings(
    capability_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    reg = CapabilityRegistry(db)
    try:
        count = reg.reindex_embeddings(capability_id, tenant_id=tenant_id)
    except ValueError as e:
        raise NotFoundError(str(e)) from e
    return {
        "capability_id": capability_id,
        "embeddings_regenerated": count,
        "model": "paraphrase-multilingual-MiniLM-L12-v2",
    }


__all__ = ["router"]
