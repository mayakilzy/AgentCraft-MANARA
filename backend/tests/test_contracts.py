"""Contract / schema tests for the eight MANARA typed contracts.

These tests assert:
* Each contract can be instantiated from a minimal valid payload.
* Pydantic validation rejects clearly-broken payloads.
* The JSON Schema generation succeeds (so external consumers can rely on it).
* Cross-contract invariants hold (e.g. Source governance requires approver
  when status==approved).
* Schema versions are pinned and stable.

These are *contract* tests, not unit tests — they validate the schema
boundary that downstream missions (G01+) will rely on.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from manara.contracts import (
    SCHEMA_VERSIONS,
    AgentRecipe,
    ClaimVerdict,
    Connector,
    Evidence,
    EvidenceKind,
    Forecast,
    Investigation,
    Measure,
    Mold,
    SearchCapability,
    Source,
    json_schemas,
)
from manara.lifecycle import (
    AgentState,
    FoundryState,
    InvestigationState,
    MoldState,
)

# ─────────────────────────────────────────────────────────────────────────────
# Source
# ─────────────────────────────────────────────────────────────────────────────


def _minimal_source_payload() -> dict:
    return {
        "identity": {
            "id": "openalex",
            "version": "0.1.0",
            "display_name": "OpenAlex",
            "description_long": "Open scholarly metadata catalog covering works, authors, institutions.",
            "homepage": "https://openalex.org",
        },
        "discovery": {
            "domains": ["academic"],
            "tags": ["publications", "citations"],
            "keywords_en": ["publications", "works"],
            "keywords_ar": ["منشورات"],
            "positive_examples": ["Find papers about sodium-ion batteries"],
            "negative_examples": ["Use as proof of clinical efficacy"],
            "coverage_geographies": ["global"],
            "languages": ["en"],
        },
        "governance": {
            "source_license": "CC0",
            "data_reuse_rights": "cache",
            "commercial_rights": "commercial",
            "status": "discovered",
        },
    }


class TestSource:
    def test_minimal_source_is_valid(self) -> None:
        s = Source(**_minimal_source_payload())
        assert s.identity.id == "openalex"
        assert s.identity.kind == "source"
        assert s.governance.status == FoundryState.DISCOVERED

    def test_invalid_id_pattern(self) -> None:
        p = _minimal_source_payload()
        p["identity"]["id"] = "OpenAlex!"  # uppercase + symbol
        with pytest.raises(ValidationError):
            Source(**p)

    def test_approved_requires_approver(self) -> None:
        p = _minimal_source_payload()
        p["governance"]["status"] = "approved"
        with pytest.raises(ValidationError, match="approved_by"):
            Source(**p)

    def test_extra_field_rejected(self) -> None:
        p = _minimal_source_payload()
        p["identity"]["unexpected"] = "boom"
        with pytest.raises(ValidationError):
            Source(**p)

    def test_timestamps_default_to_utc_now(self) -> None:
        s = Source(**_minimal_source_payload())
        assert s.created_at.tzinfo is not None
        assert s.updated_at >= s.created_at


# ─────────────────────────────────────────────────────────────────────────────
# Connector
# ─────────────────────────────────────────────────────────────────────────────


def _minimal_connector_payload() -> dict:
    return {
        "id": "openalex-v1",
        "version": "0.1.0",
        "source_id": "openalex",
        "implementation_sha": "abc1234def",
        "display_name": "OpenAlex v1 Connector",
        "description_long": "Tested HTTP client for the OpenAlex REST API with pagination and rate limiting.",
        "execution": {
            "endpoint": "https://api.openalex.org",
            "allowed_hosts": ["api.openalex.org"],
            "input_schema": {},
            "output_schema": {},
            "limits_and_pagination": {"per_page": 25},
            "timeout_policy_seconds": 30.0,
            "retry_semantics": {"max_retries": 3, "backoff": "exponential"},
            "idempotency": "idempotent",
            "health_checks": [],
        },
        "governance": {
            "source_license": "CC0",
            "status": "discovered",
        },
        "tests": {"contract_tests": ["test_basic_query"]},
    }


class TestConnector:
    def test_minimal_connector_is_valid(self) -> None:
        c = Connector(**_minimal_connector_payload())
        assert c.id == "openalex-v1"
        assert c.source_id == "openalex"
        assert c.execution.idempotency == "idempotent"

    def test_implementation_sha_min_length(self) -> None:
        p = _minimal_connector_payload()
        p["implementation_sha"] = "abc"  # too short
        with pytest.raises(ValidationError):
            Connector(**p)

    def test_approved_requires_approver(self) -> None:
        p = _minimal_connector_payload()
        p["governance"]["status"] = "approved"
        with pytest.raises(ValidationError, match="approved_by"):
            Connector(**p)

    def test_credentials_ref_is_string_not_dict(self) -> None:
        """The connector must NOT carry raw credentials — only a vault ref."""
        p = _minimal_connector_payload()
        p["execution"]["credentials_ref"] = "vault://openalex/anon"
        c = Connector(**p)
        assert c.execution.credentials_ref == "vault://openalex/anon"
        # A dict would be rejected because the field is typed ``str | None``.
        p["execution"]["credentials_ref"] = {"token": "secret"}  # type: ignore[assignment]
        with pytest.raises(ValidationError):
            Connector(**p)


# ─────────────────────────────────────────────────────────────────────────────
# SearchCapability
# ─────────────────────────────────────────────────────────────────────────────


def _minimal_capability_payload() -> dict:
    return {
        "id": "search.battery-publications",
        "version": "0.1.0",
        "display_name": "Battery Publications Search",
        "description_long": "Logical capability profile for retrieving academic publications about batteries.",
        "domains": ["energy"],
        "keywords_en": ["battery", "publications"],
        "keywords_ar": ["بطاريات"],
        "positive_examples": ["Find sodium-ion battery papers 2020-2025"],
        "negative_examples": ["Prove a battery is safe"],
        "search_purposes": ["discovery"],
        "data_types": ["academic-publications"],
        "connector_ids": ["openalex-v1"],
        "graph": {"uses_connector": ["openalex-v1"]},
        "status": "discovered",
        "source_license": "review-required",
    }


class TestSearchCapability:
    def test_minimal_capability_is_valid(self) -> None:
        c = SearchCapability(**_minimal_capability_payload())
        assert c.id == "search.battery-publications"
        assert c.kind == "search-engine"

    def test_invalid_id_prefix(self) -> None:
        p = _minimal_capability_payload()
        p["id"] = "battery-publications"  # missing search. prefix
        with pytest.raises(ValidationError):
            SearchCapability(**p)

    def test_connector_ids_must_match_graph(self) -> None:
        p = _minimal_capability_payload()
        p["connector_ids"] = ["openalex-v1", "crossref-v1"]
        p["graph"]["uses_connector"] = ["openalex-v1"]
        with pytest.raises(ValidationError, match="graph.uses_connector"):
            SearchCapability(**p)

    def test_connector_ids_auto_populate_graph(self) -> None:
        """If connector_ids set and graph.uses_connector empty, populate it."""
        p = _minimal_capability_payload()
        p["graph"]["uses_connector"] = []
        c = SearchCapability(**p)
        assert c.graph.uses_connector == ["openalex-v1"]


# ─────────────────────────────────────────────────────────────────────────────
# Mold
# ─────────────────────────────────────────────────────────────────────────────


def _minimal_mold_payload() -> dict:
    return {
        "id": "mold.recycling-2026-001",
        "version": "0.1.0",
        "display_name": "Recycling Investigation Mold",
        "description_long": "Temporary mold for assessing worldwide recycling technologies through 2035.",
        "scope": {
            "domain": "waste",
            "intent": "Assess worldwide recycling technologies and market direction to 2035.",
            "geography": ["global"],
            "deliverables": ["evidence_dossier", "scenario_report"],
        },
        "composition": {
            "capability_ids": ["search.battery-publications"],
        },
        "state": "temporary",
    }


class TestMold:
    def test_minimal_mold_is_valid(self) -> None:
        m = Mold(**_minimal_mold_payload())
        assert m.id == "mold.recycling-2026-001"
        assert m.state == MoldState.TEMPORARY

    def test_maintained_requires_last_piloted_at(self) -> None:
        p = _minimal_mold_payload()
        p["state"] = "maintained"
        with pytest.raises(ValidationError, match="last_piloted_at"):
            Mold(**p)

    def test_archived_only_when_state_archived(self) -> None:
        p = _minimal_mold_payload()
        p["archived_at"] = datetime.now(UTC).isoformat()
        with pytest.raises(ValidationError):
            Mold(**p)


# ─────────────────────────────────────────────────────────────────────────────
# AgentRecipe
# ─────────────────────────────────────────────────────────────────────────────


def _minimal_agent_payload() -> dict:
    return {
        "id": "agent.clinical-reviewer-v1",
        "version": "0.1.0",
        "display_name": "Clinical Reviewer (on-demand)",
        "description_long": "Specialist agent for reviewing clinical-trial evidence and regulatory approvals.",
        "role": "clinical_reviewer",
        "permitted_tools": ["search.clinical-trials"],
        "system_prompt": "You are a clinical reviewer. Always cite the trial registry ID.",
        "model_compatibility": ["zai:glm-4.6"],
        "state": "on_demand",
    }


class TestAgentRecipe:
    def test_minimal_agent_is_valid(self) -> None:
        a = AgentRecipe(**_minimal_agent_payload())
        assert a.id == "agent.clinical-reviewer-v1"
        assert a.state == AgentState.ON_DEMAND

    def test_tested_state_requires_evaluation_outcome(self) -> None:
        p = _minimal_agent_payload()
        p["state"] = "tested"
        with pytest.raises(ValidationError, match="last_evaluation_outcome"):
            AgentRecipe(**p)

    def test_maintained_requires_security_review(self) -> None:
        p = _minimal_agent_payload()
        p["state"] = "maintained"
        p["tests"] = {"last_evaluation_outcome": "passed"}
        with pytest.raises(ValidationError, match="security_review"):
            AgentRecipe(**p)


# ─────────────────────────────────────────────────────────────────────────────
# Evidence
# ─────────────────────────────────────────────────────────────────────────────


def _minimal_evidence_payload() -> dict:
    return {
        "id": "ev-001",
        "kind": "quote",
        "source_id": "openalex",
        "tenant_id": "tenant_demo",
        "content_preview": "Lithium-ion cell cost dropped to $100/kWh in 2023.",
        "claims": [
            {
                "id": "claim-001",
                "statement": "Li-ion cell cost reached $100/kWh in 2023.",
            }
        ],
        "provenance": {
            "observed_at": "2023-06-01T00:00:00+00:00",
        },
    }


class TestEvidence:
    def test_minimal_evidence_is_valid(self) -> None:
        e = Evidence(**_minimal_evidence_payload())
        assert e.kind == EvidenceKind.QUOTE
        assert e.tenant_id == "tenant_demo"
        assert e.claims[0].verdict == ClaimVerdict.CANDIDATE

    def test_ingested_at_must_be_after_observed_at(self) -> None:
        """Bitemporal safety: knowledge-time cannot precede world-time."""
        p = _minimal_evidence_payload()
        p["provenance"] = {
            "observed_at": "2030-01-01T00:00:00+00:00",  # future
            "ingested_at": "2020-01-01T00:00:00+00:00",  # past
        }
        with pytest.raises(ValidationError, match="ingested_at must be >= observed_at"):
            Evidence(**p)

    def test_measure_ci_sanity(self) -> None:
        m = Measure(name="cost", value=100.0, unit="USD/kWh",
                    confidence_interval_low=80.0, confidence_interval_high=120.0)
        assert m.confidence_interval_high == 120.0
        with pytest.raises(ValidationError):
            Measure(name="cost", value=100.0, unit="USD/kWh",
                    confidence_interval_low=120.0, confidence_interval_high=80.0)


# ─────────────────────────────────────────────────────────────────────────────
# Forecast
# ─────────────────────────────────────────────────────────────────────────────


def _minimal_forecast_payload() -> dict:
    return {
        "id": "fc-001",
        "investigation_id": "inv-001",
        "tenant_id": "tenant_demo",
        "target": "Global average Li-ion pack price per kWh by 2027",
        "metric": "price",
        "unit": "USD/kWh",
        "horizon_end": "2027-12-31T00:00:00+00:00",
        "reference_region": "global",
        "method": "trend_ets",
        "method_version": "0.1.0",
        "cutoff_date": "2024-01-01T00:00:00+00:00",
    }


class TestForecast:
    def test_minimal_forecast_is_valid(self) -> None:
        f = Forecast(**_minimal_forecast_payload())
        assert f.status == "draft"

    def test_insufficient_evidence_forbids_probability_distribution(self) -> None:
        p = _minimal_forecast_payload()
        p["method"] = "insufficient_evidence"
        p["probability_distribution"] = {"mean": 100.0}
        with pytest.raises(ValidationError, match="insufficient_evidence"):
            Forecast(**p)

    def test_published_requires_issue_date(self) -> None:
        p = _minimal_forecast_payload()
        p["status"] = "published"
        with pytest.raises(ValidationError, match="issue_date"):
            Forecast(**p)

    def test_published_requires_cutoff_date(self) -> None:
        """Replay safety: backtests MUST NOT see past the cutoff."""
        p = _minimal_forecast_payload()
        p["status"] = "published"
        p["issue_date"] = "2024-06-01T00:00:00+00:00"
        p["cutoff_date"] = None
        with pytest.raises(ValidationError, match="cutoff_date"):
            Forecast(**p)

    def test_cutoff_must_precede_issue_date(self) -> None:
        """No future leakage: cutoff_date <= issue_date."""
        p = _minimal_forecast_payload()
        p["status"] = "published"
        p["issue_date"] = "2024-01-01T00:00:00+00:00"
        p["cutoff_date"] = "2024-06-01T00:00:00+00:00"  # after issue_date
        with pytest.raises(ValidationError, match="cutoff_date must be <= issue_date"):
            Forecast(**p)


# ─────────────────────────────────────────────────────────────────────────────
# Investigation
# ─────────────────────────────────────────────────────────────────────────────


def _minimal_investigation_payload() -> dict:
    return {
        "id": "inv-001",
        "tenant_id": "tenant_demo",
        "user_id": "user-001",
        "scope": {
            "topic": "Future of waste recycling technologies",
            "geography": ["global"],
            "deliverables": ["evidence_dossier"],
        },
    }


class TestInvestigation:
    def test_minimal_investigation_is_valid(self) -> None:
        inv = Investigation(**_minimal_investigation_payload())
        assert inv.state == InvestigationState.RECEIVED
        assert inv.tenant_id == "tenant_demo"

    def test_invalid_state_transition(self) -> None:
        p = _minimal_investigation_payload()
        p["checkpoints"] = [
            {"state": "received"},
            {"state": "archived"},  # invalid jump
        ]
        with pytest.raises(ValidationError, match="invalid transition"):
            Investigation(**p)

    def test_final_checkpoint_must_match_state(self) -> None:
        p = _minimal_investigation_payload()
        p["state"] = "scoped"
        p["checkpoints"] = [{"state": "received"}]  # mismatch
        with pytest.raises(ValidationError, match="final checkpoint state must match"):
            Investigation(**p)

    def test_valid_walk(self) -> None:
        p = _minimal_investigation_payload()
        p["state"] = "scoped"
        p["checkpoints"] = [
            {"state": "received"},
            {"state": "scoped"},
        ]
        inv = Investigation(**p)
        assert inv.state == InvestigationState.SCOPED


# ─────────────────────────────────────────────────────────────────────────────
# Schema stability
# ─────────────────────────────────────────────────────────────────────────────


class TestSchemaStability:
    def test_eight_schemas_present(self) -> None:
        schemas = json_schemas()
        expected = {
            "Source",
            "Connector",
            "SearchCapability",
            "Mold",
            "AgentRecipe",
            "Evidence",
            "Forecast",
            "Investigation",
        }
        assert set(schemas.keys()) == expected

    def test_schema_versions_pinned(self) -> None:
        for name, version in SCHEMA_VERSIONS.items():
            assert version == "1.0.0", f"{name} has unexpected schema version {version}"
