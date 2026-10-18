"""``/status`` endpoint — service health + G00 build info.

The G00 mission requires "a simple status endpoint" that honestly reports
the current state of the foundation. It explicitly must NOT claim any
real connector, search, or forecasting capability.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from manara.config import APP_DESCRIPTION, APP_NAME, APP_VERSION, BUILD_INFO, settings

router = APIRouter(prefix="", tags=["status"])


class StatusResponse(BaseModel):
    """Service status response.

    ``capabilities`` is an honest, exhaustive list of what G00 actually
    delivers. Anything not listed here is NOT implemented.
    """

    model_config = ConfigDict(extra="forbid")

    app: str = Field(default=APP_NAME)
    version: str = Field(default=APP_VERSION)
    description: str = Field(default=APP_DESCRIPTION)
    env: str = Field(default=settings.env)
    discovery_mode: Literal["synthetic", "live"] = Field(default=settings.discovery_mode)
    timestamp_utc: datetime = Field(default_factory=lambda: datetime.now(UTC))
    build: dict[str, str] = Field(default=BUILD_INFO)
    capabilities: list[str] = Field(
        default_factory=lambda: [
            # G00 — foundation
            "typed_contracts:source",
            "typed_contracts:connector",
            "typed_contracts:search_capability",
            "typed_contracts:domain_mold",
            "typed_contracts:agent_recipe",
            "typed_contracts:evidence",
            "typed_contracts:forecast",
            "typed_contracts:investigation",
            "api:status",
            "api:discovery_synthetic_only",
            "api:contracts_schemas",
            "api:errors_envelope",
            "persistence:investigation_row_sqlite_dev_variant",
            # G01 — capability registry
            "registry:capability_crud",
            "registry:hybrid_search_text_plus_semantic",
            "registry:miniLM_embeddings_384_multilingual",
            "registry:negative_example_reranker",
            "registry:owner_approved_promotion",
            "registry:graph_relationships",
            "registry:evaluation_history",
            "registry:embedding_reindex",
            "registry:8_seed_capability_cards",
        ],
        description="Exhaustive list of G00 + G01 capabilities actually delivered.",
    )
    not_implemented: list[str] = Field(
        default_factory=lambda: [
            "real_source_discovery",        # G02
            "real_connector_execution",     # G02
            "real_search",                  # G02 (sandboxed)
            "real_evidence_collection",     # G03
            "cumulative_knowledge_memory",  # G03
            "mold_factory",                 # G04
            "on_demand_specialist_agents",  # G05
            "real_forecasting",             # G06
            "real_publishing",              # G07
            "full_ux_integration",          # G08
            "production_deployment",        # G09
            "multi_tenant_authn",          # G03
            "object_storage",
            "pgvector_index_ivfflat",       # present in code, NOT exercised (no Postgres in sandbox)
            "real_e2e_pilot_investigation",
        ],
        description="Honestly NOT done yet. Deferred to later missions per ROADMAP.",
    )
    database_url_kind: str = Field(
        default="sqlite" if settings.is_sqlite else "postgres",
        description="Honest report of which DB driver is wired (no fake PostgreSQL claims).",
    )


@router.get("/status", response_model=StatusResponse, summary="Service status")
@router.get("/health", response_model=StatusResponse, summary="Service health alias")
def get_status() -> StatusResponse:
    """Return honest service status.

    Includes:
    * Build metadata (mission, repo URLs).
    * Exhaustive ``capabilities`` list (what G00 actually delivers).
    * Exhaustive ``not_implemented`` list (what G00 explicitly does NOT do).
    * The discovery mode (synthetic-only in G00).
    """
    return StatusResponse()


__all__ = ["router", "StatusResponse"]
