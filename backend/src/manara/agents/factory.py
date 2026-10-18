"""Agent Factory — on-demand specialist agents (G05).

Per ``03_INTELLIGENCE/03_AGENT_AND_MOLD_LIFECYCLE.md`` §Agent Factory:
> "Central orchestrator resolves whether general analyst sufficient.
> Generate expert blueprint on demand for narrowly defined tasks
> requiring specialization. Agents are ephemeral runtime workers with
> least privilege and a bounded task; after completion, persist *recipe
> and evaluation*, terminate runtime. Next request rehydrates recipe
> with compatibility and security checks. This is the 'phone book
> for shift workers'."

Per owner (G05):
> "العمل عند الطلب، لا رواتب أثناء النوم، وأرقام الهواتف محفوظة
> للوردية القادمة!"

The AgentFactory:
1. :class:`GeneralistVsSpecialistResolver` — decides if the generalist
   suffices or a specialist is needed. Per owner: "لا تنشئ خبيراً تخصصياً
   لكل مهمة."
2. :class:`AgentRecipeRegistry` — CRUD for agent recipes (the phone book).
   Recipes survive their sessions and can be rehydrated from cold.
3. :class:`ToolPermissionResolver` — computes the intersection of
   capability × role × investigation permissions. Per owner: "الصلاحيات
   الفعلية هي تقاطع هذه الحدود الثلاثة. لا يستطيع الوكيل منح نفسه
   أدوات إضافية."
4. :class:`EphemeralAgentRuntime` — instantiates a recipe, executes via
   the LLM provider (mock or live), terminates after completion. Records
   the session + evaluation.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from manara.agents.providers import LLMProvider, LLMResponse, get_provider
from manara.contracts import AgentRecipe, AgentRecipeTests, AgentRetentionPolicy
from manara.db.agent_models import AgentEvaluationRow, AgentRecipeRow, AgentSessionRow
from manara.lifecycle import AgentState

# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ResolutionResult:
    """Result of the generalist-vs-specialist resolver."""

    needs_specialist: bool
    reasoning: str
    recommended_recipe_id: str | None = None
    recommended_specialty: str | None = None
    # If needs_specialist=True but no existing recipe matches,
    # the factory will create a new one.


@dataclass
class ToolPermissions:
    """The actual permissions granted to an agent in a session.

    Per owner (G05):
    > "الصلاحيات الفعلية هي تقاطع هذه الحدود الثلاثة:
    > صلاحيات القدرة + سياق التحقيق + وصفة الوكيل."

    This is the INTERSECTION — never the union. The agent cannot
    grant itself additional tools.
    """

    granted: list[str] = field(default_factory=list)
    denied: list[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class ExecutionResult:
    """Result of an ephemeral agent execution."""

    session_id: str
    recipe_id: str
    status: str  # completed | failed | terminated
    output: str
    output_json: dict[str, Any]
    is_mock: bool
    provider_name: str
    model_name: str
    duration_ms: float
    error: str | None = None
    granted_tools: list[str] = field(default_factory=list)


@dataclass
class EvaluationResult:
    """Result of evaluating an agent session."""

    session_id: str
    outcome: str  # success | partial | failure | inconclusive
    quality_score: float | None
    improvement_over_generalist: float | None
    notes: str
    criteria_results: dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# ToolPermissionResolver
# ─────────────────────────────────────────────────────────────────────────────


class ToolPermissionResolver:
    """Computes the intersection of capability × role × investigation.

    Per owner (G05):
    > "صلاحيات كل قدرة تحدد ما يمكن للأداة فعله."
    > "سياق التحقيق يضيق الصلاحيات المسموحة."
    > "وصفة الوكيل تحدد الأدوات التي يحتاج إليها."
    > "الصلاحيات الفعلية هي تقاطع هذه الحدود الثلاثة."
    > "لا يستطيع الوكيل منح نفسه أدوات إضافية."
    """

    @staticmethod
    def resolve(
        *,
        recipe_allowed_tools: list[str],
        recipe_denied_tools: list[str],
        capability_allowed_tools: list[str],
        investigation_constraints: list[str] | None = None,
    ) -> ToolPermissions:
        """Compute the actual tool permissions.

        The granted tools are the INTERSECTION of:
        - recipe_allowed_tools (what the recipe says it needs)
        - capability_allowed_tools (what the capability permits)

        Then MINUS recipe_denied_tools (explicit denials).

        investigation_constraints can further narrow the set (e.g.
        "no outbound network in this investigation").
        """
        recipe_set = set(recipe_allowed_tools)
        capability_set = set(capability_allowed_tools)
        denied_set = set(recipe_denied_tools)

        # Intersection: recipe ∩ capability
        granted = recipe_set & capability_set

        # Minus denied
        granted = granted - denied_set

        # Apply investigation constraints (if any)
        if investigation_constraints:
            # investigation_constraints is a list of tool names that are
            # allowed in this investigation context. Anything NOT in this
            # list is denied.
            investigation_set = set(investigation_constraints)
            granted = granted & investigation_set

        # Denied = everything the recipe wanted but didn't get
        all_requested = recipe_set
        actually_denied = all_requested - granted

        return ToolPermissions(
            granted=sorted(granted),
            denied=sorted(actually_denied),
            reasoning=(
                f"Granted {len(granted)} tool(s) as the intersection of "
                f"recipe ({len(recipe_set)}) ∩ capability ({len(capability_set)}) "
                f"- denied ({len(denied_set)})"
                + (f" ∩ investigation constraints ({len(investigation_constraints)})" if investigation_constraints else "")
                + ". Agent cannot grant itself additional tools."
            ),
        )


# ─────────────────────────────────────────────────────────────────────────────
# GeneralistVsSpecialistResolver
# ─────────────────────────────────────────────────────────────────────────────


class GeneralistVsSpecialistResolver:
    """Decides if a generalist suffices or a specialist is needed.

    Per owner (G05):
    > "يجب أن يقارن Resolver بين:
    > - المحلل العام مع الأدوات المناسبة.
    > - وصفة خبير تخصصي موجودة.
    > - إنشاء وصفة تخصصية جديدة.
    > أنشئ الخبير المتخصص فقط عندما تضيف خبرته قيمة يمكن تفسيرها أو قياسها."

    Decision logic:
    1. If the task is a simple literature search → generalist suffices.
    2. If the task requires domain-specific evidence evaluation (e.g.
       clinical safety assessment, patent landscape analysis) → specialist.
    3. If a specialist is needed, search the recipe registry for an
       existing matching recipe first.
    4. Only if no existing recipe matches → create a new one.
    """

    # Task types that always go to the generalist
    GENERALIST_TASK_KEYWORDS = {
        "search", "find", "list", "summarize", "overview",
        "browse", "collect", "retrieve", "fetch",
    }

    # Task types that require a specialist
    SPECIALIST_TASK_KEYWORDS = {
        "evaluate", "assess", "review", "verify", "validate",
        "clinical", "safety", "efficacy", "regulatory", "diagnose",
        "forecast", "analyze trends", "patent landscape", "compare",
    }

    def __init__(self, db: Session) -> None:
        self.db = db

    def resolve(
        self,
        *,
        task_description: str,
        tenant_id: str,
        required_evidence_types: list[str] | None = None,
    ) -> ResolutionResult:
        """Decide whether a generalist or specialist is needed.

        Args:
            task_description: what the agent needs to do.
            tenant_id: tenant scoping.
            required_evidence_types: e.g. ["clinical_trial", "peer_reviewed"]
                — if these include specialized types, a specialist is likely needed.
        """
        task_lower = task_description.lower()
        task_tokens = set(task_lower.split())

        # Check for specialist keywords
        specialist_signals = task_tokens & self.SPECIALIST_TASK_KEYWORDS
        generalist_signals = task_tokens & self.GENERALIST_TASK_KEYWORDS

        # Check for specialized evidence requirements
        specialized_evidence = False
        if required_evidence_types:
            specialized_types = {"clinical_trial", "regulatory_filing", "patent_family"}
            if set(required_evidence_types) & specialized_types:
                specialized_evidence = True

        # Decision
        if specialist_signals or specialized_evidence:
            # A specialist is needed — search for an existing recipe
            specialty = self._infer_specialty(task_description, required_evidence_types)
            existing = self._find_existing_recipe(
                specialty=specialty, tenant_id=tenant_id
            )
            if existing is not None:
                return ResolutionResult(
                    needs_specialist=True,
                    reasoning=(
                        f"Task requires specialized expertise (signals: {specialist_signals}). "
                        f"Found existing recipe '{existing.id}' for specialty '{specialty}'. "
                        f"Reusing saved recipe (no new specialist created)."
                    ),
                    recommended_recipe_id=existing.id,
                    recommended_specialty=specialty,
                )
            else:
                return ResolutionResult(
                    needs_specialist=True,
                    reasoning=(
                        f"Task requires specialized expertise (signals: {specialist_signals}). "
                        f"No existing recipe for specialty '{specialty}'. "
                        f"A new specialist recipe will be created."
                    ),
                    recommended_recipe_id=None,
                    recommended_specialty=specialty,
                )
        else:
            # Generalist suffices
            return ResolutionResult(
                needs_specialist=False,
                reasoning=(
                    f"Task appears to be a general research task (signals: "
                    f"{generalist_signals}). No specialized evidence requirements. "
                    f"The general analyst with appropriate tools is sufficient. "
                    f"No specialist recipe created."
                ),
                recommended_recipe_id=None,
                recommended_specialty=None,
            )

    def _infer_specialty(
        self, task_description: str, required_evidence_types: list[str] | None
    ) -> str:
        """Infer the specialty label from the task description."""
        task_lower = task_description.lower()
        if "clinical" in task_lower or "medical" in task_lower or "prosthe" in task_lower:
            return "clinical_reviewer"
        if "patent" in task_lower:
            return "patent_analyst"
        if "regulatory" in task_lower or "approval" in task_lower:
            return "regulatory_specialist"
        if "forecast" in task_lower or "predict" in task_lower:
            return "forecasting_analyst"
        if required_evidence_types and "clinical_trial" in required_evidence_types:
            return "clinical_reviewer"
        return "general_specialist"

    def _find_existing_recipe(
        self, *, specialty: str, tenant_id: str
    ) -> AgentRecipeRow | None:
        """Search for an existing recipe matching the specialty.

        The resolver infers a specialty (e.g. "clinical_reviewer") from
        the task description. The recipe registry stores recipes with
        specialty = recipe.role (e.g. "clinical_prosthetics_reviewer").
        We search for ANY recipe whose specialty CONTAINS the inferred
        specialty prefix (e.g. "clinical" matches "clinical_prosthetics_reviewer").
        """
        stmt = select(AgentRecipeRow).where(
            AgentRecipeRow.tenant_id == tenant_id,
            AgentRecipeRow.state.in_(["on_demand", "recipe_saved", "tested", "maintained"]),
        )
        all_recipes = list(self.db.execute(stmt).scalars())
        for recipe in all_recipes:
            # Match if the inferred specialty is a prefix of the stored specialty
            # (e.g. "clinical_reviewer" matches "clinical_prosthetics_reviewer")
            if recipe.specialty.startswith(specialty.split("_")[0]):
                return recipe
        return None


# ─────────────────────────────────────────────────────────────────────────────
# AgentRecipeRegistry — the phone book
# ─────────────────────────────────────────────────────────────────────────────


class AgentRecipeRegistry:
    """CRUD + rehydration for agent recipes.

    Per owner (G05):
    > "الوصفة ليست مجرد Prompt. إنها تعريف كامل للخبير: دوره، مهاراته،
    > أدواته المسموحة، نوع الأدلة التي يستطيع تقييمها، حدوده، واختبارات
    > كفاءته."
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def save_recipe(
        self,
        recipe: AgentRecipe,
        *,
        tenant_id: str,
    ) -> AgentRecipeRow:
        """Save a recipe to the registry (the phone book)."""
        existing = self.db.get(AgentRecipeRow, recipe.id)
        if existing is not None and existing.tenant_id == tenant_id:
            # Update in place
            self._update_row(existing, recipe, tenant_id=tenant_id)
            self.db.commit()
            return existing

        row = self._recipe_to_row(recipe, tenant_id=tenant_id)
        self.db.add(row)
        self.db.commit()
        return row

    def get_recipe(
        self, recipe_id: str, *, tenant_id: str
    ) -> AgentRecipeRow | None:
        """Fetch a recipe by ID (tenant-scoped)."""
        row = self.db.get(AgentRecipeRow, recipe_id)
        if row is None or row.tenant_id != tenant_id:
            return None
        return row

    def list_recipes(
        self,
        *,
        tenant_id: str,
        specialty: str | None = None,
        state: str | None = None,
        limit: int = 50,
    ) -> list[AgentRecipeRow]:
        """List recipes with optional filters."""
        stmt = select(AgentRecipeRow).where(AgentRecipeRow.tenant_id == tenant_id)
        if specialty:
            stmt = stmt.where(AgentRecipeRow.specialty == specialty)
        if state:
            stmt = stmt.where(AgentRecipeRow.state == state)
        stmt = stmt.order_by(AgentRecipeRow.updated_at.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars())

    def rehydrate(
        self, recipe_id: str, *, tenant_id: str
    ) -> AgentRecipe | None:
        """Rehydrate a recipe from its stored payload.

        Per owner (G05):
        > "إعادة إنشاء الخبير من وصفته المحفوظة في جلسة جديدة."
        > "التحقق من تطابق الدور والمهارات والأدوات والإصدار بعد إعادة
        > الإنشاء، دون اشتراط تطابق النص المولد حرفياً."
        """
        row = self.get_recipe(recipe_id, tenant_id=tenant_id)
        if row is None:
            return None
        return AgentRecipe.model_validate(row.payload)

    def _recipe_to_row(
        self, recipe: AgentRecipe, *, tenant_id: str
    ) -> AgentRecipeRow:
        """Convert a Pydantic AgentRecipe to an ORM row."""
        return AgentRecipeRow(
            id=recipe.id,
            tenant_id=tenant_id,
            display_name=recipe.display_name,
            description_long=recipe.description_long,
            version=recipe.version,
            schema_version=recipe.schema_version,
            state=recipe.state.value,
            role=recipe.role,
            specialty=recipe.role,  # Use role as specialty (simplified)
            keywords_en_json=[],
            keywords_ar_json=[],
            synonyms_json=[],
            positive_examples_json=[],
            negative_examples_json=[],
            required_skills_json=[],
            required_capability_ids_json=recipe.permitted_capability_ids,
            optional_capability_ids_json=[],
            allowed_tools_json=recipe.permitted_tools,
            denied_tools_json=[],
            input_contract_json={},
            output_contract_json=recipe.output_template or {},
            evidence_requirements_json={},
            verification_criteria_json=[],
            evaluation_criteria_json=[],
            provider_requirements_json={"compatible_models": recipe.model_compatibility},
            memory_access_scope_json={},
            system_prompt=recipe.system_prompt,
            user_prompt_template=recipe.user_prompt_template,
            payload=recipe.model_dump(mode="json"),
        )

    def _update_row(
        self, row: AgentRecipeRow, recipe: AgentRecipe, *, tenant_id: str
    ) -> None:
        """Update an existing row with new recipe data."""
        row.display_name = recipe.display_name
        row.description_long = recipe.description_long
        row.version = recipe.version
        row.state = recipe.state.value
        row.role = recipe.role
        row.specialty = recipe.role
        row.required_capability_ids_json = recipe.permitted_capability_ids
        row.allowed_tools_json = recipe.permitted_tools
        row.output_contract_json = recipe.output_template or {}
        row.provider_requirements_json = {"compatible_models": recipe.model_compatibility}
        row.system_prompt = recipe.system_prompt
        row.user_prompt_template = recipe.user_prompt_template
        row.payload = recipe.model_dump(mode="json")


