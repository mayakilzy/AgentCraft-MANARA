"""Unknown-domain detector — first step of the Mold Factory (G04).

Per ``03_INTELLIGENCE/03_AGENT_AND_MOLD_LIFECYCLE.md`` §Mold Architect:
> A new unfamiliar field must NOT be rejected solely for lacking a mold
> nor silently assigned a fictitious existing mold.

This module exposes ``UnknownDomainDetector`` which:
* Takes a research question + tenant_id.
* Searches the mold registry for an existing reusable/maintained mold
  whose domain or intent matches the question.
* Returns a ``DetectionResult`` that explicitly states whether the
  domain is known or unknown.

The detector does NOT fabricate a mold if none exists — it reports
"unknown" honestly. The MoldArchitect then takes over to compose a
temporary mold from existing capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from manara.db.mold_models import MoldRecipeRow


@dataclass
class DetectionResult:
    """Result of unknown-domain detection.

    ``is_unknown`` is True if NO existing mold (in reusable or maintained
    state) matches the query's domain. In that case the MoldArchitect
    must compose a temporary mold.

    ``matched_molds`` lists existing molds that could potentially satisfy
    the query (so the caller can reuse instead of composing fresh).
    """

    query: str
    tenant_id: str
    is_unknown: bool
    matched_molds: list[MoldRecipeRow] = field(default_factory=list)
    detection_reasoning: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class UnknownDomainDetector:
    """Detects whether a research question's domain is already covered
    by an existing mold recipe.

    The detector searches the mold_recipes table for any mold in
    ``reusable`` or ``maintained`` state (NOT ``temporary`` — temporary
    molds are investigation-specific, not domain-level recipes) whose
    domain or intent matches the query.

    Match strategy:
    1. Exact domain match (e.g. query mentions "waste recycling" →
       molds with domain="waste recycling").
    2. Keyword overlap: the query's tokens overlap with the mold's
       intent or description.

    The detector does NOT use embeddings here — that's the registry's
    job for capability search. Mold detection is intentionally simpler
    because the mold count is small (≤10 expected).
    """

    # Molds in these states are considered "existing" recipes
    EXISTING_STATES = ("reusable", "maintained")

    def __init__(self, db: Session) -> None:
        self.db = db

    def detect(
        self,
        query: str,
        *,
        tenant_id: str,
        domain_hint: str | None = None,
    ) -> DetectionResult:
        """Detect whether the query's domain is known or unknown.

        Args:
            query: the research question (natural language).
            tenant_id: tenant scoping (cross-tenant molds are invisible).
            domain_hint: optional explicit domain label (e.g. "waste-recycling").
              If provided, only matches molds with that exact domain.

        Returns:
            DetectionResult with is_unknown=True if no existing mold matches.
        """
        stmt = select(MoldRecipeRow).where(
            MoldRecipeRow.tenant_id == tenant_id,
            MoldRecipeRow.state.in_(self.EXISTING_STATES),
        )
        if domain_hint is not None:
            stmt = stmt.where(MoldRecipeRow.domain == domain_hint)

        candidates = list(self.db.execute(stmt).scalars())

        if not candidates:
            return DetectionResult(
                query=query,
                tenant_id=tenant_id,
                is_unknown=True,
                matched_molds=[],
                detection_reasoning=(
                    f"No mold recipe found in states={self.EXISTING_STATES} "
                    f"for tenant={tenant_id}"
                    + (f" with domain={domain_hint!r}" if domain_hint else " (any domain)")
                    + ". The MoldArchitect must compose a temporary mold."
                ),
            )

        # Score each candidate by token overlap with the query
        query_tokens = self._tokenize(query)
        scored: list[tuple[MoldRecipeRow, int]] = []
        for mold in candidates:
            intent_tokens = self._tokenize(mold.intent)
            desc_tokens = self._tokenize(mold.description_long)
            domain_tokens = self._tokenize(mold.domain)
            all_mold_tokens = intent_tokens | desc_tokens | domain_tokens
            overlap = len(query_tokens & all_mold_tokens)
            scored.append((mold, overlap))

        # Sort by overlap descending
        scored.sort(key=lambda x: x[1], reverse=True)
        best_mold, best_overlap = scored[0]

        # If best overlap is zero, the domain is effectively unknown
        if best_overlap == 0:
            return DetectionResult(
                query=query,
                tenant_id=tenant_id,
                is_unknown=True,
                matched_molds=[],
                detection_reasoning=(
                    f"Found {len(candidates)} existing mold(s) in tenant={tenant_id}, "
                    f"but none share any vocabulary with the query. "
                    f"Best candidate: '{best_mold.display_name}' (domain={best_mold.domain}, "
                    f"overlap=0). The MoldArchitect must compose a temporary mold."
                ),
            )

        # Otherwise: at least one mold has vocabulary overlap.
        # Return all molds with overlap > 0 as matched candidates.
        matched = [m for m, o in scored if o > 0]
        return DetectionResult(
            query=query,
            tenant_id=tenant_id,
            is_unknown=False,
            matched_molds=matched,
            detection_reasoning=(
                f"Found {len(matched)} existing mold(s) with vocabulary overlap. "
                f"Best match: '{best_mold.display_name}' (domain={best_mold.domain}, "
                f"overlap={best_overlap}). Reuse recommended."
            ),
        )

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        import re

        return {t for t in re.findall(r"\w+", text.lower(), flags=re.UNICODE) if len(t) >= 3}


__all__ = ["DetectionResult", "UnknownDomainDetector"]
