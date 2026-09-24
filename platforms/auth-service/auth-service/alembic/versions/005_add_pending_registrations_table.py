"""add pending_registrations table

Revision ID: 005
Revises: 004
Create Date: 2026-09-24

Backs email verification at registration: POST /auth/register no longer creates a User
directly, it creates a row here. The address is not claimed by anyone until GET
/auth/verify-email turns this row into a User -- see
docs/superpowers/specs/2026-09-24-auth-service-email-verification-design.md.
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_registrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(
        op.f("ix_pending_registrations_id"), "pending_registrations", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_pending_registrations_email"), "pending_registrations", ["email"], unique=True
    )
    op.create_index(
        op.f("ix_pending_registrations_token"), "pending_registrations", ["token"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_pending_registrations_token"), table_name="pending_registrations")
    op.drop_index(op.f("ix_pending_registrations_email"), table_name="pending_registrations")
    op.drop_index(op.f("ix_pending_registrations_id"), table_name="pending_registrations")
    op.drop_table("pending_registrations")
