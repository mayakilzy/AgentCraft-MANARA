"""Source contract — provider / dataset / website / document collection.

Maps to ``01_ARCHITECTURE/01_MASTER.md``:
    "Source is provider/dataset/website/document collection."

And to ``01_ARCHITECTURE/02_CONTRACTS.md`` suggested fields:
    identity, discovery, capabilities, execution, governance.

A Source is the *what* (e.g. OpenAlex, Crossref, arXiv). It is distinct from
a Connector (the *how*: a tested implementation of access/extraction) and from
a SearchCapability (the *why*: a logical query plan that uses one or more
connectors).

This contract intentionally mirrors the field families defined in the spec
without committing to a specific JSON-Schema dialect — Pydantic v2 is the
authoritative schema and JSON-Schema is generated from it at test time.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from manara.lifecycle import FoundryState

# ── Schema versioning ────────────────────────────────────────────────────────
# Every contract carries a `schema_version` so future migrations can detect
# stale records and reject incompatible combinations (per CONTRACTS.md:
# "schema migrations and compatibility tests").
SOURCE_SCHEMA_VERSION = "1.0.0"


class SourceIdentity(BaseModel):
    """Identity block — see CONTRACTS.md §identity."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        ...,
        description="Canonical, stable, lowercase, dotted ID "
        "(e.g. 'openalex', 'crossref', 'arxiv').",
        pattern=r"^[a-z][a-z0-9-]{1,63}$",
    )
    kind: Literal["source"] = "source"
    version: str = Field(..., description="Human-readable version tag (semver preferred).")
    schema_version: str = Field(default=SOURCE_SCHEMA_VERSION)
    display_name: str = Field(..., min_length=1, max_length=200)
    description_long: str = Field(..., min_length=20)
    author: str | None = Field(default=None, description="Maintaining org or person.")
    homepage: HttpUrl | None = Field(default=None)


class SourceDiscovery(BaseModel):
    """Discovery block — how the source is found and what it covers."""

    model_config = ConfigDict(extra="forbid")

    domains: list[str] = Field(
        default_factory=list,
        description="High-level domains served (e.g. 'academic', 'patents').",
    )
    subdomains: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    keywords_ar: list[str] = Field(default_factory=list)
    keywords_en: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    task_intents: list[str] = Field(default_factory=list)
    positive_examples: list[str] = Field(
        default_factory=list,
        min_length=0,
        description="Diverse user intents this source can serve.",
    )
    negative_examples: list[str] = Field(
        default_factory=list,
        description="Use cases this source must NOT be used for (per CONTRACTS.md).",
    )
    coverage_geographies: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


class SourceGovernance(BaseModel):
    """Governance block — license, rights, personal data, status."""

    model_config = ConfigDict(extra="forbid")

    source_license: str = Field(..., description="License or 'review-required' if unclear.")
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

    @model_validator(mode="after")
    def _approve_requires_approver(self) -> SourceGovernance:
        if self.status == FoundryState.APPROVED and not self.approved_by:
            raise ValueError("approved status requires approved_by")
        return self


class Source(BaseModel):
    """A canonical provider/dataset/collection identity.

    The Source is the *what*. A Connector (tested implementation) and a
    SearchCapability (logical query plan) reference it via `source_id`.
    """

    model_config = ConfigDict(extra="forbid")

    identity: SourceIdentity
    discovery: SourceDiscovery
    governance: SourceGovernance

    # Provenance
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _timestamps_monotonic(self) -> Source:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")
        return self


__all__ = [
    "SOURCE_SCHEMA_VERSION",
    "Source",
    "SourceIdentity",
    "SourceDiscovery",
    "SourceGovernance",
]
