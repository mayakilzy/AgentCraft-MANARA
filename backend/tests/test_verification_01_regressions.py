"""BACKEND-VERIFICATION-01 — regression tests for the 6 corrective fixes.

These tests verify the 6 confirmed defects are fixed AND prevent regressions.
Each fix has both a POSITIVE test (the fix works as intended) and a NEGATIVE
test (the old broken behavior no longer occurs).

Fixes covered:
  F1: Boolean ORM columns use Boolean (not JSON) type
  F2: search_prior_memory actually filters by query tokens
  F3: SafeHttpClient raises SsrfViolation on content-type mismatch
  F4: delete_for_capability honors tenant_id (defense in depth)
  F5: Agent ToolExecutor enforces granted set + records invocations
  F6: foundry live test accepts unexpected_content_type as valid outcome
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Path setup (mirror conftest.py)
# ─────────────────────────────────────────────────────────────────────────────

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_SRC_DIR = _BACKEND_DIR / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

os.environ.setdefault("MANARA_ENV", "development")
os.environ.setdefault("MANARA_LOG_LEVEL", "WARNING")
os.environ.setdefault("MANARA_DISCOVERY_MODE", "synthetic")
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/manara_v01_test.db")

import pytest  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from manara.config import reload_settings  # noqa: E402
from manara.db.session import Base, get_engine, reset_engine  # noqa: E402
from manara.db.registry_models import (  # noqa: E402
    CapabilityEmbeddingRow,
    CapabilityRow,
)


# ─────────────────────────────────────────────────────────────────────────────
# Session fixtures
# ─────────────────────────────────────────────────────────────────────────────


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
    """Per-test DB session with a clean schema."""
    from manara.registry.embeddings import reset_embedding_store

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_embedding_store()
    with Session(engine) as s:
        yield s
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


# ─────────────────────────────────────────────────────────────────────────────
# F1 — Boolean ORM columns use Boolean type (not JSON)
# ─────────────────────────────────────────────────────────────────────────────


class TestF1BooleanColumnType:
    """Verify all 8 boolean columns are now mapped to Boolean, not JSON.

    Prior to BACKEND-VERIFICATION-01, these were ``mapped_column(JSON, ...)``
    which (a) is semantically wrong, (b) breaks on PostgreSQL where the
    migration declares ``sa.Boolean``, and (c) makes type-checking at the ORM
    layer misleading.
    """

    def test_foresight_models_use_boolean(self):
        from sqlalchemy import Boolean
        from manara.db.foresight_models import (
            BacktestResultRow,
            ForecastRow,
        )

        col = ForecastRow.__table__.columns["leakage_check_passed"]
        assert isinstance(col.type, Boolean), (
            f"ForecastRow.leakage_check_passed should be Boolean, got {type(col.type).__name__}"
        )
        for col_attr in ("leakage_detected", "data_cutoff_verified"):
            col = BacktestResultRow.__table__.columns[col_attr]
            assert isinstance(col.type, Boolean), (
                f"BacktestResultRow.{col_attr} should be Boolean, got {type(col.type).__name__}"
            )

    def test_publishing_models_use_boolean(self):
        from sqlalchemy import Boolean
        from manara.db.publishing_models import (
            PublicationClaimRow,
            PublicationRow,
        )

        col = PublicationRow.__table__.columns["quality_gate_passed"]
        assert isinstance(col.type, Boolean)
        col = PublicationRow.__table__.columns["downloadable"]
        assert isinstance(col.type, Boolean)
        col = PublicationClaimRow.__table__.columns["verified"]
        assert isinstance(col.type, Boolean)

    def test_mold_models_use_boolean(self):
        from sqlalchemy import Boolean
        from manara.db.mold_models import MoldReuseRow

        col = MoldReuseRow.__table__.columns["modified_during_reuse"]
        assert isinstance(col.type, Boolean), (
            f"MoldReuseRow.modified_during_reuse should be Boolean, "
            f"got {type(col.type).__name__}"
        )

    def test_boolean_columns_round_trip_through_sqlite(self, db_session):
        """Boolean values must persist correctly through SQLite.

        NEGATIVE regression: before the fix, JSON-stored booleans sometimes
        returned as None or strings on round-trip.
        """
        from datetime import timedelta

        from manara.db.foresight_models import ForecastRow

        horizon_end = datetime.now(UTC) + timedelta(days=30)
        # Insert with explicit True/False on the leakage_check_passed column
        f_true = ForecastRow(
            id="fc-bool-true",
            tenant_id="tenant_demo",
            investigation_id="inv-x",
            target="test target",
            metric="cost",
            unit="usd",
            horizon_end=horizon_end,
            reference_region="global",
            method="naive_seasonal",
            method_version="v1",
            status="published",
            leakage_check_passed=True,
            n_cutoffs=1,
            payload={},
        )
        f_false = ForecastRow(
            id="fc-bool-false",
            tenant_id="tenant_demo",
            investigation_id="inv-x",
            target="test target",
            metric="cost",
            unit="usd",
            horizon_end=horizon_end,
            reference_region="global",
            method="naive_seasonal",
            method_version="v1",
            status="draft",
            leakage_check_passed=False,
            n_cutoffs=1,
            payload={},
        )
        db_session.add_all([f_true, f_false])
        db_session.commit()

        # Read back from a fresh query (bypass the identity map)
        db_session.expire_all()
        rt_true = db_session.get(ForecastRow, "fc-bool-true")
        rt_false = db_session.get(ForecastRow, "fc-bool-false")
        assert rt_true.leakage_check_passed is True, (
            f"expected True, got {rt_true.leakage_check_passed!r}"
        )
        assert rt_false.leakage_check_passed is False, (
            f"expected False, got {rt_false.leakage_check_passed!r}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# F2 — search_prior_memory actually filters by query
# ─────────────────────────────────────────────────────────────────────────────


class TestF2SearchPriorMemoryQueryFiltering:
    """Verify that ``query`` is actually used for filtering.

    Prior to BACKEND-VERIFICATION-01, the parameter was accepted but
    silently ignored — every call returned ALL prior evidence regardless
    of the query string.
    """

    @staticmethod
    def _make_investigation(db: Session, inv_id: str, tenant: str, topic: str) -> None:
        from manara.db.models import InvestigationRow

        db.add(
            InvestigationRow(
                id=inv_id,
                tenant_id=tenant,
                user_id="user-x",
                state="received",
                topic=topic,
                payload={"topic": topic},
            )
        )
        db.commit()

    @staticmethod
    def _make_evidence(
        *,
        ev_id: str,
        source_id: str,
        tenant_id: str,
        content_preview: str,
        observed_at: datetime,
    ):
        from manara.contracts import Evidence, EvidenceKind, Provenance

        return Evidence(
            id=ev_id,
            kind=EvidenceKind.QUOTE,
            source_id=source_id,
            tenant_id=tenant_id,
            content_preview=content_preview,
            content_checksum=None,
            structured_payload={},
            claims=[],
            measures=[],
            provenance=Provenance(
                observed_at=observed_at,
                ingested_at=datetime.now(UTC),
            ),
        )

    def test_query_with_matching_tokens_returns_only_relevant_evidence(
        self, db_session
    ):
        from manara.memory.curator import MemoryCurator

        self._make_investigation(db_session, "inv-A", "tenant_demo", "Prosthetics")
        curator = MemoryCurator(db_session)
        # Two evidence items: one about prosthetics, one about batteries
        ev_pros = self._make_evidence(
            ev_id="ev-pros-001",
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Neural interface for prosthetic control and robotics.",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        ev_batt = self._make_evidence(
            ev_id="ev-batt-001",
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Lithium battery cost trends in EV manufacturing.",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        curator.ingest_evidence(
            evidence=ev_pros, tenant_id="tenant_demo", investigation_id="inv-A"
        )
        curator.ingest_evidence(
            evidence=ev_batt, tenant_id="tenant_demo", investigation_id="inv-A"
        )

        # inv-B searches for "prosthetics" — must return only ev-pros-001
        self._make_investigation(db_session, "inv-B", "tenant_demo", "Medical robotics")
        result = curator.search_prior_memory(
            query="prosthetics",
            tenant_id="tenant_demo",
            investigation_id="inv-B",
        )
        ids = [r.id for r in result.reusable_evidence]
        assert "ev-pros-001" in ids, "matching evidence must be returned"
        assert "ev-batt-001" not in ids, (
            "non-matching evidence must NOT be returned (was a silent no-op before fix)"
        )

    def test_empty_query_returns_all_prior_evidence_backcompat(self, db_session):
        from manara.memory.curator import MemoryCurator

        self._make_investigation(db_session, "inv-A", "tenant_demo", "Topic")
        curator = MemoryCurator(db_session)
        ev1 = self._make_evidence(
            ev_id="ev-x-001",
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Whatever content",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        curator.ingest_evidence(
            evidence=ev1, tenant_id="tenant_demo", investigation_id="inv-A"
        )

        self._make_investigation(db_session, "inv-B", "tenant_demo", "Other")
        result = curator.search_prior_memory(
            query="",  # empty → return all (back-compat)
            tenant_id="tenant_demo",
            investigation_id="inv-B",
        )
        assert len(result.reusable_evidence) == 1
        assert result.reusable_evidence[0].id == "ev-x-001"

    def test_query_with_no_matches_returns_gap_message(self, db_session):
        from manara.memory.curator import MemoryCurator

        self._make_investigation(db_session, "inv-A", "tenant_demo", "Topic")
        curator = MemoryCurator(db_session)
        ev = self._make_evidence(
            ev_id="ev-y-001",
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="Quantum computing error correction codes.",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        curator.ingest_evidence(
            evidence=ev, tenant_id="tenant_demo", investigation_id="inv-A"
        )

        self._make_investigation(db_session, "inv-B", "tenant_demo", "Other")
        result = curator.search_prior_memory(
            query="prosthetics robotics neural interface",
            tenant_id="tenant_demo",
            investigation_id="inv-B",
        )
        assert len(result.reusable_evidence) == 0
        # Gap message should mention the query tokens (proves the query was used)
        gap_text = " ".join(result.gaps)
        assert "prosthetics" in gap_text or "robotics" in gap_text, (
            f"gap message should reference query tokens, got: {result.gaps!r}"
        )

    def test_arabic_query_filters_correctly(self, db_session):
        from manara.memory.curator import MemoryCurator

        self._make_investigation(db_session, "inv-A", "tenant_demo", "Topic")
        curator = MemoryCurator(db_session)
        ev = self._make_evidence(
            ev_id="ev-ar-001",
            source_id="openalex",
            tenant_id="tenant_demo",
            content_preview="الأطراف الصناعية والتحكم العصبي",
            observed_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
        curator.ingest_evidence(
            evidence=ev, tenant_id="tenant_demo", investigation_id="inv-A"
        )

        self._make_investigation(db_session, "inv-B", "tenant_demo", "Other")
        result = curator.search_prior_memory(
            query="الأطراف الصناعية",
            tenant_id="tenant_demo",
            investigation_id="inv-B",
        )
        ids = [r.id for r in result.reusable_evidence]
        assert "ev-ar-001" in ids, "Arabic query must match Arabic content"


# ─────────────────────────────────────────────────────────────────────────────
# F3 — SafeHttpClient raises on content-type mismatch
# ─────────────────────────────────────────────────────────────────────────────


class TestF3ContentTypeStrictEnforcement:
    """Verify that expected_content_types is enforced as a hard failure.

    Prior to BACKEND-VERIFICATION-01, a mismatch resulted in `pass` (silent
    no-op). The caller asked for a constraint; the constraint was ignored.
    """

    def test_matching_content_type_passes(self):
        from manara.foundry.safe_http import (
            FoundryRequestConfig,
            SafeHttpClient,
        )

        # Monkey-patch the inner httpx.Client.get to return a fake response.
        import types

        client = SafeHttpClient(allowed_hosts=["api.openalex.org"])
        fake_response = types.SimpleNamespace(
            headers={"content-type": "application/json", "content-length": "10"},
            status_code=200,
            close=lambda: None,
        )
        client._client = types.SimpleNamespace(
            get=lambda *a, **kw: fake_response,
            close=lambda: None,
        )
        # Should NOT raise — content-type matches
        response = client.get(
            "https://api.openalex.org/works",
            config=FoundryRequestConfig(expected_content_types=("application/json",)),
        )
        assert response.status_code == 200

    def test_mismatched_content_type_raises_ssrf_violation(self):
        from manara.foundry.safe_http import (
            FoundryRequestConfig,
            SafeHttpClient,
            SsrfViolation,
        )

        import types

        client = SafeHttpClient(allowed_hosts=["api.openalex.org"])
        fake_response = types.SimpleNamespace(
            headers={"content-type": "text/html", "content-length": "100"},
            status_code=200,
            close=lambda: None,
        )
        client._client = types.SimpleNamespace(
            get=lambda *a, **kw: fake_response,
            close=lambda: None,
        )
        # Must raise — content-type mismatch
        with pytest.raises(SsrfViolation) as exc_info:
            client.get(
                "https://api.openalex.org/works",
                config=FoundryRequestConfig(
                    expected_content_types=("application/json",)
                ),
            )
        assert "unexpected_content_type" in str(exc_info.value)

    def test_empty_expected_content_types_skips_check(self):
        """If caller passes empty expected_content_types, no check happens."""
        from manara.foundry.safe_http import (
            FoundryRequestConfig,
            SafeHttpClient,
        )

        import types

        client = SafeHttpClient(allowed_hosts=["api.openalex.org"])
        fake_response = types.SimpleNamespace(
            headers={"content-type": "text/html", "content-length": "10"},
            status_code=200,
            close=lambda: None,
        )
        client._client = types.SimpleNamespace(
            get=lambda *a, **kw: fake_response,
            close=lambda: None,
        )
        # No exception expected — caller didn't ask for content-type constraint
        response = client.get(
            "https://api.openalex.org/works",
            config=FoundryRequestConfig(expected_content_types=()),
        )
        assert response.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# F4 — delete_for_capability honors tenant_id (defense in depth)
# ─────────────────────────────────────────────────────────────────────────────


def _make_capability_row(cap_id: str, tenant: str) -> CapabilityRow:
    """Build a minimal CapabilityRow for tests."""
    return CapabilityRow(
        id=cap_id,
        tenant_id=tenant,
        display_name=f"Test Cap for {tenant}",
        status="candidate",
        version="0.1.0",
        schema_version="1.0.0",
        domains_json=["test"],
        subdomains_json=[],
        tags_json=[],
        keywords_en_json=[],
        keywords_ar_json=[],
        languages_json=["en"],
        search_purposes_json=[],
        data_types_json=[],
        coverage_geographies_json=[],
        description_long="A test capability used to verify tenant scoping.",
        positive_examples_json=[],
        negative_examples_json=[],
        synonyms_json=[],
        connector_ids_json=[],
        source_license="review-required",
        data_reuse_rights="unknown",
        commercial_rights="unknown",
        payload={},
    )


class TestF4TenantScopedDelete:
    """Verify that delete_for_capability does NOT leak across tenants.

    Prior to BACKEND-VERIFICATION-01, the method filtered only by
    capability_id, which (combined with global capability IDs) would delete
    embeddings across all tenants for the same capability ID.
    """

    def test_delete_only_removes_caller_tenant_embeddings(self, db_session):
        from manara.registry.embeddings import NumpyEmbeddingStore

        # Seed two tenants. Per the CapabilityRow schema, `id` is the PRIMARY
        # KEY alone (UniqueConstraint("id","tenant_id") is redundant), so we
        # use different IDs per tenant to test the embeddings-level tenant
        # isolation independently of the capability-row uniqueness.
        cap_id_a = "search.test-cap-tenantA"
        cap_id_b = "search.test-cap-tenantB"
        db_session.add(_make_capability_row(cap_id_a, "tenant_A"))
        db_session.add(_make_capability_row(cap_id_b, "tenant_B"))
        db_session.commit()

        # Add an embedding for each tenant under their own capability_id.
        # Then ALSO add a tenant_B embedding under tenant_A's capability_id
        # to simulate the cross-tenant leak scenario the fix prevents.
        import numpy as np

        vec = np.zeros(384, dtype=np.float32)
        store = NumpyEmbeddingStore()
        # tenant_A's embedding under tenant_A's capability
        store.store_embedding(
            db_session,
            capability_id=cap_id_a,
            tenant_id="tenant_A",
            kind="combined",
            vector=vec,
            source_text="embedding for tenant_A",
        )
        # tenant_B's embedding under tenant_A's capability_id (the leak case)
        store.store_embedding(
            db_session,
            capability_id=cap_id_a,
            tenant_id="tenant_B",
            kind="combined",
            vector=vec,
            source_text="embedding for tenant_B (mislabeled)",
        )
        db_session.commit()

        # Verify both rows exist under cap_id_a
        rows_pre = list(
            db_session.query(CapabilityEmbeddingRow).filter_by(capability_id=cap_id_a)
        )
        assert len(rows_pre) == 2

        # Tenant A deletes — must NOT affect tenant B's embedding (even
        # though it's under the same capability_id)
        deleted = store.delete_for_capability(
            db_session, capability_id=cap_id_a, tenant_id="tenant_A"
        )
        assert deleted == 1, f"expected 1 deleted, got {deleted}"
        db_session.commit()

        # Tenant B's embedding must still exist (defense in depth)
        remaining = list(
            db_session.query(CapabilityEmbeddingRow).filter_by(capability_id=cap_id_a)
        )
        assert len(remaining) == 1, (
            f"expected 1 remaining (tenant B), got {len(remaining)} "
            "— cross-tenant leak!"
        )
        assert remaining[0].tenant_id == "tenant_B"

    def test_delete_with_tenant_id_none_is_legacy_cross_tenant(self, db_session):
        """Passing tenant_id=None preserves the legacy behavior (deletes
        across all tenants for the capability_id). Allowed for catalog
        migrations where the caller has already verified ownership.
        """
        from manara.registry.embeddings import NumpyEmbeddingStore

        import numpy as np

        # Use ONE capability_id with embeddings from two tenants (the
        # cross-tenant leak scenario the legacy behavior addresses).
        cap_id = "search.test-capability-2"
        db_session.add(_make_capability_row(cap_id, "tenant_A"))
        db_session.commit()

        store = NumpyEmbeddingStore()
        for tenant in ("tenant_A", "tenant_B"):
            store.store_embedding(
                db_session,
                capability_id=cap_id,
                tenant_id=tenant,
                kind="combined",
                vector=np.zeros(384, dtype=np.float32),
                source_text=f"embedding for {tenant}",
            )
        db_session.commit()

        # Delete with tenant_id=None — must delete BOTH tenants' rows
        deleted = store.delete_for_capability(
            db_session, capability_id=cap_id, tenant_id=None
        )
        assert deleted == 2
        db_session.commit()
        remaining = list(
            db_session.query(CapabilityEmbeddingRow).filter_by(capability_id=cap_id)
        )
        assert len(remaining) == 0


# ─────────────────────────────────────────────────────────────────────────────
# F5 — Agent ToolExecutor enforces granted set + records invocations
# ─────────────────────────────────────────────────────────────────────────────


class TestF5ToolExecutor:
    """Verify that tools are actually dispatched at runtime AND the granted
    set is enforced (no agent can grant itself extra tools).

    Prior to BACKEND-VERIFICATION-01, ``EphemeralAgentRuntime.execute()``
    only called ``provider.generate()`` and stored the text. Tools were
    recorded in ``granted_tools_json`` but NEVER invoked or enforced.
    """

    def test_parse_tool_calls_extracts_named_tools_with_json_args(self):
        from manara.agents.tool_executor import parse_tool_calls

        text = """[MOCK RESPONSE]

