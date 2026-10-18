"""Initial schema: investigations table (G00).

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-18

This migration creates the only ORM table shipped with G00:
``investigations`` (the tenant-scoped InvestigationRow). Future missions
(G01 Registry, G03 Memory) will add sources, connectors, capabilities,
evidence, forecasts, molds, agent_recipes tables.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "investigations",
        sa.Column("id", sa.String(120), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False, index=True),
        sa.Column("user_id", sa.String(120), nullable=False),
        sa.Column("state", sa.String(60), nullable=False, index=True),
        sa.Column("topic", sa.String(500), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("investigations")
