"""``/contracts/schemas`` endpoint — expose the eight typed contracts' JSON Schemas.

Useful for:
* Frontend code generation.
* Future gateway-side validation.
* The G00 contract test (which asserts the schemas are stable).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from manara.contracts import SCHEMA_VERSIONS, json_schemas

router = APIRouter(prefix="/contracts", tags=["contracts"])


class ContractsSchemasResponse(BaseModel):
    """All eight contract schemas + their declared versions."""

    model_config = ConfigDict(extra="forbid")

    schema_versions: dict[str, str] = Field(default=SCHEMA_VERSIONS)
    schemas: dict[str, dict[str, Any]] = Field(default_factory=json_schemas)


@router.get(
    "/schemas",
    response_model=ContractsSchemasResponse,
    summary="JSON Schemas for the eight MANARA contracts",
)
def get_contract_schemas() -> ContractsSchemasResponse:
    """Return JSON Schemas for Source, Connector, SearchCapability, Mold,
    AgentRecipe, Evidence, Forecast, Investigation."""
    return ContractsSchemasResponse(
        schema_versions=dict(SCHEMA_VERSIONS),
        schemas=json_schemas(),
    )


__all__ = ["router", "ContractsSchemasResponse"]
