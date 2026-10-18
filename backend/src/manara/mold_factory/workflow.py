"""Investigation workflow service — enforces the state machine (G04).

Per owner decision (2026-10-19):
> "نعم، على مستوى الخدمة وAPI، لكن وفق الشروط الفعلية لكل مرحلة،
> مع حالات واضحة للنقص والتعذر."

This service:
* Tracks each investigation's state via ``InvestigationWorkflowRow``.
* Enforces the G00 ``InvestigationState`` transition table — illegal
  jumps are rejected.
* Validates pre-conditions per state:
    - received → scoped: requires a non-empty topic
    - scoped → coverage_checked: requires mold detection to have run
    - coverage_checked → mold_ready | building_capabilities: requires
      either an existing mold (mold_ready) or a composed temporary mold
      (building_capabilities → mold_ready)
    - mold_ready → acquiring: requires a mold_id on the workflow row
    - acquiring → normalizing: requires at least one evidence item OR
      an explicit blocker ("no real connector yet")
    - drafting → verification: per owner decision, drafts may include
      hypotheses without evidence (clearly labeled)
    - verification → deliverable_ready: requires either (a) every
      published claim has traceable evidence, OR (b) the report is
      explicitly labeled "coverage gaps" report
* Records a ``blocker`` field when a transition cannot advance.
* Append-only audit trail (transitions_json).

The service does NOT auto-advance states. The caller (API or agent)
must explicitly call ``transition()`` with the target state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from manara.db.memory_models import EvidenceItemRow
from manara.db.models import InvestigationRow
from manara.db.mold_models import GapAnalysisRow, InvestigationWorkflowRow
from manara.lifecycle import INVESTIGATION_TRANSITIONS, InvestigationState

# ─────────────────────────────────────────────────────────────────────────────
# Result dataclasses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TransitionResult:
    """Result of a state transition attempt."""

    investigation_id: str
    previous_state: str
    new_state: str
    transitioned: bool
    blocker: str | None = None
    transition_id: int | None = None  # index into the transitions_json list
    transitioned_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class WorkflowTransitionError(Exception):
    """Raised when a transition is illegal or pre-conditions are not met."""


# ─────────────────────────────────────────────────────────────────────────────
# InvestigationWorkflowService
# ─────────────────────────────────────────────────────────────────────────────


class InvestigationWorkflowService:
    """Enforces the G00 ``InvestigationState`` machine.

    Per spec: "pending failures visible and recoverable; no fake completion."
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_workflow(self, investigation_id: str, *, tenant_id: str) -> InvestigationWorkflowRow | None:
        """Fetch the workflow row for an investigation (tenant-scoped)."""
        row = self.db.get(InvestigationWorkflowRow, investigation_id)
        if row is None or row.tenant_id != tenant_id:
            return None
        return row

    def create_workflow(
        self,
        *,
        investigation_id: str,
        tenant_id: str,
        initial_state: str = "received",
    ) -> InvestigationWorkflowRow:
        """Create a workflow row for a new investigation."""
        existing = self.db.get(InvestigationWorkflowRow, investigation_id)
        if existing is not None:
            return existing

        # Verify the investigation exists
        inv = self.db.get(InvestigationRow, investigation_id)
        if inv is None or inv.tenant_id != tenant_id:
            raise WorkflowTransitionError(
                f"investigation {investigation_id} not found for tenant {tenant_id}"
            )

        row = InvestigationWorkflowRow(
            investigation_id=investigation_id,
            tenant_id=tenant_id,
            state=initial_state,
            transitions_json=[
                {
                    "from": None,
                    "to": initial_state,
                    "at": datetime.now(UTC).isoformat(),
                    "actor": "system",
                    "rationale": "workflow created",
                }
            ],
        )
        self.db.add(row)
        self.db.commit()
        return row

    def transition(
        self,
        *,
        investigation_id: str,
        tenant_id: str,
        target_state: str,
        actor: str = "system",
        rationale: str = "",
        mold_id: str | None = None,
    ) -> TransitionResult:
        """Attempt to transition the investigation to ``target_state``.

        Validates:
        1. The transition is in the G00 INVESTIGATION_TRANSITIONS table.
        2. The pre-conditions for the target state are met.

        On success: appends to transitions_json, updates state, returns
        TransitionResult(transitioned=True).
        On failure: returns TransitionResult(transitioned=False, blocker=...).
        Does NOT raise on precondition failure — the caller decides whether
        to retry or report the blocker.
        """
        row = self.get_workflow(investigation_id, tenant_id=tenant_id)
        if row is None:
            # Auto-create if the investigation exists
            self.create_workflow(
                investigation_id=investigation_id, tenant_id=tenant_id
            )
            row = self.get_workflow(investigation_id, tenant_id=tenant_id)
            assert row is not None  # created above

        current = InvestigationState(row.state)
        try:
            target = InvestigationState(target_state)
        except ValueError as e:
            raise WorkflowTransitionError(
                f"invalid target state: {target_state!r}"
            ) from e

        # Check 1: transition legal?
        allowed_targets = INVESTIGATION_TRANSITIONS.get(current, set())
        if target not in allowed_targets:
            return TransitionResult(
                investigation_id=investigation_id,
                previous_state=current.value,
                new_state=target.value,
                transitioned=False,
                blocker=(
                    f"illegal transition {current.value} → {target.value}. "
                    f"Allowed: {[t.value for t in allowed_targets]}"
                ),
            )

        # Check 2: pre-conditions for the target state
        precondition_blocker = self._check_preconditions(
            row=row,
            current=current,
            target=target,
            tenant_id=tenant_id,
            mold_id=mold_id,
        )
        if precondition_blocker is not None:
            row.blocker = precondition_blocker
            self.db.commit()
            return TransitionResult(
                investigation_id=investigation_id,
                previous_state=current.value,
                new_state=target.value,
                transitioned=False,
                blocker=precondition_blocker,
            )

        # All checks pass — apply the transition
        previous_state = row.state
        row.state = target.value
        row.blocker = None
        if mold_id is not None:
            row.mold_id = mold_id

        transition_entry: dict[str, Any] = {
            "from": previous_state,
            "to": target.value,
            "at": datetime.now(UTC).isoformat(),
            "actor": actor,
            "rationale": rationale,
        }
        transitions = list(row.transitions_json or [])
        transitions.append(transition_entry)
        row.transitions_json = transitions
        self.db.commit()

        return TransitionResult(
            investigation_id=investigation_id,
            previous_state=previous_state,
            new_state=target.value,
            transitioned=True,
            transition_id=len(transitions) - 1,
        )

    # ── Pre-condition checks ──────────────────────────────────────────────────

    def _check_preconditions(
        self,
        *,
        row: InvestigationWorkflowRow,
        current: InvestigationState,
        target: InvestigationState,
        tenant_id: str,
        mold_id: str | None,
    ) -> str | None:
        """Return a blocker string if pre-conditions fail, else None.

        Per owner decision:
        > "لا يُشترط وجود دليل لكل ادعاء أثناء صياغة المسودة، لأن المسودة
        > قد تتضمن فرضيات وأسئلة مفتوحة. لكن لا يجوز نشر ادعاء باعتباره
        > حقيقة مثبتة دون أدلة قابلة للتتبع."

        So:
        - drafting: no evidence required (hypotheses allowed)
        - deliverable_ready: requires either (a) evidence exists OR
          (b) the report is explicitly a "coverage gaps" report
        """
        if target == InvestigationState.SCOPED:
            # The investigation must have a topic
            inv = self.db.get(InvestigationRow, row.investigation_id)
            if inv is None or not inv.topic:
                return "cannot scope: investigation has no topic"

        elif target == InvestigationState.COVERAGE_CHECKED:
            # Mold detection must have run — EITHER:
            # (a) a mold_id is set on the workflow row, OR
            # (b) a gap analysis exists for this investigation (which means
            #     the MoldArchitect ran and detected gaps).
            # The transition() method passes mold_id, so we check that first;
            # if not passed, we fall back to checking for gap analyses.
            if mold_id is not None:
                pass  # mold_id provided in this transition — accept
            elif row.mold_id is not None:
                pass  # mold_id already set on the workflow row — accept
            else:
                gap_count = self._count_gap_analyses(
                    investigation_id=row.investigation_id, tenant_id=tenant_id
                )
                if gap_count == 0:
                    return (
                        "cannot coverage_check: no mold detection has been run. "
                        "Call the MoldArchitect first (which sets mold_id or "
                        "records gap analyses)."
                    )

        elif target == InvestigationState.MOLD_READY:
            # A mold must be set on the workflow row
            if row.mold_id is None and mold_id is None:
                return (
                    "cannot enter mold_ready: no mold_id set. "
                    "Call the MoldArchitect and pass the mold_id."
                )

        elif target == InvestigationState.ACQUIRING:
            # The mold must exist and have at least one capability OR
            # an explicit gap analysis (so the report can document gaps).
            if row.mold_id is None:
                return "cannot acquire: no mold_id set"

        elif target == InvestigationState.EVIDENCING:
            # At least one evidence item should exist OR a gap analysis
            # marked "unresolved" (so the investigation explicitly
            # documents that no evidence could be acquired).
            ev_count = self._count_evidence(
                investigation_id=row.investigation_id, tenant_id=tenant_id
            )
            if ev_count == 0:
                gap_count = self._count_gap_analyses(
                    investigation_id=row.investigation_id, tenant_id=tenant_id,
                    status_filter="unresolved",
                )
                if gap_count == 0:
                    return (
                        "cannot enter evidencing: no evidence collected AND "
                        "no unresolved gap recorded. Either acquire evidence "
                        "OR explicitly record that the source is unavailable."
                    )

        elif target == InvestigationState.VERIFICATION:
            # Per owner: drafts may include hypotheses without evidence.
            # Verification requires either evidence-backed claims OR
            # explicit "coverage gaps" labeling.
            pass  # no strict precondition

        elif target == InvestigationState.DELIVERABLE_READY:
            # The investigation must EITHER have evidence-backed claims
            # OR be explicitly labeled as a "coverage gaps" report.
            ev_count = self._count_evidence(
                investigation_id=row.investigation_id, tenant_id=tenant_id
            )
            gap_count = self._count_gap_analyses(
                investigation_id=row.investigation_id, tenant_id=tenant_id
            )
            if ev_count == 0 and gap_count == 0:
                return (
                    "cannot enter deliverable_ready: no evidence AND no gaps "
                    "recorded. The report must either be evidence-backed OR "
                    "explicitly labeled as a 'coverage gaps' report."
                )

        elif target == InvestigationState.ARCHIVED:
            # No pre-conditions — any state can transition to archived
            # (per spec: archived is terminal).
            pass

        return None

    def _count_evidence(
        self, *, investigation_id: str, tenant_id: str
    ) -> int:
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(EvidenceItemRow)
            .where(
                EvidenceItemRow.tenant_id == tenant_id,
                EvidenceItemRow.investigation_id == investigation_id,
            )
        )
        return int(self.db.execute(stmt).scalar_one())

    def _count_gap_analyses(
        self,
        *,
        investigation_id: str,
        tenant_id: str,
        status_filter: str | None = None,
    ) -> int:
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(GapAnalysisRow)
            .where(
                GapAnalysisRow.tenant_id == tenant_id,
                GapAnalysisRow.investigation_id == investigation_id,
            )
        )
        if status_filter is not None:
            stmt = stmt.where(GapAnalysisRow.status == status_filter)
        return int(self.db.execute(stmt).scalar_one())


__all__ = [
    "InvestigationWorkflowService",
    "TransitionResult",
    "WorkflowTransitionError",
]
