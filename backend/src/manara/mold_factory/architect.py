"""Mold Architect — composes investigation molds from existing capabilities (G04).

Per ``03_INTELLIGENCE/03_AGENT_AND_MOLD_LIFECYCLE.md`` §Mold Architect:
> Intent/sector/time/outcome -> inspect mold registry -> inspect
> capability registry -> detect gaps -> call Foundry for new sources/
> connectors -> compose tested mold recipe -> pilot -> temporary
> investigation -> archive/upgrade.

The MoldArchitect orchestrates:
1. Decompose the query into research needs (reuses G01-R1 decomposer).
2. For each need, check if an existing capability in the registry can
   satisfy it (reuses G01-R1 NEED_TO_CAPABILITIES mapping + the
   capability registry's stored capabilities).
3. For each need that has NO matching capability, record a gap.
4. Attempt to invoke the Foundry (G02) to discover new sources for
   the gap — but only if the Foundry has a candidate catalog entry
   for that need's domain. Otherwise, record the gap as unresolved
   (per owner decision: "لا تتحايل عليها ببطاقة افتراضية تدّعي أنها
   محرك حقيقي").
5. Compose a temporary mold from the matched capabilities + the
   unresolved gaps (the gaps become explicit "coverage gaps" in the
   mold's plan, NOT fake capabilities).
6. Persist the mold recipe (state=temporary) so it can be rehydrated.

The MoldArchitect NEVER fabricates capabilities. If the Foundry cannot
provide a source for a need, the mold is composed WITHOUT that
capability, and the gap is recorded honestly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
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
from manara.db.registry_models import CapabilityRow
from manara.foundry.catalog import CATALOG
from manara.lifecycle import MoldState
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
# Result dataclasses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class NeedCoverage:
    """Per-need coverage decision: which capability (if any) covers this need."""

    need: str
    need_label: str
    need_relevance: float
    candidate_capability_ids: list[str]
    selected_capability_id: str | None
    selection_reasoning: str


@dataclass
class GapRecord:
    """A detected gap — a need that cannot be satisfied by existing capabilities."""

    need: str
    need_label: str
    need_relevance: float
    foundry_candidates_checked: list[str]
    foundry_resolution: str  # foundry_invoked | foundry_no_candidate | unresolved
    resolution_notes: str


@dataclass
class MoldCompositionResult:
    """The full output of composing a temporary mold for a query."""

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
    # The mold is "complete" if every detected need has a selected capability.
    # If gaps exist, the mold is "partial" and the investigation report
    # must explicitly note the missing coverage.
    is_complete: bool
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
                {
                    "need": d.need,
                    "label_en": d.label_en,
                    "label_ar": d.label_ar,
                    "relevance": d.relevance,
                }
                for d in self.detected_needs
            ],
            "coverage": [
                {
                    "need": c.need,
                    "need_label": c.need_label,
                    "selected_capability_id": c.selected_capability_id,
                    "selection_reasoning": c.selection_reasoning,
                }
                for c in self.coverage
            ],
            "gaps": [
                {
                    "need": g.need,
                    "need_label": g.need_label,
                    "foundry_resolution": g.foundry_resolution,
                    "resolution_notes": g.resolution_notes,
                }
                for g in self.gaps
            ],
            "mold_recipe_id": self.mold_recipe_id,
            "mold": self.mold.model_dump(mode="json"),
            "is_complete": self.is_complete,
            "composition_notes": self.composition_notes,
            "composed_at": self.composed_at.isoformat(),
        }


# ─────────────────────────────────────────────────────────────────────────────
# MoldArchitect
# ─────────────────────────────────────────────────────────────────────────────


class MoldArchitect:
    """Composes temporary molds from existing capabilities.

    The architect coordinates:
    * UnknownDomainDetector (this package)
    * InvestigationDecomposer (G01-R1)
    * CapabilityRegistry (G01) — to check what capabilities exist
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

        Steps:
        1. Detect whether the domain is known (existing mold) or unknown.
        2. If known: return the existing mold's recipe (reuse path).
        3. If unknown: decompose the query into research needs.
        4. For each need: find a matching capability in the registry.
        5. For each need without a match: record a gap.
        6. Attempt Foundry resolution for each gap (catalog lookup only;
           no live calls in G04).
        7. Compose the temporary mold from matched capabilities + gaps.
        8. Persist the mold recipe (state=temporary).

        Per owner decision: gaps are recorded honestly; no fabricated
        capabilities are inserted into the mold's capability_ids.
        """
        # ── Step 1: Detect ───────────────────────────────────────────────────
        detection = self.detector.detect(
            query, tenant_id=tenant_id, domain_hint=domain_hint
        )

        if not detection.is_unknown and detection.matched_molds:
            # Reuse path: return the best existing mold
            best = detection.matched_molds[0]
            mold = Mold.model_validate(best.payload)
            return self._record_reuse(
                query=query,
                tenant_id=tenant_id,
                investigation_id=investigation_id,
                mold_recipe_row=best,
                mold=mold,
                detected_needs=[],
                coverage=[],
                gaps=[],
                is_complete=True,
                composition_notes=(
                    f"Reused existing mold '{best.display_name}' "
                    f"(state={best.state}, domain={best.domain}). "
                    f"{detection.detection_reasoning}"
                ),
                is_unknown_domain=False,
                detection_reasoning=detection.detection_reasoning,
            )

        # ── Step 2: Decompose ───────────────────────────────────────────────
        decomposition = decompose_query(query, embedder=self.embedder)
        detected_needs = decomposition.detected_needs + decomposition.implicit_needs

        # ── Step 3: For each need, find a matching capability ─────────────────
        coverage: list[NeedCoverage] = []
        gaps: list[GapRecord] = []

        # Load all tenant's capabilities once
        all_caps_rows = list(
            self.db.execute(
                select(CapabilityRow).where(
                    CapabilityRow.tenant_id == tenant_id,
                    CapabilityRow.status.in_(self.capability_registry.SEARCHABLE_STATUSES),
                )
            ).scalars()
        )
        all_caps: dict[str, SearchCapability] = {
            row.id: row_to_capability(row) for row in all_caps_rows
        }

        for need in detected_needs:
            candidate_ids = NEED_TO_CAPABILITIES.get(need.need, [])
            # Filter to candidates that actually exist in this tenant
            available_candidates = [cid for cid in candidate_ids if cid in all_caps]

            if available_candidates:
                # Pick the first available candidate (G01-R1 logic picks
                # the best by positive-example similarity, but for mold
                # composition we accept any candidate that matches the need).
                selected_id = available_candidates[0]
                coverage.append(NeedCoverage(
                    need=need.need,
                    need_label=need.label_en,
                    need_relevance=need.relevance,
                    candidate_capability_ids=available_candidates,
                    selected_capability_id=selected_id,
                    selection_reasoning=(
                        f"Capability '{selected_id}' maps to need '{need.need}' "
                        f"(relevance={need.relevance:.2f}). "
                        f"{len(available_candidates)} candidate(s) available."
                    ),
                ))
            else:
                # Gap detected — invoke Foundry catalog lookup
                gap = self._attempt_foundry_resolution(
                    need=need,
                    candidate_ids=candidate_ids,
                    tenant_id=tenant_id,
                )
                gaps.append(gap)

        # ── Step 4: Compose the temporary mold ──────────────────────────────
        selected_capability_ids = [c.selected_capability_id for c in coverage if c.selected_capability_id]

        # Derive domain from the query (first significant word)
        domain = self._derive_domain(query)
        intent = query[:300]  # cap intent length

        # Generate a unique mold ID: domain + timestamp + short random suffix
        # to avoid collisions when two investigations compose in the same second.
        import secrets

        random_suffix = secrets.token_hex(4)
        mold_id = f"mold.{domain}-{int(datetime.now(UTC).timestamp())}-{random_suffix}"

        mold = Mold(
            id=mold_id,
            version="0.1.0",
            display_name=f"Temporary investigation mold for: {domain}",
            description_long=(
                f"Composed on {datetime.now(UTC).isoformat()} by the MoldArchitect. "
                f"Covers {len(selected_capability_ids)} of {len(detected_needs)} detected "
                f"research needs for the query: '{query}'. "
                f"{len(gaps)} gap(s) recorded explicitly — no fabricated capabilities."
            ),
            scope=MoldScope(
                domain=domain,
                intent=intent,
                geography=["global"],
                deliverables=["evidence_dossier", "scenario_report"],
            ),
            composition=MoldComposition(
                capability_ids=selected_capability_ids,
                agent_recipe_ids=[],  # G05 will populate this
                composition_notes=(
                    f"Composed from {len(coverage)} covered needs + {len(gaps)} gaps. "
                    "Gaps are recorded in mold_gap_analyses; the investigation report "
                    "must explicitly note the missing coverage."
                ),
                plan=[
                    {
                        "step": "acquire_evidence",
                        "capability_ids": selected_capability_ids,
                    },
                    {
                        "step": "curate_evidence",
                        "uses": "manara.memory.MemoryCurator",
                    },
                    {
                        "step": "report_gaps",
                        "gap_needs": [g.need for g in gaps],
                        "note": (
                            "These needs have no matching capability in the "
                            "registry. The investigation report must include "
                            "a 'coverage gaps' section."
                        ),
                    },
                ],
            ),
            state=MoldState.TEMPORARY,
        )

        # ── Step 5: Persist the mold recipe + gap analyses ─────────────────
        mold_row = MoldRecipeRow(
            id=mold.id,
            tenant_id=tenant_id,
            display_name=mold.display_name,
            description_long=mold.description_long,
            version=mold.version,
            schema_version=mold.schema_version,
            state=mold.state.value,
            domain=mold.scope.domain,
            intent=mold.scope.intent,
            sector=mold.scope.sector,
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

        # Persist gap analyses
        for gap in gaps:
            gap_row = GapAnalysisRow(
                tenant_id=tenant_id,
                mold_id=mold.id,
                investigation_id=investigation_id,
                need=gap.need,
                need_label=gap.need_label,
                candidate_capability_ids_json=gap.foundry_candidates_checked,
                status=gap.foundry_resolution,
                resolution_notes=gap.resolution_notes,
            )
            self.db.add(gap_row)

        self.db.commit()

        is_complete = len(gaps) == 0
        composition_notes = (
            f"Composed temporary mold '{mold.id}' with "
            f"{len(selected_capability_ids)} capabilities covering "
            f"{len(coverage)}/{len(detected_needs)} needs. "
            f"{len(gaps)} gap(s) recorded explicitly."
        )

        return MoldCompositionResult(
            query=query,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            is_unknown_domain=True,
            detection_reasoning=detection.detection_reasoning,
            detected_needs=detected_needs,
            coverage=coverage,
            gaps=gaps,
            mold=mold,
            mold_recipe_id=mold.id,
            is_complete=is_complete,
            composition_notes=composition_notes,
        )

    # ── Internals ─────────────────────────────────────────────────────────────

    def _attempt_foundry_resolution(
        self,
        *,
        need: DetectedNeed,
        candidate_ids: list[str],
        tenant_id: str,
    ) -> GapRecord:
        """Look up the Foundry catalog for sources that could satisfy this need.

        Per owner decision: "لا تتحايل عليها ببطاقة افتراضية تدّعي أنها محرك
        حقيقي." We do NOT fabricate a capability. We:
        1. List Foundry candidates whose primary_data_types match the need.
        2. If a candidate exists: record status=foundry_invoked (the Foundry
           sandbox test is deferred to G05+ when agents can execute it).
        3. If no candidate exists: record status=unresolved.
        """
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
                need=need.need,
                need_label=need.label_en,
                need_relevance=need.relevance,
                foundry_candidates_checked=matching_candidates,
                foundry_resolution="foundry_invoked",
                resolution_notes=(
                    f"Foundry catalog has {len(matching_candidates)} candidate(s) "
                    f"for need '{need.need}': {matching_candidates}. "
                    f"Sandbox testing + connector build is deferred to G05+. "
                    f"The mold is composed WITHOUT a capability for this need; "
                    f"the investigation report must note the coverage gap."
                ),
            )

        return GapRecord(
            need=need.need,
            need_label=need.label_en,
            need_relevance=need.relevance,
            foundry_candidates_checked=[],
            foundry_resolution="unresolved",
            resolution_notes=(
                f"No Foundry candidate available for need '{need.need}'. "
                f"The mold is composed WITHOUT a capability for this need; "
                f"the investigation report must explicitly note the missing coverage. "
                f"No fabricated capability inserted."
            ),
        )

    def _record_reuse(
        self,
        *,
        query: str,
        tenant_id: str,
        investigation_id: str | None,
        mold_recipe_row: MoldRecipeRow,
        mold: Mold,
        detected_needs: list[DetectedNeed],
        coverage: list[NeedCoverage],
        gaps: list[GapRecord],
        is_complete: bool,
        composition_notes: str,
        is_unknown_domain: bool,
        detection_reasoning: str,
    ) -> MoldCompositionResult:
        """Record that an existing mold was reused for this investigation."""
        if investigation_id is not None:
            reuse_row = MoldReuseRow(
                tenant_id=tenant_id,
                mold_id=mold_recipe_row.id,
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
            query=query,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            is_unknown_domain=is_unknown_domain,
            detection_reasoning=detection_reasoning,
            detected_needs=detected_needs,
            coverage=coverage,
            gaps=gaps,
            mold=mold,
            mold_recipe_id=mold_recipe_row.id,
            is_complete=is_complete,
            composition_notes=composition_notes,
        )

    @staticmethod
    def _derive_domain(query: str) -> str:
        """Derive a short domain label from the query.

        Picks the first significant word (≥4 chars, not a stopword).
        Falls back to 'custom' if no good word is found.
        """
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
    "GapRecord",
    "MoldArchitect",
    "MoldCompositionResult",
    "NeedCoverage",
]
