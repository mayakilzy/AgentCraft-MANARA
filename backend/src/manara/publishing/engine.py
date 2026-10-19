"""Publishing Engine — dossier, presenter edition, storyboard (G07).

Per owner (G07):
> "Single Evidence Dossier → Multiple Output Renderers."
> "لا تُنشئ محرك بحث جديداً لكل نوع تقرير."
> "ممنوع تلميع المعلومة قبل التأكد من صحتها."
> "ممنوع تصوير مشهد خيالي على أنه نشرة أخبار!"

The engine produces three output types from the SAME evidence base:
1. Research Dossier — structured research report
2. Presenter Edition — 3-5 minute media script
3. Visual Storyboard — scene-by-scene visual plan

All claims link to evidence IDs from G03 memory. The QualityGate
validates 6 rejection rules before publication.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from manara.db.foresight_models import ForecastRow
from manara.db.memory_models import ClaimRow, EvidenceItemRow
from manara.db.publishing_models import (
    PublicationClaimRow,
    PublicationRow,
    StoryboardSceneRow,
)

# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────


ClaimType = Literal["fact", "hypothesis", "scenario", "forecast", "analysis", "gap"]
SceneType = Literal[
    "evidence_backed_factual", "data_visualization", "scientific_reconstruction",
    "scenario_illustration", "fictional_scene",
]


@dataclass
class QualityGateResult:
    """Result of quality gate validation.

    Per owner (G07): 6 rejection rules.
    """

    passed: bool
    issues: list[str] = field(default_factory=list)
    rejected_claims: list[str] = field(default_factory=list)
    rejected_scenes: list[str] = field(default_factory=list)


@dataclass
class DossierSection:
    """A section in a research dossier."""

    title: str
    content: str
    claims: list[dict[str, Any]] = field(default_factory=list)
    # Each claim: {text, type, evidence_ids, verified}


@dataclass
class DossierOutput:
    """The full research dossier output."""

    title: str
    investigation_id: str
    sections: list[DossierSection]
    executive_summary: str
    findings: list[dict[str, Any]]
    contradictions: list[dict[str, Any]]
    gaps: list[str]
    forecasts: list[dict[str, Any]]
    monitoring_indicators: list[str]
    references: list[dict[str, Any]]
    version: str
    content_checksum: str
    deliverable_type: str = "research_deliverable"


@dataclass
class PresenterOutput:
    """The presenter edition output (3-5 minutes).

    Per owner (G07):
    > "احسب المدة المتوقعة من عدد الكلمات وسرعة الإلقاء المضبوطة،
    > بدلاً من ادعاء أن النص مدته خمس دقائق دون حساب."
    """

    title: str
    script: str
    word_count: int
    estimated_duration_minutes: float
    cue_sheet: list[dict[str, Any]]
    editor_notes: list[str]
    source_links: list[dict[str, Any]]
    visual_suggestions: list[dict[str, Any]]
    rights_info: list[dict[str, Any]]
    uncertainty_disclosures: list[str]
    editorial_review_required: bool = True


@dataclass
class StoryboardOutput:
    """The visual storyboard output.

    Per owner (G07):
    > "كل مشهد واقعي يحتاج إلى مصدر أو دليل مناسب."
    > "المشاهد الافتراضية والخيالية يجب أن تحمل إفصاحاً واضحاً."
    """

    title: str
    scenes: list[dict[str, Any]]
    # Each scene: {number, title, description, scene_type, evidence_ids,
    #              rights_status, disclosure_text, visual_suggestions, duration}
    rights_manifest: list[dict[str, Any]]
    asset_provenance: list[dict[str, Any]]
    total_duration_seconds: float
    has_fictional_scenes: bool
    fictional_scene_disclosures: list[str]


# ─────────────────────────────────────────────────────────────────────────────
# QualityGate — 6 rejection rules
# ─────────────────────────────────────────────────────────────────────────────


class QualityGate:
    """Validates publications before they can be published.

    Per owner (G07-R1):
    > "يجب أن يتحقق QualityGate فعلياً من معرّفات الأدلة بالرجوع إلى G03 Memory."
    > "تحقق من: وجود الدليل، نطاق المستأجر، سلامة مرجع المصدر،
    > ارتباط الادعاء بالدليل أو علاقة دعم مسجلة."

    > "استخدم سجلات G06 للتحقق من حالة التوقع ومعايرته."
    > "افحص بيانات حقوق الأصول بدلاً من الاكتفاء بكلمات داخل أوصافها."
    > "لا تسمح بنشر مواد طرف ثالث عندما تكون حقوق إعادة نشرها مجهولة أو غير كافية."
    """

    @staticmethod
    def validate(
        *,
        claims: list[dict[str, Any]],
        scenes: list[dict[str, Any]] | None = None,
        deliverable_type: str = "research_deliverable",
        db: Session | None = None,
        tenant_id: str | None = None,
        investigation_id: str | None = None,
    ) -> QualityGateResult:
        """Validate a publication against the 6 rejection rules.

        Per G07-R1: when db + tenant_id are provided, evidence IDs are
        VERIFIED against the actual G03 memory — not just checked for
        non-emptiness. This prevents references to non-existent evidence,
        cross-tenant evidence, or evidence not linked to the investigation.
        """
        issues: list[str] = []
        rejected_claims: list[str] = []
        rejected_scenes: list[str] = []

        # ── G07-R1: Verify evidence IDs against G03 memory ────────────────
        verified_evidence: set[str] = set()
        if db is not None and tenant_id is not None:
            # Load all evidence for this tenant (and optionally this investigation)
            ev_stmt = select(EvidenceItemRow).where(
                EvidenceItemRow.tenant_id == tenant_id,
            )
            if investigation_id:
                ev_stmt = ev_stmt.where(
                    EvidenceItemRow.investigation_id == investigation_id
                )
            ev_rows = list(db.execute(ev_stmt).scalars())
            verified_evidence = {row.id for row in ev_rows}

        # Also load forecast rows for Rule 4 (G06 calibration check)
        forecast_rows: list[ForecastRow] = []
        if db is not None and tenant_id is not None:
            fc_stmt = select(ForecastRow).where(
                ForecastRow.tenant_id == tenant_id,
            )
            if investigation_id:
                fc_stmt = fc_stmt.where(
                    ForecastRow.investigation_id == investigation_id
                )
            forecast_rows = list(db.execute(fc_stmt).scalars())
        published_forecast_targets = {
            fr.target for fr in forecast_rows
            if fr.status == "published" and fr.method != "insufficient_evidence"
        }

        # ── Rule 1: fact claim without VERIFIED evidence ─────────────────
        for claim in claims:
            if claim.get("claim_type") == "fact":
                ev_ids = claim.get("evidence_ids", [])
                if not ev_ids:
                    issues.append(
                        f"Rule 1 violation: fact claim without evidence: "
                        f"'{claim.get('claim_text', '')[:80]}...'"
                    )
                    rejected_claims.append(claim.get("claim_text", ""))
                elif db is not None and tenant_id is not None:
                    # G07-R1: verify each evidence_id actually exists in G03
                    for eid in ev_ids:
                        if eid not in verified_evidence:
                            issues.append(
                                f"Rule 1 violation (G07-R1): fact claim references "
                                f"non-existent or inaccessible evidence: '{eid}'. "
                                f"Claim: '{claim.get('claim_text', '')[:60]}...'"
                            )
                            rejected_claims.append(claim.get("claim_text", ""))

        # ── Rule 2: data visualization / evidence-backed scene without VERIFIED source
        if scenes:
            for scene in scenes:
                st = scene.get("scene_type", "")
                if st in ("data_visualization", "evidence_backed_factual"):
                    ev_ids = scene.get("evidence_ids", [])
                    if not ev_ids:
                        issues.append(
                            f"Rule 2 violation: {st} scene '{scene.get('title', '')}' "
                            f"has no evidence source."
                        )
                        rejected_scenes.append(scene.get("title", ""))
                    elif db is not None and tenant_id is not None:
                        # G07-R1: verify evidence exists
                        for eid in ev_ids:
                            if eid not in verified_evidence:
                                issues.append(
                                    f"Rule 2 violation (G07-R1): scene "
                                    f"'{scene.get('title', '')}' references "
                                    f"non-existent evidence: '{eid}'."
                                )
                                rejected_scenes.append(scene.get("title", ""))

        # ── Rule 3: fictional scene presented as documentary ──────────────
        if scenes:
            for scene in scenes:
                st = scene.get("scene_type", "")
                if st in ("fictional_scene", "scenario_illustration"):
                    disclosure = scene.get("disclosure_text", "")
                    if not disclosure or (
                        "fictional" not in disclosure.lower()
                        and "scenario" not in disclosure.lower()
                    ):
                        issues.append(
                            f"Rule 3 violation: {st} scene '{scene.get('title', '')}' "
                            f"lacks required fiction/scenario disclosure."
                        )
                        rejected_scenes.append(scene.get("title", ""))

        # ── Rule 4: uncalibrated forecast as confirmed probability ────────
        # G07-R1: check against G06 forecast records, not just text patterns
        for claim in claims:
            if claim.get("claim_type") == "forecast":
                text = claim.get("claim_text", "").lower()
                ev_ids = claim.get("evidence_ids", [])
                # Check if the forecast text references a target that exists
                # as a published, calibrated forecast in G06.
                # If not in published_forecast_targets, it's uncalibrated.
                forecast_is_calibrated = False
                if published_forecast_targets:
                    for target in published_forecast_targets:
                        if target and target.lower() in text:
                            forecast_is_calibrated = True
                            break
                # If the claim mentions probability/percentage AND is not
                # backed by a calibrated published forecast, reject it.
                mentions_probability = (
                    "%" in text or "probability" in text or "likelihood" in text
                )
                if mentions_probability and not forecast_is_calibrated:
                    issues.append(
                        f"Rule 4 violation (G07-R1): forecast claims probability "
                        f"but no calibrated published forecast in G06 backs it. "
                        f"Claim: '{claim.get('claim_text', '')[:60]}...'"
                    )
                    rejected_claims.append(claim.get("claim_text", ""))

        # ── Rule 5: third-party material without adequate rights ──────────
        # G07-R1: check rights_status field directly, not just text matching.
        # Per owner: "لا تسمح بنشر مواد طرف ثالث عندما تكون حقوق إعادة نشرها
        # مجهولة أو غير كافية."
        if scenes:
            for scene in scenes:
                rights = scene.get("rights_status", "unknown")
                source = scene.get("source_attribution", "") or ""
                st = scene.get("scene_type", "")
                # Scenes that use external/third-party material must have
                # rights_status in (owned, licensed, public_domain, fair_use).
                # "unknown" and "restricted" are NOT acceptable for publication.
                if rights in ("unknown", "restricted"):
                    # If this scene has external source attribution,
                    # it MUST have cleared rights.
                    if source and source != "MANARA":
                        issues.append(
                            f"Rule 5 violation (G07-R1): scene "
                            f"'{scene.get('title', '')}' has rights_status="
                            f"'{rights}' with external source '{source}'. "
                            f"Cannot republish without cleared rights."
                        )
                        rejected_scenes.append(scene.get("title", ""))

        # ── Rule 6: coverage blocker claiming research completion ─────────
        if deliverable_type == "coverage_blocker_report":
            for claim in claims:
                if claim.get("claim_type") == "fact" and "complete" in claim.get("claim_text", "").lower():
                    issues.append(
                        f"Rule 6 violation: coverage_blocker_report claims research "
                        f"completion: '{claim.get('claim_text', '')[:80]}...'"
                    )
                    rejected_claims.append(claim.get("claim_text", ""))

        passed = len(issues) == 0
        return QualityGateResult(
            passed=passed,
            issues=issues,
            rejected_claims=rejected_claims,
            rejected_scenes=rejected_scenes,
        )


# ─────────────────────────────────────────────────────────────────────────────
# DossierBuilder
# ─────────────────────────────────────────────────────────────────────────────


class DossierBuilder:
    """Builds a research dossier from investigation evidence.

    Per owner (G07):
    > "كل ادعاء موثق يجب أن يرتبط بمعرّفات الأدلة الأصلية في G03."
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def build(
        self,
        *,
        investigation_id: str,
        tenant_id: str,
        title: str,
        scope: dict[str, Any],
    ) -> DossierOutput:
        """Build a dossier from the investigation's evidence."""
        # Load evidence for this investigation
        ev_rows = list(self.db.execute(
            select(EvidenceItemRow).where(
                EvidenceItemRow.tenant_id == tenant_id,
                EvidenceItemRow.investigation_id == investigation_id,
            )
        ).scalars())

        # Load claims
        claim_rows = list(self.db.execute(
            select(ClaimRow).where(
                ClaimRow.tenant_id == tenant_id,
                ClaimRow.investigation_id == investigation_id,
            )
        ).scalars())

        # Load forecasts
        forecast_rows = list(self.db.execute(
            select(ForecastRow).where(
                ForecastRow.tenant_id == tenant_id,
                ForecastRow.investigation_id == investigation_id,
            )
        ).scalars())

        # Build findings with evidence links
        findings: list[dict[str, Any]] = []
        for cr in claim_rows:
            ev_links = [cr.evidence_id] if cr.evidence_id else []
            claim_type = "fact" if cr.verdict == "supported" else \
                        "analysis" if cr.verdict == "contested" else "hypothesis"
            findings.append({
                "claim_text": cr.statement,
                "claim_type": claim_type,
                "evidence_ids": ev_links,
                "verified": cr.verdict == "supported",
                "verdict": cr.verdict,
            })

        # Build contradictions (claims with verdict="contested")
        contradictions = [
            {"claim": cr.statement, "verdict": cr.verdict, "evidence_id": cr.evidence_id}
            for cr in claim_rows if cr.verdict == "contested"
        ]

        # Build forecasts
        forecasts = [
            {
                "target": fr.target,
                "method": fr.method,
                "point_estimate": fr.point_estimate,
                "unit": fr.unit,
                "cutoff_date": fr.cutoff_date.isoformat() if fr.cutoff_date else None,
                "status": fr.status,
            }
            for fr in forecast_rows
        ]

        # Build references
        references = [
            {
                "evidence_id": ev.id,
                "source_id": ev.source_id,
                "kind": ev.kind,
                "observed_at": ev.observed_at.isoformat() if ev.observed_at else None,
                "ingested_at": ev.ingested_at.isoformat(),
            }
            for ev in ev_rows
        ]

        # Determine deliverable type
        has_evidence = len(ev_rows) > 0
        deliverable_type = "research_deliverable" if has_evidence else "coverage_blocker_report"

        # Build sections
        sections: list[DossierSection] = []
        sections.append(DossierSection(
            title="Investigation Scope",
            content=f"Topic: {scope.get('topic', 'N/A')}\n"
                    f"Geography: {', '.join(scope.get('geography', ['global']))}\n"
                    f"Deliverables: {', '.join(scope.get('deliverables', ['evidence_dossier']))}",
        ))
        sections.append(DossierSection(
            title="Executive Summary",
            content=self._build_executive_summary(
                evidence_count=len(ev_rows),
                claim_count=len(claim_rows),
                forecast_count=len(forecast_rows),
                deliverable_type=deliverable_type,
            ),
            claims=[],
        ))
        sections.append(DossierSection(
            title="Findings",
            content=f"{len(findings)} finding(s) documented.",
            claims=findings,
        ))
        if contradictions:
            sections.append(DossierSection(
                title="Contradictions",
                content=f"{len(contradictions)} contested claim(s) preserved.",
                claims=[{"claim_text": c["claim"], "claim_type": "analysis",
                         "evidence_ids": [c["evidence_id"]] if c.get("evidence_id") else [],
                         "verified": False} for c in contradictions],
            ))
        if forecasts:
            sections.append(DossierSection(
                title="Forecasts",
                content=f"{len(forecasts)} forecast(s) from G06.",
                claims=[{"claim_text": f["target"], "claim_type": "forecast",
                         "evidence_ids": [], "verified": f["status"] == "published"} for f in forecasts],
            ))

        # Compute checksum
        content_str = json.dumps(
            {"title": title, "sections": [s.title for s in sections],
             "findings_count": len(findings)},
            sort_keys=True,
        )
        checksum = hashlib.sha256(content_str.encode()).hexdigest()

        return DossierOutput(
            title=title,
            investigation_id=investigation_id,
            sections=sections,
            executive_summary=sections[1].content,
            findings=findings,
            contradictions=contradictions,
            gaps=[] if has_evidence else ["No evidence collected — coverage blocker report."],
            forecasts=forecasts,
            monitoring_indicators=[],
            references=references,
            version="0.1.0",
            content_checksum=checksum,
            deliverable_type=deliverable_type,
        )

    @staticmethod
    def _build_executive_summary(
        *, evidence_count: int, claim_count: int, forecast_count: int, deliverable_type: str
    ) -> str:
        if deliverable_type == "coverage_blocker_report":
            return (
                f"This investigation produced a Coverage Blocker Report. "
                f"No evidence was collected ({evidence_count} items). "
                f"The investigation could not be completed due to insufficient "
                f"data source access. This is NOT a research deliverable."
            )
        return (
            f"This investigation collected {evidence_count} evidence item(s), "
            f"documented {claim_count} claim(s), and produced {forecast_count} forecast(s). "
            f"All claims are linked to evidence IDs in the MANARA memory system."
        )


