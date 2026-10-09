"""partial index on failing results, for the report's failure causes and regressions

Failure causes and the regression candidates read only failed and errored rows: a few percent of
test_results, reached until now only by filtering every result of every run. The index covers only
those rows, so it stays small. On PostgreSQL it is built CONCURRENTLY, so uploads are not blocked on a
large table; CONCURRENTLY cannot run inside a transaction, hence the autocommit block.

Revision ID: 016
Revises: 015
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None

NAME = "ix_test_results_failing"
FAILING = "status IN ('failed','errored')"


def _postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    where = {"postgresql_where": sa.text(FAILING), "sqlite_where": sa.text(FAILING)}
    if _postgres():
        with op.get_context().autocommit_block():
            op.create_index(NAME, "test_results", ["run_id", "test_key"], postgresql_concurrently=True, if_not_exists=True, **where)
    else:
        op.create_index(NAME, "test_results", ["run_id", "test_key"], **where)


def downgrade() -> None:
    if _postgres():
        with op.get_context().autocommit_block():
            op.drop_index(NAME, table_name="test_results", postgresql_concurrently=True, if_exists=True)
    else:
        op.drop_index(NAME, table_name="test_results")