# ─────────────────────────────────────────────────────────────────────────────
# EphemeralAgentRuntime — instantiate, execute, terminate
# ─────────────────────────────────────────────────────────────────────────────


class EphemeralAgentRuntime:
    """Runs an agent recipe as an ephemeral session.

    Per spec: "Agents are ephemeral runtime workers with least privilege
    and a bounded task; after completion, persist *recipe and evaluation*,
    terminate runtime."

    The runtime:
    1. Instantiates the recipe (creates an AgentSessionRow).
    2. Resolves tool permissions (intersection of 3 sets).
    3. Calls the LLM provider (mock or live).
    4. Records the output.
    5. Terminates (sets status=completed, records duration).
    6. The session row persists for the audit log.
    """

    def __init__(
        self,
        db: Session,
        *,
        provider: LLMProvider | None = None,
    ) -> None:
        self.db = db
        self.provider = provider or get_provider()
        self.registry = AgentRecipeRegistry(db)

    def instantiate(
        self,
        *,
        recipe_id: str,
        tenant_id: str,
        investigation_id: str | None = None,
        mold_id: str | None = None,
        task_description: str,
        task_input: dict[str, Any] | None = None,
        capability_allowed_tools: list[str] | None = None,
        investigation_constraints: list[str] | None = None,
    ) -> AgentSessionRow:
        """Instantiate a recipe as an ephemeral session.

        Per owner (G05):
        > "تحديد الأدوات والصلاحيات وفق الدور والتحقيق."
        """
        recipe_row = self.registry.get_recipe(recipe_id, tenant_id=tenant_id)
        if recipe_row is None:
            raise ValueError(f"recipe {recipe_id} not found for tenant {tenant_id}")

        # Resolve tool permissions (intersection of 3 sets)
        perms = ToolPermissionResolver.resolve(
            recipe_allowed_tools=recipe_row.allowed_tools_json,
            recipe_denied_tools=recipe_row.denied_tools_json,
            capability_allowed_tools=capability_allowed_tools or recipe_row.allowed_tools_json,
            investigation_constraints=investigation_constraints,
        )

        session_id = f"session-{secrets.token_hex(8)}"
        session = AgentSessionRow(
            id=session_id,
            tenant_id=tenant_id,
            recipe_id=recipe_id,
            investigation_id=investigation_id,
            mold_id=mold_id,
            status="instantiated",
            execution_mode="mock" if self.provider.name == "mock" else "live_llm",
            task_description=task_description,
            task_input_json=task_input or {},
            task_output_json={},
            output_summary="",
            granted_tools_json=perms.granted,
            provider_name=self.provider.name,
            model_name=getattr(self.provider, "model", "unknown"),
        )
        self.db.add(session)
        self.db.commit()
        return session

    def execute(
        self,
        *,
        session_id: str,
        tenant_id: str,
    ) -> ExecutionResult:
        """Execute the agent session (call the LLM provider).

        Per owner (G05):
        > "لا تدّعِ نجاح تشغيل LLM حقيقي إذا كان الاختبار يستخدم Mock Provider."
        """
        session = self.db.get(AgentSessionRow, session_id)
        if session is None or session.tenant_id != tenant_id:
            raise ValueError(f"session {session_id} not found for tenant {tenant_id}")

        recipe_row = self.registry.get_recipe(session.recipe_id, tenant_id=tenant_id)
        if recipe_row is None:
            raise ValueError(f"recipe {session.recipe_id} not found")

        # Update status to running
        session.status = "running"
        self.db.commit()

        try:
            # Build the user prompt from the task description + input
            user_prompt = session.task_description
            if session.task_input_json:
                import json

                user_prompt += "\n\nInput data:\n" + json.dumps(
                    session.task_input_json, indent=2, ensure_ascii=False
                )

            # Call the LLM provider
            response: LLMResponse = self.provider.generate(
                system_prompt=recipe_row.system_prompt,
                user_prompt=user_prompt,
            )

            # Record output
            session.task_output_json = {
                "text": response.text,
                "is_mock": response.is_mock,
                "tokens_used": response.tokens_used,
            }
            session.output_summary = response.text[:500]
            session.status = "completed"
            session.completed_at = datetime.now(UTC)
            session.duration_ms = int(response.duration_ms)
            self.db.commit()

            return ExecutionResult(
                session_id=session_id,
                recipe_id=session.recipe_id,
                status="completed",
                output=response.text,
                output_json=session.task_output_json,
                is_mock=response.is_mock,
                provider_name=response.provider,
                model_name=response.model,
                duration_ms=response.duration_ms,
                granted_tools=session.granted_tools_json,
            )

        except Exception as e:
            session.status = "failed"
            session.error = str(e)
            session.completed_at = datetime.now(UTC)
            self.db.commit()
            return ExecutionResult(
                session_id=session_id,
                recipe_id=session.recipe_id,
                status="failed",
                output="",
                output_json={},
                is_mock=self.provider.name == "mock",
                provider_name=self.provider.name,
                model_name=getattr(self.provider, "model", "unknown"),
                duration_ms=0,
                error=str(e),
                granted_tools=session.granted_tools_json,
            )

    def terminate(
        self,
        *,
        session_id: str,
        tenant_id: str,
    ) -> bool:
        """Terminate the agent session (set status=terminated if still running).

        Per owner (G05):
        > "إيقاف جلسة التشغيل."
        """
        session = self.db.get(AgentSessionRow, session_id)
        if session is None or session.tenant_id != tenant_id:
            return False
        if session.status in ("running", "instantiated"):
            session.status = "terminated"
            session.completed_at = datetime.now(UTC)
            self.db.commit()
        return True

    def evaluate(
        self,
        *,
        session_id: str,
        tenant_id: str,
        outcome: str,
        quality_score: float | None = None,
        improvement_over_generalist: float | None = None,
        notes: str = "",
        criteria_results: dict[str, Any] | None = None,
        evaluator: str = "system",
    ) -> AgentEvaluationRow:
        """Record an evaluation for the session.

        Per spec: "persist *recipe and evaluation*" — the evaluation
        tells future investigations whether the specialist added value.
        """
        session = self.db.get(AgentSessionRow, session_id)
        if session is None or session.tenant_id != tenant_id:
            raise ValueError(f"session {session_id} not found for tenant {tenant_id}")

        eval_row = AgentEvaluationRow(
            session_id=session_id,
            recipe_id=session.recipe_id,
            tenant_id=tenant_id,
            outcome=outcome,
            quality_score=quality_score,
            improvement_over_generalist=improvement_over_generalist,
            notes=notes,
            criteria_results_json=criteria_results or {},
            evaluator=evaluator,
        )
        self.db.add(eval_row)

        # If the evaluation is positive and the recipe is still on_demand,
        # promote it to recipe_saved (it has proven useful).
        if outcome in ("success", "partial") and quality_score and quality_score >= 0.6:
            recipe_row = self.db.get(AgentRecipeRow, session.recipe_id)
            if recipe_row and recipe_row.state == "on_demand":
                recipe_row.state = "recipe_saved"
                recipe = AgentRecipe.model_validate(recipe_row.payload)
                recipe.state = AgentState.RECIPE_SAVED
                recipe.tests.last_evaluation_outcome = outcome
                recipe.tests.last_evaluation_at = datetime.now(UTC)
                recipe_row.payload = recipe.model_dump(mode="json")

        self.db.commit()
        return eval_row


