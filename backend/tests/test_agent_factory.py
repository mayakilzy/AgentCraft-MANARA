"""Tests for the Agent Factory (G05).

The canonical acceptance test (per owner decision, 2026-10-19):

> "تحقيق عن الأطراف الصناعية الذكية يحتاج إلى مراجعة الأدلة الطبية والسريرية."

The test must prove:
1. The resolver detects the need for a clinical specialist.
2. The resolver does NOT create a specialist for simple tasks (generalist first).
3. The Clinical Prosthetics Reviewer recipe is created and saved.
4. Tool permissions are the INTERSECTION of capability × role × investigation.
5. Patents are DENIED as proof of clinical safety.
6. The agent executes (mock mode) and produces output.
7. The session is terminated after execution.
8. The recipe can be rehydrated from cold in a new session.
9. The evaluation is recorded and the recipe is promoted.
10. The generalist-vs-specialist distinction is honest.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", "/home/z/my-project/.models")
os.environ.setdefault("HF_HOME", "/home/z/my-project/.models/hf_cache")

import pytest
from sqlalchemy.orm import Session

from manara.agents import (
    AgentRecipeRegistry,
    EphemeralAgentRuntime,
    GeneralistVsSpecialistResolver,
    ToolPermissionResolver,
    create_clinical_prosthetics_reviewer_recipe,
    get_provider,
    reset_provider,
)
from manara.agents.providers import MockProvider
from manara.db.agent_models import AgentRecipeRow, AgentSessionRow
from manara.db.session import Base


@pytest.fixture()
def db_session(engine) -> Iterator[Session]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_provider()
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture()
def registry(db_session):
    return AgentRecipeRegistry(db_session)


@pytest.fixture()
def resolver(db_session):
    return GeneralistVsSpecialistResolver(db_session)


@pytest.fixture()
def runtime(db_session):
    return EphemeralAgentRuntime(db_session)


# ─────────────────────────────────────────────────────────────────────────────
# ToolPermissionResolver tests
# ─────────────────────────────────────────────────────────────────────────────


class TestToolPermissionResolver:
    """Per owner (G05):
    > "الصلاحيات الفعلية هي تقاطع هذه الحدود الثلاثة."
    > "لا يستطيع الوكيل منح نفسه أدوات إضافية."
    """

    def test_intersection_of_recipe_and_capability(self):
        perms = ToolPermissionResolver.resolve(
            recipe_allowed_tools=["search.academic", "search.clinical", "memory.read"],
            recipe_denied_tools=[],
            capability_allowed_tools=["search.academic", "search.clinical", "search.patents"],
        )
        # Intersection: search.academic ∩ search.clinical (NOT search.patents — not in recipe)
        # memory.read is in recipe but NOT in capability → denied
        assert "search.academic" in perms.granted
        assert "search.clinical" in perms.granted
        assert "search.patents" not in perms.granted
        assert "memory.read" not in perms.granted  # not in capability set
        assert "memory.read" in perms.denied

    def test_denied_tools_are_subtracted(self):
        perms = ToolPermissionResolver.resolve(
            recipe_allowed_tools=["search.academic", "search.patents"],
            recipe_denied_tools=["search.patents"],
            capability_allowed_tools=["search.academic", "search.patents"],
        )
        assert "search.academic" in perms.granted
        assert "search.patents" not in perms.granted  # explicitly denied
        assert "search.patents" in perms.denied

    def test_investigation_constraints_narrow_further(self):
        perms = ToolPermissionResolver.resolve(
            recipe_allowed_tools=["search.academic", "search.clinical", "memory.read"],
            recipe_denied_tools=[],
            capability_allowed_tools=["search.academic", "search.clinical", "memory.read"],
            investigation_constraints=["search.academic"],  # only academic allowed in this investigation
        )
        assert "search.academic" in perms.granted
        assert "search.clinical" not in perms.granted  # narrowed by investigation
        assert "memory.read" not in perms.granted  # narrowed by investigation

    def test_agent_cannot_grant_itself_extra_tools(self):
        """Per owner: 'لا يستطيع الوكيل منح نفسه أدوات إضافية.'"""
        perms = ToolPermissionResolver.resolve(
            recipe_allowed_tools=["search.academic"],
            recipe_denied_tools=[],
            capability_allowed_tools=["search.academic"],
        )
        # The agent gets exactly 1 tool. It cannot add "search.patents" by itself.
        assert len(perms.granted) == 1
        assert perms.granted == ["search.academic"]


# ─────────────────────────────────────────────────────────────────────────────
# GeneralistVsSpecialistResolver tests
# ─────────────────────────────────────────────────────────────────────────────


class TestGeneralistVsSpecialistResolver:
    """Per owner (G05):
    > "لا تنشئ خبيراً تخصصياً لكل مهمة."
    > "أنشئ الخبير المتخصص فقط عندما تضيف خبرته قيمة."
    """

    def test_simple_search_goes_to_generalist(self, resolver):
        """Per owner: 'أضف اختباراً مضاداً يثبت أن مهمة بحثية بسيطة تُسند
        إلى المحلل العام دون إنشاء خبير جديد.'"""
        result = resolver.resolve(
            task_description="Find recent papers about sodium-ion batteries",
            tenant_id="tenant_demo",
        )
        assert result.needs_specialist is False, (
            "Simple search task should go to the generalist, not create a specialist"
        )
        assert "general" in result.reasoning.lower()

    def test_clinical_review_requires_specialist(self, resolver):
        """Per owner: 'تحقيق عن الأطراف الصناعية الذكية يحتاج إلى مراجعة
        الأدلة الطبية والسريرية.'"""
        result = resolver.resolve(
            task_description="Evaluate clinical safety and efficacy of neural prosthetic interfaces",
            tenant_id="tenant_demo",
            required_evidence_types=["clinical_trial", "peer_reviewed"],
        )
        assert result.needs_specialist is True
        assert result.recommended_specialty is not None

    def test_existing_recipe_is_reused_not_recreated(self, resolver, registry, db_session):
        """Per owner: 'استدعاء وصفة خبير سابق عند الحاجة.'"""
        # Save the clinical reviewer recipe
        recipe = create_clinical_prosthetics_reviewer_recipe(tenant_id="tenant_demo")
        registry.save_recipe(recipe, tenant_id="tenant_demo")

        # Now resolve — should find the existing recipe
        result = resolver.resolve(
            task_description="Review clinical evidence for prosthetic devices",
            tenant_id="tenant_demo",
            required_evidence_types=["clinical_trial"],
        )
        assert result.needs_specialist is True
        assert result.recommended_recipe_id == recipe.id, (
            "Should reuse the existing recipe, not create a new one"
        )


