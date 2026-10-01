# Analytics API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Read-only analytics endpoints in ingestion-service — daily trends, a list of tests, one test's history, and flaky-test detection — over the stored runs and results.

**Architecture:** Pure modules (`src/ingestion/analytics/trends.py`, `flaky.py`) hold the arithmetic and ranking; `service/analytics_service.py` holds the SQL (aggregates and window functions, so heavy counting stays in the database); `api/v1/endpoints/analytics.py` exposes `/api/v1/projects/{id}/analytics/*` with the run endpoints' role check. Migration 003 adds two indexes; the gateway routes `analytics` to ingestion-service.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0 (window functions: `LAG`, `ROW_NUMBER`), Alembic, `zoneinfo` + `tzdata`, pytest (SQLite), PostgreSQL in the stack.

**Spec:** `docs/superpowers/specs/2026-10-01-analytics-api-design.md`

## Global Constraints

- Routes: `GET /api/v1/projects/{project_id}/analytics/trends`, `/tests`, `/tests/{test_key}/history`, `/flaky`; access via `require_project_role(*READ_ROLES)` (same as the run endpoints: non-member/missing → 404, project-service down → 503, no token → 401).
- `pass_rate` = passed ÷ (total − skipped), errored counts as not passed, `null` when the denominator is 0, rounded to 4 decimals; averages rounded to whole milliseconds; `flip_rate` rounded to 4 decimals.
- Parameter ranges: trends `days` 1–365 (default 30), `tz` IANA name (default `UTC`, unknown → 422); tests `days` 1–90 (30), `sort` ∈ {`failures`, `duration`, `name`} (`failures`), `search` ≤ 200 chars matched literally, `limit` 1–200 (50), `offset` ≥ 0; history `test_key` `^[0-9a-f]{64}$`, `days` 1–90 (30), `limit` 1–500 (100), message cut to 500 characters, 404 `{"detail": "Test not found"}` when never seen in the project; flaky `window_days` 1–90 (14), `min_runs` 2–1000 (5), `min_flip_rate` 0–1 (0.3), at most 100 items, at most 5 commits per item.
- Trends window: from local midnight `days − 1` days before today in `tz`; every day present, oldest first, empty days zero-filled with `pass_rate`/averages `null`. Other endpoints' window: `started_at >= now − days`.
- Flaky: outcomes `pass` (`passed`) / `fail` (`failed`, `errored`); `skipped` ignored. `same_commit`: a pass and a fail for one `(commit_sha, environment)`, `commit_sha` not null. `flips`: only for tests without `same_commit`; consecutive executions per branch (null branch = one group), ordered by `started_at` then run id; summed across branches; needs runs ≥ `min_runs` and `flip_rate` ≥ `min_flip_rate`. Order: `same_commit` first, then `flip_rate` desc, then `last_seen` desc, then `test_key`.
- Response model class names must not start with `Test` (pytest would try to collect them).
- Tests run from `platforms/ingestion-service`: `SECRET_KEY=x .venv/Scripts/python -m pytest tests/ -q` (Git Bash; `.venv/bin/python` elsewhere). `$PY` means that interpreter.
- Git: commit as carneiru; `git status --short` before every `git add`; never commit stray/empty files; never push tags.

## Review Focus

