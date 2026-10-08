"""cases.scenario_line: the line of a scenario's heading in its .feature file

Revision ID: 007
Revises: 006
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cases") as batch:
        batch.add_column(sa.Column("scenario_line", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("cases") as batch:
        batch.drop_column("scenario_line")
