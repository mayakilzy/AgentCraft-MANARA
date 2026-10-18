"""Tests for the lifecycle state machines."""

from __future__ import annotations

from manara.lifecycle import (
    FOUNDRY_TRANSITIONS,
    INVESTIGATION_TRANSITIONS,
    MOLD_TRANSITIONS,
    AgentState,
    FoundryState,
    InvestigationState,
    MoldState,
)


def test_foundry_states_match_spec() -> None:
    """Per 01_ARCHITECTURE/01_MASTER.md Foundry operational states."""
    expected = {
        "discovered",
        "assessed",
        "candidate",
        "sandbox_tested",
        "review_pending",
        "approved",
        "rejected",
        "quarantined",
        "degraded",
        "retired",
    }
    actual = {s.value for s in FoundryState}
    assert actual == expected


def test_mold_states_match_spec() -> None:
    """Per spec: temporary → reusable → maintained → archived."""
    expected = {"temporary", "reusable", "maintained", "archived"}
    actual = {s.value for s in MoldState}
    assert actual == expected


def test_agent_states_match_spec() -> None:
    """Per spec: on_demand → recipe_saved → tested → maintained | retired."""
    expected = {"on_demand", "recipe_saved", "tested", "maintained", "retired"}
    actual = {s.value for s in AgentState}
    assert actual == expected


def test_investigation_states_match_spec() -> None:
    """Per 03_INTELLIGENCE/04_INVESTIGATION_PIPELINE.md state graph."""
    expected = {
        "received",
        "scoped",
        "coverage_checked",
        "building_capabilities",
        "mold_ready",
        "acquiring",
        "normalizing",
        "evidencing",
        "forecasting_or_scenarios",
        "drafting",
        "verification",
        "deliverable_ready",
        "archived",
    }
    actual = {s.value for s in InvestigationState}
    assert actual == expected


def test_foundry_transitions_have_terminal_states() -> None:
    """Rejected and Retired are terminal."""
    assert FOUNDRY_TRANSITIONS[FoundryState.REJECTED] == set()
    assert FOUNDRY_TRANSITIONS[FoundryState.RETIRED] == set()


def test_investigation_transitions_form_a_chain() -> None:
    """A linear walk received → ... → archived must be possible."""
    walk = [
        InvestigationState.RECEIVED,
        InvestigationState.SCOPED,
        InvestigationState.COVERAGE_CHECKED,
        InvestigationState.BUILDING_CAPABILITIES,
        InvestigationState.MOLD_READY,
        InvestigationState.ACQUIRING,
        InvestigationState.NORMALIZING,
        InvestigationState.EVIDENCING,
        InvestigationState.FORECASTING_OR_SCENARIOS,
        InvestigationState.DRAFTING,
        InvestigationState.VERIFICATION,
        InvestigationState.DELIVERABLE_READY,
        InvestigationState.ARCHIVED,
    ]
    for src, dst in zip(walk, walk[1:], strict=False):
        assert dst in INVESTIGATION_TRANSITIONS[src], (
            f"missing transition {src.value} → {dst.value}"
        )


def test_mold_temporary_can_become_archived_directly() -> None:
    """Per spec: a temporary mold can be archived without promotion."""
    assert MoldState.ARCHIVED in MOLD_TRANSITIONS[MoldState.TEMPORARY]
