"""MANARA typed contracts (Pydantic v2).

This package is the authoritative schema source for the eight foundational
domain types defined in ``01_ARCHITECTURE/02_CONTRACTS.md`` and the related
intelligence/search/architecture documents:

* :class:`Source` — provider/dataset/collection identity (the *what*).
* :class:`Connector` — tested implementation of access/extraction (the *how*).
* :class:`SearchCapability` — logical query plan using connectors (the *why*).
* :class:`Mold` — versioned domain orchestration recipe.
* :class:`AgentRecipe` — rehydratable specialist worker recipe.
* :class:`Evidence` — traceable, time-aware, contestable claim.
* :class:`Forecast` — immutable-at-publication forecast record.
* :class:`Investigation` — a research run with its own state and outputs.

JSON Schema for each can be generated via
``manara.contracts.json_schemas()`` (used by the contract tests).
"""

from __future__ import annotations

from typing import Any

from manara.contracts.agent_recipe import (
    AGENT_RECIPE_SCHEMA_VERSION,
    AgentRecipe,
    AgentRecipeTests,
    AgentRetentionPolicy,
)
from manara.contracts.connector import (
    CONNECTOR_SCHEMA_VERSION,
    Connector,
    ConnectorExecution,
    ConnectorGovernance,
    ConnectorTests,
)
from manara.contracts.domain_mold import (
    MOLD_SCHEMA_VERSION,
    Mold,
    MoldComposition,
    MoldScope,
)
from manara.contracts.evidence import (
    EVIDENCE_SCHEMA_VERSION,
    Claim,
    ClaimSupport,
    ClaimVerdict,
    Evidence,
    EvidenceKind,
    Measure,
    Provenance,
)
from manara.contracts.forecast import (
    FORECAST_SCHEMA_VERSION,
    Forecast,
    ForecastBaseline,
    ForecastEvaluation,
    ForecastOutcome,
)
from manara.contracts.investigation import (
    INVESTIGATION_SCHEMA_VERSION,
    Investigation,
    InvestigationCheckpoint,
    InvestigationScope,
)
from manara.contracts.search_capability import (
    SEARCH_CAPABILITY_SCHEMA_VERSION,
    CapabilityEvaluation,
    CapabilityGraph,
    SearchCapability,
)
from manara.contracts.source import (
    SOURCE_SCHEMA_VERSION,
    Source,
    SourceDiscovery,
    SourceGovernance,
    SourceIdentity,
)

# Map of contract name → schema version (used by compatibility tests)
SCHEMA_VERSIONS: dict[str, str] = {
    "Source": SOURCE_SCHEMA_VERSION,
    "Connector": CONNECTOR_SCHEMA_VERSION,
    "SearchCapability": SEARCH_CAPABILITY_SCHEMA_VERSION,
    "Mold": MOLD_SCHEMA_VERSION,
    "AgentRecipe": AGENT_RECIPE_SCHEMA_VERSION,
    "Evidence": EVIDENCE_SCHEMA_VERSION,
    "Forecast": FORECAST_SCHEMA_VERSION,
    "Investigation": INVESTIGATION_SCHEMA_VERSION,
}


def json_schemas() -> dict[str, dict[str, Any]]:
    """Return a dict of contract name → JSON Schema (Pydantic-generated).

    Used by the contract test suite to assert schema stability and by future
    consumers (e.g. a JSON-Schema gateway) to validate inbound payloads.
    """
    from pydantic import BaseModel
    from pydantic.json_schema import models_json_schema

    models: list[type[BaseModel]] = [
        Source,
        Connector,
        SearchCapability,
        Mold,
        AgentRecipe,
        Evidence,
        Forecast,
        Investigation,
    ]
    _, schemas = models_json_schema(
        [(m, "validation") for m in models],
        ref_template="#/contracts/$defs/{model}",
    )
    return {m.__name__: schemas["$defs"][m.__name__] for m in models}


__all__ = [
    # Contracts
    "Source",
    "SourceIdentity",
    "SourceDiscovery",
    "SourceGovernance",
    "Connector",
    "ConnectorExecution",
    "ConnectorGovernance",
    "ConnectorTests",
    "SearchCapability",
    "CapabilityEvaluation",
    "CapabilityGraph",
    "Mold",
    "MoldScope",
    "MoldComposition",
    "AgentRecipe",
    "AgentRetentionPolicy",
    "AgentRecipeTests",
    "Evidence",
    "EvidenceKind",
    "Claim",
    "ClaimVerdict",
    "ClaimSupport",
    "Measure",
    "Provenance",
    "Forecast",
    "ForecastBaseline",
    "ForecastEvaluation",
    "ForecastOutcome",
    "Investigation",
    "InvestigationScope",
    "InvestigationCheckpoint",
    # Schema metadata
    "SCHEMA_VERSIONS",
    "SOURCE_SCHEMA_VERSION",
    "CONNECTOR_SCHEMA_VERSION",
    "SEARCH_CAPABILITY_SCHEMA_VERSION",
    "MOLD_SCHEMA_VERSION",
    "AGENT_RECIPE_SCHEMA_VERSION",
    "EVIDENCE_SCHEMA_VERSION",
    "FORECAST_SCHEMA_VERSION",
    "INVESTIGATION_SCHEMA_VERSION",
    # Helpers
    "json_schemas",
]
