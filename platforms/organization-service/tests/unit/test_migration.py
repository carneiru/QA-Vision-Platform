"""Runs the real Alembic migrations against a throwaway SQLite DB.

The rest of the suite builds its schema with Base.metadata.create_all(), which never
exercises alembic/versions/*. These tests catch model/migration drift.
"""
import pytest
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from src.organization.db.base import Base
from src.organization.models import Organization, OrganizationMember, OrganizationInvitation  # noqa: F401  registers tables

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


def test_migration_creates_model_tables(migrated_engine):
    tables = set(inspect(migrated_engine).get_table_names())
    assert "alembic_version" in tables
    # guards against a vacuous pass if Base.metadata ever loses its registrations
    assert {"organizations", "organization_members"} <= set(Base.metadata.tables)
    assert set(Base.metadata.tables) <= tables


def test_migration_columns_match_models(migrated_engine):
    assert Base.metadata.tables, "no models registered on Base.metadata"
    inspector = inspect(migrated_engine)
    for table_name, table in Base.metadata.tables.items():
        migrated_columns = {col["name"] for col in inspector.get_columns(table_name)}
        model_columns = {col.name for col in table.columns}
        assert model_columns == migrated_columns, f"column drift in {table_name}"


def test_migration_enforces_plan_tier_check(migrated_engine):
    """Migration 002's CHECK constraint must actually reject an unlisted tier."""
    with migrated_engine.begin() as conn:
        conn.execute(
            text("INSERT INTO organizations (name, slug, plan_tier) VALUES ('Ok', 'ok', 'enterprise')")
        )

    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as conn:
            conn.execute(
                text("INSERT INTO organizations (name, slug, plan_tier) VALUES ('Bad', 'bad', 'platinum')")
            )


def test_migration_enforces_member_role_check(migrated_engine):
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO organization_members (organization_id, user_id, role, status)"
                    " VALUES (1, 1, 'sysadmin', 'active')"
                )
            )


def test_migration_enforces_invitation_role_check(migrated_engine):
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO organization_invitations"
                    " (organization_id, email, role, invited_by_user_id, token, expires_at)"
                    " VALUES (1, 'x@y.test', 'sysadmin', 1, 'tok', '2026-01-01T00:00:00+00:00')"
                )
            )
