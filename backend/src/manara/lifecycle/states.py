"""MANARA lifecycle state machines.

These enums encode the operational states defined in
``01_ARCHITECTURE/01_MASTER.md`` of the MANARA specification:

* Foundry (Source/Connector/Capability discovery pipeline):
  ``discovered → assessed → candidate → sandbox_tested → review_pending →
  approved`` or ``rejected | quarantined | degraded | retired``.
* Mold (domain orchestration recipe):
  ``temporary → reusable → maintained → archived``.
* Agent (specialist worker recipe):
  ``on_demand → recipe_saved → tested → maintained | retired``.
* Investigation (research run):
  ``received → scoped → coverage_checked → [building_capabilities?] →
  mold_ready → acquiring → normalizing → evidencing →
  forecasting_or_scenarios → drafting → verification →
  deliverable_ready → archived``.

These are deliberately small enums (not state-machine libraries) for G00.
G02+ will introduce explicit transition validators with rejection reasons,
quarantine reasons, etc.
"""

from __future__ import annotations

from enum import Enum


class FoundryState(str, Enum):
    """Operational state of a discovered source / connector / capability."""

    DISCOVERED = "discovered"
    ASSESSED = "assessed"
    CANDIDATE = "candidate"
    SANDBOX_TESTED = "sandbox_tested"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"

    # Terminal / degraded
    REJECTED = "rejected"
    QUARANTINED = "quarantined"
    DEGRADED = "degraded"
    RETIRED = "retired"


class MoldState(str, Enum):
    """Operational state of a domain mold recipe."""

    TEMPORARY = "temporary"
    REUSABLE = "reusable"
    MAINTAINED = "maintained"
    ARCHIVED = "archived"


class AgentState(str, Enum):
    """Operational state of a specialist agent recipe."""

    ON_DEMAND = "on_demand"
    RECIPE_SAVED = "recipe_saved"
    TESTED = "tested"
    MAINTAINED = "maintained"
    RETIRED = "retired"


class InvestigationState(str, Enum):
    """Operational state of an investigation run."""

    RECEIVED = "received"
    SCOPED = "scoped"
    COVERAGE_CHECKED = "coverage_checked"
    BUILDING_CAPABILITIES = "building_capabilities"
    MOLD_READY = "mold_ready"
    ACQUIRING = "acquiring"
    NORMALIZING = "normalizing"
    EVIDENCING = "evidencing"
    FORECASTING_OR_SCENARIOS = "forecasting_or_scenarios"
    DRAFTING = "drafting"
    VERIFICATION = "verification"
    DELIVERABLE_READY = "deliverable_ready"
    ARCHIVED = "archived"


# Ordered transitions for documentation / future validators
FOUNDRY_TRANSITIONS: dict[FoundryState, set[FoundryState]] = {
    FoundryState.DISCOVERED: {FoundryState.ASSESSED, FoundryState.REJECTED},
    FoundryState.ASSESSED: {FoundryState.CANDIDATE, FoundryState.REJECTED},
    FoundryState.CANDIDATE: {FoundryState.SANDBOX_TESTED, FoundryState.QUARANTINED},
    FoundryState.SANDBOX_TESTED: {FoundryState.REVIEW_PENDING, FoundryState.QUARANTINED},
    FoundryState.REVIEW_PENDING: {FoundryState.APPROVED, FoundryState.REJECTED, FoundryState.DEGRADED},
    FoundryState.APPROVED: {FoundryState.DEGRADED, FoundryState.RETIRED},
    FoundryState.REJECTED: set(),
    FoundryState.QUARANTINED: {FoundryState.CANDIDATE, FoundryState.RETIRED},
    FoundryState.DEGRADED: {FoundryState.RETIRED, FoundryState.APPROVED},
    FoundryState.RETIRED: set(),
}

INVESTIGATION_TRANSITIONS: dict[InvestigationState, set[InvestigationState]] = {
    InvestigationState.RECEIVED: {InvestigationState.SCOPED},
    InvestigationState.SCOPED: {InvestigationState.COVERAGE_CHECKED},
    InvestigationState.COVERAGE_CHECKED: {
        InvestigationState.BUILDING_CAPABILITIES,
        InvestigationState.MOLD_READY,
    },
    InvestigationState.BUILDING_CAPABILITIES: {InvestigationState.MOLD_READY},
    InvestigationState.MOLD_READY: {InvestigationState.ACQUIRING},
    InvestigationState.ACQUIRING: {InvestigationState.NORMALIZING},
    InvestigationState.NORMALIZING: {InvestigationState.EVIDENCING},
    InvestigationState.EVIDENCING: {InvestigationState.FORECASTING_OR_SCENARIOS},
    InvestigationState.FORECASTING_OR_SCENARIOS: {InvestigationState.DRAFTING},
    InvestigationState.DRAFTING: {InvestigationState.VERIFICATION},
    InvestigationState.VERIFICATION: {InvestigationState.DELIVERABLE_READY},
    InvestigationState.DELIVERABLE_READY: {InvestigationState.ARCHIVED},
    InvestigationState.ARCHIVED: set(),
}

MOLD_TRANSITIONS: dict[MoldState, set[MoldState]] = {
    MoldState.TEMPORARY: {MoldState.REUSABLE, MoldState.ARCHIVED},
    MoldState.REUSABLE: {MoldState.MAINTAINED, MoldState.ARCHIVED},
    MoldState.MAINTAINED: {MoldState.ARCHIVED},
    MoldState.ARCHIVED: set(),
}

AGENT_TRANSITIONS: dict[AgentState, set[AgentState]] = {
    AgentState.ON_DEMAND: {AgentState.RECIPE_SAVED},
    AgentState.RECIPE_SAVED: {AgentState.TESTED, AgentState.RETIRED},
    AgentState.TESTED: {AgentState.MAINTAINED, AgentState.RETIRED},
    AgentState.MAINTAINED: {AgentState.RETIRED},
    AgentState.RETIRED: set(),
}


__all__ = [
    "FoundryState",
    "MoldState",
    "AgentState",
    "InvestigationState",
    "FOUNDRY_TRANSITIONS",
    "MOLD_TRANSITIONS",
    "AGENT_TRANSITIONS",
    "INVESTIGATION_TRANSITIONS",
]
