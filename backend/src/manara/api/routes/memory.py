"""``/memory`` API routes — Cumulative Knowledge Memory surface (G03).

Endpoints:
* ``POST   /memory/evidence``                          — ingest evidence (dedup-aware)
* ``GET    /memory/evidence/{id}``                     — fetch one evidence item
* ``GET    /memory/investigations/{id}/evidence``      — list evidence in an investigation
* ``POST   /memory/evidence/{id}/claims``             — attach a claim
* ``POST   /memory/claims/{id}/support``               — add supports/refutes edge
* ``PATCH  /memory/claims/{id}/verdict``               — promote verdict (with audit)
* ``GET    /memory/investigations/{id}/claims``        — list claims in an investigation
* ``POST   /memory/investigations/{id}/search-prior``  — search prior memory for reuse
* ``POST   /memory/investigations/{id}/reuse``         — record a reuse link
* ``GET    /memory/investigations/{id}/decisions``     — audit log for an investigation
* ``POST   /memory/snapshots``                         — capture a source snapshot
* ``GET    /memory/investigations/{id}/at-cutoff``     — bitemporal replay (no future leakage)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from manara.api.errors import NotFoundError, ValidationError
from manara.config import settings
from manara.contracts import Evidence as EvidenceContract
from manara.db.memory_models import (
    ClaimRow,
    EvidenceItemRow,
    MemoryDecisionRow,
)
from manara.db.session import get_db
from manara.memory import MemoryCurator

router = APIRouter(prefix="/memory", tags=["memory"])


def _resolve_tenant() -> str:
    return settings.default_tenant_id


# ─────────────────────────────────────────────────────────────────────────────
# Request / response models
# ─────────────────────────────────────────────────────────────────────────────


class IngestEvidenceRequest(BaseModel):
    """Request body for ingesting evidence.

    The ``raw_content`` field (base64-encoded in transit) is optional.
    If provided, it is stored in object storage and the checksum is
    computed from it; otherwise the checksum from the Evidence contract
    is used.
    """

    model_config = ConfigDict(extra="forbid")

    evidence: dict[str, Any] = Field(
        ...,
        description="The Evidence Pydantic contract as a JSON dict.",
    )
    investigation_id: str = Field(..., min_length=1, max_length=120)
    raw_content_b64: str | None = Field(
        default=None,
        description="Optional base64-encoded raw content to store in object storage.",
    )
    actor: str = Field(default="curator", max_length=120)


class IngestEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    deduplicated: bool
    reused_from_investigation_id: str | None = None
    stored_at_ref: str | None = None
    checksum: str | None = None
    decision_id: int | None = None


class AttachClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(..., min_length=1, max_length=120)
    evidence_id: str = Field(..., min_length=1, max_length=120)
    statement: str = Field(..., min_length=10)
    verdict: Literal["candidate", "supported", "contested", "refuted", "superseded"] = "candidate"
    independence_group: str | None = Field(default=None, max_length=120)


class SupportEdgeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(..., min_length=1, max_length=120)
    relation: Literal["supports", "refutes", "qualifies"]
    weight: float = Field(default=1.0, ge=0.0, le=10.0)
    notes: str = Field(default="", max_length=1000)


class PromoteClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_verdict: Literal["candidate", "supported", "contested", "refuted", "superseded"]
    rationale: str = Field(..., min_length=10)
    actor: str = Field(default="ayman", max_length=120)


class SearchPriorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=2, max_length=500)
    source_id: str | None = Field(default=None, max_length=120)
    max_age_days: int | None = Field(default=None, ge=1, le=3650)


class RecordReuseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(..., min_length=1, max_length=120)
    source_investigation_id: str = Field(..., min_length=1, max_length=120)
    rationale: str = Field(..., min_length=10)
    freshness_assessment: Literal["fresh", "stale", "outdated"] = "fresh"


class SnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(..., min_length=1, max_length=120)
    response_content_b64: str = Field(..., min_length=1)
    response_meta: dict[str, Any] = Field(default_factory=dict)
    retention_class: Literal["default", "long_term", "tenant_specific"] = "default"


class CutoffReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cutoff_iso: str = Field(..., description="ISO 8601 datetime in UTC.")


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/evidence",
    response_model=IngestEvidenceResponse,
    status_code=201,
    summary="Ingest evidence (dedup-aware, bitemporal-safe)",
)
def ingest_evidence(
    req: IngestEvidenceRequest,
    db: Session = Depends(get_db),
) -> IngestEvidenceResponse:
    tenant_id = _resolve_tenant()
    curator = MemoryCurator(db)

    # Validate the evidence dict against the Pydantic contract
    try:
        evidence = EvidenceContract.model_validate(req.evidence)
    except Exception as e:
        raise ValidationError(f"evidence contract validation failed: {e}") from e

    # Decode optional raw content
    raw_content: bytes | None = None
    if req.raw_content_b64:
        import base64

        try:
            raw_content = base64.b64decode(req.raw_content_b64)
        except Exception as e:
            raise ValidationError(f"raw_content_b64 is not valid base64: {e}") from e

    try:
        result = curator.ingest_evidence(
            evidence=evidence,
            tenant_id=tenant_id,
            investigation_id=req.investigation_id,
            raw_content=raw_content,
            actor=req.actor,
        )
    except ValueError as e:
        raise ValidationError(str(e)) from e

    return IngestEvidenceResponse(
        evidence_id=result.evidence_id,
        deduplicated=result.deduplicated,
        reused_from_investigation_id=result.reused_from_investigation_id,
        stored_at_ref=result.stored_at_ref,
        checksum=result.checksum,
        decision_id=result.decision_id,
    )


@router.get(
    "/evidence/{evidence_id}",
    summary="Fetch a single evidence item (tenant-scoped)",
)
def get_evidence(evidence_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    row = db.get(EvidenceItemRow, evidence_id)
    if row is None or row.tenant_id != tenant_id:
        raise NotFoundError(f"evidence {evidence_id} not found")
    return row.payload


@router.get(
    "/investigations/{investigation_id}/evidence",
    summary="List evidence in an investigation (tenant-scoped)",
)
def list_evidence(
    investigation_id: str,
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    tenant_id = _resolve_tenant()
    stmt = (
        select(EvidenceItemRow)
        .where(
            EvidenceItemRow.tenant_id == tenant_id,
            EvidenceItemRow.investigation_id == investigation_id,
        )
        .limit(limit)
    )
    rows = list(db.execute(stmt).scalars())
    return [
        {
            "id": r.id,
            "source_id": r.source_id,
            "kind": r.kind,
            "checksum": r.content_checksum,
            "observed_at": r.observed_at.isoformat() if r.observed_at else None,
            "ingested_at": r.ingested_at.isoformat(),
        }
        for r in rows
    ]


@router.post(
    "/evidence/{evidence_id}/claims",
    status_code=201,
    summary="Attach a claim to a piece of evidence",
)
def attach_claim(
    evidence_id: str,
    req: AttachClaimRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    curator = MemoryCurator(db)
    # The investigation_id is derived from the evidence row (the claim
    # belongs to the same investigation that owns the evidence).
    ev_row = db.get(EvidenceItemRow, evidence_id)
    if ev_row is None or ev_row.tenant_id != tenant_id:
        raise NotFoundError(f"evidence {evidence_id} not found for tenant")
    try:
        row = curator.attach_claim(
            claim_id=req.claim_id,
            tenant_id=tenant_id,
            investigation_id=ev_row.investigation_id,
            evidence_id=evidence_id,
            statement=req.statement,
            verdict=req.verdict,
            independence_group=req.independence_group,
        )
    except ValueError as e:
        raise ValidationError(str(e)) from e
    return {
        "claim_id": row.id,
        "evidence_id": row.evidence_id,
        "verdict": row.verdict,
        "investigation_id": row.investigation_id,
    }


@router.post(
    "/claims/{claim_id}/support",
    status_code=201,
    summary="Add a supports/refutes/qualifies edge (preserves contradictions)",
)
def add_support_edge(
    claim_id: str,
    req: SupportEdgeRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    curator = MemoryCurator(db)
    try:
        edge = curator.add_support_edge(
            tenant_id=tenant_id,
            claim_id=claim_id,
            evidence_id=req.evidence_id,
            relation=req.relation,
            weight=req.weight,
            notes=req.notes,
        )
    except ValueError as e:
        raise ValidationError(str(e)) from e
    return {
        "edge_id": edge.id,
        "claim_id": edge.claim_id,
        "evidence_id": edge.evidence_id,
        "relation": edge.relation,
    }


@router.patch(
    "/claims/{claim_id}/verdict",
    summary="Promote a claim's verdict (with audit; never silently overwrite)",
)
def promote_claim(
    claim_id: str,
    req: PromoteClaimRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    curator = MemoryCurator(db)
    try:
        result = curator.promote_claim(
            claim_id=claim_id,
            tenant_id=tenant_id,
            new_verdict=req.new_verdict,
            rationale=req.rationale,
            actor=req.actor,
        )
    except ValueError as e:
        raise ValidationError(str(e)) from e
    return {
        "claim_id": result.claim_id,
        "previous_verdict": result.previous_verdict,
        "new_verdict": result.new_verdict,
        "decision_id": result.decision_id,
    }


@router.get(
    "/investigations/{investigation_id}/claims",
    summary="List claims in an investigation",
)
def list_claims(
    investigation_id: str,
    db: Session = Depends(get_db),
    verdict: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    tenant_id = _resolve_tenant()
    stmt = select(ClaimRow).where(
        ClaimRow.tenant_id == tenant_id,
        ClaimRow.investigation_id == investigation_id,
    )
    if verdict:
        stmt = stmt.where(ClaimRow.verdict == verdict)
    rows = list(db.execute(stmt).scalars())
    return [
        {
            "id": r.id,
            "evidence_id": r.evidence_id,
            "statement": r.statement,
            "verdict": r.verdict,
            "independence_group": r.independence_group,
            "superseded_by": r.superseded_by,
        }
        for r in rows
    ]


@router.post(
    "/investigations/{investigation_id}/search-prior",
    summary="Search prior memory for evidence reusable by this investigation",
)
def search_prior_memory(
    investigation_id: str,
    req: SearchPriorRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    curator = MemoryCurator(db)
    result = curator.search_prior_memory(
        query=req.query,
        tenant_id=tenant_id,
        investigation_id=investigation_id,
        source_id=req.source_id,
        max_age_days=req.max_age_days,
    )
    return {
        "query": result.query,
        "reusable_count": len(result.reusable_evidence),
        "reusable_evidence": [
            {
                "id": r.id,
                "source_id": r.source_id,
                "kind": r.kind,
                "ingested_at": r.ingested_at.isoformat(),
                "freshness": result.freshness_assessments.get(r.id, "unknown"),
                "original_investigation_id": r.investigation_id,
            }
            for r in result.reusable_evidence
        ],
        "gaps": result.gaps,
    }


@router.post(
    "/investigations/{investigation_id}/reuse",
    status_code=201,
    summary="Record that this investigation reused prior evidence",
)
def record_reuse(
    investigation_id: str,
    req: RecordReuseRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    curator = MemoryCurator(db)
    try:
        row = curator.record_reuse(
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            evidence_id=req.evidence_id,
            source_investigation_id=req.source_investigation_id,
            rationale=req.rationale,
            freshness_assessment=req.freshness_assessment,
        )
    except ValueError as e:
        raise ValidationError(str(e)) from e
    return {
        "reuse_id": row.id,
        "investigation_id": row.investigation_id,
        "evidence_id": row.evidence_id,
        "source_investigation_id": row.source_investigation_id,
        "freshness_assessment": row.freshness_assessment,
    }


@router.get(
    "/investigations/{investigation_id}/decisions",
    summary="Audit log for an investigation (append-only, never overwritten)",
)
def list_decisions(
    investigation_id: str,
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    tenant_id = _resolve_tenant()
    stmt = (
        select(MemoryDecisionRow)
        .where(
            MemoryDecisionRow.tenant_id == tenant_id,
            MemoryDecisionRow.investigation_id == investigation_id,
        )
        .order_by(MemoryDecisionRow.decided_at.desc())
        .limit(limit)
    )
    rows = list(db.execute(stmt).scalars())
    return [
        {
            "id": r.id,
            "decision_type": r.decision_type,
            "evidence_id": r.evidence_id,
            "claim_id": r.claim_id,
            "actor": r.actor,
            "rationale": r.rationale,
            "decided_at": r.decided_at.isoformat(),
        }
        for r in rows
    ]


@router.post(
    "/snapshots",
    status_code=201,
    summary="Capture a source response snapshot (content-addressed, idempotent)",
)
def capture_snapshot(
    req: SnapshotRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    curator = MemoryCurator(db)
    import base64

    try:
        content = base64.b64decode(req.response_content_b64)
    except Exception as e:
        raise ValidationError(f"response_content_b64 is not valid base64: {e}") from e
    row = curator.capture_source_snapshot(
        tenant_id=tenant_id,
        source_id=req.source_id,
        response_content=content,
        response_meta=req.response_meta,
        retention_class=req.retention_class,
    )
    return {
        "snapshot_id": row.id,
        "source_id": row.source_id,
        "checksum": row.snapshot_checksum,
        "stored_ref": row.snapshot_ref,
        "captured_at": row.captured_at.isoformat(),
    }


@router.post(
    "/investigations/{investigation_id}/at-cutoff",
    summary="Bitemporal replay: evidence visible at a cutoff time (no future leakage)",
)
def evidence_at_cutoff(
    investigation_id: str,
    req: CutoffReplayRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    curator = MemoryCurator(db)
    try:
        cutoff = datetime.fromisoformat(req.cutoff_iso)
    except ValueError as e:
        raise ValidationError(f"invalid cutoff_iso: {e}") from e
    rows = curator.get_evidence_at_cutoff(
        tenant_id=tenant_id,
        investigation_id=investigation_id,
        cutoff=cutoff,
    )
    return {
        "investigation_id": investigation_id,
        "cutoff": cutoff.isoformat(),
        "visible_evidence_count": len(rows),
        "visible_evidence": [
            {
                "id": r.id,
                "source_id": r.source_id,
                "observed_at": r.observed_at.isoformat() if r.observed_at else None,
                "ingested_at": r.ingested_at.isoformat(),
            }
            for r in rows
        ],
    }


__all__ = ["router"]
