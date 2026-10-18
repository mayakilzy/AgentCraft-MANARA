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
            # G01-R1 — multi-capability coverage
            "registry:investigation_decomposer",
            "registry:multi_capability_coverage_search",
            "registry:coverage_gap_analysis",
            "registry:precision_recall_benchmark",
            # G02 — search foundry
            "foundry:source_candidate_catalog",
            "foundry:safe_http_client_ssrf_protected",
            "foundry:openalex_connector",
            "foundry:sandbox_test_pipeline",
            "foundry:owner_approved_promotion",
            "foundry:quarantine_path",
            # G03 — cumulative knowledge memory
            "memory:evidence_ingestion_dedup_aware",
            "memory:claim_supports_refutes_qualifies_edges",
            "memory:contradiction_preservation",
            "memory:bitemporal_provenance_no_future_leakage",
            "memory:verdict_promotion_audit_log",
            "memory:investigation_reuse_search",
            "memory:source_snapshots_content_addressed",
            "memory:tenant_isolation_per_row",
            "memory:object_store_local_fs_dev",
            "memory:object_store_s3_compatible_prod_target",
            # G04 — adaptive mold factory
            "mold_factory:unknown_domain_detector",
            "mold_factory:mold_architect",
            "mold_factory:gap_analysis_honest_no_fabrication",
            "mold_factory:mold_recipe_persistence_and_reuse",
            "mold_factory:investigation_workflow_state_machine",
            "mold_factory:owner_approved_mold_promotion",
            "mold_factory:blocker_visibility_for_failed_transitions",
        ],
        description="Exhaustive list of G00 + G01 + G01-R1 + G02 + G03 + G04 capabilities actually delivered.",
    )
    not_implemented: list[str] = Field(
        default_factory=lambda: [
            "on_demand_specialist_agents",  # G05
            "real_forecasting",             # G06
            "real_publishing",              # G07
            "full_ux_integration",          # G08
            "production_deployment",        # G09
            "multi_tenant_authn",          # G03+
            "object_storage_s3_exercised",  # code present, no S3 creds in sandbox
            "pgvector_index_ivfflat",       # present in code, NOT exercised (no Postgres in sandbox)
            "additional_real_connectors",  # G02 only ships OpenAlex; Crossref + arXiv candidates pending
            "live_search_verified",         # only single-work GET verified; search blocked by rate limit
            "memory_vector_search",        # future: pgvector-backed semantic retrieval over evidence
            "foundry_auto_connector_generation",  # G04 records gaps; auto-build is G05+ territory
            "agent_recipe_persistence",    # G05
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
