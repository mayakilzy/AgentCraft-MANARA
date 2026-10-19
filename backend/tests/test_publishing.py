"""Tests for the Publishing Engine (G07).

Acceptance test: "Future of Intelligent Prosthetics — Research & Foresight Briefing"

Per owner (G07):
> "سأطلب النظر إلى المخرجات الفعلية: هل التقرير قابل للقراءة؟ هل الإحالات
> سليمة؟ هل نسخة المقدم تصلح للاستخدام الإعلامي؟ هل مخطط المشاهد يحترم
> الفرق بين العلم والخيال؟"

Tests:
1. Research Dossier with evidence links
2. Presenter Edition with timing calculation
3. Visual Storyboard with evidence/fiction classification
4. Quality Gate rejection rules (6 rules)
5. Download produces non-empty file
6. Coverage blocker report is labeled clearly
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime

os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", "/home/z/my-project/.models")
os.environ.setdefault("HF_HOME", "/home/z/my-project/.models/hf_cache")

import pytest
from sqlalchemy.orm import Session

from manara.contracts import Evidence, EvidenceKind, Provenance
from manara.db.models import InvestigationRow
from manara.db.session import Base
from manara.memory import MemoryCurator
from manara.publishing import (
    DossierBuilder,
    PresenterEditionBuilder,
    PublicationRegistry,
    QualityGate,
    StoryboardBuilder,
)


@pytest.fixture()
def db_session(engine) -> Iterator[Session]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture()
def registry(db_session):
    return PublicationRegistry(db_session)


def _setup_prosthetics_investigation(db, tenant_id="tenant_demo"):
    """Setup the canonical G07 test: prosthetics investigation with evidence."""
    db.add(InvestigationRow(
        id="inv-prosthetics",
        tenant_id=tenant_id,
        user_id="test",
        state="evidencing",
        topic="Future of intelligent prosthetics",
        payload={"id": "inv-prosthetics", "tenant_id": tenant_id},
    ))
    db.commit()

    curator = MemoryCurator(db)

    # Ingest 2 evidence items
    ev1 = Evidence(
        id="ev-prosthetics-001",
        kind=EvidenceKind.QUOTE,
        source_id="openalex",
        tenant_id=tenant_id,
        content_preview="Neural interface prosthetics show 80% precision in lab tests.",
        provenance=Provenance(observed_at=datetime(2024, 6, 1, tzinfo=UTC)),
    )
    curator.ingest_evidence(
        evidence=ev1, tenant_id=tenant_id, investigation_id="inv-prosthetics",
    )

    ev2 = Evidence(
        id="ev-prosthetics-002",
        kind=EvidenceKind.QUOTE,
        source_id="clinicaltrials-gov",
        tenant_id=tenant_id,
        content_preview="Field trial shows only 40% precision in real-world conditions.",
        provenance=Provenance(observed_at=datetime(2024, 9, 1, tzinfo=UTC)),
    )
    curator.ingest_evidence(
        evidence=ev2, tenant_id=tenant_id, investigation_id="inv-prosthetics",
    )

    # Attach claims
    curator.attach_claim(
        claim_id="claim-prosthetics-001",
        tenant_id=tenant_id,
        investigation_id="inv-prosthetics",
        evidence_id="ev-prosthetics-001",
        statement="Neural interfaces achieve 80% precision in lab conditions.",
        verdict="supported",
    )
    curator.attach_claim(
        claim_id="claim-prosthetics-002",
        tenant_id=tenant_id,
        investigation_id="inv-prosthetics",
        evidence_id="ev-prosthetics-002",
        statement="Real-world precision drops to 40% in field conditions.",
        verdict="contested",
    )
    # Add refuting edge to make the claim contested
    curator.add_support_edge(
        tenant_id=tenant_id,
        claim_id="claim-prosthetics-001",
        evidence_id="ev-prosthetics-002",
        relation="refutes",
    )

    return "inv-prosthetics"


# ─────────────────────────────────────────────────────────────────────────────
# Dossier tests
# ─────────────────────────────────────────────────────────────────────────────


class TestDossierBuilder:
    def test_dossier_has_executive_summary(self, db_session):
        inv_id = _setup_prosthetics_investigation(db_session)
        builder = DossierBuilder(db_session)
        dossier = builder.build(
            investigation_id=inv_id,
            tenant_id="tenant_demo",
            title="Future of Intelligent Prosthetics — Research Briefing",
            scope={"topic": "Prosthetics", "geography": ["global"]},
        )
        assert len(dossier.executive_summary) > 50
        assert "evidence" in dossier.executive_summary.lower()

    def test_dossier_findings_link_to_evidence(self, db_session):
        """Per owner: 'كل ادعاء موثق يجب أن يرتبط بمعرّفات الأدلة الأصلية.'"""
        inv_id = _setup_prosthetics_investigation(db_session)
        builder = DossierBuilder(db_session)
        dossier = builder.build(
            investigation_id=inv_id, tenant_id="tenant_demo",
            title="Prosthetics Briefing",
            scope={"topic": "Prosthetics"},
        )
        assert len(dossier.findings) > 0
        for finding in dossier.findings:
            if finding.get("claim_type") == "fact":
                assert len(finding.get("evidence_ids", [])) > 0, (
                    "Fact claim must have evidence_ids"
                )

    def test_dossier_preserves_contradictions(self, db_session):
        """Per owner: 'التناقضات لم تُحذف.'"""
        inv_id = _setup_prosthetics_investigation(db_session)
        builder = DossierBuilder(db_session)
        dossier = builder.build(
            investigation_id=inv_id, tenant_id="tenant_demo",
            title="Prosthetics Briefing",
            scope={"topic": "Prosthetics"},
        )
        assert len(dossier.contradictions) > 0, (
            "Contested claims should be preserved as contradictions"
        )

    def test_dossier_with_no_evidence_is_coverage_blocker(self, db_session):
        """Per owner: 'تقريراً يدّعي اكتمال البحث بينما التحقيق لم ينتج سوى
        Coverage Blocker Report.'"""
        db_session.add(InvestigationRow(
            id="inv-empty", tenant_id="tenant_demo", user_id="test",
            state="received", topic="Empty investigation",
            payload={"id": "inv-empty", "tenant_id": "tenant_demo"},
        ))
        db_session.commit()
        builder = DossierBuilder(db_session)
        dossier = builder.build(
            investigation_id="inv-empty", tenant_id="tenant_demo",
            title="Empty Investigation",
            scope={"topic": "Empty"},
        )
        assert dossier.deliverable_type == "coverage_blocker_report"
        assert len(dossier.gaps) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Presenter Edition tests