# ─────────────────────────────────────────────────────────────────────────────
# Specialist blueprint generator
# ─────────────────────────────────────────────────────────────────────────────


def create_clinical_prosthetics_reviewer_recipe(
    *, tenant_id: str
) -> AgentRecipe:
    """Create the Clinical Prosthetics Reviewer specialist recipe.

    This is the canonical G05 acceptance test recipe. It includes:
    - Evidence requirements that DENY patent-as-safety-proof
    - Tool permissions scoped to clinical + academic capabilities
    - System prompt that enforces the clinical evaluation boundaries
    """
    return AgentRecipe(
        id="agent.clinical-prosthetics-reviewer-v1",
        version="0.1.0",
        display_name="Clinical Prosthetics Reviewer (on-demand)",
        description_long=(
            "Specialist agent for reviewing clinical and biomedical evidence "
            "related to prosthetics and neural interfaces. Evaluates trial "
            "data, regulatory submissions, and peer-reviewed publications. "
            "Explicitly DENIES using patent filings as proof of clinical "
            "safety or efficacy — patents indicate inventive direction, "
            "not regulatory approval."
        ),
        author="manara-g05",
        role="clinical_prosthetics_reviewer",
        permitted_capability_ids=[
            "search.academic-publications",
            "search.clinical-trials",
        ],
        permitted_tools=[
            "search.academic-publications",
            "search.clinical-trials",
            "memory.read_prior_evidence",
            "memory.write_evidence",
        ],
        system_prompt=(
            "You are a Clinical Prosthetics Reviewer — a specialist agent "
            "in MANARA's on-demand agent factory. Your role is to evaluate "
            "clinical and biomedical evidence about prosthetics, neural "
            "interfaces, and medical devices.\n\n"
            "STRICT RULES:\n"
            "1. You may ONLY use evidence from academic publications and "
            "clinical trials. Do NOT use patent filings as proof of "
            "clinical safety or efficacy.\n"
            "2. A patent filing indicates inventive direction, NOT "
            "regulatory approval. Never conclude a device is safe based "
            "solely on patent data.\n"
            "3. Distinguish between lab results, clinical trial results, "
            "and regulatory approvals — they are different levels of evidence.\n"
            "4. If evidence is insufficient, say so explicitly. Do not "
            "fabricate conclusions.\n"
            "5. You are an ephemeral agent — your session terminates after "
            "this task. Your recipe and evaluation will be saved for future use."
        ),
        user_prompt_template=(
            "Investigation: {investigation_topic}\n"
            "Task: {task_description}\n"
            "Available evidence: {evidence_summary}\n"
            "Please evaluate the evidence and provide your clinical assessment."
        ),
        output_template={
            "type": "object",
            "properties": {
                "assessment": {"type": "string"},
                "evidence_quality": {"type": "string"},
                "gaps_identified": {"type": "array"},
                "recommendation": {"type": "string"},
            },
        },
        model_compatibility=["zai:glm-4.6", "openai:gpt-4o"],
        state=AgentState.ON_DEMAND,
        retention=AgentRetentionPolicy(
            repeat_demand_score=0.8,
            economic_value_score=0.7,
            improvement_over_generalist=0.6,
            rarity_score=0.7,
            maintenance_burden_score=0.3,
        ),
        tests=AgentRecipeTests(),
    )


