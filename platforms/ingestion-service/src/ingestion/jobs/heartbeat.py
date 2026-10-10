"""Job heartbeats (monitoring spec 2026-10-10 §3): after each pass a loop job upserts its row in
job_heartbeats; ingestion's /metrics turns the rows into job_last_success_timestamp_seconds and
job_last_error_timestamp_seconds (utils/job_metrics.py).

A heartbeat never stops a job: a failed write is logged and the loop carries on. An error text keeps
only its first line, at most MAX_ERROR characters, with URL credentials and password=... pairs
replaced, so no secret reaches the database or a dashboard.
"""
import json
import re
import sys
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session, sessionmaker

from src.ingestion.models.job_heartbeat import JobHeartbeat

JOBS = ("retention", "rollup", "weekly_summary")
MAX_ERROR = 500
# Userinfo of scheme://userinfo@host up to the LAST "@" before whitespace or a quote, so a
# password holding "@" or "/" is removed whole.
_URL_CREDENTIALS = re.compile(r"""(?<=://)[^\s"']*@""")
# key=value / key: value secrets (db_password=, PGPASSWORD=, password='a b', passwd:, token=).
_SECRET_PAIR = re.compile(r"""(?i)((?:pass(?:word|wd)?|pwd|secret|token)\s*[=:]\s*)("[^"]*"|'[^']*'|\S+)""")


def short_error(text: str) -> str:
    lines = str(text).strip().splitlines()
    first = lines[0] if lines else ""
    first = _URL_CREDENTIALS.sub("***@", first)
    first = _SECRET_PAIR.sub(r"\1***", first)
    return first[:MAX_ERROR]


def _upsert(db: Session, job: str, values: dict) -> None:
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:  # SQLite: the tests
        from sqlalchemy.dialects.sqlite import insert
    statement = insert(JobHeartbeat).values(job=job, **values)
    db.execute(statement.on_conflict_do_update(index_elements=[JobHeartbeat.job], set_=values))
    db.commit()


def _utc(now: Optional[datetime]) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    return now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now


def _record(session_factory: sessionmaker, job: str, values: dict) -> None:
    try:
        with session_factory() as db:
            _upsert(db, job, values)
    except Exception as exc:  # the database may be the very thing that failed the pass
        print(json.dumps({"event": "heartbeat_failed", "job": job, "error": type(exc).__name__}),
              file=sys.stderr, flush=True)


def record_success(session_factory: sessionmaker, job: str, now: Optional[datetime] = None) -> None:
    _record(session_factory, job, {"last_success_at": _utc(now)})


def record_error(session_factory: sessionmaker, job: str, error: str, now: Optional[datetime] = None) -> None:
    _record(session_factory, job, {"last_error_at": _utc(now), "last_error": short_error(error)})
