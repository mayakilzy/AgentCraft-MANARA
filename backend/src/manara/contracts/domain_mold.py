"""DomainMold contract — versioned sector/research orchestration recipe.

Maps to ``01_ARCHITECTURE/01_MASTER.md``:
    "Mold is a versioned sector/research orchestration recipe."

And to ``03_INTELLIGENCE/03_AGENT_AND_MOLD_LIFECYCLE.md``:
    `temporary` recipe can execute and be saved without operational maintenance
    burden; `reusable` saved, `maintained` monitored/version-pinned,
    `archived` preserved as recipe/history. No duplicate code per domain.

A Mold is *not* a code branch. It is a declarative recipe that composes
existing SearchCapability IDs (and optionally AgentRecipe IDs) into a
research orchestration plan for a particular sector / question family.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from manara.lifecycle import MoldState

MOLD_SCHEMA_VERSION = "1.0.0"


class MoldScope(BaseModel):
    """What the mold is for: domain, time, geography, deliverables."""

    model_config = ConfigDict(extra="forbid")

    domain: str = Field(..., min_length=1, max_length=120)
    subdomains: list[str] = Field(default_factory=list)
    intent: str = Field(..., min_length=10, description="One-sentence statement of what this mold investigates.")
    sector: str | None = Field(default=None)
    time_horizon_end: datetime | None = Field(default=None, description="Optional horizon end date.")
    geography: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(
        default_factory=lambda: ["evidence_dossier"],
        description="Deliverable shapes (dossier, scenario_report, brief, ...).",
    )
    output_language_default: str | None = Field(default=None)


class MoldComposition(BaseModel):
    """Composed capability IDs and optional agent recipe references."""

    model_config = ConfigDict(extra="forbid")

    capability_ids: list[str] = Field(
        default_factory=list,
        description="SearchCapability IDs this mold orchestrates.",
    )
    agent_recipe_ids: list[str] = Field(
        default_factory=list,
        description="Optional AgentRecipe IDs (specialist workers).",
    )
    composition_notes: str = Field(default="")
    plan: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Ordered execution plan steps (declarative, not code).",
    )


class Mold(BaseModel):
    """A versioned domain orchestration recipe."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        ...,
        description="Mold ID, e.g. 'mold.recycling-2026-001'.",
        pattern=r"^mold\.[a-z0-9][a-z0-9-]{1,80}$",
    )
    schema_version: str = Field(default=MOLD_SCHEMA_VERSION)
    version: str = Field(..., description="Recipe version (semver preferred).")
    display_name: str = Field(..., min_length=1, max_length=200)
    description_long: str = Field(..., min_length=20)
    author: str | None = Field(default=None)
    scope: MoldScope
    composition: MoldComposition = Field(default_factory=MoldComposition)
    state: MoldState = Field(default=MoldState.TEMPORARY)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_piloted_at: datetime | None = Field(default=None)
    archived_at: datetime | None = Field(default=None)

    @model_validator(mode="after")
    def _validate(self) -> Mold:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")
        if self.state == MoldState.ARCHIVED and not self.archived_at:
            # Default archive timestamp if missing
            self.archived_at = self.updated_at
        if self.state != MoldState.ARCHIVED and self.archived_at is not None:
            raise ValueError("archived_at may only be set when state == archived")
        # Maintained mold must have been piloted at least once
        if self.state == MoldState.MAINTAINED and self.last_piloted_at is None:
            raise ValueError("maintained mold requires last_piloted_at")
        return self


__all__ = [
    "MOLD_SCHEMA_VERSION",
    "Mold",
    "MoldScope",
    "MoldComposition",
]
