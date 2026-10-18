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
        ],
        description="Exhaustive list of G00 capabilities. NOT a marketing list.",
    )
    not_implemented: list[str] = Field(
        default_factory=lambda: [
            "real_source_discovery",
            "real_connector_execution",
            "real_search",
            "real_evidence_collection",
            "real_forecasting",
            "real_publishing",
            "multi_tenant_authn",
            "object_storage",
            "pgvector_semantic_search",
            "production_deployment",
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
