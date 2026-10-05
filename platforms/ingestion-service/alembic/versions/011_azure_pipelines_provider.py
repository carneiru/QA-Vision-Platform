"""ci_provider accepts azure_pipelines

Revision ID: 011
Revises: 010
Create Date: 2026-10-05
"""
from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None

NAME = "chk_test_runs_ci_provider"
NEW = "ci_provider IN ('github_actions','gitlab_ci','jenkins','azure_pipelines','other','local')"
OLD = "ci_provider IN ('github_actions','gitlab_ci','jenkins','other','local')"


def _replace(condition: str) -> None:
    # batch mode: SQLite (the migration test) cannot alter a constraint in place
    with op.batch_alter_table("test_runs") as batch:
        batch.drop_constraint(NAME, type_="check")
        batch.create_check_constraint(NAME, condition)


def upgrade() -> None:
    _replace(NEW)


def downgrade() -> None:
    _replace(OLD)
