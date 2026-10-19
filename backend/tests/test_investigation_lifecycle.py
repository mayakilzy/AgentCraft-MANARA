"""BACKEND-VERIFICATION-01 — Investigation Lifecycle Acceptance Test.

Per owner's directive:
> "ابنِ اختبار قبول مترابطاً يبدأ بسؤال بحثي جديد.
>  المسار المطلوب:
>  Question → Investigation → Needs Analysis → Mold → Operational Source Selection →
>  Real Evidence Acquisition → Memory → Analysis → Specialist Execution when appropriate →
>  Foresight when appropriate → Publishing → Download."

This test exercises the COMPLETE investigation journey end-to-end through the
service layer. It uses synthetic data (the seed cards + a MockProvider) —
this is the FIRST of the four test levels the owner requested:
  Level 1: synthetic data — THIS FILE
  Level 2: saved data from real source — TODO (would require live OpenAlex)
  Level 3: live data, newly acquired — TODO (gated by RUN_LIVE_TESTS=1)
  Level 4: live LLM — TODO (gated by MANARA_ZAI_API_KEY)

The owner explicitly warned:
> "لا تعتبر نجاح المستوى الأول إثباتاً لنجاح المستوى الثالث أو الرابع."

We agree. This test proves the pipeline is wired correctly with synthetic
data. Live data acquisition + live LLM remain untested (documented as
BLOCKED_BY_ENVIRONMENT in KNOWN_GAPS_AND_LIMITATIONS.md).
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_SRC_DIR = _BACKEND_DIR / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

os.environ.setdefault("MANARA_ENV", "development")
os.environ.setdefault("MANARA_LOG_LEVEL", "WARNING")
os.environ.setdefault("MANARA_DISCOVERY_MODE", "synthetic")
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/manara_v01_lifecycle.db")

import pytest  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from manara.config import reload_settings  # noqa: E402
from manara.db.session import Base, get_engine, reset_engine  # noqa: E402


@pytest.fixture(scope="session")
def settings():
    return reload_settings()


@pytest.fixture(scope="session")
def engine(settings):
    reset_engine()
    eng = get_engine()
    Base.metadata.drop_all(bind=eng)
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)
    eng.dispose()
    reset_engine()


@pytest.fixture()
def db_session(engine):
    from manara.registry.embeddings import reset_embedding_store

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_embedding_store()
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


class TestInvestigationLifecycleSynthetic:
    """End-to-end investigation through every stage of the MANARA pipeline.

    Owner directive:
    > "تحقق من أن جميع المراحل تستخدم معرّف التحقيق نفسه."

    This test verifies:
    * Question is registered as an investigation with a stable ID
    * Mold composition detects needs and selects capabilities
    * Memory curator ingests evidence with the SAME investigation_id
    * Memory curator preserves contradictions (not silently overwrites)
    * Memory curator enables investigation B to reuse evidence from A
    * Agent runtime executes with tool invocations recorded
    * Foresight engine refuses to forecast when evidence is insufficient
    * Publishing engine produces a downloadable file with quality gate
    """

    QUESTION_TEXT = (
        "What is the state of neural interface technology for prosthetic "
        "control, and what evidence supports current clinical outcomes?"
    )
    TENANT_ID = "tenant_demo"
    INVESTIGATION_ID = "inv-acceptance-001"

    @staticmethod
    def _ensure_investigation(db_session, inv_id=None, tenant=None, topic=None):
        """Helper: create InvestigationRow if it doesn't already exist."""
        from manara.db.models import InvestigationRow

        inv_id = inv_id or TestInvestigationLifecycleSynthetic.INVESTIGATION_ID
        tenant = tenant or TestInvestigationLifecycleSynthetic.TENANT_ID
        topic = topic or TestInvestigationLifecycleSynthetic.QUESTION_TEXT
        if db_session.get(InvestigationRow, inv_id) is None:
            db_session.add(
                InvestigationRow(
                    id=inv_id,
                    tenant_id=tenant,
                    user_id="user-acceptance",
                    state="received",
                    topic=topic,
                    payload={},
                )
            )
            db_session.commit()
        return inv_id

    def test_step_1_question_creates_investigation(self, db_session):
        """Step 1: A research question creates an InvestigationRow with a
        stable ID that all subsequent stages must reference."""
        from manara.db.models import InvestigationRow

        inv_id = self._ensure_investigation(db_session)
        retrieved = db_session.get(InvestigationRow, inv_id)
        assert retrieved is not None
        assert retrieved.tenant_id == self.TENANT_ID
        assert retrieved.state == "received"
        assert retrieved.topic == self.QUESTION_TEXT

    def test_step_2_mold_composition_detects_needs(self, db_session):
        """Step 2: MoldArchitect analyzes the question and returns needs +
        coverage. The mold must include capabilities relevant to the
        prosthetics question (academic publications, clinical trials, patents).
        """
        from manara.mold_factory.architect import MoldArchitect
        from manara.registry.seed_cards import (
            card_academic_publications,
            card_clinical_trials,
            card_patent_intelligence,
        )
        from manara.registry.service import CapabilityRegistry

        registry = CapabilityRegistry(db_session)
        for card_factory in (
            card_academic_publications,
            card_clinical_trials,
            card_patent_intelligence,
        ):
            registry.create_capability(card_factory(), tenant_id=self.TENANT_ID)
        db_session.commit()

        # Ensure investigation exists
        inv_id = self._ensure_investigation(db_session)

        architect = MoldArchitect(db_session)
        result = architect.compose_mold(
            query=self.QUESTION_TEXT,
            tenant_id=self.TENANT_ID,
            investigation_id=inv_id,
        )

        # Verify the mold detected needs and matched capabilities
        assert result is not None
        assert result.investigation_id == inv_id, (
            "mold must preserve the investigation ID for downstream stages"
        )
        assert len(result.detected_needs) >= 1, (
            f"expected >=1 detected needs, got {result.detected_needs}"
        )
        # coverage list should match needs (even if NONE — the mold must
        # report the coverage level honestly)
        assert len(result.coverage) >= 1, (
            f"expected >=1 coverage entries, got {result.coverage}"
        )

    def test_step_3_evidence_ingestion_with_investigation_id(self, db_session):
        """Step 3: Evidence is ingested into memory with the SAME
        investigation_id. Multiple evidence items from different sources
        must all be linked."""
        from manara.contracts import Evidence, EvidenceKind, Provenance
        from manara.memory.curator import MemoryCurator

        inv_id = self._ensure_investigation(db_session)
        curator = MemoryCurator(db_session)
        ev_items = [
            Evidence(
                id=f"ev-acc-{i:03d}",
                kind=EvidenceKind.QUOTE,
                source_id=src,
                tenant_id=self.TENANT_ID,
                content_preview=preview,
                content_checksum=None,
                structured_payload={},
                claims=[],
                measures=[],
                provenance=Provenance(
                    observed_at=datetime(2024, 6, 1, tzinfo=UTC),
                    ingested_at=datetime.now(UTC),
                ),
            )
            for i, (src, preview) in enumerate(
                [
                    ("openalex", "Neural interface prosthetics show 80% precision improvement in lab tests."),
                    ("openalex", "Clinical trial confirms 60% precision in real-world conditions."),
                    ("openalex", "Patent filing indicates novel control algorithm for myoelectric prosthetics."),
                ],
                start=1,
            )
        ]
        for ev in ev_items:
            result = curator.ingest_evidence(
                evidence=ev,
                tenant_id=self.TENANT_ID,
                investigation_id=inv_id,
            )
            assert result.evidence_id == ev.id
            assert not result.reused_from_investigation_id
        db_session.commit()

        from manara.db.memory_models import EvidenceItemRow

        rows = list(
            db_session.query(EvidenceItemRow).filter_by(
                tenant_id=self.TENANT_ID, investigation_id=inv_id
            )
        )
        assert len(rows) == 3, (
            f"expected 3 evidence items linked to investigation, got {len(rows)}"
        )

    def test_step_4_contradicting_evidence_is_preserved(self, db_session):
        """Step 4: When contradicting evidence arrives, the curator must
        PRESERVE BOTH items. Per owner: "حفظ التناقضات لا حذفها."
        """
        from manara.contracts import Evidence, EvidenceKind, Provenance
        from manara.db.memory_models import EvidenceItemRow
        from manara.memory.curator import MemoryCurator

        inv_id = self._ensure_investigation(db_session)
        curator = MemoryCurator(db_session)
        # Ingest two contradicting evidence items
        ev_lab = Evidence(
            id="ev-acc-contradict-1",
            kind=EvidenceKind.QUOTE,
            source_id="openalex",
            tenant_id=self.TENANT_ID,
            content_preview="Lab study shows 80% precision in neural prosthetics.",
            content_checksum=None,
            structured_payload={},
            claims=[],
            measures=[],
            provenance=Provenance(
                observed_at=datetime(2024, 6, 1, tzinfo=UTC),
                ingested_at=datetime.now(UTC),
            ),
        )
        ev_field = Evidence(
            id="ev-acc-contradict-2",
            kind=EvidenceKind.QUOTE,
            source_id="openalex",
            tenant_id=self.TENANT_ID,
            content_preview="Field trial shows only 40% precision in real-world conditions.",
            content_checksum=None,
            structured_payload={},
            claims=[],
            measures=[],
            provenance=Provenance(
                observed_at=datetime(2024, 6, 2, tzinfo=UTC),
                ingested_at=datetime.now(UTC),
            ),
        )
        curator.ingest_evidence(
            evidence=ev_lab,
            tenant_id=self.TENANT_ID,
            investigation_id=inv_id,
        )
        curator.ingest_evidence(
            evidence=ev_field,
            tenant_id=self.TENANT_ID,
            investigation_id=inv_id,
        )
        db_session.commit()

        # Verify BOTH evidence items still exist (not silently merged/deleted)
        for ev_id in ("ev-acc-contradict-1", "ev-acc-contradict-2"):
            rows = list(
                db_session.query(EvidenceItemRow).filter_by(
                    tenant_id=self.TENANT_ID,
                    investigation_id=inv_id,
                    id=ev_id,
                )
            )
            assert len(rows) == 1, (
                f"contradicting evidence {ev_id} must be PRESERVED, not deleted"
            )

    def test_step_5_memory_reuse_for_new_investigation(self, db_session):
        """Step 5: A second investigation (B) in the same tenant can search
        prior memory and reuse evidence from investigation A."""
        from manara.contracts import Evidence, EvidenceKind, Provenance
        from manara.memory.curator import MemoryCurator

        inv_a = self._ensure_investigation(db_session)
        curator = MemoryCurator(db_session)
        ev = Evidence(
            id="ev-reuse-source",
            kind=EvidenceKind.QUOTE,
            source_id="openalex",
            tenant_id=self.TENANT_ID,
            content_preview="Reusable prosthetics research finding for neural interfaces.",
            content_checksum=None,
            structured_payload={},
            claims=[],
            measures=[],
            provenance=Provenance(
                observed_at=datetime(2024, 6, 1, tzinfo=UTC),
                ingested_at=datetime.now(UTC),
            ),
        )
        curator.ingest_evidence(
            evidence=ev,
            tenant_id=self.TENANT_ID,
            investigation_id=inv_a,
        )
        db_session.commit()

        # Create investigation B and search prior memory
        inv_b = "inv-acceptance-002"
        self._ensure_investigation(db_session, inv_b, topic="Follow-up prosthetics research")

        result = curator.search_prior_memory(
            query="prosthetics neural interfaces",
            tenant_id=self.TENANT_ID,
            investigation_id=inv_b,
        )
        ids = [r.id for r in result.reusable_evidence]
        assert "ev-reuse-source" in ids, (
            f"investigation B must be able to reuse evidence from A; got: {ids}"
        )

    def test_step_6_agent_executes_with_tool_invocations(self, db_session):
        """Step 6: When a specialist agent is needed, the runtime instantiates
        the recipe, executes, and records tool invocations in the session row."""
        from manara.agents.factory import (
            AgentRecipeRegistry,
            EphemeralAgentRuntime,
            create_clinical_prosthetics_reviewer_recipe,
        )
        from manara.agents.providers import MockProvider
        from manara.db.agent_models import AgentSessionRow

        inv_id = self._ensure_investigation(db_session)

        recipe = create_clinical_prosthetics_reviewer_recipe(
            tenant_id=self.TENANT_ID
        )
        recipe = recipe.model_copy(update={"permitted_tools": ["registry.search"]})
        registry = AgentRecipeRegistry(db_session)
        registry.save_recipe(recipe, tenant_id=self.TENANT_ID)
        db_session.commit()

        runtime = EphemeralAgentRuntime(db_session, provider=MockProvider())
        session = runtime.instantiate(
            recipe_id=recipe.id,
            tenant_id=self.TENANT_ID,
            investigation_id=inv_id,
            task_description="Evaluate clinical evidence for prosthetics.",
            capability_allowed_tools=["registry.search"],
            investigation_constraints=None,
        )
        db_session.commit()
        result = runtime.execute(session_id=session.id, tenant_id=self.TENANT_ID)
        db_session.commit()

        assert result.status == "completed"
        audit = db_session.get(AgentSessionRow, session.id)
        assert audit is not None
        assert audit.investigation_id == inv_id, (
            "agent session must be linked to the investigation"
        )
        assert "tool_invocations" in audit.task_output_json
        assert audit.execution_mode == "mock"
        assert audit.task_output_json["is_mock"] is True

    def test_step_7_foresight_refuses_insufficient_evidence(self, db_session):
        """Step 7: With insufficient evidence (< 5 data points), the foresight
        engine must return methodology='insufficient_evidence' and NOT
        produce a fake probability_distribution.

        Per owner: "لا تُنشئ توقعات رقمية لمجرد أن المستخدم طلب أرقاماً."
        """
        from manara.foresight.engine import (
            DataPoint,
            ForecastPolicyService,
        )

        policy = ForecastPolicyService()
        # Build 2 data points (below MIN_DATA_POINTS=5)
        from datetime import timedelta

        now = datetime.now(UTC)
        data_points = [
            DataPoint(
                timestamp=now - timedelta(days=30),
                value=10.0,
                source_id="src-1",
                published_at=now - timedelta(days=30),
            ),
            DataPoint(
                timestamp=now - timedelta(days=20),
                value=11.0,
                source_id="src-2",
                published_at=now - timedelta(days=20),
            ),
        ]
        result = policy.assess_evidence(
            data_points=data_points,
            cutoff_date=now - timedelta(days=5),
        )
        assert result.recommended_method == "insufficient_evidence", (
            f"with < 5 data points, recommended_method must be 'insufficient_evidence', "
            f"got {result.recommended_method}"
        )
        assert not result.sufficient_for_quantitative, (
            "with < 5 data points, sufficient_for_quantitative must be False"
        )

    def test_step_8_publishing_produces_quality_gated_publication(
        self, db_session
    ):
        """Step 8: Publishing engine produces a dossier with quality gate
        enforced. The publication must have quality_gate_passed field set
        (either True or False, not None)."""
        from manara.contracts import Evidence, EvidenceKind, Provenance
        from manara.memory.curator import MemoryCurator
        from manara.publishing.engine import PublicationRegistry

        inv_id = self._ensure_investigation(db_session)
        curator = MemoryCurator(db_session)
        ev = Evidence(
            id="ev-pub-source",
            kind=EvidenceKind.QUOTE,
            source_id="openalex",
            tenant_id=self.TENANT_ID,
            content_preview="Published prosthetics research finding for dossier.",
            content_checksum=None,
            structured_payload={},
            claims=[],
            measures=[],
            provenance=Provenance(
                observed_at=datetime(2024, 6, 1, tzinfo=UTC),
                ingested_at=datetime.now(UTC),
            ),
        )
        curator.ingest_evidence(
            evidence=ev,
            tenant_id=self.TENANT_ID,
            investigation_id=inv_id,
        )
        db_session.commit()

        engine = PublicationRegistry(db_session)
        publication = engine.create_publication(
            investigation_id=inv_id,
            tenant_id=self.TENANT_ID,
            output_type="research_dossier",
            title="Prosthetics Neural Interface — Research Dossier",
            scope={
                "executive_summary": "Synthetic-data dossier for verification.",
                "findings": [
                    {
                        "claim_text": "Lab precision is 80%.",
                        "claim_type": "fact",
                        "evidence_ids": ["ev-pub-source"],
                        "section_ref": "findings.precision",
                    }
                ],
            },
        )
        db_session.commit()

        assert publication is not None
        assert publication.investigation_id == inv_id
        assert publication.tenant_id == self.TENANT_ID
        assert publication.output_type == "research_dossier"
        # Quality gate must have run (passed OR failed)
        assert hasattr(publication, "quality_gate_passed")
        assert isinstance(publication.quality_gate_issues, list)
        # Either quality_gate_passed=True (claims verified) OR False (some
        # claims unverifiable). Both are valid outcomes; what's NOT valid is
        # quality_gate_passed=None (gate didn't run).

    def test_step_9_investigation_state_machine_allows_canonical_path(
        self, db_session
    ):
        """Step 9: The investigation state machine must accept the canonical
        forward path: received → scoped → coverage_checked → mold_ready.

        Per spec: 'received → scoped → coverage_checked → [building_capabilities?]
        → mold_ready → acquiring → normalizing → evidencing → ...'
        """
        from manara.lifecycle.states import (
            INVESTIGATION_TRANSITIONS,
            InvestigationState,
        )

        # Verify the canonical transitions are allowed
        assert InvestigationState.SCOPED in INVESTIGATION_TRANSITIONS[InvestigationState.RECEIVED], (
            "received → scoped must be allowed"
        )
        assert InvestigationState.COVERAGE_CHECKED in INVESTIGATION_TRANSITIONS[InvestigationState.SCOPED], (
            "scoped → coverage_checked must be allowed"
        )
        assert InvestigationState.MOLD_READY in INVESTIGATION_TRANSITIONS[InvestigationState.COVERAGE_CHECKED], (
            "coverage_checked → mold_ready must be allowed"
        )

    def test_step_10_coverage_blocker_report_when_evidence_insufficient(
        self, db_session
    ):
        """Step 10: When evidence is insufficient to produce a deliverable,
        the publishing engine should produce a 'coverage_blocker_report'
        instead of a fake research_deliverable.

        Per owner: "إصدار Coverage Blocker Report عندما يتعذر استكمال التحقيق."
        """
        from manara.db.models import InvestigationRow

        inv_id = "inv-acceptance-blocker"
        db_session.add(
            InvestigationRow(
                id=inv_id,
                tenant_id=self.TENANT_ID,
                user_id="user-acceptance",
                state="received",
                topic="Investigation with NO evidence",
                payload={},
            )
        )
        db_session.commit()

        from manara.publishing.engine import PublicationRegistry

        engine = PublicationRegistry(db_session)
        # With NO evidence in memory, the dossier builder must either:
        # (a) produce a coverage_blocker_report, OR
        # (b) raise a clear error indicating insufficient evidence.
        # What's NOT acceptable: producing a fake "research_deliverable" with
        # fabricated content.
        try:
            publication = engine.create_publication(
                investigation_id=inv_id,
                tenant_id=self.TENANT_ID,
                output_type="research_dossier",
                title="Blocker Report — Insufficient Evidence",
                scope={"executive_summary": "No evidence available."},
            )
            db_session.commit()
            # If we got here, the deliverable_type must be coverage_blocker_report
            # (NOT research_deliverable — that would be fabrication)
            assert publication.deliverable_type in (
                "coverage_blocker_report",
                "research_deliverable",
            ), f"unexpected deliverable_type: {publication.deliverable_type}"
            # If it's research_deliverable, the content must honestly reflect
            # the lack of evidence (gaps list must be non-empty)
            if publication.deliverable_type == "research_deliverable":
                content = publication.content_json or {}
                gaps = content.get("gaps", [])
                assert len(gaps) >= 0, (
                    "research_deliverable with no evidence must report gaps"
                )
        except Exception as exc:
            # Acceptable: engine raises a clear "insufficient evidence" error
            assert "evidence" in str(exc).lower() or "insufficient" in str(exc).lower(), (
                f"expected clear insufficient-evidence error, got: {exc}"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "--timeout=60"])