def create_general_analyst_recipe(*, tenant_id: str) -> AgentRecipe:
    """Create the General Analyst recipe (always available, never retires)."""
    return AgentRecipe(
        id="agent.general-analyst-v1",
        version="0.1.0",
        display_name="General Analyst (default)",
        description_long=(
            "The default general-purpose research analyst. Handles literature "
            "searches, evidence collection, summarization, and trend analysis. "
            "No specialization — uses whatever capabilities the mold provides."
        ),
        author="manara-g05",
        role="general_analyst",
        permitted_capability_ids=[],  # Uses whatever the mold provides
        permitted_tools=[
            "search.academic-publications",
            "search.patent-intelligence",
            "search.clinical-trials",
            "search.energy-ev-datasets",
            "search.agricultural-statistics",
            "search.geopolitical-events",
            "search.waste-recycling-statistics",
            "search.github-activity",
            "memory.read_prior_evidence",
            "memory.write_evidence",
        ],
        system_prompt=(
            "You are a General Research Analyst in MANARA's on-demand agent "
            "factory. You handle general research tasks: literature searches, "
            "evidence collection, summarization, and trend analysis.\n\n"
            "RULES:\n"
            "1. Use the evidence available to you. Do not fabricate.\n"
            "2. If a task requires specialized clinical, regulatory, or "
            "patent expertise beyond your scope, flag it for the resolver.\n"
            "3. You are ephemeral — your session terminates after this task."
        ),
        user_prompt_template=None,
        output_template={},
        model_compatibility=["zai:glm-4.6", "openai:gpt-4o", "mock"],
        state=AgentState.MAINTAINED,  # Generalist is always maintained
        retention=AgentRetentionPolicy(
            repeat_demand_score=1.0,
            economic_value_score=0.5,
            improvement_over_generalist=0.0,  # IS the generalist
            rarity_score=0.0,
            maintenance_burden_score=0.2,
        ),
        tests=AgentRecipeTests(),
    )


__all__ = [
    "AgentRecipeRegistry",
    "EphemeralAgentRuntime",
    "EvaluationResult",
    "ExecutionResult",
    "GeneralistVsSpecialistResolver",
    "ResolutionResult",
    "ToolPermissionResolver",
    "ToolPermissions",
    "create_clinical_prosthetics_reviewer_recipe",
    "create_general_analyst_recipe",
]
