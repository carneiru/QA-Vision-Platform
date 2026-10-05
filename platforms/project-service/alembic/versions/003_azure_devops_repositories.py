"""repositories.provider accepts azure_devops

Revision ID: 003
Revises: 002
Create Date: 2026-10-05
"""
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

NAME = "chk_repo_provider"


def _replace(condition: str) -> None:
    # batch mode: SQLite (the migration test) cannot alter a constraint in place
    with op.batch_alter_table("repositories") as batch:
        batch.drop_constraint(NAME, type_="check")
        batch.create_check_constraint(NAME, condition)


def upgrade() -> None:
    _replace("provider IN ('github','gitlab','azure_devops')")


def downgrade() -> None:
    _replace("provider IN ('github','gitlab')")