# ─────────────────────────────────────────────────────────────────────────────


class TestPresenterEdition:
    def test_script_has_word_count_and_duration(self, db_session):
        """Per owner: 'احسب المدة المتوقعة من عدد الكلمات وسرعة الإلقاء.'"""
        inv_id = _setup_prosthetics_investigation(db_session)
        builder = DossierBuilder(db_session)
        dossier = builder.build(
            investigation_id=inv_id, tenant_id="tenant_demo",
            title="Prosthetics Briefing",
            scope={"topic": "Prosthetics"},
        )
        presenter = PresenterEditionBuilder().build(dossier=dossier)
        assert presenter.word_count > 0
        assert presenter.estimated_duration_minutes > 0
        # Duration should be based on word count / speaking rate
        expected = presenter.word_count / 140
        assert abs(presenter.estimated_duration_minutes - round(expected, 1)) < 0.1

    def test_script_has_uncertainty_disclosures(self, db_session):
        inv_id = _setup_prosthetics_investigation(db_session)
        builder = DossierBuilder(db_session)
        dossier = builder.build(
            investigation_id=inv_id, tenant_id="tenant_demo",
            title="Prosthetics Briefing",
            scope={"topic": "Prosthetics"},
        )
        presenter = PresenterEditionBuilder().build(dossier=dossier)
        assert len(presenter.uncertainty_disclosures) > 0

    def test_cue_sheet_links_to_evidence(self, db_session):
        inv_id = _setup_prosthetics_investigation(db_session)
        builder = DossierBuilder(db_session)
        dossier = builder.build(
            investigation_id=inv_id, tenant_id="tenant_demo",
            title="Prosthetics Briefing",
            scope={"topic": "Prosthetics"},
        )
        presenter = PresenterEditionBuilder().build(dossier=dossier)
        for cue in presenter.cue_sheet:
            if cue.get("claim_type") == "fact":
                assert len(cue.get("evidence_ids", [])) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Storyboard tests
# ─────────────────────────────────────────────────────────────────────────────


