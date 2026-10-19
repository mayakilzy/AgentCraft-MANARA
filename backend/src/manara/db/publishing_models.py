"""ORM models for the Publishing layer (G07).

Per ``04_OUTPUTS/01_PUBLISHING.md``:
> "A single evidence dossier powers multiple renderings."

Three tables:
* ``publications``           — published output records (dossier, presenter, storyboard)
* ``publication_claims``     — claims cited in a publication, linked to evidence
* ``storyboard_scenes``      — visual scenes with evidence/fiction classification
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from manara.db.session import Base


class PublicationRow(Base):
    """A published output (dossier, presenter edition, or storyboard).

    Per owner (G07):
    > "Single Evidence Dossier → Multiple Output Renderers."
    > "لا تُنشئ محرك بحث جديداً لكل نوع تقرير."

    Each publication is derived from the SAME evidence base (G03 memory)
    but rendered in a different format. The evidence_links table connects
    every claim in the publication back to its source evidence.
    """

    __tablename__ = "publishing_publications"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    investigation_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)

    # Output type
    output_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # research_dossier | presenter_edition | visual_storyboard

    # Versioning
    version: Mapped[str] = mapped_column(String(60), nullable=False, default="0.1.0")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", index=True)
    # draft | quality_checked | published | superseded

    # Content (JSON structure varies by output_type)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    # Dossier: {sections, executive_summary, findings, contradictions, ...}
    # Presenter: {script, cue_sheet, editor_notes, timing, ...}
    # Storyboard: {scenes, rights_manifest, asset_provenance, ...}

    # Quality gate
    quality_gate_passed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    quality_gate_issues: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Deliverable type (per owner G07: distinguish research deliverable from coverage blocker)
    deliverable_type: Mapped[str] = mapped_column(String(40), nullable=False, default="research_deliverable")
    # research_deliverable | coverage_blocker_report

    # Download info
    downloadable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    download_format: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # json | markdown | text

    # Revision tracking
    subsequent_revision_of: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    superseded_by: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Timestamps
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_publications_id_tenant"),
        Index("ix_publications_tenant_type", "tenant_id", "output_type"),
        Index("ix_publications_tenant_status", "tenant_id", "status"),
    )


class PublicationClaimRow(Base):
    """A claim cited in a publication, linked to evidence.

    Per owner (G07):
    > "كل ادعاء موثق يجب أن يرتبط بمعرّفات الأدلة الأصلية في G03،
    > لا بمجرد نص مرجع مكتوب بصورة حرة."
    """

    __tablename__ = "publishing_publication_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    publication_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("publishing_publications.id"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)

    # The claim text as it appears in the publication
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Classification (per owner G07)
    claim_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # fact | hypothesis | scenario | forecast | analysis | gap
    # Per owner: "لا يسمح قسم النشر بأن يجعل الاستنتاج غير المؤكد يبدو حقيقة"

    # Evidence links (from G03 memory)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    # Must reference real EvidenceItemRow IDs in the tenant's memory

    # Verification status
    verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    verification_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Section reference (where in the publication this claim appears)
    section_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        Index("ix_pub_claims_tenant_pub", "tenant_id", "publication_id"),
    )


class StoryboardSceneRow(Base):
    """A visual scene in a storyboard.

    Per owner (G07):
    > "كل مشهد واقعي يحتاج إلى مصدر أو دليل مناسب."
    > "المشاهد الافتراضية والخيالية يجب أن تحمل إفصاحاً واضحاً، ولا يجوز
    > تقديمها باعتبارها تصويراً وثائقياً لحدث وقع بالفعل."
    """

    __tablename__ = "publishing_storyboard_scenes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    publication_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("publishing_publications.id"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)

    scene_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Scene classification (per owner G07)
    scene_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # evidence_backed_factual | data_visualization | scientific_reconstruction
    # | scenario_illustration | fictional_scene
    #
    # Per owner: "ممنوع تصوير مشهد خيالي على أنه نشرة أخبار!"
    # Fictional scenes MUST be labeled as fictional — never presented as documentary.

    # Evidence link (required for evidence_backed and data_visualization)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    # If scene_type is fictional_scene or scenario_illustration, this can be empty.

    # Rights and provenance
    rights_status: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    # owned | licensed | fair_use | public_domain | unknown | restricted
    rights_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_attribution: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Visual suggestions
    visual_suggestions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Disclosure (required for fictional/scenario scenes)
    disclosure_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # e.g. "This is a fictional illustration of a possible future scenario.
    #        It is NOT a documentary depiction of actual events."

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        Index("ix_scenes_tenant_pub", "tenant_id", "publication_id"),
        Index("ix_scenes_pub_scene_num", "publication_id", "scene_number"),
    )


__all__ = [
    "PublicationClaimRow",
    "PublicationRow",
    "StoryboardSceneRow",
]
