"""``/foundry`` API routes — Search Foundry surface (G02).

Endpoints:
* ``GET    /foundry/candidates``                       — list candidate sources
* ``GET    /foundry/candidates/{id}``                  — fetch one candidate's metadata
* ``POST   /foundry/candidates/{id}/discover``         — register source in live registry
* ``POST   /foundry/candidates/{id}/assess``           — basic structural checks
* ``POST   /foundry/candidates/{id}/register-connector`` — register the connector (OpenAlex only in G02)
* ``POST   /foundry/candidates/{id}/sandbox-test``     — execute one real permitted call
* ``POST   /foundry/candidates/{id}/approve``          — owner-approved promotion
* ``POST   /foundry/candidates/{id}/quarantine``       — explicit quarantine
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from manara.api.errors import NotFoundError, ValidationError
from manara.config import settings
from manara.db.session import get_db as get_db_dep
from manara.foundry import CATALOG, FoundryService, get_candidate

router = APIRouter(prefix="/foundry", tags=["foundry"])


def _resolve_tenant() -> str:
    return settings.default_tenant_id


# ─────────────────────────────────────────────────────────────────────────────
# Response models
# ─────────────────────────────────────────────────────────────────────────────


class CandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    display_name: str
    homepage: str
    api_doc_url: str
    license: str
    data_reuse_rights: str
    commercial_rights: str
    auth_required: bool
    rate_limit_policy: str
    allowed_hosts: list[str]
    primary_data_types: list[str]
    coverage_geographies: list[str]
    languages: list[str]
    description: str
    notes: str = ""


class SandboxTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=2, max_length=500)
    per_page: int = Field(default=5, ge=1, le=25)


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewer: str = Field(..., min_length=1, max_length=120)
    rationale: str = Field(..., min_length=10)


class QuarantineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=10)


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────


@router.get(
    "/candidates",
    summary="List candidate sources in the Foundry catalog",
)
def list_candidates() -> list[CandidateResponse]:
    return [
        CandidateResponse(
            id=c.id,
            display_name=c.display_name,
            homepage=c.homepage,
            api_doc_url=c.api_doc_url,
            license=c.license,
            data_reuse_rights=c.data_reuse_rights,
            commercial_rights=c.commercial_rights,
            auth_required=c.auth_required,
            rate_limit_policy=c.rate_limit_policy,
            allowed_hosts=c.allowed_hosts,
            primary_data_types=c.primary_data_types,
            coverage_geographies=c.coverage_geographies,
            languages=c.languages,
            description=c.description,
            notes=c.notes,
        )
        for c in CATALOG
    ]


@router.get(
    "/candidates/{candidate_id}",
    summary="Fetch one candidate's metadata",
)
def get_candidate_endpoint(candidate_id: str) -> CandidateResponse:
    c = get_candidate(candidate_id)
    if c is None:
        raise NotFoundError(f"candidate {candidate_id!r} not in catalog")
    return CandidateResponse(
        id=c.id,
        display_name=c.display_name,
        homepage=c.homepage,
        api_doc_url=c.api_doc_url,
        license=c.license,
        data_reuse_rights=c.data_reuse_rights,
        commercial_rights=c.commercial_rights,
        auth_required=c.auth_required,
        rate_limit_policy=c.rate_limit_policy,
        allowed_hosts=c.allowed_hosts,
        primary_data_types=c.primary_data_types,
        coverage_geographies=c.coverage_geographies,
        languages=c.languages,
        description=c.description,
        notes=c.notes,
    )


@router.post(
    "/candidates/{candidate_id}/discover",
    summary="Register a candidate source in the live registry (state=discovered)",
)
def discover_candidate(
    candidate_id: str,
    db: Session = Depends(get_db_dep),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    foundry = FoundryService(db)
    try:
        row = foundry.discover_candidate(candidate_id, tenant_id=tenant_id)
    except ValueError as e:
        raise NotFoundError(str(e)) from e
    return {
        "candidate_id": candidate_id,
        "source_id": row.id,
        "status": row.status,
        "tenant_id": row.tenant_id,
    }


@router.post(
    "/candidates/{candidate_id}/assess",
    summary="Basic structural checks; promote discovered → assessed",
)
def assess_candidate(
    candidate_id: str,
    db: Session = Depends(get_db_dep),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    foundry = FoundryService(db)
    try:
        row = foundry.assess_candidate(candidate_id, tenant_id=tenant_id)
    except ValueError as e:
        raise ValidationError(str(e)) from e
    return {
        "candidate_id": candidate_id,
        "source_id": row.id,
        "status": row.status,
    }


@router.post(
    "/candidates/{candidate_id}/register-connector",
    summary="Register the connector (OpenAlex only in G02)",
)
def register_connector(
    candidate_id: str,
    db: Session = Depends(get_db_dep),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    foundry = FoundryService(db)
    try:
        row = foundry.register_connector(candidate_id, tenant_id=tenant_id)
    except (ValueError, NotImplementedError) as e:
        raise ValidationError(str(e)) from e
    return {
        "candidate_id": candidate_id,
        "connector_id": row.id,
        "implementation_sha": row.implementation_sha,
        "status": row.status,
    }


@router.post(
    "/candidates/{candidate_id}/sandbox-test",
    summary="Execute ONE real permitted call to the candidate source (REAL API CALL)",
)
def sandbox_test_candidate(
    candidate_id: str,
    req: SandboxTestRequest,
    db: Session = Depends(get_db_dep),
) -> dict[str, Any]:
    """Execute a REAL permitted API call to the candidate source.

    This endpoint makes a REAL network call to the candidate's API. It
    is NOT a mock. The result is recorded with provenance (openalex_id,
    publication_year, etc.) so it can be verified later.
    """
    tenant_id = _resolve_tenant()
    foundry = FoundryService(db)
    try:
        result = foundry.sandbox_test_candidate(
            candidate_id,
            query=req.query,
            tenant_id=tenant_id,
            per_page=req.per_page,
        )
    except (ValueError, NotImplementedError) as e:
        raise ValidationError(str(e)) from e
    return {
        "candidate_id": result.candidate_id,
        "query": result.query,
        "success": result.success,
        "work_count": result.work_count,
        "sample_works": result.sample_works,
        "error": result.error,
        "duration_ms": round(result.duration_ms, 2),
        "timestamp": result.timestamp.isoformat(),
        "connector_id": result.connector_id,
        "connector_version": result.connector_version,
        "provenance": {
            "source": "real_api_call",
            "endpoint": "api.openalex.org/works",
            "license": "CC0-1.0",
            "recorded_at": result.timestamp.isoformat(),
        },
    }


@router.post(
    "/candidates/{candidate_id}/approve",
    summary="Owner-approved promotion of a sandbox-tested connector",
)
def approve_candidate(
    candidate_id: str,
    req: ApprovalRequest,
    db: Session = Depends(get_db_dep),
) -> dict[str, Any]:
    """Promote a sandbox-tested connector to ``approved`` state.

    Per spec: failed approvals cannot run. If the connector is not in
    ``sandbox_tested`` or ``review_pending`` state, this endpoint
    returns a 422 ValidationError.
    """
    tenant_id = _resolve_tenant()
    foundry = FoundryService(db)
    try:
        result = foundry.approve_candidate(
            candidate_id,
            reviewer=req.reviewer,
            rationale=req.rationale,
            tenant_id=tenant_id,
        )
    except ValueError as e:
        raise ValidationError(str(e)) from e
    return {
        "candidate_id": result.candidate_id,
        "previous_status": result.previous_status,
        "new_status": result.new_status,
        "reviewer": result.reviewer,
        "rationale": result.rationale,
        "approved_at": result.approved_at.isoformat(),
    }


@router.post(
    "/candidates/{candidate_id}/quarantine",
    summary="Quarantine a candidate (failed test or revoked)",
)
def quarantine_candidate(
    candidate_id: str,
    req: QuarantineRequest,
    db: Session = Depends(get_db_dep),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    foundry = FoundryService(db)
    foundry.quarantine_candidate(
        candidate_id, reason=req.reason, tenant_id=tenant_id
    )
    return {"candidate_id": candidate_id, "status": "quarantined"}


# ─────────────────────────────────────────────────────────────────────────────
# Dependency moved to top of file (get_db_dep imported above)
# ─────────────────────────────────────────────────────────────────────────────


__all__ = ["router"]
