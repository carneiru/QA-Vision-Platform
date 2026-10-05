"""notification_channels: on_failure, weekly_summary, last_weekly_week

Revision ID: 014
Revises: 013
Create Date: 2026-10-05
"""
import sqlalchemy as sa
from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing channels keep announcing failed runs and get no summary until switched on
    op.add_column("notification_channels", sa.Column("on_failure", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("notification_channels", sa.Column("weekly_summary", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("notification_channels", sa.Column("last_weekly_week", sa.String(8), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("notification_channels") as batch:
        batch.drop_column("last_weekly_week")
        batch.drop_column("weekly_summary")
        batch.drop_column("on_failure")
