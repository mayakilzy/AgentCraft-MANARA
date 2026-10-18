"""Evidence contract — traceable, time-aware, contestable claims.

Maps to ``03_INTELLIGENCE/01_KNOWLEDGE_MEMORY.md``:
    `evidence_item` (quote/span/data/sample/checksum); `claim` (bounded
    statement); `claim_support` (supports/refutes/qualifies, independence
    group); `entity`; `entity_relation`; `measure` (value/unit/methodology/
    geography/valid time).

Provenance per the spec:
    Save `observed_at`, `published_at`, `valid_from/to`, `ingested_at`,
    `known_at` and revision/withdrawal date where relevant. Bitemporal
    awareness: world-time versus knowledge-time; experiments/backtests
    cannot reference later data.

Evidence is never silently deleted. Promotion moves a claim along
`candidate → supported → contested → refuted → superseded`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

EVIDENCE_SCHEMA_VERSION = "1.0.0"


class EvidenceKind(str, Enum):
    QUOTE = "quote"
    SPAN = "span"
    DATA = "data"
    SAMPLE = "sample"
    CHECKSUM = "checksum"
    FIGURE = "figure"


class ClaimVerdict(str, Enum):
    """Per the Curator algorithm: never silently delete; preserve disagreement."""

    CANDIDATE = "candidate"
    SUPPORTED = "supported"
    CONTESTED = "contested"
    REFUTED = "refuted"
    SUPERSEDED = "superseded"


class ClaimSupport(str, Enum):
    SUPPORTS = "supports"
    REFUTES = "refutes"
    QUALIFIES = "qualifies"


class Provenance(BaseModel):
    """W3C-PROV-like edges per the knowledge memory spec.

    Bitemporal awareness: ``observed_at`` (world-time, when the event was
    observed) and ``ingested_at`` (knowledge-time, when MANARA learned of it).
    Backtests MUST NOT reference evidence whose ``observed_at`` exceeds the
    simulated cutoff.
    """

    model_config = ConfigDict(extra="forbid")

    observed_at: datetime | None = Field(default=None)
    published_at: datetime | None = Field(default=None)
    valid_from: datetime | None = Field(default=None)
    valid_to: datetime | None = Field(default=None)
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    known_at: datetime | None = Field(default=None)
    revision_at: datetime | None = Field(default=None)
    withdrawn_at: datetime | None = Field(default=None)
    was_derived_from: list[str] = Field(default_factory=list)
    was_generated_by: list[str] = Field(default_factory=list)
    used: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _bitemporal_sanity(self) -> Provenance:
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to must be >= valid_from")
        if self.withdrawn_at and self.revision_at and self.withdrawn_at < self.revision_at:
            raise ValueError("withdrawn_at must be >= revision_at")
        return self


class Claim(BaseModel):
    """A bounded statement with a verdict and traceable support spans."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    statement: str = Field(..., min_length=10)
    verdict: ClaimVerdict = Field(default=ClaimVerdict.CANDIDATE)
    support_relation: ClaimSupport = Field(default=ClaimSupport.SUPPORTS)
    independence_group: str | None = Field(default=None)
    evidence_ids: list[str] = Field(default_factory=list)
    superseded_by: str | None = Field(default=None)
    notes: str = Field(default="")


class Measure(BaseModel):
    """A quantified value with unit, methodology, and geography."""

    model_config = ConfigDict(extra="forbid")

    name: str
    value: float
    unit: str
    methodology: str | None = None
    geography: str | None = None
    valid_at: datetime | None = None
    confidence_interval_low: float | None = None
    confidence_interval_high: float | None = None

    @model_validator(mode="after")
    def _ci_sanity(self) -> Measure:
        if (
            self.confidence_interval_low is not None
            and self.confidence_interval_high is not None
            and self.confidence_interval_high < self.confidence_interval_low
        ):
            raise ValueError("confidence_interval_high must be >= confidence_interval_low")
        return self


class Evidence(BaseModel):
    """A traceable evidence item with provenance, claims, and tenant scope.

    Every substantive user-facing claim has traceable evidence OR is
    explicitly labeled analysis/hypothesis/scenario (per Investigation spec).
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., min_length=1)
    schema_version: str = Field(default=EVIDENCE_SCHEMA_VERSION)
    kind: EvidenceKind
    source_id: str = Field(..., description="Canonical Source.id this evidence came from.")
    source_snapshot_ref: str | None = Field(
        default=None,
        description="Object-storage ref to a captured snapshot of the source at retrieval.",
    )
    tenant_id: str = Field(..., min_length=1, description="Tenant scoping — mandatory on every row.")

    # Content
    content_ref: str | None = Field(
        default=None,
        description="Object-storage ref to the raw content (quote/span/figure).",
    )
    content_checksum: str | None = Field(default=None, description="SHA-256 of the captured content.")
    content_preview: str | None = Field(default=None, description="Short inline preview for inspection; never the full text.")
    structured_payload: dict[str, Any] = Field(default_factory=dict)

    claims: list[Claim] = Field(default_factory=list)
    measures: list[Measure] = Field(default_factory=list)

    provenance: Provenance = Field(default_factory=Provenance)

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _validate(self) -> Evidence:
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must be >= created_at")
        # Bitemporal safety: ingested_at must not precede observed_at (if both set)
        if (
            self.provenance.observed_at is not None
            and self.provenance.ingested_at < self.provenance.observed_at
        ):
            raise ValueError("ingested_at must be >= observed_at (knowledge-time >= world-time)")
        return self


__all__ = [
    "EVIDENCE_SCHEMA_VERSION",
    "Evidence",
    "EvidenceKind",
    "Claim",
    "ClaimVerdict",
    "ClaimSupport",
    "Measure",
    "Provenance",
]
