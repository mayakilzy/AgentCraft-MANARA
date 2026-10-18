"""Tests for the Mold Factory (G04).

The canonical acceptance test (per owner decision, 2026-10-19):

> "أريد دراسة استشرافية عن مستقبل إعادة تدوير النفايات خلال السنوات
> العشر القادمة"

The test must prove:
1. No pre-registered recycling mold exists (unknown domain).
2. The system decomposes the query into research needs.
3. Existing capabilities are reused where they match (e.g. waste-recycling-
   statistics card from G01 maps to environmental_data need).
4. Gaps are detected honestly (no fabricated capabilities).
5. A temporary mold is composed and persisted (state=temporary).
6. The mold's recipe can be rehydrated for a later similar question.
7. The investigation workflow state machine enforces transitions.
8. Blockers are visible when pre-conditions fail.
9. No silent core rewrites — G00/G01/G02/G03 contracts unchanged.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", "/home/z/my-project/.models")
os.environ.setdefault("HF_HOME", "/home/z/my-project/.models/hf_cache")

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from manara.contracts import Mold
from manara.db.models import InvestigationRow
from manara.db.mold_models import (
    GapAnalysisRow,
    MoldRecipeRow,
    MoldReuseRow,
)
from manara.db.session import Base
from manara.lifecycle import MoldState
from manara.mold_factory import (
    InvestigationWorkflowService,
    MoldArchitect,
    UnknownDomainDetector,
)
from manara.registry import SEED_CAPABILITIES, CapabilityRegistry

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def db_session(engine) -> Iterator[Session]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture()
def seeded_registry(db_session):
    """Seed the 8 capability cards from G01 (so the architect can find them)."""
    reg = CapabilityRegistry(db_session)
    for cap in SEED_CAPABILITIES:
        reg.create_capability(cap, tenant_id="tenant_demo")
    return reg


@pytest.fixture()
def architect(db_session):
    return MoldArchitect(db_session)


@pytest.fixture()
def detector(db_session):
    return UnknownDomainDetector(db_session)


@pytest.fixture()
def workflow_service(db_session):
    return InvestigationWorkflowService(db_session)


def _make_investigation(db, inv_id: str, tenant_id: str, topic: str) -> InvestigationRow:
    row = InvestigationRow(
        id=inv_id, tenant_id=tenant_id, user_id="test-user", state="received",
        topic=topic,
        payload={"id": inv_id, "tenant_id": tenant_id, "user_id": "test-user",
                 "scope": {"topic": topic}, "state": "received"},
    )
    db.add(row)
    db.commit()
    return row


# ─────────────────────────────────────────────────────────────────────────────
# Unknown-domain detector tests
# ─────────────────────────────────────────────────────────────────────────────


class TestUnknownDomainDetector:
    def test_no_existing_molds_is_unknown(self, detector, db_session):
        """Empty mold registry → any query is unknown."""
        result = detector.detect(
            "Future of waste recycling", tenant_id="tenant_demo"
        )
        assert result.is_unknown is True
        assert "No mold recipe found" in result.detection_reasoning

    def test_existing_mold_with_overlap_is_known(self, detector, db_session, architect):
        """After composing a mold and promoting it to reusable, the next
        query with the same vocabulary should be detected as known."""
        # First call: compose a temporary mold
        result1 = architect.compose_mold(
            "Future of waste recycling technologies",
            tenant_id="tenant_demo",
        )
        assert result1.is_unknown_domain is True

        # Promote the mold to reusable so the detector finds it
        mold_row = db_session.get(MoldRecipeRow, result1.mold_recipe_id)
        mold_row.state = "reusable"
        mold = Mold.model_validate(mold_row.payload)
        mold.state = MoldState.REUSABLE
        mold_row.payload = mold.model_dump(mode="json")
        db_session.commit()

        # Second call: detect — should find the now-reusable mold
        result2 = detector.detect(
            "Future of waste recycling technologies",
            tenant_id="tenant_demo",
        )
        assert result2.is_unknown is False
        assert len(result2.matched_molds) >= 1

    def test_tenant_isolation_in_detection(self, detector, db_session, architect):
        """Tenant B's detector must not see tenant A's molds."""
        architect.compose_mold(
            "Future of waste recycling",
            tenant_id="tenant_A",
        )
        # Promote tenant_A's mold to reusable
        from sqlalchemy import select as sel
        rows = list(db_session.execute(
            sel(MoldRecipeRow).where(MoldRecipeRow.tenant_id == "tenant_A")
        ).scalars())
        for r in rows:
            r.state = "reusable"
        db_session.commit()

        result = detector.detect(
            "Future of waste recycling", tenant_id="tenant_B"
        )
        assert result.is_unknown is True
        assert "No mold recipe found" in result.detection_reasoning


# ─────────────────────────────────────────────────────────────────────────────
# MoldArchitect tests
# ─────────────────────────────────────────────────────────────────────────────


class TestMoldArchitect:
    def test_compose_creates_temporary_mold(self, architect, seeded_registry, db_session):
        result = architect.compose_mold(
            "Future of waste recycling technologies",
            tenant_id="tenant_demo",
        )
        assert result.is_unknown_domain is True
        assert result.mold_recipe_id.startswith("mold.")
        # The mold should be persisted with state=temporary
        mold_row = db_session.get(MoldRecipeRow, result.mold_recipe_id)
        assert mold_row is not None
        assert mold_row.state == "temporary"
        assert mold_row.origin == "temporary_fresh"

    def test_compose_records_gaps_honestly(self, architect, seeded_registry, db_session):
        """Per owner: "لا تتحايل عليها ببطاقة افتراضية تدّعي أنها محرك حقيقي."

        The recycling query will trigger needs that may not be fully covered
        by the seed cards. The architect must record gaps explicitly rather
        than fabricating capabilities.
        """
        result = architect.compose_mold(
            "Future of waste recycling technologies in the next ten years",
            tenant_id="tenant_demo",
        )
        # Gaps are recorded as GapAnalysisRow entries
        gap_rows = list(db_session.execute(
            select(GapAnalysisRow).where(
                GapAnalysisRow.mold_id == result.mold_recipe_id
            )
        ).scalars())
        # The number of gaps depends on which needs were detected and which
        # capabilities exist. We assert that:
        # 1. The gaps list in the result matches the DB rows.
        assert len(gap_rows) == len(result.gaps)
        # 2. Each gap is honestly labeled (no fabricated capability_id)
        for gap in result.gaps:
            assert gap.foundry_resolution in (
                "foundry_invoked", "foundry_no_candidate", "unresolved"
            )
            assert "fabricated" not in gap.resolution_notes.lower()
            assert "no fabricated capability" in gap.resolution_notes.lower() or \
                   "deferred to G05" in gap.resolution_notes.lower() or \
                   "no foundry candidate" in gap.resolution_notes.lower()

    def test_compose_reuses_existing_capabilities(self, architect, seeded_registry, db_session):
        """The architect must reuse existing seed capabilities (e.g.
        search.waste-recycling-statistics) rather than fabricating new ones.
        """
        result = architect.compose_mold(
            "Future of waste recycling technologies",
            tenant_id="tenant_demo",
        )
        # The mold's capability_ids must be a subset of the seed capabilities
        seed_ids = {c.id for c in SEED_CAPABILITIES}
        mold_cap_ids = set(result.mold.composition.capability_ids)
        assert mold_cap_ids.issubset(seed_ids), (
            f"Mold has non-seed capability_ids: {mold_cap_ids - seed_ids}"
        )
        # If any capability was selected, it must be from the seeds
        for cov in result.coverage:
            if cov.selected_capability_id is not None:
                assert cov.selected_capability_id in seed_ids

    def test_compose_does_not_fabricate_capabilities(self, architect, seeded_registry, db_session):
        """THE KEY G04 ACCEPTANCE TEST.

        Per owner: "إذا لم تسمح قدرات G02 الحالية ببناء موصل جديد تلقائياً،
        سجّل هذه الفجوة صراحةً. لا تتحايل عليها ببطاقة افتراضية تدّعي
        أنها محرك حقيقي."
        """
        result = architect.compose_mold(
            "Future of waste recycling technologies",
            tenant_id="tenant_demo",
        )
        # Every capability_id in the mold MUST exist in the registry
        from manara.db.registry_models import CapabilityRow
        for cap_id in result.mold.composition.capability_ids:
            row = db_session.get(CapabilityRow, cap_id)
            assert row is not None, (
                f"Fabricated capability detected: {cap_id} not in registry"
            )

    def test_compose_persists_recipe_for_reuse(self, architect, seeded_registry, db_session):
        """Per owner: "انتهاء تنفيذ القالب المؤقت لا يعني حذف وصفته أو
        نتائج تقييمه."

        The mold recipe must survive and be rehydratable.
        """
        # First investigation: compose a temporary mold
        result1 = architect.compose_mold(
            "Future of waste recycling technologies",
            tenant_id="tenant_demo",
            investigation_id="inv-A",
        )
        mold_id = result1.mold_recipe_id
        assert result1.mold.state == MoldState.TEMPORARY

        # Fetch the persisted recipe
        row = db_session.get(MoldRecipeRow, mold_id)
        assert row is not None
        assert row.state == "temporary"

        # Rehydrate: load the Pydantic contract from the payload
        rehydrated = Mold.model_validate(row.payload)
        assert rehydrated.id == result1.mold.id
        assert rehydrated.scope.domain == result1.mold.scope.domain
        assert rehydrated.composition.capability_ids == result1.mold.composition.capability_ids


# ─────────────────────────────────────────────────────────────────────────────
# Investigation workflow state machine tests
# ─────────────────────────────────────────────────────────────────────────────


class TestInvestigationWorkflow:
    """Per owner: "نعم، على مستوى الخدمة وAPI، لكن وفق الشروط الفعلية
    لكل مرحلة، مع حالات واضحة للنقص والتعذر."
    """

    def test_create_workflow_initial_state_received(self, workflow_service, db_session):
        _make_investigation(db_session, "inv-A", "tenant_demo", "Recycling")
        row = workflow_service.create_workflow(
            investigation_id="inv-A", tenant_id="tenant_demo"
        )
        assert row.state == "received"
        assert len(row.transitions_json) == 1
        assert row.transitions_json[0]["to"] == "received"

    def test_illegal_transition_blocked(self, workflow_service, db_session):
        """received → archived is illegal (must go through the full chain)."""
        _make_investigation(db_session, "inv-A", "tenant_demo", "Recycling")
        workflow_service.create_workflow(
            investigation_id="inv-A", tenant_id="tenant_demo"
        )
        result = workflow_service.transition(
            investigation_id="inv-A", tenant_id="tenant_demo",
            target_state="archived", actor="test",
        )
        assert result.transitioned is False
        assert "illegal transition" in (result.blocker or "").lower()

    def test_scoped_requires_topic(self, workflow_service, db_session):
        """received → scoped requires a non-empty topic."""
        _make_investigation(db_session, "inv-A", "tenant_demo", "")
        workflow_service.create_workflow(
            investigation_id="inv-A", tenant_id="tenant_demo"
        )
        result = workflow_service.transition(
            investigation_id="inv-A", tenant_id="tenant_demo",
            target_state="scoped", actor="test",
        )
        assert result.transitioned is False
        assert "no topic" in (result.blocker or "").lower()

    def test_coverage_checked_requires_mold_detection(self, workflow_service, db_session):
        """scoped → coverage_checked requires mold detection to have run."""
        _make_investigation(db_session, "inv-A", "tenant_demo", "Recycling")
        workflow_service.create_workflow(
            investigation_id="inv-A", tenant_id="tenant_demo"
        )
        # Transition to scoped first
        workflow_service.transition(
            investigation_id="inv-A", tenant_id="tenant_demo",
            target_state="scoped", actor="test", rationale="scoped",
        )
        # Now try coverage_checked without running the architect (no mold_id,
        # no gap analyses)
        result = workflow_service.transition(
            investigation_id="inv-A", tenant_id="tenant_demo",
            target_state="coverage_checked", actor="test",
        )
        assert result.transitioned is False
        assert "mold detection" in (result.blocker or "").lower()

    def test_coverage_checked_passes_with_mold_id(self, workflow_service, db_session, architect, seeded_registry):
        """coverage_checked passes when a mold_id is provided (no gap analysis required)."""
        _make_investigation(db_session, "inv-A2", "tenant_demo", "Recycling")
        workflow_service.create_workflow(
            investigation_id="inv-A2", tenant_id="tenant_demo"
        )
        workflow_service.transition(
            investigation_id="inv-A2", tenant_id="tenant_demo",
            target_state="scoped", actor="test", rationale="scoped",
        )
        # Compose a mold (sets mold_id)
        compose = architect.compose_mold(
            "Future of waste recycling", tenant_id="tenant_demo",
            investigation_id="inv-A2",
        )
        # Pass the mold_id → coverage_checked should pass
        result = workflow_service.transition(
            investigation_id="inv-A2", tenant_id="tenant_demo",
            target_state="coverage_checked", actor="test",
            mold_id=compose.mold_recipe_id,
        )
        assert result.transitioned is True, f"coverage_checked blocked: {result.blocker}"

    def test_mold_ready_requires_mold_id(self, workflow_service, db_session, architect, seeded_registry):
        """coverage_checked → mold_ready requires a mold_id."""
        _make_investigation(db_session, "inv-A", "tenant_demo", "Recycling")
        workflow_service.create_workflow(
            investigation_id="inv-A", tenant_id="tenant_demo"
        )
        workflow_service.transition(
            investigation_id="inv-A", tenant_id="tenant_demo",
            target_state="scoped", actor="test",
        )
        # Run the architect to create a gap analysis (so coverage_checked can pass)
        result = architect.compose_mold(
            "Future of waste recycling", tenant_id="tenant_demo",
            investigation_id="inv-A",
        )
        workflow_service.transition(
            investigation_id="inv-A", tenant_id="tenant_demo",
            target_state="coverage_checked", actor="test",
            mold_id=result.mold_recipe_id,
        )
        # mold_ready inherits the mold_id from the coverage_checked transition
        good_result = workflow_service.transition(
            investigation_id="inv-A", tenant_id="tenant_demo",
            target_state="mold_ready", actor="test",
        )
        assert good_result.transitioned is True

    def test_mold_ready_blocked_without_any_mold_id(self, workflow_service, db_session):
        """coverage_checked → mold_ready fails if NO mold_id was ever set."""
        _make_investigation(db_session, "inv-C", "tenant_demo", "Recycling")
        workflow_service.create_workflow(
            investigation_id="inv-C", tenant_id="tenant_demo"
        )
        # Manually create gap analyses so coverage_checked passes without mold_id
        from manara.db.mold_models import GapAnalysisRow
        gap = GapAnalysisRow(
            tenant_id="tenant_demo",
            mold_id="fake-mold-for-test",
            investigation_id="inv-C",
            need="environmental_data",
            need_label="Environmental data",
            status="unresolved",
            resolution_notes="Test gap.",
        )
        db_session.add(gap)
        db_session.commit()
        workflow_service.transition(
            investigation_id="inv-C", tenant_id="tenant_demo",
            target_state="scoped", actor="test",
        )
        workflow_service.transition(
            investigation_id="inv-C", tenant_id="tenant_demo",
            target_state="coverage_checked", actor="test",
        )
        # mold_ready WITHOUT mold_id → blocked
        bad_result = workflow_service.transition(
            investigation_id="inv-C", tenant_id="tenant_demo",
            target_state="mold_ready", actor="test",
        )
        assert bad_result.transitioned is False
        assert "mold_id" in (bad_result.blocker or "").lower()

    def test_evidencing_requires_evidence_or_gap(self, workflow_service, db_session):
        """acquiring → evidencing requires evidence OR an unresolved gap.

        Per owner: "التحقيق الذي يفتقر إلى الأدلة الكافية يجب أن يستطيع
        إصدار تقرير عن فجوة المعرفة، بدلاً من اختراع نتيجة."
        """
        _make_investigation(db_session, "inv-A", "tenant_demo", "Recycling")
        workflow_service.create_workflow(
            investigation_id="inv-A", tenant_id="tenant_demo"
        )
        # Skip ahead to normalizing (this test focuses on evidencing)
        # Need to pass mold_id for coverage_checked and mold_ready transitions.
        for state in ["scoped", "coverage_checked", "mold_ready", "acquiring", "normalizing"]:
            workflow_service.transition(
                investigation_id="inv-A", tenant_id="tenant_demo",
                target_state=state, actor="test",
                mold_id="some-mold-id" if state in ("coverage_checked", "mold_ready") else None,
            )
        # Try evidencing with no evidence AND no gap recorded
        result = workflow_service.transition(
            investigation_id="inv-A", tenant_id="tenant_demo",
            target_state="evidencing", actor="test",
        )
        assert result.transitioned is False
        assert "no evidence" in (result.blocker or "").lower() and \
               "no unresolved gap" in (result.blocker or "").lower()

    def test_full_workflow_chain_succeeds_with_mold_and_gap(
        self, workflow_service, db_session, architect, seeded_registry
    ):
        """The full chain: received → scoped → coverage_checked → mold_ready →
        acquiring → normalizing → evidencing → ... → archived.

        This test runs the full recycling investigation workflow, recording
        an unresolved gap (because no real connector exists for the recycling
        need) so evidencing can proceed.
        """
        _make_investigation(
            db_session, "inv-A", "tenant_demo",
            "Future of waste recycling in the next ten years",
        )
        workflow_service.create_workflow(
            investigation_id="inv-A", tenant_id="tenant_demo"
        )

        # received → scoped (topic is non-empty)
        r = workflow_service.transition(
            investigation_id="inv-A", tenant_id="tenant_demo",
            target_state="scoped", actor="test", rationale="topic OK",
        )
        assert r.transitioned is True, f"scoped blocked: {r.blocker}"

        # Run the architect (creates gap analyses → coverage_checked can pass)
        compose = architect.compose_mold(
            "Future of waste recycling in the next ten years",
            tenant_id="tenant_demo", investigation_id="inv-A",
        )
        # The mold should have at least one gap (recycling needs aren't fully
        # covered by the seed catalog).
        # Actually, search.waste-recycling-statistics maps to environmental_data,
        # so coverage may exist. We tolerate both outcomes.

        # scoped → coverage_checked (pass mold_id)
        r = workflow_service.transition(
            investigation_id="inv-A", tenant_id="tenant_demo",
            target_state="coverage_checked", actor="test",
            mold_id=compose.mold_recipe_id,
        )
        assert r.transitioned is True, f"coverage_checked blocked: {r.blocker}"

        # coverage_checked → mold_ready
        r = workflow_service.transition(
            investigation_id="inv-A", tenant_id="tenant_demo",
            target_state="mold_ready", actor="test",
            mold_id=compose.mold_recipe_id,
        )
        assert r.transitioned is True, f"mold_ready blocked: {r.blocker}"

        # mold_ready → acquiring
        r = workflow_service.transition(
            investigation_id="inv-A", tenant_id="tenant_demo",
            target_state="acquiring", actor="test",
        )
        assert r.transitioned is True, f"acquiring blocked: {r.blocker}"

        # acquiring → normalizing
        r = workflow_service.transition(
            investigation_id="inv-A", tenant_id="tenant_demo",
            target_state="normalizing", actor="test",
        )
        assert r.transitioned is True, f"normalizing blocked: {r.blocker}"

        # normalizing → evidencing (requires evidence OR gap)
        # If compose.gaps is non-empty, the gap analysis rows satisfy the precondition.
        # If compose.gaps is empty, we need evidence — but this test has none,
        # so the transition may fail unless we add an unresolved gap manually.
        from manara.db.mold_models import GapAnalysisRow
        if not compose.gaps:
            # Add a synthetic gap so the test can proceed
            gap = GapAnalysisRow(
                tenant_id="tenant_demo",
                mold_id=compose.mold_recipe_id,
                investigation_id="inv-A",
                need="environmental_data",
                need_label="Environmental data",
                status="unresolved",
                resolution_notes="No real connector available for this need.",
            )
            db_session.add(gap)
            db_session.commit()

        r = workflow_service.transition(
            investigation_id="inv-A", tenant_id="tenant_demo",
            target_state="evidencing", actor="test",
        )
        assert r.transitioned is True, f"evidencing blocked: {r.blocker}"

        # evidencing → forecasting_or_scenarios → drafting → verification → deliverable_ready
        for state in [
            "forecasting_or_scenarios", "drafting", "verification",
            "deliverable_ready", "archived",
        ]:
            r = workflow_service.transition(
                investigation_id="inv-A", tenant_id="tenant_demo",
                target_state=state, actor="test",
            )
            assert r.transitioned is True, f"{state} blocked: {r.blocker}"

    def test_audit_trail_records_all_transitions(self, workflow_service, db_session):
        """The transitions_json list must contain one entry per transition."""
        _make_investigation(db_session, "inv-A", "tenant_demo", "Recycling")
        workflow_service.create_workflow(
            investigation_id="inv-A", tenant_id="tenant_demo"
        )
        workflow_service.transition(
            investigation_id="inv-A", tenant_id="tenant_demo",
            target_state="scoped", actor="test", rationale="topic OK",
        )
        row = workflow_service.get_workflow(
            investigation_id="inv-A", tenant_id="tenant_demo"
        )
        assert row is not None
        # 1 entry for create (received) + 1 entry for scoped
        assert len(row.transitions_json) == 2
        assert row.transitions_json[1]["from"] == "received"
        assert row.transitions_json[1]["to"] == "scoped"
        assert row.transitions_json[1]["actor"] == "test"


# ─────────────────────────────────────────────────────────────────────────────
# THE G04 ACCEPTANCE TEST — recycling query
# ─────────────────────────────────────────────────────────────────────────────


class TestG04Acceptance:
    """THE CANONICAL G04 ACCEPTANCE TEST.

    Per owner decision (2026-10-19):
    > "أريد دراسة استشرافية عن مستقبل إعادة تدوير النفايات خلال السنوات
    > العشر القادمة"

    The test must prove:
    1. No pre-registered recycling mold exists (unknown domain).
    2. The system decomposes the query into research needs.
    3. Existing capabilities are reused where they match.
    4. Gaps are detected honestly (no fabricated capabilities).
    5. A temporary mold is composed and persisted.
    6. The mold's recipe can be rehydrated.
    7. The investigation workflow can advance with the mold.
    8. No silent core rewrites — G00/G01/G02/G03 contracts unchanged.
    """

    def test_recycling_unknown_domain_first_attempt(
        self, architect, detector, seeded_registry, workflow_service, db_session
    ):
        # ── Step 1: Verify no pre-registered recycling mold ─────────────────
        detection = detector.detect(
            "Future of waste recycling technologies in the next ten years",
            tenant_id="tenant_demo",
        )
        assert detection.is_unknown is True, (
            "Expected unknown domain (no pre-registered recycling mold), "
            f"but detector found: {[m.display_name for m in detection.matched_molds]}"
        )

        # ── Step 2: Create investigation + workflow ─────────────────────────
        _make_investigation(
            db_session, "inv-recycling", "tenant_demo",
            "Future of waste recycling technologies in the next ten years",
        )
        workflow_service.create_workflow(
            investigation_id="inv-recycling", tenant_id="tenant_demo"
        )

        # ── Step 3: Compose the temporary mold ─────────────────────────────
        result = architect.compose_mold(
            "Future of waste recycling technologies in the next ten years",
            tenant_id="tenant_demo",
            investigation_id="inv-recycling",
        )
        assert result.is_unknown_domain is True
        assert result.mold.state == MoldState.TEMPORARY
        assert result.mold_recipe_id.startswith("mold.")

        # ── Step 4: Decomposition happened ──────────────────────────────────
        assert len(result.detected_needs) > 0, (
            "Decomposer should have detected at least one research need"
        )

        # ── Step 5: Reused capabilities are from the seed registry ─────────
        seed_ids = {c.id for c in SEED_CAPABILITIES}
        for cov in result.coverage:
            if cov.selected_capability_id is not None:
                assert cov.selected_capability_id in seed_ids, (
                    f"Fabricated capability: {cov.selected_capability_id}"
                )

        # ── Step 6: Gaps are recorded honestly ─────────────────────────────
        # Verify gap rows in the DB match the result.gaps list
        gap_rows = list(db_session.execute(
            select(GapAnalysisRow).where(
                GapAnalysisRow.mold_id == result.mold_recipe_id
            )
        ).scalars())
        assert len(gap_rows) == len(result.gaps)
        for gap in result.gaps:
            assert gap.foundry_resolution in (
                "foundry_invoked", "foundry_no_candidate", "unresolved"
            )
            # No fabricated capability_id
            assert "no fabricated capability" in gap.resolution_notes.lower() or \
                   "deferred to G05" in gap.resolution_notes.lower() or \
                   "no foundry candidate" in gap.resolution_notes.lower(), (
                f"Gap resolution notes don't honestly declare the limitation: "
                f"{gap.resolution_notes}"
            )

        # ── Step 7: Mold recipe persisted and rehydratable ──────────────────
        mold_row = db_session.get(MoldRecipeRow, result.mold_recipe_id)
        assert mold_row is not None
        assert mold_row.state == "temporary"
        rehydrated = Mold.model_validate(mold_row.payload)
        assert rehydrated.id == result.mold.id
        assert rehydrated.scope.domain == result.mold.scope.domain

        # ── Step 8: Workflow can advance with the mold ──────────────────────
        # received → scoped
        r = workflow_service.transition(
            investigation_id="inv-recycling", tenant_id="tenant_demo",
            target_state="scoped", actor="test", rationale="topic OK",
        )
        assert r.transitioned is True

        # scoped → coverage_checked (pass mold_id so the precondition passes)
        r = workflow_service.transition(
            investigation_id="inv-recycling", tenant_id="tenant_demo",
            target_state="coverage_checked", actor="test",
            mold_id=result.mold_recipe_id,
        )
        assert r.transitioned is True

        # coverage_checked → mold_ready (pass the mold_id)
        r = workflow_service.transition(
            investigation_id="inv-recycling", tenant_id="tenant_demo",
            target_state="mold_ready", actor="test",
            mold_id=result.mold_recipe_id,
        )
        assert r.transitioned is True

        # ── Step 9: No silent core rewrites ─────────────────────────────────
        # The G00 Mold contract's schema_version must still be 1.0.0
        assert result.mold.schema_version == "1.0.0"
        # The G01 seed capabilities are unchanged
        from manara.db.registry_models import CapabilityRow
        for cap_id in seed_ids:
            row = db_session.get(CapabilityRow, cap_id)
            assert row is not None, f"seed capability {cap_id} missing"
            assert row.schema_version == "1.0.0"

    def test_mold_reuse_for_similar_question(self, architect, seeded_registry, db_session):
        """A second similar question should be able to reuse the first mold's recipe.

        Per spec: "تمكين إعادة تشغيل الوصفة في تحقيق لاحق."
        """
        # First investigation: compose a temporary mold
        result1 = architect.compose_mold(
            "Future of waste recycling technologies",
            tenant_id="tenant_demo", investigation_id="inv-A",
        )

        # Promote to reusable so the detector finds it
        mold_row = db_session.get(MoldRecipeRow, result1.mold_recipe_id)
        mold_row.state = "reusable"
        mold = Mold.model_validate(mold_row.payload)
        mold.state = MoldState.REUSABLE
        mold_row.payload = mold.model_dump(mode="json")
        db_session.commit()

        # Second investigation: similar question
        result2 = architect.compose_mold(
            "Future of waste recycling in Europe",
            tenant_id="tenant_demo", investigation_id="inv-B",
        )
        # Should reuse the first mold
        assert result2.is_unknown_domain is False, (
            "Second similar question should reuse the first mold"
        )
        assert result2.mold_recipe_id == result1.mold_recipe_id

        # A MoldReuseRow should record the reuse
        reuse_rows = list(db_session.execute(
            select(MoldReuseRow).where(
                MoldReuseRow.investigation_id == "inv-B"
            )
        ).scalars())
        assert len(reuse_rows) == 1
        assert reuse_rows[0].mold_id == result1.mold_recipe_id

    def test_tenant_isolation_in_mold_composition(self, architect, seeded_registry, db_session):
        """Tenant B's architect must not see tenant A's molds or capabilities."""
        # Tenant A composes a mold
        architect.compose_mold(
            "Future of waste recycling", tenant_id="tenant_A",
        )
        # Tenant B composes a mold for the same query
        # Tenant B has NO seeded capabilities, so the architect should
        # detect all needs as gaps
        result_b = architect.compose_mold(
            "Future of waste recycling", tenant_id="tenant_B",
        )
        # The mold is composed (with gaps) but reuses no capabilities
        # from tenant A
        assert len(result_b.mold.composition.capability_ids) == 0, (
            "Tenant B should have no capabilities to reuse"
        )
        # All detected needs become gaps
        assert len(result_b.gaps) == len(result_b.detected_needs)
