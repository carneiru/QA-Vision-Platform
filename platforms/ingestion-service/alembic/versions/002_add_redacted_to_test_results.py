"""add test_results.redacted

Revision ID: 002
Revises: 001
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "test_results",
        sa.Column("redacted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    with op.batch_alter_table("test_results") as batch:
        batch.drop_column("redacted")
