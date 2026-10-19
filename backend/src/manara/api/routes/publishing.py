"""``/publishing`` API routes — Publishing layer surface (G07).

Endpoints:
* ``POST   /publishing/publications``           — create a publication
* ``GET    /publishing/publications``             — list publications
* ``GET    /publishing/publications/{id}``        — fetch one publication
* ``GET    /publishing/publications/{id}/download`` — download (json/markdown/text)
* ``GET    /publishing/publications/{id}/quality-gate`` — quality gate result
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from manara.api.errors import NotFoundError, ValidationError
from manara.config import settings
from manara.db.publishing_models import PublicationRow
from manara.db.session import get_db
from manara.publishing import PublicationRegistry

router = APIRouter(prefix="/publishing", tags=["publishing"])


def _resolve_tenant() -> str:
    return settings.default_tenant_id


class CreatePublicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    investigation_id: str = Field(..., min_length=1, max_length=120)
    output_type: Literal["research_dossier", "presenter_edition", "visual_storyboard"]
    title: str = Field(..., min_length=5, max_length=500)
    scope: dict[str, Any] = Field(default_factory=dict)


@router.post("/publications", status_code=201, summary="Create a publication from investigation evidence")
def create_publication(
    req: CreatePublicationRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    registry = PublicationRegistry(db)
    try:
        row = registry.create_publication(
            investigation_id=req.investigation_id,
            tenant_id=tenant_id,
            output_type=req.output_type,
            title=req.title,
            scope=req.scope,
        )
    except ValueError as e:
        raise ValidationError(str(e)) from e
    return {
        "publication_id": row.id,
        "output_type": row.output_type,
        "status": row.status,
        "quality_gate_passed": row.quality_gate_passed,
        "quality_gate_issues": row.quality_gate_issues,
        "deliverable_type": row.deliverable_type,
        "downloadable": row.downloadable,
    }


@router.get("/publications", summary="List publications (tenant-scoped)")
def list_publications(
    db: Session = Depends(get_db),
    output_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    tenant_id = _resolve_tenant()
    stmt = select(PublicationRow).where(PublicationRow.tenant_id == tenant_id)
    if output_type:
        stmt = stmt.where(PublicationRow.output_type == output_type)
    stmt = stmt.order_by(PublicationRow.created_at.desc()).limit(limit)
    rows = list(db.execute(stmt).scalars())
    return [
        {
            "id": r.id,
            "title": r.title,
            "output_type": r.output_type,
            "status": r.status,
            "deliverable_type": r.deliverable_type,
            "quality_gate_passed": r.quality_gate_passed,
            "downloadable": r.downloadable,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/publications/{pub_id}", summary="Fetch one publication")
def get_publication(pub_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    tenant_id = _resolve_tenant()
    registry = PublicationRegistry(db)
    row = registry.get_publication(pub_id, tenant_id=tenant_id)
    if row is None:
        raise NotFoundError(f"publication {pub_id} not found")
    return {
        "id": row.id,
        "title": row.title,
        "output_type": row.output_type,
        "status": row.status,
        "deliverable_type": row.deliverable_type,
        "quality_gate_passed": row.quality_gate_passed,
        "quality_gate_issues": row.quality_gate_issues,
        "downloadable": row.downloadable,
        "content": row.content_json,
        "created_at": row.created_at.isoformat(),
    }


@router.get("/publications/{pub_id}/download", summary="Download publication (json/markdown/text)")
def download_publication(
    pub_id: str,
    db: Session = Depends(get_db),
    format: str = Query(default="json"),
) -> dict[str, Any]:
    """Download a publication in the requested format.

    Per owner (G07):
    > "التنزيل ينتج ملفاً سليماً وغير فارغ."
    """
    tenant_id = _resolve_tenant()
    registry = PublicationRegistry(db)
    content = registry.download(pub_id, tenant_id=tenant_id, format_=format)
    if content is None:
        raise NotFoundError(
            f"publication {pub_id} not found or not downloadable "
            f"(quality gate may have failed)"
        )
    return {
        "publication_id": pub_id,
        "format": format,
        "content": content,
    }


__all__ = ["router"]