class TestStoryboard:
    def test_scenes_classified_by_type(self, db_session):
        """Per owner: 'ميّز بين المشهد المبني على دليل والمشهد التخيلي.'"""
        inv_id = _setup_prosthetics_investigation(db_session)
        builder = DossierBuilder(db_session)
        dossier = builder.build(
            investigation_id=inv_id, tenant_id="tenant_demo",
            title="Prosthetics Briefing",
            scope={"topic": "Prosthetics"},
        )
        storyboard = StoryboardBuilder().build(dossier=dossier)
        assert len(storyboard.scenes) > 0
        for scene in storyboard.scenes:
            assert scene["scene_type"] in (
                "evidence_backed_factual", "data_visualization",
                "scientific_reconstruction", "scenario_illustration",
                "fictional_scene",
            )

    def test_fictional_scenes_have_disclosure(self, db_session):
        """Per owner: 'المشاهد الافتراضية والخيالية يجب أن تحمل إفصاحاً واضحاً.'"""
        inv_id = _setup_prosthetics_investigation(db_session)
        builder = DossierBuilder(db_session)
        dossier = builder.build(
            investigation_id=inv_id, tenant_id="tenant_demo",
            title="Prosthetics Briefing",
            scope={"topic": "Prosthetics"},
        )
        storyboard = StoryboardBuilder().build(dossier=dossier)
        if storyboard.has_fictional_scenes:
            assert len(storyboard.fictional_scene_disclosures) > 0
            for disclosure in storyboard.fictional_scene_disclosures:
                assert "NOT" in disclosure or "not" in disclosure, (
                    "Fictional scene disclosure must clearly state it is NOT documentary"
                )

    def test_evidence_backed_scenes_have_evidence_ids(self, db_session):
        """Per owner: 'كل مشهد واقعي يحتاج إلى مصدر أو دليل مناسب.'"""
        inv_id = _setup_prosthetics_investigation(db_session)
        builder = DossierBuilder(db_session)
        dossier = builder.build(
            investigation_id=inv_id, tenant_id="tenant_demo",
            title="Prosthetics Briefing",
            scope={"topic": "Prosthetics"},
        )
        storyboard = StoryboardBuilder().build(dossier=dossier)
        for scene in storyboard.scenes:
            if scene["scene_type"] in ("evidence_backed_factual", "data_visualization"):
                assert len(scene.get("evidence_ids", [])) > 0, (
                    f"Evidence-backed scene '{scene['title']}' has no evidence_ids"
                )

    def test_rights_manifest_present(self, db_session):
        """Per owner: 'Asset Provenance وRights Manifest.'"""
        inv_id = _setup_prosthetics_investigation(db_session)
        builder = DossierBuilder(db_session)
        dossier = builder.build(
            investigation_id=inv_id, tenant_id="tenant_demo",
            title="Prosthetics Briefing",
            scope={"topic": "Prosthetics"},
        )
        storyboard = StoryboardBuilder().build(dossier=dossier)
        assert len(storyboard.rights_manifest) > 0
        assert len(storyboard.asset_provenance) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Quality Gate tests
# ─────────────────────────────────────────────────────────────────────────────


