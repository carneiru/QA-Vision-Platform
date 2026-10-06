"""cases.feature_name: the Gherkin Feature an imported case came from (case filters)

Revision ID: 003
Revises: 002
Create Date: 2026-10-06
"""
import sqlalchemy as sa
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cases") as batch:
        batch.add_column(sa.Column("feature_name", sa.String(500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("cases") as batch:
        batch.drop_column("feature_name")