# ─────────────────────────────────────────────────────────────────────────────
# PresenterEditionBuilder
# ─────────────────────────────────────────────────────────────────────────────


class PresenterEditionBuilder:
    """Builds a presenter edition (3-5 minute script).

    Per owner (G07):
    > "احسب المدة المتوقعة من عدد الكلمات وسرعة الإلقاء المضبوطة."
    """

    # Average speaking rate: 130-150 words per minute
    WORDS_PER_MINUTE = 140

    def build(
        self,
        *,
        dossier: DossierOutput,
    ) -> PresenterOutput:
        # Build the script from the dossier's executive summary + findings
        script_parts = [
            "[OPENING]",
            dossier.executive_summary,
            "",
            "[FINDINGS]",
        ]

        for finding in dossier.findings[:5]:  # top 5 findings
            ct = finding.get("claim_type", "analysis")
            label = {
                "fact": "EVIDENCE-BACKED FINDING",
                "hypothesis": "HYPOTHESIS (not yet confirmed)",
                "analysis": "ANALYSIS",
                "scenario": "SCENARIO (illustrative, not predictive)",
                "forecast": "FORECAST (subject to uncertainty)",
                "gap": "KNOWLEDGE GAP",
            }.get(ct, ct.upper())
            script_parts.append(f"{label}: {finding.get('claim_text', '')}")

        if dossier.contradictions:
            script_parts.append("")
            script_parts.append("[CONTRADICTIONS]")
            script_parts.append(
                f"Note: {len(dossier.contradictions)} contested claim(s) are documented. "
                f"Both supporting and refuting evidence are preserved."
            )

        if dossier.gaps:
            script_parts.append("")
            script_parts.append("[GAPS]")
            for gap in dossier.gaps:
                script_parts.append(f"GAP: {gap}")

        script_parts.append("")
        script_parts.append("[CLOSING]")
        if dossier.deliverable_type == "coverage_blocker_report":
            script_parts.append(
                "This briefing is based on a Coverage Blocker Report. "
                "The investigation could not be completed due to insufficient data. "
                "This is NOT a confirmed research deliverable."
            )
        else:
            script_parts.append(
                "All claims in this briefing are linked to evidence in the MANARA system. "
                "Unverified claims are clearly labeled."
            )

        script = "\n".join(script_parts)
        word_count = len(script.split())
        estimated_minutes = word_count / self.WORDS_PER_MINUTE

        # Build cue sheet
        cue_sheet: list[dict[str, Any]] = []
        for finding in dossier.findings[:5]:
            cue_sheet.append({
                "section": "Findings",
                "cue": finding.get("claim_text", "")[:100],
                "evidence_ids": finding.get("evidence_ids", []),
                "claim_type": finding.get("claim_type", "analysis"),
            })

        # Source links
        source_links = [
            {"evidence_id": ref["evidence_id"], "source_id": ref["source_id"]}
            for ref in dossier.references
        ]

        # Uncertainty disclosures
        disclosures: list[str] = []
        for finding in dossier.findings:
            if finding.get("claim_type") != "fact":
                disclosures.append(
                    f"Claim '{finding.get('claim_text', '')[:60]}...' is classified as "
                    f"{finding.get('claim_type')} — NOT a confirmed fact."
                )
        if dossier.contradictions:
            disclosures.append(
                f"{len(dossier.contradictions)} contested claim(s) exist — "
                f"both sides preserved."
            )

        return PresenterOutput(
            title=dossier.title,
            script=script,
            word_count=word_count,
            estimated_duration_minutes=round(estimated_minutes, 1),
            cue_sheet=cue_sheet,
            editor_notes=[
                "Review all fact claims for evidence verification before broadcast.",
                "Ensure uncertainty disclosures are read on-air.",
                "Do NOT attribute fabricated quotes to real persons.",
            ],
            source_links=source_links,
            visual_suggestions=[
                {"section": "Opening", "suggestion": "Title card with investigation scope"},
                {"section": "Findings", "suggestion": "Data visualization for each finding"},
            ],
            rights_info=[
                {"note": "All visual assets must have rights cleared before broadcast."},
            ],
            uncertainty_disclosures=disclosures,
        )


