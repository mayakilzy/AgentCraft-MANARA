"""Connector contract — tested implementation of access/extraction.

Maps to ``01_ARCHITECTURE/01_MASTER.md``:
    "Connector is tested implementation of access/extraction with rate limits/
    auth/licensing."

And to ``01_ARCHITECTURE/02_CONTRACTS.md`` execution block:
    connector_ids, input_schema, limits_and_pagination, credentials_ref
    (never raw secret), allowed_hosts, timeout_policy, retry_semantics,
    idempotency, health_checks.

A Connector is the *how* — code that talks to a Source (e.g. openalex-v1
adapter). Credentials live in a vault reference; NEVER inline.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from manara.lifecycle import FoundryState

CONNECTOR_SCHEMA_VERSION = "1.0.0"


class ConnectorTests(BaseModel):
    """Reference to the test matrix that justified promotion."""

    model_config = ConfigDict(extra="forbid")

    contract_tests: list[str] = Field(default_factory=list, description="Test IDs or paths.")
    sandbox_fixtures: list[str] = Field(default_factory=list)
    live_sample_id: str | None = Field(default=None, description="Real permitted call sample ID.")
    schema_drift_tests: list[str] = Field(default_factory=list)
    ssrf_redirect_tests: list[str] = Field(default_factory=list)
    rate_limit_backoff_tests: list[str] = Field(default_factory=list)


class ConnectorExecution(BaseModel):
    """Execution contract: how the connector talks to the source."""

    model_config = ConfigDict(extra="forbid")

    endpoint: HttpUrl = Field(..., description="Base endpoint URL.")
    allowed_hosts: list[str] = Field(
        default_factory=list,
        description="Host allowlist; the connector MUST NOT call off-list hosts.",
    )
    credentials_ref: str | None = Field(
        default=None,
        description="Vault/secret-manager reference. NEVER a raw secret.",
    )
    input_schema: dict[str, Any] = Field(default_factory=dict, description="JSON-Schema fragment.")
    output_schema: dict[str, Any] = Field(default_factory=dict)
    limits_and_pagination: dict[str, Any] = Field(default_factory=dict)
    timeout_policy_seconds: float = Field(default=30.0, gt=0)
    retry_semantics: dict[str, Any] = Field(default_factory=dict)
    idempotency: Literal["none", "idempotent", "at-least-once"] = "idempotent"
    health_checks: list[str] = Field(default_factory=list)


class ConnectorGovernance(BaseModel):
    """Governance — license, status, security review."""

    model_config = ConfigDict(extra="forbid")

    source_license: str = Field(default="review-required")
    data_reuse_rights: Literal["unknown", "read-only", "cache", "derivative", "commercial"] = "unknown"
    commercial_rights: Literal["unknown", "none", "non-commercial", "commercial-with-attribution", "commercial"] = (
        "unknown"
    )
    status: FoundryState = Field(default=FoundryState.DISCOVERED)
    approved_by: str | None = Field(default=None)
    security_review: str | None = Field(default=None)
    owner_tenant: str | None = Field(default=None)
    last_verified_at: datetime | None = Field(default=None)

    @model_validator(mode="after")
    def _approve_requires_approver(self) -> ConnectorGovernance:
        if self.status == FoundryState.APPROVED and not self.approved_by:
            raise ValueError("approved status requires approved_by")
        return self


class Connector(BaseModel):
    """A tested implementation of access/extraction against a Source.

    Multiple connectors may target the same source (e.g. v1 and v2 of an API).
    A connector is referenced by one or more SearchCapability instances.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        ...,
        description="Connector ID, e.g. 'openalex-v1'.",
        pattern=r"^[a-z0-9][a-z0-9-]{1,63}$",
    )
    schema_version: str = Field(default=CONNECTOR_SCHEMA_VERSION)
    version: str = Field(..., description="Implementation version (semver preferred).")
    source_id: str = Field(..., description="Canonical Source.id this connector targets.")
    implementation_sha: str = Field(
        ...,
        description="Git SHA or content hash of the implemented code, for provenance.",
        min_length=7,
    )
    display_name: str = Field(..., min_length=1, max_length=200)
    description_long: str = Field(..., min_length=20)
    execution: ConnectorExecution
    governance: ConnectorGovernance
    tests: ConnectorTests = Field(default_factory=ConnectorTests)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _timestamps_monotonic(self) -> Connector:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")
        return self


__all__ = [
    "CONNECTOR_SCHEMA_VERSION",
    "Connector",
    "ConnectorExecution",
    "ConnectorGovernance",
    "ConnectorTests",
]
