"""Runs the real Alembic migration against a throwaway SQLite DB (the rest of the suite uses
create_all), catching model/migration drift and exercising the constraints."""
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from src.ingestion.db.base import Base
from src.ingestion.models import ApiKey, Run, RunResult  # noqa: F401  registers tables

SERVICE_ROOT = Path(__file__).resolve().parents[2]

KEY = (
    "INSERT INTO api_keys (project_id, organization_id, name, key_prefix, key_hash, created_by)"
    " VALUES (1, 1, 'k', 'qav_abcdefgh', :hash, 1)"
)
RUN = (
    "INSERT INTO test_runs (project_id, api_key_id, idempotency_key, request_hash, ci_provider,"
    " started_at, finished_at, duration_ms, total, passed, failed, skipped, errored)"
    " VALUES (1, 1, :idem, 'h', :provider, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:01+00:00',"
    " 1000, 0, 0, 0, 0, 0)"
)


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


def test_migration_creates_model_tables(migrated_engine):
    tables = set(inspect(migrated_engine).get_table_names())
    assert {"api_keys", "test_runs", "test_results"} <= set(Base.metadata.tables)
    assert set(Base.metadata.tables) <= tables


def test_migration_columns_match_models(migrated_engine):
    inspector = inspect(migrated_engine)
    for table_name, table in Base.metadata.tables.items():
        migrated = {col["name"] for col in inspector.get_columns(table_name)}
        assert {col.name for col in table.columns} == migrated, f"column drift in {table_name}"


def test_key_hash_is_unique(migrated_engine):
    with migrated_engine.begin() as conn:
        conn.execute(text(KEY), {"hash": "a" * 64})
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as conn:
            conn.execute(text(KEY), {"hash": "a" * 64})


def test_ci_provider_check(migrated_engine):
    with migrated_engine.begin() as conn:
        conn.execute(text(KEY), {"hash": "b" * 64})
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as conn:
            conn.execute(text(RUN), {"idem": None, "provider": "travis"})


def test_idempotency_key_unique_per_project_but_nulls_do_not_collide(migrated_engine):
    with migrated_engine.begin() as conn:
        conn.execute(text(KEY), {"hash": "c" * 64})
        conn.execute(text(RUN), {"idem": None, "provider": "local"})
        conn.execute(text(RUN), {"idem": None, "provider": "local"})  # must not raise
        conn.execute(text(RUN), {"idem": "run-1", "provider": "local"})
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as conn:
            conn.execute(text(RUN), {"idem": "run-1", "provider": "local"})


def test_result_status_check(migrated_engine):
    with migrated_engine.begin() as conn:
        conn.execute(text(KEY), {"hash": "d" * 64})
        conn.execute(text(RUN), {"idem": None, "provider": "local"})
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO test_results (run_id, test_key, suite, class_name, name, status, duration_ms, truncated)"
                " VALUES (1, :k, '', '', 't', 'error', 0, 0)"
            ), {"k": "e" * 64})


def test_redacted_defaults_to_false(migrated_engine):
    with migrated_engine.begin() as conn:
        conn.execute(text(KEY), {"hash": "f" * 64})
        conn.execute(text(RUN), {"idem": None, "provider": "local"})
        conn.execute(text(
            "INSERT INTO test_results (run_id, test_key, suite, class_name, name, status, duration_ms)"
            " VALUES (1, :k, '', '', 't', 'passed', 0)"
        ), {"k": "f" * 64})
        assert conn.execute(text("SELECT redacted FROM test_results")).scalar() in (False, 0)


def test_analytics_indexes_exist(migrated_engine):
    inspector = inspect(migrated_engine)
    result_indexes = {ix["name"]: ix["column_names"] for ix in inspector.get_indexes("test_results")}
    run_indexes = {ix["name"]: ix["column_names"] for ix in inspector.get_indexes("test_runs")}
    assert result_indexes["ix_test_results_test_key_run"] == ["test_key", "run_id"]
    assert run_indexes["ix_test_runs_project_started"] == ["project_id", "started_at"]


def test_model_indexes_match_the_migration():
    assert "ix_test_results_test_key_run" in {ix.name for ix in Base.metadata.tables["test_results"].indexes}
    assert "ix_test_runs_project_started" in {ix.name for ix in Base.metadata.tables["test_runs"].indexes}
