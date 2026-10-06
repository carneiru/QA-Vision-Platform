"""Runs the real Alembic migration against a throwaway SQLite DB (the rest of the suite uses
create_all), catching model/migration drift and exercising the constraints."""
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

import src.casebook.models  # noqa: F401  registers tables
from src.casebook.db.base import Base

SERVICE_ROOT = Path(__file__).resolve().parents[2]

CASE = ("INSERT INTO cases (project_id, number, title, steps, created_by, priority, status)"
        " VALUES (:project, :number, 't', '[]', 1, :priority, :status)")


@pytest.fixture
def migrated_engine(tmp_path):
    url = f"sqlite:///{(tmp_path / 'migration_test.db').as_posix()}"
    cfg = Config()  # no ini file: env.py would otherwise reconfigure logging for the whole test run
    cfg.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    try:
        yield engine
    finally:
        engine.dispose()


def test_migration_creates_every_model_table(migrated_engine):
    assert set(Base.metadata.tables) <= set(inspect(migrated_engine).get_table_names())


def test_migration_columns_match_models(migrated_engine):
    inspector = inspect(migrated_engine)
    for name, table in Base.metadata.tables.items():
        assert {c["name"] for c in inspector.get_columns(name)} == {c.name for c in table.columns}, name


def test_numbers_are_unique_per_project(migrated_engine):
    with migrated_engine.begin() as conn:
        conn.execute(text(CASE), {"project": 1, "number": 1, "priority": "low", "status": "draft"})
        conn.execute(text(CASE), {"project": 2, "number": 1, "priority": "low", "status": "draft"})
    with pytest.raises(IntegrityError), migrated_engine.begin() as conn:
        conn.execute(text(CASE), {"project": 1, "number": 1, "priority": "low", "status": "draft"})


@pytest.mark.parametrize("priority, status", [("urgent", "draft"), ("low", "deleted")])
def test_priority_and_status_are_constrained(migrated_engine, priority, status):
    with pytest.raises(IntegrityError), migrated_engine.begin() as conn:
        conn.execute(text(CASE), {"project": 1, "number": 1, "priority": priority, "status": status})


SOURCED = ("INSERT INTO cases (project_id, number, title, steps, created_by, source_key)"
           " VALUES (:project, :number, 't', '[]', 1, :key)")


def test_source_keys_are_unique_per_project_and_manual_cases_are_free(migrated_engine):
    with migrated_engine.begin() as conn:
        conn.execute(text(SOURCED), {"project": 1, "number": 1, "key": "k" * 64})
        conn.execute(text(SOURCED), {"project": 2, "number": 1, "key": "k" * 64})
        conn.execute(text(SOURCED), {"project": 1, "number": 2, "key": None})
        conn.execute(text(SOURCED), {"project": 1, "number": 3, "key": None})
    with pytest.raises(IntegrityError), migrated_engine.begin() as conn:
        conn.execute(text(SOURCED), {"project": 1, "number": 4, "key": "k" * 64})


def test_downgrade_to_001_drops_the_source_columns(tmp_path):
    url = f"sqlite:///{(tmp_path / 'down.db').as_posix()}"
    cfg = Config()
    cfg.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "001")
    engine = create_engine(url)
    try:
        columns = {c["name"] for c in inspect(engine).get_columns("cases")}
    finally:
        engine.dispose()
    assert not columns & {"source_path", "source_key", "gherkin"}
