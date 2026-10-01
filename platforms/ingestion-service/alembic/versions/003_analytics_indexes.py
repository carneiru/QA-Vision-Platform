"""indexes for the analytics queries

Revision ID: 003
Revises: 002
Create Date: 2026-10-01
"""
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # One test's executions (history, flaky) without scanning every result
    op.create_index("ix_test_results_test_key_run", "test_results", ["test_key", "run_id"])
    # Every analytics window is on started_at (the existing index is on created_at)
    op.create_index("ix_test_runs_project_started", "test_runs", ["project_id", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_test_runs_project_started", table_name="test_runs")
    op.drop_index("ix_test_results_test_key_run", table_name="test_results")