class TestQualityGate:
    """Per owner (G07): 6 rejection rules."""

    def test_rule1_fact_without_evidence_rejected(self):
        """Rule 1: 'ادعاءً مصنفاً كحقيقة مثبتة بلا دليل.'"""
        result = QualityGate.validate(
            claims=[{"claim_text": "Prosthetics are 100% safe.", "claim_type": "fact", "evidence_ids": []}],
        )
        assert not result.passed
        assert any("Rule 1" in issue for issue in result.issues)

    def test_rule1_fact_with_evidence_accepted(self):
        result = QualityGate.validate(
            claims=[{"claim_text": "Prosthetics show 80% precision.", "claim_type": "fact", "evidence_ids": ["ev-001"]}],
        )
        assert result.passed

    def test_rule3_fictional_scene_without_disclosure_rejected(self):
        """Rule 3: 'مشهداً خيالياً يُقدم باعتباره توثيقاً.'"""
        result = QualityGate.validate(
            claims=[],
            scenes=[{
                "title": "Future City",
                "scene_type": "fictional_scene",
                "disclosure_text": "",  # NO disclosure!
            }],
        )
        assert not result.passed
        assert any("Rule 3" in issue for issue in result.issues)

    def test_rule3_fictional_scene_with_disclosure_accepted(self):
        result = QualityGate.validate(
            claims=[],
            scenes=[{
                "title": "Future City",
                "scene_type": "fictional_scene",
                "disclosure_text": "This is a fictional illustration, NOT a documentary.",
            }],
        )
        assert result.passed

    def test_rule4_uncalibrated_forecast_rejected(self):
        """Rule 4: 'توقعاً غير معاير يُعرض كنسبة احتمالية مؤكدة.'"""
        result = QualityGate.validate(
            claims=[{
                "claim_text": "There is a 95% probability that prosthetics will be perfect by 2030.",
                "claim_type": "forecast",
                "evidence_ids": [],  # no evidence!
            }],
        )
        assert not result.passed
        assert any("Rule 4" in issue for issue in result.issues)

    def test_rule6_coverage_blocker_claiming_completion_rejected(self):
        """Rule 6: 'تقريراً يدّعي اكتمال البحث بينما التحقيق لم ينتج سوى
        Coverage Blocker Report.'"""
        result = QualityGate.validate(
            claims=[{
                "claim_text": "The research is complete and all findings are confirmed.",
                "claim_type": "fact",
                "evidence_ids": [],
            }],
            deliverable_type="coverage_blocker_report",
        )
        assert not result.passed
        assert any("Rule 6" in issue for issue in result.issues)


# ─────────────────────────────────────────────────────────────────────────────
# Publication Registry + Download tests
# ─────────────────────────────────────────────────────────────────────────────


class TestPublicationRegistry:
    def test_create_dossier_publication(self, db_session):
        inv_id = _setup_prosthetics_investigation(db_session)
        registry = PublicationRegistry(db_session)
        row = registry.create_publication(
            investigation_id=inv_id,
            tenant_id="tenant_demo",
            output_type="research_dossier",
            title="Prosthetics Research Briefing",
            scope={"topic": "Prosthetics", "geography": ["global"]},
        )
        assert row.output_type == "research_dossier"
        assert row.deliverable_type == "research_deliverable"
        assert row.quality_gate_passed is True  # all facts have evidence

    def test_create_presenter_publication(self, db_session):
        inv_id = _setup_prosthetics_investigation(db_session)
        registry = PublicationRegistry(db_session)
        row = registry.create_publication(
            investigation_id=inv_id,
            tenant_id="tenant_demo",
            output_type="presenter_edition",
            title="Prosthetics Presenter Script",
            scope={"topic": "Prosthetics"},
        )
        assert row.output_type == "presenter_edition"
        content = row.content_json
        assert "script" in content
        assert content["word_count"] > 0
        assert content["estimated_duration_minutes"] > 0

    def test_create_storyboard_publication(self, db_session):
        inv_id = _setup_prosthetics_investigation(db_session)
        registry = PublicationRegistry(db_session)
        row = registry.create_publication(
            investigation_id=inv_id,
            tenant_id="tenant_demo",
            output_type="visual_storyboard",
            title="Prosthetics Visual Storyboard",
            scope={"topic": "Prosthetics"},
        )
        assert row.output_type == "visual_storyboard"
        content = row.content_json
        assert len(content["scenes"]) > 0
        assert len(content["rights_manifest"]) > 0

    def test_download_json_produces_non_empty_content(self, db_session):
        """Per owner: 'التنزيل ينتج ملفاً سليماً وغير فارغ.'"""
        inv_id = _setup_prosthetics_investigation(db_session)
        registry = PublicationRegistry(db_session)
        row = registry.create_publication(
            investigation_id=inv_id,
            tenant_id="tenant_demo",
            output_type="research_dossier",
            title="Prosthetics Briefing",
            scope={"topic": "Prosthetics"},
        )
        downloaded = registry.download(row.id, tenant_id="tenant_demo", format_="json")
        assert downloaded is not None
        assert len(downloaded) > 0  # non-empty

    def test_download_markdown_produces_readable_text(self, db_session):
        inv_id = _setup_prosthetics_investigation(db_session)
        registry = PublicationRegistry(db_session)
        row = registry.create_publication(
            investigation_id=inv_id,
            tenant_id="tenant_demo",
            output_type="research_dossier",
            title="Prosthetics Briefing",
            scope={"topic": "Prosthetics"},
        )
        downloaded = registry.download(row.id, tenant_id="tenant_demo", format_="markdown")
        assert downloaded is not None
        assert "# Prosthetics Briefing" in downloaded
        assert "Executive Summary" in downloaded or "executive" in downloaded.lower()

    def test_download_fails_if_quality_gate_not_passed(self, db_session):
        """If quality gate fails, downloadable=False and download returns None."""
        inv_id = _setup_prosthetics_investigation(db_session)
        registry = PublicationRegistry(db_session)
        row = registry.create_publication(
            investigation_id=inv_id,
            tenant_id="tenant_demo",
            output_type="research_dossier",
            title="Prosthetics Briefing",
            scope={"topic": "Prosthetics"},
        )
        # Manually fail the quality gate
        row.quality_gate_passed = False
        row.downloadable = False
        db_session.commit()
        downloaded = registry.download(row.id, tenant_id="tenant_demo")
        assert downloaded is None

    def test_coverage_blocker_report_downloadable(self, db_session):
        """Per owner: 'لا تمنع نشر تقارير نقص الأدلة؛ بل أعطها تصنيفاً
        ومظهراً واضحين.'"""
        db_session.add(InvestigationRow(
            id="inv-empty", tenant_id="tenant_demo", user_id="test",
            state="received", topic="Empty investigation",
            payload={"id": "inv-empty", "tenant_id": "tenant_demo"},
        ))
        db_session.commit()
        registry = PublicationRegistry(db_session)
        row = registry.create_publication(
            investigation_id="inv-empty",
            tenant_id="tenant_demo",
            output_type="research_dossier",
            title="Coverage Blocker Report — Empty Investigation",
            scope={"topic": "Empty"},
        )
        assert row.deliverable_type == "coverage_blocker_report"
        # Coverage blocker reports ARE downloadable (they're honest reports)
        assert row.downloadable is True
        downloaded = registry.download(row.id, tenant_id="tenant_demo", format_="markdown")
        assert downloaded is not None
        assert "Coverage Blocker" in downloaded or "coverage" in downloaded.lower()


