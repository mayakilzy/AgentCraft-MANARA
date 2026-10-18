"""``/discovery`` endpoint — G00 synthetic-only capability discovery view.

Per the G00 mission:
    "Add a simple status endpoint, one mock/stub discovery view clearly
    labeled synthetic; NO claims of real search or forecasts yet."

This endpoint returns ONE hard-coded, in-process, *clearly labeled*
synthetic capability card. The card is derived from the example file
``examples/capability_patent_intelligence.yaml`` shipped with the spec
package, but explicitly tagged ``status=example_only`` and
``data_origin=synthetic``.

It does NOT call any external service. It does NOT claim real source access.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from manara.config import settings
from manara.contracts import CapabilityGraph, SearchCapability
from manara.lifecycle import FoundryState

router = APIRouter(prefix="/discovery", tags=["discovery"])


class SyntheticDiscoveryView(BaseModel):
    """Wrapper that labels the discovery view as synthetic.

    The ``label`` field exists at every nesting level so the frontend can
    show a persistent "SYNTHETIC" badge. No real source is contacted.
    """

    model_config = ConfigDict(extra="forbid")

    label: Literal["synthetic"] = "synthetic"
    data_origin: Literal["hardcoded_in_process_example"] = "hardcoded_in_process_example"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    warning: str = Field(
        default=(
            "This is a SYNTHETIC, in-process example for G00 contract validation only. "
            "No real source has been queried. Real discovery arrives in G02."
        )
    )
    capability: SearchCapability
    notes: list[str] = Field(
        default_factory=lambda: [
            "Derived from spec example examples/capability_patent_intelligence.yaml",
            "Status is forced to example-only regardless of input",
            "connector_ids are empty (no real connector exists yet)",
        ]
    )


def _synthetic_patent_capability() -> SearchCapability:
    """Build the one and only synthetic capability card shipped with G00.

    The card mirrors the spec's example YAML but with the Foundry state
    forced to ``discovered`` (NOT ``approved``) and connector_ids empty
    so that no consumer can accidentally treat it as a real connector.
    """
    return SearchCapability(
        id="search.patent-innovation",
        kind="search-engine",
        version="0.1.0",
        display_name="Patent Innovation Search (SYNTHETIC)",
        description_long=(
            "SYNTHETIC G00 example capability. Mirrors the spec's "
            "examples/capability_patent_intelligence.yaml. Does NOT call any "
            "real patent API. A patent filing does not validate scientific "
            "efficacy or commercial deployment."
        ),
        author="manara-g00",
        domains=["industry", "batteries", "medicine", "agriculture", "robotics", "construction"],
        subdomains=[],
        tags=["patents", "patent-family", "ip-intelligence", "early-indicator", "synthetic"],
        keywords_en=["patent", "patent family", "innovation trajectory", "assignee", "filing date"],
        keywords_ar=["براءات", "براءة اختراع", "اتجاه الابتكار", "صاحب البراءة", "تاريخ الإيداع"],
        synonyms=[],
        task_intents=["technology-signals", "historical-trend"],
        positive_examples=[
            "Identify patent families about sodium-ion battery manufacturing",
            "Compare neural prosthetics patent activity by year",
            "Trace desalination membrane innovations across assignees",
            "Find filings related to precision irrigation robots",
            "Compare construction material inventions in two countries",
        ],
        negative_examples=[
            "Prove a medical implant is safe based only on patent filing",
            "Declare patented prototype commercially shipped",
            "Measure independent inventions by raw application count without grouping families",
        ],
        coverage_geographies=["global"],
        languages=["en", "ar"],
        search_purposes=["discovery", "technology-signals", "historical-trend"],
        data_types=["patent-metadata", "patent-family"],
        temporal_coverage={},
        freshness_policy=None,
        forecast_relevance="low",
        output_schema={"$ref": "normalized-patent-evidence-v1"},
        quality_contract={"requires": ["provider-provenance", "timestamp", "family-dedup", "claims-not-proof"]},
        connector_ids=[],
        input_schema={},
        limits_and_pagination={},
        timeout_policy_seconds=30.0,
        retry_semantics={},
        idempotency="idempotent",
        health_checks=[],
        source_license="review-required",
        data_reuse_rights="unknown",
        commercial_rights="unknown",
        personal_data_policy="review-required",
        status=FoundryState.DISCOVERED,
        approved_by=None,
        security_review=None,
        owner_tenant=settings.default_tenant_id,
        last_verified_at=None,
        graph=CapabilityGraph(),
        evaluations=[],
    )


@router.get(
    "",
    response_model=SyntheticDiscoveryView,
    summary="Synthetic capability discovery view (G00)",
)
def get_discovery() -> SyntheticDiscoveryView:
    """Return the one and only synthetic discovery view for G00.

    The view is **clearly labeled synthetic** at the wrapper level and
    inside the capability itself. It exists only to validate the API
    contract end-to-end. Real discovery is deferred to G02.
    """
    if settings.discovery_mode != "synthetic":
        # Defensive: even if someone flips the env flag, G00 must refuse to
        # return anything that looks like a real discovery result.
        # (Live mode arrives with G02 and a real connector behind it.)
        pass  # we still return the synthetic card; the flag is informational

    return SyntheticDiscoveryView(
        capability=_synthetic_patent_capability(),
    )


__all__ = ["router", "SyntheticDiscoveryView"]
