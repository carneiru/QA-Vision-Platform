"""add plan_tier check constraint to organizations

Revision ID: 002
Revises: 001
Create Date: 2026-09-17
"""
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

PLAN_TIER_CHECK = "plan_tier IN ('free','pro','enterprise','enterprise_plus')"


def upgrade() -> None:
    # batch_alter_table so this also applies on SQLite (used by the migration test), which
    # cannot ALTER TABLE ADD CONSTRAINT and needs the table recreated instead.
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.create_check_constraint("chk_plan_tier", PLAN_TIER_CHECK)


def downgrade() -> None:
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.drop_constraint("chk_plan_tier", type_="check")