# ─────────────────────────────────────────────────────────────────────────────
# THE G07 ACCEPTANCE TEST
# ─────────────────────────────────────────────────────────────────────────────


class TestG07Acceptance:
    """THE CANONICAL G07 ACCEPTANCE TEST.

    Per owner: "Future of Intelligent Prosthetics — Research & Foresight Briefing"
    """

    def test_full_prosthetics_briefing_all_three_outputs(self, db_session):
        inv_id = _setup_prosthetics_investigation(db_session)
        registry = PublicationRegistry(db_session)

        # A. Research Dossier
        dossier_row = registry.create_publication(
            investigation_id=inv_id,
            tenant_id="tenant_demo",
            output_type="research_dossier",
            title="Future of Intelligent Prosthetics — Research Briefing",
            scope={"topic": "Prosthetics", "geography": ["global"]},
        )
        assert dossier_row.quality_gate_passed is True
        assert dossier_row.deliverable_type == "research_deliverable"
        dossier_download = registry.download(dossier_row.id, tenant_id="tenant_demo", format_="markdown")
        assert dossier_download is not None
        assert "Prosthetics" in dossier_download

        # B. Presenter Edition
        presenter_row = registry.create_publication(
            investigation_id=inv_id,
            tenant_id="tenant_demo",
            output_type="presenter_edition",
            title="Prosthetics Presenter Script",
            scope={"topic": "Prosthetics"},
        )
        presenter_content = presenter_row.content_json
        assert presenter_content["word_count"] > 0
        assert presenter_content["estimated_duration_minutes"] > 0
        assert "script" in presenter_content

        # C. Visual Storyboard
        storyboard_row = registry.create_publication(
            investigation_id=inv_id,
            tenant_id="tenant_demo",
            output_type="visual_storyboard",
            title="Prosthetics Visual Storyboard",
            scope={"topic": "Prosthetics"},
        )
        sb_content = storyboard_row.content_json
        assert len(sb_content["scenes"]) > 0
        # Every evidence-backed scene has evidence_ids
        for scene in sb_content["scenes"]:
            if scene["scene_type"] in ("evidence_backed_factual", "data_visualization"):
                assert len(scene.get("evidence_ids", [])) > 0
        # Fictional/scenario scenes have disclosures
        for scene in sb_content["scenes"]:
            if scene["scene_type"] in ("fictional_scene", "scenario_illustration"):
                assert scene.get("disclosure_text", "") != ""
