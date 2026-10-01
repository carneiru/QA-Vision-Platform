"""Retention: delete runs older than each project's retention period, and empty deleted projects.

    python -m src.ingestion.jobs.retention [--dry-run] [--loop]

Retention periods come from project-service's internal endpoint, called with the HTTP Basic
credentials in PROJECT_SERVICE_INTERNAL_URL. A pass that cannot get a trustworthy answer deletes
nothing, and projects missing from the answer are never touched, so a bug or an empty list can
never wipe data.
"""
import argparse
import json
import signal
import sys
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterator, List, Optional
from urllib.parse import unquote, urlsplit, urlunsplit

import httpx
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Query, Session, sessionmaker

from src.ingestion.core.config import settings
from src.ingestion.models import ApiKey, Run, RunResult

RETENTION_PATH = "/internal/v1/projects/retention"
LOCK_ID = 7_351_001  # any fixed number; only this job takes it
TIMEOUT_SECONDS = 10.0


class RetentionError(Exception):
    """The pass cannot run safely, so it deletes nothing. Messages never contain the password."""


@dataclass(frozen=True)
class Policy:
    project_id: int
    days: int
    deleted: bool


@dataclass(frozen=True)
class Endpoint:
    url: str        # without credentials
    username: str
    password: str
    display: str    # for logs: the password replaced with ***


def parse_internal_url(value: str) -> Endpoint:
    problem = RetentionError("PROJECT_SERVICE_INTERNAL_URL must look like http://user:password@host:port")
    try:
        parts = urlsplit(value.strip())
        username, password, hostname = parts.username, parts.password, parts.hostname
    except ValueError:
        raise problem from None
    if parts.scheme not in ("http", "https") or not hostname or not username or not password:
        raise problem
    host = parts.netloc.rpartition("@")[2]
    path = parts.path.rstrip("/")
    return Endpoint(
        url=urlunsplit((parts.scheme, host, path + RETENTION_PATH, "", "")),
        username=unquote(username),
        password=unquote(password),
        display=urlunsplit((parts.scheme, f"{username}:***@{host}", path, "", "")),
    )


def fetch_policies(endpoint: Endpoint) -> List[Policy]:
    try:
        response = httpx.get(endpoint.url, auth=(endpoint.username, endpoint.password), timeout=TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        raise RetentionError(f"cannot reach {endpoint.display}: {type(exc).__name__}: {exc}") from None
    if response.status_code != 200:
        raise RetentionError(f"{endpoint.display} answered {response.status_code}")
    try:
        body = response.json()
    except ValueError:
        raise RetentionError(f"{endpoint.display} returned a body that is not JSON") from None
    projects = body.get("projects") if isinstance(body, dict) else None
    if not isinstance(projects, list):
        raise RetentionError(f"{endpoint.display} returned an unexpected body")
    return [_policy(item, endpoint) for item in projects]


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)  # bool is a subclass of int


def _policy(item: object, endpoint: Endpoint) -> Policy:
    if (
        not isinstance(item, dict)
        or not _is_int(item.get("project_id"))
        or not _is_int(item.get("result_retention_days"))
        or not 1 <= item["result_retention_days"] <= 365
        or not isinstance(item.get("deleted"), bool)
    ):
        raise RetentionError(f"{endpoint.display} returned an unexpected body")
    return Policy(project_id=item["project_id"], days=item["result_retention_days"], deleted=item["deleted"])


