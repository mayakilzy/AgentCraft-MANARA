"""SearchCapability contract — logical domain-specific query plan.

Maps to ``01_ARCHITECTURE/01_MASTER.md``:
    "Search Engine/Capability is a semantic domain-specific query plan/profile
     using one or more connectors, selectors, extraction policies and output
     schema."

And to ``02_SEARCH/02_REGISTRY.md``: a capability unit with rich description,
multilingual tags/synonyms, negative cases, technical schema, source/rights,
provenance, trust and evaluation.

A SearchCapability (engine) is the *why* — a logical query profile that uses
one or more Connectors. As the spec stresses: "A new search capability need
not generate Python code when a tested connector and filters suffice."
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from manara.lifecycle import FoundryState

SEARCH_CAPABILITY_SCHEMA_VERSION = "1.0.0"


class CapabilityEvaluation(BaseModel):
    """Dated live-sample evaluation per ``02_SEARCH/02_REGISTRY.md``."""

    model_config = ConfigDict(extra="forbid")

    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    evaluator: str
    benchmark_query_set: str
    precision: float | None = Field(default=None, ge=0.0, le=1.0)
    recall: float | None = Field(default=None, ge=0.0, le=1.0)
    false_positive_misuse_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: str = Field(default="")


class CapabilityGraph(BaseModel):
    """Relationships between capabilities per CONTRACTS.md §graph."""

    model_config = ConfigDict(extra="forbid")

    uses_connector: list[str] = Field(default_factory=list)
    complements: list[str] = Field(default_factory=list, description="Other capability IDs.")
    specializes: list[str] = Field(default_factory=list)
    replaces: list[str] = Field(default_factory=list)
    conflicts_with: list[str] = Field(default_factory=list)


class SearchCapability(BaseModel):
    """A logical search capability / engine.

    The capability references Connectors (via ``graph.uses_connector``) and
    declares what kinds of investigations it can serve. Per the spec, an
    engine must declare both ``positive_examples`` AND ``negative_examples``;
    the latter is what prevents misuse (e.g. patents ≠ efficacy evidence).
    """

    model_config = ConfigDict(extra="forbid")

    # ── Identity ────────────────────────────────────────────────────────────
    id: str = Field(
        ...,
        description="Capability ID, e.g. 'search.battery-publications'.",
        pattern=r"^search\.[a-z0-9][a-z0-9-]{1,63}$",
    )
    kind: Literal["search-engine"] = "search-engine"
    schema_version: str = Field(default=SEARCH_CAPABILITY_SCHEMA_VERSION)
    version: str = Field(..., description="Capability version (semver preferred).")
    display_name: str = Field(..., min_length=1, max_length=200)
    description_long: str = Field(..., min_length=20)
    author: str | None = Field(default=None)

    # ── Discovery ───────────────────────────────────────────────────────────
    domains: list[str] = Field(default_factory=list)
    subdomains: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    keywords_ar: list[str] = Field(default_factory=list)
    keywords_en: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    task_intents: list[str] = Field(default_factory=list)
    positive_examples: list[str] = Field(
        default_factory=list,
        description="Diverse user intents this engine can serve (target 15-30 per Registry spec).",
    )
    negative_examples: list[str] = Field(
        default_factory=list,
        description="Use cases this engine must NOT be used for.",
    )
    coverage_geographies: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)

    # ── Capabilities ───────────────────────────────────────────────────────
    search_purposes: list[str] = Field(default_factory=list)
    data_types: list[str] = Field(default_factory=list)
    temporal_coverage: dict[str, Any] = Field(default_factory=dict)
    freshness_policy: str | None = Field(default=None)
    forecast_relevance: Literal["none", "low", "medium", "high"] = "none"
    output_schema: dict[str, Any] = Field(default_factory=dict)
    quality_contract: dict[str, Any] = Field(default_factory=dict)

    # ── Execution ───────────────────────────────────────────────────────────
    connector_ids: list[str] = Field(
        default_factory=list,
        description="Connector IDs this capability depends on (zero or more).",
    )
    input_schema: dict[str, Any] = Field(default_factory=dict)
    limits_and_pagination: dict[str, Any] = Field(default_factory=dict)
    timeout_policy_seconds: float = Field(default=30.0, gt=0)
    retry_semantics: dict[str, Any] = Field(default_factory=dict)
    idempotency: Literal["none", "idempotent", "at-least-once"] = "idempotent"
    health_checks: list[str] = Field(default_factory=list)

    # ── Governance ──────────────────────────────────────────────────────────
    source_license: str = Field(default="review-required")
    data_reuse_rights: Literal["unknown", "read-only", "cache", "derivative", "commercial"] = "unknown"
    commercial_rights: Literal["unknown", "none", "non-commercial", "commercial-with-attribution", "commercial"] = (
        "unknown"
    )
    personal_data_policy: str = Field(default="review-required")
    status: FoundryState = Field(default=FoundryState.DISCOVERED)
    approved_by: str | None = Field(default=None)
    security_review: str | None = Field(default=None)
    owner_tenant: str | None = Field(default=None)
    last_verified_at: datetime | None = Field(default=None)

    # ── Graph ───────────────────────────────────────────────────────────────
    graph: CapabilityGraph = Field(default_factory=CapabilityGraph)

    # ── Evaluation ──────────────────────────────────────────────────────────
    evaluations: list[CapabilityEvaluation] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _validate(self) -> SearchCapability:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")
        if self.status == FoundryState.APPROVED and not self.approved_by:
            raise ValueError("approved status requires approved_by")
        # If a capability declares connectors, they must match graph.uses_connector
        if self.connector_ids and self.graph.uses_connector:
            missing = set(self.connector_ids) - set(self.graph.uses_connector)
            if missing:
                raise ValueError(
                    f"connector_ids not reflected in graph.uses_connector: {missing}"
                )
        if self.connector_ids and not self.graph.uses_connector:
            self.graph.uses_connector = list(self.connector_ids)
        return self


__all__ = [
    "SEARCH_CAPABILITY_SCHEMA_VERSION",
    "SearchCapability",
    "CapabilityEvaluation",
    "CapabilityGraph",
]
