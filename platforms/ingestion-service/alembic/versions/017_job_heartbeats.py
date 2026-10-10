"""job_heartbeats: when each loop job last succeeded and last failed

The loop jobs (retention, rollup, weekly_summary) have no HTTP port, so Prometheus cannot scrape them.
After each pass a job upserts its row here; ingestion's /metrics reads the rows on each scrape
(monitoring spec 2026-10-10 §3).

Revision ID: 017
Revises: 016
Create Date: 2026-10-10
"""
import sqlalchemy as sa
from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_heartbeats",
        sa.Column("job", sa.String(length=50), primary_key=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("job_heartbeats")
