"""feature_files: the raw text of each imported .feature file

Revision ID: 006
Revises: 005
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feature_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("feature_name", sa.String(500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "path", name="uq_feature_files_project_path"),
    )
    op.create_index("ix_feature_files_project_id", "feature_files", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_feature_files_project_id", table_name="feature_files")
    op.drop_table("feature_files")
