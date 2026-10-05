"""notification_channels: where a project's failed runs are announced

Revision ID: 012
Revises: 011
Create Date: 2026-10-05
"""
import sqlalchemy as sa
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("branch", sa.String(length=255), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_status", sa.String(length=10), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("kind IN ('slack','teams','webhook')", name="chk_notification_kind"),
    )
    op.create_index("ix_notification_channels_id", "notification_channels", ["id"])
    op.create_index("ix_notification_channels_project_id", "notification_channels", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_notification_channels_project_id", table_name="notification_channels")
    op.drop_index("ix_notification_channels_id", table_name="notification_channels")
    op.drop_table("notification_channels")
