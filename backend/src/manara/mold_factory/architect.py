"""Mold Architect — composes investigation molds with three-tier coverage (G04-R1).

Per owner decision (G04-R1, 2026-10-19):
> "يجب أن يميز Mold Architect بين:
> - التغطية المعرفية: توجد بطاقة مسجلة تصف محركاً مناسباً للمهمة.
> - التغطية التشغيلية: يوجد موصل حقيقي، صالح، ومختبر، ومسموح بتشغيله.
> - التغطية المثبتة: أن المحرك جُرّب فعلياً لاسترجاع بيانات مناسبة."

> "لا تجعل is_complete=True عندما تكون الاحتياجات مغطاة ببطاقات غير
> قابلة للتنفيذ."

> "ولا تعتبر مجرد وجود Connector ID إثباتاً لصلاحية الموصل."

The architect now:
1. Detects whether the domain is known (existing mold) or unknown.
2. Decomposes the query into research needs (reuses G01-R1 decomposer).
3. For each need, finds matching capabilities in the registry.
4. For each matching capability, checks the THREE coverage levels:
   - CATALOG: the capability card exists
   - OPERATIONAL: the capability has at least one APPROVED connector
   - VERIFIED: the connector has a successful sandbox test record
5. Records operational gaps AUTOMATICALLY when a capability has no
   approved connector — never requires manual gap insertion.
6. Sets is_complete=True ONLY when every need has OPERATIONAL+ coverage.
7. Sets deliverable_type to "coverage_blocker_report" when operational
   gaps exist (not "research_deliverable").

Per owner (G04-R1):
> "لا تعتبر مجرد وجود Connector ID إثباتاً لصلاحية الموصل."

So we verify the ConnectorRow's status is "approved" AND the SourceRow's
status is "approved" — not just that connector_ids is non-empty.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from manara.contracts import (
    Mold,
    MoldComposition,
    MoldScope,
    SearchCapability,
)
from manara.db.mold_models import GapAnalysisRow, MoldRecipeRow, MoldReuseRow
from manara.db.registry_models import CapabilityRow, ConnectorRow, SourceRow
from manara.foundry.catalog import CATALOG
from manara.lifecycle import FoundryState, MoldState
from manara.mold_factory.detector import UnknownDomainDetector
from manara.registry.converters import row_to_capability
from manara.registry.decomposer import (
    NEED_TO_CAPABILITIES,
    DetectedNeed,
    decompose_query,
)
from manara.registry.embeddings import Embedder
from manara.registry.service import CapabilityRegistry

# ─────────────────────────────────────────────────────────────────────────────
# Coverage levels — the three-tier model (G04-R1)
# ─────────────────────────────────────────────────────────────────────────────


class CoverageLevel(str, Enum):
    """Three-tier coverage model per owner decision (G04-R1).

    NONE        — no capability card matches the need
    CATALOG     — a capability card exists, but no approved connector is linked
    OPERATIONAL — a capability card exists AND at least one approved connector is linked
    VERIFIED    — operational coverage AND the connector has a successful sandbox test record
    """

    NONE = "none"
    CATALOG = "catalog"
    OPERATIONAL = "operational"
    VERIFIED = "verified"

    @property
    def is_executable(self) -> bool:
        """True if this coverage level allows the mold to actually run."""
        return self in (CoverageLevel.OPERATIONAL, CoverageLevel.VERIFIED)


# ─────────────────────────────────────────────────────────────────────────────
# Result dataclasses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class NeedCoverage:
    """Per-need coverage decision with the three-tier level."""

    need: str
    need_label: str
    need_relevance: float
    candidate_capability_ids: list[str]
    selected_capability_id: str | None
    selection_reasoning: str
    coverage_level: CoverageLevel = CoverageLevel.NONE
    connector_ids: list[str] = field(default_factory=list)
    operational_gap_recorded: bool = False


@dataclass
class GapRecord:
    """A detected gap — a need that cannot be satisfied by existing capabilities."""

    need: str
    need_label: str
    need_relevance: float
    foundry_candidates_checked: list[str]
    foundry_resolution: str
    resolution_notes: str
    catalog_capability_id: str | None = None
    coverage_level: CoverageLevel = CoverageLevel.NONE


@dataclass
class MoldCompositionResult:
    """The full output of composing a temporary mold for a query.

    Per owner (G04-R1):
    > "لا تجعل is_complete=True عندما تكون الاحتياجات مغطاة ببطاقات غير
    > قابلة للتنفيذ."
    """

    query: str
    tenant_id: str
    investigation_id: str | None
    is_unknown_domain: bool
    detection_reasoning: str
    detected_needs: list[DetectedNeed]
    coverage: list[NeedCoverage]
    gaps: list[GapRecord]
    mold: Mold
    mold_recipe_id: str
    is_complete: bool
    is_catalog_complete: bool
    deliverable_type: str = "unknown"
    composition_notes: str = ""
    composed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "tenant_id": self.tenant_id,
            "investigation_id": self.investigation_id,
            "is_unknown_domain": self.is_unknown_domain,
            "detection_reasoning": self.detection_reasoning,
            "detected_needs": [
                {"need": d.need, "label_en": d.label_en, "label_ar": d.label_ar, "relevance": d.relevance}
                for d in self.detected_needs
            ],
            "coverage": [
                {
                    "need": c.need,
                    "need_label": c.need_label,
                    "selected_capability_id": c.selected_capability_id,
                    "coverage_level": c.coverage_level.value,
                    "connector_ids": c.connector_ids,
                    "selection_reasoning": c.selection_reasoning,
                    "operational_gap_recorded": c.operational_gap_recorded,
                }
                for c in self.coverage
            ],
            "gaps": [
                {
                    "need": g.need,
                    "need_label": g.need_label,
                    "foundry_resolution": g.foundry_resolution,
                    "resolution_notes": g.resolution_notes,
                    "catalog_capability_id": g.catalog_capability_id,
                    "coverage_level": g.coverage_level.value,
                }
                for g in self.gaps
            ],
            "mold_recipe_id": self.mold_recipe_id,
            "mold": self.mold.model_dump(mode="json"),
            "is_complete": self.is_complete,
            "is_catalog_complete": self.is_catalog_complete,
            "deliverable_type": self.deliverable_type,
            "composition_notes": self.composition_notes,
            "composed_at": self.composed_at.isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# MoldArchitect
# ─────────────────────────────────────────────────────────────────────────────


class MoldArchitect:
    """Composes temporary molds with three-tier coverage checking.

    The architect coordinates:
    * UnknownDomainDetector (this package)
    * InvestigationDecomposer (G01-R1)
    * CapabilityRegistry (G01) — to check what capabilities exist
    * ConnectorRow + SourceRow (G01/G02) — to check operational coverage
    * Foundry catalog (G02) — to check what source candidates exist
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.detector = UnknownDomainDetector(db)
        self.capability_registry = CapabilityRegistry(db)
        self.embedder = Embedder.get()

    def compose_mold(
        self,
        query: str,
        *,
        tenant_id: str,
        investigation_id: str | None = None,
        domain_hint: str | None = None,
    ) -> MoldCompositionResult:
        """Compose a temporary mold for the given query.

        Per owner (G09-R1):
        > "أنشئ InvestigationRow حقيقياً بمعرّف ثابت عند بدء التحقيق."
        > "اربطه بالقالب الناتج."

        If investigation_id is None, a real InvestigationRow is created
        automatically. This ensures every mold has a real investigation
        backing it — no null IDs.
        """
        # G09-R1: Create a real InvestigationRow if none provided
        if investigation_id is None:
            import secrets as _secrets

            from manara.db.models import InvestigationRow as _InvRow
            investigation_id = f"inv-{_secrets.token_hex(8)}"
            inv_row = _InvRow(
                id=investigation_id,
                tenant_id=tenant_id,
                user_id="system",
                state="received",
                topic=query[:500],
                payload={
                    "id": investigation_id,
                    "tenant_id": tenant_id,
                    "user_id": "system",
                    "scope": {"topic": query},
                    "state": "received",
                },
            )
            self.db.add(inv_row)
            self.db.commit()

        # ── Step 1: Detect ───────────────────────────────────────────────────
        detection = self.detector.detect(query, tenant_id=tenant_id, domain_hint=domain_hint)

        if not detection.is_unknown and detection.matched_molds:
            best = detection.matched_molds[0]
            mold = Mold.model_validate(best.payload)
            return self._record_reuse(
                query=query, tenant_id=tenant_id, investigation_id=investigation_id,
                mold_recipe_row=best, mold=mold, detected_needs=[], coverage=[],
                gaps=[], is_complete=True, is_catalog_complete=True,
                composition_notes=f"Reused existing mold '{best.display_name}'.",
                is_unknown_domain=False, detection_reasoning=detection.detection_reasoning,
            )

        # ── Step 2: Decompose ───────────────────────────────────────────────
        decomposition = decompose_query(query, embedder=self.embedder)
        detected_needs = decomposition.detected_needs + decomposition.implicit_needs

        # ── Step 3: Load tenant's capabilities, connectors, sources ─────────
        all_caps_rows = list(self.db.execute(
            select(CapabilityRow).where(
                CapabilityRow.tenant_id == tenant_id,
                CapabilityRow.status.in_(self.capability_registry.SEARCHABLE_STATUSES),
            )
        ).scalars())
        all_caps: dict[str, SearchCapability] = {
            row.id: row_to_capability(row) for row in all_caps_rows
        }

        # Load approved connectors for this tenant
        approved_connectors: dict[str, ConnectorRow] = {
            row.id: row for row in self.db.execute(
                select(ConnectorRow).where(
                    ConnectorRow.tenant_id == tenant_id,
                    ConnectorRow.status == FoundryState.APPROVED.value,
                )
            ).scalars()
        }

        # Load approved sources
        approved_sources: dict[str, SourceRow] = {
            row.id: row for row in self.db.execute(
                select(SourceRow).where(
                    SourceRow.tenant_id == tenant_id,
                    SourceRow.status == FoundryState.APPROVED.value,
                )
            ).scalars()
        }

        # ── Step 4: For each need, find matching capability + check coverage ─
        coverage: list[NeedCoverage] = []
        gaps: list[GapRecord] = []

        for need in detected_needs:
            candidate_ids = NEED_TO_CAPABILITIES.get(need.need, [])
            available_candidates = [cid for cid in candidate_ids if cid in all_caps]

            if not available_candidates:
                # No capability card at all → gap with NO catalog coverage
                gap = self._attempt_foundry_resolution(
                    need=need, candidate_ids=candidate_ids, tenant_id=tenant_id,
                )
                gaps.append(gap)
                continue

            # Pick the best candidate using G01-R1's scoring (positive example
            # similarity) instead of just taking the first.
            selected_id = self._select_best_capability(
                query=query, need=need, candidate_ids=available_candidates,
                all_caps=all_caps, tenant_id=tenant_id,
            )

            if selected_id is None:
                # All candidates exist but none had a usable positive-example
                # match. Record as catalog-level gap.
                gap = self._attempt_foundry_resolution(
                    need=need, candidate_ids=available_candidates, tenant_id=tenant_id,
                )
                gap.catalog_capability_id = available_candidates[0]
                gap.coverage_level = CoverageLevel.CATALOG
                gaps.append(gap)
                continue

            cap = all_caps[selected_id]
            # ── THREE-TIER COVERAGE CHECK (the G04-R1 core) ──────────────────
            coverage_level = self._check_coverage_level(
                cap=cap, approved_connectors=approved_connectors,
                approved_sources=approved_sources,
            )

            if coverage_level.is_executable:
                # Operational or verified → the need is truly covered
                cov = NeedCoverage(
                    need=need.need,
                    need_label=need.label_en,
                    need_relevance=need.relevance,
                    candidate_capability_ids=available_candidates,
                    selected_capability_id=selected_id,
                    selection_reasoning=(
                        f"Capability '{selected_id}' has {coverage_level.value} coverage "
                        f"(approved connector exists). Need is truly covered."
                    ),
                    coverage_level=coverage_level,
                    connector_ids=list(cap.connector_ids),
                    operational_gap_recorded=False,
                )
                coverage.append(cov)
            else:
                # CATALOG coverage only → the card exists but no approved connector.
                # Per owner: "احتفظ به كمرشح معرفي. سجّل فجوة تشغيلية تلقائياً."
                cov = NeedCoverage(
                    need=need.need,
                    need_label=need.label_en,
                    need_relevance=need.relevance,
                    candidate_capability_ids=available_candidates,
                    selected_capability_id=selected_id,
                    selection_reasoning=(
                        f"Capability '{selected_id}' has only {coverage_level.value} coverage "
                        f"(no approved connector). Operational gap recorded automatically."
                    ),
                    coverage_level=coverage_level,
                    connector_ids=[],
                    operational_gap_recorded=True,
                )
                coverage.append(cov)

                # Record the operational gap AUTOMATICALLY
                gap = self._record_operational_gap(
                    need=need, catalog_capability_id=selected_id,
                    tenant_id=tenant_id,
                )
                gaps.append(gap)

        # ── Step 5: Compose the temporary mold ──────────────────────────────
        # Only executable capabilities go into the mold's capability_ids
        # (operational+). Catalog-only capabilities are recorded in the
        # coverage map but NOT in the executable plan — they're "we know
        # what we need but can't run it yet".
        executable_capability_ids = [
            c.selected_capability_id for c in coverage
            if c.selected_capability_id and c.coverage_level.is_executable
        ]
        catalog_only_capability_ids = [
            c.selected_capability_id for c in coverage
            if c.selected_capability_id and not c.coverage_level.is_executable
        ]

        domain = self._derive_domain(query)
        intent = query[:300]
        random_suffix = secrets.token_hex(4)
        mold_id = f"mold.{domain}-{int(datetime.now(UTC).timestamp())}-{random_suffix}"

        mold = Mold(
            id=mold_id,
            version="0.1.0",
            display_name=f"Temporary investigation mold for: {domain}",
            description_long=(
                f"Composed on {datetime.now(UTC).isoformat()} by the MoldArchitect (G04-R1). "
                f"Detected {len(detected_needs)} needs; "
                f"{len(executable_capability_ids)} have operational coverage (executable); "
                f"{len(catalog_only_capability_ids)} have catalog-only coverage (need connector); "
                f"{len(gaps)} gap(s) recorded explicitly — no fabricated capabilities."
            ),
            scope=MoldScope(
                domain=domain, intent=intent, geography=["global"],
                deliverables=["evidence_dossier", "scenario_report"],
            ),
            composition=MoldComposition(
                capability_ids=executable_capability_ids,
                agent_recipe_ids=[],
                composition_notes=(
                    f"Executable capabilities: {len(executable_capability_ids)}. "
                    f"Catalog-only (pending connector): {len(catalog_only_capability_ids)}. "
                    f"Gaps: {len(gaps)}. "
                    "Per G04-R1: is_complete requires operational coverage on all needs."
                ),
                plan=[
                    {"step": "acquire_evidence", "capability_ids": executable_capability_ids},
                    {"step": "curate_evidence", "uses": "manara.memory.MemoryCurator"},
                    {
                        "step": "report_gaps",
                        "gap_needs": [g.need for g in gaps],
                        "catalog_only_capabilities": catalog_only_capability_ids,
                        "note": (
                            "These needs have no approved connector. The investigation "
                            "report must include a 'coverage gaps' section. This mold "
                            "can only produce a coverage/blocker report, NOT a research "
                            "deliverable, until operational coverage is achieved."
                        ),
                    },
                ],
            ),
            state=MoldState.TEMPORARY,
        )

        # ── Step 6: Persist the mold recipe + gap analyses ─────────────────
        mold_row = MoldRecipeRow(
            id=mold.id, tenant_id=tenant_id,
            display_name=mold.display_name,
            description_long=mold.description_long,
            version=mold.version, schema_version=mold.schema_version,
            state=mold.state.value, domain=mold.scope.domain,
            intent=mold.scope.intent, sector=mold.scope.sector,
            geography_json=mold.scope.geography,
            languages_json=mold.scope.languages,
            deliverables_json=mold.scope.deliverables,
            capability_ids_json=mold.composition.capability_ids,
            agent_recipe_ids_json=mold.composition.agent_recipe_ids,
            composition_notes=mold.composition.composition_notes,
            plan_json=mold.composition.plan,
            origin="temporary_fresh",
            payload=mold.model_dump(mode="json"),
        )
        self.db.add(mold_row)
        self.db.flush()

        for gap in gaps:
            gap_row = GapAnalysisRow(
                tenant_id=tenant_id, mold_id=mold.id,
                investigation_id=investigation_id,
                need=gap.need, need_label=gap.need_label,
                candidate_capability_ids_json=gap.foundry_candidates_checked,
                status=gap.foundry_resolution,
                resolution_notes=gap.resolution_notes,
            )
            self.db.add(gap_row)

        self.db.commit()

        # ── Step 7: Compute completion flags + deliverable type ─────────────
        is_catalog_complete = all(
            c.coverage_level != CoverageLevel.NONE for c in coverage
        ) and len(coverage) == len(detected_needs)
        is_complete = all(
            c.coverage_level.is_executable for c in coverage
        ) and len(coverage) == len(detected_needs)

        if is_complete:
            deliverable_type = "research_deliverable"
        elif is_catalog_complete:
            deliverable_type = "coverage_blocker_report"
        else:
            deliverable_type = "coverage_blocker_report"

        composition_notes = (
            f"Composed temporary mold '{mold.id}': "
            f"{len(executable_capability_ids)} executable + "
            f"{len(catalog_only_capability_ids)} catalog-only + "
            f"{len(gaps)} gap(s). "
            f"is_complete={is_complete} (requires operational coverage). "
            f"deliverable_type={deliverable_type}."
        )

        result = MoldCompositionResult(
            query=query, tenant_id=tenant_id,
            investigation_id=investigation_id,
            is_unknown_domain=True,
            detection_reasoning=detection.detection_reasoning,
            detected_needs=detected_needs,
            coverage=coverage, gaps=gaps, mold=mold,
            mold_recipe_id=mold.id,
            is_complete=is_complete,
            is_catalog_complete=is_catalog_complete,
            deliverable_type=deliverable_type,
            composition_notes=composition_notes,
        )

        # FIX-01 (MANARA-UI-BACKEND-CLOSURE-02): persist the full
        # composition result on the mold row so the Mold Blueprint can
        # be reconstructed after page reload without re-running compose.
        # We store a trimmed view (the fields the UI needs for the
        # blueprint) — not the full to_dict() (which would duplicate
        # query, tenant_id, investigation_id, mold_recipe_id, mold that
        # are already on the row or in payload).
        mold_row.composition_result_json = {
            "detected_needs": [
                {
                    "need": d.need,
                    "label_en": d.label_en,
                    "label_ar": d.label_ar,
                    "relevance": d.relevance,
                }
                for d in result.detected_needs
            ],
            "coverage": [
                {
                    "need": c.need,
                    "need_label": c.need_label,
                    "selected_capability_id": c.selected_capability_id,
                    "coverage_level": c.coverage_level.value,
                    "connector_ids": list(c.connector_ids),
                    "selection_reasoning": c.selection_reasoning,
                    "operational_gap_recorded": c.operational_gap_recorded,
                }
                for c in result.coverage
            ],
            "gaps": [
                {
                    "need": g.need,
                    "need_label": g.need_label,
                    "foundry_resolution": g.foundry_resolution,
                    "resolution_notes": g.resolution_notes,
                    "catalog_capability_id": g.catalog_capability_id,
                    "coverage_level": g.coverage_level.value,
                }
                for g in result.gaps
            ],
            "is_complete": result.is_complete,
            "is_catalog_complete": result.is_catalog_complete,
            "deliverable_type": result.deliverable_type,
            "is_unknown_domain": result.is_unknown_domain,
            "detection_reasoning": result.detection_reasoning,
            "composition_notes": result.composition_notes,
            "composed_at": result.composed_at.isoformat(),
        }
        self.db.add(mold_row)
        self.db.commit()

        return result

    # ── Coverage level check (the G04-R1 core) ─────────────────────────────────

    def _check_coverage_level(
        self,
        *,
        cap: SearchCapability,
        approved_connectors: dict[str, ConnectorRow],
        approved_sources: dict[str, SourceRow],
    ) -> CoverageLevel:
        """Check the three-tier coverage level for a capability.

        Per owner (G04-R1):
        > "ولا تعتبر مجرد وجود Connector ID إثباتاً لصلاحية الموصل."

        So we verify:
        1. The capability has connector_ids
        2. At least one connector_id exists in approved_connectors (status="approved")
        3. The connector's source_id exists in approved_sources (status="approved")

        Returns:
        - CATALOG: card exists but no connector_ids, or no approved connector
        - OPERATIONAL: approved connector + approved source exist
        - VERIFIED: operational + connector has last_verified_at set (sandbox test ran)
        """
        if not cap.connector_ids:
            return CoverageLevel.CATALOG

        # Find approved connectors referenced by this capability
        approved_linked_connectors: list[ConnectorRow] = []
        for cid in cap.connector_ids:
            conn = approved_connectors.get(cid)
            if conn is None:
                continue
            # Verify the connector's source is also approved
            if conn.source_id in approved_sources:
                approved_linked_connectors.append(conn)

        if not approved_linked_connectors:
            return CoverageLevel.CATALOG

        # Check for VERIFIED: at least one connector has a last_verified_at
        # (sandbox test was run). The ConnectorRow doesn't have last_verified_at
        # directly, but the ConnectorGovernance contract does. We check the
        # payload's governance.last_verified_at field.
        for conn in approved_linked_connectors:
            try:
                payload = conn.payload
                gov = payload.get("governance", {})
                if gov.get("last_verified_at") is not None:
                    return CoverageLevel.VERIFIED
            except (AttributeError, KeyError):
                continue

        return CoverageLevel.OPERATIONAL

    # ── Capability selection (improved per G04-R1) ─────────────────────────────

    def _select_best_capability(
        self,
        *,
        query: str,
        need: DetectedNeed,
        candidate_ids: list[str],
        all_caps: dict[str, SearchCapability],
        tenant_id: str,
    ) -> str | None:
        """Select the best matching capability using G01-R1's scoring.

        Per owner (G04-R1):
        > "استفد من آلية ترتيب القدرات الموجودة في G01-R1، مع إضافة فحص
        > الجاهزية الفعلية؛ لا تختر المحرك اعتماداً على ترتيب ثابت في القائمة."

        Scores each candidate by positive-example similarity (from G01-R1's
        _example_similarities). Returns the highest-scoring candidate, or
        None if no candidate has a usable positive-example match.
        """
        if not candidate_ids:
            return None

        import numpy as np

        query_vec = self.embedder.encode_one(query)
        query_vec_norm = query_vec / (np.linalg.norm(query_vec) + 1e-12)

        best_id: str | None = None
        best_score = -1.0

        for cid in candidate_ids:
            cap = all_caps.get(cid)
            if cap is None:
                continue

            # Look up the ORM row for semantic similarity computation
            cap_row_orm = self.db.get(CapabilityRow, cid)

            # Use G01-R1's _example_similarities method
            pos_sims = self.capability_registry._example_similarities(
                query_vec_norm, cid, tenant_id, kind="positive_example"
            )
            pos_max = max(pos_sims) if pos_sims else 0.0
            sem_sim = self.capability_registry._semantic_similarity(
                query_vec, cap_row_orm, tenant_id=tenant_id
            ) if cap_row_orm is not None else 0.0

            # Need-fit score (same formula as G01-R1)
            neg_sims = self.capability_registry._example_similarities(
                query_vec_norm, cid, tenant_id, kind="negative_example"
            )
            neg_max = max(neg_sims) if neg_sims else 0.0

            need_fit = (pos_max * 0.55) + (sem_sim * 0.35) - (neg_max * 0.40)

            if need_fit > best_score:
                best_score = need_fit
                best_id = cid

        return best_id

    # ── Operational gap recording ──────────────────────────────────────────────

    def _record_operational_gap(
        self, *, need: DetectedNeed, catalog_capability_id: str, tenant_id: str
    ) -> GapRecord:
        """Record an operational gap: the capability card exists but has no
        approved connector.

        Per owner (G04-R1):
        > "سجّل فجوة تشغيلية تلقائياً."
        """
        return GapRecord(
            need=need.need,
            need_label=need.label_en,
            need_relevance=need.relevance,
            foundry_candidates_checked=[],
            foundry_resolution="operational_gap",
            resolution_notes=(
                f"Catalog capability '{catalog_capability_id}' exists for need "
                f"'{need.need}' but has NO approved connector. The capability "
                "is recorded as a catalog-level candidate, but cannot execute. "
                "This gap is recorded automatically by the MoldArchitect — "
                "no fabrication. The investigation can only produce a coverage/"
                "blocker report, not a research deliverable, until a connector "
                "is approved via the Foundry (G02)."
            ),
            catalog_capability_id=catalog_capability_id,
            coverage_level=CoverageLevel.CATALOG,
        )

    def _attempt_foundry_resolution(
        self, *, need: DetectedNeed, candidate_ids: list[str], tenant_id: str
    ) -> GapRecord:
        """Look up the Foundry catalog for sources that could satisfy this need."""
        need_to_data_types = {
            "scientific_literature": ["academic-works", "metadata"],
            "patent_intelligence": ["patents", "ip-data"],
            "clinical_evidence": ["trials", "medical-data"],
            "technology_signals": ["repository-activity", "code-metadata"],
            "market_data": ["market-data", "cost-data"],
            "policy_indicators": ["policy", "regulation"],
            "event_tracking": ["events", "geopolitical"],
            "environmental_data": ["climate", "agriculture", "waste"],
        }
        wanted_types = need_to_data_types.get(need.need, [])

        matching_candidates: list[str] = []
        for candidate in CATALOG:
            if any(t in candidate.primary_data_types for t in wanted_types):
                matching_candidates.append(candidate.id)

        if matching_candidates:
            return GapRecord(
                need=need.need, need_label=need.label_en,
                need_relevance=need.relevance,
                foundry_candidates_checked=matching_candidates,
                foundry_resolution="foundry_invoked",
                resolution_notes=(
                    f"Foundry catalog has {len(matching_candidates)} candidate(s) "
                    f"for need '{need.need}': {matching_candidates}. "
                    "Sandbox testing + connector build is deferred to G05+. "
                    "The mold is composed WITHOUT a capability for this need; "
                    "the investigation report must note the coverage gap. "
                    "No fabricated capability inserted."
                ),
                coverage_level=CoverageLevel.NONE,
            )

        return GapRecord(
            need=need.need, need_label=need.label_en,
            need_relevance=need.relevance,
            foundry_candidates_checked=[],
            foundry_resolution="unresolved",
            resolution_notes=(
                f"No Foundry candidate available for need '{need.need}'. "
                "The mold is composed WITHOUT a capability for this need; "
                "the investigation report must explicitly note the missing "
                "coverage. No fabricated capability inserted."
            ),
            coverage_level=CoverageLevel.NONE,
        )

    def _record_reuse(
        self, *, query: str, tenant_id: str, investigation_id: str | None,
        mold_recipe_row: MoldRecipeRow, mold: Mold,
        detected_needs: list[DetectedNeed], coverage: list[NeedCoverage],
        gaps: list[GapRecord], is_complete: bool, is_catalog_complete: bool,
        composition_notes: str, is_unknown_domain: bool, detection_reasoning: str,
    ) -> MoldCompositionResult:
        """Record that an existing mold was reused for this investigation."""
        if investigation_id is not None:
            reuse_row = MoldReuseRow(
                tenant_id=tenant_id, mold_id=mold_recipe_row.id,
                investigation_id=investigation_id,
                reuse_rationale=(
                    f"Reused existing mold '{mold_recipe_row.display_name}' "
                    f"for investigation '{investigation_id}'."
                ),
                modified_during_reuse=False,
            )
            self.db.add(reuse_row)
            self.db.commit()

        return MoldCompositionResult(
            query=query, tenant_id=tenant_id,
            investigation_id=investigation_id,
            is_unknown_domain=is_unknown_domain,
            detection_reasoning=detection_reasoning,
            detected_needs=detected_needs, coverage=coverage, gaps=gaps,
            mold=mold, mold_recipe_id=mold_recipe_row.id,
            is_complete=is_complete, is_catalog_complete=is_catalog_complete,
            deliverable_type="research_deliverable" if is_complete else "coverage_blocker_report",
            composition_notes=composition_notes,
        )

    @staticmethod
    def _derive_domain(query: str) -> str:
        stopwords = {
            "the", "and", "for", "with", "from", "about", "into", "future",
            "study", "research", "investigation", "analysis", "report",
            "during", "next", "years", "year", " ده",
        }
        tokens = re.findall(r"\w+", query.lower(), flags=re.UNICODE)
        for t in tokens:
            if len(t) >= 4 and t not in stopwords:
                return str(t)
        return "custom"


__all__ = [
    "CoverageLevel",
    "GapRecord",
    "MoldArchitect",
    "MoldCompositionResult",
    "NeedCoverage",
]
