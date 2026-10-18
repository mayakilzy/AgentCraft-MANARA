"""Investigation contract — a research run with its own evidence state.

Maps to ``01_ARCHITECTURE/01_MASTER.md``:
    "Investigation is a run with its own temporary evidence state and outputs."

And to ``03_INTELLIGENCE/04_INVESTIGATION_PIPELINE.md``:
    End-to-end state graph:
    received → scoped → coverage_checked → [building_capabilities?] →
    mold_ready → acquiring → normalizing → evidencing →
    forecasting_or_scenarios → drafting → verification →
    deliverable_ready → archived.
    Each state: owner, checkpoint hash, retry semantics, evidence, next
    action; pending failures visible and recoverable; no fake completion.

An Investigation is tenant-scoped from authorization through all
jobs/joins/embeddings/object storage (per the security policy).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from manara.lifecycle import INVESTIGATION_TRANSITIONS, InvestigationState

INVESTIGATION_SCHEMA_VERSION = "1.0.0"


class InvestigationScope(BaseModel):
    """The user's question, refined into scope."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(..., min_length=10, description="The user's research question.")
    horizon_end: datetime | None = Field(default=None)
    geography: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(
        default_factory=lambda: ["evidence_dossier"],
        description="Requested output shapes.",
    )
    output_language_default: str | None = Field(default=None)
    constraints: dict[str, Any] = Field(default_factory=dict)


class InvestigationCheckpoint(BaseModel):
    """A checkpoint in the state graph with hash and retry semantics."""

    model_config = ConfigDict(extra="forbid")

    state: InvestigationState
    entered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    owner: str | None = Field(default=None, description="User or agent that advanced the state.")
    checkpoint_hash: str | None = Field(default=None, description="Content hash of intermediate state, for resume.")
    retry_count: int = Field(default=0, ge=0)
    retry_semantics: dict[str, Any] = Field(default_factory=dict)
    next_action: str | None = Field(default=None)
    notes: str = Field(default="")


class Investigation(BaseModel):
    """A single investigation run.

    The investigation carries:
    * a ``tenant_id`` (mandatory — tenant scoping on every row, per security policy)
    * a ``user_id`` (the requester)
    * a state machine with ordered transitions
    * a list of evidence IDs (collected during evidencing state)
    * a mold recipe reference (if a mold was composed)
    * agent recipe references (if specialists were used)
    * forecast references (if any)
    * a checkpoint history (for resumable workflows)
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    schema_version: str = Field(default=INVESTIGATION_SCHEMA_VERSION)
    tenant_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    scope: InvestigationScope

    state: InvestigationState = Field(default=InvestigationState.RECEIVED)

    mold_recipe_id: str | None = Field(default=None)
    agent_recipe_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    forecast_ids: list[str] = Field(default_factory=list)
    deliverable_refs: list[str] = Field(default_factory=list)

    checkpoints: list[InvestigationCheckpoint] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    archived_at: datetime | None = Field(default=None)

    @model_validator(mode="after")
    def _validate(self) -> Investigation:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")
        if self.state == InvestigationState.ARCHIVED and not self.archived_at:
            self.archived_at = self.updated_at
        if self.state != InvestigationState.ARCHIVED and self.archived_at is not None:
            raise ValueError("archived_at may only be set when state == archived")

        # Checkpoint history must be a valid walk along the state graph.
        if self.checkpoints:
            seen: set[InvestigationState] = set()
            prev: InvestigationState | None = None
            for cp in self.checkpoints:
                if cp.state in seen and cp.state != self.checkpoints[-1].state:
                    # Allow only the *last* checkpoint to be a re-entry of a prior state
                    # (e.g. retry). For G00 we keep this lenient.
                    pass
                if prev is not None:
                    allowed = INVESTIGATION_TRANSITIONS.get(prev, set())
                    if cp.state not in allowed and cp.state != prev:
                        raise ValueError(
                            f"invalid transition {prev.value} → {cp.state.value}"
                        )
                prev = cp.state
                seen.add(cp.state)
            # Final checkpoint must match the current state
            if self.checkpoints[-1].state != self.state:
                raise ValueError("final checkpoint state must match investigation state")
        return self


__all__ = [
    "INVESTIGATION_SCHEMA_VERSION",
    "Investigation",
    "InvestigationScope",
    "InvestigationCheckpoint",
]
