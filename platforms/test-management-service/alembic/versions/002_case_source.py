"""cases: source_path, source_key, gherkin (Gherkin import, ADR-023)

Revision ID: 002
Revises: 001
Create Date: 2026-10-06
"""
import sqlalchemy as sa
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cases") as batch:
        batch.add_column(sa.Column("source_path", sa.String(500), nullable=True))
        batch.add_column(sa.Column("source_key", sa.String(64), nullable=True))
        batch.add_column(sa.Column("gherkin", sa.Text(), nullable=True))
    # NULLs never collide, in PostgreSQL and SQLite alike, so manual cases are unaffected
    op.create_index("uq_cases_project_source_key", "cases", ["project_id", "source_key"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_cases_project_source_key", table_name="cases")
    with op.batch_alter_table("cases") as batch:
        batch.drop_column("gherkin")
        batch.drop_column("source_key")
        batch.drop_column("source_path")