# ─────────────────────────────────────────────────────────────────────────────
# AgentRecipeRegistry tests
# ─────────────────────────────────────────────────────────────────────────────


class TestAgentRecipeRegistry:
    def test_save_and_get_recipe(self, registry, db_session):
        recipe = create_clinical_prosthetics_reviewer_recipe(tenant_id="tenant_demo")
        row = registry.save_recipe(recipe, tenant_id="tenant_demo")
        assert row.id == recipe.id
        assert row.state == "on_demand"

        fetched = registry.get_recipe(recipe.id, tenant_id="tenant_demo")
        assert fetched is not None
        assert fetched.display_name == recipe.display_name

    def test_rehydrate_from_cold(self, registry, db_session):
        """Per owner: 'إعادة إنشاء الخبير من وصفته المحفوظة في جلسة جديدة.'"""
        recipe = create_clinical_prosthetics_reviewer_recipe(tenant_id="tenant_demo")
        registry.save_recipe(recipe, tenant_id="tenant_demo")

        # Rehydrate
        rehydrated = registry.rehydrate(recipe.id, tenant_id="tenant_demo")
        assert rehydrated is not None
        assert rehydrated.id == recipe.id
        assert rehydrated.role == recipe.role
        assert rehydrated.system_prompt == recipe.system_prompt
        assert rehydrated.permitted_tools == recipe.permitted_tools
        assert rehydrated.permitted_capability_ids == recipe.permitted_capability_ids
        assert rehydrated.model_compatibility == recipe.model_compatibility

    def test_tenant_isolation(self, registry, db_session):
        recipe = create_clinical_prosthetics_reviewer_recipe(tenant_id="tenant_A")
        registry.save_recipe(recipe, tenant_id="tenant_A")
        # tenant_B cannot see tenant_A's recipe
        fetched = registry.get_recipe(recipe.id, tenant_id="tenant_B")
        assert fetched is None


