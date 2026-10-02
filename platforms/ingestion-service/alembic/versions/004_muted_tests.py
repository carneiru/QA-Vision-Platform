"""muted (acknowledged) flaky tests

Revision ID: 004
Revises: 003
Create Date: 2026-10-02
"""
import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "muted_tests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("test_key", sa.String(length=500), nullable=False),
        sa.Column("muted_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "test_key", name="uq_muted_project_test"),
    )
    op.create_index("ix_muted_tests_project_id", "muted_tests", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_muted_tests_project_id", table_name="muted_tests")
    op.drop_table("muted_tests")