def run_pass(db: Session, policies: List[Policy], now: datetime, *, batch_size: int, dry_run: bool) -> dict:
    runs_deleted = keys_revoked = 0
    for policy in policies:
        runs = db.query(Run.id).filter(Run.project_id == policy.project_id)
        if not policy.deleted:
            runs = runs.filter(Run.created_at < now - timedelta(days=policy.days))
        runs_deleted += runs.count() if dry_run else _delete_in_batches(db, runs, batch_size)
        if policy.deleted:
            keys = db.query(ApiKey).filter(ApiKey.project_id == policy.project_id, ApiKey.revoked_at.is_(None))
            if dry_run:
                keys_revoked += keys.count()
            else:
                keys_revoked += keys.update({ApiKey.revoked_at: now}, synchronize_session=False)
                db.commit()
    listed = {policy.project_id for policy in policies}
    known = {pid for (pid,) in db.query(Run.project_id).distinct()} | {
        pid for (pid,) in db.query(ApiKey.project_id).distinct()
    }
    return {
        "event": "retention",
        "projects": len(policies),
        "runs_deleted": runs_deleted,
        "keys_revoked": keys_revoked,
        "projects_skipped": len(known - listed),
        "dry_run": dry_run,
    }


def _delete_in_batches(db: Session, runs: Query, batch_size: int) -> int:
    deleted = 0
    while True:
        batch = [run_id for (run_id,) in runs.order_by(Run.id).limit(batch_size)]
        if not batch:
            return deleted
        # Results first, explicitly: SQLite (the tests) does not enforce ON DELETE CASCADE by default
        db.query(RunResult).filter(RunResult.run_id.in_(batch)).delete(synchronize_session=False)
        db.query(Run).filter(Run.id.in_(batch)).delete(synchronize_session=False)
        db.commit()
        deleted += len(batch)


@contextmanager
def _advisory_lock(engine: Engine) -> Iterator[bool]:
    """One pass at a time across every copy of the job; PostgreSQL only (the tests use SQLite)."""
    if engine.dialect.name != "postgresql":
        yield True
        return
    with engine.connect() as conn:
        acquired = bool(conn.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": LOCK_ID}).scalar())
        conn.commit()
        try:
            yield acquired
        finally:
            if acquired:
                conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": LOCK_ID})
                conn.commit()


def _log(record: dict, error: bool = False) -> None:
    print(json.dumps(record), file=sys.stderr if error else sys.stdout, flush=True)


def run_once(*, dry_run: bool, now: Callable[[], datetime], session_factory: sessionmaker, lock_engine: Engine) -> bool:
    try:
        endpoint = parse_internal_url(settings.PROJECT_SERVICE_INTERNAL_URL)
        with _advisory_lock(lock_engine) as acquired:
            if not acquired:
                _log({"event": "retention_skipped", "reason": "another pass is already running"})
                return True
            policies = fetch_policies(endpoint)
            with session_factory() as db:
                summary = run_pass(db, policies, now(), batch_size=settings.RETENTION_BATCH_SIZE, dry_run=dry_run)
    except RetentionError as exc:
        _log({"event": "retention_failed", "error": str(exc)}, error=True)
        return False
    except Exception as exc:  # e.g. the database is down: report it; the loop tries again later
        _log({"event": "retention_failed", "error": f"{type(exc).__name__}: {exc}"}, error=True)
        return False
    _log(summary)
    return True


def main(
    argv: Optional[List[str]] = None,
    *,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    session_factory: Optional[sessionmaker] = None,
    lock_engine: Optional[Engine] = None,
    stop: Optional[threading.Event] = None,
) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.ingestion.jobs.retention",
        description="Delete runs older than each project's retention period; empty deleted projects.",
    )
    parser.add_argument("--dry-run", action="store_true", help="report what would be deleted; change nothing")
    parser.add_argument("--loop", action="store_true", help="a pass now, then every RETENTION_INTERVAL_HOURS")
    args = parser.parse_args(argv)

    if session_factory is None:
        from src.ingestion.db.session import SessionLocal

        session_factory = SessionLocal
    if lock_engine is None:
        lock_engine = session_factory.kw["bind"]

    def once() -> bool:
        return run_once(dry_run=args.dry_run, now=now, session_factory=session_factory, lock_engine=lock_engine)

    if not args.loop:
        return 0 if once() else 1

    if stop is None:
        stop = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
    while not stop.is_set():
        once()  # a failed pass is logged; the next one may succeed
        stop.wait(settings.RETENTION_INTERVAL_HOURS * 3600)
    return 0


if __name__ == "__main__":
    sys.exit(main())