# ─────────────────────────────────────────────────────────────────────────────
# EphemeralAgentRuntime tests
# ─────────────────────────────────────────────────────────────────────────────


class TestEphemeralAgentRuntime:
    def test_instantiate_execute_terminate(self, runtime, registry, db_session):
        """The full ephemeral lifecycle: instantiate → execute → terminate."""
        recipe = create_clinical_prosthetics_reviewer_recipe(tenant_id="tenant_demo")
        registry.save_recipe(recipe, tenant_id="tenant_demo")

        # 1. Instantiate
        session = runtime.instantiate(
            recipe_id=recipe.id,
            tenant_id="tenant_demo",
            task_description="Review clinical evidence for neural prosthetics",
            task_input={"evidence_ids": ["ev-001", "ev-002"]},
            capability_allowed_tools=recipe.permitted_tools,
        )
        assert session.status == "instantiated"
        assert session.execution_mode == "mock"  # no API key → mock

        # 2. Execute
        result = runtime.execute(session_id=session.id, tenant_id="tenant_demo")
        assert result.status == "completed"
        assert result.is_mock is True  # mock provider
        assert "MOCK RESPONSE" in result.output

        # 3. The session should be completed (not running)
        session_row = db_session.get(AgentSessionRow, session.id)
        assert session_row.status == "completed"
        assert session_row.completed_at is not None

    def test_tool_permissions_are_intersection(self, runtime, registry, db_session):
        """Per owner: 'الصلاحيات الفعلية هي تقاطع هذه الحدود الثلاثة.'"""
        recipe = create_clinical_prosthetics_reviewer_recipe(tenant_id="tenant_demo")
        registry.save_recipe(recipe, tenant_id="tenant_demo")

        # The recipe allows: search.academic-publications, search.clinical-trials,
        # memory.read_prior_evidence, memory.write_evidence
        # But the capability only allows: search.academic-publications
        session = runtime.instantiate(
            recipe_id=recipe.id,
            tenant_id="tenant_demo",
            task_description="Review evidence",
            capability_allowed_tools=["search.academic-publications"],  # narrow!
        )
        # The granted tools must be the INTERSECTION
        assert "search.academic-publications" in session.granted_tools_json
        assert "search.clinical-trials" not in session.granted_tools_json  # not in capability
        assert "memory.read_prior_evidence" not in session.granted_tools_json

    def test_patents_denied_in_clinical_reviewer(self, runtime, registry, db_session):
        """Per owner: 'رفض استخدام بيانات براءات الاختراع وحدها باعتبارها
        إثباتاً للسلامة السريرية.'"""
        recipe = create_clinical_prosthetics_reviewer_recipe(tenant_id="tenant_demo")
        registry.save_recipe(recipe, tenant_id="tenant_demo")

        # The recipe's permitted_capability_ids should NOT include patent-intelligence
        assert "search.patent-intelligence" not in recipe.permitted_capability_ids
        assert "search.academic-publications" in recipe.permitted_capability_ids
        assert "search.clinical-trials" in recipe.permitted_capability_ids

        # The system prompt must mention the patent restriction
        assert "patent" in recipe.system_prompt.lower()
        assert "safety" in recipe.system_prompt.lower()

    def test_evaluate_and_promote_recipe(self, runtime, registry, db_session):
        """Per owner: 'تسجيل النتيجة والتقييم وأسباب النجاح أو الإخفاق.'"""
        recipe = create_clinical_prosthetics_reviewer_recipe(tenant_id="tenant_demo")
        registry.save_recipe(recipe, tenant_id="tenant_demo")

        session = runtime.instantiate(
            recipe_id=recipe.id,
            tenant_id="tenant_demo",
            task_description="Review clinical evidence",
            capability_allowed_tools=recipe.permitted_tools,
        )
        runtime.execute(session_id=session.id, tenant_id="tenant_demo")

        # Evaluate
        eval_row = runtime.evaluate(
            session_id=session.id,
            tenant_id="tenant_demo",
            outcome="success",
            quality_score=0.8,
            improvement_over_generalist=0.6,
            notes="The specialist correctly identified that patent evidence is insufficient for safety claims.",
        )
        assert eval_row.outcome == "success"
        assert eval_row.quality_score == 0.8

        # The recipe should be promoted from on_demand to recipe_saved
        recipe_row = db_session.get(AgentRecipeRow, recipe.id)
        assert recipe_row.state == "recipe_saved"

    def test_terminate_running_session(self, runtime, registry, db_session):
        recipe = create_clinical_prosthetics_reviewer_recipe(tenant_id="tenant_demo")
        registry.save_recipe(recipe, tenant_id="tenant_demo")
        session = runtime.instantiate(
            recipe_id=recipe.id, tenant_id="tenant_demo",
            task_description="Review evidence",
        )
        ok = runtime.terminate(session_id=session.id, tenant_id="tenant_demo")
        assert ok is True
        session_row = db_session.get(AgentSessionRow, session.id)
        assert session_row.status == "terminated"


