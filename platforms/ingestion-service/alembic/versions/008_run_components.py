"""components under test per run: repo name + commit sha pairs

Revision ID: 008
Revises: 007
Create Date: 2026-10-02
"""
import sqlalchemy as sa
from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_components",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sha", sa.String(length=40), nullable=False),
    )
    op.create_index("ix_run_components_run_id", "run_components", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_run_components_run_id", table_name="run_components")
    op.drop_table("run_components")
