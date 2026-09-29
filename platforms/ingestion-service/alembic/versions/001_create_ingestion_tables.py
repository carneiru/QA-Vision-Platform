"""create api_keys, test_runs and test_results

Revision ID: 001
Revises:
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )
    op.create_index("ix_api_keys_id", "api_keys", ["id"])
    op.create_index("ix_api_keys_project_id", "api_keys", ["project_id"])

    op.create_table(
        "test_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("api_key_id", sa.Integer(), sa.ForeignKey("api_keys.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("ci_provider", sa.String(20), nullable=False),
        sa.Column("ci_run_url", sa.String(2048), nullable=True),
        sa.Column("commit_sha", sa.String(40), nullable=True),
        sa.Column("branch", sa.String(255), nullable=True),
        sa.Column("environment", sa.String(100), nullable=True),
        sa.Column("agent_version", sa.String(50), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("errored", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_test_runs_project_idempotency"),
        sa.CheckConstraint(
            "ci_provider IN ('github_actions','gitlab_ci','jenkins','other','local')", name="chk_test_runs_ci_provider"
        ),
    )
    op.create_index("ix_test_runs_id", "test_runs", ["id"])
    op.create_index("ix_test_runs_project_created", "test_runs", ["project_id", "created_at"])
    op.create_index("ix_test_runs_project_branch", "test_runs", ["project_id", "branch"])

    op.create_table(
        "test_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("test_key", sa.String(64), nullable=False),
        sa.Column("suite", sa.String(500), nullable=False, server_default=""),
        sa.Column("class_name", sa.String(500), nullable=False, server_default=""),
        sa.Column("name", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("truncated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("file", sa.String(1000), nullable=True),
        sa.CheckConstraint("status IN ('passed','failed','skipped','errored')", name="chk_test_results_status"),
    )
    op.create_index("ix_test_results_id", "test_results", ["id"])
    op.create_index("ix_test_results_run_id", "test_results", ["run_id"])
    op.create_index("ix_test_results_test_key", "test_results", ["test_key"])


def downgrade() -> None:
    op.drop_table("test_results")
    op.drop_table("test_runs")
    op.drop_table("api_keys")