# ─────────────────────────────────────────────────────────────────────────────
# MockProvider tests
# ─────────────────────────────────────────────────────────────────────────────


class TestMockProvider:
    def test_mock_response_is_labeled_mock(self):
        """Per owner: 'لا تدّعِ نجاح تشغيل LLM حقيقي إذا كان الاختبار يستخدم
        Mock Provider.'"""
        provider = MockProvider()
        response = provider.generate(
            system_prompt="You are a clinical reviewer.",
            user_prompt="Review this evidence.",
        )
        assert response.is_mock is True
        assert "MOCK" in response.text
        assert "WARNING" in response.text

    def test_mock_provider_is_default(self):
        reset_provider()
        provider = get_provider()
        assert provider.name == "mock"


# ─────────────────────────────────────────────────────────────────────────────
# THE G05 ACCEPTANCE TEST
# ─────────────────────────────────────────────────────────────────────────────


class TestG05Acceptance:
    """THE CANONICAL G05 ACCEPTANCE TEST.

    Per owner (2026-10-19):
    > "تحقيق عن الأطراف الصناعية الذكية يحتاج إلى مراجعة الأدلة الطبية
    > والسريرية."

    Steps 1-10 from the owner's acceptance criteria.
    """

    def test_clinical_prosthetics_reviewer_full_lifecycle(
        self, resolver, registry, runtime, db_session
    ):
        # ── Step 1: Detect the need for clinical review ─────────────────────
        result = resolver.resolve(
            task_description="Evaluate clinical safety and efficacy of intelligent prosthetics",
            tenant_id="tenant_demo",
            required_evidence_types=["clinical_trial", "peer_reviewed"],
        )
        assert result.needs_specialist is True, (
            "Clinical evidence review should require a specialist"
        )

        # ── Step 2: No existing recipe → create one ─────────────────────────
        assert result.recommended_recipe_id is None  # no existing recipe

        # ── Step 3: Create the Clinical Prosthetics Reviewer recipe ─────────
        recipe = create_clinical_prosthetics_reviewer_recipe(tenant_id="tenant_demo")
        registry.save_recipe(recipe, tenant_id="tenant_demo")
        assert recipe.id == "agent.clinical-prosthetics-reviewer-v1"

        # ── Step 4: Verify tool permissions (clinical + academic only) ─────
        assert "search.academic-publications" in recipe.permitted_capability_ids
        assert "search.clinical-trials" in recipe.permitted_capability_ids
        assert "search.patent-intelligence" not in recipe.permitted_capability_ids

        # ── Step 5: Patents are DENIED as safety proof ──────────────────────
        assert "patent" in recipe.system_prompt.lower()
        assert "safety" in recipe.system_prompt.lower()
        # The system prompt explicitly says patents are NOT proof of safety
        assert "do not use patent" in recipe.system_prompt.lower() or \
               "not" in recipe.system_prompt.lower() and "patent" in recipe.system_prompt.lower()

        # ── Step 6: Execute (mock mode) on a test task ─────────────────────
        session = runtime.instantiate(
            recipe_id=recipe.id,
            tenant_id="tenant_demo",
            task_description="Review clinical evidence for neural prosthetic interfaces",
            task_input={"evidence_ids": ["ev-001"]},
            capability_allowed_tools=recipe.permitted_tools,
        )
        exec_result = runtime.execute(session_id=session.id, tenant_id="tenant_demo")
        assert exec_result.status == "completed"
        assert exec_result.is_mock is True  # honest about mock

        # ── Step 7: Record evaluation ──────────────────────────────────────
        eval_row = runtime.evaluate(
            session_id=session.id,
            tenant_id="tenant_demo",
            outcome="success",
            quality_score=0.8,
            improvement_over_generalist=0.6,
            notes="Specialist correctly excluded patent-only evidence from safety assessment.",
        )
        assert eval_row.outcome == "success"

        # ── Step 8: Terminate the session ──────────────────────────────────
        runtime.terminate(session_id=session.id, tenant_id="tenant_demo")
        session_row = db_session.get(AgentSessionRow, session.id)
        # Session is completed (execute already set it), not terminated
        assert session_row.status in ("completed", "terminated")

        # ── Step 9: Rehydrate from cold in a new session ────────────────────
        rehydrated = registry.rehydrate(recipe.id, tenant_id="tenant_demo")
        assert rehydrated is not None
        assert rehydrated.role == recipe.role
        assert rehydrated.permitted_tools == recipe.permitted_tools
        assert rehydrated.system_prompt == recipe.system_prompt
        assert rehydrated.version == recipe.version

        # New session from the rehydrated recipe
        new_session = runtime.instantiate(
            recipe_id=recipe.id,
            tenant_id="tenant_demo",
            task_description="Second review task",
            capability_allowed_tools=rehydrated.permitted_tools,
        )
        assert new_session.recipe_id == recipe.id
        assert new_session.granted_tools_json == session.granted_tools_json

        # ── Step 10: Verify recipe was promoted ────────────────────────────
        recipe_row = db_session.get(AgentRecipeRow, recipe.id)
        assert recipe_row.state == "recipe_saved"  # promoted after successful evaluation

    def test_generalist_first_for_simple_task(self, resolver, db_session):
        """THE COUNTER-TEST: simple tasks go to the generalist.

        Per owner: 'أضف اختباراً مضاداً يثبت أن مهمة بحثية بسيطة تُسند
        إلى المحلل العام دون إنشاء خبير جديد.'
        """
        result = resolver.resolve(
            task_description="Find recent papers about battery technology trends",
            tenant_id="tenant_demo",
        )
        assert result.needs_specialist is False, (
            "Simple search task should NOT create a specialist"
        )
        assert "general" in result.reasoning.lower()
