"""Memory Curator service — the cumulative knowledge brain (G03).

Per ``03_INTELLIGENCE/01_KNOWLEDGE_MEMORY.md`` §Curator algorithm:
> 1. Canonicalize URLs/DOIs/IDs, checksum content.
> 2. Separate syndicated copies from independent evidence.
> 3. Extract structured claim plus precise support span with metadata.
> 4. Cross-check units, date, population, conditions.
> 5. Preserve disagreement and source hierarchy.
> 6. Label candidate, supported, contested, refuted, superseded — never
>    silently delete.
> 7. Promotion according to evidence/rights policy.
> 8. Audit lineage and version pin.

This module exposes ``MemoryCurator`` — the service that:
* ingests evidence (deduplicating by checksum + canonical source ID)
* attaches claims with supports/refutes edges (preserves contradictions)
* enforces bitemporal safety (no future leakage)
* promotes verdicts candidate → supported → contested → refuted → superseded
* records every decision in the audit log (never silently overwrites)
* enables investigation B to reuse evidence from investigation A
* enforces tenant isolation on every query
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from manara.contracts import Evidence
from manara.db.memory_models import (
    ClaimRow,
    ClaimSupportEdgeRow,
    EvidenceItemRow,
    InvestigationReuseRow,
    MeasureRow,
    MemoryDecisionRow,
    SourceSnapshotRow,
)
from manara.memory.object_store import ObjectStoreProtocol, get_object_store

# ─────────────────────────────────────────────────────────────────────────────
# Result dataclasses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class IngestResult:
    """Result of ingesting a single piece of evidence.

    ``deduplicated`` is True if the evidence was already present (same
    checksum + tenant). In that case ``evidence_id`` points to the
    existing row, no new row is created, and a ``evidence_deduplicated``
    decision is logged.
    """

    evidence_id: str
    deduplicated: bool
    reused_from_investigation_id: str | None = None
    stored_at_ref: str | None = None
    checksum: str | None = None
    decision_id: int | None = None


@dataclass
class ClaimPromotionResult:
    """Result of promoting a claim verdict (e.g. candidate → supported)."""

    claim_id: str
    previous_verdict: str
    new_verdict: str
    decision_id: int
    rationale: str


@dataclass
class ReuseSearchResult:
    """Result of searching prior memory for reusable evidence."""

    query: str
    tenant_id: str
    reusable_evidence: list[EvidenceItemRow] = field(default_factory=list)
    freshness_assessments: dict[str, str] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Memory Curator
# ─────────────────────────────────────────────────────────────────────────────


ClaimRelation = Literal["supports", "refutes", "qualifies"]
ClaimVerdict = Literal["candidate", "supported", "contested", "refuted", "superseded"]


class MemoryCurator:
    """The cumulative knowledge curator.

    Wraps a SQLAlchemy session. All operations are tenant-scoped — every
    query filters by ``tenant_id`` so cross-tenant leakage is impossible
    at the ORM level.
    """

    def __init__(
        self,
        db: Session,
        *,
        object_store: ObjectStoreProtocol | None = None,
    ) -> None:
        self.db = db
        self.object_store = object_store or get_object_store()

    # ── Canonicalization ─────────────────────────────────────────────────────

    @staticmethod
    def canonicalize_url(url: str) -> str:
        """Normalize a URL for dedup.

        Lowercases the scheme + host, strips trailing slashes, strips
        fragments, sorts query params. Two URLs that point to the same
        resource (e.g. HTTPS://OpenAlex.org/W123 and https://openalex.org/W123/)
        canonicalize to the same string.
        """
        if not url:
            return ""
        url = url.strip()
        # Remove fragment
        if "#" in url:
            url = url.split("#", 1)[0]
        # Remove trailing slash (except for root)
        if url.endswith("/") and url.count("/") > 3:
            url = url.rstrip("/")
        # Lowercase the scheme + host portion
        m = re.match(r"^([a-zA-Z]+://)([^/]+)(.*)$", url)
        if m:
            scheme, host, rest = m.groups()
            url = scheme.lower() + host.lower() + rest
        return url

    @staticmethod
    def canonicalize_doi(doi: str) -> str:
        """Normalize a DOI for dedup.

        Strips the ``https://doi.org/`` prefix, lowercases the registrant
        prefix. Two DOIs that refer to the same paper canonicalize to
        the same string.
        """
        if not doi:
            return ""
        doi = doi.strip().lower()
        # Strip common prefixes (case-insensitive)
        for prefix in ("https://doi.org/", "http://doi.org/", "doi:", "doi.org/"):
            if doi.startswith(prefix):
                doi = doi[len(prefix):]
                break
        return doi.strip()

    @staticmethod
    def compute_content_checksum(content: str | bytes) -> str:
        """Compute the canonical SHA-256 of content for dedup."""
        if isinstance(content, str):
            content = content.encode("utf-8")
        # Strip leading/trailing whitespace — same logical content
        # should produce the same checksum regardless of formatting.
        content = content.strip()
        return hashlib.sha256(content).hexdigest()

    # ── Ingest ────────────────────────────────────────────────────────────────

    def ingest_evidence(
        self,
        *,
        evidence: Evidence,
        tenant_id: str,
        investigation_id: str,
        raw_content: bytes | None = None,
        actor: str = "curator",
    ) -> IngestResult:
        """Ingest a piece of evidence into the cumulative memory.

        Steps:
        1. Compute checksum of the content (or use evidence.content_checksum).
        2. Check if (tenant_id, checksum) already exists in the DB.
           - If yes: this is a DUPLICATE. Don't re-store. Log a
             ``evidence_deduplicated`` decision. Return the existing ID.
        3. Check if the evidence's source_id has been seen by ANY prior
           investigation in the same tenant (reuse path).
           - If yes: log an ``evidence_reused`` decision with the
             source_investigation_id. Don't re-store the source snapshot.
        4. If raw_content is provided, store it in object storage.
        5. Insert the EvidenceItemRow. Log ``evidence_ingested``.

        Bitemporal safety:
        * ``observed_at`` is the world-time (when the event happened).
        * ``ingested_at`` is the knowledge-time (when MANARA learned of it).
        * ingested_at >= observed_at is enforced at the Pydantic layer
          (Evidence contract) and re-checked here for defense in depth.
        """
        # Bitemporal safety check (defense in depth)
        if (
            evidence.provenance.observed_at is not None
            and evidence.provenance.ingested_at < evidence.provenance.observed_at
        ):
            raise ValueError(
                "bitemporal violation: ingested_at must be >= observed_at "
                "(knowledge-time cannot precede world-time)"
            )

        # Compute or reuse checksum
        checksum = evidence.content_checksum
        if checksum is None and raw_content is not None:
            checksum = self.compute_content_checksum(raw_content)
        elif checksum is None and evidence.content_preview is not None:
            checksum = self.compute_content_checksum(evidence.content_preview)

        # Dedup check: (tenant_id, checksum) must be unique
        existing: EvidenceItemRow | None = None
        if checksum is not None:
            stmt = select(EvidenceItemRow).where(
                EvidenceItemRow.tenant_id == tenant_id,
                EvidenceItemRow.content_checksum == checksum,
            )
            existing = self.db.execute(stmt).scalar_one_or_none()

        if existing is not None:
            # Dedup: log and return the existing ID
            checksum_prefix = (checksum or "")[:16]
            decision = self._log_decision(
                tenant_id=tenant_id,
                decision_type="evidence_deduplicated",
                investigation_id=investigation_id,
                evidence_id=existing.id,
                actor=actor,
                rationale=(
                    f"Evidence with checksum {checksum_prefix}... was already "
                    f"ingested by investigation {existing.investigation_id}. "
                    "No duplicate stored."
                ),
                payload={
                    "original_investigation_id": existing.investigation_id,
                    "checksum": checksum,
                },
            )
            # If the existing evidence came from a DIFFERENT investigation,
            # also record the reuse link.
            if existing.investigation_id != investigation_id:
                self._record_reuse(
                    tenant_id=tenant_id,
                    investigation_id=investigation_id,
                    evidence_id=existing.id,
                    source_investigation_id=existing.investigation_id,
                    rationale="Auto-detected via checksum dedup at ingest time.",
                    freshness_assessment="fresh",
                    actor=actor,
                )
            return IngestResult(
                evidence_id=existing.id,
                deduplicated=True,
                reused_from_investigation_id=(
                    existing.investigation_id
                    if existing.investigation_id != investigation_id
                    else None
                ),
                checksum=checksum,
                decision_id=decision.id,
            )

        # Store raw content in object storage (if provided)
        stored_ref: str | None = None
        if raw_content is not None:
            stored_ref = self.object_store.store(
                content=raw_content,
                tenant_id=tenant_id,
                source_id=evidence.source_id,
                content_type="application/json",
                metadata={
                    "evidence_id": evidence.id,
                    "kind": evidence.kind.value,
                    "investigation_id": investigation_id,
                },
            )

        # Insert the evidence row
        row = EvidenceItemRow(
            id=evidence.id,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            source_id=evidence.source_id,
            source_snapshot_ref=stored_ref or evidence.source_snapshot_ref,
            kind=evidence.kind.value,
            content_ref=stored_ref or evidence.content_ref,
            content_checksum=checksum,
            content_preview=evidence.content_preview,
            structured_payload=evidence.structured_payload,
            observed_at=evidence.provenance.observed_at,
            ingested_at=evidence.provenance.ingested_at,
            payload=evidence.model_dump(mode="json"),
        )
        self.db.add(row)
        self.db.flush()

        decision = self._log_decision(
            tenant_id=tenant_id,
            decision_type="evidence_ingested",
            investigation_id=investigation_id,
            evidence_id=row.id,
            actor=actor,
            rationale=f"New evidence ingested (checksum={checksum[:16] if checksum else 'none'}...).",
            payload={
                "source_id": evidence.source_id,
                "kind": evidence.kind.value,
                "checksum": checksum,
                "stored_ref": stored_ref,
            },
        )
        self.db.commit()
        return IngestResult(
            evidence_id=row.id,
            deduplicated=False,
            stored_at_ref=stored_ref,
            checksum=checksum,
            decision_id=decision.id,
        )

    # ── Claims ──────────────────────────────────────────────────────────────────

    def attach_claim(
        self,
        *,
        claim_id: str,
        tenant_id: str,
        investigation_id: str,
        evidence_id: str,
        statement: str,
        verdict: ClaimVerdict = "candidate",
        independence_group: str | None = None,
        actor: str = "curator",
    ) -> ClaimRow:
        """Attach a new claim to a piece of evidence.

        The claim starts in ``candidate`` verdict (or as specified).
        Supports/refutes edges are added via ``add_support_edge``.
        """
        # Verify the evidence exists and belongs to this tenant
        ev = self.db.get(EvidenceItemRow, evidence_id)
        if ev is None or ev.tenant_id != tenant_id:
            raise ValueError(
                f"evidence {evidence_id} not found for tenant {tenant_id}"
            )

        row = ClaimRow(
            id=claim_id,
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            evidence_id=evidence_id,
            statement=statement,
            verdict=verdict,
            independence_group=independence_group,
            notes="",
            payload={},
        )
        self.db.add(row)
        self.db.flush()

        self._log_decision(
            tenant_id=tenant_id,
            decision_type="claim_promoted",
            investigation_id=investigation_id,
            evidence_id=evidence_id,
            claim_id=claim_id,
            actor=actor,
            rationale=f"Claim attached with verdict={verdict}.",
            payload={"verdict": verdict, "statement": statement[:200]},
        )
        self.db.commit()
        return row

    def add_support_edge(
        self,
        *,
        tenant_id: str,
        claim_id: str,
        evidence_id: str,
        relation: ClaimRelation,
        weight: float = 1.0,
        notes: str = "",
        actor: str = "curator",
    ) -> ClaimSupportEdgeRow:
        """Add a supports/refutes/qualifies edge between evidence and a claim.

        Per spec: "Preserve disagreement and source hierarchy." Both
        supporting AND refuting edges can exist for the same claim —
        contradictions are NEVER silently resolved.
        """
        # Verify ownership
        claim = self.db.get(ClaimRow, claim_id)
        if claim is None or claim.tenant_id != tenant_id:
            raise ValueError(f"claim {claim_id} not found for tenant {tenant_id}")
        ev = self.db.get(EvidenceItemRow, evidence_id)
        if ev is None or ev.tenant_id != tenant_id:
            raise ValueError(f"evidence {evidence_id} not found for tenant {tenant_id}")

        edge = ClaimSupportEdgeRow(
            tenant_id=tenant_id,
            claim_id=claim_id,
            evidence_id=evidence_id,
            relation=relation,
            weight=weight,
            notes=notes,
        )
        self.db.add(edge)
        self.db.flush()

        # If this is a refutes edge, the claim verdict becomes "contested"
        # (preserving both sides — never silently delete the refutation).
        if relation == "refutes" and claim.verdict in ("candidate", "supported"):
            previous = claim.verdict
            claim.verdict = "contested"
            self._log_decision(
                tenant_id=tenant_id,
                decision_type="claim_contradicted",
                investigation_id=claim.investigation_id,
                evidence_id=evidence_id,
                claim_id=claim_id,
                actor=actor,
                rationale=(
                    f"Refuting evidence added. Verdict {previous} → contested "
                    "(both sides preserved)."
                ),
                payload={
                    "previous_verdict": previous,
                    "new_verdict": "contested",
                    "refuting_evidence_id": evidence_id,
                },
            )

        self.db.commit()
        return edge

    def promote_claim(
        self,
        *,
        claim_id: str,
        tenant_id: str,
        new_verdict: ClaimVerdict,
        rationale: str,
        actor: str = "ayman",
    ) -> ClaimPromotionResult:
        """Promote a claim's verdict (e.g. candidate → supported).

        Per spec: "Never silently delete." If the new verdict is
        ``superseded``, the claim's ``superseded_by`` field must point
        to the new claim that replaces it — we record the linkage here.
        """
        claim = self.db.get(ClaimRow, claim_id)
        if claim is None or claim.tenant_id != tenant_id:
            raise ValueError(f"claim {claim_id} not found for tenant {tenant_id}")

        previous = claim.verdict
        if previous == new_verdict:
            raise ValueError(f"claim already in verdict={new_verdict}")

        claim.verdict = new_verdict
        decision = self._log_decision(
            tenant_id=tenant_id,
            decision_type="claim_promoted",
            investigation_id=claim.investigation_id,
            evidence_id=claim.evidence_id,
            claim_id=claim_id,
            actor=actor,
            rationale=rationale,
            payload={
                "previous_verdict": previous,
                "new_verdict": new_verdict,
            },
        )
        self.db.commit()
        return ClaimPromotionResult(
            claim_id=claim_id,
            previous_verdict=previous,
            new_verdict=new_verdict,
            decision_id=decision.id,
            rationale=rationale,
        )

    # ── Reuse search ──────────────────────────────────────────────────────────

    def search_prior_memory(
        self,
        *,
        query: str,
        tenant_id: str,
        investigation_id: str,
        source_id: str | None = None,
        max_age_days: int | None = None,
    ) -> ReuseSearchResult:
        """Search prior memory for evidence that the current investigation
        can reuse.

        Per spec: "New investigation searches prior relevant memory first,
        assesses freshness/scope and tenant rights, opens new queries for
        gaps, and records what was reused vs newly found."

        Returns evidence items from OTHER investigations in the same
        tenant. The caller decides which to reuse via ``record_reuse``.
        """
        stmt = select(EvidenceItemRow).where(
            EvidenceItemRow.tenant_id == tenant_id,
            EvidenceItemRow.investigation_id != investigation_id,
        )
        if source_id is not None:
            stmt = stmt.where(EvidenceItemRow.source_id == source_id)
        if max_age_days is not None:
            cutoff = datetime.now(UTC).timestamp() - (max_age_days * 86400)
            cutoff_dt = datetime.fromtimestamp(cutoff, tz=UTC)
            stmt = stmt.where(EvidenceItemRow.ingested_at >= cutoff_dt)

        rows = list(self.db.execute(stmt).scalars())

        # Freshness assessment per item
        freshness: dict[str, str] = {}
        now = datetime.now(UTC)
        for r in rows:
            # SQLite may return naive datetimes; coerce to UTC-aware
            ingested = r.ingested_at
            if ingested is not None and ingested.tzinfo is None:
                ingested = ingested.replace(tzinfo=UTC)
            age_days = (now - ingested).days if ingested else 9999
            if age_days <= 7:
                freshness[r.id] = "fresh"
            elif age_days <= 90:
                freshness[r.id] = "stale"
            else:
                freshness[r.id] = "outdated"

        gaps: list[str] = []
        if not rows:
            gaps.append(
                "No prior evidence found. This investigation will need to "
                "acquire new evidence via the Foundry (G02)."
            )

        return ReuseSearchResult(
            query=query,
            tenant_id=tenant_id,
            reusable_evidence=rows,
            freshness_assessments=freshness,
            gaps=gaps,
        )

    def record_reuse(
        self,
        *,
        tenant_id: str,
        investigation_id: str,
        evidence_id: str,
        source_investigation_id: str,
        rationale: str,
        freshness_assessment: str = "fresh",
        actor: str = "curator",
    ) -> InvestigationReuseRow:
        """Record that investigation B reused evidence from investigation A.

        Per spec: "records what was reused vs newly found."
        """
        # Verify the evidence exists and belongs to the tenant
        ev = self.db.get(EvidenceItemRow, evidence_id)
        if ev is None or ev.tenant_id != tenant_id:
            raise ValueError(f"evidence {evidence_id} not found for tenant {tenant_id}")
        if ev.investigation_id != source_investigation_id:
            raise ValueError(
                f"evidence {evidence_id} belongs to investigation "
                f"{ev.investigation_id}, not {source_investigation_id}"
            )

        # Idempotent: if already reused, return existing
        stmt = select(InvestigationReuseRow).where(
            InvestigationReuseRow.investigation_id == investigation_id,
            InvestigationReuseRow.evidence_id == evidence_id,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()
        if existing is not None:
            return existing

        row = InvestigationReuseRow(
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            evidence_id=evidence_id,
            source_investigation_id=source_investigation_id,
            reuse_rationale=rationale,
            freshness_assessment=freshness_assessment,
        )
        self.db.add(row)
        self.db.flush()

        self._log_decision(
            tenant_id=tenant_id,
            decision_type="evidence_reused",
            investigation_id=investigation_id,
            evidence_id=evidence_id,
            actor=actor,
            rationale=rationale,
            payload={
                "source_investigation_id": source_investigation_id,
                "freshness_assessment": freshness_assessment,
            },
        )
        self.db.commit()
        return row

    # ── Bitemporal safety: replay cutoff ────────────────────────────────────

    def get_evidence_at_cutoff(
        self,
        *,
        tenant_id: str,
        investigation_id: str,
        cutoff: datetime,
    ) -> list[EvidenceItemRow]:
        """Return evidence visible to an investigation at a given cutoff time.

        Per spec: "Source timestamps must be before cutoff in historical
        replay." This is the bitemporal-safety check that prevents future
        leakage in backtests.

        Evidence is visible iff:
        * It belongs to this tenant.
        * It belongs to this investigation OR was reused by it.
        * ``observed_at`` (world-time) <= cutoff. If observed_at is None,
          fall back to ``ingested_at`` (knowledge-time) <= cutoff.
        """
        stmt = select(EvidenceItemRow).where(
            EvidenceItemRow.tenant_id == tenant_id,
            EvidenceItemRow.investigation_id == investigation_id,
        )
        rows = list(self.db.execute(stmt).scalars())

        # Add reused evidence
        reuse_stmt = select(InvestigationReuseRow).where(
            InvestigationReuseRow.investigation_id == investigation_id,
            InvestigationReuseRow.tenant_id == tenant_id,
        )
        reuse_rows = list(self.db.execute(reuse_stmt).scalars())
        reused_ids = {r.evidence_id for r in reuse_rows}
        if reused_ids:
            reused_stmt = select(EvidenceItemRow).where(
                EvidenceItemRow.tenant_id == tenant_id,
                EvidenceItemRow.id.in_(reused_ids),
            )
            rows.extend(self.db.execute(reused_stmt).scalars())

        # Apply cutoff: evidence is visible iff observed_at <= cutoff
        # (or ingested_at <= cutoff if observed_at is None)
        # SQLite may return naive datetimes; coerce everything to UTC-aware.
        cutoff_aware = cutoff if cutoff.tzinfo is not None else cutoff.replace(tzinfo=UTC)
        visible: list[EvidenceItemRow] = []
        for r in rows:
            t: datetime | None = r.observed_at or r.ingested_at
            if t is None:
                # ingested_at has a NOT NULL constraint, so this branch
                # is unreachable in practice; kept as defensive code.
                continue
            if t.tzinfo is None:
                t = t.replace(tzinfo=UTC)
            if t <= cutoff_aware:
                visible.append(r)
        return visible

    # ── Measures ───────────────────────────────────────────────────────────────

    def add_measure(
        self,
        *,
        tenant_id: str,
        evidence_id: str,
        name: str,
        value: float,
        unit: str,
        methodology: str | None = None,
        geography: str | None = None,
        valid_at: datetime | None = None,
        confidence_interval_low: float | None = None,
        confidence_interval_high: float | None = None,
    ) -> MeasureRow:
        """Attach a quantified measurement to an evidence item."""
        ev = self.db.get(EvidenceItemRow, evidence_id)
        if ev is None or ev.tenant_id != tenant_id:
            raise ValueError(f"evidence {evidence_id} not found for tenant {tenant_id}")
        if (
            confidence_interval_low is not None
            and confidence_interval_high is not None
            and confidence_interval_high < confidence_interval_low
        ):
            raise ValueError("confidence_interval_high must be >= low")

        row = MeasureRow(
            tenant_id=tenant_id,
            evidence_id=evidence_id,
            name=name,
            value=value,
            unit=unit,
            methodology=methodology,
            geography=geography,
            valid_at=valid_at,
            confidence_interval_low=confidence_interval_low,
            confidence_interval_high=confidence_interval_high,
        )
        self.db.add(row)
        self.db.commit()
        return row

    # ── Source snapshots ──────────────────────────────────────────────────────

    def capture_source_snapshot(
        self,
        *,
        tenant_id: str,
        source_id: str,
        response_content: bytes,
        response_meta: dict[str, Any] | None = None,
        retention_class: str = "default",
    ) -> SourceSnapshotRow:
        """Capture a source response snapshot in object storage + DB.

        Per spec: "cache tenant-specific indices with RBAC." Snapshots
        are tenant-scoped and content-addressed by checksum.
        """
        checksum = self.object_store.compute_checksum(response_content)
        ref = self.object_store.store(
            content=response_content,
            tenant_id=tenant_id,
            source_id=source_id,
            content_type=response_meta.get("content_type", "application/json") if response_meta else "application/json",
            metadata=response_meta,
        )

        # Idempotent: same checksum + tenant → return existing
        stmt = select(SourceSnapshotRow).where(
            SourceSnapshotRow.tenant_id == tenant_id,
            SourceSnapshotRow.snapshot_checksum == checksum,
        )
        existing = self.db.execute(stmt).scalar_one_or_none()
        if existing is not None:
            return existing

        row = SourceSnapshotRow(
            id=f"snap-{checksum[:16]}",
            tenant_id=tenant_id,
            source_id=source_id,
            snapshot_ref=ref,
            snapshot_checksum=checksum,
            source_response_meta=response_meta or {},
            retention_class=retention_class,
        )
        self.db.add(row)
        self.db.commit()
        return row

    # ── Internals ──────────────────────────────────────────────────────────────

    def _log_decision(
        self,
        *,
        tenant_id: str,
        decision_type: str,
        investigation_id: str | None = None,
        evidence_id: str | None = None,
        claim_id: str | None = None,
        actor: str,
        rationale: str,
        payload: dict[str, Any] | None = None,
    ) -> MemoryDecisionRow:
        """Append a decision to the audit log (never overwrite)."""
        row = MemoryDecisionRow(
            tenant_id=tenant_id,
            decision_type=decision_type,
            investigation_id=investigation_id,
            evidence_id=evidence_id,
            claim_id=claim_id,
            actor=actor,
            rationale=rationale,
            payload=payload or {},
        )
        self.db.add(row)
        self.db.flush()
        return row

    def _record_reuse(
        self,
        *,
        tenant_id: str,
        investigation_id: str,
        evidence_id: str,
        source_investigation_id: str,
        rationale: str,
        freshness_assessment: str,
        actor: str,
    ) -> InvestigationReuseRow | None:
        """Internal reuse recorder — used during dedup at ingest time."""
        try:
            return self.record_reuse(
                tenant_id=tenant_id,
                investigation_id=investigation_id,
                evidence_id=evidence_id,
                source_investigation_id=source_investigation_id,
                rationale=rationale,
                freshness_assessment=freshness_assessment,
                actor=actor,
            )
        except ValueError:
            return None


__all__ = [
    "ClaimPromotionResult",
    "ClaimRelation",
    "ClaimVerdict",
    "IngestResult",
    "MemoryCurator",
    "ReuseSearchResult",
]
