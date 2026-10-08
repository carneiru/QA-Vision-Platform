"""run_requests.estimate_ms / estimate_upper_ms: the duration the dashboard estimated before Play

Revision ID: 008
Revises: 007
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("run_requests") as batch:
        batch.add_column(sa.Column("estimate_ms", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("estimate_upper_ms", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("run_requests") as batch:
        batch.drop_column("estimate_upper_ms")
        batch.drop_column("estimate_ms")
