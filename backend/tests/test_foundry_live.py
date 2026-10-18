"""G02 LIVE test — real OpenAlex API call.

This test file makes REAL network calls to https://api.openalex.org.
It is the "permitted live provider call" required by G02 acceptance:

> "At least one real permitted source result with provenance, quarantine
> path and approved registry record; failed approvals cannot run."

These tests are marked ``live`` and should be run separately from the
unit suite:

    pytest tests/test_foundry_live.py -v -m live

To skip live tests in unit runs:

    pytest -m "not live"
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

from manara.db.session import Base

os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", "/home/z/my-project/.models")
os.environ.setdefault("HF_HOME", "/home/z/my-project/.models/hf_cache")


# Live tests are skipped by default; opt in with `--live` or RUN_LIVE_TESTS=1.
RUN_LIVE = os.environ.get("RUN_LIVE_TESTS", "0") == "1"

live_marker = pytest.mark.live
skip_if_not_live = pytest.mark.skipif(
    not RUN_LIVE,
    reason="Live tests require RUN_LIVE_TESTS=1 (they make real API calls).",
)


@pytest.fixture()
def db_session(engine) -> Iterator[Session]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


# ─────────────────────────────────────────────────────────────────────────────
# Live OpenAlex API call — the G02 acceptance proof
# ─────────────────────────────────────────────────────────────────────────────


@skip_if_not_live
class TestLiveOpenAlexCall:
    """Make a real call to OpenAlex and verify the result has provenance.

    This is the single most important test in G02 — it proves MANARA can
    retrieve real data from a real source, with all SSRF protections in
    place, and record the call in the Foundry evidence ledger.

    NOTE on rate limits: OpenAlex's free tier shares a daily budget across
    all users on the same IP. Search calls cost 10 credits each; single-work
    GETs cost 1 credit. When the shared budget is exhausted (HTTP 429),
    the search tests will be marked as skipped (not failed) with a clear
    reason. The single-work GET test is the canonical G02 acceptance
    proof — it always succeeds unless the IP is fully blocked.
    """

    def test_get_single_work_returns_real_record(self):
        """Live call: fetch a specific OpenAlex work by ID.

        This is the canonical G02 acceptance test — it proves MANARA can
        retrieve real data with provenance from a real source.

        Uses W2741809807 — a stable OpenAlex work ID (the OpenAlex team's
        own "State of OA" paper). If this ID is ever removed, the test
        will fail and should be updated to a different stable ID.
        """
        from manara.foundry import OpenAlexConnector

        with OpenAlexConnector() as conn:
            work, record = conn.get_work("W2741809807")
        assert record.status_code == 200, f"API call failed: {record.error}"
        assert work is not None
        assert work.openalex_id == "https://openalex.org/W2741809807"
        assert work.display_name or work.title, "work has no title/display_name"
        assert isinstance(work.cited_by_count, int)
        # Provenance: the call record must show the request was real
        assert record.url == "https://api.openalex.org/works/W2741809807"
        assert record.params.get("mailto")  # polite pool was used
        print(
            f"\n  ✓ Live OpenAlex get_work returned: "
            f"'{work.display_name or work.title}' (cited_by={work.cited_by_count}, "
            f"duration={record.duration_ms:.0f}ms)"
        )

    def test_search_works_returns_real_results(self):
        """Live call: search OpenAlex for a real query.

        This test may be skipped if OpenAlex's shared IP rate limit budget
        is exhausted (HTTP 429). The single-work GET test above is the
        canonical acceptance proof; this test is supplementary.
        """
        from manara.foundry import OpenAlexConnector

        with OpenAlexConnector() as conn:
            works, record = conn.search_works(
                "neural prosthetics brain computer interface",
                per_page=3,
            )
        if record.status_code == 429 or record.error == "rate_limited_after_retries":
            pytest.skip(
                "OpenAlex shared IP rate limit exhausted. "
                "Retry after midnight UTC reset, or set MANARA_OPENALEX_API_KEY."
            )
        assert record.status_code == 200, f"API call failed: {record.error}"
        assert record.error is None
        assert len(works) > 0, "Expected at least one work result"
        for w in works:
            assert w.openalex_id.startswith("https://openalex.org/W"), (
                f"openalex_id has unexpected shape: {w.openalex_id}"
            )
            assert isinstance(w.cited_by_count, int)
            assert w.title or w.display_name
        assert record.duration_ms < 30000.0
        assert record.params.get("mailto")
        print(
            f"\n  ✓ Live OpenAlex search returned {len(works)} works in "
            f"{record.duration_ms:.0f}ms (status={record.status_code})"
        )


@skip_if_not_live
class TestFoundrySandboxLive:
    """Run the full Foundry sandbox test pipeline with a real call.

    Per G02 acceptance: "At least one real permitted source result with
    provenance, quarantine path and approved registry record."
    """

    def test_full_sandbox_pipeline_with_real_call(self, db_session):
        from manara.foundry import FoundryService

        foundry = FoundryService(db_session)
        # 1. Discover
        foundry.discover_candidate("openalex", tenant_id="tenant_demo")
        # 2. Assess
        foundry.assess_candidate("openalex", tenant_id="tenant_demo")
        # 3. Register connector
        conn_row = foundry.register_connector("openalex", tenant_id="tenant_demo")
        assert conn_row.status == "candidate"
        # 4. Sandbox test — REAL call
        result = foundry.sandbox_test_candidate(
            "openalex",
            query="sodium-ion battery manufacturing",
            tenant_id="tenant_demo",
            per_page=3,
        )
        assert result.success, (
            f"Sandbox test failed: {result.error}; "
            f"sample_works={result.sample_works}"
        )
        assert result.work_count > 0
        assert len(result.sample_works) > 0
        # Each sample must carry provenance
        for sw in result.sample_works:
            assert sw["openalex_id"].startswith("https://openalex.org/W")
            assert "title" in sw or "doi" in sw
        # 5. After successful sandbox, the connector state must be sandbox_tested
        from manara.db.registry_models import ConnectorRow

        row = db_session.get(ConnectorRow, "openalex-v1")
        assert row.status == "sandbox_tested"

    def test_approval_after_successful_sandbox(self, db_session):
        """The full G02 acceptance: real call → sandbox_tested → approved."""
        from manara.foundry import FoundryService
        from manara.registry import SEED_CAPABILITIES, CapabilityRegistry

        # Seed the academic-publications capability so it can be linked to the connector
        reg = CapabilityRegistry(db_session)
        for cap in SEED_CAPABILITIES:
            try:
                reg.create_capability(cap, tenant_id="tenant_demo")
            except ValueError:
                pass  # already exists

        foundry = FoundryService(db_session)
        foundry.discover_candidate("openalex", tenant_id="tenant_demo")
        foundry.assess_candidate("openalex", tenant_id="tenant_demo")
        foundry.register_connector("openalex", tenant_id="tenant_demo")
        # Sandbox test
        result = foundry.sandbox_test_candidate(
            "openalex",
            query="prosthetics neural interface clinical trials",
            tenant_id="tenant_demo",
            per_page=3,
        )
        assert result.success, f"Sandbox test failed: {result.error}"
        # Owner approval
        approval = foundry.approve_candidate(
            "openalex",
            reviewer="ayman",
            rationale="Sandbox test passed with real OpenAlex call. CC0 license verified.",
            tenant_id="tenant_demo",
        )
        assert approval.new_status == "approved"
        assert approval.previous_status == "sandbox_tested"
        # Verify the capability is now linked to the connector
        from sqlalchemy import select

        from manara.db.registry_models import CapabilityRow

        cap_row = db_session.execute(
            select(CapabilityRow).where(CapabilityRow.id == "search.academic-publications")
        ).scalar_one_or_none()
        assert cap_row is not None
        assert "openalex-v1" in cap_row.connector_ids_json
        assert cap_row.status == "approved"

    def test_approval_fails_without_sandbox(self, db_session):
        """Per G02: 'failed approvals cannot run'."""
        from manara.foundry import FoundryService

        foundry = FoundryService(db_session)
        foundry.discover_candidate("openalex", tenant_id="tenant_demo")
        foundry.assess_candidate("openalex", tenant_id="tenant_demo")
        foundry.register_connector("openalex", tenant_id="tenant_demo")
        # Try to approve WITHOUT sandbox test
        with pytest.raises(ValueError, match="approval requires sandbox_tested"):
            foundry.approve_candidate(
                "openalex",
                reviewer="ayman",
                rationale="Approval without sandbox test must fail.",
                tenant_id="tenant_demo",
            )
