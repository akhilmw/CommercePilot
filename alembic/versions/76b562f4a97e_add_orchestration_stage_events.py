"""Store agent stage events for orchestration runs."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "76b562f4a97e"
down_revision = "175dfa255294"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orchestration_runs", sa.Column("stage_events", JSONB()))


def downgrade() -> None:
    op.drop_column("orchestration_runs", "stage_events")
