"""One-off: how fast is each report section? Not part of CI (spec: Performance targets).

    SIZE=A docker compose exec -T -e SIZE=A ingestion-service python - < scripts/bench_report.py
    SIZE=B docker compose exec -T -e SIZE=B ingestion-service python - < scripts/bench_report.py

Seeds project 900002 (no such project exists in project-service) over 180 days -- the 90-day period plus its
90-day look-back -- times each section through report_service.build_report under the same 20 s statement
timeout as the endpoint, prints p50 and p95 of REPEAT runs, then deletes everything it seeded and vacuums.
Anything left by an aborted earlier run is deleted first. Run it in a throwaway stack.

    A: about 100,000 results per 90 days (about 1,500 runs, 1,000 tests): the expected size. Target p95 <= 1 s.
       Seeds 3,060 runs x 67 results over the 180 days.
    B: the README benchmark, 2 million results per 90 days. Target <= 8 s each, never the 20 s timeout.
       Seeds 3,960 runs x 1,000 results over the 180 days.

SECTIONS (comma-separated, default every registered section) picks the sections; an unknown one stops
the script before seeding.
"""
import os
import random
import statistics
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from sqlalchemy import delete, insert, select, text

from src.ingestion.analytics.report_period import Period, choose_bucket
from src.ingestion.db.session import SessionLocal
from src.ingestion.models import ApiKey, Run, RunResult
from src.ingestion.service import report_service
from src.ingestion.service.ingest_service import test_key

SIZE = os.environ.get("SIZE", "A")
PROJECT = 900002
DAYS = 180
TESTS = 1000
RUNS_PER_DAY, TESTS_PER_RUN = (17, 67) if SIZE == "A" else (22, 1000)
REPEAT = 20  # p95 is then the 19th of 20 samples, not the slowest
SECTIONS = os.environ.get("SECTIONS", ",".join(report_service.SECTION_BUILDERS)).split(",")
STATUSES = ("passed", "failed", "errored", "skipped")
WEIGHTS = (95, 3, 1, 1)
MESSAGES = ["TimeoutError: locator('#pay-button') after {} ms", "AssertionError: expected {} got {}",
            "Error: connect ECONNREFUSED 10.0.0.{}:5432", None]

random.seed(11)
keys = [test_key("bench", f"Class{i // 50}", f"test_{i}") for i in range(TESTS)]
now = datetime.now(timezone.utc)
db = SessionLocal()


def clean() -> None:
    """Delete everything seeded for PROJECT, then VACUUM ANALYZE so the next size does not run on a bloated table."""
    db.rollback()
    run_ids = select(Run.id).where(Run.project_id == PROJECT)
    db.execute(delete(RunResult).where(RunResult.run_id.in_(run_ids)))
    db.execute(delete(Run).where(Run.project_id == PROJECT))
    db.execute(delete(ApiKey).where(ApiKey.project_id == PROJECT))
    db.commit()
    vacuum()


def vacuum() -> None:
    """VACUUM cannot run in a transaction. After a bulk load it also sets the visibility map, as autovacuum
    would on a live table, so index-only scans are measured as they behave in production."""
    with db.get_bind().connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text("VACUUM (ANALYZE, PARALLEL 0) test_runs"))  # no DSM: Docker's 64 MB /dev/shm
        connection.execute(text("VACUUM (ANALYZE, PARALLEL 0) test_results"))


def seed() -> None:
    api_key = ApiKey(project_id=PROJECT, organization_id=1, name="bench", key_prefix="qeos_bench1", key_hash="c" * 64,
                     created_by=1)
    db.add(api_key)
    db.flush()
    started = time.perf_counter()
    for day in range(DAYS):
        for number in range(RUNS_PER_DAY):
            when = now - timedelta(days=day, minutes=number * 40)
            chosen = random.sample(range(TESTS), TESTS_PER_RUN)
            statuses = random.choices(STATUSES, WEIGHTS, k=TESTS_PER_RUN)
            run = Run(project_id=PROJECT, api_key_id=api_key.id, request_hash="bench",
                      ci_provider=random.choice(("github_actions", "jenkins")),
                      ci_run_url=f"https://github.com/acme/obt/actions/runs/{day * 100 + number}",
                      branch=random.choice(("main", "main", "feature")), environment=random.choice(("staging", "prod")),
                      started_at=when, finished_at=when + timedelta(minutes=5), duration_ms=random.randint(200_000, 900_000),
                      total=TESTS_PER_RUN, passed=statuses.count("passed"), failed=statuses.count("failed"),
                      errored=statuses.count("errored"), skipped=statuses.count("skipped"))
            db.add(run)
            db.flush()
            db.execute(insert(RunResult), [
                {"run_id": run.id, "test_key": keys[t], "suite": "bench", "class_name": f"Class{t // 50}", "name": f"test_{t}",
                 "status": s, "duration_ms": random.randint(5, 2000), "truncated": False, "redacted": False,
                 "message": None if s in ("passed", "skipped") else
                 (lambda m: m and m.format(random.randint(1, 9000), random.randint(1, 9)))(random.choice(MESSAGES))}
                for t, s in zip(chosen, statuses)
            ])
        db.commit()
    vacuum()
    print(f"size {SIZE}: seeded {DAYS * RUNS_PER_DAY} runs x {TESTS_PER_RUN} results in {time.perf_counter() - started:.0f} s")


def scope(days: int, **filters) -> report_service.Scope:
    zone = ZoneInfo("UTC")
    today = now.astimezone(zone).date()
    period = Period(today - timedelta(days=days - 1), today, zone)
    body = SimpleNamespace(test_keys=filters.get("test_keys"), requested_run_urls=filters.get("urls"),
                           branch=filters.get("branch"), environment=None, ci_provider=None,
                           origin=filters.get("origin", "any"))
    return report_service.Scope.from_request(PROJECT, body, period)


def timed(label: str, s: report_service.Scope, section: str) -> None:
    samples = []
    for _ in range(REPEAT):
        start = time.perf_counter()
        report_service.limit_statement_time(db)
        report_service.build_report(db, s, [section], choose_bucket("auto", s.period.days), now)
        db.rollback()
        samples.append((time.perf_counter() - start) * 1000)
    samples.sort()
    p95 = samples[min(len(samples) - 1, round(0.95 * (len(samples) - 1)))]
    print(f"{label:<44} {section:<15} p50 {statistics.median(samples):>8.0f} ms   p95 {p95:>8.0f} ms", flush=True)


missing = [name for name in SECTIONS if name not in report_service.SECTION_BUILDERS]
if missing:
    raise SystemExit(f"unknown report sections: {', '.join(missing)}")

try:
    clean()
    seed()
    seeded_urls = db.execute(select(Run.ci_run_url).where(Run.project_id == PROJECT).order_by(Run.id)).scalars().all()
    for label, s in [
        ("90 days, every branch", scope(90)),
        ("90 days, main", scope(90, branch="main")),
        ("90 days, 300 test keys", scope(90, test_keys=keys[:300])),
        ("90 days, origin qeos (2,000 URLs)", scope(90, origin="qeos", urls=random.sample(seeded_urls, 2000))),
        ("30 days, every branch", scope(30)),
    ]:
        for section in SECTIONS:
            timed(label, s, section)
finally:
    clean()
    db.close()
