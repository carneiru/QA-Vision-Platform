"""Runs the real Alembic migration against a throwaway SQLite DB, so model/migration drift
and the partial unique indexes are exercised (the rest of the suite uses create_all)."""
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from src.project.db.base import Base
from src.project.models import Project, Repository  # noqa: F401  registers tables

SERVICE_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def migrated_engine(tmp_path):
    url = f"sqlite:///{(tmp_path / 'migration_test.db').as_posix()}"
    cfg = Config(str(SERVICE_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    try:
        yield engine
    finally:
        engine.dispose()


def _insert_project(conn, name, slug, deleted=False):
    conn.execute(
        text(
            "INSERT INTO projects (organization_id, name, slug, settings, created_by, deleted_at)"
            " VALUES (1, :name, :slug, '{}', 1, :deleted_at)"
        ),
        {"name": name, "slug": slug, "deleted_at": "2026-01-01T00:00:00+00:00" if deleted else None},
    )


def test_migration_creates_model_tables(migrated_engine):
    tables = set(inspect(migrated_engine).get_table_names())
    assert {"projects", "repositories"} <= set(Base.metadata.tables)
    assert set(Base.metadata.tables) <= tables


def test_migration_columns_match_models(migrated_engine):
    inspector = inspect(migrated_engine)
    for table_name, table in Base.metadata.tables.items():
        migrated = {col["name"] for col in inspector.get_columns(table_name)}
        assert {col.name for col in table.columns} == migrated, f"column drift in {table_name}"


def test_migration_creates_partial_unique_indexes(migrated_engine):
    names = {index["name"] for index in inspect(migrated_engine).get_indexes("projects")}
    assert {"uq_project_org_name", "uq_project_org_slug"} <= names


def test_live_duplicate_name_is_rejected(migrated_engine):
    with migrated_engine.begin() as conn:
        _insert_project(conn, "Checkout", "checkout")
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as conn:
            _insert_project(conn, "Checkout", "checkout-2")


def test_deleted_projects_name_and_slug_can_be_reused(migrated_engine):
    with migrated_engine.begin() as conn:
        _insert_project(conn, "Checkout", "checkout", deleted=True)
        _insert_project(conn, "Checkout", "checkout")  # must not raise


def test_repository_provider_check(migrated_engine):
    with migrated_engine.begin() as conn:
        _insert_project(conn, "P", "p")
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO repositories (project_id, provider, owner, name, full_name_key, url,"
                    " default_branch, default_branch_is_user_set, verification_status)"
                    " VALUES (1, 'bitbucket', 'a', 'b', 'a/b', 'https://bitbucket.org/a/b', 'main', 0, 'unchecked')"
                )
            )


def test_repository_unique_per_project_provider_key(migrated_engine):
    insert = text(
        "INSERT INTO repositories (project_id, provider, owner, name, full_name_key, url,"
        " default_branch, default_branch_is_user_set, verification_status)"
        " VALUES (1, 'github', :owner, 'shop', 'acme/shop', 'https://github.com/acme/shop', 'main', 0, 'unchecked')"
    )
    with migrated_engine.begin() as conn:
        _insert_project(conn, "P", "p")
        conn.execute(insert, {"owner": "acme"})
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as conn:
            conn.execute(insert, {"owner": "Acme"})
