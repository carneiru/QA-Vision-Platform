"""cases, case_labels, suites, suite_cases

Revision ID: 001
Revises:
Create Date: 2026-10-06
"""
import sqlalchemy as sa
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(10), nullable=False, server_default="draft"),
        sa.Column("automated_test_key", sa.String(64), nullable=True),
        sa.Column("automated_name", sa.String(1500), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("project_id", "number", name="uq_cases_project_number"),
        sa.CheckConstraint("priority IN ('low','medium','high','critical')", name="chk_cases_priority"),
        sa.CheckConstraint("status IN ('draft','ready','archived')", name="chk_cases_status"),
    )
    op.create_index("ix_cases_project_id", "cases", ["project_id"])
    op.create_index("ix_cases_project_status", "cases", ["project_id", "status"])
    op.create_index("ix_cases_automated_test_key", "cases", ["automated_test_key"])

    op.create_table(
        "case_labels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(40), nullable=False),
        sa.UniqueConstraint("case_id", "label", name="uq_case_labels_case_label"),
    )
    op.create_index("ix_case_labels_case_id", "case_labels", ["case_id"])
    op.create_index("ix_case_labels_label", "case_labels", ["label"])

    op.create_table(
        "suites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("project_id", "name", name="uq_suites_project_name"),
    )
    op.create_index("ix_suites_project_id", "suites", ["project_id"])

    op.create_table(
        "suite_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("suite_id", sa.Integer(), sa.ForeignKey("suites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("suite_id", "case_id", name="uq_suite_cases_suite_case"),
    )
    op.create_index("ix_suite_cases_suite_id", "suite_cases", ["suite_id"])
    op.create_index("ix_suite_cases_case_id", "suite_cases", ["case_id"])


def downgrade() -> None:
    op.drop_table("suite_cases")
    op.drop_table("suites")
    op.drop_table("case_labels")
    op.drop_table("cases")