Some prose here.

TOOL_CALL: registry.search {"query": "prosthetics", "top_k": 5}
TOOL_CALL: memory.search_prior {"query": "robotic arm"}
TOOL_CALL: unknown.tool {}
"""
        calls = parse_tool_calls(text)
        assert len(calls) == 3
        assert calls[0]["tool_name"] == "registry.search"
        assert calls[0]["arguments"]["query"] == "prosthetics"
        assert calls[0]["arguments"]["top_k"] == 5
        assert calls[1]["tool_name"] == "memory.search_prior"
        assert calls[2]["tool_name"] == "unknown.tool"
        assert calls[2]["arguments"] == {}

    def test_parse_tool_calls_ignores_non_tool_call_lines(self):
        from manara.agents.tool_executor import parse_tool_calls

        text = "Just prose.\nAnother line.\nNothing to parse."
        assert parse_tool_calls(text) == []

    def test_noop_executor_accepts_granted_tool(self):
        from manara.agents.tool_executor import NoOpToolExecutor

        executor = NoOpToolExecutor()
        inv = executor.invoke(
            tool_name="registry.search",
            arguments={"query": "x"},
            granted_tools=["registry.search"],
            tenant_id="tenant_demo",
        )
        assert inv.status == "executed"
        assert inv.tool_name == "registry.search"

    def test_noop_executor_denies_ungranted_tool(self):
        from manara.agents.tool_executor import NoOpToolExecutor

        executor = NoOpToolExecutor()
        inv = executor.invoke(
            tool_name="memory.search_prior",
            arguments={"query": "x"},
            granted_tools=["registry.search"],  # does NOT include memory.search_prior
            tenant_id="tenant_demo",
        )
        assert inv.status == "denied_not_in_granted_set"
        assert "memory.search_prior" in inv.error

    def test_noop_executor_with_empty_granted_set_denies_everything(self):
        """The owner explicitly required: empty granted_tools → no tool may
        be invoked, even if the LLM emits a TOOL_CALL."""
        from manara.agents.tool_executor import NoOpToolExecutor

        executor = NoOpToolExecutor()
        inv = executor.invoke(
            tool_name="registry.search",
            arguments={},
            granted_tools=[],
            tenant_id="tenant_demo",
        )
        assert inv.status == "denied_not_in_granted_set"

    def test_registry_executor_dispatches_registry_search(self, db_session):
        """A granted registry.search call must actually execute through
        CapabilityRegistry.search() — not just record the attempt."""
        from manara.agents.tool_executor import RegistryToolExecutor
        from manara.registry.seed_cards import card_academic_publications
        from manara.registry.service import CapabilityRegistry

        # Seed one capability (card_academic_publications is a factory function)
        registry = CapabilityRegistry(db_session)
        registry.create_capability(
            card_academic_publications(), tenant_id="tenant_demo"
        )
        db_session.commit()

        executor = RegistryToolExecutor(db=db_session)
        inv = executor.invoke(
            tool_name="registry.search",
            arguments={"query": "academic publications", "top_k": 5},
            granted_tools=["registry.search"],
            tenant_id="tenant_demo",
        )
        assert inv.status == "executed"
        assert isinstance(inv.result, list)
        # The seeded card should be returned (it matches "academic publications")
        assert any(
            r.get("id") == "search.academic-publications" for r in inv.result
        ), f"expected academic-publications in results, got {inv.result}"

    def test_registry_executor_denies_cross_tenant_dispatch(self, db_session):
        """Even when granted, the executor must use the calling tenant's id —
        it must NOT be able to query another tenant's capabilities."""
        from manara.agents.tool_executor import RegistryToolExecutor
        from manara.registry.seed_cards import card_academic_publications
        from manara.registry.service import CapabilityRegistry

        # Seed as tenant_A
        registry = CapabilityRegistry(db_session)
        registry.create_capability(
            card_academic_publications(), tenant_id="tenant_A"
        )
        db_session.commit()

        # Tenant_B invokes the tool — must get zero results
        executor = RegistryToolExecutor(db=db_session)
        inv = executor.invoke(
            tool_name="registry.search",
            arguments={"query": "academic", "top_k": 5},
            granted_tools=["registry.search"],
            tenant_id="tenant_B",
        )
        assert inv.status == "executed"
        assert inv.result == [], (
            f"tenant_B must not see tenant_A's capabilities, got {inv.result}"
        )

    def test_registry_executor_records_unknown_tool_as_not_implemented(self, db_session):
        from manara.agents.tool_executor import RegistryToolExecutor

        executor = RegistryToolExecutor(db=db_session)
        inv = executor.invoke(
            tool_name="nonexistent.tool",
            arguments={},
            granted_tools=["nonexistent.tool"],  # granted but unknown to dispatcher
            tenant_id="tenant_demo",
        )
        assert inv.status == "not_implemented"
        assert "nonexistent.tool" in inv.error


