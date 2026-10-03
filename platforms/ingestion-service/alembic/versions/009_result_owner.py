"""owner per result: CODEOWNERS owners of the test's file, via the collector

Revision ID: 009
Revises: 008
Create Date: 2026-10-03
"""
import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("test_results", sa.Column("owner", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("test_results", "owner")
