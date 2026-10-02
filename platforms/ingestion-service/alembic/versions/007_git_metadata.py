"""git metadata per run: author, commit subject, PR number, base branch

Revision ID: 007
Revises: 006
Create Date: 2026-10-02
"""
import sqlalchemy as sa
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("test_runs", sa.Column("commit_author", sa.String(length=255), nullable=True))
    op.add_column("test_runs", sa.Column("commit_message", sa.String(length=500), nullable=True))
    op.add_column("test_runs", sa.Column("pr_number", sa.Integer(), nullable=True))
    op.add_column("test_runs", sa.Column("base_branch", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("test_runs", "base_branch")
    op.drop_column("test_runs", "pr_number")
    op.drop_column("test_runs", "commit_message")
    op.drop_column("test_runs", "commit_author")
