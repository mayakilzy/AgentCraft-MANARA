"""ORM models for the Agent Factory (G05).

Per ``03_INTELLIGENCE/03_AGENT_AND_MOLD_LIFECYCLE.md``:
> "Agents are ephemeral runtime workers with least privilege and a
> bounded task; after completion, persist *recipe and evaluation*,
> terminate runtime."

Three tables:
* ``agent_recipes``    — stored specialist recipes (the G00 AgentRecipe
  contract materialized). Rehydratable for future investigations.
* ``agent_sessions``   — ephemeral execution records. Each session is
  one instantiation of a recipe; the runtime is terminated after the
  task completes, but the session record persists for the audit log.
* ``agent_evaluations`` — per-session evaluation records. Track outcome,
  quality metrics, and learning notes for future recipe promotion.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
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


class AgentRecipeRow(Base):
    """A stored specialist agent recipe.

    Mirrors the G00 ``AgentRecipe`` contract. Recipes survive their
    investigations — they can be rehydrated for future similar questions
    without re-creating the specialist from scratch.

    Lifecycle (per owner decision):
    > "الوكيل المؤقت ينتهي بعد المهمة، وتبقى وصفته قابلة للاستدعاء."

    States: on_demand → recipe_saved → tested → maintained → retired
    """

    __tablename__ = "agent_recipes"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description_long: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(60), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False, default="1.0.0")
    state: Mapped[str] = mapped_column(String(40), nullable=False, default="on_demand", index=True)
    # on_demand | recipe_saved | tested | maintained | retired

    # Role and specialty
    role: Mapped[str] = mapped_column(String(120), nullable=False)
    specialty: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    # e.g. "clinical_prosthetics_reviewer", "patent_analyst", "general_analyst"

    # Keywords (multilingual)
    keywords_en_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    keywords_ar_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    synonyms_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Use cases
    positive_examples_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    negative_examples_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Required skills and capabilities
    required_skills_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    required_capability_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    optional_capability_ids_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Tool permissions
    allowed_tools_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    denied_tools_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Input/Output contracts
    input_contract_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    output_contract_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Evidence requirements
    evidence_requirements_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    # e.g. {"requires_peer_reviewed": true, "requires_clinical_trial": true,
    #       "denies_patent_as_safety_proof": true}

    # Verification and evaluation criteria
    verification_criteria_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    evaluation_criteria_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Provider requirements
    provider_requirements_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    # e.g. {"min_context_window": 32000, "multilingual": true,
    #       "compatible_models": ["zai:glm-4.6", "openai:gpt-4o"]}

    # Memory access scope
    memory_access_scope_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    # e.g. {"can_read_prior_investigations": true, "can_write_evidence": false,
    #       "tenant_scoped": true}

    # System prompt template
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Promotion metadata
    promoted_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    promotion_rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")

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
        UniqueConstraint("id", "tenant_id", name="uq_agent_recipes_id_tenant"),
        Index("ix_agent_recipes_tenant_state", "tenant_id", "state"),
        Index("ix_agent_recipes_tenant_specialty", "tenant_id", "specialty"),
    )


class AgentSessionRow(Base):
    """An ephemeral agent execution session.

    Per spec: "Agents are ephemeral runtime workers with least privilege
    and a bounded task; after completion, persist *recipe and evaluation*,
    terminate runtime."

    Each row is ONE instantiation of a recipe. The runtime is terminated
    after the task completes, but the session record persists for the
    audit log. This is the "phone book entry" — the record that a specialist
    was called, did the job, and went home.
    """

    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    recipe_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("agent_recipes.id"), nullable=False, index=True
    )
    investigation_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    mold_id: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Execution state
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="instantiated", index=True)
    # instantiated → running → completed | failed | terminated
    execution_mode: Mapped[str] = mapped_column(String(40), nullable=False, default="mock")
    # mock | live_llm

    # The task
    task_description: Mapped[str] = mapped_column(Text, nullable=False)
    task_input_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # The output
    task_output_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    output_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Tool permissions actually granted (intersection of capability × role × investigation)
    granted_tools_json: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Provider used
    provider_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float] = mapped_column(Integer, nullable=False, default=0)

    # Error (if failed)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    __table_args__ = (
        Index("ix_agent_sessions_tenant_status", "tenant_id", "status"),
    )


class AgentEvaluationRow(Base):
    """Per-session evaluation record.

    Per spec: "persist *recipe and evaluation*" — the evaluation tells
    future investigations whether the specialist actually added value.
    """

    __tablename__ = "agent_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("agent_sessions.id"), nullable=False, index=True
    )
    recipe_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("agent_recipes.id"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)

    # Evaluation outcome
    outcome: Mapped[str] = mapped_column(String(40), nullable=False)
    # success | partial | failure | inconclusive
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0..1.0

    # Did the specialist add value over the generalist?
    improvement_over_generalist: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 0.0 = no improvement, 1.0 = major improvement

    # Learning notes (for future recipe promotion decisions)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # The criteria that were evaluated
    criteria_results_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    evaluator: Mapped[str] = mapped_column(String(120), nullable=False, default="system")

    __table_args__ = (
        Index("ix_agent_evaluations_tenant_recipe", "tenant_id", "recipe_id"),
    )


__all__ = [
    "AgentEvaluationRow",
    "AgentRecipeRow",
    "AgentSessionRow",
]
