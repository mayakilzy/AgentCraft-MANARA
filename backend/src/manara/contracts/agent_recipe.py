"""AgentRecipe contract — rehydratable specialist worker recipe.

Maps to ``01_ARCHITECTURE/01_MASTER.md``:
    "Agent executes tasks via authorized capabilities; not the source of truth."

And to ``03_INTELLIGENCE/03_AGENT_AND_MOLD_LIFECYCLE.md``:
    After completion, persist *recipe and evaluation* (role, prompts, permitted
    tools, template, model compatibility, tests, outcome, learning notes),
    terminate runtime. Next request rehydrates recipe with compatibility and
    security checks. This is the 'phone book for shift workers'.

Important: the Agent is **ephemeral** at runtime; the **recipe** is what
persists. This contract describes the recipe, not a live process.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from manara.lifecycle import AgentState

AGENT_RECIPE_SCHEMA_VERSION = "1.0.0"


class AgentRetentionPolicy(BaseModel):
    """When to keep a recipe vs retire it.

    Per the spec, retention is *not* just frequency: it considers repeat
    demand + economic value + proven improvement over generalist + rarity
    + operational maintenance burden, with empirical gates.
    """

    model_config = ConfigDict(extra="forbid")

    repeat_demand_score: float = Field(default=0.0, ge=0.0, le=1.0)
    economic_value_score: float = Field(default=0.0, ge=0.0, le=1.0)
    improvement_over_generalist: float = Field(default=0.0, ge=0.0, le=1.0)
    rarity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    maintenance_burden_score: float = Field(default=0.0, ge=0.0, le=1.0)
    notes: str = Field(default="")


class AgentRecipeTests(BaseModel):
    """Reference to recipe-level tests/evaluations."""

    model_config = ConfigDict(extra="forbid")

    unit_tests: list[str] = Field(default_factory=list)
    evaluation_fixtures: list[str] = Field(default_factory=list)
    last_evaluation_outcome: str | None = Field(default=None)
    last_evaluation_at: datetime | None = Field(default=None)


class AgentRecipe(BaseModel):
    """A rehydratable specialist agent recipe.

    The recipe captures role, prompts, permitted tools, model compatibility,
    and tests. When a future investigation needs this specialist, the runtime
    is spun up from the recipe — never a long-running worker.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        ...,
        description="AgentRecipe ID, e.g. 'agent.clinical-reviewer-v1'.",
        pattern=r"^agent\.[a-z0-9][a-z0-9-]{1,80}$",
    )
    schema_version: str = Field(default=AGENT_RECIPE_SCHEMA_VERSION)
    version: str = Field(..., description="Recipe version (semver preferred).")
    display_name: str = Field(..., min_length=1, max_length=200)
    description_long: str = Field(..., min_length=20)
    author: str | None = Field(default=None)

    role: str = Field(..., min_length=1, max_length=120, description="Specialist role label.")
    permitted_capability_ids: list[str] = Field(
        default_factory=list,
        description="SearchCapability IDs this agent is allowed to invoke.",
    )
    permitted_tools: list[str] = Field(
        default_factory=list,
        description="Tool names this agent is authorized to call.",
    )
    system_prompt: str = Field(..., min_length=10, description="System prompt template.")
    user_prompt_template: str | None = Field(default=None)
    output_template: dict[str, Any] | None = Field(default=None)
    model_compatibility: list[str] = Field(
        default_factory=list,
        description="Compatible model identifiers (provider:model).",
    )

    state: AgentState = Field(default=AgentState.ON_DEMAND)
    approved_by: str | None = Field(default=None)
    security_review: str | None = Field(default=None)

    retention: AgentRetentionPolicy = Field(default_factory=AgentRetentionPolicy)
    tests: AgentRecipeTests = Field(default_factory=AgentRecipeTests)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _validate(self) -> AgentRecipe:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")
        # Tested or maintained recipes must have evaluation evidence
        if self.state in (AgentState.TESTED, AgentState.MAINTAINED):
            if self.tests.last_evaluation_outcome is None:
                raise ValueError(
                    f"agent state {self.state.value} requires tests.last_evaluation_outcome"
                )
        # Maintained recipes require explicit security review
        if self.state == AgentState.MAINTAINED and not self.security_review:
            raise ValueError("maintained agent requires security_review")
        return self


__all__ = [
    "AGENT_RECIPE_SCHEMA_VERSION",
    "AgentRecipe",
    "AgentRetentionPolicy",
    "AgentRecipeTests",
]
