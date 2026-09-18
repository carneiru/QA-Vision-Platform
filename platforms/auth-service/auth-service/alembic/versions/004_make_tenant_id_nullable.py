"""make users.tenant_id nullable

Revision ID: 004
Revises: 003
Create Date: 2026-09-18

tenant_id was created NOT NULL with no server default, while UserCreate had no field to
supply it and nothing in the service ever set it. Every INSERT into users therefore failed
its NOT NULL constraint, which made registration and SSO login structurally impossible.

A user legitimately exists before belonging to any organization (registration precedes
organization creation), and organization-service's organization_members table is now the
authoritative record of who belongs to which organization. So the column becomes nullable
rather than acquiring an invented default.
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch_alter_table so this also applies on SQLite, which cannot ALTER COLUMN in place
    # and needs the table recreated instead.
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("tenant_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Reverting requires every existing row to have a tenant_id; rows created while the
    # column was nullable would violate the restored constraint.
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("tenant_id", existing_type=sa.Integer(), nullable=False)
