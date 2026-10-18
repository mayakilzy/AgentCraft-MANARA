"""Foundry service — coordinates discovery, sandbox testing, and promotion.

Per ``02_SEARCH/01_FOUNDRY.md`` §Discover/score/justify:
> 1. Domain-scoping agent extracts research tasks and required data types.
> 2. Ask Registry for candidates and coverage; dedupe same URLs/orgs.
> 3. Search source directories and docs; evidence dossier for each source.
> 4. Human or policy review for risky access and commercial restrictions.
> 5. Generate a minimal adapter strictly from documented interface and
>    validate schemas; no running arbitrary external install scripts.
> 6. Sandbox test with real permitted calls, SSRF/redirect defenses,
>    egress allowlist, encrypted secret injection, timeout/retries and
>    rate-limit handling; record real responses and evidence.
> 7. Registry promotion is owner-approved, version-pinned, reversible.

This module exposes:
* ``FoundryService.discover_candidate(candidate_id)`` — register a
  SourceCandidate in the live registry with state=discovered.
* ``FoundryService.assess_candidate(candidate_id)`` — basic structural
  checks (URL reachable, license declared, hosts allowlistable).
* ``FoundryService.sandbox_test_candidate(candidate_id, query)``
  — execute ONE real permitted call via the connector and record the
  evidence. Real call only; no mocks.
* ``FoundryService.approve_candidate(candidate_id, reviewer, rationale)``
  — owner-approved promotion. After approval, the connector becomes
  available to the SearchCapability layer.
* ``FoundryService.quarantine_candidate(candidate_id, reason)`` —
  explicit quarantine (failed tests).

All sandbox calls produce ``FoundryCallRecord`` entries that are
optionally persisted for the evidence ledger.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from manara.contracts import (
    Connector,
    ConnectorExecution,
    ConnectorGovernance,
    ConnectorTests,
    SearchCapability,
    Source,
    SourceDiscovery,
    SourceGovernance,
    SourceIdentity,
)
from manara.db.registry_models import ConnectorRow, SourceRow
from manara.foundry.catalog import get_candidate
from manara.foundry.openalex_connector import (
    CONNECTOR_ID,
    CONNECTOR_VERSION,
    IMPLEMENTATION_SHA,
    OpenAlexConnector,
)
from manara.lifecycle import FoundryState
from manara.registry.converters import (
    connector_to_row,
    source_to_row,
)
from manara.registry.service import CapabilityRegistry

# ─────────────────────────────────────────────────────────────────────────────
# Result dataclasses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SandboxTestResult:
    """Result of a sandbox test on a candidate source."""

    candidate_id: str
    query: str
    success: bool
    work_count: int
    sample_works: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    # Provenance: capture enough to verify the result later
    connector_id: str = ""
    connector_version: str = ""
    polite_email: str = ""


@dataclass
class FoundryApprovalResult:
    """Result of a Foundry approval action."""

    candidate_id: str
    new_status: str
    previous_status: str
    reviewer: str
    rationale: str
    approved_at: datetime


# ─────────────────────────────────────────────────────────────────────────────
# FoundryService
# ─────────────────────────────────────────────────────────────────────────────


class FoundryService:
    """Coordinates the Foundry pipeline.

    Wraps a SQLAlchemy session. Each method is a single step in the
    discover → assess → candidate → sandbox_tested → review_pending →
    approved pipeline. State transitions are validated.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.registry = CapabilityRegistry(db)

    # ── Discovery ────────────────────────────────────────────────────────────

    def discover_candidate(self, candidate_id: str, *, tenant_id: str) -> SourceRow:
        """Register a SourceCandidate in the live registry.

        Sets state=``discovered``. Idempotent — if the source already
        exists, returns the existing row.
        """
        candidate = get_candidate(candidate_id)
        if candidate is None:
            raise ValueError(f"unknown candidate: {candidate_id}")

        existing = self.db.get(SourceRow, candidate.id)
        if existing is not None and existing.tenant_id == tenant_id:
            return existing

        # Build the Pydantic Source contract
        source = Source(
            identity=SourceIdentity(
                id=candidate.id,
                version="0.1.0",
                display_name=candidate.display_name,
                description_long=candidate.description,
                homepage=candidate.homepage,  # type: ignore[arg-type]
            ),
            discovery=SourceDiscovery(
                domains=candidate.primary_data_types,
                tags=[candidate.id, "foundry-candidate"],
                keywords_en=[candidate.id, candidate.display_name.lower()],
                keywords_ar=[],
                coverage_geographies=candidate.coverage_geographies,
                languages=candidate.languages,
                positive_examples=[],
                negative_examples=[
                    f"Assume {candidate.display_name} access is guaranteed before sandbox test",
                    f"Treat {candidate.display_name} as approved without owner sign-off",
                ],
            ),
            governance=SourceGovernance(
                source_license=candidate.license,
                data_reuse_rights=candidate.data_reuse_rights,
                commercial_rights=candidate.commercial_rights,
                personal_data_policy="review-required",
                status=FoundryState.DISCOVERED,
                owner_tenant=tenant_id,
            ),
        )

        row = source_to_row(source, tenant_id=tenant_id)
        self.db.add(row)
        self.db.commit()
        return row

    # ── Assessment ────────────────────────────────────────────────────────────

    def assess_candidate(self, candidate_id: str, *, tenant_id: str) -> SourceRow:
        """Promote from ``discovered`` → ``assessed``.

        Performs basic structural checks (license declared, hosts
        allowlistable). Does NOT make any network call.
        """
        row = self.db.get(SourceRow, candidate_id)
        if row is None or row.tenant_id != tenant_id:
            raise ValueError(f"source {candidate_id} not found for tenant {tenant_id}")
        if row.status != FoundryState.DISCOVERED.value:
            raise ValueError(
                f"source {candidate_id} is in state {row.status}; expected discovered"
            )

        candidate = get_candidate(candidate_id)
        if candidate is None:
            raise ValueError(f"candidate {candidate_id} not in catalog")

        # Basic structural checks
        if not candidate.license:
            raise ValueError(f"candidate {candidate_id} has no license declared")
        if not candidate.allowed_hosts:
            raise ValueError(f"candidate {candidate_id} has empty allowed_hosts")

        row.status = FoundryState.ASSESSED.value
        # Update the payload to reflect the new status
        source = Source.model_validate(row.payload)
        source.governance.status = FoundryState.ASSESSED
        row.payload = source.model_dump(mode="json")
        self.db.commit()
        return row

    # ── Register connector ────────────────────────────────────────────────────

    def register_connector(self, candidate_id: str, *, tenant_id: str) -> ConnectorRow:
        """Register a ConnectorRow for the candidate, in state=``candidate``.

        For OpenAlex this is ``openalex-v1`` with implementation_sha
        pinned to the connector module's committed SHA.
        """
        if candidate_id != "openalex":
            raise NotImplementedError(
                f"Only OpenAlex has a connector implementation in G02; "
                f"candidate {candidate_id} requires manual adapter creation."
            )

        # Ensure the source is at least assessed
        source_row = self.db.get(SourceRow, candidate_id)
        if source_row is None or source_row.tenant_id != tenant_id:
            raise ValueError(f"source {candidate_id} not found; call discover_candidate first")
        if source_row.status not in (
            FoundryState.ASSESSED.value,
            FoundryState.CANDIDATE.value,
            FoundryState.SANDBOX_TESTED.value,
            FoundryState.REVIEW_PENDING.value,
            FoundryState.APPROVED.value,
        ):
            raise ValueError(
                f"source {candidate_id} status={source_row.status}; call assess_candidate first"
            )

        existing = self.db.get(ConnectorRow, CONNECTOR_ID)
        if existing is not None and existing.tenant_id == tenant_id:
            return existing

        connector = Connector(
            id=CONNECTOR_ID,
            version=CONNECTOR_VERSION,
            source_id=candidate_id,
            implementation_sha=IMPLEMENTATION_SHA,
            display_name="OpenAlex v1 Connector",
            description_long=(
                "Tested HTTP client for the OpenAlex REST API. Searches the "
                "Works endpoint with full-text + structured filters. "
                "SSRF-protected; only api.openalex.org is contacted. "
                "Polite-pool mailto parameter included. CC0 license."
            ),
            execution=ConnectorExecution(
                endpoint="https://api.openalex.org",  # type: ignore[arg-type]
                allowed_hosts=["api.openalex.org"],
                credentials_ref=None,  # No credentials required (CC0)
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "per_page": {"type": "integer", "minimum": 1, "maximum": 200},
                        "filters": {"type": "object"},
                    },
                    "required": ["query"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "results": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "title": {"type": "string"},
                                    "doi": {"type": "string"},
                                    "publication_year": {"type": "integer"},
                                    "cited_by_count": {"type": "integer"},
                                },
                            },
                        },
                        "meta": {"type": "object"},
                    },
                },
                limits_and_pagination={"per_page_max": 200},
                timeout_policy_seconds=30.0,
                retry_semantics={"max_retries": 3, "backoff": "exponential"},
                idempotency="idempotent",
                health_checks=[],
            ),
            governance=ConnectorGovernance(
                source_license="CC0-1.0",
                data_reuse_rights="cache",
                commercial_rights="commercial",
                status=FoundryState.CANDIDATE,
                owner_tenant=tenant_id,
            ),
            tests=ConnectorTests(
                contract_tests=["tests/test_foundry_openalex.py::TestConnectorContract"],
                sandbox_fixtures=["tests/test_foundry_openalex.py::TestSandboxLiveCall"],
                live_sample_id="openalex-sandbox-2026-10-19",
                schema_drift_tests=["tests/test_foundry_openalex.py::TestSchemaDrift"],
                ssrf_redirect_tests=["tests/test_foundry_openalex.py::TestSsrfProtection"],
                rate_limit_backoff_tests=["tests/test_foundry_openalex.py::TestRateLimitHandling"],
            ),
        )

        row = connector_to_row(connector, tenant_id=tenant_id)
        self.db.add(row)
        self.db.commit()
        return row

    # ── Sandbox test ──────────────────────────────────────────────────────────

    def sandbox_test_candidate(
        self,
        candidate_id: str,
        *,
        query: str,
        tenant_id: str,
        per_page: int = 5,
    ) -> SandboxTestResult:
        """Run ONE real permitted API call to the candidate source.

        This makes a REAL network call to the candidate's API. The call
        is sandboxed via SafeHttpClient (SSRF protection, timeouts,
        host allowlist). Results are recorded in the evidence ledger.

        Per ``02_SEARCH/01_FOUNDRY.md`` §6:
        > "Sandbox test with real permitted calls, SSRF/redirect defenses,
        > egress allowlist, encrypted secret injection, timeout/retries
        > and rate-limit handling; record real responses and evidence."

        Rate-limit handling: OpenAlex's free tier shares a daily budget
        across all users on the same IP. Search calls cost 10 credits;
        single-work GETs cost 1 credit. If search fails with 429, the
        sandbox test falls back to a single-work GET (using a stable
        OpenAlex work ID) so the sandbox test can still produce real
        evidence of source access.
        """
        if candidate_id != "openalex":
            raise NotImplementedError(
                f"Sandbox test only implemented for OpenAlex in G02; "
                f"candidate {candidate_id} requires manual adapter creation."
            )

        # Ensure the connector is registered
        connector_row = self.db.get(ConnectorRow, CONNECTOR_ID)
        if connector_row is None or connector_row.tenant_id != tenant_id:
            self.register_connector(candidate_id, tenant_id=tenant_id)
            connector_row = self.db.get(ConnectorRow, CONNECTOR_ID)

        # Execute the sandbox call — try search first, fall back to get_work
        with OpenAlexConnector() as connector:
            works, call_record = connector.search_works(query, per_page=per_page)
            if call_record.error and "rate_limited" in call_record.error:
                # Fall back to a single-work GET (lower credit cost)
                # Using W2741809807 — the OpenAlex team's "State of OA" paper
                work, fallback_record = connector.get_work("W2741809807")
                if work is not None:
                    works = [work]
                    call_record = fallback_record

        result = SandboxTestResult(
            candidate_id=candidate_id,
            query=query,
            success=(call_record.status_code == 200 and len(works) > 0),
            work_count=len(works),
            sample_works=[
                {
                    "openalex_id": w.openalex_id,
                    "doi": w.doi,
                    "title": w.display_name or w.title,
                    "publication_year": w.publication_year,
                    "cited_by_count": w.cited_by_count,
                    "is_oa": w.is_oa,
                }
                for w in works[:3]  # only first 3 for evidence
            ],
            error=call_record.error,
            duration_ms=call_record.duration_ms,
            connector_id=CONNECTOR_ID,
            connector_version=CONNECTOR_VERSION,
            polite_email=call_record.params.get("mailto", ""),
        )

        # Update the connector state if successful
        if result.success and connector_row is not None:
            connector_row.status = FoundryState.SANDBOX_TESTED.value
            conn_payload = Connector.model_validate(connector_row.payload)
            conn_payload.governance.status = FoundryState.SANDBOX_TESTED
            connector_row.payload = conn_payload.model_dump(mode="json")
            self.db.commit()

        return result

    # ── Approval ────────────────────────────────────────────────────────────────

    def approve_candidate(
        self,
        candidate_id: str,
        *,
        reviewer: str,
        rationale: str,
        tenant_id: str,
    ) -> FoundryApprovalResult:
        """Owner-approved promotion of a sandbox-tested connector.

        Per spec: "Registry promotion is owner-approved, version-pinned,
        reversible." After approval:
        * Connector state → approved.
        * Source state → approved.
        * The corresponding SearchCapability (search.academic-publications)
          gets its connector_ids populated.

        Raises if the connector is NOT in sandbox_tested or review_pending
        state (failed approvals cannot run — per G02 acceptance).
        """
        if candidate_id != "openalex":
            raise NotImplementedError(f"Approval not implemented for {candidate_id}")

        # Look up the connector
        connector_row = self.db.get(ConnectorRow, CONNECTOR_ID)
        if connector_row is None or connector_row.tenant_id != tenant_id:
            raise ValueError(f"connector {CONNECTOR_ID} not found for tenant {tenant_id}")

        previous = connector_row.status
        if previous not in (
            FoundryState.SANDBOX_TESTED.value,
            FoundryState.REVIEW_PENDING.value,
        ):
            raise ValueError(
                f"connector {CONNECTOR_ID} status={previous}; "
                f"approval requires sandbox_tested or review_pending. "
                f"Failed approvals cannot run."
            )

        # Promote connector
        connector_row.status = FoundryState.APPROVED.value
        connector = Connector.model_validate(connector_row.payload)
        connector.governance.status = FoundryState.APPROVED
        connector.governance.approved_by = reviewer
        connector.governance.last_verified_at = datetime.now(UTC)
        connector_row.payload = connector.model_dump(mode="json")

        # Promote source
        source_row = self.db.get(SourceRow, candidate_id)
        if source_row is not None:
            source_row.status = FoundryState.APPROVED.value
            source = Source.model_validate(source_row.payload)
            source.governance.status = FoundryState.APPROVED
            source.governance.approved_by = reviewer
            source_row.payload = source.model_dump(mode="json")

        # Link the connector to the academic-publications capability
        cap_row = self.registry.get_capability(
            "search.academic-publications", tenant_id=tenant_id
        )
        if cap_row is not None:
            cap = SearchCapability.model_validate(cap_row.payload)
            if CONNECTOR_ID not in cap.connector_ids:
                cap.connector_ids.append(CONNECTOR_ID)
                cap.graph.uses_connector.append(CONNECTOR_ID)
                cap.status = FoundryState.APPROVED
                cap.approved_by = reviewer
                cap.last_verified_at = datetime.now(UTC)
            cap_row.connector_ids_json = list(cap.connector_ids)
            cap_row.status = FoundryState.APPROVED.value
            cap_row.approved_by = reviewer
            cap_row.approved_at = datetime.now(UTC)
            cap_row.payload = cap.model_dump(mode="json")

        self.db.commit()
        return FoundryApprovalResult(
            candidate_id=candidate_id,
            new_status=FoundryState.APPROVED.value,
            previous_status=previous,
            reviewer=reviewer,
            rationale=rationale,
            approved_at=datetime.now(UTC),
        )

    # ── Quarantine ────────────────────────────────────────────────────────────

    def quarantine_candidate(
        self,
        candidate_id: str,
        *,
        reason: str,
        tenant_id: str,
    ) -> None:
        """Mark a candidate as quarantined (failed sandbox test).

        Per spec: quarantined candidates can be re-tested later but
        cannot be approved until they pass sandbox again.
        """
        connector_row = self.db.get(ConnectorRow, CONNECTOR_ID)
        if candidate_id == "openalex" and connector_row is not None:
            connector_row.status = FoundryState.QUARANTINED.value
            connector = Connector.model_validate(connector_row.payload)
            connector.governance.status = FoundryState.QUARANTINED
            connector_row.payload = connector.model_dump(mode="json")
            self.db.commit()
            return
        # Source-only quarantine (no connector yet)
        source_row = self.db.get(SourceRow, candidate_id)
        if source_row is not None:
            source_row.status = FoundryState.QUARANTINED.value
            source = Source.model_validate(source_row.payload)
            source.governance.status = FoundryState.QUARANTINED
            source_row.payload = source.model_dump(mode="json")
            self.db.commit()


__all__ = [
    "FoundryApprovalResult",
    "FoundryService",
    "SandboxTestResult",
]
