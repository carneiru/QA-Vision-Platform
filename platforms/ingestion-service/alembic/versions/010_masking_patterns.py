"""masking_patterns: per-project masking rules (RE2 syntax)

Revision ID: 010
Revises: 009
Create Date: 2026-10-05
"""
import sqlalchemy as sa
from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "masking_patterns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("pattern", sa.String(length=256), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "name", name="uq_masking_pattern_project_name"),
    )
    op.create_index("ix_masking_patterns_id", "masking_patterns", ["id"])
    op.create_index("ix_masking_patterns_project_id", "masking_patterns", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_masking_patterns_project_id", table_name="masking_patterns")
    op.drop_index("ix_masking_patterns_id", table_name="masking_patterns")
    op.drop_table("masking_patterns")
