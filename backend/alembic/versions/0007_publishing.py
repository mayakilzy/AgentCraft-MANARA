"""G07: Publishing tables.

Revision ID: 0007_publishing
Revises: 0006_foresight
Create Date: 2026-10-19
"""

from __future__ import annotations
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0007_publishing"
down_revision: Union[str, Sequence[str], None] = "0006_foresight"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "publishing_publications",
        sa.Column("id", sa.String(120), primary_key=True, nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("investigation_id", sa.String(120), nullable=False),
        sa.Column("output_type", sa.String(40), nullable=False),
        sa.Column("version", sa.String(60), nullable=False, server_default="0.1.0"),
        sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("quality_gate_passed", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("quality_gate_issues", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("deliverable_type", sa.String(40), nullable=False, server_default="research_deliverable"),
        sa.Column("downloadable", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("download_format", sa.String(20), nullable=True),
        sa.Column("subsequent_revision_of", sa.String(120), nullable=True),
        sa.Column("superseded_by", sa.String(120), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_checksum", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("id", "tenant_id", name="uq_publications_id_tenant"),
    )
    op.create_index("ix_publications_tenant_id", "publishing_publications", ["tenant_id"])
    op.create_index("ix_publications_output_type", "publishing_publications", ["output_type"])
    op.create_index("ix_publications_status", "publishing_publications", ["status"])
    op.create_index("ix_publications_tenant_type", "publishing_publications", ["tenant_id", "output_type"])
    op.create_index("ix_publications_tenant_status", "publishing_publications", ["tenant_id", "status"])
    op.create_index("ix_publications_subsequent_revision_of", "publishing_publications", ["subsequent_revision_of"])

    op.create_table(
        "publishing_publication_claims",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("publication_id", sa.String(120), sa.ForeignKey("publishing_publications.id"), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("claim_text", sa.Text, nullable=False),
        sa.Column("claim_type", sa.String(40), nullable=False),
        sa.Column("evidence_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("verified", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("verification_notes", sa.Text, nullable=False, server_default=""),
        sa.Column("section_ref", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_pub_claims_tenant_id", "publishing_publication_claims", ["tenant_id"])
    op.create_index("ix_pub_claims_publication_id", "publishing_publication_claims", ["publication_id"])
    op.create_index("ix_pub_claims_tenant_pub", "publishing_publication_claims", ["tenant_id", "publication_id"])

    op.create_table(
        "publishing_storyboard_scenes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("publication_id", sa.String(120), sa.ForeignKey("publishing_publications.id"), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("scene_number", sa.Integer, nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("scene_type", sa.String(40), nullable=False),
        sa.Column("evidence_ids", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("rights_status", sa.String(40), nullable=False, server_default="unknown"),
        sa.Column("rights_notes", sa.Text, nullable=False, server_default=""),
        sa.Column("source_attribution", sa.String(500), nullable=True),
        sa.Column("visual_suggestions", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("duration_seconds", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("disclosure_text", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_scenes_tenant_id", "publishing_storyboard_scenes", ["tenant_id"])
    op.create_index("ix_scenes_publication_id", "publishing_storyboard_scenes", ["publication_id"])
    op.create_index("ix_scenes_tenant_pub", "publishing_storyboard_scenes", ["tenant_id", "publication_id"])
    op.create_index("ix_scenes_pub_scene_num", "publishing_storyboard_scenes", ["publication_id", "scene_number"])


def downgrade() -> None:
    op.drop_table("publishing_storyboard_scenes")
    op.drop_table("publishing_publication_claims")
    op.drop_table("publishing_publications")
