"""Flaky rollup job: keep flaky_daily/flaky_daily_commits current.

    python -m src.ingestion.jobs.rollup [--loop]

Each pass visits every project with runs: it backfills any missing day in the
last 90 and always recomputes yesterday and today (late uploads land there).
One pass at a time across copies (PostgreSQL advisory lock), like retention.
"""

import argparse
import json
import sys
import threading
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Iterator, Optional

from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.ingestion.analytics.rollup import upsert_day
from src.ingestion.models import Run
from src.ingestion.models.flaky_rollup import FlakyRollupDay

WINDOW_DAYS = 90
LOCK_ID = 7_351_002  # distinct from retention's lock
DEFAULT_INTERVAL_HOURS = 6.0


def _log(record: dict, error: bool = False) -> None:
    print(json.dumps(record), file=sys.stderr if error else sys.stdout, flush=True)


def days_to_compute(db: Session, project_id: int, today: date) -> list:
    first = db.execute(
        select(func.min(Run.started_at)).where(Run.project_id == project_id)
    ).scalar()
    if first is None:
        return []
    start = max(today - timedelta(days=WINDOW_DAYS - 1), first.date())
    have = {
        day for (day,) in db.execute(
            select(FlakyRollupDay.day).where(FlakyRollupDay.project_id == project_id)
        ).all()
    }
    wanted = []
    day = start
    while day <= today:
        if day not in have or day >= today - timedelta(days=1):
            wanted.append(day)
        day += timedelta(days=1)
    return wanted


def run_pass(db: Session, now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> dict:
    today = now().date()
    projects = [pid for (pid,) in db.execute(select(Run.project_id).distinct()).all()]
    computed = 0
    for project_id in projects:
        for day in days_to_compute(db, project_id, today):
            upsert_day(db, project_id, day)
            computed += 1
    summary = {"event": "flaky_rollup", "projects": len(projects), "days_computed": computed}
    _log(summary)
    return summary


@contextmanager
def _advisory_lock(engine: Engine) -> Iterator[bool]:
    if engine.dialect.name != "postgresql":
        yield True
        return
    with engine.connect() as conn:
        acquired = bool(conn.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": LOCK_ID}).scalar())
        try:
            yield acquired
        finally:
            if acquired:
                conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": LOCK_ID})
                conn.commit()


def run_once(*, session_factory: sessionmaker, lock_engine: Engine) -> bool:
    try:
        with _advisory_lock(lock_engine) as acquired:
            if not acquired:
                _log({"event": "flaky_rollup", "skipped": "another copy holds the lock"})
                return True
            with session_factory() as db:
                run_pass(db)
        return True
    except Exception as exc:  # the loop must survive a bad pass
        _log({"event": "flaky_rollup", "error": f"{type(exc).__name__}: {exc}"}, error=True)
        return False


def main(
    argv: Optional[list] = None,
    *,
    session_factory: Optional[sessionmaker] = None,
    lock_engine: Optional[Engine] = None,
    stop: Optional[threading.Event] = None,
    interval_hours: float = DEFAULT_INTERVAL_HOURS,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true", help="run forever, one pass per interval")
    args = parser.parse_args(argv)

    if session_factory is None:
        from src.ingestion.db.session import SessionLocal

        session_factory = SessionLocal
    if lock_engine is None:
        lock_engine = session_factory.kw["bind"]

    stop = stop or threading.Event()
    ok = run_once(session_factory=session_factory, lock_engine=lock_engine)
    if not args.loop:
        return 0 if ok else 1
    while not stop.wait(interval_hours * 3600):
        run_once(session_factory=session_factory, lock_engine=lock_engine)
    return 0


if __name__ == "__main__":
    sys.exit(main())
