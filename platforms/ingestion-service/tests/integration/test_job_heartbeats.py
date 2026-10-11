"""Job heartbeats: each loop job upserts its row after every pass (spec §3)."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from src.ingestion.jobs import heartbeat
from src.ingestion.models.job_heartbeat import JobHeartbeat

NOW = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def session_factory(db):
    return sessionmaker(bind=db.get_bind(), autocommit=False, autoflush=False)


def aware(moment):
    """SQLite (the tests) hands timezone-aware columns back naive, in UTC."""
    return None if moment is None else (moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc))


def row(db, job):
    db.expire_all()
    return db.get(JobHeartbeat, job)


def test_success_creates_the_row(db, session_factory):
    heartbeat.record_success(session_factory, "rollup", NOW)
    hb = row(db, "rollup")
    assert aware(hb.last_success_at) == NOW and hb.last_error_at is None and hb.last_error is None


def test_an_error_after_a_success_keeps_the_success_time(db, session_factory):
    heartbeat.record_success(session_factory, "rollup", NOW)
    heartbeat.record_error(session_factory, "rollup", "RuntimeError: boom\nTraceback", NOW + timedelta(hours=6))
    hb = row(db, "rollup")
    assert aware(hb.last_success_at) == NOW
    assert aware(hb.last_error_at) == NOW + timedelta(hours=6)
    assert hb.last_error == "RuntimeError: boom"


def test_a_later_success_moves_only_the_success_time(db, session_factory):
    heartbeat.record_error(session_factory, "retention", "RetentionError: x", NOW)
    heartbeat.record_success(session_factory, "retention", NOW + timedelta(days=1))
    hb = row(db, "retention")
    assert aware(hb.last_success_at) == NOW + timedelta(days=1) and aware(hb.last_error_at) == NOW


def test_the_stored_error_never_holds_a_password(db, session_factory):
    heartbeat.record_error(session_factory, "retention", "OperationalError: postgresql://u:topsecret@db/x refused", NOW)
    assert "topsecret" not in row(db, "retention").last_error


def test_a_failing_database_never_stops_the_job(capsys):
    def broken():
        raise OperationalError("INSERT", {}, Exception("connection refused"))

    heartbeat.record_success(broken, "rollup", NOW)  # must not raise
    heartbeat.record_error(broken, "rollup", "x", NOW)
    err = capsys.readouterr().err
    assert '"event": "heartbeat_failed"' in err and '"job": "rollup"' in err


def test_a_naive_now_is_stored_as_utc(db, session_factory):
    heartbeat.record_success(session_factory, "rollup", datetime(2026, 10, 10, 12, 0))
    heartbeat.record_error(session_factory, "rollup", "x", datetime(2026, 10, 10, 13, 0))
    hb = row(db, "rollup")
    assert aware(hb.last_success_at) == NOW and aware(hb.last_error_at) == NOW + timedelta(hours=1)


from contextlib import contextmanager  # noqa: E402

import httpx  # noqa: E402

from src.ingestion.core.config import settings  # noqa: E402
from src.ingestion.jobs import retention, rollup, weekly_summary  # noqa: E402

INTERNAL = "http://ingestion-service:p%40ss%3Aw%2Frd@project-service:8000"
RETENTION_URL = "http://project-service:8000/internal/v1/projects/retention"


def recent(moment):
    return abs(datetime.now(timezone.utc) - aware(moment)) < timedelta(minutes=1)


def test_a_retention_pass_records_its_success(db, session_factory, http, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_SERVICE_INTERNAL_URL", INTERNAL)
    http.get(RETENTION_URL).mock(return_value=httpx.Response(200, json={"projects": []}))
    assert retention.main([], now=lambda: NOW, session_factory=session_factory) == 0
    hb = row(db, "retention")
    assert aware(hb.last_success_at) == NOW and hb.last_error_at is None


def test_a_failed_retention_pass_records_the_error_without_the_password(db, session_factory, http, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_SERVICE_INTERNAL_URL", INTERNAL)
    http.get(RETENTION_URL).mock(return_value=httpx.Response(500))
    assert retention.main([], now=lambda: NOW, session_factory=session_factory) == 1
    hb = row(db, "retention")
    assert hb.last_success_at is None and aware(hb.last_error_at) == NOW
    assert "answered 500" in hb.last_error and "p@ss" not in hb.last_error and "p%40ss" not in hb.last_error


def test_an_unconfigured_retention_job_records_an_error(db, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "PROJECT_SERVICE_INTERNAL_URL", "")
    assert retention.main([], now=lambda: NOW, session_factory=session_factory) == 1
    assert row(db, "retention").last_error.startswith("PROJECT_SERVICE_INTERNAL_URL must look like")


def test_a_rollup_pass_records_its_success(db, session_factory):
    assert rollup.main([], session_factory=session_factory) == 0
    assert recent(row(db, "rollup").last_success_at)


def test_a_failed_rollup_pass_records_the_error(db, session_factory, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(rollup, "run_pass", boom)
    assert rollup.main([], session_factory=session_factory) == 1
    hb = row(db, "rollup")
    assert hb.last_success_at is None and hb.last_error == "RuntimeError: boom" and recent(hb.last_error_at)


def test_a_weekly_summary_pass_records_its_success(db, session_factory):
    assert weekly_summary.main([], session_factory=session_factory) == 0
    assert recent(row(db, "weekly_summary").last_success_at)


def test_a_failed_weekly_summary_pass_records_the_error(db, session_factory, monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(weekly_summary, "run_pass", boom)
    assert weekly_summary.main([], session_factory=session_factory) == 1
    assert row(db, "weekly_summary").last_error == "RuntimeError: smtp down"


@pytest.mark.parametrize("module", [rollup, weekly_summary])
def test_a_pass_skipped_for_the_lock_writes_no_heartbeat(db, session_factory, monkeypatch, module):
    @contextmanager
    def held(_engine):
        yield False

    monkeypatch.setattr(module, "_advisory_lock", held)
    assert module.main([], session_factory=session_factory) == 0
    assert row(db, module.JOB) is None
