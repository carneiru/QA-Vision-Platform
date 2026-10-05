"""legal hold on projects: retention deletes nothing of a held project

Revision ID: 002
Revises: 001
Create Date: 2026-10-05
"""
import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("legal_hold_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("legal_hold_by", sa.Integer(), nullable=True))
    op.add_column("projects", sa.Column("legal_hold_reason", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "legal_hold_reason")
    op.drop_column("projects", "legal_hold_by")
    op.drop_column("projects", "legal_hold_at")
