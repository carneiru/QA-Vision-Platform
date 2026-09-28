"""create projects and repositories

Revision ID: 001
Revises:
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

LIVE = sa.text("deleted_at IS NULL")


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "settings", sa.JSON().with_variant(JSONB(), "postgresql"),
            nullable=False, server_default=sa.text("'{}'"),
        ),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_projects_id", "projects", ["id"])
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"])
    op.create_index(
        "uq_project_org_name", "projects", ["organization_id", "name"],
        unique=True, sqlite_where=LIVE, postgresql_where=LIVE,
    )
    op.create_index(
        "uq_project_org_slug", "projects", ["organization_id", "slug"],
        unique=True, sqlite_where=LIVE, postgresql_where=LIVE,
    )

    op.create_table(
        "repositories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("owner", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("full_name_key", sa.String(511), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("default_branch", sa.String(255), nullable=False),
        sa.Column("default_branch_is_user_set", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verification_status", sa.String(20), nullable=False, server_default="unchecked"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("project_id", "provider", "full_name_key", name="uq_repo_project_provider_key"),
        sa.CheckConstraint("provider IN ('github','gitlab')", name="chk_repo_provider"),
        sa.CheckConstraint(
            "verification_status IN ('verified','not_found','unchecked')", name="chk_repo_verification_status"
        ),
    )
    op.create_index("ix_repositories_id", "repositories", ["id"])
    op.create_index("ix_repositories_project_id", "repositories", ["project_id"])


def downgrade() -> None:
    op.drop_table("repositories")
    op.drop_index("uq_project_org_slug", table_name="projects")
    op.drop_index("uq_project_org_name", table_name="projects")
    op.drop_table("projects")
