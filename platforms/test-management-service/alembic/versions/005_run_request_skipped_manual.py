"""run_requests.skipped_manual: manual cases a whole-suite run left out

Revision ID: 005
Revises: 004
Create Date: 2026-10-07
"""
import sqlalchemy as sa
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("run_requests") as batch:
        batch.add_column(sa.Column("skipped_manual", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("run_requests") as batch:
        batch.drop_column("skipped_manual")
