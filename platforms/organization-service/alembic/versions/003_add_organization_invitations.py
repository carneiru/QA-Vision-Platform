"""create organization_invitations

Revision ID: 003
Revises: 002
Create Date: 2026-09-17
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("invited_by_user_id", sa.Integer(), nullable=False),
        # uniqueness comes from the unique index created below, matching the model's
        # unique=True/index=True; declaring it here too would add a second, redundant
        # unique index on Postgres plus a constraint the model never declares
        sa.Column("token", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "role IN ('owner','admin','member','viewer','billing_manager')", name="chk_invitation_role"
        ),
    )
    op.create_index("ix_organization_invitations_organization_id", "organization_invitations", ["organization_id"])
    op.create_index("ix_organization_invitations_token", "organization_invitations", ["token"], unique=True)


def downgrade() -> None:
    op.drop_table("organization_invitations")