1. **Search terms with LIKE wildcards** (`%`, `_`, `\`): must match literally, never everything. Pinned by `test_tests_search_matches_literally` (Task 4).
2. **Interleaved branches**: flips must be counted per branch, not across the interleaved stream. Pinned by `test_flips_are_counted_per_branch` (Task 5).
3. **A test seen only in another project**: its history must be 404 here, never another project's data. Pinned by `test_history_of_another_projects_test_is_404` (Task 5).
4. **A `tz` value that is a path** (`../etc/passwd`) or nonsense: 422, never an error or a file read. Pinned by `test_invalid_parameters_are_422` (Task 4).
5. **A day boundary across a daylight-saving change**: runs land on the right local day. Pinned by `test_daylight_saving_change` (Task 1).

---

### Task 1: Trends arithmetic (pure)

**Files:**
- Create: `platforms/ingestion-service/src/ingestion/analytics/__init__.py` (empty)
- Create: `platforms/ingestion-service/src/ingestion/analytics/trends.py`
- Modify: `platforms/ingestion-service/requirements.txt` (add `tzdata`)
- Test: `platforms/ingestion-service/tests/unit/test_analytics_trends.py`

**Interfaces:**
- Produces:
  - `RunRow(started_at: datetime, total: int, passed: int, failed: int, errored: int, skipped: int, duration_ms: int)` (frozen dataclass; field order matters — the service builds it positionally)
  - `window_start(now: datetime, days: int, zone: ZoneInfo) -> datetime` (aware, UTC)
  - `daily(rows: Iterable[RunRow], now: datetime, days: int, zone: ZoneInfo) -> List[dict]` (keys `date`, `runs`, `total`, `passed`, `failed`, `errored`, `skipped`, `pass_rate`, `avg_run_duration_ms`, `max_run_duration_ms`)
  - `pass_rate(passed: int, total: int, skipped: int) -> Optional[float]`
  - `as_utc(value: datetime) -> datetime` (naive → UTC; aware → converted to UTC)

- [ ] **Step 1: Add tzdata**

Append to `platforms/ingestion-service/requirements.txt`, after `prometheus-client==0.20.0`:

```
# IANA time zones for zoneinfo on systems without a zone database (Windows, slim images)
tzdata==2025.2
```

Run (from `platforms/ingestion-service`): `$PY -m pip install -q tzdata==2025.2 && $PY -c "from zoneinfo import ZoneInfo; print(ZoneInfo('Europe/Lisbon'))"`
Expected: `Europe/Lisbon`.

- [ ] **Step 2: Write the failing tests**

`platforms/ingestion-service/tests/unit/test_analytics_trends.py`:

```python
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from src.ingestion.analytics.trends import RunRow, as_utc, daily, pass_rate, window_start

UTC = ZoneInfo("UTC")
LISBON = ZoneInfo("Europe/Lisbon")
NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def row(started, total=1, passed=1, failed=0, errored=0, skipped=0, duration_ms=1000):
    return RunRow(started, total, passed, failed, errored, skipped, duration_ms)


def test_window_start_is_local_midnight():
    assert window_start(NOW, 1, UTC) == datetime(2026, 10, 1, tzinfo=timezone.utc)
    assert window_start(NOW, 3, UTC) == datetime(2026, 9, 29, tzinfo=timezone.utc)
    # Lisbon is UTC+1 in summer: local midnight on 1 October is 23:00 UTC on 30 September
    assert window_start(NOW, 1, LISBON) == datetime(2026, 9, 30, 23, 0, tzinfo=timezone.utc)


def test_a_run_late_in_the_utc_day_lands_on_the_next_local_day():
    late = datetime(2026, 9, 30, 23, 30, tzinfo=timezone.utc)
    assert [(d["date"], d["runs"]) for d in daily([row(late)], NOW, 2, LISBON)] == [("2026-09-30", 0), ("2026-10-01", 1)]
    assert [(d["date"], d["runs"]) for d in daily([row(late)], NOW, 2, UTC)] == [("2026-09-30", 1), ("2026-10-01", 0)]


def test_daylight_saving_change():
    # Lisbon goes back from UTC+1 to UTC at 01:00 UTC on 25 October 2026
    now = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
    assert window_start(now, 3, LISBON) == datetime(2026, 10, 23, 23, 0, tzinfo=timezone.utc)
    before = datetime(2026, 10, 24, 23, 30, tzinfo=timezone.utc)  # 00:30 on the 25th in Lisbon (UTC+1)
    after = datetime(2026, 10, 25, 23, 30, tzinfo=timezone.utc)   # 23:30 on the 25th in Lisbon (UTC)
    days = daily([row(before), row(after)], now, 3, LISBON)
    assert [(d["date"], d["runs"]) for d in days] == [("2026-10-24", 0), ("2026-10-25", 2), ("2026-10-26", 0)]


def test_empty_days_are_zero_filled_oldest_first():
    days = daily([], NOW, 3, UTC)
    assert [d["date"] for d in days] == ["2026-09-29", "2026-09-30", "2026-10-01"]
    assert days[0] == {"date": "2026-09-29", "runs": 0, "total": 0, "passed": 0, "failed": 0, "errored": 0,
                       "skipped": 0, "pass_rate": None, "avg_run_duration_ms": None, "max_run_duration_ms": None}


def test_a_day_adds_up_its_runs():
    days = daily([row(NOW, total=10, passed=6, failed=1, errored=1, skipped=2, duration_ms=1000),
                  row(NOW - timedelta(hours=1), total=2, passed=2, duration_ms=3000)], NOW, 1, UTC)
    assert days == [{"date": "2026-10-01", "runs": 2, "total": 12, "passed": 8, "failed": 1, "errored": 1,
                     "skipped": 2, "pass_rate": 0.8, "avg_run_duration_ms": 2000, "max_run_duration_ms": 3000}]


def test_pass_rate():
    assert pass_rate(6, 10, 2) == 0.75  # errored and failed are not passed; skipped is left out
    assert pass_rate(2, 3, 0) == 0.6667
    assert pass_rate(0, 4, 4) is None
    assert pass_rate(0, 0, 0) is None


def test_runs_outside_the_window_are_ignored():
    assert sum(d["runs"] for d in daily([row(NOW - timedelta(days=5))], NOW, 2, UTC)) == 0


def test_naive_datetimes_are_utc():
    assert as_utc(datetime(2026, 10, 1, 10, 0)) == datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
    lisbon_noon = datetime(2026, 10, 1, 12, 0, tzinfo=LISBON)
    assert as_utc(lisbon_noon) == datetime(2026, 10, 1, 11, 0, tzinfo=timezone.utc)
    assert daily([row(datetime(2026, 10, 1, 10, 0))], NOW, 1, UTC)[0]["runs"] == 1
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `SECRET_KEY=x $PY -m pytest tests/unit/test_analytics_trends.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'src.ingestion.analytics'`.

- [ ] **Step 4: Write the module**

Create the empty `platforms/ingestion-service/src/ingestion/analytics/__init__.py`.

`platforms/ingestion-service/src/ingestion/analytics/trends.py`:

```python
"""Daily trend arithmetic over run rows. Pure: no database, no clock."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class RunRow:
    started_at: datetime
    total: int
    passed: int
    failed: int
    errored: int
    skipped: int
    duration_ms: int


def as_utc(value: datetime) -> datetime:
    """SQLite (the tests) hands back naive datetimes; they were stored as UTC."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def pass_rate(passed: int, total: int, skipped: int) -> Optional[float]:
    considered = total - skipped
    return None if considered <= 0 else round(passed / considered, 4)


def window_start(now: datetime, days: int, zone: ZoneInfo) -> datetime:
    """Local midnight `days - 1` days before today in `zone`, as an aware UTC datetime."""
    first = as_utc(now).astimezone(zone).date() - timedelta(days=days - 1)
    return datetime.combine(first, time.min, tzinfo=zone).astimezone(timezone.utc)


def daily(rows: Iterable[RunRow], now: datetime, days: int, zone: ZoneInfo) -> List[dict]:
    today = as_utc(now).astimezone(zone).date()
    dates = [today - timedelta(days=days - 1 - offset) for offset in range(days)]
    buckets: Dict[date, List[RunRow]] = defaultdict(list)
    wanted = set(dates)
    for run in rows:
        local_day = as_utc(run.started_at).astimezone(zone).date()
        if local_day in wanted:
            buckets[local_day].append(run)
    return [_day(day, buckets.get(day, [])) for day in dates]


def _day(day: date, runs: List[RunRow]) -> dict:
    total = sum(r.total for r in runs)
    skipped = sum(r.skipped for r in runs)
    passed = sum(r.passed for r in runs)
    durations = [r.duration_ms for r in runs]
    return {
        "date": day.isoformat(),
        "runs": len(runs),
        "total": total,
        "passed": passed,
        "failed": sum(r.failed for r in runs),
        "errored": sum(r.errored for r in runs),
        "skipped": skipped,
        "pass_rate": pass_rate(passed, total, skipped),
        "avg_run_duration_ms": round(sum(durations) / len(durations)) if durations else None,
        "max_run_duration_ms": max(durations) if durations else None,
    }
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `SECRET_KEY=x $PY -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd ../..   # repository root
git status --short
git add platforms/ingestion-service/requirements.txt platforms/ingestion-service/src/ingestion/analytics platforms/ingestion-service/tests/unit/test_analytics_trends.py
git commit -m "feat(ingestion): daily trend arithmetic in a requested time zone

Run rows grouped into local days (zoneinfo, tzdata for systems without a
zone database), every day in the window present and zero-filled, pass
rate excluding skipped.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Flaky ranking (pure)

**Files:**
- Create: `platforms/ingestion-service/src/ingestion/analytics/flaky.py`
- Test: `platforms/ingestion-service/tests/unit/test_analytics_flaky.py`

**Interfaces:**
- Consumes: `as_utc` (Task 1).
- Produces:
  - `FlipCount(test_key: str, runs: int, flips: int, pairs: int)`
  - `MixedCommit(test_key: str, commit_sha: str, environment: Optional[str], latest: datetime)`
  - `LatestExecution(test_key: str, suite: str, class_name: str, name: str, status: str, started_at: datetime)`
  - `rank_flaky(flips: Iterable[FlipCount], mixed: Iterable[MixedCommit], latest: Dict[str, LatestExecution], *, min_runs: int, min_flip_rate: float, limit: int = 100) -> List[dict]` — items with keys `test_key`, `suite`, `class_name`, `name`, `reason`, `commits`, `flips`, `flip_rate`, `runs`, `last_status`, `last_seen`. Only tests present in `latest` are considered.

- [ ] **Step 1: Write the failing tests**

`platforms/ingestion-service/tests/unit/test_analytics_flaky.py`:

```python
from datetime import datetime, timedelta, timezone

from src.ingestion.analytics.flaky import FlipCount, LatestExecution, MixedCommit, rank_flaky

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def latest(key, status="failed", minutes=0, name=None):
    return LatestExecution(key, "s", "C", name or key, status, NOW - timedelta(minutes=minutes))


def rank(flips=(), mixed=(), rows=(), min_runs=5, min_flip_rate=0.3, limit=100):
    return rank_flaky(flips, mixed, {r.test_key: r for r in rows}, min_runs=min_runs,
                      min_flip_rate=min_flip_rate, limit=limit)


def test_a_mixed_commit_is_confirmed():
    items = rank(flips=[FlipCount("k", 2, 1, 1)], mixed=[MixedCommit("k", "c1", None, NOW)], rows=[latest("k")])
    assert items == [{
        "test_key": "k", "suite": "s", "class_name": "C", "name": "k", "reason": "same_commit",
        "commits": [{"commit_sha": "c1", "environment": None}], "flips": None, "flip_rate": None,
        "runs": 2, "last_status": "failed", "last_seen": NOW,
    }]


def test_flips_at_or_above_the_rate_are_suspected():
    rows, flips = [latest("k", status="passed")], [FlipCount("k", 6, 2, 5)]  # 2 of 5 pairs = 0.4
    item = rank(flips=flips, rows=rows, min_flip_rate=0.4)[0]
    assert (item["reason"], item["flips"], item["flip_rate"], item["commits"], item["runs"]) == ("flips", 2, 0.4, [], 6)
    assert rank(flips=flips, rows=rows, min_flip_rate=0.5) == []


def test_too_few_runs_or_no_pairs_are_not_suspected():
    assert rank(flips=[FlipCount("k", 4, 3, 3)], rows=[latest("k")]) == []
    assert rank(flips=[FlipCount("k", 5, 0, 0)], rows=[latest("k")]) == []
    assert rank(rows=[latest("k")]) == []


def test_a_confirmed_test_is_not_listed_again_under_flips():
    items = rank(flips=[FlipCount("k", 9, 8, 8)], mixed=[MixedCommit("k", "c1", "py39", NOW)], rows=[latest("k")])
    assert [(i["test_key"], i["reason"]) for i in items] == [("k", "same_commit")]
    assert items[0]["commits"] == [{"commit_sha": "c1", "environment": "py39"}]


def test_order_confirmed_then_flip_rate_then_last_seen():
    rows = [latest("k3", minutes=60), latest("k1", minutes=10), latest("k2", minutes=1), latest("k4", minutes=5)]
    flips = [FlipCount("k1", 5, 4, 4), FlipCount("k2", 6, 2, 5), FlipCount("k4", 5, 4, 4)]
    mixed = [MixedCommit("k3", "c1", None, NOW - timedelta(minutes=60))]
    assert [i["test_key"] for i in rank(flips=flips, mixed=mixed, rows=rows)] == ["k3", "k4", "k1", "k2"]


def test_at_most_five_commits_most_recent_first():
    mixed = [MixedCommit("k", f"c{i}", None, NOW - timedelta(minutes=i)) for i in range(6)]
    commits = rank(mixed=mixed, rows=[latest("k")])[0]["commits"]
    assert [c["commit_sha"] for c in commits] == ["c0", "c1", "c2", "c3", "c4"]


def test_identity_comes_from_the_latest_execution():
    item = rank(mixed=[MixedCommit("k", "c1", None, NOW)], rows=[latest("k", name="renamed")])[0]
    assert item["name"] == "renamed"


def test_at_most_limit_items():
    rows = [latest(f"k{i:03d}") for i in range(150)]
    flips = [FlipCount(f"k{i:03d}", 5, 4, 4) for i in range(150)]
    assert len(rank(flips=flips, rows=rows)) == 100
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `SECRET_KEY=x $PY -m pytest tests/unit/test_analytics_flaky.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'src.ingestion.analytics.flaky'`.

- [ ] **Step 3: Write the module**

`platforms/ingestion-service/src/ingestion/analytics/flaky.py`:

```python
"""Flaky-test ranking over per-test totals. Pure: the database computes the totals.

`same_commit` (confirmed): the test both passed and failed for one (commit, environment).
`flips` (suspected): its outcome changed between consecutive executions on a branch often enough.
"""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from src.ingestion.analytics.trends import as_utc

MAX_COMMITS = 5


@dataclass(frozen=True)
class FlipCount:
    test_key: str
    runs: int    # non-skipped executions in the window
    flips: int   # outcome changes between consecutive executions, per branch, summed
    pairs: int   # consecutive pairs, per branch, summed


@dataclass(frozen=True)
class MixedCommit:
    test_key: str
    commit_sha: str
    environment: Optional[str]
    latest: datetime


@dataclass(frozen=True)
class LatestExecution:
    test_key: str
    suite: str
    class_name: str
    name: str
    status: str
    started_at: datetime


def rank_flaky(
    flips: Iterable[FlipCount],
    mixed: Iterable[MixedCommit],
    latest: Dict[str, LatestExecution],
    *,
    min_runs: int,
    min_flip_rate: float,
    limit: int = 100,
) -> List[dict]:
    counts = {count.test_key: count for count in flips}
    commits_by_test: Dict[str, List[MixedCommit]] = defaultdict(list)
    for commit in mixed:
        commits_by_test[commit.test_key].append(commit)

    items = []
    for key, last in latest.items():
        count = counts.get(key)
        base = {
            "test_key": key,
            "suite": last.suite,
            "class_name": last.class_name,
            "name": last.name,
            "runs": count.runs if count else 0,
            "last_status": last.status,
            "last_seen": as_utc(last.started_at),
        }
        if key in commits_by_test:
            newest = sorted(commits_by_test[key], key=lambda c: (as_utc(c.latest), c.commit_sha), reverse=True)
            items.append({
                **base, "reason": "same_commit", "flips": None, "flip_rate": None,
                "commits": [{"commit_sha": c.commit_sha, "environment": c.environment} for c in newest[:MAX_COMMITS]],
            })
        elif count and count.runs >= min_runs and count.pairs > 0 and count.flips / count.pairs >= min_flip_rate:
            items.append({
                **base, "reason": "flips", "commits": [], "flips": count.flips,
                "flip_rate": round(count.flips / count.pairs, 4),
            })

    items.sort(key=lambda item: (
        item["reason"] != "same_commit",
        -(item["flip_rate"] or 0.0),
        -item["last_seen"].timestamp(),
        item["test_key"],
    ))
    return items[:limit]
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `SECRET_KEY=x $PY -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd ../..
git status --short
git add platforms/ingestion-service/src/ingestion/analytics/flaky.py platforms/ingestion-service/tests/unit/test_analytics_flaky.py
git commit -m "feat(ingestion): rank flaky tests from per-test totals

Confirmed (same commit and environment) first, then suspected by flip
rate, then by when last seen; thresholds, at most five commits per test.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Indexes (migration 003)

**Files:**
- Create: `platforms/ingestion-service/alembic/versions/003_analytics_indexes.py`
- Modify: `platforms/ingestion-service/src/ingestion/models/run.py`
- Test: `platforms/ingestion-service/tests/unit/test_migration.py`

**Interfaces:**
- Produces: indexes `ix_test_results_test_key_run` on `test_results(test_key, run_id)` and `ix_test_runs_project_started` on `test_runs(project_id, started_at)`, in both the migration and the models.

- [ ] **Step 1: Write the failing test**

Add to the end of `platforms/ingestion-service/tests/unit/test_migration.py`:

```python
def test_analytics_indexes_exist(migrated_engine):
    inspector = inspect(migrated_engine)
    result_indexes = {ix["name"]: ix["column_names"] for ix in inspector.get_indexes("test_results")}
    run_indexes = {ix["name"]: ix["column_names"] for ix in inspector.get_indexes("test_runs")}
    assert result_indexes["ix_test_results_test_key_run"] == ["test_key", "run_id"]
    assert run_indexes["ix_test_runs_project_started"] == ["project_id", "started_at"]


def test_model_indexes_match_the_migration():
    assert "ix_test_results_test_key_run" in {ix.name for ix in Base.metadata.tables["test_results"].indexes}
    assert "ix_test_runs_project_started" in {ix.name for ix in Base.metadata.tables["test_runs"].indexes}
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `SECRET_KEY=x $PY -m pytest tests/unit/test_migration.py -q`
Expected: the two new tests fail with `KeyError: 'ix_test_results_test_key_run'` / `AssertionError`.

- [ ] **Step 3: Migration and models**

`platforms/ingestion-service/alembic/versions/003_analytics_indexes.py`:

```python
"""indexes for the analytics queries

Revision ID: 003
Revises: 002
Create Date: 2026-10-01
"""
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # One test's executions (history, flaky) without scanning every result
    op.create_index("ix_test_results_test_key_run", "test_results", ["test_key", "run_id"])
    # Every analytics window is on started_at (the existing index is on created_at)
    op.create_index("ix_test_runs_project_started", "test_runs", ["project_id", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_test_runs_project_started", table_name="test_runs")
    op.drop_index("ix_test_results_test_key_run", table_name="test_results")
```

In `platforms/ingestion-service/src/ingestion/models/run.py`:
- In `Run.__table_args__`, after `Index("ix_test_runs_project_branch", "project_id", "branch"),` add
  `Index("ix_test_runs_project_started", "project_id", "started_at"),`
- In `RunResult.__table_args__`, after the `CheckConstraint(...)` line add
  `Index("ix_test_results_test_key_run", "test_key", "run_id"),`

- [ ] **Step 4: Run the tests to see them pass**

Run: `SECRET_KEY=x $PY -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd ../..
git status --short
git add platforms/ingestion-service/alembic/versions/003_analytics_indexes.py platforms/ingestion-service/src/ingestion/models/run.py platforms/ingestion-service/tests/unit/test_migration.py
git commit -m "feat(ingestion): indexes for the analytics queries (migration 003)

test_results(test_key, run_id) for one test's executions and
test_runs(project_id, started_at) for every analytics window.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Trends and test list endpoints

**Files:**
- Create: `platforms/ingestion-service/src/ingestion/schemas/analytics.py`
- Create: `platforms/ingestion-service/src/ingestion/service/analytics_service.py`
- Create: `platforms/ingestion-service/src/ingestion/api/v1/endpoints/analytics.py`
- Modify: `platforms/ingestion-service/src/ingestion/api/v1/api.py`
- Test: `platforms/ingestion-service/tests/integration/test_analytics_endpoints.py`

**Interfaces:**
- Consumes: `RunRow`, `daily`, `window_start`, `pass_rate`, `as_utc` (Task 1); fixtures `client`, `auth`, `project_role`, `make_key`, `db`, `http`.
- Produces:
  - `analytics_service.trend_rows(db, project_id, since, branch, environment) -> List[RunRow]`
  - `analytics_service.list_tests(db, project_id, since, *, sort, search, limit, offset) -> List[dict]`
  - `analytics_service.latest_executions(db, filters: list, keys_clause) -> Dict[str, LatestExecution]` (used again in Task 5)
  - `analytics_service.window_filters(project_id, since, branch=None) -> list`
  - Schemas `TrendDay`, `TrendsOut`, `CountsOut`, `StatsRowOut`, `ExecutionOut`, `HistoryOut`, `CommitRef`, `FlakyOut`.
  - `endpoints.analytics.router` mounted at `/projects/{project_id}/analytics`; `endpoints.analytics._now()` (tests may monkeypatch).
  - Test-file fixture `seed(...)` and constants `BASE`, `ALL_ROLES` (Task 5 appends to the same file).

- [ ] **Step 1: Write the failing tests**

`platforms/ingestion-service/tests/integration/test_analytics_endpoints.py`:

```python
from collections import Counter
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from src.ingestion.models import Run, RunResult
from src.ingestion.service.ingest_service import test_key as key_of

BASE = "/api/v1/projects/1/analytics"
ALL_ROLES = ("owner", "admin", "member", "viewer", "billing_manager")


@pytest.fixture
def seed(db, make_key):
    """seed(...) inserts one run with the given results: (name, status, duration_ms) tuples."""
    keys = {}

    def _seed(project_id=1, days_ago=0, minutes_ago=0, branch="main", commit_sha=None, environment=None,
              results=(("t1", "passed", 10),), message=None):
        if project_id not in keys:
            keys[project_id] = make_key(project_id=project_id)[0]
        start = datetime.now(timezone.utc) - timedelta(days=days_ago, minutes=minutes_ago)
        counts = Counter(status for _, status, _ in results)
        run = Run(project_id=project_id, api_key_id=keys[project_id].id, request_hash="h", ci_provider="local",
                  branch=branch, commit_sha=commit_sha, environment=environment, started_at=start,
                  finished_at=start + timedelta(seconds=1), duration_ms=1000, total=len(results),
                  passed=counts["passed"], failed=counts["failed"], skipped=counts["skipped"],
                  errored=counts["errored"], created_at=start)
        db.add(run)
        db.flush()
        for name, status, duration in results:
            db.add(RunResult(run_id=run.id, test_key=key_of("s", "C", name), suite="s", class_name="C", name=name,
                             status=status, duration_ms=duration,
                             message=message if message is not None else (None if status == "passed" else f"{name} {status}")))
        db.commit()
        return run

    return _seed


def get(client, auth, path):
    return client.get(BASE + path, headers=auth())


@pytest.mark.parametrize("role", ALL_ROLES)
@pytest.mark.parametrize("path", ["/trends", "/tests"])
def test_every_reading_role_can_read(client, auth, project_role, role, path):
    project_role(role)
    assert get(client, auth, path).status_code == 200


@pytest.mark.parametrize("path", ["/trends", "/tests"])
def test_access_failures_behave_like_the_run_endpoints(client, auth, project_role, path):
    project_role(status_code=404, body={"detail": "Project not found"})
    assert get(client, auth, path).status_code == 404
    project_role(exc=httpx.ConnectError("refused"))
    assert get(client, auth, path).status_code == 503
    assert client.get(BASE + path).status_code == 401


def test_trends_count_runs_per_day(client, auth, project_role, seed):
    project_role("viewer")
    seed(results=(("a", "passed", 10), ("b", "failed", 20), ("c", "skipped", 0)))
    seed(days_ago=1, results=(("a", "passed", 10),))

    body = get(client, auth, "/trends?days=3").json()

    assert body["tz"] == "UTC" and len(body["days"]) == 3
    before, yesterday, today = body["days"]
    assert (today["runs"], today["total"], today["passed"], today["failed"], today["skipped"]) == (1, 3, 1, 1, 1)
    assert today["pass_rate"] == 0.5 and today["avg_run_duration_ms"] == 1000
    assert yesterday["runs"] == 1 and yesterday["pass_rate"] == 1.0
    assert before["runs"] == 0 and before["pass_rate"] is None


def test_trends_filter_by_branch_and_environment(client, auth, project_role, seed):
    project_role()
    seed(branch="main", environment="staging")
    seed(branch="dev", environment="prod")

    def runs(query):
        return get(client, auth, f"/trends?days=1{query}").json()["days"][0]["runs"]

    assert (runs(""), runs("&branch=main"), runs("&environment=prod"), runs("&branch=main&environment=prod")) == (2, 1, 1, 0)


def test_trends_ignore_other_projects(client, auth, project_role, seed):
    project_role()
    seed(project_id=2)
    assert get(client, auth, "/trends?days=1").json()["days"][0]["runs"] == 0


def test_trends_echo_the_time_zone(client, auth, project_role):
    project_role()
    body = get(client, auth, "/trends?days=7&tz=Europe/Lisbon").json()
    assert body["tz"] == "Europe/Lisbon" and len(body["days"]) == 7


def test_tests_list_counts_and_last_status(client, auth, project_role, seed):
    project_role()
    seed(days_ago=2, results=(("a", "failed", 10), ("b", "passed", 30)))
    seed(days_ago=1, results=(("a", "passed", 20), ("b", "passed", 50)))

    rows = get(client, auth, "/tests").json()

    a = next(r for r in rows if r["name"] == "a")
    assert a["test_key"] == key_of("s", "C", "a")
    assert (a["suite"], a["class_name"]) == ("s", "C")
    assert (a["runs"], a["passed"], a["failed"], a["errored"], a["skipped"]) == (2, 1, 1, 0, 0)
    assert (a["pass_rate"], a["avg_duration_ms"], a["last_status"]) == (0.5, 15, "passed")
    assert a["last_seen"] is not None


def test_tests_sort(client, auth, project_role, seed):
    project_role()
    seed(results=(("slow", "passed", 900), ("flaky", "failed", 10), ("zeta", "passed", 5)))
    seed(results=(("slow", "passed", 900), ("flaky", "errored", 10), ("zeta", "passed", 5)))

    def names(sort):
        return [r["name"] for r in get(client, auth, f"/tests?sort={sort}").json()]

    assert names("failures")[0] == "flaky"
    assert names("duration")[0] == "slow"
    assert names("name") == ["flaky", "slow", "zeta"]


def test_tests_search_matches_literally(client, auth, project_role, seed):
    project_role()
    seed(results=(("100% done", "passed", 1), ("a_b", "passed", 1), ("axb", "passed", 1), ("back\\slash", "passed", 1)))

    def names(term):
        return sorted(r["name"] for r in client.get(BASE + "/tests", params={"search": term}, headers=auth()).json())

    assert names("%") == ["100% done"]
    assert names("a_b") == ["a_b"]
    assert names("\\") == ["back\\slash"]
    assert names("A_B") == ["a_b"]  # case-insensitive


def test_tests_paging(client, auth, project_role, seed):
    project_role()
    seed(results=(("a", "passed", 1), ("b", "passed", 1), ("c", "passed", 1)))
    assert [r["name"] for r in get(client, auth, "/tests?sort=name&limit=2&offset=1").json()] == ["b", "c"]


def test_tests_window(client, auth, project_role, seed):
    project_role()
    seed(days_ago=40, results=(("old", "passed", 1),))
    assert get(client, auth, "/tests?days=30").json() == []
    assert [r["name"] for r in get(client, auth, "/tests?days=60").json()] == ["old"]


@pytest.mark.parametrize("query", [
    "/trends?days=0", "/trends?days=366", "/trends?tz=Not/AZone", "/trends?tz=..%2F..%2Fetc%2Fpasswd",
    "/trends?tz=", "/tests?days=91", "/tests?sort=bogus", "/tests?limit=201", "/tests?offset=-1",
    "/tests?search=" + "x" * 201,
])
def test_invalid_parameters_are_422(client, auth, project_role, query):
    project_role()
    assert get(client, auth, query).status_code == 422
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `SECRET_KEY=x $PY -m pytest tests/integration/test_analytics_endpoints.py -q`
Expected: failures with 404 for every `/analytics` path (the role/422 tests included).

- [ ] **Step 3: Schemas**

`platforms/ingestion-service/src/ingestion/schemas/analytics.py`:

```python
"""Response models for /projects/{id}/analytics/*. No class name may start with "Test":
pytest would try to collect it wherever a test module imports it."""
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel


class TrendDay(BaseModel):
    date: str
    runs: int
    total: int
    passed: int
    failed: int
    errored: int
    skipped: int
    pass_rate: Optional[float] = None
    avg_run_duration_ms: Optional[int] = None
    max_run_duration_ms: Optional[int] = None


class TrendsOut(BaseModel):
    tz: str
    days: List[TrendDay]


class CountsOut(BaseModel):
    runs: int
    passed: int
    failed: int
    errored: int
    skipped: int
    pass_rate: Optional[float] = None
    avg_duration_ms: Optional[int] = None


class StatsRowOut(CountsOut):
    test_key: str
    suite: str
    class_name: str
    name: str
    last_status: str
    last_seen: datetime


class ExecutionOut(BaseModel):
    run_id: int
    started_at: datetime
    branch: Optional[str] = None
    commit_sha: Optional[str] = None
    environment: Optional[str] = None
    status: str
    duration_ms: int
    message: Optional[str] = None


class HistoryOut(BaseModel):
    test_key: str
    suite: str
    class_name: str
    name: str
    summary: CountsOut
    executions: List[ExecutionOut]


class CommitRef(BaseModel):
    commit_sha: str
    environment: Optional[str] = None


class FlakyOut(BaseModel):
    test_key: str
    suite: str
    class_name: str
    name: str
    reason: Literal["same_commit", "flips"]
    commits: List[CommitRef]
    flips: Optional[int] = None
    flip_rate: Optional[float] = None
    runs: int
    last_status: str
    last_seen: datetime
```

- [ ] **Step 4: Queries**

`platforms/ingestion-service/src/ingestion/service/analytics_service.py`:

```python
"""Database queries for the analytics endpoints. Counting stays in SQL; the ranking and day
grouping live in src/ingestion/analytics."""
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from src.ingestion.analytics.flaky import LatestExecution
from src.ingestion.analytics.trends import RunRow, as_utc, pass_rate
from src.ingestion.models import Run, RunResult


def _count(*statuses: str):
    return func.sum(case((RunResult.status.in_(statuses), 1), else_=0))


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def window_filters(project_id: int, since: datetime, branch: Optional[str] = None) -> list:
    filters = [Run.project_id == project_id, Run.started_at >= since]
    if branch is not None:
        filters.append(Run.branch == branch)
    return filters


def trend_rows(db: Session, project_id: int, since: datetime, branch: Optional[str],
               environment: Optional[str]) -> List[RunRow]:
    query = db.query(Run.started_at, Run.total, Run.passed, Run.failed, Run.errored, Run.skipped,
                     Run.duration_ms).filter(*window_filters(project_id, since, branch))
    if environment is not None:
        query = query.filter(Run.environment == environment)
    return [RunRow(*row) for row in query.all()]


def latest_executions(db: Session, filters: list, keys_clause) -> Dict[str, LatestExecution]:
    """The newest execution (started_at, then run id) of each test matching the filters."""
    ranked = (
        select(
            RunResult.test_key, RunResult.suite, RunResult.class_name, RunResult.name, RunResult.status,
            Run.started_at,
            func.row_number().over(
                partition_by=RunResult.test_key, order_by=(Run.started_at.desc(), Run.id.desc())
            ).label("position"),
        )
        .join(Run, Run.id == RunResult.run_id)
        .where(*filters, keys_clause)
    ).subquery()
    rows = db.execute(select(ranked).where(ranked.c.position == 1)).all()
    return {
        row.test_key: LatestExecution(row.test_key, row.suite, row.class_name, row.name, row.status,
                                      as_utc(row.started_at))
        for row in rows
    }


def list_tests(db: Session, project_id: int, since: datetime, *, sort: str, search: Optional[str],
               limit: int, offset: int) -> List[dict]:
    failures = _count("failed", "errored")
    average = func.avg(RunResult.duration_ms)
    name = func.max(RunResult.name)
    filters = window_filters(project_id, since)
    query = (
        db.query(
            RunResult.test_key, func.max(RunResult.suite), func.max(RunResult.class_name), name,
            func.count(RunResult.id), _count("passed"), _count("failed"), _count("errored"), _count("skipped"),
            average,
        )
        .join(Run, Run.id == RunResult.run_id)
        .filter(*filters)
        .group_by(RunResult.test_key)
    )
    if search:
        query = query.filter(RunResult.name.ilike(f"%{_escape_like(search)}%", escape="\\"))
    order = {"failures": failures.desc(), "duration": average.desc(), "name": name.asc()}[sort]
    rows = query.order_by(order, RunResult.test_key).offset(offset).limit(limit).all()

    latest = latest_executions(db, filters, RunResult.test_key.in_([row[0] for row in rows])) if rows else {}
    out = []
    for key, suite, class_name, test_name, runs, passed, failed, errored, skipped, avg in rows:
        last = latest[key]
        out.append({
            "test_key": key, "suite": suite, "class_name": class_name, "name": test_name,
            "runs": runs, "passed": int(passed), "failed": int(failed), "errored": int(errored),
            "skipped": int(skipped), "pass_rate": pass_rate(int(passed), runs, int(skipped)),
            "avg_duration_ms": round(float(avg)) if avg is not None else None,
            "last_status": last.status, "last_seen": last.started_at,
        })
    return out
```

- [ ] **Step 5: Routes**

`platforms/ingestion-service/src/ingestion/api/v1/endpoints/analytics.py`:

```python
"""Read-only analytics over a project's runs, with the run endpoints' access rule."""
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.ingestion.analytics.trends import daily, window_start
from src.ingestion.api.deps import READ_ROLES, ProjectAccess, get_db, require_project_role
from src.ingestion.schemas.analytics import StatsRowOut, TrendsOut
from src.ingestion.service import analytics_service

router = APIRouter()  # mounted at /projects/{project_id}/analytics


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        # ValueError: not a valid zone key at all (e.g. a path); never read as a file
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unknown time zone: {name!r}")


@router.get("/trends", response_model=TrendsOut)
def trends(
    days: int = Query(30, ge=1, le=365),
    tz: str = Query("UTC", min_length=1, max_length=64),
    branch: Optional[str] = Query(None, max_length=255),
    environment: Optional[str] = Query(None, max_length=100),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    zone = _zone(tz)
    now = _now()
    rows = analytics_service.trend_rows(db, access.project_id, window_start(now, days, zone), branch, environment)
    return {"tz": tz, "days": daily(rows, now, days, zone)}


@router.get("/tests", response_model=List[StatsRowOut])
def tests(
    days: int = Query(30, ge=1, le=90),
    sort: Literal["failures", "duration", "name"] = Query("failures"),
    search: Optional[str] = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    since = _now() - timedelta(days=days)
    return analytics_service.list_tests(db, access.project_id, since, sort=sort, search=search,
                                        limit=limit, offset=offset)
```

In `platforms/ingestion-service/src/ingestion/api/v1/api.py`, change `from src.ingestion.api.v1.endpoints import api_keys, collect, runs` to `from src.ingestion.api.v1.endpoints import analytics, api_keys, collect, runs` and, after the `runs.project_router` line, add:

```python
api_router.include_router(analytics.router, prefix="/projects/{project_id}/analytics", tags=["analytics"])
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `SECRET_KEY=x $PY -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
cd ../..
git status --short
git add platforms/ingestion-service/src platforms/ingestion-service/tests/integration/test_analytics_endpoints.py
git commit -m "feat(ingestion): analytics trends and test list endpoints

GET /projects/{id}/analytics/trends (daily, in a requested time zone,
zero-filled) and /tests (per-test counts, pass rate, average duration,
last status; sorted, searched literally, paged). Same access rule as the
run endpoints.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: History and flaky endpoints

**Files:**
- Modify: `platforms/ingestion-service/src/ingestion/service/analytics_service.py`
- Modify: `platforms/ingestion-service/src/ingestion/api/v1/endpoints/analytics.py`
- Test: `platforms/ingestion-service/tests/integration/test_analytics_endpoints.py` (appended)

**Interfaces:**
- Consumes: `rank_flaky`, `FlipCount`, `MixedCommit` (Task 2); `latest_executions`, `window_filters`, `_count` (Task 4); the `seed` fixture and `BASE`, `ALL_ROLES`, `get`, `key_of` (Task 4's test file).
- Produces:
  - `analytics_service.test_seen(db, project_id, test_key) -> bool`
  - `analytics_service.test_history(db, project_id, test_key, since, branch, limit) -> dict` (shape of `HistoryOut`)
  - `analytics_service.flaky_inputs(db, project_id, since, branch) -> Tuple[List[FlipCount], List[MixedCommit], Dict[str, LatestExecution]]`
  - Routes `GET /tests/{test_key}/history` and `GET /flaky`.

- [ ] **Step 1: Write the failing tests**

Append to `platforms/ingestion-service/tests/integration/test_analytics_endpoints.py`:

```python
# ---- history ------------------------------------------------------------------------------

def test_history_newest_first_with_limit_and_summary(client, auth, project_role, seed):
    project_role()
    for days_ago, status in ((3, "passed"), (2, "failed"), (1, "passed")):
        seed(days_ago=days_ago, commit_sha=f"c0ffee{days_ago}", results=(("a", status, 10 * days_ago),))
    key = key_of("s", "C", "a")

    body = get(client, auth, f"/tests/{key}/history?limit=2").json()

    assert (body["test_key"], body["suite"], body["class_name"], body["name"]) == (key, "s", "C", "a")
    assert [e["duration_ms"] for e in body["executions"]] == [10, 20]
    assert [e["commit_sha"] for e in body["executions"]] == ["c0ffee1", "c0ffee2"]
    assert body["summary"] == {"runs": 3, "passed": 2, "failed": 1, "errored": 0, "skipped": 0,
                               "pass_rate": 0.6667, "avg_duration_ms": 20}


def test_history_cuts_the_message_to_500_characters(client, auth, project_role, seed):
    project_role()
    seed(results=(("a", "failed", 1),), message="x" * 800)
    body = get(client, auth, f"/tests/{key_of('s', 'C', 'a')}/history").json()
    assert body["executions"][0]["message"] == "x" * 500


def test_history_filters_by_branch(client, auth, project_role, seed):
    project_role()
    seed(branch="main", results=(("a", "passed", 1),))
    seed(branch="dev", results=(("a", "failed", 1),))
    body = get(client, auth, f"/tests/{key_of('s', 'C', 'a')}/history?branch=dev").json()
    assert [e["status"] for e in body["executions"]] == ["failed"]
    assert body["summary"]["runs"] == 1


def test_history_of_an_unknown_test_is_404(client, auth, project_role):
    project_role()
    response = get(client, auth, f"/tests/{'0' * 64}/history")
    assert response.status_code == 404
    assert response.json() == {"detail": "Test not found"}


def test_history_of_another_projects_test_is_404(client, auth, project_role, seed):
    project_role()
    seed(project_id=2, results=(("a", "passed", 1),))
    assert get(client, auth, f"/tests/{key_of('s', 'C', 'a')}/history").status_code == 404


def test_history_of_a_known_test_outside_the_window_is_empty(client, auth, project_role, seed):
    project_role()
    seed(days_ago=40, results=(("a", "passed", 1),))
    body = get(client, auth, f"/tests/{key_of('s', 'C', 'a')}/history?days=30").json()
    assert body["executions"] == [] and body["name"] == "a"
    assert body["summary"] == {"runs": 0, "passed": 0, "failed": 0, "errored": 0, "skipped": 0,
                               "pass_rate": None, "avg_duration_ms": None}


@pytest.mark.parametrize("bad_key", ["xyz", "A" * 64, "0" * 63])
def test_history_rejects_a_malformed_key(client, auth, project_role, bad_key):
    project_role()
    assert get(client, auth, f"/tests/{bad_key}/history").status_code == 422


# ---- flaky --------------------------------------------------------------------------------

@pytest.mark.parametrize("role", ALL_ROLES)
def test_every_reading_role_can_read_flaky(client, auth, project_role, role):
    project_role(role)
    assert get(client, auth, "/flaky").status_code == 200


def test_flaky_end_to_end(client, auth, project_role, seed):
    project_role()
    # confirmed: a pass and a fail on one commit, one environment
    seed(minutes_ago=60, commit_sha="aaaaaaa", results=(("confirmed", "passed", 1),))
    seed(minutes_ago=59, commit_sha="aaaaaaa", results=(("confirmed", "failed", 1),))
    # suspected: flips on main, no commit
    for i, status in enumerate(("passed", "failed", "passed", "failed", "passed")):
        seed(minutes_ago=50 - i, results=(("flipper", status, 1),))
    # an environment-specific failure: not confirmed, and too few runs to count as flips
    seed(minutes_ago=40, commit_sha="bbbbbbb", environment="py39", results=(("envbug", "failed", 1),))
    seed(minutes_ago=39, commit_sha="bbbbbbb", environment="py312", results=(("envbug", "passed", 1),))
    # errored -> failed is not a flip
    for i, status in enumerate(("failed", "errored", "failed", "errored", "failed")):
        seed(minutes_ago=30 - i, results=(("broken", status, 1),))
    # skipped results are ignored: P S F S P S F S P is 5 runs with 4 flips
    for i, status in enumerate(("passed", "skipped", "failed", "skipped", "passed", "skipped", "failed", "skipped",
                                "passed")):
        seed(minutes_ago=20 - i, results=(("skippy", status, 1),))

    items = get(client, auth, "/flaky").json()

    # confirmed first; then flip rate 1.0 for both, the more recently seen first
    assert [(i["name"], i["reason"]) for i in items] == [("confirmed", "same_commit"), ("skippy", "flips"),
                                                         ("flipper", "flips")]
    assert items[0]["commits"] == [{"commit_sha": "aaaaaaa", "environment": None}]
    skippy = items[1]
    assert (skippy["runs"], skippy["flips"], skippy["flip_rate"], skippy["last_status"]) == (5, 4, 1.0, "passed")


def test_flips_are_counted_per_branch(client, auth, project_role, seed):
    project_role()
    # interleaved: main P, dev P, main P, dev F, main P -> per branch 1 flip in 3 pairs (0.3333);
    # counted across the interleaved stream it would be 2 in 4 (0.5)
    for i, (branch, status) in enumerate((("main", "passed"), ("dev", "passed"), ("main", "passed"),
                                          ("dev", "failed"), ("main", "passed"))):
        seed(minutes_ago=10 - i, branch=branch, results=(("t", status, 1),))
    items = get(client, auth, "/flaky").json()
    assert [(i["name"], i["flips"], i["flip_rate"]) for i in items] == [("t", 1, 0.3333)]


def test_flaky_filters_by_branch_and_window(client, auth, project_role, seed):
    project_role()
    for i, status in enumerate(("passed", "failed", "passed", "failed", "passed")):
        seed(days_ago=20, minutes_ago=i, results=(("old", status, 1),))
    for i, status in enumerate(("passed", "failed", "passed", "failed", "passed")):
        seed(minutes_ago=10 - i, branch="dev", results=(("devonly", status, 1),))

    assert [i["name"] for i in get(client, auth, "/flaky").json()] == ["devonly"]          # 14-day window
    assert sorted(i["name"] for i in get(client, auth, "/flaky?window_days=30").json()) == ["devonly", "old"]
    assert get(client, auth, "/flaky?branch=main").json() == []


@pytest.mark.parametrize("query", ["/flaky?window_days=0", "/flaky?window_days=91", "/flaky?min_runs=1",
                                   "/flaky?min_runs=1001", "/flaky?min_flip_rate=1.5", "/flaky?min_flip_rate=-0.1",
                                   "/tests/" + "0" * 64 + "/history?days=91", "/tests/" + "0" * 64 + "/history?limit=501"])
def test_invalid_history_and_flaky_parameters_are_422(client, auth, project_role, query):
    project_role()
    assert get(client, auth, query).status_code == 422
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `SECRET_KEY=x $PY -m pytest tests/integration/test_analytics_endpoints.py -q`
Expected: the new tests fail with 404 (no such routes); Task 4's tests still pass.

- [ ] **Step 3: Queries**

Append to `platforms/ingestion-service/src/ingestion/service/analytics_service.py`:

```python
MESSAGE_EXCERPT = 500


def test_seen(db: Session, project_id: int, test_key: str) -> bool:
    return db.query(RunResult.id).join(Run, Run.id == RunResult.run_id).filter(
        Run.project_id == project_id, RunResult.test_key == test_key
    ).first() is not None


test_seen.__test__ = False  # not a pytest test, despite the name


def test_history(db: Session, project_id: int, test_key: str, since: datetime, branch: Optional[str],
                 limit: int) -> dict:
    filters = window_filters(project_id, since, branch) + [RunResult.test_key == test_key]
    base = db.query(RunResult).join(Run, Run.id == RunResult.run_id).filter(*filters)
    rows = base.with_entities(
        Run.id, Run.started_at, Run.branch, Run.commit_sha, Run.environment, RunResult.status,
        RunResult.duration_ms, RunResult.message, RunResult.suite, RunResult.class_name, RunResult.name,
    ).order_by(Run.started_at.desc(), Run.id.desc()).limit(limit).all()
    runs, passed, failed, errored, skipped, avg = base.with_entities(
        func.count(RunResult.id), _count("passed"), _count("failed"), _count("errored"), _count("skipped"),
        func.avg(RunResult.duration_ms),
    ).one()

    if rows:
        identity = rows[0][8:11]
    else:  # known test, nothing in the window: identity from its latest execution ever
        identity = db.query(RunResult.suite, RunResult.class_name, RunResult.name).join(
            Run, Run.id == RunResult.run_id
        ).filter(Run.project_id == project_id, RunResult.test_key == test_key).order_by(
            Run.started_at.desc(), Run.id.desc()
        ).first()
    passed, failed, errored, skipped = (int(v or 0) for v in (passed, failed, errored, skipped))
    return {
        "test_key": test_key, "suite": identity[0], "class_name": identity[1], "name": identity[2],
        "summary": {
            "runs": runs, "passed": passed, "failed": failed, "errored": errored, "skipped": skipped,
            "pass_rate": pass_rate(passed, runs, skipped),
            "avg_duration_ms": round(float(avg)) if avg is not None else None,
        },
        "executions": [
            {"run_id": run_id, "started_at": as_utc(started_at), "branch": run_branch, "commit_sha": commit_sha,
             "environment": environment, "status": status, "duration_ms": duration_ms,
             "message": message[:MESSAGE_EXCERPT] if message is not None else None}
            for run_id, started_at, run_branch, commit_sha, environment, status, duration_ms, message, *_ in rows
        ],
    }


test_history.__test__ = False  # not a pytest test, despite the name


def flaky_inputs(db: Session, project_id: int, since: datetime, branch: Optional[str]):
    """Per-test flip totals, mixed (commit, environment) groups, and latest executions, for the
    tests with at least one failure in the window. All counting happens in the database."""
    filters = window_filters(project_id, since, branch)
    candidates = select(RunResult.test_key).join(Run, Run.id == RunResult.run_id).where(
        *filters, RunResult.status.in_(("failed", "errored"))
    ).distinct()
    executions = filters + [RunResult.status != "skipped", RunResult.test_key.in_(candidates)]

    outcome = case((RunResult.status == "passed", "pass"), else_="fail")
    sequence = (
        select(
            RunResult.test_key.label("test_key"),
            outcome.label("outcome"),
            func.lag(outcome).over(
                partition_by=(RunResult.test_key, Run.branch), order_by=(Run.started_at, Run.id)
            ).label("previous"),
        )
        .join(Run, Run.id == RunResult.run_id)
        .where(*executions)
    ).subquery()
    has_previous = sequence.c.previous.is_not(None)
    flip_rows = db.execute(
        select(
            sequence.c.test_key,
            func.count(),
            func.sum(case(((has_previous & (sequence.c.previous != sequence.c.outcome)), 1), else_=0)),
            func.sum(case((has_previous, 1), else_=0)),
        ).group_by(sequence.c.test_key)
    ).all()
    flips = [FlipCount(key, runs, int(flipped or 0), int(pairs or 0)) for key, runs, flipped, pairs in flip_rows]

    mixed_rows = db.execute(
        select(RunResult.test_key, Run.commit_sha, Run.environment, func.max(Run.started_at))
        .join(Run, Run.id == RunResult.run_id)
        .where(*executions, Run.commit_sha.is_not(None))
        .group_by(RunResult.test_key, Run.commit_sha, Run.environment)
        .having((_count("passed") > 0) & (_count("failed", "errored") > 0))
    ).all()
    mixed = [MixedCommit(key, sha, environment, as_utc(latest)) for key, sha, environment, latest in mixed_rows]

    latest = latest_executions(db, filters + [RunResult.status != "skipped"], RunResult.test_key.in_(candidates))
    return flips, mixed, latest
```

and change the import line `from src.ingestion.analytics.flaky import LatestExecution` to `from src.ingestion.analytics.flaky import FlipCount, LatestExecution, MixedCommit`.

- [ ] **Step 4: Routes**

In `platforms/ingestion-service/src/ingestion/api/v1/endpoints/analytics.py`:
- change `from fastapi import APIRouter, Depends, HTTPException, Query, status` to `from fastapi import APIRouter, Depends, HTTPException, Path, Query, status`;
- change `from src.ingestion.analytics.trends import daily, window_start` to `from src.ingestion.analytics.flaky import rank_flaky` + newline + `from src.ingestion.analytics.trends import daily, window_start`;
- change `from src.ingestion.schemas.analytics import StatsRowOut, TrendsOut` to `from src.ingestion.schemas.analytics import FlakyOut, HistoryOut, StatsRowOut, TrendsOut`;
- append:

```python
@router.get("/tests/{test_key}/history", response_model=HistoryOut)
def history(
    test_key: str = Path(..., pattern=r"^[0-9a-f]{64}$"),
    days: int = Query(30, ge=1, le=90),
    branch: Optional[str] = Query(None, max_length=255),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    if not analytics_service.test_seen(db, access.project_id, test_key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test not found")
    since = _now() - timedelta(days=days)
    return analytics_service.test_history(db, access.project_id, test_key, since, branch, limit)


@router.get("/flaky", response_model=List[FlakyOut])
def flaky(
    window_days: int = Query(14, ge=1, le=90),
    min_runs: int = Query(5, ge=2, le=1000),
    min_flip_rate: float = Query(0.3, ge=0.0, le=1.0),
    branch: Optional[str] = Query(None, max_length=255),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    since = _now() - timedelta(days=window_days)
    flips, mixed, latest = analytics_service.flaky_inputs(db, access.project_id, since, branch)
    return rank_flaky(flips, mixed, latest, min_runs=min_runs, min_flip_rate=min_flip_rate)
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `SECRET_KEY=x $PY -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
cd ../..
git status --short
git add platforms/ingestion-service/src platforms/ingestion-service/tests/integration/test_analytics_endpoints.py
git commit -m "feat(ingestion): test history and flaky-test endpoints

GET /projects/{id}/analytics/tests/{test_key}/history (newest first,
summary over the window, message excerpt, 404 for a test never seen in
the project) and /flaky (same commit + environment confirmed; flips per
branch suspected; counted in SQL with window functions, ranked in Python).

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Gateway, smoke checks, benchmark, docs

**Files:**
- Modify: `gateway/nginx.conf.template`
- Modify: `scripts/smoke_gateway.sh`
- Create: `scripts/analytics_benchmark.py`
- Modify: `platforms/ingestion-service/README.md`, `TODO.md`

**Interfaces:**
- Consumes: the four routes (Tasks 4–5); `analytics_service.trend_rows`, `list_tests`, `test_history`, `flaky_inputs`; `daily`, `window_start`, `rank_flaky`.
- Produces: routing, 7 smoke checks, measured timings in the README.

- [ ] **Step 1: Gateway**

In `gateway/nginx.conf.template`, replace

```nginx
        location ~ ^/api/v1/projects/[0-9]+/(api-keys|runs)(/|$) {
```

with

```nginx
        location ~ ^/api/v1/projects/[0-9]+/(api-keys|runs|analytics)(/|$) {
```

and in the comment above it change `/api/v1/projects/{id}/api-keys` / `and /runs away` to mention analytics: `# A regex location wins over prefix locations, so this takes /api/v1/projects/{id}/api-keys,` / `# /runs and /analytics away from project-service's /api/v1/projects prefix below.`

Run: `docker build -q -t qa-vision/gateway:check gateway > /dev/null && docker run --rm qa-vision/gateway:check nginx -t`
Expected: `... test is successful`.

- [ ] **Step 2: Smoke checks**

In `scripts/smoke_gateway.sh`, insert immediately before the line `check "revoke the key" 204 DELETE "$BASE/api/v1/projects/$PROJECT_ID/api-keys/$KEY_ID" "${AUTH[@]}"`:

```bash
# ---- analytics, through the gateway's overlap route ----
check "analytics trends -> ingestion-service (overlap route)" 200 GET \
  "$BASE/api/v1/projects/$PROJECT_ID/analytics/trends?days=2" "${AUTH[@]}"
if grep -qE '"runs":[1-9]' "$TMP/body"; then
  pass "... the runs uploaded above are counted"
else
  fail "... no runs counted: $(head -c 300 "$TMP/body")"
fi
check "analytics tests" 200 GET "$BASE/api/v1/projects/$PROJECT_ID/analytics/tests?search=fails" "${AUTH[@]}"
body_has "... lists the failing test" '"name":"fails"'
FAILS_KEY="$(sed -n 's/.*"test_key":"\([0-9a-f]\{64\}\)".*/\1/p' "$TMP/body" | head -1)"
check "analytics history of that test" 200 GET \
  "$BASE/api/v1/projects/$PROJECT_ID/analytics/tests/${FAILS_KEY:-0}/history" "${AUTH[@]}"
body_has "... with its executions" '"executions":[{'
check "analytics flaky" 200 GET "$BASE/api/v1/projects/$PROJECT_ID/analytics/flaky" "${AUTH[@]}"

```

Run: `bash -n scripts/smoke_gateway.sh && echo syntax-ok`
Expected: `syntax-ok`.

- [ ] **Step 3: Benchmark script**

`scripts/analytics_benchmark.py`:

```python
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
    timed("flaky, 90 days", lambda: rank_flaky(*analytics_service.flaky_inputs(db, PROJECT, since90, None),
                                                min_runs=5, min_flip_rate=0.3))
finally:
    db.rollback()
    run_ids = select(Run.id).where(Run.project_id == PROJECT)
    db.execute(delete(RunResult).where(RunResult.run_id.in_(run_ids)))
    db.execute(delete(Run).where(Run.project_id == PROJECT))
    db.execute(delete(ApiKey).where(ApiKey.project_id == PROJECT))
    db.commit()
    db.close()
```

- [ ] **Step 4: Run the stack, the smoke test and the benchmark**

Run (repository root, Git Bash). A throwaway compose project keeps the dev data untouched:

```bash
export SECRET_KEY=local-smoke-secret INTERNAL_API_PASSWORD=local-internal-secret GATEWAY_HTTP_PORT=18080 COMPOSE_PROJECT_NAME=qav-analytics-check
docker compose up -d --build --wait --wait-timeout 300 gateway
bash scripts/smoke_gateway.sh
docker compose exec -T ingestion-service python - < scripts/analytics_benchmark.py
docker compose down --volumes
```

Expected: every smoke line `ok`, including the analytics checks, last line `all gateway checks passed`; the benchmark prints a seeding line and one timing per query, each **under 3000 ms**. Record the printed timings for Step 5. If any query is over 3000 ms, keep the numbers, record a ledger ruling, and add the summary-table TODO note with the measured figure in Step 5.

- [ ] **Step 5: Docs**

In `platforms/ingestion-service/README.md`, insert before the `## Operations` heading:

```markdown
## Analytics

Read-only, under `/api/v1/projects/{project_id}/analytics/`, for every role that can read runs:

| Endpoint | Returns |
|---|---|
| `GET /trends?days=30&tz=UTC&branch=&environment=` | One entry per local day (`days` 1–365, zone `tz`), oldest first, empty days zero-filled: runs, counts, `pass_rate`, average and maximum run duration |
| `GET /tests?days=30&sort=failures&search=&limit=50&offset=0` | One row per test in the window (`days` 1–90): counts, `pass_rate`, average duration, last status and when last seen; `sort` is `failures`, `duration` or `name`; `search` matches the name literally, case-insensitively |
| `GET /tests/{test_key}/history?days=30&branch=&limit=100` | One test: a summary over the window and its executions, newest first, with the message cut to 500 characters. 404 if the test was never seen in this project |
| `GET /flaky?window_days=14&min_runs=5&min_flip_rate=0.3&branch=` | At most 100 flaky tests |

- `pass_rate` = passed ÷ (total − skipped); errored counts as not passed; `null` when nothing ran.
- **Flaky, confirmed (`same_commit`):** the test both passed and failed (or errored) on the same commit **in the same environment**. Set `QAV_ENVIRONMENT` (or `--environment`) per CI matrix leg: legs that do not set it share one environment, so a failure specific to one leg shows as confirmed.
- **Flaky, suspected (`flips`):** for other tests, the share of consecutive executions on a branch whose outcome (pass vs failed/errored) changed, over at least `min_runs` executions; skipped results are ignored.
- Computed on request; migration 003 adds the indexes the queries use.

Measured on a throwaway stack with 1,980 runs × 1,000 tests (about 2 million results over 90 days), PostgreSQL 15 in Docker:

| Query | Time |
|---|---|
| trends, 365 days | <fill in from Task 6 Step 4> |
| tests, 90 days, sort=failures | <fill in> |
| tests, 90 days, search | <fill in> |
| history, 90 days | <fill in> |
| flaky, 14 days | <fill in> |
| flaky, 90 days | <fill in> |

Regenerate with `docker compose exec -T ingestion-service python - < scripts/analytics_benchmark.py` in a throwaway stack.

```

Replace each `<fill in…>` with the milliseconds printed in Step 4 (for example `412 ms`) — the README must not ship with a placeholder.

In `TODO.md`, insert immediately before the line `### Phase 4: Test Management`:

```markdown
### Analytics API (Phase 3, step 1)
- [x] Daily trends in a requested time zone; per-test list, history; flaky detection (same commit + environment, flip rate)
- [ ] Summary tables when live queries get slow
- [ ] Weekly and monthly views
- [ ] Branch comparison
- [ ] Mute / acknowledge a flaky test
- [ ] CSV export
- [ ] Dashboard UI

```

- [ ] **Step 6: Commit**

```bash
git status --short
git add gateway/nginx.conf.template scripts/smoke_gateway.sh scripts/analytics_benchmark.py platforms/ingestion-service/README.md TODO.md
git commit -m "feat: analytics through the gateway; smoke checks, benchmark, docs

The gateway's overlap route sends /projects/{id}/analytics to
ingestion-service; the smoke test reads trends, tests, a history and
the flaky list through it. A one-off benchmark seeds ~2 million results
and times each query; the timings are in the README.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```