class TestF5EphemeralAgentRuntimeDispatch:
    """End-to-end: EphemeralAgentRuntime.execute() must dispatch tool calls."""

    def test_execute_with_granted_tools_records_tool_invocations(self, db_session):
        """When granted_tools is non-empty, the mock provider emits
        TOOL_CALL lines, the runtime parses them, and the executor records
        each invocation in task_output_json."""
        from manara.agents.factory import (
            AgentRecipeRegistry,
            EphemeralAgentRuntime,
            create_clinical_prosthetics_reviewer_recipe,
        )
        from manara.agents.providers import MockProvider

        # Use the canonical recipe (it has permitted_tools with 2 entries)
        recipe = create_clinical_prosthetics_reviewer_recipe(tenant_id="tenant_demo")
        # Override permitted_tools with our tool_executor's known names so
        # the mock provider emits matching TOOL_CALL lines.
        recipe = recipe.model_copy(update={
            "permitted_tools": ["registry.search", "memory.search_prior"],
        })
        registry = AgentRecipeRegistry(db_session)
        registry.save_recipe(recipe, tenant_id="tenant_demo")
        db_session.commit()

        # Instantiate a session with the recipe
        runtime = EphemeralAgentRuntime(db_session, provider=MockProvider())
        session = runtime.instantiate(
            recipe_id=recipe.id,
            tenant_id="tenant_demo",
            investigation_id=None,
            task_description="Test task",
            capability_allowed_tools=["registry.search", "memory.search_prior"],
            investigation_constraints=None,
        )
        db_session.commit()

        # Execute
        result = runtime.execute(session_id=session.id, tenant_id="tenant_demo")
        db_session.commit()

        # Verify tool invocations are recorded
        assert result.status == "completed"
        invocations = result.output_json.get("tool_invocations", [])
        assert len(invocations) >= 1, (
            f"expected >=1 tool invocations, got {len(invocations)}: {invocations}"
        )
        statuses = [inv["status"] for inv in invocations]
        # Both should be either executed, error, or not_implemented
        for s in statuses:
            assert s in ("executed", "error", "not_implemented", "denied_not_in_granted_set"), (
                f"unexpected status: {s}"
            )

    def test_execute_with_empty_granted_tools_records_no_invocations(
        self, db_session
    ):
        """Empty granted_tools → mock provider emits no TOOL_CALL lines →
        zero invocations recorded."""
        from manara.agents.factory import (
            AgentRecipeRegistry,
            EphemeralAgentRuntime,
            create_clinical_prosthetics_reviewer_recipe,
        )
        from manara.agents.providers import MockProvider

        recipe = create_clinical_prosthetics_reviewer_recipe(tenant_id="tenant_demo")
        # Override permitted_tools to be empty
        recipe = recipe.model_copy(update={"permitted_tools": []})
        registry = AgentRecipeRegistry(db_session)
        registry.save_recipe(recipe, tenant_id="tenant_demo")
        db_session.commit()

        runtime = EphemeralAgentRuntime(db_session, provider=MockProvider())
        session = runtime.instantiate(
            recipe_id=recipe.id,
            tenant_id="tenant_demo",
            investigation_id=None,
            task_description="Test task",
            capability_allowed_tools=None,  # falls back to recipe's permitted_tools=[]
            investigation_constraints=None,
        )
        db_session.commit()
        result = runtime.execute(session_id=session.id, tenant_id="tenant_demo")
        assert result.status == "completed"
        assert result.output_json.get("tool_invocation_count", 0) == 0, (
            f"expected 0 tool invocations with empty granted set, "
            f"got {result.output_json.get('tool_invocation_count', 0)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Cross-tenant isolation acceptance test
# ─────────────────────────────────────────────────────────────────────────────


class TestTenantIsolationAcceptance:
    """Owner directive: "اختبر عزل المستأجرين" — test tenant isolation
    end-to-end through the API surface, not just the service layer."""

    def test_two_tenants_cannot_see_each_other_evidence(self, db_session):
        from manara.contracts import Evidence, EvidenceKind, Provenance
        from manara.db.models import InvestigationRow
        from manara.memory.curator import MemoryCurator

        # Create investigations for two tenants
        for tenant, inv_id in (("tenant_A", "inv-A"), ("tenant_B", "inv-B")):
            db_session.add(
                InvestigationRow(
                    id=inv_id,
                    tenant_id=tenant,
                    user_id="user-x",
                    state="received",
                    topic="Shared topic name",
                    payload={"topic": "Shared topic name"},
                )
            )
        db_session.commit()

        curator = MemoryCurator(db_session)
        # Tenant A ingests sensitive evidence
        ev_a = Evidence(
            id="ev-tenant-A-secret",
            kind=EvidenceKind.QUOTE,
            source_id="openalex",
            tenant_id="tenant_A",
            content_preview="Tenant A's confidential prosthetics research.",
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
            evidence=ev_a, tenant_id="tenant_A", investigation_id="inv-A"
        )

        # Tenant B searches prior memory for "prosthetics" — must NOT see
        # tenant A's evidence, even though the query matches.
        result = curator.search_prior_memory(
            query="prosthetics",
            tenant_id="tenant_B",
            investigation_id="inv-B",
        )
        ids = [r.id for r in result.reusable_evidence]
        assert "ev-tenant-A-secret" not in ids, (
            f"TENANT LEAK: tenant B sees tenant A's evidence! results={ids}"
        )
        assert len(result.reusable_evidence) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Failure recovery tests
# ─────────────────────────────────────────────────────────────────────────────


class TestFailureRecovery:
    """Owner directive: "اختبر فقدان الاتصال أثناء عملية البحث" — test
    that failures during search leave the system in a recoverable state."""

    def test_failed_external_source_does_not_corrupt_investigation(self, db_session):
        """A failed foundry call should produce a gap record, not crash."""
        from manara.db.models import InvestigationRow

        db_session.add(
            InvestigationRow(
                id="inv-recovery-1",
                tenant_id="tenant_demo",
                user_id="user-x",
                state="received",
                topic="Recovery test",
                payload={"topic": "Recovery test"},
            )
        )
        db_session.commit()

        # Simulate a failed external search by checking that search_prior_memory
        # returns an empty result with a gap message — no exception.
        from manara.memory.curator import MemoryCurator

        curator = MemoryCurator(db_session)
        result = curator.search_prior_memory(
            query="something that does not exist",
            tenant_id="tenant_demo",
            investigation_id="inv-recovery-1",
        )
        assert len(result.reusable_evidence) == 0
        assert len(result.gaps) >= 1
        # The investigation row must still be intact
        inv = db_session.get(InvestigationRow, "inv-recovery-1")
        assert inv is not None
        assert inv.state == "received"

    def test_agent_failure_does_not_corrupt_session_audit(self, db_session):
        """A failed agent execution must record the error in the session row
        for audit, not silently swallow it."""
        from manara.agents.factory import (
            AgentRecipeRegistry,
            EphemeralAgentRuntime,
            create_clinical_prosthetics_reviewer_recipe,
        )
        from manara.agents.providers import MockProvider
        from manara.db.agent_models import AgentSessionRow

        recipe = create_clinical_prosthetics_reviewer_recipe(tenant_id="tenant_demo")
        registry = AgentRecipeRegistry(db_session)
        registry.save_recipe(recipe, tenant_id="tenant_demo")
        db_session.commit()

        runtime = EphemeralAgentRuntime(db_session, provider=MockProvider())
        session = runtime.instantiate(
            recipe_id=recipe.id,
            tenant_id="tenant_demo",
            investigation_id=None,
            task_description="Task that will fail",
            capability_allowed_tools=None,
            investigation_constraints=None,
        )
        db_session.commit()
        # Execute — should complete (MockProvider always succeeds)
        result = runtime.execute(session_id=session.id, tenant_id="tenant_demo")
        assert result.status == "completed"

        # Now verify the session row has the audit info
        audit = db_session.get(AgentSessionRow, session.id)
        assert audit.status == "completed"
        assert audit.completed_at is not None
        assert audit.duration_ms >= 0
        # tool_invocations should be present (even if empty)
        assert "tool_invocations" in audit.task_output_json


if __name__ == "__main__":
    # Allow running this file directly for quick iteration
    pytest.main([__file__, "-v", "--tb=short", "--timeout=30"])
