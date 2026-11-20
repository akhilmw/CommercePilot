"""create campaign drafts

Revision ID: a91c5e7d2f40
Revises: e7c19082b4e0
Create Date: 2026-11-20 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a91c5e7d2f40"
down_revision: str | Sequence[str] | None = "e7c19082b4e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaign_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("source_catalog_version", sa.Integer(), nullable=False),
        sa.Column("source_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("objective", sa.String(500), nullable=False),
        sa.Column("target_audience", sa.String(500), nullable=False),
        sa.Column("core_message", sa.Text(), nullable=False),
        sa.Column("assets", postgresql.JSONB(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("success_metrics", postgresql.JSONB(), nullable=False),
        sa.Column("supporting_evidence_ids", postgresql.JSONB(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "approved",
                "launched",
                "rejected",
                name="campaign_draft_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("launched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_catalog_version >= 1",
            name="ck_campaign_drafts_catalog_version",
        ),
        sa.CheckConstraint(
            "source_price >= 0",
            name="ck_campaign_drafts_source_price",
        ),
        sa.CheckConstraint(
            "duration_days BETWEEN 1 AND 90",
            name="ck_campaign_drafts_duration_days",
        ),
        sa.CheckConstraint(
            "confidence BETWEEN 0 AND 1",
            name="ck_campaign_drafts_confidence_range",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(assets) = 'array'",
            name="ck_campaign_drafts_assets_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(success_metrics) = 'array'",
            name="ck_campaign_drafts_metrics_array",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(supporting_evidence_ids) = 'array'",
            name="ck_campaign_drafts_evidence_ids_array",
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_campaign_drafts_product_id"),
        "campaign_drafts",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_campaign_drafts_status"),
        "campaign_drafts",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_campaign_drafts_status"), table_name="campaign_drafts")
    op.drop_index(
        op.f("ix_campaign_drafts_product_id"),
        table_name="campaign_drafts",
    )
    op.drop_table("campaign_drafts")
