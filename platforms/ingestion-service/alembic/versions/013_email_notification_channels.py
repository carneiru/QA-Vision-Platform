"""notification_channels.kind accepts email

Revision ID: 013
Revises: 012
Create Date: 2026-10-05
"""
from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None

NAME = "chk_notification_kind"


def _replace(condition: str) -> None:
    # batch mode: SQLite (the migration test) cannot alter a constraint in place
    with op.batch_alter_table("notification_channels") as batch:
        batch.drop_constraint(NAME, type_="check")
        batch.create_check_constraint(NAME, condition)


def upgrade() -> None:
    _replace("kind IN ('slack','teams','webhook','email')")


def downgrade() -> None:
    _replace("kind IN ('slack','teams','webhook')")
