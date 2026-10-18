"""ORM models — thin persistence layer for G00.

The Pydantic contracts in :mod:`manara.contracts` are the authoritative
schema. These ORM models exist only to demonstrate end-to-end persistence of
the tenant-scoped ``Investigation`` row through the API → DB → API round
trip. Full ORM coverage for Source/Connector/SearchCapability/Evidence/
Forecast/Mold/AgentRecipe arrives in G01 (Registry) and G03 (Cumulative
Memory), per the roadmap.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from manara.db.session import Base


class InvestigationRow(Base):
    """Tenant-scoped investigation row.

    The full Pydantic :class:`manara.contracts.Investigation` is serialized
    to JSON and stored in ``payload``. The indexed columns (``tenant_id``,
    ``state``, ``id``) are extracted for queryability.

    This is intentionally minimal: G00 only proves the persistence contract
    works end-to-end. The richer columnar schema arrives with G03.
    """

    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    topic: Mapped[str] = mapped_column(String(500), nullable=False)

    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


__all__ = ["InvestigationRow"]
