"""G08-closure-02: persist MoldCompositionResult for blueprint reload.

Revision ID: 0008_mold_composition
Revises: 0007_publishing
Create Date: 2026-10-20

Adds the ``composition_result_json`` column to ``mold_recipes`` so that
the full MoldCompositionResult (detected_needs, coverage, gaps,
is_complete, is_catalog_complete, deliverable_type,
detection_reasoning, is_unknown_domain, composition_notes, composed_at)
can be reconstructed after page reload without re-running
``POST /mold-factory/compose``.

This is FIX-01 of MANARA-UI-BACKEND-CLOSURE-02.

The column is nullable to preserve compatibility with molds persisted
before this migration. Read paths return
``composition_details_available=false`` when the column is NULL,
never fabricating missing data.

Backwards-compatible: existing rows are NOT rewritten. They keep
``composition_result_json = NULL`` and the read path signals the
absence honestly.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_mold_composition"
down_revision: Union[str, Sequence[str], None] = "0007_publishing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composition_result_json column to mold_recipes."""
    # Nullable: existing rows keep NULL. The ORM + read path treats NULL as
    # "composition details not available for this legacy mold" and signals
    # that honestly to the UI rather than fabricating values.
    op.add_column(
        "mold_recipes",
        sa.Column(
            "composition_result_json",
            sa.JSON,
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Remove composition_result_json column."""
    op.drop_column("mold_recipes", "composition_result_json")