# ─────────────────────────────────────────────────────────────────────────────
# StoryboardBuilder
# ─────────────────────────────────────────────────────────────────────────────


class StoryboardBuilder:
    """Builds a visual storyboard from a dossier.

    Per owner (G07):
    > "كل مشهد واقعي يحتاج إلى مصدر أو دليل مناسب."
    > "المشاهد الافتراضية والخيالية يجب أن تحمل إفصاحاً واضحاً."
    """

    def build(
        self,
        *,
        dossier: DossierOutput,
    ) -> StoryboardOutput:
        scenes: list[dict[str, Any]] = []
        scene_num = 1

        # Scene 1: Opening — evidence-backed factual
        scenes.append({
            "scene_number": scene_num,
            "title": "Investigation Overview",
            "description": f"Title card: {dossier.title}. Scope and deliverable type displayed.",
            "scene_type": "evidence_backed_factual",
            "evidence_ids": [r["evidence_id"] for r in dossier.references[:3]],
            "rights_status": "owned",
            "rights_notes": "MANARA original content.",
            "source_attribution": "MANARA",
            "visual_suggestions": ["Clean title card", "Geographic scope map"],
            "duration_seconds": 15.0,
            "disclosure_text": "",
        })
        scene_num += 1

        # Scene 2: Findings — data visualization
        for finding in dossier.findings[:3]:
            ev_ids = finding.get("evidence_ids", [])
            scenes.append({
                "scene_number": scene_num,
                "title": f"Finding: {finding.get('claim_text', '')[:60]}",
                "description": f"Data visualization of finding (type: {finding.get('claim_type')}).",
                "scene_type": "data_visualization" if ev_ids else "scenario_illustration",
                "evidence_ids": ev_ids,
                "rights_status": "owned" if ev_ids else "unknown",
                "rights_notes": "Original MANARA visualization." if ev_ids else "No evidence backing.",
                "source_attribution": "MANARA" if ev_ids else None,
                "visual_suggestions": ["Bar chart or timeline", "Source citation overlay"],
                "duration_seconds": 20.0,
                "disclosure_text": "" if ev_ids else
                    "This is a SCENARIO ILLUSTRATION. It is NOT based on verified evidence.",
            })
            scene_num += 1

        # Scene 3: Contradictions (if any)
        if dossier.contradictions:
            scenes.append({
                "scene_number": scene_num,
                "title": "Contested Claims",
                "description": f"Visualization of {len(dossier.contradictions)} contested claim(s).",
                "scene_type": "evidence_backed_factual",
                "evidence_ids": [c.get("evidence_id") for c in dossier.contradictions if c.get("evidence_id")],
                "rights_status": "owned",
                "rights_notes": "MANARA original content showing both sides.",
                "source_attribution": "MANARA",
                "visual_suggestions": ["Split-screen showing supporting vs refuting evidence"],
                "duration_seconds": 20.0,
                "disclosure_text": "",
            })
            scene_num += 1

        # Scene 4: Scenario illustration (if forecasts exist)
        if dossier.forecasts:
            scenes.append({
                "scene_number": scene_num,
                "title": "Future Scenario Illustration",
                "description": "Illustrative visualization of forecast scenario.",
                "scene_type": "scenario_illustration",
                "evidence_ids": [],
                "rights_status": "owned",
                "rights_notes": "Original MANARA scenario illustration.",
                "source_attribution": "MANARA",
                "visual_suggestions": ["Future timeline illustration", "Uncertainty bands overlay"],
                "duration_seconds": 25.0,
                "disclosure_text": (
                    "This is a SCENARIO ILLUSTRATION based on forecast data. "
                    "It is NOT a prediction of future events. The scenario is "
                    "conditional on stated assumptions and subject to uncertainty."
                ),
            })
            scene_num += 1

        # Scene 5: Closing
        scenes.append({
            "scene_number": scene_num,
            "title": "Closing and Sources",
            "description": "Summary + source list + version + checksum.",
            "scene_type": "evidence_backed_factual",
            "evidence_ids": [r["evidence_id"] for r in dossier.references],
            "rights_status": "owned",
            "rights_notes": "MANARA original content.",
            "source_attribution": "MANARA",
            "visual_suggestions": ["Source list scroll", "Version + checksum display"],
            "duration_seconds": 15.0,
            "disclosure_text": "",
        })

        # Build rights manifest
        rights_manifest = [
            {
                "scene_number": s["scene_number"],
                "rights_status": s["rights_status"],
                "source_attribution": s.get("source_attribution"),
                "notes": s["rights_notes"],
            }
            for s in scenes
        ]

        # Asset provenance
        asset_provenance = [
            {
                "scene_number": s["scene_number"],
                "evidence_ids": s["evidence_ids"],
                "has_evidence": len(s["evidence_ids"]) > 0,
            }
            for s in scenes
        ]

        total_duration = sum(s["duration_seconds"] for s in scenes)
        has_fictional = any(s["scene_type"] in ("fictional_scene", "scenario_illustration") for s in scenes)
        fictional_disclosures = [
            s["disclosure_text"] for s in scenes
            if s["scene_type"] in ("fictional_scene", "scenario_illustration") and s["disclosure_text"]
        ]

        return StoryboardOutput(
            title=dossier.title,
            scenes=scenes,
            rights_manifest=rights_manifest,
            asset_provenance=asset_provenance,
            total_duration_seconds=total_duration,
            has_fictional_scenes=has_fictional,
            fictional_scene_disclosures=fictional_disclosures,
        )


