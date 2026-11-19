"""create approved actions table

Revision ID: b8e2d7c4a910
Revises: 680a2761d991
Create Date: 2026-11-19 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b8e2d7c4a910"
down_revision: str | Sequence[str] | None = "680a2761d991"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approved_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status",
            sa.String(length=24),
            server_default="approved",
            nullable=False,
        ),
        sa.Column("approved_by", sa.String(length=100), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('approved', 'executed', 'failed')",
            name="ck_approved_actions_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_approved_actions_action_type"),
        "approved_actions",
        ["action_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_approved_actions_idempotency_key"),
        "approved_actions",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        op.f("ix_approved_actions_status"),
        "approved_actions",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_approved_actions_status"),
        table_name="approved_actions",
    )
    op.drop_index(
        op.f("ix_approved_actions_idempotency_key"),
        table_name="approved_actions",
    )
    op.drop_index(
        op.f("ix_approved_actions_action_type"),
        table_name="approved_actions",
    )
    op.drop_table("approved_actions")
