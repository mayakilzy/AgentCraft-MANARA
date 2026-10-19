"""ORM models for the Mold Factory (G04).

These tables store mold recipes (the G00 ``Mold`` contract materialized
as rows) plus the gap analysis records produced by the Mold Architect
when it cannot fully satisfy a request from existing capabilities.

Per ``03_INTELLIGENCE/03_AGENT_AND_MOLD_LIFECYCLE.md``:
> A new unfamiliar field must NOT be rejected solely for lacking a mold
> nor silently assigned a fictitious existing mold.

The Mold Factory detects the gap, attempts to compose a temporary mold
from existing capabilities, and records the residual gaps honestly —
never fabricating capabilities that don't exist.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from manara.db.session import Base


class MoldRecipeRow(Base):
    """A stored mold recipe (the G00 ``Mold`` contract materialized).

    State transitions per spec:
        temporary → reusable → maintained → archived

    A temporary mold can be created on-demand and saved as a recipe
    without operational maintenance burden. Reusable recipes can be
    rehydrated for new investigations. Maintained recipes are
    version-pinned and periodically re-validated. Archived recipes
    retain their history but no longer execute.

    Per owner decision (2026-10-19):
    > "انتهاء تنفيذ القالب المؤقت لا يعني حذف وصفته أو نتائج تقييمه."

    So a temporary mold's recipe survives even after its investigation
    completes — it can be rehydrated for the next similar question.
    """

    __tablename__ = "mold_recipes"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description_long: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(60), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False, default="1.0.0")
    state: Mapped[str] = mapped_column(String(40), nullable=False, default="temporary", index=True)
    # temporary | reusable | maintained | archived

    # Mold scope (denormalized for fast filtering)
    domain: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    intent: Mapped[str] = mapped_column(Text, nullable=False)
    sector: Mapped[str | None] = mapped_column(String(120), nullable=True)
    geography_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    languages_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    deliverables_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Composition: which capabilities and (future) agent recipes
    capability_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    agent_recipe_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    composition_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    plan_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)

    # Origin: was this mold created fresh (temporary) or loaded from a recipe?
    origin: Mapped[str] = mapped_column(String(40), nullable=False, default="temporary")
    # temporary_fresh | reused_from_recipe | promoted

    # Promotion metadata (set when state becomes reusable/maintained)
    promoted_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    promotion_rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Last pilot (set when an investigation actually runs this mold)
    last_piloted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # The full Pydantic contract payload
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

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
        UniqueConstraint("id", "tenant_id", name="uq_mold_recipes_id_tenant"),
        Index("ix_mold_recipes_tenant_state", "tenant_id", "state"),
        Index("ix_mold_recipes_tenant_domain", "tenant_id", "domain"),
    )


class GapAnalysisRow(Base):
    """A record of capabilities that were MISSING when composing a mold.

    Per spec:
    > "Discover what's missing. Don't fabricate capabilities."

    Each row records one detected gap: a research need that the current
    registry cannot satisfy. The Foundry (G02) is invoked to assess
    whether the gap can be filled by discovering a new source/connector.
    If the Foundry cannot fill it, the gap is recorded as ``unresolved``
    and the mold is composed WITHOUT that capability — the investigation
    report will explicitly note the missing coverage.

    Per owner decision (2026-10-19):
    > "إذا لم تسمح قدرات G02 الحالية ببناء موصل جديد تلقائياً، سجّل هذه
    > الفجوة صراحةً. لا تتحايل عليها ببطاقة افتراضية تدّعي أنها محرك حقيقي."
    """

    __tablename__ = "mold_gap_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    mold_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("mold_recipes.id"), nullable=False, index=True
    )
    investigation_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)

    need: Mapped[str] = mapped_column(String(60), nullable=False)
    # scientific_literature | patent_intelligence | clinical_evidence | ...
    need_label: Mapped[str] = mapped_column(String(200), nullable=False)

    # What the registry has (if anything)
    candidate_capability_ids_json: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )

    # Resolution status
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="open")
    # open | foundry_invoked | foundry_no_candidate | resolved | unresolved
    # - open: gap detected, Foundry not yet invoked
    # - foundry_invoked: Foundry sandbox test requested
    # - foundry_no_candidate: Foundry has no source for this need
    # - resolved: gap filled (new connector approved)
    # - unresolved: gap cannot be filled with current Foundry capabilities

    resolution_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    foundry_candidate_id: Mapped[str | None] = mapped_column(String(120), nullable=True)

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
        Index("ix_gap_tenant_status", "tenant_id", "status"),
        Index("ix_gap_mold_need", "mold_id", "need"),
    )


class MoldReuseRow(Base):
    """Records when a mold recipe is rehydrated for a new investigation.

    Per spec: a temporary mold's recipe survives its first investigation
    and can be re-used by subsequent similar questions.
    """

    __tablename__ = "mold_reuse"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    mold_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("mold_recipes.id"), nullable=False, index=True
    )
    investigation_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    reuse_rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Was the mold updated during this reuse (e.g. new capability added)?
    modified_during_reuse: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False  # SQLAlchemy boolean stored as 0/1
    )

    reused_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("mold_id", "investigation_id", name="uq_mold_reuse"),
        Index("ix_mold_reuse_tenant_investigation", "tenant_id", "investigation_id"),
    )


class InvestigationWorkflowRow(Base):
    """Tracks the workflow state of an investigation through the G04 pipeline.

    The G00 ``Investigation`` contract carries a state machine, but G04
    is the first mission that ENFORCES it at the service + API layer.
    This row records the current state and the audit trail of transitions.

    Per owner decision (2026-10-19):
    > "نعم، على مستوى الخدمة وAPI، لكن وفق الشروط الفعلية لكل مرحلة،
    > مع حالات واضحة للنقص والتعذر."
    """

    __tablename__ = "investigation_workflows"

    investigation_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("investigations.id"), primary_key=True
    )
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    state: Mapped[str] = mapped_column(String(60), nullable=False, default="received", index=True)
    mold_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)

    # Transition audit trail (append-only)
    transitions_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )

    # Blockers (when state cannot advance)
    blocker: Mapped[str | None] = mapped_column(Text, nullable=True)
    # e.g. "no mold available", "foundry cannot resolve gap", "no evidence collected"

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
        Index("ix_workflow_tenant_state", "tenant_id", "state"),
    )


__all__ = [
    "GapAnalysisRow",
    "InvestigationWorkflowRow",
    "MoldRecipeRow",
    "MoldReuseRow",
]
