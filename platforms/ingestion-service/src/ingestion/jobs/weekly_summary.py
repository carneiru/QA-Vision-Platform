"""Weekly summary job: send last ISO week's summary to every channel that asks for it.

    python -m src.ingestion.jobs.weekly_summary [--loop]

From Monday WEEKLY_SUMMARY_HOUR_UTC on, each enabled channel with the weekly summary switched
on gets the previous week once; `last_weekly_week` remembers it, so restarts, a missed Monday
and several copies never send twice. A failed delivery is recorded and not retried that week.
One pass at a time across copies (PostgreSQL advisory lock), like retention and rollup.
"""

import argparse
import json
import sys
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterator, Optional

from sqlalchemy import or_, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from src.ingestion.core.config import settings
from src.ingestion.jobs import heartbeat
from src.ingestion.models.notification_channel import NotificationChannel
from src.ingestion.service import weekly_summary
from src.ingestion.service.notification_service import deliver, record

LOCK_ID = 7_351_003  # distinct from retention's and rollup's locks
DEFAULT_INTERVAL_MINUTES = 30.0
JOB = "weekly_summary"


def _log(record_: dict, error: bool = False) -> None:
    print(json.dumps(record_), file=sys.stderr if error else sys.stdout, flush=True)


def run_pass(session_factory: sessionmaker, now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> dict:
    moment = now()
    start, end, label = weekly_summary.previous_week(moment)
    result = {"event": "weekly_summary", "week": label, "sent": 0, "failed": 0}
    # Monday before the configured hour: last week's summary is not due yet
    if moment < end + timedelta(hours=settings.WEEKLY_SUMMARY_HOUR_UTC):
        _log(result)
        return result

    with session_factory() as db:
        due = (
            db.query(NotificationChannel)
            .filter(NotificationChannel.enabled.is_(True), NotificationChannel.weekly_summary.is_(True),
                    or_(NotificationChannel.last_weekly_week.is_(None), NotificationChannel.last_weekly_week != label))
            .order_by(NotificationChannel.id).all()
        )
        messages = []
        summaries = {}
        for c in due:
            scope = (c.project_id, c.branch)
            if scope not in summaries:
                summaries[scope] = weekly_summary.build(db, c.project_id, moment, c.branch)
            messages.append((c.id, c.kind, c.url, weekly_summary.PAYLOADS[c.kind](c.name, summaries[scope])))
        # Claim the week before sending: a crash mid-pass can lose a message, never repeat one
        for c in due:
            c.last_weekly_week = label
        db.commit()

    outcomes = [(cid, deliver(kind, url, payload)) for cid, kind, url, payload in messages]
    with session_factory() as db:
        for cid, outcome in outcomes:
            record(db, cid, outcome)
            result["sent" if outcome[0] == "delivered" else "failed"] += 1
        db.commit()
    _log(result)
    return result


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
                _log({"event": "weekly_summary", "skipped": "another copy holds the lock"})
                return True  # the copy holding the lock writes the heartbeat
            run_pass(session_factory)
    except Exception as exc:  # the loop must survive a bad pass
        message = f"{type(exc).__name__}: {exc}"
        _log({"event": "weekly_summary", "error": message}, error=True)
        heartbeat.record_error(session_factory, JOB, message)
        return False
    heartbeat.record_success(session_factory, JOB)
    return True


def main(
    argv: Optional[list] = None,
    *,
    session_factory: Optional[sessionmaker] = None,
    lock_engine: Optional[Engine] = None,
    stop: Optional[threading.Event] = None,
    interval_minutes: float = DEFAULT_INTERVAL_MINUTES,
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
    while not stop.wait(interval_minutes * 60):
        run_once(session_factory=session_factory, lock_engine=lock_engine)
    return 0


if __name__ == "__main__":
    sys.exit(main())
