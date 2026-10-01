"""One-off: how fast are the analytics queries on a big project? Not part of CI.

    docker compose exec -T ingestion-service python - < scripts/analytics_benchmark.py

Seeds project 900001 (no such project exists in project-service) with RUNS_PER_DAY runs a day for
DAYS days and TESTS results each -- about two million rows -- times each analytics query against
the stack's PostgreSQL, then deletes everything it seeded. Run it in a throwaway stack.
"""
import random
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import delete, insert, select, text

from src.ingestion.analytics.flaky import rank_flaky
from src.ingestion.analytics.trends import daily, window_start
from src.ingestion.db.session import SessionLocal
from src.ingestion.models import ApiKey, Run, RunResult
from src.ingestion.service import analytics_service
from src.ingestion.service.ingest_service import test_key

PROJECT = 900001
DAYS = 90
RUNS_PER_DAY = 22
TESTS = 1000
STATUSES = ("passed", "failed", "errored", "skipped")
WEIGHTS = (95, 3, 1, 1)

random.seed(7)
keys = [test_key("bench", f"Class{i // 50}", f"test_{i}") for i in range(TESTS)]
now = datetime.now(timezone.utc)
db = SessionLocal()


def timed(label, fn):
    start = time.perf_counter()
    result = fn()
    print(f"{label}: {(time.perf_counter() - start) * 1000:.0f} ms", flush=True)
    return result


try:
    api_key = ApiKey(project_id=PROJECT, organization_id=1, name="bench", key_prefix="qav_bench0",
                     key_hash="b" * 64, created_by=1)
    db.add(api_key)
    db.flush()
    started_seeding = time.perf_counter()
    for day in range(DAYS):
        for number in range(RUNS_PER_DAY):
            started = now - timedelta(days=day, minutes=number * 30)
            statuses = random.choices(STATUSES, WEIGHTS, k=TESTS)
            run = Run(project_id=PROJECT, api_key_id=api_key.id, request_hash="bench", ci_provider="local",
                      branch=random.choice(("main", "main", "feature")), commit_sha=f"{day:04x}{number:03x}",
                      started_at=started, finished_at=started + timedelta(minutes=5), duration_ms=300000,
                      total=TESTS, passed=statuses.count("passed"), failed=statuses.count("failed"),
                      errored=statuses.count("errored"), skipped=statuses.count("skipped"))
            db.add(run)
            db.flush()
            db.execute(insert(RunResult), [
                {"run_id": run.id, "test_key": keys[i], "suite": "bench", "class_name": f"Class{i // 50}",
                 "name": f"test_{i}", "status": statuses[i], "duration_ms": random.randint(5, 2000),
                 "truncated": False, "redacted": False}
                for i in range(TESTS)
            ])
        db.commit()
    db.execute(text("ANALYZE test_runs"))
    db.execute(text("ANALYZE test_results"))
    db.commit()
    print(f"seeded {DAYS * RUNS_PER_DAY} runs x {TESTS} results in {time.perf_counter() - started_seeding:.0f} s")

    utc = ZoneInfo("UTC")
    since90, since14 = now - timedelta(days=90), now - timedelta(days=14)
    timed("trends, 365 days", lambda: daily(
        analytics_service.trend_rows(db, PROJECT, window_start(now, 365, utc), None, None), now, 365, utc))
    timed("tests, 90 days, sort=failures", lambda: analytics_service.list_tests(
        db, PROJECT, since90, sort="failures", search=None, limit=50, offset=0))
    timed("tests, 90 days, search", lambda: analytics_service.list_tests(
        db, PROJECT, since90, sort="name", search="test_99", limit=50, offset=0))
    timed("history, 90 days", lambda: analytics_service.test_history(db, PROJECT, keys[0], since90, None, 100))
    timed("flaky, 14 days", lambda: rank_flaky(*analytics_service.flaky_inputs(db, PROJECT, since14, None),
                                                min_runs=5, min_flip_rate=0.3))
    since30 = now - timedelta(days=30)
    timed("flaky, 30 days", lambda: rank_flaky(*analytics_service.flaky_inputs(db, PROJECT, since30, None),
                                                min_runs=5, min_flip_rate=0.3))
finally:
    db.rollback()
    run_ids = select(Run.id).where(Run.project_id == PROJECT)
    db.execute(delete(RunResult).where(RunResult.run_id.in_(run_ids)))
    db.execute(delete(Run).where(Run.project_id == PROJECT))
    db.execute(delete(ApiKey).where(ApiKey.project_id == PROJECT))
    db.commit()
    db.close()