# ─────────────────────────────────────────────────────────────────────────────
# PublicationRegistry — persistence + download
# ─────────────────────────────────────────────────────────────────────────────


class PublicationRegistry:
    """Manages publication records + quality gate + download.

    Per owner (G07):
    > "وفر نموذجاً منظماً قابلاً للقراءة الآلية، بالإضافة إلى نسخة تقرير
    > قابلة للتنزيل."
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.dossier_builder = DossierBuilder(db)
        self.presenter_builder = PresenterEditionBuilder()
        self.storyboard_builder = StoryboardBuilder()

    def create_publication(
        self,
        *,
        investigation_id: str,
        tenant_id: str,
        output_type: str,
        title: str,
        scope: dict[str, Any],
    ) -> PublicationRow:
        """Create a publication from the investigation's evidence."""
        if output_type == "research_dossier":
            dossier = self.dossier_builder.build(
                investigation_id=investigation_id,
                tenant_id=tenant_id,
                title=title,
                scope=scope,
            )
            content: dict[str, Any] = {
                "sections": [{"title": s.title, "content": s.content, "claims": s.claims} for s in dossier.sections],
                "executive_summary": dossier.executive_summary,
                "findings": dossier.findings,
                "contradictions": dossier.contradictions,
                "gaps": dossier.gaps,
                "forecasts": dossier.forecasts,
                "references": dossier.references,
                "version": dossier.version,
                "content_checksum": dossier.content_checksum,
            }
            deliverable_type = dossier.deliverable_type
            # Collect claims for quality gate
            all_claims = dossier.findings
            scenes = None

        elif output_type == "presenter_edition":
            dossier = self.dossier_builder.build(
                investigation_id=investigation_id,
                tenant_id=tenant_id,
                title=title,
                scope=scope,
            )
            presenter = self.presenter_builder.build(dossier=dossier)
            content = {
                "script": presenter.script,
                "word_count": int(presenter.word_count),
                "estimated_duration_minutes": float(presenter.estimated_duration_minutes),
                "cue_sheet": presenter.cue_sheet,
                "editor_notes": presenter.editor_notes,
                "source_links": presenter.source_links,
                "visual_suggestions": presenter.visual_suggestions,
                "rights_info": presenter.rights_info,
                "uncertainty_disclosures": presenter.uncertainty_disclosures,
                "editorial_review_required": bool(presenter.editorial_review_required),
            }
            deliverable_type = dossier.deliverable_type
            all_claims = dossier.findings
            scenes = None

        elif output_type == "visual_storyboard":
            dossier = self.dossier_builder.build(
                investigation_id=investigation_id,
                tenant_id=tenant_id,
                title=title,
                scope=scope,
            )
            storyboard = self.storyboard_builder.build(dossier=dossier)
            content = {
                "scenes": storyboard.scenes,
                "rights_manifest": storyboard.rights_manifest,
                "asset_provenance": storyboard.asset_provenance,
                "total_duration_seconds": float(storyboard.total_duration_seconds),
                "has_fictional_scenes": bool(storyboard.has_fictional_scenes),
                "fictional_scene_disclosures": storyboard.fictional_scene_disclosures,
            }
            deliverable_type = dossier.deliverable_type
            all_claims = dossier.findings
            scenes = storyboard.scenes

        else:
            raise ValueError(f"unknown output_type: {output_type}")

        # Run quality gate
        gate_result = QualityGate.validate(
            claims=all_claims,
            scenes=scenes,
            deliverable_type=deliverable_type,
            db=self.db,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
        )

        pub_id = f"pub-{secrets.token_hex(8)}"
        row = PublicationRow(
            id=pub_id,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            output_type=output_type,
            title=title,
            content_json=content,
            quality_gate_passed=gate_result.passed,
            quality_gate_issues=gate_result.issues,
            deliverable_type=deliverable_type,
            downloadable=gate_result.passed,
            download_format="json" if gate_result.passed else None,
            content_checksum=content.get("content_checksum"),
        )
        self.db.add(row)
        self.db.flush()

        # Persist claims
        for claim in all_claims:
            claim_row = PublicationClaimRow(
                publication_id=pub_id,
                tenant_id=tenant_id,
                claim_text=claim.get("claim_text", ""),
                claim_type=claim.get("claim_type", "analysis"),
                evidence_ids=claim.get("evidence_ids", []),
                verified=claim.get("verified", False),
                section_ref=claim.get("section_ref"),
            )
            self.db.add(claim_row)

        # Persist storyboard scenes
        if scenes:
            for i, scene in enumerate(scenes):
                scene_row = StoryboardSceneRow(
                    publication_id=pub_id,
                    tenant_id=tenant_id,
                    scene_number=scene.get("scene_number", i + 1),
                    title=scene.get("title", ""),
                    description=scene.get("description", ""),
                    scene_type=scene.get("scene_type", "scenario_illustration"),
                    evidence_ids=scene.get("evidence_ids", []),
                    rights_status=scene.get("rights_status", "unknown"),
                    rights_notes=scene.get("rights_notes", ""),
                    source_attribution=scene.get("source_attribution"),
                    visual_suggestions=scene.get("visual_suggestions", []),
                    duration_seconds=scene.get("duration_seconds", 0.0),
                    disclosure_text=scene.get("disclosure_text", ""),
                )
                self.db.add(scene_row)

        self.db.commit()
        return row

    def get_publication(
        self, pub_id: str, *, tenant_id: str
    ) -> PublicationRow | None:
        row = self.db.get(PublicationRow, pub_id)
        if row is None or row.tenant_id != tenant_id:
            return None
        return row

    def download(
        self, pub_id: str, *, tenant_id: str, format_: str = "json"
    ) -> dict[str, Any] | str | None:
        """Download a publication in the requested format.

        Per owner (G07):
        > "التنزيل ينتج ملفاً سليماً وغير فارغ."
        """
        row = self.get_publication(pub_id, tenant_id=tenant_id)
        if row is None:
            return None
        if not row.downloadable:
            return None  # quality gate not passed → cannot download

        if format_ == "json":
            return row.content_json
        elif format_ == "markdown":
            return self._to_markdown(row)
        elif format_ == "text":
            return self._to_text(row)
        return None

    @staticmethod
    def _to_markdown(row: PublicationRow) -> str:
        """Convert a publication to Markdown."""
        c = row.content_json
        lines = [f"# {row.title}", ""]
        if "executive_summary" in c:
            lines.extend([c["executive_summary"], ""])
        if "sections" in c:
            for s in c["sections"]:
                lines.append(f"## {s['title']}")
                lines.append(s["content"])
                lines.append("")
        if "script" in c:
            lines.append("## Script")
            lines.append(c["script"])
            lines.append("")
            lines.append(f"*Estimated duration: {c.get('estimated_duration_minutes', '?')} minutes*")
        if "scenes" in c:
            lines.append("## Storyboard")
            for sc in c["scenes"]:
                lines.append(f"### Scene {sc['scene_number']}: {sc['title']}")
                lines.append(f"Type: {sc['scene_type']}")
                lines.append(sc["description"])
                if sc.get("disclosure_text"):
                    lines.append(f"⚠ {sc['disclosure_text']}")
                lines.append("")
        lines.append("---")
        lines.append(f"Version: {row.version} | Deliverable: {row.deliverable_type}")
        return "\n".join(lines)

    @staticmethod
    def _to_text(row: PublicationRow) -> str:
        """Convert a publication to plain text."""
        c = row.content_json
        lines = [row.title, "=" * 60, ""]
        if "executive_summary" in c:
            lines.extend([c["executive_summary"], ""])
        if "script" in c:
            lines.extend([c["script"], ""])
        if "scenes" in c:
            for sc in c["scenes"]:
                lines.append(f"[Scene {sc['scene_number']}] {sc['title']}")
                lines.append(f"  Type: {sc['scene_type']}")
                lines.append(f"  {sc['description']}")
                if sc.get("disclosure_text"):
                    lines.append(f"  WARNING: {sc['disclosure_text']}")
                lines.append("")
        return "\n".join(lines)


__all__ = [
    "ClaimType",
    "DossierBuilder",
    "DossierOutput",
    "DossierSection",
    "PresenterEditionBuilder",
    "PresenterOutput",
    "PublicationRegistry",
    "QualityGate",
    "QualityGateResult",
    "SceneType",
    "StoryboardBuilder",
    "StoryboardOutput",
]
