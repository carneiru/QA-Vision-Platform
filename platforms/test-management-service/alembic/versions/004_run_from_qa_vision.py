"""cases.scenario_name; ci_targets, run_requests, ci_target_events (run from QEOS)

Revision ID: 004
Revises: 003
Create Date: 2026-10-07
"""
import sqlalchemy as sa
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

ACTIVE_WHERE = "status IN ('queued','running','cancelling')"


def upgrade() -> None:
    with op.batch_alter_table("cases") as batch:
        batch.add_column(sa.Column("scenario_name", sa.Text(), nullable=True))

    op.create_table(
        "ci_targets",
        sa.Column("project_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("repo", sa.String(200), nullable=False),
        sa.Column("workflow", sa.String(200), nullable=False),
        sa.Column("ref", sa.String(255), nullable=False),
        sa.Column("token_encrypted", sa.Text(), nullable=False),
        sa.Column("token_last4", sa.String(4), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "run_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("selection", sa.JSON(), nullable=False),
        sa.Column("suite_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("conclusion", sa.String(30), nullable=True),
        sa.Column("github_run_id", sa.BigInteger(), nullable=True),
        sa.Column("github_run_url", sa.Text(), nullable=True),
        sa.Column("stopped_by", sa.Integer(), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued','running','completed','cancelling','cancelled','failed_to_start')",
            name="chk_run_requests_status",
        ),
    )
    op.create_index("ix_run_requests_project_id", "run_requests", ["project_id"])
    op.create_index("uq_run_requests_one_active", "run_requests", ["project_id"], unique=True,
                    postgresql_where=sa.text(ACTIVE_WHERE), sqlite_where=sa.text(ACTIVE_WHERE))

    op.create_table(
        "ci_target_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("action IN ('created','updated','token_replaced','deleted')",
                           name="chk_ci_target_events_action"),
    )
    op.create_index("ix_ci_target_events_project_id", "ci_target_events", ["project_id"])


def downgrade() -> None:
    op.drop_table("ci_target_events")
    op.drop_table("run_requests")
    op.drop_table("ci_targets")
    with op.batch_alter_table("cases") as batch:
        batch.drop_column("scenario_name")
