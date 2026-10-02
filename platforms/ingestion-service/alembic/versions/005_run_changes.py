"""code-change data per run

Revision ID: 005
Revises: 004
Create Date: 2026-10-02
"""
import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_changed_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("path", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=1), nullable=False),
        sa.Column("additions", sa.Integer(), nullable=True),
        sa.Column("deletions", sa.Integer(), nullable=True),
    )
    op.create_index("ix_run_changed_files_run_id", "run_changed_files", ["run_id"])
    # Nullable summary columns: null means "the upload carried no change data"
    op.add_column("test_runs", sa.Column("change_base_ref", sa.String(length=255), nullable=True))
    op.add_column("test_runs", sa.Column("changed_files", sa.Integer(), nullable=True))
    op.add_column("test_runs", sa.Column("additions", sa.Integer(), nullable=True))
    op.add_column("test_runs", sa.Column("deletions", sa.Integer(), nullable=True))
    op.add_column("test_runs", sa.Column("changes_truncated", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("test_runs", "changes_truncated")
    op.drop_column("test_runs", "deletions")
    op.drop_column("test_runs", "additions")
    op.drop_column("test_runs", "changed_files")
    op.drop_column("test_runs", "change_base_ref")
    op.drop_index("ix_run_changed_files_run_id", table_name="run_changed_files")
    op.drop_table("run_changed_files")
