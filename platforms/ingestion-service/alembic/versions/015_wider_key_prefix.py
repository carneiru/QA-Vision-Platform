"""api_keys.key_prefix: String(12) -> String(16) for the qeos_ prefix

"qeos_" + 8 characters is 13, one over the old width. Keys issued before the QEOS
rename keep their 12-character "qav_" prefixes.

Revision ID: 015
Revises: 014
Create Date: 2026-10-07
"""
import sqlalchemy as sa
from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("api_keys") as batch:
        batch.alter_column("key_prefix", existing_type=sa.String(12), type_=sa.String(16), existing_nullable=False)


def downgrade() -> None:
    # A 13-character "qeos_" prefix does not fit back; keep its first 12 characters.
    op.execute("UPDATE api_keys SET key_prefix = SUBSTR(key_prefix, 1, 12) WHERE LENGTH(key_prefix) > 12")
    with op.batch_alter_table("api_keys") as batch:
        batch.alter_column("key_prefix", existing_type=sa.String(16), type_=sa.String(12), existing_nullable=False)
