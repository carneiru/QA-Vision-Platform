"""daily flaky rollups: recombine windows without rescanning executions

Revision ID: 006
Revises: 005
Create Date: 2026-10-02
"""
import sqlalchemy as sa
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "flaky_daily",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("branch", sa.String(length=255), nullable=True),
        sa.Column("test_key", sa.String(length=500), nullable=False),
        sa.Column("suite", sa.String(length=500), nullable=False),
        sa.Column("class_name", sa.String(length=500), nullable=False),
        sa.Column("name", sa.String(length=1000), nullable=False),
        sa.Column("runs", sa.Integer(), nullable=False),
        sa.Column("flips", sa.Integer(), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("first_status", sa.String(length=20), nullable=False),
        sa.Column("last_status", sa.String(length=20), nullable=False),
        sa.Column("last_outcome", sa.String(length=10), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "day", "branch", "test_key", name="uq_flaky_daily"),
    )
    op.create_index("ix_flaky_daily_project_day", "flaky_daily", ["project_id", "day"])
    op.create_table(
        "flaky_rollup_days",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.UniqueConstraint("project_id", "day", name="uq_flaky_rollup_days"),
    )
    op.create_index("ix_flaky_rollup_days_project_id", "flaky_rollup_days", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_flaky_rollup_days_project_id", table_name="flaky_rollup_days")
    op.drop_table("flaky_rollup_days")
    op.drop_index("ix_flaky_daily_project_day", table_name="flaky_daily")
    op.drop_table("flaky_daily")
