# Report Deep Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Execution: subagent-driven.** A fresh implementer subagent per task, a fresh reviewer per task, then one whole-branch review at the end of each phase. Each phase (P1, P2, P3) ships on its own: its last task runs every suite and the CI-mirroring pre-push steps.

**Goal:** The Report page gets filters kept in the URL (period, branch, environment, CI provider, origin, area, suite) and five analysis sections (summary with deltas, failure causes, by area, regressions and stability, coverage and duration), each with a chart, a table and a CSV export, and Print / Save as PDF keeps working.

**Architecture:**
- **ingestion-service** gets one read-only endpoint, `POST /api/v1/projects/{id}/analytics/report`. One scoped-runs query (period plus the previous period of the same length) feeds every section. Pure arithmetic (periods, buckets, signatures, streaks, flips, percentiles) lives in `src/ingestion/analytics/report_*.py`; the SQL lives in `src/ingestion/service/report_service.py`. Migration 016 adds a partial index on failing results (P2).
- **test-management-service** gets `GET /case-areas` (every active case, dictionary-encoded) and `GET /run-requests/run-urls` (the GitHub run URLs of Play requests).
- **ADR-022 holds:** services never call each other. The dashboard turns area and suite filters into test keys from `case-areas`, sends Play URLs from `run-urls` for the origin filter, and groups ingestion's per-test rows by area (P3).
- **The gateway** routes `case-areas` to test-management and gzips exactly two responses (`case-areas` and `analytics/report`).
- **The dashboard** moves the page to `src/pages/report/`, with `useReportFilters` (URL state), `lib/reportScope.ts` (pure joins), one component per section, a print header and a "Report updated" live region.

**Tech Stack:** FastAPI, SQLAlchemy 2.1, Alembic, pydantic 2, pytest (SQLite in tests; PostgreSQL 15 in the gateway smoke job and the bench script). React 19, TypeScript 6, TanStack Query 5, Recharts 2, vitest 5 + msw 3 + Testing Library, lucide-react.

**Spec:** `docs/superpowers/specs/2026-10-08-report-deep-analysis-design.md`. The spec is binding, including "Decisions confirmed by the user (2026-10-08)". Executors read it with this plan. Where this plan makes a ruling the spec left open, the ruling is listed under "Rulings" below and repeated in the task.

## Global Constraints

Copied from the spec. Every task implicitly includes all of them.

- **ADR-022:** services never call each other; the dashboard joins. Ingestion never calls test-management or project-service for report data.
- **Roles:** every report and `case-areas` / `run-urls` endpoint is open to every project role (`READ_ROLES`). A non-member gets 404; no token gets 401.
- **Report request limits (ingestion, 422 otherwise, message names the rule):**
  - `from` ≤ `to`; span (`to` − `from` + 1) ≤ **90** days; `to` ≤ today in `tz` + 1 day; `from` ≥ today − **400** days.
  - `tz` checked against the zone list with the existing `_zone()`.
  - `branch` ≤ 255 characters, `environment` ≤ 100, no NUL; an empty string means no filter.
  - `ci_provider` one of `CI_PROVIDERS` (`models/run.py`).
  - `origin` is `any` (default), `ci` or `qeos`. `requested_run_urls` is required when `origin` is not `any` ("requested_run_urls is required with origin"); each URL ≤ 2,048 characters, no NUL; at most **5,000** URLs; an empty list is allowed (`qeos` then matches nothing, `ci` everything); ignored when `origin = any`.
  - `test_keys`: optional; 1–**20,000** keys of 64 hexadecimal characters, lower-cased and de-duplicated by the server; `null` = no key filter; an empty list is a 422.
  - `sections`: 1–5 unique values of `summary`, `failure_causes`, `regressions`, `tests`, `duration`.
  - `bucket`: `auto` (default), `day` or `week`; `auto` is `day` for spans ≤ **31** days, else `week`; weeks start on Monday on the local calendar.
  - The body model uses `extra="forbid"`.
- **Definitions:** an execution is one `test_results` row; the outcome of a test in a run is its **last attempt** (highest `test_results.id`) among non-skipped rows; failing = `failed` or `errored`; pass rate = passed ÷ (executions − skipped) via the existing `pass_rate()`; the period runs from local midnight of `from` to local midnight after `to` (end exclusive); the previous period is the same number of days immediately before.
- **Query rules:** one scoped-runs query over `[previous.start, period.end)` through `ix_test_runs_project_started`; `test_keys` and URL lists go to PostgreSQL as one array parameter (`= ANY(CAST(:x AS varchar[]))`), never 20,000 bind parameters (SQLite tests use an expanding `IN`); every report query runs under `SET LOCAL statement_timeout = '20s'`; a timeout is a 503 with code `report_timeout` and "This report took too long. Narrow the period or the filters."; the handler never writes and ends its transaction before returning; no server-side cache.
- **case-areas:** cases with `status != 'archived'`; at most **50,000** cases, else 409 `too_many_cases`; folder = directory part of `source_path`; dictionaries `folders`, `features`, `labels`, `suites` are sorted and cases point into them by index; short field names `n`, `t`, `k`, `fo`, `fe`, `l`, `s`.
- **run-urls:** non-null `github_run_url` of requests with `requested_at >= since`, newest first, at most **5,000** (`truncated` above); registered before `/{request_id}`.
- **Gateway:** `gzip on; gzip_proxied any; gzip_types application/json; gzip_min_length 1024;` only inside the two locations for `case-areas` and `analytics/report`, never server-wide (BREACH).
- **Dashboard rules:**
  - Colours from tokens only (`index.css` `:root` and its dark blocks). Icons are lucide with `aria-hidden`. No `any`.
  - Reuse `PageHeader`, `FilterChips`, `FiltersDisclosure`, `FilterSelect`, `FolderSelect`, `StatusPill`, `SortableTh`, `NarrowMeta`, `ChartKit` (`ChartPatternDefs`, `SeriesLegend`, `DataTableDisclosure`, `PATTERN`), `lib/csv.ts`, `lib/chartFormat.ts`, `lib/sort.ts`, `Skeleton`, `ErrorBanner`.
  - Charts: a `figure` with an off-screen `figcaption`, Recharts `accessibilityLayer`, a `DataTableDisclosure`, never `role="img"`; status series use the shared textures; comparison lines are dashed with markers.
  - A section error is an `ErrorBanner` with Retry, never an empty period.
  - React Query `staleTime` 5 minutes; report key `["report", projectId, section, filters, caseAreasVersion]`; keys are never part of a query key.
  - **Invoke the `ui-ux-pro-max` skill before any dashboard UI edit** (every dashboard task that touches `.tsx` or `index.css`).
- **Commands:**
  - Python: `cd platforms/<svc> && SECRET_KEY=test .venv/Scripts/python -m pytest -q` (one file: append the path and `-q`).
  - Dashboard: `cd dashboard && npm run lint && npm run typecheck && npx vitest run --maxWorkers=4 && npm run build`.
- **Git:** work on `master`, never push (the user pushes; pre-push mirrors `ci.yml`). Another agent may be editing dashboard files: commit only your own paths: `git add <paths> && git commit -m "<msg>" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- <paths>`. Never `git add -A`.

## Rulings (gaps the spec left open)

1. **Default branch (decision 1).** project-service has no project-level default branch; it has repositories (`GET /projects/{id}/repositories`, ordered by id), each with `default_branch`. The report's default is the **first repository's** `default_branch`, else `main` (also when the call fails). The URL leaves `branch` out for the default; `branch=*` means every branch (`*` is not a legal git branch name). The chip reads "Branch: main (default)"; removing it writes `branch=*` ("Branch: all branches"); removing that returns to the default. "Clear all" returns to the default branch.
2. **Previous-period chart line.** `summary.buckets` alone cannot draw the dashed previous line, so `summary` also returns `previous_buckets`: same length and fields as `buckets`, where bucket *i* holds the previous-period runs whose local day + `days` falls in bucket *i*, and `date` is the bucket's date − `days`.
3. **Delta wording.** DESIGN.md's KPI rule ("the arrow is an icon, not a Unicode glyph") wins over the spec's "▲" examples: a lucide `ArrowUp`/`ArrowDown`/`Minus` icon plus the words, e.g. "up 1.2 pts vs previous 30 days" and the verdict word "better"/"worse".
4. **503 body.** The existing convention `{"detail": {"code": "report_timeout", "message": "..."}}` (as `run_active`), which `api/http.ts` already parses into `ApiError.code`. Same for 409 `too_many_cases`.
5. **`run-urls` look-back.** The dashboard asks `since` = previous period's `from` − 1 day, which can reach 491 days back. The endpoint accepts `since` up to **500** days back (the spec's 400 would 422 for old custom periods).
6. **P1 Flaky section with a custom range.** `/flaky` only knows "last N days": it is asked with `window_days = min(90, days from from to today)`, and the note says "Covers the last N days".
7. **"At least 5 non-skipped outcomes" in By area** uses executions − skipped (what the Flaky page counts as runs).
8. **PostgreSQL coverage.** CI runs the Python suites on SQLite only; the PostgreSQL paths (`ANY` arrays, `SET LOCAL`, the partial index) are exercised by new checks in `scripts/smoke_gateway.sh` (CI "Gateway and full stack" job) and by `scripts/bench_report.py`.
9. **List orders the spec does not fix:** newly failing by `failing_since` newest first; fixed by `fixed_at` newest first; longest failing by `failing_since` oldest first, then more consecutive failures; ties by `test_key`, then branch. Branches by runs, then name (no branch last). Facets by run count, then value.

## Review Focus

The inputs most likely to bite a person, that no single spec bullet pins; each has a test in the owning task.

1. **A period that crosses a DST change** (Lisbon, last Sunday of October): buckets and the previous period must stay on local calendar days, with no lost or doubled hour. Test in Task 1.
2. **A run whose URL differs only in case or has a trailing slash from GitHub** (`HTTPS://GitHub.com/...`): case must not matter; a trailing slash is a different URL (documented, not normalised). Test in Task 3.
3. **A test with retries where the last attempt passes after a failure in the same run**: the outcome is "passed", counts still count both rows. Tests in Tasks 4 (counts) and 20 (outcome).
4. **A hand-edited URL** (`period=45`, `from` after `to`, `ci=travis`, `area=bogus`, `suite=abc`): parameters dropped, the notice shown once, no request sent with them. Test in Task 10.
5. **A filter change while sections are still loading**: the in-flight requests are aborted and the old result is never shown under the new filters; "Report updated" is announced once. Test in Task 14.

---

## File map

**ingestion-service** (`platforms/ingestion-service/`)

| File | Phase | Responsibility |
|---|---|---|
| `src/ingestion/analytics/report_period.py` | P1 | Period, previous period, bucket choice and bucket index on the local calendar. Pure. |
| `src/ingestion/analytics/report_stats.py` | P2 | `percentile`, `mean` over ints. Pure. |
| `src/ingestion/analytics/report_causes.py` | P2 | Group failing occurrences by signature: new/recurring/resolved, cap 50 + other. Pure. |
| `src/ingestion/analytics/report_streaks.py` | P2 | Outcome sequences per (test, branch): newly failing, fixed, longest failing, time to fix, flips per bucket. Pure. |
| `src/ingestion/schemas/report.py` | P1 | `ReportIn` request model. |
| `src/ingestion/service/report_service.py` | P1–P3 | Scope, scoped runs, `in_list`, per-section queries, `build_report`, statement timeout. |
| `src/ingestion/api/v1/endpoints/report.py` | P1 | `POST /report` under `/projects/{id}/analytics`. |
| `src/ingestion/api/v1/api.py` | P1 | Mount the report router. |
| `src/ingestion/models/run.py` | P2 | Declare `ix_test_results_failing`. |
| `alembic/versions/016_report_indexes.py` | P2 | Partial index, concurrently on PostgreSQL. |
| `tests/conftest.py` | P1 | `seed_run`, `report_key`, `report_now` fixtures. |
| `tests/unit/test_report_period.py`, `test_report_stats.py`, `test_report_causes.py`, `test_report_streaks.py` | P1–P2 | Pure tests. |
| `tests/integration/test_report_api.py`, `test_report_summary.py`, `test_report_causes.py`, `test_report_regressions.py`, `test_report_tests_duration.py` | P1–P3 | Endpoint tests. |
| `scripts/bench_report.py` (repo root `scripts/`) | P2 | Sizes A and B, p50/p95 per section. |
| `README.md` | P1–P3 | Report endpoint, timing table. |

**test-management-service** (`platforms/test-management-service/`)

| File | Phase | Responsibility |
|---|---|---|
| `src/casebook/service/case_area_service.py` | P1 | The dictionary-encoded case list. |
| `src/casebook/api/v1/endpoints/case_areas.py` | P1 | `GET /case-areas`. |
| `src/casebook/service/run_request_service.py` | P1 | `run_urls()`. |
| `src/casebook/api/v1/endpoints/run_requests.py` | P1 | `GET /run-urls`, before `/{request_id}`. |
| `src/casebook/api/v1/api.py` | P1 | Mount `case-areas`. |
| `tests/integration/test_case_areas.py`, `test_run_urls.py` | P1 | Endpoint tests. |
| `README.md` | P1 | The two endpoints. |

**gateway and scripts:** `gateway/nginx.conf.template`, `scripts/smoke_gateway.sh` (P1).

**dashboard** (`dashboard/src/`)

| File | Phase | Responsibility |
|---|---|---|
| `api/report.ts` (+ `report.test.ts`) | P1–P3 | Types and `postReport`. |
| `api/cases.ts` (+ test) | P1 | `getCaseAreas`, decoding the short names. |
| `api/runRequests.ts` (+ test) | P1 | `getRunUrls`. |
| `lib/ciProviders.ts` | P1 | `CI_LABELS`, moved out of `RunsPage.tsx`. |
| `lib/reportScope.ts` (+ test) | P1, P3 | Area parsing, key resolution; P3 grouping, never-run, unlinked. |
| `lib/reportDelta.ts` (+ test) | P1 | Delta text and verdict. |
| `pages/report/useReportFilters.ts` (+ test) | P1 | URL state: parse, validate, normalise, presets in `tz`. |
| `pages/report/useReportRequest.ts` | P1 | Default branch, case-areas, run-urls gating; per-section queries. |
| `pages/report/ReportSection.tsx` | P1 | Section frame: loading, blocked, error (503/422), no runs. |
| `pages/report/ReportFilterBar.tsx` | P1 | Period chips, applied chips, Add filter form. |
| `pages/report/describeFilters.ts` | P1 | Filters as "Name: value" (chips, subtitle, print header); `formatPeriod`. |
| `pages/report/PrintHeader.tsx` | P1 | Print-only header. |
| `pages/report/useGrouping.ts` | P3 | The `group`/`depth` view setting shared by Sections 3 and 5. |
| `pages/report/testFixtures.ts` | P1–P3 | Report fixtures for the tests (imported by tests only). |
| `pages/report/DeltaTile.tsx` | P1 | KPI tile with delta. |
| `pages/report/sections/SummarySection.tsx` | P1 | Section 1. |
| `pages/report/sections/FlakySection.tsx` | P1 (removed P2) | The kept Flaky table with its note. |
| `pages/report/sections/FailureCausesSection.tsx` | P2 | Section 2. |
| `pages/report/sections/RegressionsSection.tsx` | P2 | Section 4. |
| `pages/report/sections/AreaSection.tsx` | P3 | Section 3. |
| `pages/report/sections/CoverageDurationSection.tsx` | P3 | Section 5. |
| `pages/report/ReportPage.tsx` (+ `ReportPage.test.tsx`) | P1–P3 | The page. Replaces `pages/ReportPage.tsx` and its test. |
| `App.tsx` | P1 | Import path. |
| `index.css` | P1–P3 | Report styles, print rules. |
| `test/server.ts` | P1 | Default handlers for the new endpoints. |

**docs:** `docs/architecture/adr/ADR-026-report-joins-in-the-dashboard.md` and `INDEX.md` (P1), `DESIGN.md` (P1–P3), `TODO.md` (P1: the origin marker item).

---

# Phase 1: filters and summary

### Task 1: Report periods and buckets (pure)

**Files:**
- Create: `platforms/ingestion-service/src/ingestion/analytics/report_period.py`
- Test: `platforms/ingestion-service/tests/unit/test_report_period.py`

**Interfaces:**
- Consumes: `as_utc` from `src/ingestion/analytics/trends.py`.
- Produces:
  - `class PeriodError(ValueError)`
  - `@dataclass(frozen=True) class Period(first: date, last: date, zone: ZoneInfo)` with properties `days: int`, `start: datetime` (aware UTC), `end: datetime` (aware UTC, exclusive), methods `previous() -> Period`, `out() -> dict` (`{"from","to","days","start","end"}`, ISO dates and `...Z` datetimes).
  - `check_period(first: date, last: date, zone: ZoneInfo, now: datetime) -> Period` (raises `PeriodError`).
  - `choose_bucket(requested: str, days: int) -> str` (`"day"` or `"week"`).
  - `bucket_starts(period: Period, bucket: str) -> list[date]`
  - `bucket_index(day: date, starts: list[date], bucket: str) -> Optional[int]`
  - `local_day(moment: datetime, zone: ZoneInfo) -> date`
  - `iso(moment: datetime) -> str`
  - Constants `MAX_SPAN_DAYS = 90`, `MAX_AGE_DAYS = 400`, `AUTO_DAY_LIMIT = 31`.

- [ ] **Step 1: Write the failing tests**

```python
"""Report periods on the user's calendar (spec: Terms, Filters, Request body)."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from src.ingestion.analytics.report_period import (
    Period, PeriodError, bucket_index, bucket_starts, check_period, choose_bucket, iso, local_day,
)

UTC = ZoneInfo("UTC")
LISBON = ZoneInfo("Europe/Lisbon")
NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


def test_a_period_runs_from_local_midnight_to_the_midnight_after_to():
    p = Period(date(2026, 9, 9), date(2026, 10, 8), LISBON)
    assert p.days == 30
    assert p.start == datetime(2026, 9, 8, 23, 0, tzinfo=timezone.utc)   # Lisbon is UTC+1 in September
    assert p.end == datetime(2026, 10, 8, 23, 0, tzinfo=timezone.utc)
    assert p.out() == {"from": "2026-09-09", "to": "2026-10-08", "days": 30,
                       "start": "2026-09-08T23:00:00Z", "end": "2026-10-08T23:00:00Z"}


def test_the_previous_period_has_the_same_length_and_ends_the_day_before():
    prev = Period(date(2026, 9, 9), date(2026, 10, 8), UTC).previous()
    assert (prev.first, prev.last, prev.days) == (date(2026, 8, 10), date(2026, 9, 8), 30)


def test_a_dst_change_inside_the_period_keeps_local_days():
    # Lisbon goes from UTC+1 to UTC at 01:00 UTC on 25 October 2026
    p = Period(date(2026, 10, 24), date(2026, 10, 26), LISBON)
    assert p.start == datetime(2026, 10, 23, 23, 0, tzinfo=timezone.utc)
    assert p.end == datetime(2026, 10, 27, 0, 0, tzinfo=timezone.utc)
    starts = bucket_starts(p, "day")
    assert starts == [date(2026, 10, 24), date(2026, 10, 25), date(2026, 10, 26)]
    late_on_the_25th = datetime(2026, 10, 25, 23, 30, tzinfo=timezone.utc)  # 23:30 local, after the change
    assert bucket_index(local_day(late_on_the_25th, LISBON), starts, "day") == 1


@pytest.mark.parametrize("first,last,message", [
    (date(2026, 10, 8), date(2026, 10, 1), "from must be on or before to"),
    (date(2026, 7, 1), date(2026, 10, 1), "at most 90"),
    (date(2026, 10, 1), date(2026, 10, 10), "to is in the future"),
    (date(2025, 9, 1), date(2025, 9, 5), "more than 400 days ago"),
])
def test_check_period_names_the_rule(first, last, message):
    with pytest.raises(PeriodError, match=message):
        check_period(first, last, UTC, NOW)


def test_tomorrow_is_allowed_for_clock_skew_and_90_days_is_the_limit():
    assert check_period(date(2026, 7, 12), date(2026, 10, 9), UTC, NOW).days == 90


def test_auto_bucket_is_day_up_to_31_days_then_week():
    assert choose_bucket("auto", 31) == "day"
    assert choose_bucket("auto", 32) == "week"
    assert choose_bucket("day", 90) == "day"
    assert choose_bucket("week", 7) == "week"


def test_weeks_start_on_monday_and_cover_the_period():
    p = Period(date(2026, 9, 9), date(2026, 10, 8), UTC)   # Wednesday to Thursday
    starts = bucket_starts(p, "week")
    assert starts[0] == date(2026, 9, 7) and starts[-1] == date(2026, 10, 5)
    assert all(s.weekday() == 0 for s in starts) and len(starts) == 5
    assert bucket_index(date(2026, 9, 9), starts, "week") == 0
    assert bucket_index(date(2026, 10, 8), starts, "week") == 4
    assert bucket_index(date(2026, 10, 12), starts, "week") is None


def test_iso_is_utc_with_z():
    assert iso(datetime(2026, 10, 8, 14, 2, 11, tzinfo=timezone.utc)) == "2026-10-08T14:02:11Z"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/unit/test_report_period.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.ingestion.analytics.report_period'`.

- [ ] **Step 3: Write the implementation**

```python
"""Report periods and buckets on the user's local calendar. Pure: no database, no clock.

The period is the days the user picked, from local midnight of `first` to local midnight after
`last` (end exclusive). The previous period is the same number of days just before it.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

from src.ingestion.analytics.trends import as_utc

MAX_SPAN_DAYS = 90
MAX_AGE_DAYS = 400
AUTO_DAY_LIMIT = 31


class PeriodError(ValueError):
    """A period the report refuses; the message names the rule and is the 422 detail."""


def local_midnight(day: date, zone: ZoneInfo) -> datetime:
    return datetime.combine(day, time.min, tzinfo=zone).astimezone(timezone.utc)


def iso(moment: datetime) -> str:
    return as_utc(moment).strftime("%Y-%m-%dT%H:%M:%SZ")


def local_day(moment: datetime, zone: ZoneInfo) -> date:
    return as_utc(moment).astimezone(zone).date()


@dataclass(frozen=True)
class Period:
    first: date
    last: date
    zone: ZoneInfo

    @property
    def days(self) -> int:
        return (self.last - self.first).days + 1

    @property
    def start(self) -> datetime:
        return local_midnight(self.first, self.zone)

    @property
    def end(self) -> datetime:
        return local_midnight(self.last + timedelta(days=1), self.zone)

    def previous(self) -> "Period":
        return Period(self.first - timedelta(days=self.days), self.first - timedelta(days=1), self.zone)

    def out(self) -> dict:
        return {"from": self.first.isoformat(), "to": self.last.isoformat(), "days": self.days,
                "start": iso(self.start), "end": iso(self.end)}


def check_period(first: date, last: date, zone: ZoneInfo, now: datetime) -> Period:
    if first > last:
        raise PeriodError("from must be on or before to")
    span = (last - first).days + 1
    if span > MAX_SPAN_DAYS:
        raise PeriodError(f"The period is {span} days; it can be at most {MAX_SPAN_DAYS}")
    today = local_day(now, zone)
    if last > today + timedelta(days=1):
        raise PeriodError("to is in the future")
    if first < today - timedelta(days=MAX_AGE_DAYS):
        raise PeriodError(f"from is more than {MAX_AGE_DAYS} days ago")
    return Period(first, last, zone)


def choose_bucket(requested: str, days: int) -> str:
    if requested != "auto":
        return requested
    return "day" if days <= AUTO_DAY_LIMIT else "week"


def bucket_starts(period: Period, bucket: str) -> List[date]:
    """Every bucket touching the period, oldest first; a week starts on Monday, so the first and
    last weeks may be partial."""
    if bucket == "day":
        return [period.first + timedelta(days=i) for i in range(period.days)]
    cursor = period.first - timedelta(days=period.first.weekday())
    starts = []
    while cursor <= period.last:
        starts.append(cursor)
        cursor += timedelta(days=7)
    return starts


def bucket_index(day: date, starts: List[date], bucket: str) -> Optional[int]:
    if not starts:
        return None
    offset = (day - starts[0]).days
    index = offset if bucket == "day" else offset // 7
    return index if 0 <= index < len(starts) and offset >= 0 else None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/unit/test_report_period.py -q`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add platforms/ingestion-service/src/ingestion/analytics/report_period.py platforms/ingestion-service/tests/unit/test_report_period.py
git commit -m "feat(ingestion): report periods and buckets on the local calendar" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- platforms/ingestion-service/src/ingestion/analytics/report_period.py platforms/ingestion-service/tests/unit/test_report_period.py
```

---

### Task 2: `POST /analytics/report`: request model, validation, roles, envelope, statement timeout

**Files:**
- Create: `platforms/ingestion-service/src/ingestion/schemas/report.py`
- Create: `platforms/ingestion-service/src/ingestion/service/report_service.py`
- Create: `platforms/ingestion-service/src/ingestion/api/v1/endpoints/report.py`
- Modify: `platforms/ingestion-service/src/ingestion/api/v1/api.py` (import `report`, include its router at `/projects/{project_id}/analytics`)
- Modify: `platforms/ingestion-service/tests/conftest.py` (append the fixtures below)
- Test: `platforms/ingestion-service/tests/integration/test_report_api.py`

**Interfaces:**
- Consumes: Task 1 (`check_period`, `PeriodError`, `choose_bucket`, `bucket_starts`, `iso`, `Period`); `_zone` and `NO_NUL` from `src/ingestion/api/v1/endpoints/analytics.py`; `READ_ROLES`, `require_project_role`, `get_db` from `api/deps.py`; `CI_PROVIDERS` from `models/run.py`.
- Produces:
  - `ReportIn` (pydantic; field `from_` aliased `from`), `SECTIONS: tuple[str, ...]`.
  - `report_service.Scope(project_id: int, period: Period, previous: Period, branch: Optional[str], environment: Optional[str], ci_provider: Optional[str], origin: str, urls: tuple[str, ...], keys: Optional[tuple[str, ...]])`, `Scope.from_request(project_id, body, period) -> Scope`.
  - `report_service.in_list(db, column, values, item_type) -> ColumnElement` (array parameter on PostgreSQL).
  - `report_service.ScopedRun(id, started_at, branch, duration_ms, total, passed, failed, errored, skipped, current: bool)`.
  - `report_service.scoped_runs(db, scope) -> list[ScopedRun]` (Task 3 fills in the filters; here it applies project and window only).
  - `report_service.build_report(db, scope, sections: list[str], bucket: str, now: datetime) -> dict` (envelope; sections are added by later tasks through `SECTION_BUILDERS: dict[str, Callable]`).
  - `report_service.limit_statement_time(db)`, `report_service.is_timeout(exc) -> bool`, `REPORT_TIMEOUT_MESSAGE`.
  - Endpoint module `report.py` with `_now()`, `router`.
  - conftest fixtures `seed_run`, `report_key(name) -> str`, `report_now`, and helper `post_report(client, auth, **body)`.

- [ ] **Step 1: Add the shared fixtures to `tests/conftest.py`**

Append at the end of `platforms/ingestion-service/tests/conftest.py`:

```python
# ---- report (docs/superpowers/specs/2026-10-08-report-deep-analysis-design.md) ----
REPORT_NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
REPORT_URL = "/api/v1/projects/1/analytics/report"


def report_key(name: str) -> str:
    """The test_key seed_run gives a result named `name` (suite "s", class "C")."""
    from src.ingestion.service.ingest_service import test_key
    return test_key("s", "C", name)


@pytest.fixture
def report_now(monkeypatch):
    """Freeze the report endpoint's clock at REPORT_NOW (Thursday 8 October 2026, 12:00 UTC)."""
    from src.ingestion.api.v1.endpoints import report
    monkeypatch.setattr(report, "_now", lambda: REPORT_NOW)
    return REPORT_NOW


@pytest.fixture
def seed_run(db, make_key):
    """seed_run(started_at, results=((name, status, duration_ms[, message]), ...), **run fields) inserts
    one run. A name listed twice is a retry: two rows with the same key, later rows win."""
    from collections import Counter

    keys = {}

    def _seed(started_at, results=(("t1", "passed", 10),), project_id=1, branch="main", environment=None,
              ci_provider="local", ci_run_url=None, duration_ms=1000, commit_sha=None):
        if project_id not in keys:
            keys[project_id] = make_key(project_id=project_id)[0]
        counts = Counter(r[1] for r in results)
        run = Run(project_id=project_id, api_key_id=keys[project_id].id, request_hash="h", ci_provider=ci_provider,
                  ci_run_url=ci_run_url, branch=branch, environment=environment, commit_sha=commit_sha,
                  started_at=started_at, finished_at=started_at + timedelta(seconds=1), duration_ms=duration_ms,
                  total=len(results), passed=counts["passed"], failed=counts["failed"],
                  skipped=counts["skipped"], errored=counts["errored"], created_at=started_at)
        db.add(run)
        db.flush()
        for r in results:
            name, status, duration = r[0], r[1], r[2]
            message = r[3] if len(r) > 3 else (None if status in ("passed", "skipped") else f"{name} {status}")
            db.add(RunResult(run_id=run.id, test_key=report_key(name), suite="s", class_name="C", name=name,
                             status=status, duration_ms=duration, message=message))
        db.commit()
        return run

    return _seed


def post_report(client, auth, **body):
    """POST the report with a 7-day UTC period (1-7 October 2026) unless the body says otherwise."""
    payload = {"from": "2026-10-01", "to": "2026-10-07", "tz": "UTC", "sections": ["summary"], **body}
    return client.post(REPORT_URL, json=payload, headers=auth())
```

- [ ] **Step 2: Write the failing tests**

`platforms/ingestion-service/tests/integration/test_report_api.py`:

```python
"""POST /analytics/report: validation, roles, isolation, envelope, timeout (spec: ingestion section)."""
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy.exc import OperationalError

from src.ingestion.service import report_service
from conftest import REPORT_URL, post_report

ALL_ROLES = ("owner", "admin", "member", "viewer", "billing_manager")
KEY = "a" * 64


@pytest.mark.parametrize("role", ALL_ROLES)
def test_every_project_role_reads_the_report(client, auth, project_role, report_now, role):
    project_role(role)
    assert post_report(client, auth).status_code == 200


def test_a_non_member_gets_404_and_no_token_401(client, auth, project_role, report_now):
    project_role(status_code=404, body={"detail": "Project not found"})
    assert post_report(client, auth).status_code == 404
    project_role(exc=httpx.ConnectError("refused"))
    assert post_report(client, auth).status_code == 503
    assert client.post(REPORT_URL, json={"from": "2026-10-01", "to": "2026-10-07", "sections": ["summary"]}).status_code == 401


@pytest.mark.parametrize("body,detail", [
    ({"from": "2026-10-07", "to": "2026-10-01"}, "from must be on or before to"),
    ({"from": "2026-06-01", "to": "2026-10-01"}, "at most 90"),
    ({"from": "2025-08-01", "to": "2025-08-05"}, "more than 400 days ago"),
    ({"to": "2026-10-20"}, "to is in the future"),
    ({"tz": "America"}, "Unknown time zone"),
])
def test_period_and_zone_rules_are_422_with_the_rule(client, auth, project_role, report_now, body, detail):
    project_role()
    response = post_report(client, auth, **body)
    assert response.status_code == 422
    assert detail in str(response.json()["detail"])


@pytest.mark.parametrize("body", [
    {"test_keys": []},
    {"test_keys": ["not-hex"]},
    {"test_keys": [KEY] * 20001},
    {"origin": "qeos"},
    {"origin": "ci", "requested_run_urls": ["https://github.com/a/b/actions/runs/1"] * 5001},
    {"origin": "ci", "requested_run_urls": ["x" * 2049]},
    {"sections": []},
    {"sections": ["summary", "summary"]},
    {"sections": ["everything"]},
    {"ci_provider": "travis"},
    {"branch": "b" * 256},
    {"environment": "e" * 101},
    {"branch": "a\u0000b"},
    {"bucket": "month"},
    {"surprise": 1},
])
def test_bad_bodies_are_422(client, auth, project_role, report_now, body):
    project_role()
    assert post_report(client, auth, **body).status_code == 422


def test_origin_without_urls_says_so(client, auth, project_role, report_now):
    project_role()
    response = post_report(client, auth, origin="ci")
    assert "requested_run_urls is required with origin" in str(response.json()["detail"])


def test_the_envelope_has_the_periods_scope_and_only_the_asked_sections(client, auth, project_role, report_now):
    project_role("viewer")
    body = post_report(client, auth, tz="Europe/Lisbon", test_keys=[KEY.upper(), KEY]).json()
    assert body["period"] == {"from": "2026-10-01", "to": "2026-10-07", "days": 7,
                              "start": "2026-09-30T23:00:00Z", "end": "2026-10-07T23:00:00Z"}
    assert body["previous_period"]["from"] == "2026-09-24" and body["previous_period"]["to"] == "2026-09-30"
    assert body["tz"] == "Europe/Lisbon" and body["bucket"] == "day"
    assert body["generated_at"] == "2026-10-08T12:00:00Z"
    assert body["scope"] == {"runs": 0, "previous_runs": 0, "test_keys": 1}  # duplicates and case removed
    assert set(body) == {"period", "previous_period", "tz", "bucket", "generated_at", "scope", "summary"}


def test_a_long_period_buckets_by_week(client, auth, project_role, report_now):
    project_role()
    assert post_report(client, auth, **{"from": "2026-08-01", "to": "2026-10-07"}).json()["bucket"] == "week"
    assert post_report(client, auth, **{"from": "2026-08-01", "to": "2026-10-07", "bucket": "day"}).json()["bucket"] == "day"


def test_another_projects_runs_never_count(client, auth, project_role, report_now, seed_run):
    project_role()
    seed_run(datetime(2026, 10, 3, 10, tzinfo=timezone.utc), project_id=2)
    seed_run(datetime(2026, 9, 26, 10, tzinfo=timezone.utc), project_id=2)
    assert post_report(client, auth).json()["scope"] == {"runs": 0, "previous_runs": 0, "test_keys": None}


def test_runs_count_by_period(client, auth, project_role, report_now, seed_run):
    project_role()
    seed_run(datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc))      # first instant of the period
    seed_run(datetime(2026, 10, 7, 23, 59, tzinfo=timezone.utc))
    seed_run(datetime(2026, 10, 8, 0, 0, tzinfo=timezone.utc))      # end is exclusive
    seed_run(datetime(2026, 9, 24, 0, 0, tzinfo=timezone.utc))      # previous period
    seed_run(datetime(2026, 9, 23, 23, 59, tzinfo=timezone.utc))    # before both
    assert post_report(client, auth).json()["scope"] == {"runs": 2, "previous_runs": 1, "test_keys": None}


class _Cancelled(Exception):
    sqlstate = "57014"  # PostgreSQL query_canceled: what statement_timeout raises


def test_a_statement_timeout_is_503_report_timeout(client, auth, project_role, report_now, monkeypatch):
    project_role()

    def slow(*args, **kwargs):
        raise OperationalError("SELECT ...", {}, _Cancelled("canceling statement due to statement timeout"))

    monkeypatch.setattr(report_service, "build_report", slow)
    response = post_report(client, auth)
    assert response.status_code == 503
    assert response.json()["detail"] == {"code": "report_timeout",
                                         "message": "This report took too long. Narrow the period or the filters."}


def test_other_database_errors_are_not_disguised_as_timeouts():
    assert not report_service.is_timeout(OperationalError("x", {}, Exception("disk full")))
    assert report_service.is_timeout(OperationalError("x", {}, _Cancelled()))


def test_the_handler_ends_its_transaction(client, auth, project_role, report_now, db):
    project_role()
    assert post_report(client, auth).status_code == 200
    assert not db.in_transaction()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/integration/test_report_api.py -q`
Expected: FAIL: `ImportError` for `report_service` (and 404s once it imports).

- [ ] **Step 4: Write the request model**

`platforms/ingestion-service/src/ingestion/schemas/report.py`:

```python
"""Request body of POST /projects/{id}/analytics/report. No class name may start with "Test"."""
from datetime import date
from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from src.ingestion.models.run import CI_PROVIDERS

NO_NUL = r"^[^\x00]*$"
SECTIONS = ("summary", "failure_causes", "regressions", "tests", "duration")
MAX_KEYS = 20_000
MAX_URLS = 5_000

Key = Annotated[str, StringConstraints(pattern=r"^[0-9a-fA-F]{64}$")]
Url = Annotated[str, StringConstraints(max_length=2048, pattern=NO_NUL)]


class ReportIn(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: date = Field(alias="from")
    to: date
    tz: str = Field("UTC", min_length=1, max_length=64)
    branch: Optional[Annotated[str, StringConstraints(max_length=255, pattern=NO_NUL)]] = None
    environment: Optional[Annotated[str, StringConstraints(max_length=100, pattern=NO_NUL)]] = None
    ci_provider: Optional[str] = None
    origin: Literal["any", "ci", "qeos"] = "any"
    requested_run_urls: Optional[List[Url]] = Field(None, max_length=MAX_URLS)
    test_keys: Optional[List[Key]] = Field(None, min_length=1, max_length=MAX_KEYS)
    sections: List[Literal["summary", "failure_causes", "regressions", "tests", "duration"]] = Field(
        min_length=1, max_length=len(SECTIONS))
    bucket: Literal["auto", "day", "week"] = "auto"

    @field_validator("ci_provider")
    @classmethod
    def known_provider(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in CI_PROVIDERS:
            raise ValueError(f"ci_provider must be one of {', '.join(CI_PROVIDERS)}")
        return value

    @field_validator("sections")
    @classmethod
    def unique_sections(cls, value: List[str]) -> List[str]:
        if len(set(value)) != len(value):
            raise ValueError("sections must be unique")
        return value

    @model_validator(mode="after")
    def urls_with_origin(self) -> "ReportIn":
        if self.origin != "any" and self.requested_run_urls is None:
            raise ValueError("requested_run_urls is required with origin")
        return self
```

- [ ] **Step 5: Write the service skeleton**

`platforms/ingestion-service/src/ingestion/service/report_service.py`:

```python
"""Queries behind POST /analytics/report (docs/superpowers/specs/2026-10-08-report-deep-analysis-design.md).

One scoped-runs query over the previous period plus the period feeds every section. Counting stays in
SQL; sequences, streaks and signatures are computed in Python over the rows (src/ingestion/analytics).
The handler never writes."""
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Optional, Sequence

from sqlalchemy import String, any_, bindparam, select, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from src.ingestion.analytics.report_period import Period, bucket_starts, iso
from src.ingestion.analytics.trends import as_utc
from src.ingestion.models import Run

STATEMENT_TIMEOUT = "20s"  # below the gateway's 30 s proxy_read_timeout
REPORT_TIMEOUT_MESSAGE = "This report took too long. Narrow the period or the filters."
QUERY_CANCELED = "57014"


@dataclass(frozen=True)
class Scope:
    project_id: int
    period: Period
    previous: Period
    branch: Optional[str]
    environment: Optional[str]
    ci_provider: Optional[str]
    origin: str                       # any | ci | qeos
    urls: tuple                       # lower-cased Play run URLs (origin != any)
    keys: Optional[tuple]             # lower-cased, de-duplicated test keys, or None

    @classmethod
    def from_request(cls, project_id: int, body, period: Period) -> "Scope":
        keys = None if body.test_keys is None else tuple(sorted({k.lower() for k in body.test_keys}))
        urls = tuple(sorted({u.lower() for u in (body.requested_run_urls or [])}))
        return cls(project_id=project_id, period=period, previous=period.previous(),
                   branch=body.branch or None, environment=body.environment or None,
                   ci_provider=body.ci_provider or None, origin=body.origin, urls=urls, keys=keys)


@dataclass(frozen=True)
class ScopedRun:
    id: int
    started_at: datetime
    branch: Optional[str]
    duration_ms: int
    total: int
    passed: int
    failed: int
    errored: int
    skipped: int
    current: bool  # in the period; False: in the previous period


def in_list(db: Session, column, values: Sequence, item_type=String):
    """`column IN values`. PostgreSQL gets one array parameter (`= ANY(:x)`), so 20,000 keys stay one
    bind; SQLite (the tests) gets an expanding IN."""
    values = list(values)
    if db.get_bind().dialect.name == "postgresql":
        return column == any_(bindparam(None, values, type_=ARRAY(item_type)))
    return column.in_(values)


def run_filters(db: Session, scope: Scope) -> list:
    """Project and window. Task 3 adds branch, environment, CI provider and origin."""
    return [Run.project_id == scope.project_id, Run.started_at >= scope.previous.start,
            Run.started_at < scope.period.end]


def scoped_runs(db: Session, scope: Scope) -> List[ScopedRun]:
    rows = db.execute(
        select(Run.id, Run.started_at, Run.branch, Run.duration_ms, Run.total, Run.passed, Run.failed,
               Run.errored, Run.skipped)
        .where(*run_filters(db, scope))
        .order_by(Run.started_at, Run.id)
    ).all()
    start = scope.period.start
    return [ScopedRun(r.id, as_utc(r.started_at), r.branch, r.duration_ms, r.total, r.passed, r.failed,
                      r.errored, r.skipped, as_utc(r.started_at) >= start) for r in rows]


def runs_with_results(db: Session, scope: Scope, runs: List[ScopedRun]) -> set:
    """Ids of the runs that count: every scoped run, or with test_keys only those with a result for them.
    Task 3 implements the key case."""
    return {r.id for r in runs}


# Section name -> builder(db, scope, runs, context) -> dict. Tasks 4, 17, 19, 24, 25 register theirs.
SECTION_BUILDERS: Dict[str, Callable] = {}


@dataclass(frozen=True)
class Context:
    """What every section shares: the bucket and its starts, and the runs that count."""
    bucket: str
    starts: list
    counted: set


def build_report(db: Session, scope: Scope, sections: List[str], bucket: str, now: datetime) -> dict:
    runs = scoped_runs(db, scope)
    counted = runs_with_results(db, scope, runs)
    context = Context(bucket=bucket, starts=bucket_starts(scope.period, bucket), counted=counted)
    out = {
        "period": scope.period.out(),
        "previous_period": scope.previous.out(),
        "tz": scope.period.zone.key,
        "bucket": bucket,
        "generated_at": iso(now),
        "scope": {
            "runs": sum(1 for r in runs if r.current and r.id in counted),
            "previous_runs": sum(1 for r in runs if not r.current and r.id in counted),
            "test_keys": None if scope.keys is None else len(scope.keys),
        },
    }
    for name in sections:
        builder = SECTION_BUILDERS.get(name)
        out[name] = builder(db, scope, runs, context) if builder else None
    return out


def limit_statement_time(db: Session) -> None:
    """Every report query in this transaction is cancelled after 20 s (PostgreSQL only)."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'"))


def is_timeout(exc: OperationalError) -> bool:
    orig = getattr(exc, "orig", None)
    return (getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)) == QUERY_CANCELED
```

Note: sections without a builder yet return `null`; the endpoint test above only asks for `summary`, which Task 4 registers. Until then `summary` is `null` in the response and the envelope test still passes (it checks the keys, not the value).

- [ ] **Step 6: Write the endpoint and mount it**

`platforms/ingestion-service/src/ingestion/api/v1/endpoints/report.py`:

```python
"""POST /projects/{id}/analytics/report: every report section, scoped by the dashboard's filters."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from src.ingestion.analytics.report_period import PeriodError, check_period, choose_bucket
from src.ingestion.api.deps import READ_ROLES, ProjectAccess, get_db, require_project_role
from src.ingestion.api.v1.endpoints.analytics import _zone
from src.ingestion.schemas.report import ReportIn
from src.ingestion.service import report_service

router = APIRouter()  # mounted at /projects/{project_id}/analytics


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/report")
def report(
    body: ReportIn,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    zone = _zone(body.tz)
    now = _now()
    try:
        period = check_period(body.from_, body.to, zone, now)
    except PeriodError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    scope = report_service.Scope.from_request(access.project_id, body, period)
    try:
        report_service.limit_statement_time(db)
        return report_service.build_report(db, scope, body.sections, choose_bucket(body.bucket, period.days), now)
    except OperationalError as exc:
        if report_service.is_timeout(exc):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail={"code": "report_timeout", "message": report_service.REPORT_TIMEOUT_MESSAGE})
        raise
    finally:
        db.rollback()  # read-only: end the transaction (and its SET LOCAL) before the response is sent
```

In `platforms/ingestion-service/src/ingestion/api/v1/api.py` change the import line to include `report` and add, right after the analytics router line:

```python
from src.ingestion.api.v1.endpoints import analytics, api_keys, collect, export, masking_patterns, notifications, report, runs
...
api_router.include_router(analytics.router, prefix="/projects/{project_id}/analytics", tags=["analytics"])
api_router.include_router(report.router, prefix="/projects/{project_id}/analytics", tags=["analytics"])
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/integration/test_report_api.py -q`
Expected: PASS. If `test_the_handler_ends_its_transaction` fails because the TestClient's shared session autobegins on a later access, assert inside the endpoint path instead by checking `db.in_transaction()` right after the request returns (as written): the `finally: db.rollback()` must have run.

- [ ] **Step 8: Run the whole ingestion suite**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest -q`
Expected: PASS (no other test changes behaviour).

- [ ] **Step 9: Commit**

```bash
git add platforms/ingestion-service/src/ingestion/schemas/report.py platforms/ingestion-service/src/ingestion/service/report_service.py platforms/ingestion-service/src/ingestion/api/v1/endpoints/report.py platforms/ingestion-service/src/ingestion/api/v1/api.py platforms/ingestion-service/tests/conftest.py platforms/ingestion-service/tests/integration/test_report_api.py
git commit -m "feat(ingestion): POST analytics/report with validation, envelope and a 20 s statement timeout" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- platforms/ingestion-service/src/ingestion/schemas/report.py platforms/ingestion-service/src/ingestion/service/report_service.py platforms/ingestion-service/src/ingestion/api/v1/endpoints/report.py platforms/ingestion-service/src/ingestion/api/v1/api.py platforms/ingestion-service/tests/conftest.py platforms/ingestion-service/tests/integration/test_report_api.py
```

---

### Task 3: Scoped runs: branch, environment, CI provider, origin, test keys

**Files:**
- Modify: `platforms/ingestion-service/src/ingestion/service/report_service.py` (`run_filters`, `runs_with_results`)
- Test: `platforms/ingestion-service/tests/integration/test_report_api.py` (append)

**Interfaces:**
- Consumes: Task 2 (`Scope`, `in_list`, `ScopedRun`, `build_report`, conftest `seed_run`, `post_report`, `report_key`).
- Produces: `run_filters(db, scope) -> list` now applies every run filter; `runs_with_results(db, scope, runs) -> set[int]` honours `scope.keys`; `key_filter(db, scope) -> list` (`[]` or `[in_list(db, RunResult.test_key, scope.keys)]`) for every later results query.

- [ ] **Step 1: Write the failing tests** (append to `test_report_api.py`)

```python
from conftest import report_key

GH = "https://github.com/acme/obt/actions/runs/"


def runs_of(client, auth, **body):
    response = post_report(client, auth, **body)
    assert response.status_code == 200, response.text
    return response.json()["scope"]["runs"]


def test_each_run_filter_alone_and_combined(client, auth, project_role, report_now, seed_run):
    project_role()
    day = datetime(2026, 10, 3, 10, tzinfo=timezone.utc)
    seed_run(day, branch="main", environment="staging", ci_provider="github_actions")
    seed_run(day, branch="main", environment="prod", ci_provider="jenkins")
    seed_run(day, branch="dev", environment="staging", ci_provider="jenkins")
    assert runs_of(client, auth) == 3
    assert runs_of(client, auth, branch="main") == 2
    assert runs_of(client, auth, branch="") == 3                  # empty means no filter
    assert runs_of(client, auth, environment="staging") == 2
    assert runs_of(client, auth, ci_provider="jenkins") == 2
    assert runs_of(client, auth, branch="main", environment="staging", ci_provider="jenkins") == 0


def test_origin_matches_the_play_url_without_regard_to_case_on_github_only(client, auth, project_role, report_now, seed_run):
    project_role()
    day = datetime(2026, 10, 3, 10, tzinfo=timezone.utc)
    seed_run(day, ci_provider="github_actions", ci_run_url=GH + "7")                   # requested from QEOS
    seed_run(day, ci_provider="github_actions", ci_run_url=GH + "7")                   # a shard of the same Play
    seed_run(day, ci_provider="github_actions", ci_run_url=GH + "8")                   # CI
    seed_run(day, ci_provider="local", ci_run_url=GH + "7")                            # not GitHub: CI
    seed_run(day, ci_provider="github_actions", ci_run_url=None)                       # CI
    seed_run(day, ci_provider="github_actions", ci_run_url=GH + "7/")                  # trailing slash: another URL
    urls = [(GH + "7").upper()]
    assert runs_of(client, auth, origin="qeos", requested_run_urls=urls) == 2
    assert runs_of(client, auth, origin="ci", requested_run_urls=urls) == 4
    assert runs_of(client, auth, origin="any", requested_run_urls=urls) == 6        # ignored with any
    assert runs_of(client, auth, origin="qeos", requested_run_urls=[]) == 0
    assert runs_of(client, auth, origin="ci", requested_run_urls=[]) == 6


def test_test_keys_count_only_runs_with_a_result_for_them(client, auth, project_role, report_now, seed_run):
    project_role()
    day = datetime(2026, 10, 3, 10, tzinfo=timezone.utc)
    seed_run(day, results=(("t1", "passed", 1), ("t2", "failed", 1)))
    seed_run(day, results=(("t1", "passed", 1),))
    seed_run(datetime(2026, 9, 26, tzinfo=timezone.utc), results=(("t2", "passed", 1),))
    scope = post_report(client, auth, test_keys=[report_key("t2").upper()]).json()["scope"]
    assert scope == {"runs": 1, "previous_runs": 1, "test_keys": 1}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/integration/test_report_api.py -q`
Expected: FAIL in the three new tests (filters ignored: counts too high).

- [ ] **Step 3: Implement the filters**

In `report_service.py`, add `RunResult` to the models import and `and_, func, not_` to the sqlalchemy import, then replace `run_filters` and `runs_with_results`:

```python
def run_filters(db: Session, scope: Scope) -> list:
    """Project and window, then branch, environment, CI provider and origin. These are checked on the
    window's few thousand runs, so they need no index."""
    filters = [Run.project_id == scope.project_id, Run.started_at >= scope.previous.start,
               Run.started_at < scope.period.end]
    if scope.branch:
        filters.append(Run.branch == scope.branch)
    if scope.environment:
        filters.append(Run.environment == scope.environment)
    if scope.ci_provider:
        filters.append(Run.ci_provider == scope.ci_provider)
    if scope.origin != "any":
        # Requested from QEOS: a GitHub Actions run whose URL is a Play's github_run_url (ADR-026).
        # Every other run is CI, runs without a URL included. A NULL URL makes the AND false, never NULL.
        requested = and_(Run.ci_provider == "github_actions", Run.ci_run_url.is_not(None),
                         in_list(db, func.lower(Run.ci_run_url), scope.urls))
        filters.append(requested if scope.origin == "qeos" else not_(requested))
    return filters


def key_filter(db: Session, scope: Scope) -> list:
    """The test_keys restriction for any query over test_results ([] without keys)."""
    return [] if scope.keys is None else [in_list(db, RunResult.test_key, scope.keys)]


def run_ids(db: Session, runs) -> list:
    return [r.id for r in runs]


def runs_with_results(db: Session, scope: Scope, runs: List[ScopedRun]) -> set:
    """Ids of the runs that count: every scoped run, or with test_keys the runs that have at least one
    result for those keys."""
    if scope.keys is None or not runs:
        return {r.id for r in runs}
    rows = db.execute(
        select(RunResult.run_id).distinct()
        .where(in_list(db, RunResult.run_id, run_ids(db, runs), Integer), *key_filter(db, scope))
    ).all()
    return {run_id for (run_id,) in rows}
```

Also add `Integer` to the sqlalchemy import.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/integration/test_report_api.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add platforms/ingestion-service/src/ingestion/service/report_service.py platforms/ingestion-service/tests/integration/test_report_api.py
git commit -m "feat(ingestion): report scope filters, origin by Play URL, and test keys" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- platforms/ingestion-service/src/ingestion/service/report_service.py platforms/ingestion-service/tests/integration/test_report_api.py
```

---

### Task 4: Section `summary`

**Files:**
- Modify: `platforms/ingestion-service/src/ingestion/service/report_service.py`
- Test: `platforms/ingestion-service/tests/integration/test_report_summary.py`

**Interfaces:**
- Consumes: Tasks 1–3 (`Scope`, `ScopedRun`, `Context`, `in_list`, `key_filter`, `run_ids`, `SECTION_BUILDERS`, `bucket_index`, `local_day`); `pass_rate` from `analytics/trends.py`.
- Produces:
  - `@dataclass Counts(executions=0, passed=0, failed=0, errored=0, skipped=0, duration_ms=0)` with `add(other)`.
  - `run_counts(db, scope, runs) -> dict[int, Counts]` (per run: from `test_runs` columns without keys; from results with keys; `duration_ms` is the sum of result durations with keys, else 0).
  - `summary(db, scope, runs, context) -> dict` registered as `SECTION_BUILDERS["summary"]`.
  - The `summary` JSON per the spec plus `previous_buckets` (Ruling 2).

- [ ] **Step 1: Write the failing tests**

`platforms/ingestion-service/tests/integration/test_report_summary.py`:

```python
"""Section summary (spec: Section summary (P1); Ruling 2: previous_buckets)."""
from datetime import datetime, timezone

import pytest

from conftest import post_report, report_key


def at(day, hour=10):
    return datetime(2026, 10, day, hour, tzinfo=timezone.utc)


@pytest.fixture
def seeded(project_role, report_now, seed_run):
    project_role()
    seed_run(at(2), results=(("t1", "passed", 100), ("t2", "failed", 300), ("t3", "skipped", 0)), duration_ms=1000)
    seed_run(at(5), results=(("t1", "passed", 120), ("t2", "passed", 280)), duration_ms=3000)
    seed_run(at(6), branch="dev", environment="staging", results=(("t1", "errored", 50),), duration_ms=2000)
    seed_run(datetime(2026, 9, 25, 10, tzinfo=timezone.utc), results=(("t1", "passed", 1), ("t2", "passed", 1)),
             duration_ms=2000)
    seed_run(at(3), project_id=2, results=(("t9", "failed", 1),))


def summary(client, auth, **body):
    response = post_report(client, auth, **body)
    assert response.status_code == 200, response.text
    return response.json()["summary"]


def test_current_and_previous_totals(client, auth, seeded):
    s = summary(client, auth)
    assert s["current"] == {"runs": 3, "executions": 6, "passed": 3, "failed": 1, "errored": 1, "skipped": 1,
                            "pass_rate": 0.6, "tests": 3, "failing_tests": 2, "avg_run_duration_ms": 2000}
    assert s["previous"] == {"runs": 1, "executions": 2, "passed": 2, "failed": 0, "errored": 0, "skipped": 0,
                             "pass_rate": 1.0, "tests": 2, "failing_tests": 0, "avg_run_duration_ms": 2000}


def test_previous_is_null_when_the_previous_period_has_no_runs(client, auth, seeded):
    assert summary(client, auth, branch="dev")["previous"] is None


def test_buckets_cover_every_day_with_zeros(client, auth, seeded):
    buckets = summary(client, auth)["buckets"]
    assert [b["date"] for b in buckets] == [f"2026-10-0{d}" for d in range(1, 8)]
    assert buckets[0] == {"date": "2026-10-01", "runs": 0, "executions": 0, "passed": 0, "failed": 0,
                          "errored": 0, "skipped": 0, "pass_rate": None}
    assert (buckets[1]["runs"], buckets[1]["executions"], buckets[1]["pass_rate"]) == (1, 3, 0.5)
    assert (buckets[5]["errored"], buckets[5]["pass_rate"]) == (1, 0.0)


def test_previous_buckets_align_bucket_by_bucket(client, auth, seeded):
    prev = summary(client, auth)["previous_buckets"]
    assert len(prev) == 7
    assert prev[1]["date"] == "2026-09-25" and prev[1]["runs"] == 1 and prev[1]["pass_rate"] == 1.0
    assert sum(b["runs"] for b in prev) == 1


def test_top_failing_lists_only_tests_that_failed_and_slowest_by_average(client, auth, seeded):
    s = summary(client, auth)
    failing = {r["name"]: r for r in s["top_failing"]}
    assert set(failing) == {"t1", "t2"}
    assert failing["t2"] == {"test_key": report_key("t2"), "suite": "s", "class_name": "C", "name": "t2",
                             "executions": 2, "failures": 1, "pass_rate": 0.5}
    assert [r["name"] for r in s["slowest"]][:2] == ["t2", "t1"]
    assert s["slowest"][0]["avg_duration_ms"] == 290


def test_branches_by_runs_and_facets_ignore_other_filters(client, auth, seeded):
    s = summary(client, auth, branch="main")
    assert [(b["branch"], b["runs"]) for b in s["branches"]] == [("main", 2)]
    assert s["facets"] == {"branches": ["main", "dev"], "environments": ["staging"], "ci_providers": ["local"]}
    assert s["current"]["runs"] == 2


def test_test_keys_narrow_every_figure(client, auth, seeded):
    s = summary(client, auth, test_keys=[report_key("t2")])
    assert (s["current"]["runs"], s["current"]["executions"], s["current"]["failing_tests"]) == (2, 2, 1)
    assert [r["name"] for r in s["top_failing"]] == ["t2"]


def test_a_retry_counts_every_row(client, auth, project_role, report_now, seed_run):
    project_role()
    seed_run(at(2), results=(("t1", "failed", 10), ("t1", "passed", 10)))
    s = summary(client, auth)
    assert (s["current"]["executions"], s["current"]["failed"], s["current"]["passed"]) == (2, 1, 1)
    assert s["current"]["failing_tests"] == 1


def test_an_empty_period(client, auth, project_role, report_now):
    project_role()
    s = summary(client, auth)
    assert s["current"]["runs"] == 0 and s["current"]["pass_rate"] is None
    assert s["current"]["avg_run_duration_ms"] is None and s["previous"] is None
    assert s["top_failing"] == [] and s["branches"] == [] and len(s["buckets"]) == 7
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/integration/test_report_summary.py -q`
Expected: FAIL: `TypeError: 'NoneType' object is not subscriptable` (no `summary` builder yet).

- [ ] **Step 3: Implement the section**

Append to `report_service.py`, extending its imports: `case, distinct` from `sqlalchemy`; `timedelta` from `datetime`; `bucket_index, local_day` from `src.ingestion.analytics.report_period`; `pass_rate` from `src.ingestion.analytics.trends`:

```python
FAILING = ("failed", "errored")
TOP = 10
MAX_FACETS = 50


@dataclass
class Counts:
    executions: int = 0
    passed: int = 0
    failed: int = 0
    errored: int = 0
    skipped: int = 0
    duration_ms: int = 0  # sum of result durations; only filled when test_keys are set

    def add(self, other: "Counts") -> None:
        self.executions += other.executions
        self.passed += other.passed
        self.failed += other.failed
        self.errored += other.errored
        self.skipped += other.skipped
        self.duration_ms += other.duration_ms

    def out(self) -> dict:
        return {"executions": self.executions, "passed": self.passed, "failed": self.failed,
                "errored": self.errored, "skipped": self.skipped,
                "pass_rate": pass_rate(self.passed, self.executions, self.skipped)}


def _count(*statuses: str):
    return func.sum(case((RunResult.status.in_(statuses), 1), else_=0))


def run_counts(db: Session, scope: Scope, runs: List[ScopedRun]) -> Dict[int, Counts]:
    """Per counted run. Without test_keys the run's own counters (computed from its results at upload);
    with test_keys the results for those keys, which also gives the summed test time."""
    if scope.keys is None:
        return {r.id: Counts(r.total, r.passed, r.failed, r.errored, r.skipped) for r in runs}
    if not runs:
        return {}
    rows = db.execute(
        select(RunResult.run_id, func.count(RunResult.id), _count("passed"), _count("failed"), _count("errored"),
               _count("skipped"), func.sum(RunResult.duration_ms))
        .where(in_list(db, RunResult.run_id, run_ids(db, runs), Integer), *key_filter(db, scope))
        .group_by(RunResult.run_id)
    ).all()
    return {run_id: Counts(n, int(p or 0), int(f or 0), int(e or 0), int(s or 0), int(d or 0))
            for run_id, n, p, f, e, s, d in rows}


def _test_figures(db: Session, scope: Scope, ids: list) -> tuple:
    """(distinct tests executed, distinct tests with a failing execution) over the given runs."""
    if not ids:
        return 0, 0
    tests, failing = db.execute(
        select(func.count(distinct(RunResult.test_key)),
               func.count(distinct(case((RunResult.status.in_(FAILING), RunResult.test_key)))))
        .where(in_list(db, RunResult.run_id, ids, Integer), *key_filter(db, scope))
    ).one()
    return int(tests or 0), int(failing or 0)


def _totals(db: Session, scope: Scope, runs: List[ScopedRun], counts: Dict[int, Counts]) -> dict:
    total = Counts()
    for r in runs:
        total.add(counts[r.id])
    tests, failing = _test_figures(db, scope, [r.id for r in runs])
    durations = [r.duration_ms for r in runs]
    return {"runs": len(runs), **total.out(), "tests": tests, "failing_tests": failing,
            "avg_run_duration_ms": round(sum(durations) / len(durations)) if durations else None}


def _bucket_rows(scope: Scope, context: Context, runs, counts, shift_days: int) -> List[dict]:
    """One entry per bucket of the period. shift_days moves a previous-period run onto the bucket that
    lies `days` later, so the previous period lines up bucket by bucket (Ruling 2)."""
    per = [Counts() for _ in context.starts]
    per_runs = [0] * len(context.starts)
    zone = scope.period.zone
    for r in runs:
        index = bucket_index(local_day(r.started_at, zone) + timedelta(days=shift_days), context.starts, context.bucket)
        if index is None:
            continue
        per[index].add(counts[r.id])
        per_runs[index] += 1
    return [{"date": (start - timedelta(days=shift_days)).isoformat(), "runs": per_runs[i], **per[i].out()}
            for i, start in enumerate(context.starts)]


def _test_rows(db: Session, scope: Scope, ids: list, *, slowest: bool) -> List[dict]:
    """The 10 most failing (only tests with a failure) or slowest tests, ordered as /tests orders them."""
    if not ids:
        return []
    failures = _count(*FAILING)
    average = func.avg(RunResult.duration_ms)
    query = (
        select(RunResult.test_key, func.max(RunResult.suite), func.max(RunResult.class_name),
               func.max(RunResult.name), func.count(RunResult.id), failures, _count("passed"), _count("skipped"),
               average)
        .where(in_list(db, RunResult.run_id, ids, Integer), *key_filter(db, scope))
        .group_by(RunResult.test_key)
    )
    query = query.order_by(average.desc(), RunResult.test_key) if slowest else \
        query.having(failures > 0).order_by(failures.desc(), RunResult.test_key)
    out = []
    for key, suite, class_name, name, n, failed, passed, skipped, avg in db.execute(query.limit(TOP)).all():
        row = {"test_key": key, "suite": suite, "class_name": class_name, "name": name, "executions": n}
        if slowest:
            row["avg_duration_ms"] = round(float(avg)) if avg is not None else None
        else:
            row["failures"] = int(failed)
            row["pass_rate"] = pass_rate(int(passed), n, int(skipped))
        out.append(row)
    return out


def _branches(runs: List[ScopedRun], counts: Dict[int, Counts]) -> List[dict]:
    grouped: Dict[Optional[str], list] = {}
    for r in runs:
        grouped.setdefault(r.branch, []).append(r)
    rows = []
    for branch, members in grouped.items():
        total = Counts()
        for r in members:
            total.add(counts[r.id])
        rows.append({"branch": branch, "runs": len(members), "executions": total.executions,
                     "failures": total.failed + total.errored,
                     "pass_rate": pass_rate(total.passed, total.executions, total.skipped)})
    rows.sort(key=lambda b: (-b["runs"], b["branch"] is None, b["branch"] or ""))
    return rows[:TOP]


def _facets(db: Session, scope: Scope) -> dict:
    """The period's busiest values, ignoring every other filter, so they offer a way out of an empty result."""
    out = {}
    for name, column in (("branches", Run.branch), ("environments", Run.environment), ("ci_providers", Run.ci_provider)):
        rows = db.execute(
            select(column, func.count(Run.id))
            .where(Run.project_id == scope.project_id, Run.started_at >= scope.period.start,
                   Run.started_at < scope.period.end, column.is_not(None))
            .group_by(column).order_by(func.count(Run.id).desc(), column).limit(MAX_FACETS)
        ).all()
        out[name] = [value for value, _ in rows]
    return out


def summary(db: Session, scope: Scope, runs: List[ScopedRun], context: Context) -> dict:
    counted = [r for r in runs if r.id in context.counted]
    counts = run_counts(db, scope, counted)
    current = [r for r in counted if r.current]
    previous = [r for r in counted if not r.current]
    current_ids = [r.id for r in current]
    return {
        "current": _totals(db, scope, current, counts),
        "previous": _totals(db, scope, previous, counts) if previous else None,
        "buckets": _bucket_rows(scope, context, current, counts, 0),
        "previous_buckets": _bucket_rows(scope, context, previous, counts, scope.period.days),
        "top_failing": _test_rows(db, scope, current_ids, slowest=False),
        "slowest": _test_rows(db, scope, current_ids, slowest=True),
        "branches": _branches(current, counts),
        "facets": _facets(db, scope),
    }


SECTION_BUILDERS["summary"] = summary
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/integration/test_report_summary.py tests/integration/test_report_api.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add platforms/ingestion-service/src/ingestion/service/report_service.py platforms/ingestion-service/tests/integration/test_report_summary.py
git commit -m "feat(ingestion): report summary section with previous-period deltas and facets" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- platforms/ingestion-service/src/ingestion/service/report_service.py platforms/ingestion-service/tests/integration/test_report_summary.py
```

---

### Task 5: test-management `GET /case-areas`

**Files:**
- Create: `platforms/test-management-service/src/casebook/service/case_area_service.py`
- Create: `platforms/test-management-service/src/casebook/api/v1/endpoints/case_areas.py`
- Modify: `platforms/test-management-service/src/casebook/api/v1/api.py`
- Test: `platforms/test-management-service/tests/integration/test_case_areas.py`

**Interfaces:**
- Consumes: models `Case`, `CaseLabel`, `Suite`, `SuiteCase`; deps `READ_ROLES`, `require_project_role`, `get_db`.
- Produces: `case_area_service.MAX_CASES = 50_000`, `class TooManyCases(Exception)`, `case_areas(db, project_id, now) -> dict`; route `GET /api/v1/projects/{id}/case-areas` returning the spec's JSON (`generated_at`, `counts`, `folders`, `features`, `labels`, `suites`, `cases[{n,t,k,fo,fe,l,s}]`); 409 `{"detail": {"code": "too_many_cases", "message": "This project has more cases than the report can join (50,000)"}}`.

- [ ] **Step 1: Write the failing tests**

```python
"""GET /case-areas: every active case, dictionary-encoded, for the report's joins (spec: test-management)."""
import time

import httpx
import pytest
from sqlalchemy import insert

from src.casebook.models import Case, CaseLabel, Suite, SuiteCase
from src.casebook.service import case_area_service

P = "/api/v1/projects/1"
KEY = "ab" * 32


def add_case(db, number, *, title=None, source_path=None, feature=None, key=None, status="ready", labels=(),
             project_id=1):
    row = Case(project_id=project_id, number=number, title=title or f"case {number}", steps=[], status=status,
               source_path=source_path, feature_name=feature, automated_test_key=key, created_by=1,
               labels=[CaseLabel(label=label) for label in labels])
    db.add(row)
    db.flush()
    return row


def add_suite(db, name, cases, project_id=1):
    suite = Suite(project_id=project_id, name=name, created_by=1)
    db.add(suite)
    db.flush()
    for position, case in enumerate(cases):
        db.add(SuiteCase(suite_id=suite.id, case_id=case.id, position=position))
    return suite


@pytest.fixture
def seeded(db, project_role):
    project_role("viewer")
    a = add_case(db, 1, title="Book one-way", source_path="features/booking/air/a.feature", feature="Air booking",
                 key=KEY.upper(), labels=("smoke", "ado-12"))
    b = add_case(db, 2, source_path="features/booking/b.feature", feature="Booking", key="cd" * 32, labels=("smoke",))
    add_case(db, 3, source_path="root.feature", feature="Root", key="ef" * 32)
    m = add_case(db, 4, title="manual check")
    add_case(db, 5, source_path="features/old/x.feature", feature="Old", status="archived", labels=("legacy",))
    add_case(db, 6, status="draft", title="draft manual")
    add_case(db, 7, project_id=2, source_path="other/z.feature", feature="Other")
    add_suite(db, "Regression", [a, b])
    add_suite(db, "Nightly", [a, m])
    add_suite(db, "Empty", [])
    db.commit()


def areas(client, auth):
    response = client.get(f"{P}/case-areas", headers=auth())
    assert response.status_code == 200, response.text
    return response.json()


def test_active_cases_with_sorted_dictionaries(client, auth, seeded):
    body = areas(client, auth)
    assert body["counts"] == {"cases": 5, "linked": 3, "manual": 2}            # archived 5 left out, draft 6 kept
    assert body["folders"] == ["features/booking", "features/booking/air"]     # root.feature has no folder
    assert body["features"] == ["Air booking", "Booking", "Root"]
    assert body["labels"] == ["ado-12", "smoke"]                               # "legacy" only on an archived case
    assert body["suites"] == [{"id": 3, "name": "Empty"}, {"id": 2, "name": "Nightly"}, {"id": 1, "name": "Regression"}]
    assert [c["n"] for c in body["cases"]] == [1, 2, 3, 4, 6]
    assert body["generated_at"].endswith("Z")


def test_each_case_points_into_the_dictionaries(client, auth, seeded):
    body = areas(client, auth)
    cases = {c["n"]: c for c in body["cases"]}
    one = cases[1]
    assert one["t"] == "Book one-way" and one["k"] == KEY                      # lower-cased
    assert body["folders"][one["fo"]] == "features/booking/air"
    assert body["features"][one["fe"]] == "Air booking"
    assert [body["labels"][i] for i in one["l"]] == ["ado-12", "smoke"]
    assert sorted(body["suites"][i]["name"] for i in one["s"]) == ["Nightly", "Regression"]
    assert cases[3]["fo"] is None and body["features"][cases[3]["fe"]] == "Root"
    assert (cases[4]["k"], cases[4]["fo"], cases[4]["fe"], cases[4]["l"]) == (None, None, None, [])
    assert [body["suites"][i]["name"] for i in cases[4]["s"]] == ["Nightly"]


def test_every_role_reads_and_other_projects_are_invisible(client, auth, seeded, project_role):
    for role in ("owner", "admin", "member", "viewer", "billing_manager"):
        project_role(role)
        assert client.get(f"{P}/case-areas", headers=auth()).status_code == 200
    project_role(status_code=404, body={"detail": "Project not found"})
    assert client.get(f"{P}/case-areas", headers=auth()).status_code == 404
    assert client.get(f"{P}/case-areas").status_code == 401


def test_too_many_cases_is_409(client, auth, seeded, monkeypatch):
    monkeypatch.setattr(case_area_service, "MAX_CASES", 4)
    response = client.get(f"{P}/case-areas", headers=auth())
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "too_many_cases"


def test_twenty_thousand_cases_answer_quickly(client, auth, db, project_role):
    project_role()
    db.execute(insert(Case), [
        {"project_id": 1, "number": n, "title": f"Scenario {n}", "steps": [], "status": "ready", "created_by": 1,
         "source_path": f"features/area{n % 40}/f{n % 400}.feature", "feature_name": f"Feature {n % 400}",
         "automated_test_key": f"{n:064x}"}
        for n in range(1, 20_001)
    ])
    db.commit()
    started = time.perf_counter()
    body = areas(client, auth)
    elapsed = time.perf_counter() - started
    assert body["counts"]["cases"] == 20_000
    assert elapsed < 5.0  # SQLite on a CI runner; the PostgreSQL target (300 ms) is checked by hand
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd platforms/test-management-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/integration/test_case_areas.py -q`
Expected: FAIL with 404 (route missing) or ImportError for `case_area_service`.

- [ ] **Step 3: Write the service**

`platforms/test-management-service/src/casebook/service/case_area_service.py`:

```python
"""Every active case of a project in one compact response, for the report's joins in the dashboard
(docs/superpowers/specs/2026-10-08-report-deep-analysis-design.md, ADR-026). Three queries, no paging."""
from datetime import datetime
from typing import Dict, List

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.casebook.models import Case, CaseLabel, Suite, SuiteCase

MAX_CASES = 50_000


class TooManyCases(Exception):
    pass


def folder_of(source_path):
    """The directory part of source_path (the rule of folder_counts); None at the root or for a manual case."""
    if not source_path or "/" not in source_path:
        return None
    return source_path.rsplit("/", 1)[0]


def _index(values) -> Dict[str, int]:
    return {value: i for i, value in enumerate(sorted(values))}


def case_areas(db: Session, project_id: int, now: datetime) -> dict:
    active = (Case.project_id == project_id, Case.status != "archived")
    count = db.execute(select(func.count(Case.id)).where(*active)).scalar_one()
    if count > MAX_CASES:
        raise TooManyCases()
    cases = db.execute(
        select(Case.id, Case.number, Case.title, Case.automated_test_key, Case.source_path, Case.feature_name)
        .where(*active).order_by(Case.number)
    ).all()
    label_rows = db.execute(
        select(CaseLabel.case_id, CaseLabel.label).join(Case, Case.id == CaseLabel.case_id).where(*active)
    ).all()
    suites = db.execute(select(Suite.id, Suite.name).where(Suite.project_id == project_id).order_by(Suite.name)).all()
    member_rows = db.execute(
        select(SuiteCase.case_id, SuiteCase.suite_id).join(Suite, Suite.id == SuiteCase.suite_id)
        .where(Suite.project_id == project_id)
    ).all()

    folders = _index({f for f in (folder_of(c.source_path) for c in cases) if f})
    features = _index({c.feature_name for c in cases if c.feature_name})
    labels = _index({label for _, label in label_rows})
    suite_index = {suite_id: i for i, (suite_id, _) in enumerate(suites)}
    labels_of: Dict[int, List[int]] = {}
    for case_id, label in label_rows:
        labels_of.setdefault(case_id, []).append(labels[label])
    suites_of: Dict[int, List[int]] = {}
    for case_id, suite_id in member_rows:
        suites_of.setdefault(case_id, []).append(suite_index[suite_id])

    linked = sum(1 for c in cases if c.automated_test_key)
    return {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "counts": {"cases": len(cases), "linked": linked, "manual": len(cases) - linked},
        "folders": sorted(folders, key=folders.get),
        "features": sorted(features, key=features.get),
        "labels": sorted(labels, key=labels.get),
        "suites": [{"id": suite_id, "name": name} for suite_id, name in suites],
        "cases": [
            {"n": c.number, "t": c.title, "k": c.automated_test_key.lower() if c.automated_test_key else None,
             "fo": folders.get(folder_of(c.source_path)) if folder_of(c.source_path) else None,
             "fe": features[c.feature_name] if c.feature_name else None,
             "l": sorted(labels_of.get(c.id, [])), "s": sorted(suites_of.get(c.id, []))}
            for c in cases
        ],
    }
```

Note: the `suites` dictionary is sorted by name, and the test above expects that order ("Empty", "Nightly", "Regression").

- [ ] **Step 4: Write the endpoint and mount it**

`platforms/test-management-service/src/casebook/api/v1/endpoints/case_areas.py`:

```python
"""GET /projects/{id}/case-areas: every active case, dictionary-encoded, for the report."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.casebook.api.deps import READ_ROLES, ProjectAccess, get_db, require_project_role
from src.casebook.service import case_area_service

router = APIRouter()  # mounted at /projects/{project_id}/case-areas


@router.get("")
def case_areas(db: Session = Depends(get_db), access: ProjectAccess = Depends(require_project_role(*READ_ROLES))):
    try:
        return case_area_service.case_areas(db, access.project_id, datetime.now(timezone.utc))
    except case_area_service.TooManyCases:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={
            "code": "too_many_cases",
            "message": f"This project has more cases than the report can join ({case_area_service.MAX_CASES:,})"})
```

In `api/v1/api.py`: add `case_areas` to the endpoints import and
`api_router.include_router(case_areas.router, prefix="/projects/{project_id}/case-areas", tags=["cases"])`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd platforms/test-management-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/integration/test_case_areas.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add platforms/test-management-service/src/casebook/service/case_area_service.py platforms/test-management-service/src/casebook/api/v1/endpoints/case_areas.py platforms/test-management-service/src/casebook/api/v1/api.py platforms/test-management-service/tests/integration/test_case_areas.py
git commit -m "feat(test-management): GET case-areas, every active case dictionary-encoded for the report" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- platforms/test-management-service/src/casebook/service/case_area_service.py platforms/test-management-service/src/casebook/api/v1/endpoints/case_areas.py platforms/test-management-service/src/casebook/api/v1/api.py platforms/test-management-service/tests/integration/test_case_areas.py
```

---

### Task 6: test-management `GET /run-requests/run-urls`

**Files:**
- Modify: `platforms/test-management-service/src/casebook/service/run_request_service.py` (append)
- Modify: `platforms/test-management-service/src/casebook/api/v1/endpoints/run_requests.py` (new route **above** `get_run_request`)
- Test: `platforms/test-management-service/tests/integration/test_run_urls.py`

**Interfaces:**
- Consumes: `RunRequest` model (`requested_at`, `github_run_url`, `project_id`).
- Produces: `run_request_service.MAX_RUN_URLS = 5000`, `RUN_URLS_MAX_AGE_DAYS = 500` (Ruling 5), `run_urls(db, project_id, since) -> tuple[list[str], bool]`; route `GET /run-requests/run-urls?since=<ISO datetime>` → `{"urls": [...], "truncated": bool}`.

- [ ] **Step 1: Write the failing tests**

```python
"""GET /run-requests/run-urls: the GitHub run URLs of Play requests, for the report's origin filter."""
from datetime import datetime, timedelta, timezone

import pytest

from src.casebook.models import RunRequest
from src.casebook.service import run_request_service

P = "/api/v1/projects/1/run-requests"
NOW = datetime.now(timezone.utc)


def add(db, days_ago, url, project_id=1, status="completed"):
    db.add(RunRequest(project_id=project_id, requested_by=1, requested_at=NOW - timedelta(days=days_ago),
                      selection=[], status=status, github_run_url=url))


@pytest.fixture
def seeded(db, project_role):
    project_role("viewer")
    add(db, 1, "https://github.com/acme/obt/actions/runs/3")
    add(db, 5, "https://github.com/acme/obt/actions/runs/2")
    add(db, 6, None, status="failed_to_start")
    add(db, 40, "https://github.com/acme/obt/actions/runs/1")
    add(db, 2, "https://github.com/other/repo/actions/runs/9", project_id=2)
    db.commit()


def since(days):
    return (NOW - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_urls_since_newest_first_without_nulls(client, auth, seeded):
    body = client.get(f"{P}/run-urls", params={"since": since(10)}, headers=auth()).json()
    assert body == {"urls": ["https://github.com/acme/obt/actions/runs/3", "https://github.com/acme/obt/actions/runs/2"],
                    "truncated": False}


def test_the_route_is_not_taken_for_a_request_id(client, auth, seeded):
    assert client.get(f"{P}/run-urls", params={"since": since(60)}, headers=auth()).status_code == 200


def test_since_is_required_and_at_most_500_days_back(client, auth, seeded):
    assert client.get(f"{P}/run-urls", headers=auth()).status_code == 422
    assert client.get(f"{P}/run-urls", params={"since": since(501)}, headers=auth()).status_code == 422
    assert client.get(f"{P}/run-urls", params={"since": since(499)}, headers=auth()).status_code == 200
    assert client.get(f"{P}/run-urls", params={"since": "yesterday"}, headers=auth()).status_code == 422


def test_truncated_above_the_cap(client, auth, seeded, monkeypatch):
    monkeypatch.setattr(run_request_service, "MAX_RUN_URLS", 2)
    body = client.get(f"{P}/run-urls", params={"since": since(60)}, headers=auth()).json()
    assert len(body["urls"]) == 2 and body["truncated"] is True


def test_roles(client, auth, seeded, project_role):
    for role in ("owner", "admin", "member", "viewer", "billing_manager"):
        project_role(role)
        assert client.get(f"{P}/run-urls", params={"since": since(10)}, headers=auth()).status_code == 200
    project_role(status_code=404, body={"detail": "Project not found"})
    assert client.get(f"{P}/run-urls", params={"since": since(10)}, headers=auth()).status_code == 404
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd platforms/test-management-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/integration/test_run_urls.py -q`
Expected: FAIL: 422 (`run-urls` parsed as `request_id`).

- [ ] **Step 3: Implement**

Append to `run_request_service.py`:

```python
MAX_RUN_URLS = 5000
RUN_URLS_MAX_AGE_DAYS = 500  # a previous report period reaches 491 days back (spec Ruling 5)


def run_urls(db: Session, project_id: int, since: datetime) -> tuple:
    """GitHub run URLs (html_url) of the project's Play requests made since `since`, newest first;
    (urls, truncated)."""
    rows = db.execute(
        select(RunRequest.github_run_url)
        .where(RunRequest.project_id == project_id, RunRequest.requested_at >= since,
               RunRequest.github_run_url.is_not(None))
        .order_by(RunRequest.requested_at.desc(), RunRequest.id.desc())
        .limit(MAX_RUN_URLS + 1)
    ).all()
    urls = [url for (url,) in rows]
    return urls[:MAX_RUN_URLS], len(urls) > MAX_RUN_URLS
```

(Check the module's existing imports: add `select` from sqlalchemy and `datetime` if missing.)

In `run_requests.py`, add **between** `list_run_requests` and `get_run_request` (FastAPI matches routes in order, so this must come before `/{request_id}`):

```python
@router.get("/run-urls")
def run_urls(
    since: datetime = Query(...),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    """The Play requests' GitHub run URLs, for the report's origin filter (ADR-026)."""
    moment = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
    if moment < datetime.now(timezone.utc) - timedelta(days=runs.RUN_URLS_MAX_AGE_DAYS):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"since is more than {runs.RUN_URLS_MAX_AGE_DAYS} days ago")
    urls, truncated = runs.run_urls(db, access.project_id, moment)
    return {"urls": urls, "truncated": truncated}
```

Add `from datetime import datetime, timedelta, timezone` at the top.

- [ ] **Step 4: Run the tests to verify they pass, then the whole service**

Run: `cd platforms/test-management-service && SECRET_KEY=test .venv/Scripts/python -m pytest -q`
Expected: PASS (the existing `test_run_requests.py` still passes: `/{request_id}` is unchanged).

- [ ] **Step 5: Commit**

```bash
git add platforms/test-management-service/src/casebook/service/run_request_service.py platforms/test-management-service/src/casebook/api/v1/endpoints/run_requests.py platforms/test-management-service/tests/integration/test_run_urls.py
git commit -m "feat(test-management): GET run-requests/run-urls for the report's origin filter" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- platforms/test-management-service/src/casebook/service/run_request_service.py platforms/test-management-service/src/casebook/api/v1/endpoints/run_requests.py platforms/test-management-service/tests/integration/test_run_urls.py
```

---

### Task 7: Gateway: `case-areas` route and gzip on exactly two locations; smoke checks

**Files:**
- Modify: `gateway/nginx.conf.template`
- Modify: `scripts/smoke_gateway.sh`

**Interfaces:**
- Consumes: Tasks 2–6 (the endpoints exist in the stack).
- Produces: routing and compression the dashboard relies on; smoke checks that also run the report's PostgreSQL paths in CI (Ruling 8).

- [ ] **Step 1: Write the failing smoke checks**

In `scripts/smoke_gateway.sh`, add after the `features -> test-management-service` checks (where `$PROJECT_ID` and the imported case exist):

```bash
# ---- report (spec 2026-10-08): case-areas and run-urls -> test-management; gzip on case-areas ----
# 40 scenarios make the case-areas body larger than gzip_min_length (1024 bytes)
AREAS_FEATURE="Feature: Report areas\n"
for i in $(seq 1 40); do AREAS_FEATURE="${AREAS_FEATURE}  Scenario: report area scenario number $i with a long title\n    Given step $i\n"; done
check "import 40 scenarios for case-areas" 200 POST "$BASE/api/v1/projects/$PROJECT_ID/cases/import" "${AUTH[@]}" \
  -H "Content-Type: application/json" -d "{\"files\":[{\"path\":\"tests/features/report/areas.feature\",\"content\":\"$AREAS_FEATURE\"}]}"
check "case-areas -> test-management-service" 200 GET "$BASE/api/v1/projects/$PROJECT_ID/case-areas" "${AUTH[@]}" \
  -H "Accept-Encoding: gzip" --compressed
body_has "... lists the imported folder" '"tests/features/report"'
if grep -qi '^content-encoding: gzip' "$TMP/headers"; then pass "case-areas is gzip-encoded"; else fail "case-areas is not gzip-encoded"; fi
SINCE="$(date -u -d '-30 days' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-30d +%Y-%m-%dT%H:%M:%SZ)"
check "run-urls -> test-management-service (not taken as a request id)" 200 GET \
  "$BASE/api/v1/projects/$PROJECT_ID/run-requests/run-urls?since=$SINCE" "${AUTH[@]}"
body_has "... an empty list" '"urls":[]'
```

And after the `analytics flaky` check (runs exist by then):

```bash
# ---- report on PostgreSQL: one array parameter for keys and URLs, SET LOCAL statement_timeout, gzip ----
TODAY="$(date -u +%Y-%m-%d)"
FROM="$(date -u -d '-29 days' +%Y-%m-%d 2>/dev/null || date -u -v-29d +%Y-%m-%d)"
REPORT_BODY="{\"from\":\"$FROM\",\"to\":\"$TODAY\",\"tz\":\"UTC\",\"sections\":[\"summary\"],\"origin\":\"ci\",\"requested_run_urls\":[\"https://github.com/a/b/actions/runs/1\"],\"test_keys\":[\"${FAILS_KEY:-$(printf 'a%.0s' $(seq 64))}\"]}"
check "analytics report -> ingestion-service" 200 POST "$BASE/api/v1/projects/$PROJECT_ID/analytics/report" "${AUTH[@]}" \
  -H "Content-Type: application/json" -H "Accept-Encoding: gzip" --compressed -d "$REPORT_BODY"
body_has "... counts the uploaded runs" '"scope":{"runs":'
if grep -qi '^content-encoding: gzip' "$TMP/headers"; then pass "analytics report is gzip-encoded"; else fail "analytics report is not gzip-encoded"; fi
check "a report over 90 days is refused" 422 POST "$BASE/api/v1/projects/$PROJECT_ID/analytics/report" "${AUTH[@]}" \
  -H "Content-Type: application/json" -d '{"from":"2026-01-01","to":"2026-06-01","sections":["summary"]}'
# gzip is not server-wide (BREACH): a large JSON response elsewhere and the login response stay plain
check "trends over 90 days (a large response outside the two gzip locations)" 200 GET \
  "$BASE/api/v1/projects/$PROJECT_ID/analytics/trends?days=90" "${AUTH[@]}" -H "Accept-Encoding: gzip"
if grep -qi '^content-encoding: gzip' "$TMP/headers"; then fail "trends is gzip-encoded: gzip leaked out of its two locations"; else pass "trends is not compressed"; fi
check "login is never compressed" 401 POST "$BASE/api/v1/auth/login" -H "Accept-Encoding: gzip" \
  -H "Content-Type: application/json" -d '{"email":"nobody@example.com","password":"wrong-password-1"}'
if grep -qi '^content-encoding: gzip' "$TMP/headers"; then fail "login is gzip-encoded"; else pass "login is not compressed"; fi
```

Note: the login check must run before the rate-limit block at the end (it does: it sits with the analytics checks). If the login endpoint answers 422 for this body in the current auth-service, change the expected status to the one it answers for wrong credentials; the point of the check is the header.

- [ ] **Step 2: Verify the checks fail against the current gateway**

Run (Docker required): `SECRET_KEY=s INTERNAL_API_PASSWORD=p docker compose up -d --build --wait gateway && SECRET_KEY=s INTERNAL_API_PASSWORD=p bash scripts/smoke_gateway.sh`
Expected: FAIL on "case-areas -> test-management-service" (404 from project-service) and on both gzip checks.
If Docker is not available to the implementer, say so in the task report and rely on the CI "Gateway and full stack" job; do not skip Step 3.

- [ ] **Step 3: Change the gateway**

In `gateway/nginx.conf.template`, in the `# ---- test-management-service (ADR-022) ----` block, add **before** the general test-management regex location (regex locations are tried in order):

```nginx
        # Report joins (ADR-026): every active case in one response; gzip only here and on
        # analytics/report, never server-wide (compressing responses that carry secrets or echo input
        # opens BREACH)
        location ~ ^/api/v1/projects/[0-9]+/case-areas$ {
            limit_req zone=api burst=40 nodelay;
            gzip on;
            gzip_proxied any;
            gzip_types application/json;
            gzip_min_length 1024;
            set $upstream http://test-management-service:8000;
            proxy_pass $upstream;
        }
```

Change the general test-management regex to include `case-areas`:

```nginx
        location ~ ^/api/v1/projects/[0-9]+/(cases|case-labels|case-folders|case-features|case-areas|features|suites|ci-target|run-requests)(/|$) {
```

In the `# ---- ingestion-service ----` block, add **before** the ingestion regex location:

```nginx
        # The report (spec 2026-10-08): a POST with up to 20,000 test keys (about 1.4 MB, under the
        # 10m body cap); the response is gzipped here only
        location ~ ^/api/v1/projects/[0-9]+/analytics/report$ {
            limit_req zone=api burst=40 nodelay;
            gzip on;
            gzip_proxied any;
            gzip_types application/json;
            gzip_min_length 1024;
            set $upstream http://ingestion-service:8000;
            proxy_pass $upstream;
        }
```

- [ ] **Step 4: Check the config and run the smoke test**

Run: `docker build -t qa-vision/gateway:local gateway && docker run --rm qa-vision/gateway:local nginx -t`
Expected: `syntax is ok` / `test is successful`.
Run: `SECRET_KEY=s INTERNAL_API_PASSWORD=p docker compose up -d --build --wait gateway && SECRET_KEY=s INTERNAL_API_PASSWORD=p bash scripts/smoke_gateway.sh`
Expected: `all gateway checks passed`.

- [ ] **Step 5: Commit**

```bash
git add gateway/nginx.conf.template scripts/smoke_gateway.sh
git commit -m "feat(gateway): route case-areas; gzip case-areas and analytics/report only" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- gateway/nginx.conf.template scripts/smoke_gateway.sh
```

---
### Task 8: Dashboard API modules: `postReport`, `getCaseAreas`, `getRunUrls`; `CI_LABELS` shared

**Files:**
- Create: `dashboard/src/api/report.ts`, `dashboard/src/api/report.test.ts`
- Create: `dashboard/src/lib/ciProviders.ts`
- Modify: `dashboard/src/api/cases.ts` (append), `dashboard/src/api/cases.test.ts` (append)
- Modify: `dashboard/src/api/runRequests.ts` (append)
- Modify: `dashboard/src/pages/RunsPage.tsx` (import `CI_LABELS` instead of the local constant; no behaviour change)
- Modify: `dashboard/src/test/server.ts` (default handler for repositories)

**Interfaces:**
- Consumes: `apiFetch`, `buildQuery` (`api/http.ts`).
- Produces (later tasks import exactly these):
  - `api/report.ts`: `ReportSectionName`, `ReportOrigin`, `ReportRequest`, `ReportPeriod`, `ReportTotals`, `ReportBucket`, `ReportTestRef`, `SummarySection`, `Report`, `postReport(projectId: number, body: ReportRequest, init?: { signal?: AbortSignal }): Promise<Report>`, `testLabel(r: { suite: string; class_name: string; name: string }): string`.
  - `api/cases.ts`: `CaseArea { number; title; testKey: string | null; folder: string | null; feature: string | null; labels: string[]; suiteIds: number[] }`, `CaseAreas { generatedAt: string; counts: { cases; linked; manual }; folders: string[]; features: string[]; labels: string[]; suites: { id: number; name: string }[]; cases: CaseArea[] }`, `getCaseAreas(projectId: number, init?: { signal?: AbortSignal }): Promise<CaseAreas>`.
  - `api/runRequests.ts`: `getRunUrls(projectId: number, since: string, init?: { signal?: AbortSignal }): Promise<{ urls: string[]; truncated: boolean }>`.
  - `lib/ciProviders.ts`: `CI_LABELS: Record<string, string>`.

- [ ] **Step 1: Write the failing tests**

`dashboard/src/api/report.test.ts`:

```ts
import { http, HttpResponse } from "msw";
import { server } from "../test/server";
import { setAccessToken } from "../auth/tokens";
import { postReport, testLabel, type ReportRequest } from "./report";

beforeEach(() => setAccessToken("acc"));

const BODY: ReportRequest = {
  from: "2026-09-09", to: "2026-10-08", tz: "Europe/Lisbon", branch: "main", environment: null, ci_provider: null,
  origin: "any", requested_run_urls: null, test_keys: null, sections: ["summary"], bucket: "auto",
};

test("postReport sends the body as JSON to the project's report", async () => {
  let seen: unknown = null;
  server.use(http.post("/api/v1/projects/42/analytics/report", async ({ request }) => {
    seen = await request.json();
    return HttpResponse.json({ scope: { runs: 0, previous_runs: 0, test_keys: null } });
  }));
  const report = await postReport(42, BODY);
  expect(seen).toEqual(BODY);
  expect(report.scope.runs).toBe(0);
});

test("a 503 report_timeout keeps its code", async () => {
  server.use(http.post("/api/v1/projects/42/analytics/report", () => HttpResponse.json(
    { detail: { code: "report_timeout", message: "This report took too long. Narrow the period or the filters." } },
    { status: 503 })));
  await expect(postReport(42, BODY)).rejects.toMatchObject({ status: 503, code: "report_timeout" });
});

test("testLabel joins suite, class and name", () => {
  expect(testLabel({ suite: "checkout", class_name: "", name: "pays" })).toBe("checkout › pays");
});
```

Append to `dashboard/src/api/cases.test.ts` (keep its existing imports; add these two):

```ts
import { getCaseAreas } from "./cases";
import { getRunUrls } from "./runRequests";

test("getCaseAreas maps the short names through the dictionaries", async () => {
  server.use(http.get("/api/v1/projects/42/case-areas", () => HttpResponse.json({
    generated_at: "2026-10-08T14:02:11Z", counts: { cases: 2, linked: 1, manual: 1 },
    folders: ["features/booking"], features: ["Air booking"], labels: ["ado-12", "smoke"],
    suites: [{ id: 12, name: "Regression" }],
    cases: [
      { n: 1, t: "Book", k: "ab".repeat(32), fo: 0, fe: 0, l: [0, 1], s: [0] },
      { n: 4, t: "manual", k: null, fo: null, fe: null, l: [], s: [] },
    ],
  })));
  const areas = await getCaseAreas(42);
  expect(areas.generatedAt).toBe("2026-10-08T14:02:11Z");
  expect(areas.cases[0]).toEqual({ number: 1, title: "Book", testKey: "ab".repeat(32), folder: "features/booking",
    feature: "Air booking", labels: ["ado-12", "smoke"], suiteIds: [12] });
  expect(areas.cases[1]).toEqual({ number: 4, title: "manual", testKey: null, folder: null, feature: null, labels: [], suiteIds: [] });
});

test("getRunUrls asks with since", async () => {
  let since: string | null = null;
  server.use(http.get("/api/v1/projects/42/run-requests/run-urls", ({ request }) => {
    since = new URL(request.url).searchParams.get("since");
    return HttpResponse.json({ urls: ["https://github.com/a/b/actions/runs/1"], truncated: false });
  }));
  expect((await getRunUrls(42, "2026-08-09T00:00:00Z")).urls).toHaveLength(1);
  expect(since).toBe("2026-08-09T00:00:00Z");
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd dashboard && npx vitest run src/api/report.test.ts src/api/cases.test.ts`
Expected: FAIL (modules and exports missing).

- [ ] **Step 3: Write `api/report.ts`**

```ts
import { apiFetch } from "./http";

// Types mirror platforms/ingestion-service/src/ingestion/schemas/report.py and service/report_service.py
// (spec docs/superpowers/specs/2026-10-08-report-deep-analysis-design.md). Phases 2 and 3 add their sections.

export type ReportSectionName = "summary" | "failure_causes" | "regressions" | "tests" | "duration";
export type ReportOrigin = "any" | "ci" | "qeos";

export interface ReportRequest {
  from: string;
  to: string;
  tz: string;
  branch: string | null;
  environment: string | null;
  ci_provider: string | null;
  origin: ReportOrigin;
  requested_run_urls: string[] | null;
  test_keys: string[] | null;
  sections: ReportSectionName[];
  bucket: "auto" | "day" | "week";
}

export interface ReportPeriod { from: string; to: string; days: number; start: string; end: string }

export interface ReportTotals {
  runs: number;
  executions: number;
  passed: number;
  failed: number;
  errored: number;
  skipped: number;
  pass_rate: number | null;
  tests: number;
  failing_tests: number;
  avg_run_duration_ms: number | null;
}

export interface ReportBucket {
  date: string;
  runs: number;
  executions: number;
  passed: number;
  failed: number;
  errored: number;
  skipped: number;
  pass_rate: number | null;
}

export interface ReportTestRef { test_key: string; suite: string; class_name: string; name: string }

export interface SummarySection {
  current: ReportTotals;
  previous: ReportTotals | null;
  buckets: ReportBucket[];
  /** The previous period, bucket by bucket: `date` is the previous period's day (plan Ruling 2) */
  previous_buckets: ReportBucket[];
  top_failing: (ReportTestRef & { executions: number; failures: number; pass_rate: number | null })[];
  slowest: (ReportTestRef & { executions: number; avg_duration_ms: number | null })[];
  branches: { branch: string | null; runs: number; executions: number; failures: number; pass_rate: number | null }[];
  facets: { branches: string[]; environments: string[]; ci_providers: string[] };
}

export interface Report {
  period: ReportPeriod;
  previous_period: ReportPeriod;
  tz: string;
  bucket: "day" | "week";
  generated_at: string;
  scope: { runs: number; previous_runs: number; test_keys: number | null };
  summary?: SummarySection;
}

export function postReport(projectId: number, body: ReportRequest, init: { signal?: AbortSignal } = {}): Promise<Report> {
  return apiFetch(`/api/v1/projects/${projectId}/analytics/report`, {
    method: "POST", body: JSON.stringify(body), signal: init.signal,
  });
}

export function testLabel(r: { suite: string; class_name: string; name: string }): string {
  return [r.suite, r.class_name, r.name].filter(Boolean).join(" › ");
}
```

- [ ] **Step 4: Append to `api/cases.ts`**

```ts
/** GET /case-areas as the server sends it: short names keep 20,000 cases near 0.5 MB gzipped. */
interface CaseAreasWire {
  generated_at: string;
  counts: { cases: number; linked: number; manual: number };
  folders: string[];
  features: string[];
  labels: string[];
  suites: { id: number; name: string }[];
  cases: { n: number; t: string; k: string | null; fo: number | null; fe: number | null; l: number[]; s: number[] }[];
}

/** One active case, for the report's joins (the dashboard maps test keys to areas; ADR-026). */
export interface CaseArea {
  number: number;
  title: string;
  testKey: string | null;
  /** The directory part of its .feature path; null at the root and for a manual case */
  folder: string | null;
  feature: string | null;
  labels: string[];
  suiteIds: number[];
}

export interface CaseAreas {
  generatedAt: string;
  counts: { cases: number; linked: number; manual: number };
  folders: string[];
  features: string[];
  labels: string[];
  suites: { id: number; name: string }[];
  cases: CaseArea[];
}

/** Every active case in one response; a 409 `too_many_cases` above 50,000. The short names are mapped here, once. */
export async function getCaseAreas(projectId: number, init: { signal?: AbortSignal } = {}): Promise<CaseAreas> {
  const wire = await apiFetch<CaseAreasWire>(`${base(projectId)}/case-areas`, init);
  return {
    generatedAt: wire.generated_at,
    counts: wire.counts,
    folders: wire.folders,
    features: wire.features,
    labels: wire.labels,
    suites: wire.suites,
    cases: wire.cases.map((c) => ({
      number: c.n,
      title: c.t,
      testKey: c.k,
      folder: c.fo === null ? null : wire.folders[c.fo],
      feature: c.fe === null ? null : wire.features[c.fe],
      labels: c.l.map((i) => wire.labels[i]),
      suiteIds: c.s.map((i) => wire.suites[i].id),
    })),
  };
}
```

- [ ] **Step 5: Append to `api/runRequests.ts`; add `lib/ciProviders.ts`; use it in RunsPage; default handler**

```ts
/** The GitHub run URLs of Play requests made since `since` (ISO), newest first: the report's origin filter. */
export function getRunUrls(
  projectId: number,
  since: string,
  init: { signal?: AbortSignal } = {},
): Promise<{ urls: string[]; truncated: boolean }> {
  return apiFetch(`${base(projectId)}/run-requests/run-urls${buildQuery({ since })}`, init);
}
```

`dashboard/src/lib/ciProviders.ts`:

```ts
/** Display names of ingestion's CI_PROVIDERS (platforms/ingestion-service/src/ingestion/models/run.py). */
export const CI_LABELS: Record<string, string> = {
  github_actions: "GitHub Actions",
  gitlab_ci: "GitLab CI",
  azure_pipelines: "Azure Pipelines",
  jenkins: "Jenkins",
  other: "Other",
  local: "Local",
};
```

In `pages/RunsPage.tsx` delete the local `const CI_LABELS: Record<string, string> = { ... };` block and add `import { CI_LABELS } from "../lib/ciProviders";`.

In `test/server.ts`, add to the default handlers:

```ts
  // The report's default branch reads the project's repositories; tests about it override
  http.get("/api/v1/projects/:projectId/repositories", () => HttpResponse.json([])),
```

- [ ] **Step 6: Run the tests, lint and typecheck**

Run: `cd dashboard && npx vitest run src/api src/pages/RunsPage.test.tsx && npm run lint && npm run typecheck`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add dashboard/src/api/report.ts dashboard/src/api/report.test.ts dashboard/src/api/cases.ts dashboard/src/api/cases.test.ts dashboard/src/api/runRequests.ts dashboard/src/lib/ciProviders.ts dashboard/src/pages/RunsPage.tsx dashboard/src/test/server.ts
git commit -m "feat(dashboard): report, case-areas and run-urls API clients" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard/src/api/report.ts dashboard/src/api/report.test.ts dashboard/src/api/cases.ts dashboard/src/api/cases.test.ts dashboard/src/api/runRequests.ts dashboard/src/lib/ciProviders.ts dashboard/src/pages/RunsPage.tsx dashboard/src/test/server.ts
```

---

### Task 9: `lib/reportDelta.ts` and `lib/reportScope.ts` (key resolution)

**Files:**
- Create: `dashboard/src/lib/reportDelta.ts`, `dashboard/src/lib/reportDelta.test.ts`
- Create: `dashboard/src/lib/reportScope.ts`, `dashboard/src/lib/reportScope.test.ts`

**Interfaces:**
- Consumes: `CaseAreas`, `CaseArea` (Task 8).
- Produces:
  - `reportDelta.ts`: `type Better = "up" | "down" | "neither"`, `interface Delta { direction: "up" | "down" | "flat"; text: string; spoken: string; verdict: "better" | "worse" | null }`, `pointsDelta(current: number | null, previous: number | null, days: number, better: Better): Delta | null`, `relativeDelta(current: number | null, previous: number | null, days: number, better: Better): Delta | null`.
  - `reportScope.ts`: `type AreaKind = "feature" | "folder" | "label"`, `interface AreaFilter { kind: AreaKind; value: string }`, `AREA_KINDS`, `AREA_NAMES: Record<AreaKind, string>`, `MAX_REPORT_KEYS = 20000`, `parseArea(raw: string): AreaFilter | null`, `formatArea(a: AreaFilter): string`, `caseInArea(c: CaseArea, area: AreaFilter): boolean`, `type KeyScope = { kind: "all" } | { kind: "keys"; keys: string[] } | { kind: "empty" } | { kind: "too_many"; count: number }`, `resolveScope(areas: CaseAreas, area: AreaFilter | null, suiteId: number | null): KeyScope`, `folderCounts(areas: CaseAreas): { path: string; count: number }[]` (each folder counts its subfolders' cases, for `FolderSelect`).

- [ ] **Step 1: Write the failing tests**

`dashboard/src/lib/reportDelta.test.ts`:

```ts
import { pointsDelta, relativeDelta } from "./reportDelta";

test("pass rate moves in points and up is better", () => {
  expect(pointsDelta(0.9781, 0.9661, 30, "up")).toEqual({
    direction: "up", text: "up 1.2 pts vs previous 30 days", spoken: "up 1.2 points versus the previous 30 days", verdict: "better",
  });
  expect(pointsDelta(0.9, 0.95, 7, "up")?.verdict).toBe("worse");
});

test("counts and durations move relatively; failures down is better", () => {
  expect(relativeDelta(86, 100, 30, "down")).toEqual({
    direction: "down", text: "down 14% vs previous 30 days", spoken: "down 14 percent versus the previous 30 days", verdict: "better",
  });
  expect(relativeDelta(120, 100, 30, "down")?.verdict).toBe("worse");
});

test("runs are neutral, no change is flat, and a start from zero is said in words", () => {
  expect(relativeDelta(412, 398, 30, "neither")?.verdict).toBeNull();
  expect(relativeDelta(100, 100, 30, "down")).toMatchObject({ direction: "flat", text: "no change vs previous 30 days", verdict: null });
  expect(relativeDelta(5, 0, 30, "down")).toMatchObject({ direction: "up", text: "up from 0 vs previous 30 days", verdict: "worse" });
  expect(relativeDelta(0, 0, 30, "down")?.direction).toBe("flat");
});

test("no delta without both values", () => {
  expect(pointsDelta(null, 0.9, 30, "up")).toBeNull();
  expect(relativeDelta(3, null, 30, "down")).toBeNull();
});
```

`dashboard/src/lib/reportScope.test.ts`:

```ts
import type { CaseArea, CaseAreas } from "../api/cases";
import { MAX_REPORT_KEYS, folderCounts, formatArea, parseArea, resolveScope } from "./reportScope";

const k = (n: number) => n.toString(16).padStart(64, "0");

function area(number: number, over: Partial<CaseArea> = {}): CaseArea {
  return { number, title: `case ${number}`, testKey: k(number), folder: null, feature: null, labels: [], suiteIds: [], ...over };
}

const AREAS: CaseAreas = {
  generatedAt: "2026-10-08T14:02:11Z", counts: { cases: 5, linked: 4, manual: 1 },
  folders: ["features/booking", "features/booking/air", "features/bookingx"], features: ["Air", "Booking"],
  labels: ["smoke"], suites: [{ id: 12, name: "Regression" }],
  cases: [
    area(1, { folder: "features/booking", feature: "Booking", labels: ["smoke"], suiteIds: [12] }),
    area(2, { folder: "features/booking/air", feature: "Air", suiteIds: [12] }),
    area(3, { folder: "features/bookingx", feature: "Booking" }),
    area(4, { testKey: null, folder: "features/booking", feature: "Booking", suiteIds: [12] }),
    area(5, { testKey: k(1), feature: "Air" }),  // a second case linked to the same test
  ],
};

test("areas parse and format; malformed ones are null", () => {
  expect(parseArea("feature:Air booking")).toEqual({ kind: "feature", value: "Air booking" });
  expect(parseArea("folder:features/booking/")).toEqual({ kind: "folder", value: "features/booking" });
  expect(formatArea({ kind: "label", value: "smoke" })).toBe("label:smoke");
  for (const bad of ["", "feature:", "bogus:x", "nocolon", `feature:${"x".repeat(501)}`]) expect(parseArea(bad)).toBeNull();
});

test("no area and no suite is every test", () => {
  expect(resolveScope(AREAS, null, null)).toEqual({ kind: "all" });
});

test("feature, folder (with subfolders, whole segments) and label resolve to linked keys only", () => {
  expect(resolveScope(AREAS, { kind: "feature", value: "Booking" }, null)).toEqual({ kind: "keys", keys: [k(1), k(3)] });
  expect(resolveScope(AREAS, { kind: "folder", value: "features/booking" }, null)).toEqual({ kind: "keys", keys: [k(1), k(2)] });
  expect(resolveScope(AREAS, { kind: "label", value: "SMOKE" }, null)).toEqual({ kind: "keys", keys: [k(1)] });
});

test("a suite alone and combined with an area", () => {
  expect(resolveScope(AREAS, null, 12)).toEqual({ kind: "keys", keys: [k(1), k(2)] });
  expect(resolveScope(AREAS, { kind: "feature", value: "Air" }, 12)).toEqual({ kind: "keys", keys: [k(2)] });
});

test("nothing linked is empty; more than 20,000 keys is too many", () => {
  expect(resolveScope(AREAS, { kind: "feature", value: "Nothing" }, null)).toEqual({ kind: "empty" });
  const many: CaseAreas = { ...AREAS, cases: Array.from({ length: MAX_REPORT_KEYS + 1 }, (_, i) => area(i + 1, { feature: "Big" })) };
  expect(resolveScope(many, { kind: "feature", value: "Big" }, null)).toEqual({ kind: "too_many", count: MAX_REPORT_KEYS + 1 });
});

test("folder counts include subfolders, for the folder picker", () => {
  expect(folderCounts(AREAS)).toEqual([
    { path: "features", count: 4 },
    { path: "features/booking", count: 3 },
    { path: "features/booking/air", count: 1 },
    { path: "features/bookingx", count: 1 },
  ]);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd dashboard && npx vitest run src/lib/reportDelta.test.ts src/lib/reportScope.test.ts`
Expected: FAIL (modules missing).

- [ ] **Step 3: Write `lib/reportDelta.ts`**

```ts
/** Which way is good for a metric: pass rate "up", failures and durations "down", runs "neither". */
export type Better = "up" | "down" | "neither";

/** A change against the previous period, in words: never an arrow or a colour alone (DESIGN.md, KPI Tiles). */
export interface Delta {
  direction: "up" | "down" | "flat";
  /** Visible: "up 1.2 pts vs previous 30 days" */
  text: string;
  /** For the tile's accessible name: "up 1.2 points versus the previous 30 days" */
  spoken: string;
  verdict: "better" | "worse" | null;
}

function verdict(direction: Delta["direction"], better: Better): Delta["verdict"] {
  if (direction === "flat" || better === "neither") return null;
  return direction === better ? "better" : "worse";
}

function flat(days: number): Delta {
  return { direction: "flat", text: `no change vs previous ${days} days`, spoken: `no change versus the previous ${days} days`, verdict: null };
}

/** A rate (0..1) as percentage points to one decimal. */
export function pointsDelta(current: number | null, previous: number | null, days: number, better: Better): Delta | null {
  if (current === null || previous === null) return null;
  const points = Math.round((current - previous) * 1000) / 10;
  if (points === 0) return flat(days);
  const direction = points > 0 ? "up" : "down";
  const size = Math.abs(points).toFixed(1);
  return {
    direction,
    text: `${direction} ${size} pts vs previous ${days} days`,
    spoken: `${direction} ${size} points versus the previous ${days} days`,
    verdict: verdict(direction, better),
  };
}

/** A count or a duration as a whole percentage of the previous value. */
export function relativeDelta(current: number | null, previous: number | null, days: number, better: Better): Delta | null {
  if (current === null || previous === null) return null;
  if (previous === 0) {
    if (current === 0) return flat(days);
    return { direction: "up", text: `up from 0 vs previous ${days} days`, spoken: `up from 0 versus the previous ${days} days`, verdict: verdict("up", better) };
  }
  const percent = Math.round(((current - previous) / previous) * 100);
  if (percent === 0) return flat(days);
  const direction = percent > 0 ? "up" : "down";
  const size = Math.abs(percent);
  return {
    direction,
    text: `${direction} ${size}% vs previous ${days} days`,
    spoken: `${direction} ${size} percent versus the previous ${days} days`,
    verdict: verdict(direction, better),
  };
}
```

- [ ] **Step 4: Write `lib/reportScope.ts`**

```ts
import type { CaseArea, CaseAreas } from "../api/cases";

/** The report's joins (spec: Filters; ADR-026): area and suite filters become test keys from case-areas.
 *  Pure, so every rule is unit-tested. Phase 3 adds grouping by area. */

export type AreaKind = "feature" | "folder" | "label";
export interface AreaFilter { kind: AreaKind; value: string }
export const AREA_KINDS: AreaKind[] = ["feature", "folder", "label"];
export const AREA_NAMES: Record<AreaKind, string> = { feature: "Feature", folder: "Folder", label: "Label" };

/** The most keys one report request carries (the cap of /cases/search too). */
export const MAX_REPORT_KEYS = 20_000;
const MAX_AREA_VALUE = 500;

/** "feature:Booking", "folder:features/booking" or "label:smoke"; anything else is null. */
export function parseArea(raw: string): AreaFilter | null {
  const colon = raw.indexOf(":");
  if (colon <= 0) return null;
  const kind = raw.slice(0, colon);
  let value = raw.slice(colon + 1);
  if (!(AREA_KINDS as string[]).includes(kind)) return null;
  if (kind === "folder") value = value.replace(/\/+$/, "");
  if (value === "" || value.length > MAX_AREA_VALUE || value.includes("\u0000")) return null;
  return { kind: kind as AreaKind, value };
}

export function formatArea(a: AreaFilter): string {
  return `${a.kind}:${a.value}`;
}

/** A folder includes its subfolders, matched on whole path segments (the Cases folder filter's rule). */
export function caseInArea(c: CaseArea, area: AreaFilter): boolean {
  if (area.kind === "feature") return c.feature === area.value;
  if (area.kind === "label") return c.labels.includes(area.value.toLowerCase());
  return c.folder !== null && (c.folder === area.value || c.folder.startsWith(`${area.value}/`));
}

export type KeyScope =
  | { kind: "all" }
  | { kind: "keys"; keys: string[] }
  | { kind: "empty" }
  | { kind: "too_many"; count: number };

/** The test keys of the automated cases in the area and the suite (AND). Unlinked cases drop out. */
export function resolveScope(areas: CaseAreas, area: AreaFilter | null, suiteId: number | null): KeyScope {
  if (area === null && suiteId === null) return { kind: "all" };
  const keys = new Set<string>();
  for (const c of areas.cases) {
    if (!c.testKey) continue;
    if (area && !caseInArea(c, area)) continue;
    if (suiteId !== null && !c.suiteIds.includes(suiteId)) continue;
    keys.add(c.testKey.toLowerCase());
  }
  if (keys.size === 0) return { kind: "empty" };
  if (keys.size > MAX_REPORT_KEYS) return { kind: "too_many", count: keys.size };
  return { kind: "keys", keys: [...keys].sort() };
}

/** Every folder and its ancestors with the number of cases under it, sorted by path: FolderSelect's input. */
export function folderCounts(areas: CaseAreas): { path: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const c of areas.cases) {
    if (!c.folder) continue;
    const parts = c.folder.split("/");
    for (let i = 1; i <= parts.length; i++) {
      const path = parts.slice(0, i).join("/");
      counts.set(path, (counts.get(path) ?? 0) + 1);
    }
  }
  return [...counts].map(([path, count]) => ({ path, count })).sort((a, b) => a.path.localeCompare(b.path));
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd dashboard && npx vitest run src/lib/reportDelta.test.ts src/lib/reportScope.test.ts && npm run lint && npm run typecheck`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add dashboard/src/lib/reportDelta.ts dashboard/src/lib/reportDelta.test.ts dashboard/src/lib/reportScope.ts dashboard/src/lib/reportScope.test.ts
git commit -m "feat(dashboard): report deltas in words and area/suite key resolution" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard/src/lib/reportDelta.ts dashboard/src/lib/reportDelta.test.ts dashboard/src/lib/reportScope.ts dashboard/src/lib/reportScope.test.ts
```

---

### Task 10: `useReportFilters`: URL state, validation, presets in `tz`

**Files:**
- Create: `dashboard/src/pages/report/useReportFilters.ts`
- Test: `dashboard/src/pages/report/useReportFilters.test.tsx`

**Interfaces:**
- Consumes: `CI_LABELS` (Task 8); `AreaFilter`, `parseArea` (Task 9).
- Produces:
  - `PRESETS = ["7", "30", "90"] as const`, `type Preset`, `DEFAULT_PRESET = "30"`, `MAX_SPAN_DAYS = 90`, `MAX_AGE_DAYS = 400`, `ALL_BRANCHES = "*"`.
  - `FILTER_KEYS = ["period", "from", "to", "branch", "env", "ci", "origin", "area", "suite"] as const`, `type FilterKey`.
  - `interface ReportFilters { preset: Preset | null; from: string; to: string; days: number; branch: string; environment: string; ci: string; origin: "any" | "ci" | "qeos"; area: AreaFilter | null; suite: number | null }` (`branch`: `""` = the default branch, `ALL_BRANCHES` = every branch).
  - `todayIn(tz: string, now?: Date): string`, `addDays(day: string, n: number): string`, `spanDays(from: string, to: string): number`.
  - `parseReportFilters(params: URLSearchParams, today: string): { filters: ReportFilters; dropped: FilterKey[] }`.
  - `useReportFilters(tz: string): { filters: ReportFilters; update(patch: Partial<Record<FilterKey, string>>): void; clearAll(): void; notice: boolean; dismissNotice(): void }`.

- [ ] **Step 1: Write the failing tests**

```tsx
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { addDays, parseReportFilters, spanDays, todayIn, useReportFilters } from "./useReportFilters";

const TODAY = "2026-10-08";
const parse = (q: string) => parseReportFilters(new URLSearchParams(q), TODAY);

test("today is the calendar day in the zone", () => {
  const late = new Date("2026-10-08T23:30:00Z");
  expect(todayIn("UTC", late)).toBe("2026-10-08");
  expect(todayIn("Europe/Lisbon", late)).toBe("2026-10-09");
  expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
  expect(spanDays("2026-09-09", "2026-10-08")).toBe(30);
});

test("the default is the last 30 days, the default branch, every origin", () => {
  const { filters, dropped } = parse("");
  expect(filters).toEqual({ preset: "30", from: "2026-09-09", to: TODAY, days: 30, branch: "", environment: "", ci: "",
    origin: "any", area: null, suite: null });
  expect(dropped).toEqual([]);
});

test("every filter round-trips from the URL", () => {
  const { filters } = parse("from=2026-09-01&to=2026-09-30&branch=*&env=staging&ci=jenkins&origin=qeos&area=folder:features/booking&suite=12");
  expect(filters).toEqual({ preset: null, from: "2026-09-01", to: "2026-09-30", days: 30, branch: "*", environment: "staging",
    ci: "jenkins", origin: "qeos", area: { kind: "folder", value: "features/booking" }, suite: 12 });
  expect(parse("period=7").filters).toMatchObject({ preset: "7", from: "2026-10-02", to: TODAY, days: 7 });
});

test.each([
  ["period=45", ["period"]],
  ["from=2026-09-30&to=2026-09-01", ["from", "to"]],
  ["from=2026-06-01&to=2026-09-30", ["from", "to"]],     // more than 90 days
  ["from=2026-10-01&to=2026-10-09", ["from", "to"]],     // after today
  ["from=2025-08-01&to=2025-08-05", ["from", "to"]],     // more than 400 days ago
  ["from=2026-02-30&to=2026-03-02", ["from", "to"]],     // not a date
  ["from=2026-09-01", ["from"]],
  ["ci=travis", ["ci"]],
  ["origin=sometimes", ["origin"]],
  ["area=bogus", ["area"]],
  ["suite=abc", ["suite"]],
  [`branch=${"b".repeat(256)}`, ["branch"]],
  [`env=${"e".repeat(101)}`, ["env"]],
])("%s is dropped", (q, dropped) => {
  expect(parse(q).dropped).toEqual(dropped);
});

function Probe() {
  const { filters, update, clearAll, notice, dismissNotice } = useReportFilters("UTC");
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <div>
      <output data-testid="filters">{JSON.stringify(filters)}</output>
      <output data-testid="search">{location.search}</output>
      {notice && <p>Some filters in the link were not valid and were removed <button onClick={dismissNotice}>Dismiss</button></p>}
      <button onClick={() => update({ period: "7" })}>7 days</button>
      <button onClick={() => update({ from: "2026-09-01", to: "2026-09-02" })}>custom</button>
      <button onClick={clearAll}>Clear all</button>
      <button onClick={() => navigate(-1)}>Back</button>
    </div>
  );
}

function renderAt(search: string) {
  render(
    <MemoryRouter initialEntries={["/projects/42/report", `/projects/42/report${search}`]} initialIndex={1}>
      <Routes><Route path="/projects/:projectId/report" element={<Probe />} /></Routes>
    </MemoryRouter>,
  );
}

const read = () => JSON.parse(screen.getByTestId("filters").textContent!);
const search = () => screen.getByTestId("search").textContent;

test("updates write the URL, presets and custom ranges replace each other, Back restores", async () => {
  renderAt("?env=staging");
  await userEvent.click(screen.getByRole("button", { name: "7 days" }));
  expect(search()).toBe("?env=staging&period=7");
  await userEvent.click(screen.getByRole("button", { name: "custom" }));
  expect(search()).toBe("?env=staging&from=2026-09-01&to=2026-09-02");
  await userEvent.click(screen.getByRole("button", { name: "Back" }));
  expect(read().preset).toBe("7");
});

test("Clear all keeps the period and the view settings, and returns to the default branch", async () => {
  renderAt("?period=90&branch=release&ci=jenkins&group=folder");
  await userEvent.click(screen.getByRole("button", { name: "Clear all" }));
  expect(search()).toBe("?period=90&group=folder");
  expect(read().branch).toBe("");
});

test("invalid parameters are removed from the URL with a notice", async () => {
  renderAt("?ci=travis&env=staging");
  expect(await screen.findByText(/some filters in the link were not valid/i)).toBeInTheDocument();
  expect(search()).toBe("?env=staging");
  await act(() => userEvent.click(screen.getByRole("button", { name: "Dismiss" })));
  expect(screen.queryByText(/some filters in the link/i)).not.toBeInTheDocument();
});
```

Note: `parse()` uses `TODAY`; the Probe tests use the real clock and only assert URL text and presets. The custom range `2026-09-01..02` must be valid for "today" at execution time, which holds until 2027-10 (400-day rule); if it fails then, move the dates forward.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd dashboard && npx vitest run src/pages/report/useReportFilters.test.tsx`
Expected: FAIL (module missing).

- [ ] **Step 3: Write `useReportFilters.ts`**

```ts
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CI_LABELS } from "../../lib/ciProviders";
import { type AreaFilter, parseArea } from "../../lib/reportScope";

/** The report's filters live in the URL (spec: Filters): reload, share and Back restore them. */

export const PRESETS = ["7", "30", "90"] as const;
export type Preset = (typeof PRESETS)[number];
export const DEFAULT_PRESET: Preset = "30";
export const MAX_SPAN_DAYS = 90;
export const MAX_AGE_DAYS = 400;
/** `branch=*`: every branch. No `branch`: the project's default branch (plan Ruling 1). `*` is not a legal git branch name. */
export const ALL_BRANCHES = "*";

export const FILTER_KEYS = ["period", "from", "to", "branch", "env", "ci", "origin", "area", "suite"] as const;
export type FilterKey = (typeof FILTER_KEYS)[number];
const PERIOD_KEYS: readonly FilterKey[] = ["period", "from", "to"];

export interface ReportFilters {
  /** null: a custom from-to range */
  preset: Preset | null;
  from: string;
  to: string;
  days: number;
  /** "" = the project's default branch; ALL_BRANCHES = every branch; else that branch */
  branch: string;
  environment: string;
  ci: string;
  origin: "any" | "ci" | "qeos";
  area: AreaFilter | null;
  suite: number | null;
}

const DAY_MS = 86_400_000;

/** The calendar day it is now in `tz`, as YYYY-MM-DD. */
export function todayIn(tz: string, now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}

export function addDays(day: string, n: number): string {
  return new Date(Date.parse(`${day}T00:00:00Z`) + n * DAY_MS).toISOString().slice(0, 10);
}

/** Days from `from` to `to`, both included. */
export function spanDays(from: string, to: string): number {
  return Math.round((Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / DAY_MS) + 1;
}

function isDay(s: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const time = Date.parse(`${s}T00:00:00Z`);
  return !Number.isNaN(time) && new Date(time).toISOString().slice(0, 10) === s;
}

const noNul = (s: string) => !s.includes("\u0000");

/** Reads and checks the URL. Invalid parameters are listed in `dropped` and read as unset. */
export function parseReportFilters(params: URLSearchParams, today: string): { filters: ReportFilters; dropped: FilterKey[] } {
  const dropped: FilterKey[] = [];
  const get = (k: FilterKey) => params.get(k) ?? "";

  let preset: Preset | null = DEFAULT_PRESET;
  const period = get("period");
  if (period && !(PRESETS as readonly string[]).includes(period)) dropped.push("period");
  else if (period) preset = period as Preset;

  let from = "";
  let to = "";
  const rawFrom = get("from");
  const rawTo = get("to");
  if (rawFrom || rawTo) {
    const ok = isDay(rawFrom) && isDay(rawTo) && rawFrom <= rawTo && spanDays(rawFrom, rawTo) <= MAX_SPAN_DAYS
      && rawTo <= today && rawFrom >= addDays(today, -MAX_AGE_DAYS);
    if (ok) {
      from = rawFrom;
      to = rawTo;
      preset = null;
    } else {
      if (rawFrom) dropped.push("from");
      if (rawTo) dropped.push("to");
    }
  }
  if (preset !== null) {
    to = today;
    from = addDays(today, -(Number(preset) - 1));
  }

  const branch = get("branch");
  const okBranch = branch.length <= 255 && noNul(branch);
  if (!okBranch) dropped.push("branch");
  const env = get("env");
  const okEnv = env.length <= 100 && noNul(env);
  if (!okEnv) dropped.push("env");
  const ci = get("ci");
  const okCi = ci === "" || ci in CI_LABELS;
  if (!okCi) dropped.push("ci");
  const origin = get("origin");
  const okOrigin = origin === "" || origin === "ci" || origin === "qeos";
  if (!okOrigin) dropped.push("origin");
  const rawArea = get("area");
  const area = rawArea ? parseArea(rawArea) : null;
  if (rawArea && !area) dropped.push("area");
  const rawSuite = get("suite");
  const okSuite = rawSuite === "" || /^[1-9]\d{0,9}$/.test(rawSuite);
  if (!okSuite) dropped.push("suite");

  return {
    filters: {
      preset, from, to, days: spanDays(from, to),
      branch: okBranch ? branch : "",
      environment: okEnv ? env : "",
      ci: okCi ? ci : "",
      origin: okOrigin && origin ? (origin as "ci" | "qeos") : "any",
      area,
      suite: okSuite && rawSuite ? Number(rawSuite) : null,
    },
    dropped,
  };
}

export function useReportFilters(tz: string) {
  const [params, setParams] = useSearchParams();
  const today = todayIn(tz);
  const { filters, dropped } = useMemo(() => parseReportFilters(params, today), [params, today]);

  // A hand-edited or stale link: remove what is invalid (replacing the history entry, so Back does not
  // return to it) and say so until dismissed
  const [notice, setNotice] = useState(false);
  const droppedKey = dropped.join("|");
  useEffect(() => {
    if (!droppedKey) return;
    setNotice(true);
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      for (const key of droppedKey.split("|")) next.delete(key);
      return next;
    }, { replace: true });
  }, [droppedKey, setParams]);

  /** "" removes a key. A preset removes the custom range and the other way round; the default preset is left out. */
  const update = useCallback((patch: Partial<Record<FilterKey, string>>) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      for (const [key, value] of Object.entries(patch)) {
        if (value) next.set(key, value);
        else next.delete(key);
      }
      if (patch.period) {
        next.delete("from");
        next.delete("to");
      }
      if (patch.from || patch.to) next.delete("period");
      if (next.get("period") === DEFAULT_PRESET) next.delete("period");
      return next;
    });
  }, [setParams]);

  /** Every filter back to its default except the period; view settings (P3 grouping) stay. */
  const clearAll = useCallback(() => {
    setParams((prev) => {
      const next = new URLSearchParams(prev);
      for (const key of FILTER_KEYS) if (!PERIOD_KEYS.includes(key)) next.delete(key);
      return next;
    });
  }, [setParams]);

  const dismissNotice = useCallback(() => setNotice(false), []);
  return { filters, update, clearAll, notice, dismissNotice };
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd dashboard && npx vitest run src/pages/report/useReportFilters.test.tsx && npm run lint && npm run typecheck`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/pages/report/useReportFilters.ts dashboard/src/pages/report/useReportFilters.test.tsx
git commit -m "feat(dashboard): report filters in the URL with validation and a notice" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard/src/pages/report/useReportFilters.ts dashboard/src/pages/report/useReportFilters.test.tsx
```

---

### Task 11: Request gating (`useReportRequest`) and the section frame (`ReportSection`)

Invoke the `ui-ux-pro-max` skill before editing `ReportSection.tsx` or `index.css`.

**Files:**
- Create: `dashboard/src/pages/report/useReportRequest.ts`, `dashboard/src/pages/report/useReportRequest.test.ts`
- Create: `dashboard/src/pages/report/ReportSection.tsx`, `dashboard/src/pages/report/ReportSection.test.tsx`
- Modify: `dashboard/src/index.css` (section head and empty-state rules, next to the existing `.report-*` rules)

**Interfaces:**
- Consumes: Tasks 8–10 (`postReport`, `getCaseAreas`, `getRunUrls`, `resolveScope`, `formatArea`, `MAX_REPORT_KEYS`, `ReportFilters`, `ALL_BRANCHES`, `addDays`), `listRepositories` (`api/repositories.ts`), `ApiError`.
- Produces:
  - `REPORT_STALE_MS = 300_000`.
  - `type Gate = { state: "wait" } | { state: "blocked"; message: string; error?: unknown; retry?: () => void } | { state: "ready"; base: Omit<ReportRequest, "sections">; key: readonly unknown[] }`.
  - `interface GateInput { filters: ReportFilters; tz: string; defaultBranch: string | null; caseAreas: { data?: CaseAreas; error: unknown; refetch: () => unknown }; runUrls: { data?: { urls: string[] }; error: unknown; refetch: () => unknown } }`, `computeGate(input: GateInput): Gate` (pure).
  - `effectiveBranch(filters, defaultBranch): string | null`, `runUrlsSince(filters): string`, `caseAreasMessage(error: unknown): string`.
  - `useDefaultBranch(projectId: number): string | null` (null while loading).
  - `useReportRequest(projectId, filters, tz, opts: { loadCaseAreas: boolean }): { gate: Gate; caseAreas: UseQueryResult<CaseAreas>; runUrls: UseQueryResult<{ urls: string[]; truncated: boolean }>; defaultBranch: string | null; effectiveBranch: string | null }`.
  - `useReportSection(projectId: number, gate: Gate, section: ReportSectionName): UseQueryResult<Report>`.
  - `ReportSection.tsx`: `interface SectionQuery { data: Report | undefined; error: unknown; isPending: boolean; refetch: () => unknown }`; default export `ReportSection(props: { id: string; title: string; gate: Gate; query: SectionQuery; height?: number; actions?: ReactNode; note?: ReactNode; noRuns?: (report: Report) => ReactNode; onResetFilters: () => void; children: (report: Report) => ReactNode })`.

- [ ] **Step 1: Write the failing tests**

`dashboard/src/pages/report/useReportRequest.test.ts`:

```ts
import { ApiError } from "../../api/http";
import type { CaseAreas } from "../../api/cases";
import { parseReportFilters } from "./useReportFilters";
import { caseAreasMessage, computeGate, effectiveBranch, runUrlsSince } from "./useReportRequest";

const TODAY = "2026-10-08";
const filters = (q = "") => parseReportFilters(new URLSearchParams(q), TODAY).filters;
const idle = { data: undefined, error: null, refetch: () => undefined };
const AREAS: CaseAreas = {
  generatedAt: "v1", counts: { cases: 1, linked: 1, manual: 0 }, folders: [], features: ["Booking"], labels: [], suites: [],
  cases: [{ number: 1, title: "a", testKey: "ab".repeat(32), folder: null, feature: "Booking", labels: [], suiteIds: [] }],
};

test("the default branch waits for the repositories; * is every branch", () => {
  expect(computeGate({ filters: filters(), tz: "UTC", defaultBranch: null, caseAreas: idle, runUrls: idle })).toEqual({ state: "wait" });
  expect(effectiveBranch(filters(), "develop")).toBe("develop");
  expect(effectiveBranch(filters("branch=*"), "develop")).toBeNull();
  expect(effectiveBranch(filters("branch=release"), "develop")).toBe("release");
});

test("ready: the request base and a key without the test keys", () => {
  const gate = computeGate({ filters: filters("env=staging"), tz: "Europe/Lisbon", defaultBranch: "main", caseAreas: idle, runUrls: idle });
  expect(gate).toEqual({
    state: "ready",
    base: { from: "2026-09-09", to: TODAY, tz: "Europe/Lisbon", branch: "main", environment: "staging", ci_provider: null,
      origin: "any", requested_run_urls: null, test_keys: null, bucket: "auto" },
    key: [{ from: "2026-09-09", to: TODAY, tz: "Europe/Lisbon", branch: "main", environment: "staging", ci: "", origin: "any",
      area: null, suite: null }, null],
  });
});

test("an area waits for case-areas, then sends its keys and keys the query on the case-areas version", () => {
  const f = filters("area=feature:Booking");
  expect(computeGate({ filters: f, tz: "UTC", defaultBranch: "main", caseAreas: idle, runUrls: idle }).state).toBe("wait");
  const gate = computeGate({ filters: f, tz: "UTC", defaultBranch: "main", caseAreas: { ...idle, data: AREAS }, runUrls: idle });
  expect(gate.state === "ready" && gate.base.test_keys).toEqual(["ab".repeat(32)]);
  expect(gate.state === "ready" && gate.key[1]).toBe("v1");
});

test("an area with no linked tests, too many, or failed case-areas blocks the sections", () => {
  const nothing = computeGate({ filters: filters("area=feature:Nothing"), tz: "UTC", defaultBranch: "main", caseAreas: { ...idle, data: AREAS }, runUrls: idle });
  expect(nothing).toEqual({ state: "blocked", message: "No automated tests are linked to cases in this area" });
  const failed = computeGate({ filters: filters("suite=3"), tz: "UTC", defaultBranch: "main",
    caseAreas: { ...idle, error: new ApiError(409, "x", "too_many_cases") }, runUrls: idle });
  expect(failed).toMatchObject({ state: "blocked", message: "This project has more cases than the report can join (50,000)" });
  expect(caseAreasMessage(new ApiError(500, "boom"))).toBe("Cases could not be loaded");
});

test("origin waits for the Play URLs and never sends the sections unfiltered", () => {
  const f = filters("origin=qeos");
  expect(computeGate({ filters: f, tz: "UTC", defaultBranch: "main", caseAreas: idle, runUrls: idle }).state).toBe("wait");
  expect(computeGate({ filters: f, tz: "UTC", defaultBranch: "main", caseAreas: idle, runUrls: { ...idle, error: new ApiError(500, "down") } }))
    .toMatchObject({ state: "blocked", message: "Play requests could not be loaded" });
  const ready = computeGate({ filters: f, tz: "UTC", defaultBranch: "main", caseAreas: idle, runUrls: { ...idle, data: { urls: ["u"] } } });
  expect(ready.state === "ready" && ready.base.requested_run_urls).toEqual(["u"]);
  expect(runUrlsSince(f)).toBe("2026-08-09T00:00:00Z");  // previous from (2026-08-10) minus one day
});
```

`dashboard/src/pages/report/ReportSection.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "../../api/http";
import type { Report } from "../../api/report";
import ReportSection, { type SectionQuery } from "./ReportSection";
import type { Gate } from "./useReportRequest";

const READY: Gate = { state: "ready", base: {} as never, key: [] };
const report = (runs: number) => ({ scope: { runs, previous_runs: 0, test_keys: null } }) as Report;
const q = (over: Partial<SectionQuery>): SectionQuery => ({ data: undefined, error: null, isPending: false, refetch: vi.fn(), ...over });

function show(gate: Gate, query: SectionQuery, reset = vi.fn()) {
  render(
    <ReportSection id="s" title="Summary" gate={gate} query={query} onResetFilters={reset} noRuns={() => <button>Clear filters</button>}>
      {(r) => <p>{r.scope.runs} runs shown</p>}
    </ReportSection>,
  );
  return reset;
}

test("a section is a region named by its heading, with data", () => {
  show(READY, q({ data: report(3) }));
  expect(screen.getByRole("region", { name: "Summary" })).toHaveTextContent("3 runs shown");
});

test("loading while the gate waits or the request runs", () => {
  show({ state: "wait" }, q({ isPending: true }));
  expect(screen.getByRole("status", { name: /loading summary/i })).toBeInTheDocument();
});

test("no runs: says so and offers the section's way out", () => {
  show(READY, q({ data: report(0) }));
  expect(screen.getByText("No runs match these filters in this period")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Clear filters" })).toBeInTheDocument();
});

test("a blocked gate shows its message, with Retry when it carries an error", async () => {
  const retry = vi.fn();
  show({ state: "blocked", message: "Cases could not be loaded", error: new ApiError(500, "boom"), retry }, q({}));
  expect(screen.getByText("Cases could not be loaded")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(retry).toHaveBeenCalled();
});

test("a timeout shows the server's message with Retry", async () => {
  const refetch = vi.fn();
  show(READY, q({ error: new ApiError(503, "This report took too long. Narrow the period or the filters.", "report_timeout"), refetch }));
  expect(screen.getByRole("alert")).toHaveTextContent("This report took too long");
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(refetch).toHaveBeenCalled();
});

test("a 422 names the problem and offers Reset filters", async () => {
  const reset = show(READY, q({ error: new ApiError(422, "from: the period is 95 days") }));
  expect(screen.getByRole("alert")).toHaveTextContent("These filters are not valid: from: the period is 95 days");
  await userEvent.click(screen.getByRole("button", { name: "Reset filters" }));
  expect(reset).toHaveBeenCalled();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd dashboard && npx vitest run src/pages/report/useReportRequest.test.ts src/pages/report/ReportSection.test.tsx`
Expected: FAIL (modules missing).

- [ ] **Step 3: Write `useReportRequest.ts`**

```ts
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { type CaseAreas, getCaseAreas } from "../../api/cases";
import { ApiError } from "../../api/http";
import { type Report, type ReportRequest, type ReportSectionName, postReport } from "../../api/report";
import { listRepositories } from "../../api/repositories";
import { getRunUrls } from "../../api/runRequests";
import { MAX_REPORT_KEYS, formatArea, resolveScope } from "../../lib/reportScope";
import { ALL_BRANCHES, type ReportFilters, addDays } from "./useReportFilters";

/** Report answers are reused for 5 minutes (spec: Caching). */
export const REPORT_STALE_MS = 5 * 60_000;

/** Whether the sections can be asked yet: they wait for the default branch, the case-areas join and the Play
 *  URLs they need, and are never sent unfiltered while one of those is missing. */
export type Gate =
  | { state: "wait" }
  | { state: "blocked"; message: string; error?: unknown; retry?: () => void }
  | { state: "ready"; base: Omit<ReportRequest, "sections">; key: readonly unknown[] };

interface Loaded<T> { data?: T; error: unknown; refetch: () => unknown }
export interface GateInput {
  filters: ReportFilters;
  tz: string;
  defaultBranch: string | null;
  caseAreas: Loaded<CaseAreas>;
  runUrls: Loaded<{ urls: string[] }>;
}

export function effectiveBranch(filters: ReportFilters, defaultBranch: string | null): string | null {
  if (filters.branch === ALL_BRANCHES) return null;
  return filters.branch || defaultBranch;
}

/** Play requests are made before their runs start: ask from the previous period's first day, minus one. */
export function runUrlsSince(filters: ReportFilters): string {
  return `${addDays(filters.from, -filters.days - 1)}T00:00:00Z`;
}

export function caseAreasMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 409 && error.code === "too_many_cases") {
    return "This project has more cases than the report can join (50,000)";
  }
  return "Cases could not be loaded";
}

export function computeGate({ filters, tz, defaultBranch, caseAreas, runUrls }: GateInput): Gate {
  if (filters.branch === "" && defaultBranch === null) return { state: "wait" };
  let keys: string[] | null = null;
  let version: string | null = null;
  if (filters.area !== null || filters.suite !== null) {
    if (caseAreas.error) {
      return { state: "blocked", message: caseAreasMessage(caseAreas.error), error: caseAreas.error, retry: () => void caseAreas.refetch() };
    }
    if (!caseAreas.data) return { state: "wait" };
    const scope = resolveScope(caseAreas.data, filters.area, filters.suite);
    if (scope.kind === "empty") return { state: "blocked", message: "No automated tests are linked to cases in this area" };
    if (scope.kind === "too_many") {
      return { state: "blocked", message: `This selection has more than ${MAX_REPORT_KEYS.toLocaleString("en")} automated tests. Narrow it with another filter.` };
    }
    if (scope.kind === "keys") keys = scope.keys;
    // Only a key filter depends on case-areas, so only then does its version join the query key
    version = caseAreas.data.generatedAt;
  }
  let urls: string[] | null = null;
  if (filters.origin !== "any") {
    if (runUrls.error) {
      return { state: "blocked", message: "Play requests could not be loaded", error: runUrls.error, retry: () => void runUrls.refetch() };
    }
    if (!runUrls.data) return { state: "wait" };
    urls = runUrls.data.urls;
  }
  const branch = effectiveBranch(filters, defaultBranch);
  return {
    state: "ready",
    base: {
      from: filters.from, to: filters.to, tz, branch, environment: filters.environment || null,
      ci_provider: filters.ci || null, origin: filters.origin, requested_run_urls: urls, test_keys: keys, bucket: "auto",
    },
    // The filters, never the keys: the keys follow from the filters and the case-areas version
    key: [{
      from: filters.from, to: filters.to, tz, branch, environment: filters.environment, ci: filters.ci,
      origin: filters.origin, area: filters.area ? formatArea(filters.area) : null, suite: filters.suite,
    }, version],
  };
}

/** The first repository's default branch, else main (plan Ruling 1); null while loading. */
export function useDefaultBranch(projectId: number): string | null {
  const repos = useQuery({
    queryKey: ["repositories", projectId], queryFn: () => listRepositories(projectId), staleTime: REPORT_STALE_MS, retry: false,
  });
  if (repos.isPending) return null;
  return repos.data?.[0]?.default_branch || "main";
}

export function useReportRequest(projectId: number, filters: ReportFilters, tz: string, opts: { loadCaseAreas: boolean }) {
  const defaultBranch = useDefaultBranch(projectId);
  const needAreas = opts.loadCaseAreas || filters.area !== null || filters.suite !== null;
  const caseAreas = useQuery({
    queryKey: ["case-areas", projectId], queryFn: ({ signal }) => getCaseAreas(projectId, { signal }),
    enabled: needAreas, staleTime: REPORT_STALE_MS, retry: false,
  });
  const since = runUrlsSince(filters);
  const runUrls = useQuery({
    queryKey: ["run-urls", projectId, since], queryFn: ({ signal }) => getRunUrls(projectId, since, { signal }),
    enabled: filters.origin !== "any", staleTime: REPORT_STALE_MS, retry: false,
  });
  const { data: areasData, error: areasError, refetch: refetchAreas } = caseAreas;
  const { data: urlsData, error: urlsError, refetch: refetchUrls } = runUrls;
  const gate = useMemo(
    () => computeGate({
      filters, tz, defaultBranch,
      caseAreas: { data: areasData, error: areasError, refetch: refetchAreas },
      runUrls: { data: urlsData, error: urlsError, refetch: refetchUrls },
    }),
    [filters, tz, defaultBranch, areasData, areasError, refetchAreas, urlsData, urlsError, refetchUrls],
  );
  return { gate, caseAreas, runUrls, defaultBranch, effectiveBranch: effectiveBranch(filters, defaultBranch) };
}

/** One request per section, so each loads and fails on its own; a filter change aborts the one in flight. */
export function useReportSection(projectId: number, gate: Gate, section: ReportSectionName) {
  return useQuery<Report>({
    queryKey: ["report", projectId, section, ...(gate.state === "ready" ? gate.key : [])],
    queryFn: ({ signal }) => {
      if (gate.state !== "ready") throw new Error("The report is not ready to be asked");
      return postReport(projectId, { ...gate.base, sections: [section] }, { signal });
    },
    enabled: gate.state === "ready",
    staleTime: REPORT_STALE_MS,
    retry: false,
  });
}
```

- [ ] **Step 4: Write `ReportSection.tsx`**

```tsx
import type { ReactNode } from "react";
import { ApiError } from "../../api/http";
import type { Report } from "../../api/report";
import ErrorBanner from "../../components/ErrorBanner";
import { SkeletonStatus } from "../../components/Skeleton";
import type { Gate } from "./useReportRequest";

/** What a section needs from its query (UseQueryResult<Report> fits). */
export interface SectionQuery {
  data: Report | undefined;
  error: unknown;
  isPending: boolean;
  refetch: () => unknown;
}

interface Props {
  id: string;
  title: string;
  gate: Gate;
  query: SectionQuery;
  /** The skeleton's height, so the page does not jump when the data arrives */
  height?: number;
  /** CSV buttons and grouping controls; never printed */
  actions?: ReactNode;
  /** A help line under the heading (what a figure counts, which filters do not apply) */
  note?: ReactNode;
  /** Extra content for "No runs match these filters in this period" */
  noRuns?: (report: Report) => ReactNode;
  onResetFilters: () => void;
  children: (report: Report) => ReactNode;
}

function SectionError({ error, retry, reset }: { error: unknown; retry: () => unknown; reset: () => void }) {
  if (error instanceof ApiError && error.status === 422) {
    return (
      <div className="error-banner" role="alert">
        <span>These filters are not valid: {error.detail}</span>
        <button type="button" onClick={reset}>Reset filters</button>
      </div>
    );
  }
  // A 503 report_timeout carries its own sentence ("This report took too long. Narrow the period or the filters.")
  return <ErrorBanner error={error} onRetry={() => void retry()} />;
}

/** One report section: an h2-named region whose body is loading, blocked, an error with Retry, "no runs", or the data.
 *  An error is never shown as an empty period. */
export default function ReportSection({ id, title, gate, query, height = 240, actions, note, noRuns, onResetFilters, children }: Props) {
  let body: ReactNode;
  if (gate.state === "blocked") {
    body = gate.error != null
      ? <><p>{gate.message}</p><ErrorBanner error={gate.error} onRetry={gate.retry} /></>
      : <p className="muted">{gate.message}</p>;
  } else if (query.error != null) {
    body = <SectionError error={query.error} retry={query.refetch} reset={onResetFilters} />;
  } else if (gate.state === "wait" || query.isPending || !query.data) {
    body = (
      <SkeletonStatus label={`Loading ${title.toLowerCase()}…`}>
        <span className="skeleton skeleton-block" style={{ height }} aria-hidden="true" />
      </SkeletonStatus>
    );
  } else if (query.data.scope.runs === 0) {
    body = (
      <div className="report-empty">
        <p className="muted">No runs match these filters in this period</p>
        {noRuns?.(query.data)}
      </div>
    );
  } else {
    body = children(query.data);
  }
  return (
    <section className="card report-section" aria-labelledby={id}>
      <div className="report-section-head">
        <h2 id={id}>{title}</h2>
        {actions != null && <div className="report-section-actions no-print">{actions}</div>}
      </div>
      {note != null && <p className="muted report-note">{note}</p>}
      {body}
    </section>
  );
}
```

- [ ] **Step 5: Styles**

Append next to the `.report-*` rules in `dashboard/src/index.css` (tokens only):

```css
.report-section-head { display: flex; justify-content: space-between; align-items: baseline; gap: var(--space-3); flex-wrap: wrap; }
.report-section-head h2 { margin: 0; }
.report-section-actions { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.report-section-actions button { display: inline-flex; align-items: center; gap: var(--space-2); }
.report-empty { display: flex; flex-direction: column; gap: var(--space-3); align-items: flex-start; }
.report-empty .button-row { display: flex; gap: var(--space-2); flex-wrap: wrap; }
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd dashboard && npx vitest run src/pages/report && npm run lint && npm run typecheck`
Expected: PASS (lint: 0 errors).

- [ ] **Step 7: Commit**

```bash
git add dashboard/src/pages/report/useReportRequest.ts dashboard/src/pages/report/useReportRequest.test.ts dashboard/src/pages/report/ReportSection.tsx dashboard/src/pages/report/ReportSection.test.tsx dashboard/src/index.css
git commit -m "feat(dashboard): report request gating and the section frame" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard/src/pages/report/useReportRequest.ts dashboard/src/pages/report/useReportRequest.test.ts dashboard/src/pages/report/ReportSection.tsx dashboard/src/pages/report/ReportSection.test.tsx dashboard/src/index.css
```

---
### Task 12: `DeltaTile` and Section 1 `SummarySection`

Invoke the `ui-ux-pro-max` skill before writing these components or editing `index.css`.

**Files:**
- Create: `dashboard/src/pages/report/DeltaTile.tsx`
- Create: `dashboard/src/pages/report/sections/SummarySection.tsx`
- Create: `dashboard/src/pages/report/testFixtures.ts` (test data shared by the report tests; imported by tests only)
- Test: `dashboard/src/pages/report/sections/SummarySection.test.tsx`
- Modify: `dashboard/src/index.css` (delta verdict colours)

**Interfaces:**
- Consumes: Tasks 8–11 (`Report`, `testLabel`, `pointsDelta`, `relativeDelta`, `ReportSection`, `SectionQuery`, `Gate`, `FilterKey`), `formatPassRate`, `formatDuration` (`api/analytics.ts`), ChartKit, `formatTick`, `formatPointLabel`, `toCsv`, `downloadCsv`, `NarrowMeta`.
- Produces:
  - `DeltaTile({ title: string; value: string; delta: Delta | null; noPrevious: boolean })` (a `group` whose name is the whole sentence).
  - `SummarySection({ projectId: number; gate: Gate; query: SectionQuery; branch: string | null; environment: string; onClearFilters(): void; onTry(patch: Partial<Record<FilterKey, string>>): void })`.
  - Pure exports from `SummarySection.tsx`: `bucketsCsv(r: Report): string`, `testsCsv(r: Report): string`, `branchesCsv(r: Report): string`, `suggestions(r: Report, branch: string | null, environment: string): { label: string; patch: Partial<Record<FilterKey, string>> }[]`.
  - `testFixtures.ts`: `SUMMARY_REPORT: Report` (30 days, deltas as in the spec's examples), `emptyReport(): Report`.

- [ ] **Step 1: Write the fixtures and the failing tests**

`dashboard/src/pages/report/testFixtures.ts`:

```ts
import type { Report, ReportBucket, ReportTotals } from "../../api/report";

const bucket = (date: string, over: Partial<ReportBucket> = {}): ReportBucket => ({
  date, runs: 14, executions: 3301, passed: 3200, failed: 70, errored: 3, skipped: 28, pass_rate: 0.9776, ...over,
});

const totals = (over: Partial<ReportTotals> = {}): ReportTotals => ({
  runs: 412, executions: 98234, passed: 95010, failed: 2011, errored: 113, skipped: 1100, pass_rate: 0.9781,
  tests: 1003, failing_tests: 61, avg_run_duration_ms: 734000, ...over,
});

/** A 30-day report: pass rate up 1.2 pts, failures down 14%, average run time up 5% (the spec's examples). */
export const SUMMARY_REPORT: Report = {
  period: { from: "2026-09-09", to: "2026-10-08", days: 30, start: "2026-09-08T23:00:00Z", end: "2026-10-08T23:00:00Z" },
  previous_period: { from: "2026-08-10", to: "2026-09-08", days: 30, start: "2026-08-09T23:00:00Z", end: "2026-09-08T23:00:00Z" },
  tz: "Europe/Lisbon",
  bucket: "day",
  generated_at: "2026-10-08T14:02:11Z",
  scope: { runs: 412, previous_runs: 398, test_keys: null },
  summary: {
    current: totals(),
    previous: totals({ runs: 398, executions: 95000, failed: 2400, errored: 70, pass_rate: 0.9661, failing_tests: 70, avg_run_duration_ms: 700000 }),
    buckets: [bucket("2026-10-07"), bucket("2026-10-08", { failed: 140, pass_rate: 0.95 })],
    previous_buckets: [bucket("2026-09-07", { pass_rate: 0.97 }), bucket("2026-09-08", { pass_rate: null, runs: 0 })],
    top_failing: [{ test_key: "a".repeat(64), suite: "checkout", class_name: "Cart", name: "pays", executions: 30, failures: 12, pass_rate: 0.6 }],
    slowest: [{ test_key: "b".repeat(64), suite: "checkout", class_name: "Cart", name: "slow one", executions: 30, avg_duration_ms: 81000 }],
    branches: [{ branch: "main", runs: 120, executions: 30120, failures: 400, pass_rate: 0.986 }],
    facets: { branches: ["main", "release/2.4"], environments: ["staging"], ci_providers: ["github_actions"] },
  },
};

/** No runs match: the summary still carries facets, for the suggestions. */
export function emptyReport(): Report {
  return {
    ...SUMMARY_REPORT,
    scope: { runs: 0, previous_runs: 0, test_keys: null },
    summary: { ...SUMMARY_REPORT.summary!, current: totals({ runs: 0, executions: 0, pass_rate: null }), previous: null },
  };
}
```

`dashboard/src/pages/report/sections/SummarySection.test.tsx`:

```tsx
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import type { Report } from "../../../api/report";
import type { SectionQuery } from "../ReportSection";
import type { Gate } from "../useReportRequest";
import { SUMMARY_REPORT, emptyReport } from "../testFixtures";
import SummarySection, { branchesCsv, bucketsCsv, suggestions, testsCsv } from "./SummarySection";

const READY: Gate = { state: "ready", base: {} as never, key: [] };
const query = (data: Report): SectionQuery => ({ data, error: null, isPending: false, refetch: vi.fn() });

function show(data: Report, handlers = { onClearFilters: vi.fn(), onTry: vi.fn() }) {
  render(
    <MemoryRouter>
      <SummarySection projectId={42} gate={READY} query={query(data)} branch="main" environment="" {...handlers} />
    </MemoryRouter>,
  );
  return handlers;
}

test("tiles carry the value and the delta in words, with better or worse", () => {
  show(SUMMARY_REPORT);
  expect(screen.getByRole("group", { name: "Pass rate 97.8%, up 1.2 points versus the previous 30 days, better" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Failures 2,124, down 14 percent versus the previous 30 days, better" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: /^Average run time 12m 14s, up 5 percent versus the previous 30 days, worse$/ })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: /^Runs 412, up 4 percent versus the previous 30 days$/ })).toBeInTheDocument();  // neutral
  expect(screen.getByText("up 1.2 pts vs previous 30 days")).toBeInTheDocument();
});

test("without a previous period the tiles say so instead of a delta", () => {
  const report = { ...SUMMARY_REPORT, summary: { ...SUMMARY_REPORT.summary!, previous: null } };
  show(report);
  expect(screen.getAllByText("No data in the previous period")).toHaveLength(6);
});

test("the chart is a figure with a caption and a data table; the three tables honour the filters", () => {
  show(SUMMARY_REPORT);
  const figure = screen.getByRole("figure");
  expect(within(figure).getByText(/98,234 executions in 412 runs, pass rate 97\.8%, 96\.6% in the previous period/)).toBeInTheDocument();
  expect(screen.getByText(/show data table/i)).toBeInTheDocument();
  const failing = screen.getByRole("table", { name: /most failing tests/i });
  expect(within(failing).getByRole("link", { name: /checkout › Cart › pays/ })).toHaveAttribute(
    "href", `/projects/42/tests/${"a".repeat(64)}?branch=main`);
  expect(within(screen.getByRole("table", { name: /slowest tests/i })).getByText(/slow one/)).toBeInTheDocument();
  expect(within(screen.getByRole("table", { name: /branches/i })).getByText("main")).toBeInTheDocument();
});

test("no runs: Clear filters and facet suggestions", async () => {
  const { onClearFilters, onTry } = show(emptyReport());
  await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
  expect(onClearFilters).toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: "Try branch release/2.4" }));
  expect(onTry).toHaveBeenCalledWith({ branch: "release/2.4" });
  expect(suggestions(emptyReport(), "main", "")).toEqual([
    { label: "Try branch release/2.4", patch: { branch: "release/2.4" } },
    { label: "Try environment staging", patch: { env: "staging" } },
  ]);
});

test("CSV exports have headers and one row per item", () => {
  expect(bucketsCsv(SUMMARY_REPORT).split("\r\n")).toEqual([
    "date,runs,executions,passed,failed,errored,skipped,pass_rate,previous_date,previous_runs,previous_pass_rate",
    "2026-10-07,14,3301,3200,70,3,28,0.9776,2026-09-07,14,0.97",
    "2026-10-08,14,3301,3200,140,3,28,0.95,2026-09-08,0,",
  ]);
  expect(testsCsv(SUMMARY_REPORT).split("\r\n")[0]).toBe("list,suite,class_name,name,test_key,executions,failures,pass_rate,avg_duration_ms");
  expect(testsCsv(SUMMARY_REPORT).split("\r\n")).toHaveLength(3);
  expect(branchesCsv(SUMMARY_REPORT).split("\r\n")).toEqual(["branch,runs,executions,failures,pass_rate", "main,120,30120,400,0.986"]);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd dashboard && npx vitest run src/pages/report/sections/SummarySection.test.tsx`
Expected: FAIL (modules missing).

- [ ] **Step 3: Write `DeltaTile.tsx`**

```tsx
import { ArrowDown, ArrowUp, CircleAlert, CircleCheck, CircleDot, Minus } from "lucide-react";
import type { Delta } from "../../lib/reportDelta";

const ARROW = { up: ArrowUp, down: ArrowDown, flat: Minus } as const;
const TONE_ICON = { neutral: CircleDot, good: CircleCheck, bad: CircleAlert } as const;

/** A KPI tile with its change against the previous period (DESIGN.md: KPI Tiles, Delta Tiles). The change is an
 *  icon plus words, and "better" or "worse" says the verdict: never colour alone. The group's name is the sentence. */
export default function DeltaTile({ title, value, delta, noPrevious }: {
  title: string;
  value: string;
  delta: Delta | null;
  noPrevious: boolean;
}) {
  const tone = delta?.verdict === "better" ? "good" : delta?.verdict === "worse" ? "bad" : "neutral";
  const ToneIcon = TONE_ICON[tone];
  const Arrow = delta ? ARROW[delta.direction] : null;
  const spoken = noPrevious
    ? "no data in the previous period"
    : delta ? `${delta.spoken}${delta.verdict ? `, ${delta.verdict}` : ""}` : "";
  return (
    <div role="group" aria-label={`${title} ${value}${spoken ? `, ${spoken}` : ""}`} className={`kpi kpi-${tone}`}>
      <div className="kpi-body" aria-hidden="true">
        <span className="kpi-title"><span className="kpi-tone"><ToneIcon size={14} aria-hidden="true" /></span>{title}</span>
        <span className="kpi-value">{value}</span>
        {noPrevious ? (
          <span className="kpi-sub">No data in the previous period</span>
        ) : delta && Arrow ? (
          <span className={`kpi-sub delta-${delta.verdict ?? "neutral"}`}>
            <Arrow size={13} aria-hidden="true" />
            <span>{delta.text}</span>
            {delta.verdict && <strong className="delta-verdict">· {delta.verdict}</strong>}
          </span>
        ) : null}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Write `sections/SummarySection.tsx`**

```tsx
import { useState } from "react";
import { Link } from "react-router-dom";
import { Download } from "lucide-react";
import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatDuration, formatPassRate } from "../../../api/analytics";
import { type Report, testLabel } from "../../../api/report";
import { DataTableDisclosure, type LegendSeries, PATTERN, SeriesLegend } from "../../../components/ChartKit";
import NarrowMeta from "../../../components/NarrowMeta";
import { formatPointLabel, formatTick } from "../../../lib/chartFormat";
import { downloadCsv, toCsv } from "../../../lib/csv";
import { pointsDelta, relativeDelta } from "../../../lib/reportDelta";
import DeltaTile from "../DeltaTile";
import ReportSection, { type SectionQuery } from "../ReportSection";
import type { FilterKey } from "../useReportFilters";
import type { Gate } from "../useReportRequest";

const number = new Intl.NumberFormat();
const axisTick = { fill: "var(--text-secondary)", fontSize: 12 } as const;
const tooltipStyles = {
  contentStyle: { background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 6 },
  itemStyle: { color: "var(--text-primary)" },
  labelStyle: { color: "var(--text-secondary)" },
} as const;

const STATUS = [
  { key: "passed", label: "Passed", paint: "var(--status-passed)" },
  { key: "failed", label: "Failed", paint: `url(#${PATTERN.failed})` },
  { key: "errored", label: "Errored", paint: `url(#${PATTERN.errored})` },
  { key: "skipped", label: "Skipped", paint: `url(#${PATTERN.skipped})` },
] as const;
const LEGEND: LegendSeries[] = [
  ...STATUS.map((s) => ({ key: s.key, label: s.label, paint: s.paint })),
  { key: "rate", label: "Pass rate", paint: "var(--series-1)", line: {} },
  { key: "previousRate", label: "Pass rate, previous period", paint: "var(--series-2)", line: { dash: "5 4" } },
];

type Patch = Partial<Record<FilterKey, string>>;
const pct = (rate: number | null) => (rate === null ? null : Math.round(rate * 1000) / 10);

export function bucketsCsv(r: Report): string {
  const s = r.summary!;
  return toCsv(
    ["date", "runs", "executions", "passed", "failed", "errored", "skipped", "pass_rate", "previous_date", "previous_runs", "previous_pass_rate"],
    s.buckets.map((b, i) => {
      const p = s.previous_buckets[i];
      return [b.date, b.runs, b.executions, b.passed, b.failed, b.errored, b.skipped, b.pass_rate,
        p?.date ?? null, p?.runs ?? null, p?.pass_rate ?? null];
    }),
  );
}

export function testsCsv(r: Report): string {
  const s = r.summary!;
  return toCsv(
    ["list", "suite", "class_name", "name", "test_key", "executions", "failures", "pass_rate", "avg_duration_ms"],
    [
      ...s.top_failing.map((t) => ["most failing", t.suite, t.class_name, t.name, t.test_key, t.executions, t.failures, t.pass_rate, null]),
      ...s.slowest.map((t) => ["slowest", t.suite, t.class_name, t.name, t.test_key, t.executions, null, null, t.avg_duration_ms]),
    ],
  );
}

export function branchesCsv(r: Report): string {
  return toCsv(["branch", "runs", "executions", "failures", "pass_rate"],
    r.summary!.branches.map((b) => [b.branch, b.runs, b.executions, b.failures, b.pass_rate]));
}

/** Up to three ways out of an empty result, from the period's busiest values (facets ignore the other filters). */
export function suggestions(r: Report, branch: string | null, environment: string): { label: string; patch: Patch }[] {
  const facets = r.summary?.facets;
  if (!facets) return [];
  return [
    ...facets.branches.filter((b) => b !== branch).map((b) => ({ label: `Try branch ${b}`, patch: { branch: b } })),
    ...facets.environments.filter((e) => e !== environment).map((e) => ({ label: `Try environment ${e}`, patch: { env: e } })),
  ].slice(0, 3);
}

function csvButton(label: string, filename: string, csv: () => string) {
  return (
    <button type="button" onClick={() => downloadCsv(filename, csv())}>
      <Download size={15} aria-hidden="true" /> {label}
    </button>
  );
}

interface Props {
  projectId: number;
  gate: Gate;
  query: SectionQuery;
  /** The branch the report is on (null: every branch), for the test-history links */
  branch: string | null;
  environment: string;
  onClearFilters: () => void;
  onTry: (patch: Patch) => void;
}

/** Section 1 (spec: Section 1: Summary): six delta tiles, results per bucket with this and the previous period's
 *  pass rate, and the most failing, slowest and branch tables, all under the page's filters. */
export default function SummarySection({ projectId, gate, query, branch, environment, onClearFilters, onTry }: Props) {
  const [hidden, setHidden] = useState<ReadonlySet<string>>(new Set());
  const toggle = (key: string) => setHidden((h) => {
    const next = new Set(h);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    return next;
  });
  const file = (r: Report, part: string) => `report-${projectId}-${r.period.from}-${r.period.to}-${part}.csv`;
  const history = (key: string) =>
    `/projects/${projectId}/tests/${encodeURIComponent(key)}${branch ? `?branch=${encodeURIComponent(branch)}` : ""}`;

  return (
    <ReportSection
      id="report-summary"
      title="Summary"
      gate={gate}
      query={query}
      height={420}
      onResetFilters={onClearFilters}
      actions={query.data?.summary && query.data.scope.runs > 0 ? (
        <>
          {csvButton("Buckets CSV", file(query.data, "buckets"), () => bucketsCsv(query.data!))}
          {csvButton("Tests CSV", file(query.data, "tests"), () => testsCsv(query.data!))}
          {csvButton("Branches CSV", file(query.data, "branches"), () => branchesCsv(query.data!))}
        </>
      ) : undefined}
      noRuns={(r) => (
        <div className="button-row no-print">
          <button type="button" onClick={onClearFilters}>Clear filters</button>
          {suggestions(r, branch, environment).map((s) => (
            <button type="button" key={s.label} onClick={() => onTry(s.patch)}>{s.label}</button>
          ))}
        </div>
      )}
    >
      {(r) => {
        const s = r.summary!;
        const cur = s.current;
        const prev = s.previous;
        const days = r.period.days;
        const failures = cur.failed + cur.errored;
        const prevFailures = prev ? prev.failed + prev.errored : null;
        const unit = r.bucket;
        const rows = s.buckets.map((b, i) => ({
          date: b.date, passed: b.passed, failed: b.failed, errored: b.errored, skipped: b.skipped,
          rate: pct(b.pass_rate), previousRate: pct(s.previous_buckets[i]?.pass_rate ?? null),
        }));
        const worst = [...s.buckets].sort((a, b) => (b.failed + b.errored) - (a.failed + a.errored))[0];
        const caption = `${number.format(cur.executions)} executions in ${number.format(cur.runs)} runs, pass rate ${formatPassRate(cur.pass_rate)}`
          + (prev ? `, ${formatPassRate(prev.pass_rate)} in the previous period.` : ", no data in the previous period.")
          + (worst && worst.failed + worst.errored > 0
            ? ` Most failures on ${formatPointLabel(worst.date, unit)}: ${number.format(worst.failed + worst.errored)}.` : "");
        return (
          <>
            <ul className="kpi-tiles report-tiles" aria-label="Summary figures">
              <li><DeltaTile title="Runs" value={number.format(cur.runs)} noPrevious={!prev}
                delta={relativeDelta(cur.runs, prev?.runs ?? null, days, "neither")} /></li>
              <li><DeltaTile title="Executions" value={number.format(cur.executions)} noPrevious={!prev}
                delta={relativeDelta(cur.executions, prev?.executions ?? null, days, "neither")} /></li>
              <li><DeltaTile title="Pass rate" value={formatPassRate(cur.pass_rate)} noPrevious={!prev}
                delta={pointsDelta(cur.pass_rate, prev?.pass_rate ?? null, days, "up")} /></li>
              <li><DeltaTile title="Failures" value={number.format(failures)} noPrevious={!prev}
                delta={relativeDelta(failures, prevFailures, days, "down")} /></li>
              <li><DeltaTile title="Failing tests" value={number.format(cur.failing_tests)} noPrevious={!prev}
                delta={relativeDelta(cur.failing_tests, prev?.failing_tests ?? null, days, "down")} /></li>
              <li><DeltaTile title="Average run time" value={formatDuration(cur.avg_run_duration_ms)} noPrevious={!prev}
                delta={relativeDelta(cur.avg_run_duration_ms, prev?.avg_run_duration_ms ?? null, days, "down")} /></li>
            </ul>
            <p className="muted report-note">Pass rate leaves skipped tests out: passed ÷ (executions − skipped).</p>

            <h3 id="summary-chart">Results per {unit}</h3>
            <SeriesLegend series={LEGEND} hidden={hidden} onToggle={toggle} label="Show or hide a series" />
            <figure className="chart-figure" aria-labelledby="summary-chart">
              <figcaption className="sr-only">{caption}</figcaption>
              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={rows} barCategoryGap="20%" accessibilityLayer>
                  <CartesianGrid stroke="var(--grid)" vertical={false} />
                  <XAxis dataKey="date" stroke="var(--text-muted)" tick={axisTick} tickLine={false}
                    tickFormatter={(d: string) => formatTick(d, unit)} minTickGap={16} interval="preserveStartEnd" />
                  <YAxis yAxisId="count" allowDecimals={false} stroke="var(--text-muted)" tick={axisTick} tickLine={false} width={48} />
                  <YAxis yAxisId="rate" orientation="right" domain={[0, 100]} tickFormatter={(v: number) => `${v}%`}
                    stroke="var(--text-muted)" tick={axisTick} tickLine={false} width={44} />
                  <Tooltip {...tooltipStyles} labelFormatter={(d) => formatPointLabel(String(d), unit)} />
                  {STATUS.map((st, i) => (
                    <Bar key={st.key} yAxisId="count" dataKey={st.key} name={st.label} stackId="status" fill={st.paint}
                      hide={hidden.has(st.key)} stroke="var(--surface-1)" strokeWidth={1}
                      radius={i === STATUS.length - 1 ? [4, 4, 0, 0] : undefined} />
                  ))}
                  <Line yAxisId="rate" dataKey="rate" name="Pass rate" stroke="var(--series-1)" strokeWidth={2} hide={hidden.has("rate")}
                    dot={{ r: 2.5, fill: "var(--series-1)", stroke: "var(--surface-1)" }} connectNulls={false} />
                  <Line yAxisId="rate" dataKey="previousRate" name="Pass rate, previous period" stroke="var(--series-2)" strokeWidth={2}
                    strokeDasharray="5 4" hide={hidden.has("previousRate")}
                    dot={{ r: 2.5, fill: "var(--series-2)", stroke: "var(--surface-1)" }} connectNulls={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </figure>
            <DataTableDisclosure name={`results per ${unit}`}>
              <table className="data">
                <caption className="sr-only">Results per {unit}</caption>
                <thead><tr>
                  <th scope="col">{unit === "day" ? "Date" : "Week of"}</th><th scope="col" className="num">Runs</th>
                  <th scope="col" className="num">Executions</th><th scope="col" className="num">Passed</th>
                  <th scope="col" className="num">Failed</th><th scope="col" className="num">Errored</th>
                  <th scope="col" className="num">Skipped</th><th scope="col" className="num">Pass rate</th>
                  <th scope="col" className="num">Previous period</th>
                </tr></thead>
                <tbody>
                  {s.buckets.map((b, i) => (
                    <tr key={b.date}>
                      <td>{formatPointLabel(b.date, unit)}</td><td className="num">{number.format(b.runs)}</td>
                      <td className="num">{number.format(b.executions)}</td><td className="num">{number.format(b.passed)}</td>
                      <td className="num">{number.format(b.failed)}</td><td className="num">{number.format(b.errored)}</td>
                      <td className="num">{number.format(b.skipped)}</td><td className="num">{formatPassRate(b.pass_rate)}</td>
                      <td className="num">{formatPassRate(s.previous_buckets[i]?.pass_rate ?? null)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </DataTableDisclosure>

            <h3>Most failing tests (top 10)</h3>
            {s.top_failing.length === 0 ? <p className="muted">No failures in this period.</p> : (
              <table className="data">
                <caption className="sr-only">Most failing tests</caption>
                <thead><tr><th scope="col">Test</th><th scope="col" className="num hide-narrow">Executions</th>
                  <th scope="col" className="num">Failures</th><th scope="col" className="num">Pass rate</th></tr></thead>
                <tbody>
                  {s.top_failing.map((t) => (
                    <tr key={t.test_key}>
                      <td className="wrap-anywhere">
                        <Link to={history(t.test_key)}>{testLabel(t)}</Link>
                        <NarrowMeta items={[{ label: "Executions", value: number.format(t.executions) }]} />
                      </td>
                      <td className="num hide-narrow">{number.format(t.executions)}</td>
                      <td className="num">{number.format(t.failures)}</td>
                      <td className="num">{formatPassRate(t.pass_rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <h3>Slowest tests (top 10)</h3>
            <table className="data">
              <caption className="sr-only">Slowest tests</caption>
              <thead><tr><th scope="col">Test</th><th scope="col" className="num hide-narrow">Executions</th>
                <th scope="col" className="num">Average duration</th></tr></thead>
              <tbody>
                {s.slowest.map((t) => (
                  <tr key={t.test_key}>
                    <td className="wrap-anywhere">
                      <Link to={history(t.test_key)}>{testLabel(t)}</Link>
                      <NarrowMeta items={[{ label: "Executions", value: number.format(t.executions) }]} />
                    </td>
                    <td className="num hide-narrow">{number.format(t.executions)}</td>
                    <td className="num">{formatDuration(t.avg_duration_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <h3>Branches (top 10)</h3>
            <table className="data">
              <caption className="sr-only">Branches</caption>
              <thead><tr><th scope="col">Branch</th><th scope="col" className="num">Runs</th>
                <th scope="col" className="num hide-narrow">Executions</th><th scope="col" className="num">Failures</th>
                <th scope="col" className="num">Pass rate</th></tr></thead>
              <tbody>
                {s.branches.map((b) => (
                  <tr key={b.branch ?? "(none)"}>
                    <td>
                      {b.branch ?? <span className="muted">no branch</span>}
                      <NarrowMeta items={[{ label: "Executions", value: number.format(b.executions) }]} />
                    </td>
                    <td className="num">{number.format(b.runs)}</td>
                    <td className="num hide-narrow">{number.format(b.executions)}</td>
                    <td className="num">{number.format(b.failures)}</td>
                    <td className="num">{formatPassRate(b.pass_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        );
      }}
    </ReportSection>
  );
}
```

Note: the `kpi-tiles` grid holds 4 columns; six tiles wrap to two rows of 4 + 2. If the ui-ux-pro-max review prefers 3 + 3, add `.report-tiles { grid-template-columns: repeat(3, minmax(0, 1fr)); }` with the same breakpoints.

- [ ] **Step 5: Styles**

Append to `dashboard/src/index.css` near the `.kpi-sub` rules:

```css
/* Report delta tiles: the colour follows the verdict, not the direction (failures up is worse) */
.kpi-sub.delta-better { color: var(--passed-text); }
.kpi-sub.delta-worse { color: var(--danger-text); }
.kpi-sub .delta-verdict { font-weight: 600; }
.report-section h3 { margin: var(--space-5) 0 var(--space-2); font-size: 15px; }
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd dashboard && npx vitest run src/pages/report && npm run lint && npm run typecheck`
Expected: PASS. If the average-run-time tile reads another duration format, read `formatDuration(734000)` in `api/analytics.ts` and fix the expected text in the test, not the component.

- [ ] **Step 7: Commit**

```bash
git add dashboard/src/pages/report/DeltaTile.tsx dashboard/src/pages/report/sections/SummarySection.tsx dashboard/src/pages/report/sections/SummarySection.test.tsx dashboard/src/pages/report/testFixtures.ts dashboard/src/index.css
git commit -m "feat(dashboard): report summary section with delta tiles, previous-period line and CSVs" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard/src/pages/report/DeltaTile.tsx dashboard/src/pages/report/sections/SummarySection.tsx dashboard/src/pages/report/sections/SummarySection.test.tsx dashboard/src/pages/report/testFixtures.ts dashboard/src/index.css
```

---

### Task 13: The filter bar (`ReportFilterBar`, `describeFilters`)

Invoke the `ui-ux-pro-max` skill before writing the component or editing `index.css` / `FilterChips.tsx`.

**Files:**
- Create: `dashboard/src/pages/report/describeFilters.ts`
- Create: `dashboard/src/pages/report/ReportFilterBar.tsx`
- Test: `dashboard/src/pages/report/ReportFilterBar.test.tsx`
- Modify: `dashboard/src/components/FilterChips.tsx` (optional `title` on an applied chip)
- Modify: `dashboard/src/index.css`

**Interfaces:**
- Consumes: Tasks 8–11 (`CaseAreas`, `CI_LABELS`, `AREA_KINDS`, `AREA_NAMES`, `formatArea`, `folderCounts`, `ReportFilters`, `FilterKey`, `ALL_BRANCHES`, `PRESETS`, `addDays`, `spanDays`, `MAX_SPAN_DAYS`, `MAX_AGE_DAYS`, `caseAreasMessage`), `FilterChips`, `revealFilters`, `FilterSelect`, `FolderSelect`, `ErrorBanner`.
- Produces:
  - `describeFilters.ts`: `LINKED_ONLY = "Only automated tests linked to a case are counted"`, `describeFilters(f: ReportFilters, defaultBranch: string | null, areas?: CaseAreas): AppliedFilter[]`, `formatPeriod(from: string, to: string): string` ("9 Sep – 8 Oct 2026").
  - `AppliedFilter` gains `title?: string` (FilterChips renders it as the chip's `title`).
  - `ReportFilterBar(props: { filters; update; clearAll; today: string; defaultBranch: string | null; caseAreas: { data?: CaseAreas; error: unknown; isPending: boolean; refetch: () => unknown }; runUrls: { error: unknown; refetch: () => unknown }; facets?: { branches: string[]; environments: string[] }; onFormOpen: () => void })`.

- [ ] **Step 1: Write the failing tests**

```tsx
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import type { CaseAreas } from "../../api/cases";
import { ApiError } from "../../api/http";
import ReportFilterBar from "./ReportFilterBar";
import { describeFilters, formatPeriod } from "./describeFilters";
import { parseReportFilters, todayIn, useReportFilters } from "./useReportFilters";

const AREAS: CaseAreas = {
  generatedAt: "v1", counts: { cases: 2, linked: 2, manual: 0 },
  folders: ["features/booking"], features: ["Booking", "Payments"], labels: ["smoke"], suites: [{ id: 12, name: "Regression" }],
  cases: [
    { number: 1, title: "a", testKey: "a".repeat(64), folder: "features/booking", feature: "Booking", labels: ["smoke"], suiteIds: [12] },
    { number: 2, title: "b", testKey: "b".repeat(64), folder: "features/booking", feature: "Payments", labels: [], suiteIds: [] },
  ],
};
const ok = { data: AREAS, error: null, isPending: false, refetch: vi.fn() };

type AreasProp = { data?: CaseAreas; error: unknown; isPending: boolean; refetch: () => unknown };

function Harness({ caseAreas = ok, runUrlsError = null }: { caseAreas?: AreasProp; runUrlsError?: unknown }) {
  const { filters, update, clearAll } = useReportFilters("UTC");
  const location = useLocation();
  return (
    <>
      <ReportFilterBar filters={filters} update={update} clearAll={clearAll} today={todayIn("UTC")} defaultBranch="main"
        caseAreas={caseAreas} runUrls={{ error: runUrlsError, refetch: vi.fn() }}
        facets={{ branches: ["main", "release/2.4"], environments: ["staging"] }} onFormOpen={vi.fn()} />
      <output data-testid="search">{location.search}</output>
    </>
  );
}

function renderAt(search = "", props: Parameters<typeof Harness>[0] = {}) {
  render(
    <MemoryRouter initialEntries={[`/projects/42/report${search}`]}>
      <Routes><Route path="/projects/:projectId/report" element={<Harness {...props} />} /></Routes>
    </MemoryRouter>,
  );
}
const search = () => screen.getByTestId("search").textContent;

test("period chips; Custom opens the form at From", async () => {
  renderAt();
  const chips = screen.getByRole("group", { name: "Quick filters" });
  expect(within(chips).getByRole("button", { name: "30 days" })).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(within(chips).getByRole("button", { name: "7 days" }));
  expect(search()).toBe("?period=7");
  await userEvent.click(within(chips).getByRole("button", { name: "7 days" }));  // pressing the pressed preset keeps it
  expect(search()).toBe("?period=7");
  await userEvent.click(within(chips).getByRole("button", { name: "Custom…" }));
  expect(screen.getByLabelText("From")).toHaveFocus();
});

test("the default branch is a chip; removing it means every branch, and removing that returns to the default", async () => {
  renderAt();
  await userEvent.click(screen.getByRole("button", { name: "Remove filter Branch: main (default)" }));
  expect(search()).toBe("?branch=*");
  await userEvent.click(screen.getByRole("button", { name: "Remove filter Branch: all branches" }));
  expect(search()).toBe("");
});

test("applied chips name each filter; removing one moves focus to the next chip", async () => {
  renderAt("?env=staging&ci=jenkins&origin=qeos&area=feature:Booking&suite=12");
  for (const name of ["Environment: staging", "CI: Jenkins", "Origin: Requested from QEOS", "Feature: Booking", "Suite: Regression"]) {
    expect(screen.getByText(name)).toBeInTheDocument();
  }
  expect(screen.getByText("Feature: Booking").closest(".fchip")).toHaveAttribute("title", "Only automated tests linked to a case are counted");
  await userEvent.click(screen.getByRole("button", { name: "Remove filter Environment: staging" }));
  expect(search()).not.toContain("env=");
  expect(screen.getByRole("button", { name: "Remove filter CI: Jenkins" })).toHaveFocus();
});

test("Clear all keeps the period", async () => {
  renderAt("?period=90&env=staging");
  await userEvent.click(screen.getByRole("button", { name: "Clear all" }));
  expect(search()).toBe("?period=90");
});

test("the area is chosen in two steps, by keyboard", async () => {
  renderAt();
  await userEvent.click(screen.getByRole("button", { name: "+ Filter" }));
  await userEvent.selectOptions(screen.getByLabelText("Area"), "feature");
  await userEvent.selectOptions(screen.getByLabelText("Feature"), "Payments");
  expect(search()).toBe("?area=feature%3APayments");
  await userEvent.selectOptions(screen.getByLabelText("Area"), "folder");
  expect(search()).toBe("");                                           // a new kind clears the old value
  expect(screen.getByRole("button", { name: /folder/i })).toBeInTheDocument();  // FolderSelect's trigger
});

test("a custom range is checked before it is applied", async () => {
  renderAt();
  await userEvent.click(screen.getByRole("button", { name: "+ Filter" }));
  const today = todayIn("UTC");
  await userEvent.type(screen.getByLabelText("From"), today);
  await userEvent.type(screen.getByLabelText("To"), "2020-01-01");
  await userEvent.click(screen.getByRole("button", { name: "Apply" }));
  expect(screen.getByRole("alert")).toHaveTextContent("From must be on or before To");
  expect(search()).toBe("");
});

test("case-areas failing disables area and suite with Retry; a run-urls failure shows on the origin filter", async () => {
  renderAt("?origin=ci", { caseAreas: { data: undefined, error: new ApiError(409, "x", "too_many_cases"), isPending: false, refetch: vi.fn() },
    runUrlsError: new ApiError(500, "down") });
  await userEvent.click(screen.getByRole("button", { name: "+ Filter" }));
  expect(screen.getByLabelText("Area")).toBeDisabled();
  expect(screen.getByText("This project has more cases than the report can join (50,000)")).toBeInTheDocument();
  expect(screen.getByText(/play requests could not be loaded/i)).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Retry" })).toHaveLength(2);
});

test("describeFilters and formatPeriod", () => {
  const f = parseReportFilters(new URLSearchParams("branch=*&ci=github_actions"), "2026-10-08").filters;
  expect(describeFilters(f, "main").map((a) => `${a.name}: ${a.value}`)).toEqual(["Branch: all branches", "CI: GitHub Actions"]);
  expect(formatPeriod("2026-09-09", "2026-10-08")).toBe("9 Sep – 8 Oct 2026");
  expect(formatPeriod("2025-12-20", "2026-01-05")).toBe("20 Dec 2025 – 5 Jan 2026");
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd dashboard && npx vitest run src/pages/report/ReportFilterBar.test.tsx`
Expected: FAIL (modules missing).

- [ ] **Step 3: Let an applied chip carry a title**

In `components/FilterChips.tsx`: add `title?: string;` to `AppliedFilter` (with the comment `/** A tooltip on the chip, e.g. what the filter leaves out */`) and render it: `<span key={f.key} className="fchip fchip-applied" title={f.title}>`. No other change.

- [ ] **Step 4: Write `describeFilters.ts`**

```ts
import type { AppliedFilter } from "../../components/FilterChips";
import type { CaseAreas } from "../../api/cases";
import { CI_LABELS } from "../../lib/ciProviders";
import { AREA_NAMES } from "../../lib/reportScope";
import { ALL_BRANCHES, type ReportFilters } from "./useReportFilters";

export const LINKED_ONLY = "Only automated tests linked to a case are counted";

/** Every filter in force, as people name it: the chips, the subtitle and the print header all read this. */
export function describeFilters(f: ReportFilters, defaultBranch: string | null, areas?: CaseAreas): AppliedFilter[] {
  const out: AppliedFilter[] = [];
  if (f.branch === ALL_BRANCHES) out.push({ key: "branch", name: "Branch", value: "all branches" });
  else if (f.branch) out.push({ key: "branch", name: "Branch", value: f.branch });
  else if (defaultBranch) out.push({ key: "branch", name: "Branch", value: `${defaultBranch} (default)` });
  if (f.environment) out.push({ key: "env", name: "Environment", value: f.environment });
  if (f.ci) out.push({ key: "ci", name: "CI", value: CI_LABELS[f.ci] ?? f.ci });
  if (f.origin !== "any") out.push({ key: "origin", name: "Origin", value: f.origin === "ci" ? "CI" : "Requested from QEOS" });
  if (f.area) out.push({ key: "area", name: AREA_NAMES[f.area.kind], value: f.area.value, title: LINKED_ONLY });
  if (f.suite !== null) {
    const name = areas?.suites.find((s) => s.id === f.suite)?.name ?? `#${f.suite}`;
    out.push({ key: "suite", name: "Suite", value: name, title: LINKED_ONLY });
  }
  return out;
}

// Fixed names: Intl's en-GB says "Sept" in newer ICU, and the period must read the same everywhere
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "9 Sep – 8 Oct 2026"; the year is repeated only when the range crosses one. These are calendar days (YYYY-MM-DD). */
export function formatPeriod(from: string, to: string): string {
  const [fy, fm, fd] = from.split("-").map(Number);
  const [ty, tm, td] = to.split("-").map(Number);
  const left = `${fd} ${MONTHS[fm - 1]}${fy === ty ? "" : ` ${fy}`}`;
  return `${left} – ${td} ${MONTHS[tm - 1]} ${ty}`;
}
```

- [ ] **Step 5: Write `ReportFilterBar.tsx`**

```tsx
import { type FormEvent, useEffect, useId, useRef, useState } from "react";
import { ChevronRight } from "lucide-react";
import type { CaseAreas } from "../../api/cases";
import ErrorBanner from "../../components/ErrorBanner";
import FilterChips, { type QuickChip, revealFilters } from "../../components/FilterChips";
import FilterSelect from "../../components/FilterSelect";
import FolderSelect from "../../components/FolderSelect";
import { CI_LABELS } from "../../lib/ciProviders";
import { AREA_KINDS, AREA_NAMES, type AreaKind, folderCounts, formatArea } from "../../lib/reportScope";
import { LINKED_ONLY, describeFilters, formatPeriod } from "./describeFilters";
import {
  ALL_BRANCHES, type FilterKey, MAX_AGE_DAYS, MAX_SPAN_DAYS, PRESETS, type ReportFilters, addDays, spanDays,
} from "./useReportFilters";
import { caseAreasMessage } from "./useReportRequest";

type Patch = Partial<Record<FilterKey, string>>;
const ORIGIN_HELP = "Requested from QEOS: runs started with Play, matched by their GitHub run. A Play whose run was never "
  + "matched counts as CI, and runs outside GitHub Actions are always CI.";

interface Props {
  filters: ReportFilters;
  update: (patch: Patch) => void;
  clearAll: () => void;
  today: string;
  defaultBranch: string | null;
  caseAreas: { data?: CaseAreas; error: unknown; isPending: boolean; refetch: () => unknown };
  runUrls: { error: unknown; refetch: () => unknown };
  /** The period's busiest values (summary.facets), offered in the branch and environment lists */
  facets?: { branches: string[]; environments: string[] };
  /** The first opening of the form loads case-areas (spec: Requests per phase) */
  onFormOpen: () => void;
}

/** One row above the sections (spec: Filter bar): period chips, a chip per filter in force, "+ Filter" and
 *  "Clear all"; the form sits in a disclosure that "+ Filter" opens. */
export default function ReportFilterBar({ filters, update, clearAll, today, defaultBranch, caseAreas, runUrls, facets, onFormOpen }: Props) {
  const uid = useId();
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const fromRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState({ from: "", to: "", branch: "", allBranches: false, environment: "" });
  const [rangeError, setRangeError] = useState<string | null>(null);
  const [areaKind, setAreaKind] = useState<AreaKind | "">(filters.area?.kind ?? "");
  const areas = caseAreas.data;

  // The drafts follow the URL (Back, a chip removed, a pasted link)
  useEffect(() => {
    setDraft({
      from: filters.preset === null ? filters.from : "", to: filters.preset === null ? filters.to : "",
      branch: filters.branch === ALL_BRANCHES ? "" : filters.branch, allBranches: filters.branch === ALL_BRANCHES,
      environment: filters.environment,
    });
  }, [filters.preset, filters.from, filters.to, filters.branch, filters.environment]);
  // A filter in the URL picks its kind; clearing the value keeps the chosen kind, so the second step stays open
  useEffect(() => {
    if (filters.area) setAreaKind(filters.area.kind);
  }, [filters.area]);

  const custom = filters.preset === null;
  const quick: QuickChip[] = [
    ...PRESETS.map((p) => ({ key: "period", value: p, label: `${p} days` })),
    { key: "period", value: "custom", label: custom ? `Custom: ${formatPeriod(filters.from, filters.to)}` : "Custom…" },
  ];
  const applied = describeFilters(filters, defaultBranch, areas);
  const active = applied.filter((a) => !(a.key === "branch" && filters.branch === "")).length;

  function openForm(focusFrom: boolean) {
    revealFilters(detailsRef.current);
    if (focusFrom) fromRef.current?.focus();
  }

  function onChipChange(patch: Record<string, string>) {
    if ("period" in patch) {
      if (patch.period === "custom") openForm(true);
      else if (patch.period) update({ period: patch.period });
      // "" (the pressed preset pressed again): a period is always set, so nothing changes
      return;
    }
    if ("branch" in patch && patch.branch === "") {
      // The default branch's chip goes to every branch; every other branch chip goes back to the default
      update({ branch: filters.branch === "" ? ALL_BRANCHES : "" });
      return;
    }
    update(patch as Patch);
  }

  function apply(e: FormEvent) {
    e.preventDefault();
    const patch: Patch = {
      branch: draft.allBranches ? ALL_BRANCHES : draft.branch.trim(),
      env: draft.environment.trim(),
    };
    if (draft.from || draft.to) {
      const problem = !draft.from || !draft.to ? "Give both From and To"
        : draft.from > draft.to ? "From must be on or before To"
        : spanDays(draft.from, draft.to) > MAX_SPAN_DAYS ? `The period can be at most ${MAX_SPAN_DAYS} days`
        : draft.to > today ? "To cannot be after today"
        : draft.from < addDays(today, -MAX_AGE_DAYS) ? `From can be at most ${MAX_AGE_DAYS} days ago`
        : null;
      if (problem) {
        setRangeError(problem);
        return;
      }
      patch.from = draft.from;
      patch.to = draft.to;
    }
    setRangeError(null);
    update(patch);
  }

  const areaValue = (kind: AreaKind) => (filters.area?.kind === kind ? filters.area.value : "");
  const setArea = (kind: AreaKind, value: string) => update({ area: value ? formatArea({ kind, value }) : "" });

  return (
    <div className="report-filter-bar no-print">
      <FilterChips
        quick={quick}
        values={{ period: filters.preset ?? "custom" }}
        applied={applied}
        onChange={onChipChange}
        onClearAll={clearAll}
        onAddFilter={() => openForm(false)}
      />
      <details
        ref={detailsRef}
        className="more-filters"
        open={open}
        onToggle={(e) => {
          const now = (e.currentTarget as HTMLDetailsElement).open;
          setOpen(now);
          if (now) onFormOpen();
        }}
      >
        <summary><ChevronRight size={14} aria-hidden="true" className="chevron" /> Filters{active > 0 && ` (${active} active)`}</summary>
        <form className="filters report-filter-form" onSubmit={apply}>
          <label>From
            <input ref={fromRef} type="date" value={draft.from} min={addDays(today, -MAX_AGE_DAYS)} max={today}
              onChange={(e) => setDraft((d) => ({ ...d, from: e.target.value }))} />
          </label>
          <label>To
            <input type="date" value={draft.to} min={addDays(today, -MAX_AGE_DAYS)} max={today}
              onChange={(e) => setDraft((d) => ({ ...d, to: e.target.value }))} />
          </label>
          <label>Branch
            <input list={`${uid}-branches`} value={draft.branch} maxLength={255} disabled={draft.allBranches}
              placeholder={defaultBranch ? `${defaultBranch} (default)` : ""}
              onChange={(e) => setDraft((d) => ({ ...d, branch: e.target.value }))} />
          </label>
          <datalist id={`${uid}-branches`}>{facets?.branches.map((b) => <option key={b} value={b} />)}</datalist>
          <label className="check-label">
            <input type="checkbox" checked={draft.allBranches} onChange={(e) => setDraft((d) => ({ ...d, allBranches: e.target.checked }))} />
            All branches
          </label>
          <label>Environment
            <input list={`${uid}-envs`} value={draft.environment} maxLength={100}
              onChange={(e) => setDraft((d) => ({ ...d, environment: e.target.value }))} />
          </label>
          <datalist id={`${uid}-envs`}>{facets?.environments.map((v) => <option key={v} value={v} />)}</datalist>
          <button type="submit" className="primary">Apply</button>
          {rangeError && <p className="field-error" role="alert">{rangeError}</p>}

          <FilterSelect label="CI provider" value={filters.ci} onChange={(v) => update({ ci: v })}
            options={Object.entries(CI_LABELS).map(([value, label]) => ({ value, label }))} />
          <label>Origin
            <select value={filters.origin} onChange={(e) => update({ origin: e.target.value === "any" ? "" : e.target.value })}>
              <option value="any">Any</option>
              <option value="ci">CI</option>
              <option value="qeos">Requested from QEOS</option>
            </select>
          </label>
          <p className="muted filter-help">{ORIGIN_HELP}</p>
          {filters.origin !== "any" && runUrls.error != null && (
            <div><p>Play requests could not be loaded</p><ErrorBanner error={runUrls.error} onRetry={() => void runUrls.refetch()} /></div>
          )}

          <label>Area
            <select value={areaKind} disabled={!areas}
              onChange={(e) => {
                setAreaKind(e.target.value as AreaKind | "");
                if (filters.area) update({ area: "" });
              }}>
              <option value="">Any</option>
              {AREA_KINDS.map((k) => <option key={k} value={k}>{AREA_NAMES[k]}</option>)}
            </select>
          </label>
          {areas && areaKind === "feature" && (
            <FilterSelect label="Feature" value={areaValue("feature")} onChange={(v) => setArea("feature", v)}
              options={areas.features.map((f) => ({ value: f, label: f }))} />
          )}
          {areas && areaKind === "label" && (
            <FilterSelect label="Label" value={areaValue("label")} onChange={(v) => setArea("label", v)}
              options={areas.labels.map((l) => ({ value: l, label: l }))} />
          )}
          {areas && areaKind === "folder" && (
            <FolderSelect folders={folderCounts(areas)} value={areaValue("folder")} onChange={(p) => setArea("folder", p)} />
          )}
          {areas ? (
            <FilterSelect label="Suite" value={filters.suite === null ? "" : String(filters.suite)} onChange={(v) => update({ suite: v })}
              options={areas.suites.map((s) => ({ value: String(s.id), label: s.name }))} />
          ) : (
            <label>Suite<select disabled value=""><option value="">Any</option></select></label>
          )}
          {caseAreas.isPending && !caseAreas.error && <p className="muted filter-help">Loading areas and suites…</p>}
          {caseAreas.error != null && (
            <div><p>{caseAreasMessage(caseAreas.error)}</p><ErrorBanner error={caseAreas.error} onRetry={() => void caseAreas.refetch()} /></div>
          )}
          <p className="muted filter-help">{LINKED_ONLY}; the Coverage section counts the tests without a case.</p>
        </form>
      </details>
    </div>
  );
}
```

Note: when the gate is "wait" for a branch the form shows nothing different. When the area kind select is not yet chosen but a filter is in the URL, `areaKind` follows `filters.area?.kind`. When `caseAreas.isPending` is true but the query is disabled (form never opened, no area filter) React Query reports `isPending: true` with `fetchStatus: "idle"`; the page passes `isPending: caseAreas.isFetching` instead (Task 14) so "Loading areas and suites…" only shows while it loads.

- [ ] **Step 6: Styles**

Append to `dashboard/src/index.css`:

```css
.report-filter-bar { margin: 0 0 var(--space-4); }
.report-filter-form { align-items: flex-end; }
.report-filter-form .filter-help { flex: 1 1 100%; margin: 0; font-size: 12.5px; }
.report-filter-form .field-error { flex: 1 1 100%; margin: 0; color: var(--danger-text); }
.report-filter-form .check-label { flex-direction: row; align-items: center; gap: var(--space-2); }
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd dashboard && npx vitest run src/pages/report src/components/FilterChips.test.tsx && npm run lint && npm run typecheck`
Expected: PASS. If the "+ Filter" label in `FilterChips` is not "+ Filter", use the label it has.

- [ ] **Step 8: Commit**

```bash
git add dashboard/src/pages/report/describeFilters.ts dashboard/src/pages/report/ReportFilterBar.tsx dashboard/src/pages/report/ReportFilterBar.test.tsx dashboard/src/components/FilterChips.tsx dashboard/src/index.css
git commit -m "feat(dashboard): report filter bar: period chips, applied chips, two-step area, origin" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard/src/pages/report/describeFilters.ts dashboard/src/pages/report/ReportFilterBar.tsx dashboard/src/pages/report/ReportFilterBar.test.tsx dashboard/src/components/FilterChips.tsx dashboard/src/index.css
```

---

### Task 14: The new Report page: assembly, P1 Flaky section, print header, live region

Invoke the `ui-ux-pro-max` skill before writing the page or editing `index.css`.

**Files:**
- Create: `dashboard/src/pages/report/ReportPage.tsx`, `dashboard/src/pages/report/ReportPage.test.tsx`
- Create: `dashboard/src/pages/report/PrintHeader.tsx`
- Create: `dashboard/src/pages/report/sections/FlakySection.tsx`
- Delete: `dashboard/src/pages/ReportPage.tsx`, `dashboard/src/pages/ReportPage.test.tsx` (`git rm`)
- Modify: `dashboard/src/App.tsx` (`import ReportPage from "./pages/report/ReportPage";`)
- Modify: `dashboard/src/index.css` (print rules)

**Interfaces:**
- Consumes: Tasks 8–13; `getProject` (`api/orgs.ts`), `getFlaky`, `ChartPatternDefs`.
- Produces:
  - `PrintHeader({ filters: ReportFilters; tz: string; applied: AppliedFilter[]; generatedAt: string | null })`.
  - `FlakySection({ projectId: number; gate: Gate; filters: ReportFilters; branch: string | null; today: string })` (removed in Task 23).
  - `useAnnouncement(signature: string | null, busy: boolean): string` (exported from `ReportPage.tsx`).
  - `ReportPage` default export (route `report` unchanged).

- [ ] **Step 1: Write the failing page tests**

`dashboard/src/pages/report/ReportPage.test.tsx`:

```tsx
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { delay, http, HttpResponse } from "msw";
import { server } from "../../test/server";
import { setAccessToken } from "../../auth/tokens";
import type { ReportRequest } from "../../api/report";
import { SUMMARY_REPORT } from "./testFixtures";
import { addDays, todayIn } from "./useReportFilters";
import ReportPage from "./ReportPage";

const P = "/api/v1/projects/42";
const TZ = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
let bodies: ReportRequest[] = [];
/** Phase 2 and 3 add a request per section; the summary's are the ones these tests read. */
const summaryBodies = () => bodies.filter((b) => b.sections[0] === "summary");

function serve(over: { report?: (body: ReportRequest) => Response | Promise<Response> } = {}) {
  bodies = [];
  server.use(
    http.get(P, () => HttpResponse.json({ id: 42, name: "Web Shop", organization_id: 1, my_role: "viewer" })),
    http.get(`${P}/repositories`, () => HttpResponse.json([{ id: 1, default_branch: "main" }])),
    http.post(`${P}/analytics/report`, async ({ request }) => {
      const body = (await request.json()) as ReportRequest;
      bodies.push(body);
      return over.report ? over.report(body) : HttpResponse.json(SUMMARY_REPORT);
    }),
    http.get(`${P}/analytics/flaky`, () => HttpResponse.json([{ test_key: "c".repeat(64), suite: "checkout", class_name: "Cart",
      name: "coupon", reason: "flips", commits: [], flips: 4, flip_rate: 0.4, runs: 10, last_status: "passed", last_seen: "2026-10-05T10:00:00Z" }])),
    http.get(`${P}/case-areas`, () => HttpResponse.json({ generated_at: "v1", counts: { cases: 1, linked: 1, manual: 0 },
      folders: [], features: ["Booking"], labels: [], suites: [],
      cases: [{ n: 1, t: "Book", k: "c".repeat(64), fo: null, fe: 0, l: [], s: [] }] })),
    http.get(`${P}/run-requests/run-urls`, () => HttpResponse.json({ urls: ["https://github.com/a/b/actions/runs/7"], truncated: false })),
  );
}

function renderPage(search = "") {
  setAccessToken("acc");
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/projects/42/report${search}`]}>
        <Routes><Route path="/projects/:projectId/report" element={<ReportPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("the summary is asked for the last 30 days on the default branch, in the reader's zone", async () => {
  serve();
  renderPage();
  expect(await screen.findByRole("heading", { level: 1, name: "Report" })).toBeInTheDocument();
  expect(await screen.findByRole("group", { name: /^Pass rate 97\.8%/ })).toBeInTheDocument();
  const today = todayIn(TZ);
  expect(summaryBodies()[0]).toEqual({ from: addDays(today, -29), to: today, tz: TZ, branch: "main", environment: null, ci_provider: null,
    origin: "any", requested_run_urls: null, test_keys: null, sections: ["summary"], bucket: "auto" });
  expect(screen.getByText(/web shop: quality report/i)).toBeInTheDocument();
  expect(within(screen.getByRole("group", { name: "Quick filters" })).getByText("Branch: main (default)")).toBeInTheDocument();
});

test("an area filter sends the linked keys; one with no linked tests sends nothing", async () => {
  serve();
  renderPage("?area=feature:Booking");
  await screen.findByRole("group", { name: /^Pass rate/ });
  expect(summaryBodies()[0].test_keys).toEqual(["c".repeat(64)]);
  expect(within(screen.getByRole("region", { name: /flaky tests/i })).getByText(/coupon/)).toBeInTheDocument();
});

test("an area with no linked tests never calls the report", async () => {
  serve();
  renderPage("?area=feature:Nothing");
  expect(await screen.findAllByText("No automated tests are linked to cases in this area")).not.toHaveLength(0);
  expect(bodies).toHaveLength(0);
});

test("origin sends the Play URLs", async () => {
  serve();
  renderPage("?origin=qeos");
  await screen.findByRole("group", { name: /^Pass rate/ });
  expect(summaryBodies()[0]).toMatchObject({ origin: "qeos", requested_run_urls: ["https://github.com/a/b/actions/runs/7"] });
});

test("a timeout and a 422 show in the section, with Retry and Reset filters", async () => {
  serve({ report: () => HttpResponse.json({ detail: { code: "report_timeout",
    message: "This report took too long. Narrow the period or the filters." } }, { status: 503 }) });
  renderPage();
  const summary = await screen.findByRole("region", { name: "Summary" });
  expect(await within(summary).findByText(/this report took too long/i)).toBeInTheDocument();
  expect(within(summary).getByRole("button", { name: "Retry" })).toBeInTheDocument();
});

test("a link with invalid filters shows the notice and asks without them", async () => {
  serve();
  renderPage("?ci=travis");
  expect(await screen.findByText("Some filters in the link were not valid and were removed")).toBeInTheDocument();
  await screen.findByRole("group", { name: /^Pass rate/ });
  expect(bodies.every((b) => b.ci_provider === null)).toBe(true);
});

test("a filter change mid-load never shows the old answer and is announced once", async () => {
  serve({
    report: async (body) => {
      if (body.branch === "main") {
        await delay(300);
        return HttpResponse.json({ ...SUMMARY_REPORT, summary: { ...SUMMARY_REPORT.summary!, current: { ...SUMMARY_REPORT.summary!.current, runs: 111 } } });
      }
      return HttpResponse.json({ ...SUMMARY_REPORT, summary: { ...SUMMARY_REPORT.summary!, current: { ...SUMMARY_REPORT.summary!.current, runs: 222 } } });
    },
  });
  renderPage();
  await userEvent.click(await screen.findByRole("button", { name: "Remove filter Branch: main (default)" }));
  expect(await screen.findByRole("group", { name: /^Runs 222/ })).toBeInTheDocument();
  await delay(400);
  expect(screen.queryByRole("group", { name: /^Runs 111/ })).not.toBeInTheDocument();
  expect(screen.getByText("Report updated")).toBeInTheDocument();
  expect(summaryBodies().map((b) => b.branch)).toEqual(["main", null]);
});

test("print: Save as PDF prints; the print header lists the period and every filter; data tables open", async () => {
  serve();
  const print = vi.spyOn(window, "print").mockImplementation(() => {});
  renderPage("?env=staging");
  await screen.findByRole("group", { name: /^Pass rate/ });
  await userEvent.click(screen.getByRole("button", { name: /save as pdf/i }));
  expect(print).toHaveBeenCalled();
  const header = document.querySelector(".report-print-header")!;
  expect(header).toHaveTextContent("Branch: main (default)");
  expect(header).toHaveTextContent("Environment: staging");
  expect(header).toHaveTextContent(/compared with/i);
  window.dispatchEvent(new Event("beforeprint"));
  document.querySelectorAll("details.chart-data").forEach((d) => expect(d).toHaveAttribute("open"));
  window.dispatchEvent(new Event("afterprint"));
  document.querySelectorAll("details.chart-data").forEach((d) => expect(d).not.toHaveAttribute("open"));
  print.mockRestore();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd dashboard && npx vitest run src/pages/report/ReportPage.test.tsx`
Expected: FAIL (module missing).

- [ ] **Step 3: Write `PrintHeader.tsx`**

```tsx
import type { AppliedFilter } from "../../components/FilterChips";
import { formatPeriod } from "./describeFilters";
import { type ReportFilters, addDays } from "./useReportFilters";

/** Printed under the title only (spec: Print / Save as PDF): the period and zone, every filter, the period the
 *  deltas compare with, and when the report was generated. */
export default function PrintHeader({ filters, tz, applied, generatedAt }: {
  filters: ReportFilters;
  tz: string;
  applied: AppliedFilter[];
  generatedAt: string | null;
}) {
  const previousFrom = addDays(filters.from, -filters.days);
  const previousTo = addDays(filters.from, -1);
  return (
    <div className="print-only report-print-header">
      <p><strong>Period:</strong> {formatPeriod(filters.from, filters.to)} ({filters.days} days), {tz}</p>
      <p><strong>Compared with:</strong> {formatPeriod(previousFrom, previousTo)}</p>
      {applied.length === 0
        ? <p><strong>Filters:</strong> none</p>
        : <ul>{applied.map((f) => <li key={f.key}>{f.name}: {f.value}</li>)}</ul>}
      <p><strong>Generated:</strong> {new Date(generatedAt ?? Date.now()).toLocaleString()}</p>
    </div>
  );
}
```

- [ ] **Step 4: Write `sections/FlakySection.tsx`**

```tsx
import { useQuery } from "@tanstack/react-query";
import { formatPassRate, getFlaky } from "../../../api/analytics";
import { testLabel } from "../../../api/report";
import ErrorBanner from "../../../components/ErrorBanner";
import { SkeletonStatus } from "../../../components/Skeleton";
import { type ReportFilters, spanDays } from "../useReportFilters";
import { type Gate, REPORT_STALE_MS } from "../useReportRequest";

const number = new Intl.NumberFormat();
// The Flaky page's defaults, so the report and that page agree
const FLAKY_MIN_RUNS = 5;
const FLAKY_MIN_FLIP_RATE = 0.3;
const TOP = 10;

/** Phase 1 keeps the Flaky table (spec: Section 1, "Flaky tests in P1"). /flaky only knows "the last N days" and a
 *  branch, so a custom range is read up to today (plan Ruling 6), and area or suite keys filter its rows here. */
export default function FlakySection({ projectId, gate, filters, branch, today }: {
  projectId: number;
  gate: Gate;
  filters: ReportFilters;
  branch: string | null;
  today: string;
}) {
  const windowDays = Math.min(90, spanDays(filters.from, today));
  const flaky = useQuery({
    queryKey: ["report-flaky", projectId, windowDays, branch],
    queryFn: () => getFlaky(projectId, { windowDays, minRuns: FLAKY_MIN_RUNS, minFlipRate: FLAKY_MIN_FLIP_RATE, branch: branch ?? undefined }),
    enabled: gate.state === "ready",
    staleTime: REPORT_STALE_MS,
    retry: false,
  });
  const keys = gate.state === "ready" && gate.base.test_keys ? new Set(gate.base.test_keys) : null;
  const rows = (flaky.data ?? []).filter((r) => !keys || keys.has(r.test_key.toLowerCase())).slice(0, TOP);

  let body;
  if (gate.state === "blocked") body = <p className="muted">{gate.message}</p>;
  else if (flaky.error != null) body = <ErrorBanner error={flaky.error} onRetry={() => void flaky.refetch()} />;
  else if (gate.state === "wait" || flaky.isPending) {
    body = <SkeletonStatus label="Loading flaky tests…"><span className="skeleton skeleton-block" style={{ height: 160 }} aria-hidden="true" /></SkeletonStatus>;
  } else if (rows.length === 0) body = <p className="muted">No flaky tests in this period.</p>;
  else {
    body = (
      <table className="data">
        <caption className="sr-only">Flaky tests</caption>
        <thead><tr><th scope="col">Test</th><th scope="col" className="num">Runs</th><th scope="col">Why flaky</th></tr></thead>
        <tbody>
          {rows.map((f) => (
            <tr key={f.test_key}>
              <td className="wrap-anywhere">{testLabel(f)}</td>
              <td className="num">{number.format(f.runs)}</td>
              <td>{f.reason === "same_commit"
                ? `Passed and failed on the same commit (${f.commits.length})`
                : `Flipped ${f.flips ?? 0} times (${formatPassRate(f.flip_rate)} of runs)`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }
  return (
    <section className="card report-section" aria-labelledby="report-flaky">
      <div className="report-section-head"><h2 id="report-flaky">Flaky tests</h2></div>
      <p className="muted report-note">
        Covers the last {windowDays} days. Environment, CI provider and origin filters do not apply here.
      </p>
      {body}
    </section>
  );
}
```

- [ ] **Step 5: Write `ReportPage.tsx`**

```tsx
import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Printer, RefreshCw, X } from "lucide-react";
import { getProject } from "../../api/orgs";
import { ChartPatternDefs } from "../../components/ChartKit";
import PageHeader from "../../components/PageHeader";
import PrintHeader from "./PrintHeader";
import ReportFilterBar from "./ReportFilterBar";
import { describeFilters, formatPeriod } from "./describeFilters";
import FlakySection from "./sections/FlakySection";
import SummarySection from "./sections/SummarySection";
import { todayIn, useReportFilters } from "./useReportFilters";
import { useReportRequest, useReportSection } from "./useReportRequest";

/** "Report updated", once, when every section asked after a filter change has settled (spec: Filter bar). The first
 *  load is not announced. */
export function useAnnouncement(signature: string | null, busy: boolean): string {
  const [message, setMessage] = useState("");
  const last = useRef<string | null>(null);
  const waiting = useRef(false);
  useEffect(() => {
    if (signature === null) return;
    if (last.current !== null && last.current !== signature) {
      waiting.current = true;
      setMessage("");
    }
    last.current = signature;
  }, [signature]);
  useEffect(() => {
    if (waiting.current && !busy) {
      waiting.current = false;
      setMessage("Report updated");
    }
  }, [busy, signature]);
  return message;
}

/** Keeps every chart's data table open on paper (spec: Print / Save as PDF). */
function usePrintOpensDataTables() {
  useEffect(() => {
    const opened: HTMLDetailsElement[] = [];
    const before = () => {
      document.querySelectorAll<HTMLDetailsElement>(".report details.chart-data:not([open])").forEach((d) => {
        d.open = true;
        opened.push(d);
      });
    };
    const after = () => opened.splice(0).forEach((d) => { d.open = false; });
    window.addEventListener("beforeprint", before);
    window.addEventListener("afterprint", after);
    return () => {
      window.removeEventListener("beforeprint", before);
      window.removeEventListener("afterprint", after);
    };
  }, []);
}

export default function ReportPage() {
  const { projectId } = useParams();
  const id = Number(projectId);
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const today = todayIn(tz);
  const qc = useQueryClient();
  const { filters, update, clearAll, notice, dismissNotice } = useReportFilters(tz);
  const [formOpened, setFormOpened] = useState(false);
  const project = useQuery({ queryKey: ["project", id], queryFn: () => getProject(id) });
  const { gate, caseAreas, runUrls, defaultBranch, effectiveBranch } = useReportRequest(id, filters, tz, { loadCaseAreas: formOpened });
  const summary = useReportSection(id, gate, "summary");
  usePrintOpensDataTables();

  const busy = summary.fetchStatus === "fetching";
  const announcement = useAnnouncement(gate.state === "ready" ? JSON.stringify(gate.key) : null, busy);
  const applied = describeFilters(filters, defaultBranch, caseAreas.data);
  const generated = summary.data?.generated_at ?? null;
  const subtitle = `${project.data?.name ?? "Project"}: quality report. ${formatPeriod(filters.from, filters.to)} (${filters.days} days), ${tz}.`
    + (generated ? ` Generated ${new Date(generated).toLocaleString()}.` : "")
    + (applied.length ? ` ${applied.map((f) => `${f.name}: ${f.value}`).join("; ")}.` : "");

  function refresh() {
    for (const key of [["report", id], ["report-flaky", id], ["case-areas", id], ["run-urls", id]]) {
      void qc.invalidateQueries({ queryKey: key });
    }
  }

  return (
    <div className="report">
      <ChartPatternDefs />
      <PageHeader
        title="Report"
        subtitle={subtitle}
        actions={
          <div className="report-actions no-print">
            <button type="button" onClick={refresh}><RefreshCw size={15} aria-hidden="true" /> Refresh</button>
            <button type="button" onClick={() => window.print()}><Printer size={15} aria-hidden="true" /> Save as PDF</button>
          </div>
        }
      />
      <PrintHeader filters={filters} tz={tz} applied={applied} generatedAt={generated} />
      {notice && (
        <div className="report-notice no-print" role="status">
          <span>Some filters in the link were not valid and were removed</span>
          <button type="button" className="ghost" aria-label="Dismiss the notice" onClick={dismissNotice}><X size={14} aria-hidden="true" /></button>
        </div>
      )}
      <ReportFilterBar
        filters={filters} update={update} clearAll={clearAll} today={today} defaultBranch={defaultBranch}
        caseAreas={{ data: caseAreas.data, error: caseAreas.error, isPending: caseAreas.isFetching, refetch: caseAreas.refetch }}
        runUrls={{ error: runUrls.error, refetch: runUrls.refetch }}
        facets={summary.data?.summary?.facets}
        onFormOpen={() => setFormOpened(true)}
      />
      <p className="sr-only" role="status" aria-live="polite">{announcement}</p>
      <SummarySection projectId={id} gate={gate} query={summary} branch={effectiveBranch} environment={filters.environment}
        onClearFilters={clearAll} onTry={update} />
      <FlakySection projectId={id} gate={gate} filters={filters} branch={effectiveBranch} today={today} />
    </div>
  );
}
```

Delete the old page and test, and point the route at the new one:

```bash
git rm dashboard/src/pages/ReportPage.tsx dashboard/src/pages/ReportPage.test.tsx
```

In `dashboard/src/App.tsx`: `import ReportPage from "./pages/report/ReportPage";` (the `<Route path="report" ...>` line is unchanged).

- [ ] **Step 6: Print styles**

In `dashboard/src/index.css`, add outside `@media print`:

```css
.print-only { display: none; }
.report-notice { display: flex; gap: var(--space-3); align-items: center; justify-content: space-between; border: 1px solid var(--border-strong); border-radius: var(--radius-sm); padding: var(--space-2) var(--space-3); margin: 0 0 var(--space-3); background: var(--surface-2); }
```

and inside the existing `@media print { ... }` block:

```css
  .print-only { display: block !important; }
  .report-print-header { margin: 0 0 12px; font-size: 12px; }
  .report-print-header ul { margin: 4px 0; padding-left: 18px; }
  .report-section figure, .report-section table.data thead { break-inside: avoid; }
  table.data thead { display: table-header-group; }
```

- [ ] **Step 7: Run the page tests, then the whole dashboard check**

Run: `cd dashboard && npx vitest run src/pages/report src/pageHeadings.test.tsx`
Expected: PASS (the h1 renders while every API call fails).
Run: `cd dashboard && npm run lint && npm run typecheck && npx vitest run --maxWorkers=4 && npm run build`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add dashboard/src/pages/report/ReportPage.tsx dashboard/src/pages/report/ReportPage.test.tsx dashboard/src/pages/report/PrintHeader.tsx dashboard/src/pages/report/sections/FlakySection.tsx dashboard/src/App.tsx dashboard/src/index.css
git commit -m "feat(dashboard): Report page with URL filters, summary, print header and live region" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard/src/pages/report/ReportPage.tsx dashboard/src/pages/report/ReportPage.test.tsx dashboard/src/pages/report/PrintHeader.tsx dashboard/src/pages/report/sections/FlakySection.tsx dashboard/src/App.tsx dashboard/src/index.css dashboard/src/pages/ReportPage.tsx dashboard/src/pages/ReportPage.test.tsx
```

---

### Task 15: Phase 1 docs (ADR-026, READMEs, DESIGN.md, TODO) and the phase gate

**Files:**
- Create: `docs/architecture/adr/ADR-026-report-joins-in-the-dashboard.md`
- Modify: `docs/architecture/adr/INDEX.md` (row after ADR-025)
- Modify: `platforms/ingestion-service/README.md` (Analytics: the report endpoint)
- Modify: `platforms/test-management-service/README.md` (API table: two rows)
- Modify: `DESIGN.md` (Components: "Report Filter Bar", "Delta Tiles", "Print Header")
- Modify: `TODO.md` (the stored origin marker)

**Interfaces:** documentation only; no code.

- [ ] **Step 1: Write ADR-026**

```markdown
# ADR-026: The report joins in the dashboard; run origin is matched by CI run URL

Status: Accepted (2026-10-08) · Spec: `docs/superpowers/specs/2026-10-08-report-deep-analysis-design.md`

## Context
The Report page needs filters that live in two services: branch, environment, CI provider and run
data in ingestion; Gherkin features, folders, labels and suites in test-management. ADR-022 says
services never call each other. People also want to tell runs started from QEOS (Play, ADR-025)
from ordinary CI runs, and no upload carries that fact.

## Decision
- **The dashboard joins.** Test-management serves every active case once, dictionary-encoded
  (`GET /case-areas`, 409 above 50,000 cases). The dashboard turns an area or suite filter into
  test keys and sends them to ingestion's one report endpoint (`POST /analytics/report`, at most
  20,000 keys, one array parameter on PostgreSQL). In phase 3 the dashboard also groups
  ingestion's per-test rows by area.
- **Origin is matched by URL.** A run is "requested from QEOS" when `ci_provider = github_actions`
  and `lower(ci_run_url)` is one of the Play requests' `github_run_url`s
  (`GET /run-requests/run-urls`). Every other run is CI. Shards and re-run attempts share the URL,
  so they count as the same Play.
- **Known limits:** a Play whose GitHub run was never matched counts as CI; runs outside GitHub
  Actions are always CI.
- **The report's default branch** is the first repository's default branch (project-service), else
  `main`; `branch=*` in the URL means every branch.
- Only `case-areas` and `analytics/report` are gzipped at the gateway (BREACH).

## Alternatives rejected
- **A stored origin marker** (a Play workflow input, a collector field, an ingestion column and a
  backfill). Worth it only if the URL match proves unreliable; listed in TODO.md.
- **Inferring origin from `ci_provider`.** A Play run is an ordinary `github_actions` run.
- **Ingestion calling test-management for areas.** Breaks ADR-022 and couples the services' uptime.

## Consequences
- Up to 1.4 MB request bodies on the report; within the gateway's 10 MB cap.
- The report's area filters only see automated tests linked to a case; the Coverage section (phase
  3) counts the others.
```

Add to `INDEX.md` after the ADR-025 row:

```markdown
| [ADR-026](ADR-026-report-joins-in-the-dashboard.md) | The report joins in the dashboard (case-areas + test keys); run origin is matched by CI run URL |
```

- [ ] **Step 2: READMEs**

In `platforms/ingestion-service/README.md`, under `## Analytics`, after the endpoint table, add a `### Report` subsection:

```markdown
### Report

`POST /api/v1/projects/{project_id}/analytics/report`, every project role. One request per section; the
dashboard sends them in parallel. Body (`extra` fields are a 422):

| Field | Rule |
|---|---|
| `from`, `to` | ISO dates in `tz`; `from` ≤ `to`; at most 90 days; `to` ≤ today + 1; `from` ≥ today − 400 days |
| `tz` | IANA zone, default `UTC` |
| `branch`, `environment` | exact match; empty means no filter (≤ 255 / ≤ 100 characters) |
| `ci_provider` | one of the upload's providers |
| `origin`, `requested_run_urls` | `any` (default), `ci` or `qeos`; the URLs (≤ 5,000, from test-management's `run-urls`) are required with `ci`/`qeos`; a run is `qeos` when it is GitHub Actions and its `ci_run_url` matches one, case-insensitively (ADR-026) |
| `test_keys` | optional, 1–20,000 keys (64 hex); runs then count only when they have a result for one |
| `sections` | 1–5 of `summary`, `failure_causes`, `regressions`, `tests`, `duration` |
| `bucket` | `auto` (day up to 31 days, else Monday weeks), `day`, `week` |

The response carries `period`, `previous_period` (the same number of days just before), `tz`, `bucket`,
`generated_at`, `scope` and the asked sections. `summary`: current and previous totals (`previous` is null
without runs), buckets and `previous_buckets` (the previous period aligned bucket by bucket), the 10 most
failing and slowest tests, the 10 busiest branches, and facets (the period's 50 busiest branches,
environments and CI providers, ignoring the other filters). Each request runs under a 20 s statement
timeout; a timeout is 503 `{"detail": {"code": "report_timeout", ...}}`. Nothing is cached server-side.
```

In `platforms/test-management-service/README.md`, add to the API table:

```markdown
| `GET` | `/case-areas` | every active case for the report's joins (ADR-026): `{generated_at, counts{cases, linked, manual}, folders, features, labels, suites[{id, name}], cases[{n, t, k, fo, fe, l, s}]}`; the four dictionaries are sorted and cases point into them by index (`fo`/`fe` null when absent); folder is the directory part of `source_path`; 409 `too_many_cases` above 50,000 cases; every project role |
| `GET` | `/run-requests/run-urls?since=` | `{urls, truncated}`: the non-null `github_run_url` of requests made since `since` (ISO datetime, at most 500 days back), newest first, at most 5,000; every project role |
```

- [ ] **Step 3: DESIGN.md**

Add after "### Filter Chips" (keep the house style: short, concrete):

```markdown
### Report Filter Bar
The Report page's filters live in the URL (`period` or `from`/`to`, `branch`, `env`, `ci`, `origin`, `area=kind:value`, `suite`), so a report can be bookmarked and shared and Back undoes a change. One row of `FilterChips`: the period presets (7, 30, 90 days, and "Custom…", which reads "Custom: 9 Sep – 8 Oct 2026" when pressed), a chip per filter in force, "+ Filter" and "Clear all" (which keeps the period). The branch starts on the project's default branch and shows it ("Branch: main (default)"); removing that chip means every branch ("Branch: all branches"). The form is a disclosure, closed until "+ Filter" opens it: dates and text fields apply with Apply; selects apply at once. Area is two steps (Feature, Folder or Label, then the value: a searchable `FilterSelect`, or `FolderSelect` for folders). Area and suite chips carry a tooltip: only automated tests linked to a case are counted. A link with invalid parameters loses them and says so in a dismissible notice. A polite live region says "Report updated" once the sections asked after a change have settled.

### Delta Tiles
The Report's KPI tiles (`DeltaTile`) are KPI Tiles with a change against the previous period of the same length: a lucide arrow (or a dash) and the words ("up 1.2 pts vs previous 30 days"), then the verdict "better" or "worse" in 600 weight. The colour follows the verdict, not the direction: Passed Text for better, Danger Text for worse, Graphite for neutral metrics (runs, executions). Pass rate moves in points, counts and durations in percent. The tile's accessible name is the whole sentence. Without previous data the sub-line says "No data in the previous period".

### Print Header
A `.print-only` block under the Report's title: the period with its days and time zone, the period the deltas compare with, every filter as "Name: value", and when the report was generated. On paper the filter bar and every button are hidden (`.no-print`), each chart and table header avoids a page break, table headers repeat, and every "Show data table" disclosure opens on `beforeprint` and closes again after.
```

- [ ] **Step 4: TODO.md**

Add under the most fitting heading (or at the end):

```markdown
- [ ] Report origin marker (ADR-026 fallback): a Play workflow input → collector field → ingestion `test_runs.origin` column and a backfill. Only if the URL match proves unreliable.
```

- [ ] **Step 5: Phase gate: every suite and the CI-mirroring checks**

Run:

```bash
cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest -q
cd ../test-management-service && SECRET_KEY=test .venv/Scripts/python -m pytest -q
cd ../../dashboard && npm run lint && npm run typecheck && npx vitest run --maxWorkers=4 && npm run build
node --test ../templates/github/qeos-run.test.mjs
```

Expected: all green. The gateway smoke (Task 7) runs in CI's "Gateway and full stack" job; run it locally too if Docker is available.

- [ ] **Step 6: Commit**

```bash
git add docs/architecture/adr/ADR-026-report-joins-in-the-dashboard.md docs/architecture/adr/INDEX.md platforms/ingestion-service/README.md platforms/test-management-service/README.md DESIGN.md TODO.md
git commit -m "docs: report filters and summary (ADR-026, READMEs, DESIGN.md)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- docs/architecture/adr/ADR-026-report-joins-in-the-dashboard.md docs/architecture/adr/INDEX.md platforms/ingestion-service/README.md platforms/test-management-service/README.md DESIGN.md TODO.md
```

Phase 1 ships here (the user pushes; the pre-push hook mirrors `ci.yml`).

---

# Phase 2: failure causes, regressions and stability

### Task 16: Migration 016: partial index on failing results

**Files:**
- Create: `platforms/ingestion-service/alembic/versions/016_report_indexes.py`
- Modify: `platforms/ingestion-service/src/ingestion/models/run.py` (declare the index on `RunResult`)
- Modify: `platforms/ingestion-service/tests/unit/test_migration.py` (append)
- Modify: `scripts/smoke_gateway.sh` (PostgreSQL check that the index is partial)

**Interfaces:**
- Produces: index `ix_test_results_failing` on `test_results (run_id, test_key) WHERE status IN ('failed','errored')`, which Tasks 18 and 20 read through.

- [ ] **Step 1: Write the failing tests** (append to `tests/unit/test_migration.py`)

```python
def test_failing_results_index_is_partial(migrated_engine):
    """Migration 016: failure causes and regression candidates read only failing rows (spec: Indexes)."""
    columns = {ix["name"]: ix["column_names"] for ix in inspect(migrated_engine).get_indexes("test_results")}
    assert columns["ix_test_results_failing"] == ["run_id", "test_key"]
    with migrated_engine.connect() as conn:
        sql = conn.execute(text("SELECT sql FROM sqlite_master WHERE name = 'ix_test_results_failing'")).scalar()
    assert "WHERE" in sql.upper() and "'failed'" in sql and "'errored'" in sql


def test_model_declares_the_failing_index():
    assert "ix_test_results_failing" in {ix.name for ix in Base.metadata.tables["test_results"].indexes}


def test_failing_index_downgrade_drops_it(tmp_path):
    url = f"sqlite:///{(tmp_path / 'downgrade_016.db').as_posix()}"
    cfg = Config()
    cfg.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "015")
    engine = create_engine(url)
    try:
        assert "ix_test_results_failing" not in {ix["name"] for ix in inspect(engine).get_indexes("test_results")}
    finally:
        engine.dispose()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/unit/test_migration.py -q`
Expected: FAIL with `KeyError: 'ix_test_results_failing'`.

- [ ] **Step 3: Write the migration and declare the index**

`platforms/ingestion-service/alembic/versions/016_report_indexes.py`:

```python
"""partial index on failing results, for the report's failure causes and regressions

Failure causes and the regression candidates read only failed and errored rows: a few percent of
test_results, reached until now only by filtering every result of every run. The index covers only
those rows, so it stays small. On PostgreSQL it is built CONCURRENTLY, so uploads are not blocked on a
large table; CONCURRENTLY cannot run inside a transaction, hence the autocommit block.

Revision ID: 016
Revises: 015
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None

NAME = "ix_test_results_failing"
FAILING = "status IN ('failed','errored')"


def _postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    where = {"postgresql_where": sa.text(FAILING), "sqlite_where": sa.text(FAILING)}
    if _postgres():
        with op.get_context().autocommit_block():
            op.create_index(NAME, "test_results", ["run_id", "test_key"], postgresql_concurrently=True, **where)
    else:
        op.create_index(NAME, "test_results", ["run_id", "test_key"], **where)


def downgrade() -> None:
    if _postgres():
        with op.get_context().autocommit_block():
            op.drop_index(NAME, table_name="test_results", postgresql_concurrently=True)
    else:
        op.drop_index(NAME, table_name="test_results")
```

In `src/ingestion/models/run.py`: add `text` to the sqlalchemy import and extend `RunResult.__table_args__`:

```python
    __table_args__ = (
        CheckConstraint("status IN ('passed','failed','skipped','errored')", name="chk_test_results_status"),
        Index("ix_test_results_test_key_run", "test_key", "run_id"),
        # Migration 016: the report reads only failing rows for causes and regression candidates
        Index("ix_test_results_failing", "run_id", "test_key",
              postgresql_where=text("status IN ('failed','errored')"),
              sqlite_where=text("status IN ('failed','errored')")),
    )
```

- [ ] **Step 4: Add the PostgreSQL check to the smoke script**

In `scripts/smoke_gateway.sh`, after the report checks added in Task 7:

```bash
INDEXDEF="$(docker compose exec -T postgres psql -U postgres -d ingestion_db -tAc \
  "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_test_results_failing'" | tr -d '\r')"
case "$INDEXDEF" in
  *WHERE*failed*errored*) pass "ix_test_results_failing is partial on PostgreSQL" ;;
  *) fail "ix_test_results_failing missing or not partial: $INDEXDEF" ;;
esac
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest -q`
Expected: PASS (the whole suite: `create_all` now builds the partial index on SQLite too).

- [ ] **Step 6: Commit**

```bash
git add platforms/ingestion-service/alembic/versions/016_report_indexes.py platforms/ingestion-service/src/ingestion/models/run.py platforms/ingestion-service/tests/unit/test_migration.py scripts/smoke_gateway.sh
git commit -m "feat(ingestion): migration 016, a partial index on failing results for the report" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- platforms/ingestion-service/alembic/versions/016_report_indexes.py platforms/ingestion-service/src/ingestion/models/run.py platforms/ingestion-service/tests/unit/test_migration.py scripts/smoke_gateway.sh
```

---

### Task 17: Percentiles and failure-cause grouping (pure)

**Files:**
- Create: `platforms/ingestion-service/src/ingestion/analytics/report_stats.py`, `tests/unit/test_report_stats.py`
- Create: `platforms/ingestion-service/src/ingestion/analytics/report_causes.py`, `tests/unit/test_report_causes.py`

**Interfaces:**
- Consumes: `iso` (Task 1), `NONE` from `analytics/signature.py`.
- Produces:
  - `report_stats.percentile(values: Sequence[int], p: float) -> Optional[int]` (linear interpolation between closest ranks), `report_stats.mean(values: Sequence[int]) -> Optional[int]`.
  - `report_causes.Occurrence(signature, headline, test_key, suite, class_name, name, status, run_id, started_at, current: bool, quarantined: bool, bucket: Optional[int])`, `group_causes(occurrences: Iterable[Occurrence], bucket_count: int) -> dict` (the spec's `failure_causes` JSON), constants `MAX_GROUPS = 50`, `MAX_TOP_TESTS = 10`, `MAX_RESOLVED = 20`.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_report_stats.py`:

```python
from src.ingestion.analytics.report_stats import mean, percentile


def test_percentiles_interpolate_between_ranks():
    values = [40, 10, 30, 20]
    assert percentile(values, 0.5) == 25
    assert percentile(values, 0.9) == 37
    assert percentile([7], 0.9) == 7
    assert percentile([], 0.5) is None


def test_mean_rounds_to_whole_milliseconds():
    assert mean([100, 200, 400]) == 233
    assert mean([]) is None
```

`tests/unit/test_report_causes.py`:

```python
"""Failure causes over a period (spec: Section failure_causes)."""
from datetime import datetime, timezone

from src.ingestion.analytics import report_causes
from src.ingestion.analytics.report_causes import Occurrence, group_causes


def occ(sig, *, day=2, test="t1", run=1, status="failed", current=True, quarantined=False, bucket=None, headline=None):
    started = datetime(2026, 10 if current else 9, day, 10, tzinfo=timezone.utc)
    return Occurrence(sig, headline or f"{sig} headline", f"key-{test}", "s", "C", test, status, run, started, current,
                      quarantined, bucket if bucket is not None else (day - 1 if current else None))


def test_new_recurring_and_resolved():
    out = group_causes([
        occ("aaa", current=False, day=25, run=1),
        occ("aaa", day=2, run=5), occ("aaa", day=3, run=6, test="t2"),
        occ("bbb", day=4, run=7, status="errored"),
        occ("gone", current=False, day=26, run=2),
    ], bucket_count=7)
    groups = {g["signature"]: g for g in out["groups"]}
    assert out["failures"] == 3 and out["groups_total"] == 2
    assert groups["aaa"]["status"] == "recurring" and groups["aaa"]["previous_occurrences"] == 1
    assert groups["aaa"]["first_seen"] == "2026-09-25T10:00:00Z" and groups["aaa"]["first_seen_run_id"] == 1
    assert groups["aaa"]["last_seen"] == "2026-10-03T10:00:00Z" and groups["aaa"]["last_seen_run_id"] == 6
    assert (groups["aaa"]["tests"], groups["aaa"]["runs"]) == (2, 2)
    assert groups["aaa"]["buckets"] == [0, 1, 1, 0, 0, 0, 0]
    assert groups["bbb"]["status"] == "new" and (groups["bbb"]["failed"], groups["bbb"]["errored"]) == (0, 1)
    assert out["resolved"] == [{"signature": "gone", "headline": "gone headline", "previous_occurrences": 1,
                                "last_seen": "2026-09-26T10:00:00Z"}]


def test_order_is_occurrences_then_newer_last_seen_then_signature_and_none_last():
    out = group_causes([
        occ("zzz", day=3, run=3), occ("none", day=3, run=3), occ("mmm", day=2, run=2),
        occ("big", day=1, run=1), occ("big", day=1, run=1),
    ], bucket_count=7)
    assert [g["signature"] for g in out["groups"]] == ["big", "zzz", "none", "mmm"]


def test_the_cap_and_other(monkeypatch):
    monkeypatch.setattr(report_causes, "MAX_GROUPS", 2)
    out = group_causes([occ("a"), occ("a"), occ("a"), occ("b"), occ("b"), occ("c"), occ("d")], bucket_count=7)
    assert [g["signature"] for g in out["groups"]] == ["a", "b"]
    assert out["other"] == {"groups": 2, "occurrences": 2}
    assert out["groups_total"] == 4 and out["failures"] == 7


def test_top_tests_and_quarantine():
    out = group_causes([occ("a", test="t1", run=1), occ("a", test="t2", run=1, quarantined=True), occ("a", test="t2", run=2, day=3)],
                       bucket_count=7)
    group = out["groups"][0]
    assert group["quarantined"] == 1
    assert [(t["name"], t["occurrences"], t["last_run_id"]) for t in group["top_tests"]] == [("t2", 2, 2), ("t1", 1, 1)]


def test_nothing_failed():
    assert group_causes([], bucket_count=7) == {"failures": 0, "groups_total": 0, "groups": [],
                                                "other": {"groups": 0, "occurrences": 0}, "resolved": []}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/unit/test_report_stats.py tests/unit/test_report_causes.py -q`
Expected: FAIL (modules missing).

- [ ] **Step 3: Write `report_stats.py`**

```python
"""Statistics over whole milliseconds, in Python: the report needs a few thousand values at most, and SQLite (the
tests) has no percentile_cont. Pure."""
from typing import Optional, Sequence


def percentile(values: Sequence[int], p: float) -> Optional[int]:
    """Linear interpolation between the closest ranks (numpy's default method); None without values."""
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * p
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return round(ordered[low] + (ordered[high] - ordered[low]) * (rank - low))


def mean(values: Sequence[int]) -> Optional[int]:
    return round(sum(values) / len(values)) if values else None
```

- [ ] **Step 4: Write `report_causes.py`**

```python
"""Failure causes over a period (spec: Section failure_causes): the run view's signature groups
(analytics/signature.py, unchanged) extended from one run to a period, against the previous period. Pure."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, Optional

from src.ingestion.analytics.report_period import iso
from src.ingestion.analytics.signature import NONE

MAX_GROUPS = 50
MAX_TOP_TESTS = 10
MAX_RESOLVED = 20


@dataclass(frozen=True)
class Occurrence:
    """One failing result (failed or errored) of an in-scope run."""
    signature: str
    headline: Optional[str]
    test_key: str
    suite: str
    class_name: str
    name: str
    status: str
    run_id: int
    started_at: datetime
    current: bool              # in the period; False: in the previous period
    quarantined: bool          # the test is muted: shown and counted, flagged
    bucket: Optional[int]      # index into the period's buckets; None in the previous period


def group_causes(occurrences: Iterable[Occurrence], bucket_count: int) -> dict:
    ordered = sorted(occurrences, key=lambda o: (o.started_at, o.run_id))
    first: Dict[str, Occurrence] = {}
    previous: Dict[str, int] = defaultdict(int)
    previous_last: Dict[str, datetime] = {}
    previous_headline: Dict[str, Optional[str]] = {}
    groups: Dict[str, dict] = {}
    for o in ordered:
        first.setdefault(o.signature, o)
        if not o.current:
            previous[o.signature] += 1
            previous_last[o.signature] = o.started_at
            previous_headline.setdefault(o.signature, o.headline)
            continue
        g = groups.get(o.signature)
        if g is None:
            g = groups[o.signature] = {
                "signature": o.signature, "headline": o.headline, "occurrences": 0, "failed": 0, "errored": 0,
                "quarantined": 0, "buckets": [0] * bucket_count, "_tests": {}, "_runs": set(), "_last": o,
            }
        g["occurrences"] += 1
        g[o.status] += 1
        g["quarantined"] += int(o.quarantined)
        g["_runs"].add(o.run_id)
        g["_last"] = o
        if o.bucket is not None:
            g["buckets"][o.bucket] += 1
        test = g["_tests"].setdefault(o.test_key, {"test_key": o.test_key, "suite": o.suite, "class_name": o.class_name,
                                                   "name": o.name, "occurrences": 0, "last_run_id": o.run_id})
        test["occurrences"] += 1
        test["last_run_id"] = o.run_id

    rows = []
    for signature, g in groups.items():
        seen_first, last = first[signature], g.pop("_last")
        tests, runs = g.pop("_tests"), g.pop("_runs")
        g.update({
            "tests": len(tests), "runs": len(runs),
            "status": "recurring" if previous.get(signature) else "new",
            "previous_occurrences": previous.get(signature, 0),
            "first_seen": iso(seen_first.started_at), "first_seen_run_id": seen_first.run_id,
            "last_seen": iso(last.started_at), "last_seen_run_id": last.run_id,
            "top_tests": sorted(tests.values(), key=lambda t: (-t["occurrences"], t["test_key"]))[:MAX_TOP_TESTS],
        })
        rows.append((last.started_at, g))
    # Biggest first; ties to the newer last_seen, then the signature, with "none" last among equals
    rows.sort(key=lambda pair: (-pair[1]["occurrences"], -pair[0].timestamp(), pair[1]["signature"] == NONE,
                                pair[1]["signature"]))
    ordered_groups = [g for _, g in rows]
    kept, rest = ordered_groups[:MAX_GROUPS], ordered_groups[MAX_GROUPS:]
    resolved = sorted(
        ({"signature": s, "headline": previous_headline[s], "previous_occurrences": n, "last_seen": iso(previous_last[s])}
         for s, n in previous.items() if s not in groups),
        key=lambda r: (-r["previous_occurrences"], r["signature"]),
    )
    return {
        "failures": sum(g["occurrences"] for g in ordered_groups),
        "groups_total": len(ordered_groups),
        "groups": kept,
        "other": {"groups": len(rest), "occurrences": sum(g["occurrences"] for g in rest)},
        "resolved": resolved[:MAX_RESOLVED],
    }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/unit/test_report_stats.py tests/unit/test_report_causes.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add platforms/ingestion-service/src/ingestion/analytics/report_stats.py platforms/ingestion-service/src/ingestion/analytics/report_causes.py platforms/ingestion-service/tests/unit/test_report_stats.py platforms/ingestion-service/tests/unit/test_report_causes.py
git commit -m "feat(ingestion): report percentiles and failure-cause grouping over a period" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- platforms/ingestion-service/src/ingestion/analytics/report_stats.py platforms/ingestion-service/src/ingestion/analytics/report_causes.py platforms/ingestion-service/tests/unit/test_report_stats.py platforms/ingestion-service/tests/unit/test_report_causes.py
```

---

### Task 18: Section `failure_causes`

**Files:**
- Modify: `platforms/ingestion-service/src/ingestion/service/report_service.py`
- Test: `platforms/ingestion-service/tests/integration/test_report_causes.py`

**Interfaces:**
- Consumes: Tasks 2–4 (`in_list`, `key_filter`, `Context`, `SECTION_BUILDERS`, `FAILING`), Task 17 (`Occurrence`, `group_causes`), `signature`, `headline`, `analytics_service.muted_keys`.
- Produces: `MESSAGE_PREFIX = 2000`; `failure_causes(db, scope, runs, context) -> dict` registered as `SECTION_BUILDERS["failure_causes"]`.

- [ ] **Step 1: Write the failing tests**

```python
"""Section failure_causes (spec: Section failure_causes (P2))."""
from datetime import datetime, timezone

import pytest

from src.ingestion.analytics.signature import signature
from src.ingestion.models import MutedTest
from conftest import post_report, report_key

TIMEOUT = "TimeoutError: locator('#pay') after {} ms"


def at(month, day):
    return datetime(2026, month, day, 10, tzinfo=timezone.utc)


@pytest.fixture
def seeded(project_role, report_now, seed_run):
    project_role()
    seed_run(at(9, 25), results=(("t1", "failed", 1, TIMEOUT.format(3000)), ("t5", "failed", 1, "Gone: old cause 1")))
    seed_run(at(10, 2), results=(("t1", "failed", 1, TIMEOUT.format(5000)), ("t2", "failed", 1, "AssertionError: expected 3 got 4"),
                                 ("t3", "errored", 1, None)))
    seed_run(at(10, 5), results=(("t1", "failed", 1, TIMEOUT.format(4000)), ("t2", "passed", 1)))


def causes(client, auth, **body):
    response = post_report(client, auth, sections=["failure_causes"], **body)
    assert response.status_code == 200, response.text
    return response.json()["failure_causes"]


def test_groups_new_recurring_resolved(client, auth, seeded):
    c = causes(client, auth)
    assert c["failures"] == 4 and c["groups_total"] == 3
    timeout, assertion, none = c["groups"]
    assert timeout["signature"] == signature(TIMEOUT.format(1)) and timeout["occurrences"] == 2
    assert (timeout["status"], timeout["previous_occurrences"], timeout["first_seen"]) == ("recurring", 1, "2026-09-25T10:00:00Z")
    assert (timeout["tests"], timeout["runs"]) == (1, 2)
    assert timeout["buckets"] == [0, 1, 0, 0, 1, 0, 0]
    assert timeout["top_tests"][0]["name"] == "t1" and timeout["top_tests"][0]["occurrences"] == 2
    assert assertion["status"] == "new" and assertion["headline"] == "AssertionError: expected 3 got 4"
    assert none["signature"] == "none" and none["errored"] == 1          # a tie with the assertion: none sorts last
    assert [r["headline"] for r in c["resolved"]] == ["Gone: old cause 1"]


def test_quarantined_occurrences_still_count(client, auth, seeded, db):
    db.add(MutedTest(project_id=1, test_key=report_key("t1"), muted_by_user_id=1))
    db.commit()
    timeout = causes(client, auth)["groups"][0]
    assert (timeout["occurrences"], timeout["quarantined"]) == (2, 2)


def test_filters_apply(client, auth, seeded):
    c = causes(client, auth, test_keys=[report_key("t2")])
    assert [g["headline"] for g in c["groups"]] == ["AssertionError: expected 3 got 4"] and c["resolved"] == []
    assert causes(client, auth, branch="dev") == {"failures": 0, "groups_total": 0, "groups": [],
                                                  "other": {"groups": 0, "occurrences": 0}, "resolved": []}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/integration/test_report_causes.py -q`
Expected: FAIL (`failure_causes` is `null`).

- [ ] **Step 3: Implement**

Append to `report_service.py` (imports: `from src.ingestion.analytics.report_causes import Occurrence, group_causes`, `from src.ingestion.analytics.signature import headline, signature`, `from src.ingestion.service.analytics_service import muted_keys`):

```python
MESSAGE_PREFIX = 2000  # only the first line names a cause; this bounds memory on long stack traces


def _bucket_of(scope: Scope, context: Context, run: ScopedRun) -> Optional[int]:
    if not run.current:
        return None
    return bucket_index(local_day(run.started_at, scope.period.zone), context.starts, context.bucket)


def failure_causes(db: Session, scope: Scope, runs: List[ScopedRun], context: Context) -> dict:
    """The failing rows of the in-scope runs of both periods (through ix_test_results_failing), grouped by
    signature in Python, as the run view does."""
    by_id = {r.id: r for r in runs if r.id in context.counted}
    if not by_id:
        return group_causes([], len(context.starts))
    rows = db.execute(
        select(RunResult.run_id, RunResult.test_key, RunResult.suite, RunResult.class_name, RunResult.name,
               RunResult.status, func.substr(RunResult.message, 1, MESSAGE_PREFIX))
        .where(in_list(db, RunResult.run_id, list(by_id), Integer), RunResult.status.in_(FAILING),
               *key_filter(db, scope))
    ).all()
    muted = {key.lower() for key in muted_keys(db, scope.project_id)}
    occurrences = []
    for run_id, key, suite, class_name, name, status, message in rows:
        run = by_id[run_id]
        occurrences.append(Occurrence(signature(message), headline(message), key, suite, class_name, name, status,
                                      run_id, run.started_at, run.current, key.lower() in muted,
                                      _bucket_of(scope, context, run)))
    return group_causes(occurrences, len(context.starts))


SECTION_BUILDERS["failure_causes"] = failure_causes
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/integration/test_report_causes.py tests/integration/test_report_summary.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add platforms/ingestion-service/src/ingestion/service/report_service.py platforms/ingestion-service/tests/integration/test_report_causes.py
git commit -m "feat(ingestion): report failure causes: new, recurring and resolved over the period" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- platforms/ingestion-service/src/ingestion/service/report_service.py platforms/ingestion-service/tests/integration/test_report_causes.py
```

---

### Task 19: Outcome streaks and flips (pure)

**Files:**
- Create: `platforms/ingestion-service/src/ingestion/analytics/report_streaks.py`
- Test: `platforms/ingestion-service/tests/unit/test_report_streaks.py`

**Interfaces:**
- Consumes: Task 17 (`percentile`, `mean`).
- Produces:
  - `Outcome(test_key: str, branch: Optional[str], run_id: int, started_at: datetime, passed: bool, headline: Optional[str])`.
  - `build_sequences(outcomes) -> dict[(test_key, branch), list[Outcome]]` (each ordered by `(started_at, run_id)`).
  - `classify_streaks(sequences, period_start: datetime, previous_start: datetime) -> {"newly_failing": [...], "fixed": [...], "longest_failing": [...], "time_to_fix": {...}}` (full, uncapped lists of dicts with `datetime` values; the service names, caps and serialises them).
  - `flips_by_bucket(sequences, period_start, bucket_of: Callable[[datetime], Optional[int]], bucket_count: int) -> tuple[list[int], list[set[str]]]`.

- [ ] **Step 1: Write the failing tests**

```python
"""Outcome sequences per (test, branch) (spec: Section regressions; plan Ruling 9 for list orders)."""
from datetime import datetime, timedelta, timezone

from src.ingestion.analytics.report_streaks import Outcome, build_sequences, classify_streaks, flips_by_bucket

PREVIOUS_START = datetime(2026, 9, 24, tzinfo=timezone.utc)
PERIOD_START = datetime(2026, 10, 1, tzinfo=timezone.utc)
DAY = 86_400_000


def o(test, day, passed, run=None, branch="main", month=10, headline=None):
    started = datetime(2026, month, day, 10, tzinfo=timezone.utc)
    return Outcome(test, branch, run or month * 100 + day, started, passed, None if passed else (headline or f"{test} broke"))


def classify(*outcomes):
    return classify_streaks(build_sequences(outcomes), PERIOD_START, PREVIOUS_START)


def test_newly_failing_after_a_pass_in_the_previous_period():
    out = classify(o("t1", 25, True, month=9), o("t1", 2, False), o("t1", 3, False, headline="latest"))
    (item,) = out["newly_failing"]
    assert item["failing_since"] == datetime(2026, 10, 2, 10, tzinfo=timezone.utc)
    assert item["last_passed_at"] == datetime(2026, 9, 25, 10, tzinfo=timezone.utc)
    assert (item["failures"], item["headline"], item["branch"]) == (2, "latest", "main")
    assert out["longest_failing"][0]["failing_since_bounded"] is False


def test_a_streak_that_began_before_the_period_is_not_new():
    out = classify(o("t1", 24, True, month=9), o("t1", 26, False, month=9), o("t1", 2, False))
    assert out["newly_failing"] == []
    assert out["longest_failing"][0]["failing_since"] == datetime(2026, 9, 26, 10, tzinfo=timezone.utc)


def test_a_streak_cut_off_by_the_look_back_is_bounded():
    out = classify(o("t3", 25, False, month=9), o("t3", 2, False), o("t3", 3, False))
    (item,) = out["longest_failing"]
    assert item["failing_since"] == PREVIOUS_START and item["failing_since_bounded"] is True
    assert item["consecutive_failures"] == 3 and out["newly_failing"] == []


def test_fixed_and_time_to_fix():
    out = classify(o("t2", 24, True, month=9), o("t2", 25, False, month=9), o("t2", 2, True),
                   o("t5", 2, False), o("t5", 4, True))
    fixed = {f["test_key"]: f for f in out["fixed"]}
    assert fixed["t2"]["time_to_fix_ms"] == 7 * DAY and fixed["t2"]["failing_since_bounded"] is False
    assert fixed["t5"]["time_to_fix_ms"] == 2 * DAY and fixed["t5"]["failing_since_bounded"] is True
    assert [f["test_key"] for f in out["fixed"]] == ["t5", "t2"]          # newest fix first
    assert out["time_to_fix"] == {"fixes": 2, "mean_ms": int(4.5 * DAY), "median_ms": int(4.5 * DAY),
                                  "p90_ms": int(6.5 * DAY), "bounded": 1}


def test_every_fix_inside_the_period_counts_toward_time_to_fix():
    out = classify(o("t1", 1, False), o("t1", 2, True), o("t1", 3, False), o("t1", 5, True))
    assert out["time_to_fix"]["fixes"] == 2
    assert [f["fixed_at"].day for f in out["fixed"]] == [5]               # only the current passing streak is "fixed"


def test_no_fixes_is_all_null():
    assert classify(o("t1", 2, True))["time_to_fix"] == {"fixes": 0, "mean_ms": None, "median_ms": None, "p90_ms": None, "bounded": 0}


def test_branches_are_separate_stories():
    out = classify(o("t1", 1, True, branch="main"), o("t1", 2, False, branch="main"), o("t1", 3, True, branch="dev"))
    assert [(i["test_key"], i["branch"]) for i in out["newly_failing"]] == [("t1", "main")]


def test_list_orders():
    out = classify(o("a", 1, True), o("a", 3, False), o("b", 1, True), o("b", 2, False),
                   o("c", 25, False, month=9), o("c", 2, False))
    assert [i["test_key"] for i in out["newly_failing"]] == ["a", "b"]         # newest first
    assert [i["test_key"] for i in out["longest_failing"]] == ["c", "b", "a"]  # oldest first


def test_flips_land_in_the_later_outcomes_bucket():
    seqs = build_sequences([o("t1", 25, True, month=9), o("t1", 2, False), o("t1", 4, True), o("t2", 4, True), o("t2", 5, True)])
    flips, flaky = flips_by_bucket(seqs, PERIOD_START, lambda moment: moment.day - 1, 7)
    assert flips == [0, 1, 0, 1, 0, 0, 0]
    assert flaky[1] == {"t1"} and flaky[3] == {"t1"} and flaky[4] == set()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/unit/test_report_streaks.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Write `report_streaks.py`**

```python
"""Regressions and stability (spec: Section regressions). Pure: the service hands over each test's last-attempt,
non-skipped outcome per run; the story of a test is told per branch."""
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

from src.ingestion.analytics.report_stats import mean, percentile

SequenceKey = Tuple[str, Optional[str]]


@dataclass(frozen=True)
class Outcome:
    test_key: str
    branch: Optional[str]
    run_id: int
    started_at: datetime
    passed: bool
    headline: Optional[str]  # a failing outcome's message headline


def build_sequences(outcomes: Iterable[Outcome]) -> Dict[SequenceKey, List[Outcome]]:
    sequences: Dict[SequenceKey, List[Outcome]] = defaultdict(list)
    for outcome in outcomes:
        sequences[(outcome.test_key, outcome.branch)].append(outcome)
    for sequence in sequences.values():
        sequence.sort(key=lambda x: (x.started_at, x.run_id))
    return dict(sequences)


def _ms(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() * 1000)


def classify_streaks(sequences: Dict[SequenceKey, List[Outcome]], period_start: datetime,
                     previous_start: datetime) -> dict:
    newly, fixed, longest, fixes = [], [], [], []
    for (key, branch), seq in sequences.items():
        last = seq[-1]
        streak = len(seq) - 1  # index where the current streak starts
        while streak > 0 and seq[streak - 1].passed == last.passed:
            streak -= 1
        start, before = seq[streak], (seq[streak - 1] if streak > 0 else None)
        base = {"test_key": key, "branch": branch}
        if not last.passed:
            cut = before is None  # the streak reaches back past the look-back: its start is unknown
            longest.append({**base, "failing_since": previous_start if cut else start.started_at,
                            "failing_since_bounded": cut, "consecutive_failures": len(seq) - streak,
                            "last_run_id": last.run_id, "headline": last.headline})
            if before is not None and start.started_at >= period_start:
                newly.append({**base, "failing_since": start.started_at, "failing_since_run_id": start.run_id,
                              "last_passed_at": before.started_at, "last_passed_run_id": before.run_id,
                              "failures": len(seq) - streak, "headline": last.headline})
        # Every failing streak that ended inside the period: a pass after one or more failures
        j = 0
        while j < len(seq):
            if seq[j].passed:
                j += 1
                continue
            k = j
            while k < len(seq) and not seq[k].passed:
                k += 1
            if k < len(seq) and seq[k].started_at >= period_start:
                cut = j == 0
                took = _ms(seq[j].started_at, seq[k].started_at)
                fixes.append((took, cut))
                if last.passed and k == streak:
                    fixed.append({**base, "fixed_at": seq[k].started_at, "fixed_run_id": seq[k].run_id,
                                  "failing_since": seq[j].started_at, "failing_since_bounded": cut,
                                  "time_to_fix_ms": took})
            j = k
    tie = lambda item: (item["test_key"], item["branch"] or "")  # noqa: E731
    newly.sort(key=lambda i: (-i["failing_since"].timestamp(), *tie(i)))
    fixed.sort(key=lambda i: (-i["fixed_at"].timestamp(), *tie(i)))
    longest.sort(key=lambda i: (i["failing_since"], -i["consecutive_failures"], *tie(i)))
    took = [ms for ms, _ in fixes]
    return {
        "newly_failing": newly, "fixed": fixed, "longest_failing": longest,
        "time_to_fix": {"fixes": len(took), "mean_ms": mean(took), "median_ms": percentile(took, 0.5),
                        "p90_ms": percentile(took, 0.9), "bounded": sum(1 for _, cut in fixes if cut)},
    }


def flips_by_bucket(sequences: Dict[SequenceKey, List[Outcome]], period_start: datetime,
                    bucket_of: Callable[[datetime], Optional[int]], bucket_count: int) -> Tuple[List[int], List[Set[str]]]:
    """A flip is an outcome change between consecutive outcomes on one branch, counted in the bucket of the later
    outcome; a test with a flip in a bucket is flaky in that bucket ("Instability (flips)")."""
    flips = [0] * bucket_count
    flaky: List[Set[str]] = [set() for _ in range(bucket_count)]
    for (key, _), seq in sequences.items():
        for before, after in zip(seq, seq[1:]):
            if after.started_at < period_start or before.passed == after.passed:
                continue
            index = bucket_of(after.started_at)
            if index is None:
                continue
            flips[index] += 1
            flaky[index].add(key)
    return flips, flaky
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/unit/test_report_streaks.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add platforms/ingestion-service/src/ingestion/analytics/report_streaks.py platforms/ingestion-service/tests/unit/test_report_streaks.py
git commit -m "feat(ingestion): outcome streaks per test and branch, time to fix, flips per bucket" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- platforms/ingestion-service/src/ingestion/analytics/report_streaks.py platforms/ingestion-service/tests/unit/test_report_streaks.py
```

---

### Task 20: Section `regressions`

**Files:**
- Modify: `platforms/ingestion-service/src/ingestion/service/report_service.py`
- Test: `platforms/ingestion-service/tests/integration/test_report_regressions.py`

**Interfaces:**
- Consumes: Tasks 2–4, 18 (`MESSAGE_PREFIX`, `_bucket_of`), 19 (`Outcome`, `build_sequences`, `classify_streaks`, `flips_by_bucket`).
- Produces:
  - `_candidates(db, scope, ids) -> dict[str, tuple[str, str, str]]` (tests with a failing execution, with their identity).
  - `_outcomes(db, ids: list[int], keys: list[str], by_id: dict[int, ScopedRun]) -> list[Outcome]` (last non-skipped attempt per test and run). Task 24 reuses it.
  - `regressions(db, scope, runs, context) -> dict` registered as `SECTION_BUILDERS["regressions"]`; `MAX_NEWLY = 100`, `MAX_FIXED = 100`, `MAX_LONGEST = 50`.

- [ ] **Step 1: Write the failing tests**

```python
"""Section regressions (spec: Section regressions (P2))."""
from datetime import datetime, timezone

import pytest

from conftest import post_report

DAY = 86_400_000


def at(month, day):
    return datetime(2026, month, day, 10, tzinfo=timezone.utc)


@pytest.fixture
def seeded(project_role, report_now, seed_run):
    project_role()
    seed_run(at(9, 24), results=(("t2", "passed", 1),))
    seed_run(at(9, 25), results=(("t1", "passed", 1), ("t2", "failed", 1), ("t3", "failed", 1)))
    seed_run(at(10, 2), results=(("t1", "failed", 1, "AssertionError: x"), ("t2", "passed", 1), ("t3", "failed", 1),
                                 ("t5", "failed", 1)))
    seed_run(at(10, 3), results=(("t1", "failed", 1, "AssertionError: y"), ("t2", "passed", 1), ("t3", "failed", 1),
                                 ("t4", "skipped", 0)))
    seed_run(at(10, 4), results=(("t5", "failed", 1), ("t5", "passed", 1)))   # a retry: the later row wins
    seed_run(at(10, 5), branch="dev", results=(("t1", "passed", 1),))


def regressions(client, auth, **body):
    response = post_report(client, auth, sections=["regressions"], **body)
    assert response.status_code == 200, response.text
    return response.json()["regressions"]


def test_newly_failing_fixed_and_longest(client, auth, seeded):
    r = regressions(client, auth)
    assert r["newly_failing"]["total"] == 1
    (newly,) = r["newly_failing"]["items"]
    assert (newly["name"], newly["branch"], newly["failures"], newly["headline"]) == ("t1", "main", 2, "AssertionError: y")
    assert (newly["failing_since"], newly["last_passed_at"]) == ("2026-10-02T10:00:00Z", "2026-09-25T10:00:00Z")
    fixed = {f["name"]: f for f in r["fixed"]["items"]}
    assert set(fixed) == {"t2", "t5"}
    assert fixed["t2"]["time_to_fix_ms"] == 7 * DAY and fixed["t2"]["failing_since_bounded"] is False
    assert fixed["t5"]["fixed_at"] == "2026-10-04T10:00:00Z" and fixed["t5"]["failing_since_bounded"] is True
    longest = r["longest_failing"]["items"]
    assert [(i["name"], i["failing_since_bounded"]) for i in longest] == [("t3", True), ("t1", False)]
    assert longest[0]["failing_since"] == "2026-09-24T00:00:00Z" and longest[0]["consecutive_failures"] == 3


def test_time_to_fix(client, auth, seeded):
    assert regressions(client, auth)["time_to_fix"] == {"fixes": 2, "mean_ms": int(4.5 * DAY), "median_ms": int(4.5 * DAY),
                                                         "p90_ms": int(6.5 * DAY), "bounded": 1}


def test_flakiness_per_bucket(client, auth, seeded):
    days = {d["date"]: d for d in regressions(client, auth)["flakiness"]}
    assert len(days) == 7
    assert (days["2026-10-02"]["flips"], days["2026-10-02"]["flaky_tests"], days["2026-10-02"]["tests_executed"]) == (2, 2, 4)
    assert days["2026-10-03"]["tests_executed"] == 3                    # t4 was only skipped
    assert (days["2026-10-04"]["flips"], days["2026-10-04"]["tests_executed"]) == (1, 1)
    assert days["2026-10-05"]["flaky_tests"] == 0                       # dev's first outcome is no flip


def test_a_branch_filter_and_test_keys(client, auth, seeded):
    from conftest import report_key
    assert regressions(client, auth, branch="dev")["newly_failing"]["total"] == 0
    only_t3 = regressions(client, auth, test_keys=[report_key("t3")])
    assert only_t3["fixed"]["total"] == 0 and [i["name"] for i in only_t3["longest_failing"]["items"]] == ["t3"]


def test_list_caps(client, auth, seeded, monkeypatch):
    from src.ingestion.service import report_service
    monkeypatch.setattr(report_service, "MAX_FIXED", 1)
    fixed = regressions(client, auth)["fixed"]
    assert fixed["total"] == 2 and len(fixed["items"]) == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/integration/test_report_regressions.py -q`
Expected: FAIL (`regressions` is `null`).

- [ ] **Step 3: Implement**

Append to `report_service.py` (import `Outcome, build_sequences, classify_streaks, flips_by_bucket` from `report_streaks`):

```python
MAX_NEWLY = 100
MAX_FIXED = 100
MAX_LONGEST = 50


def _candidates(db: Session, scope: Scope, ids: list) -> Dict[str, tuple]:
    """Tests with at least one failing execution in scope (previous period plus period): a test that never
    failed cannot regress, be fixed or flip. The partial index serves this read."""
    rows = db.execute(
        select(RunResult.test_key, func.max(RunResult.suite), func.max(RunResult.class_name), func.max(RunResult.name))
        .where(in_list(db, RunResult.run_id, ids, Integer), RunResult.status.in_(FAILING), *key_filter(db, scope))
        .group_by(RunResult.test_key)
    ).all()
    return {key: (suite, class_name, name) for key, suite, class_name, name in rows}


def _outcomes(db: Session, ids: list, keys: list, by_id: Dict[int, ScopedRun]) -> List[Outcome]:
    """Each test's outcome in each run: its last attempt (highest id) among non-skipped rows."""
    if not ids or not keys:
        return []
    ranked = (
        select(RunResult.run_id.label("run_id"), RunResult.test_key.label("test_key"), RunResult.status.label("status"),
               func.substr(RunResult.message, 1, MESSAGE_PREFIX).label("message"),
               func.row_number().over(partition_by=(RunResult.test_key, RunResult.run_id),
                                      order_by=RunResult.id.desc()).label("attempt"))
        .where(in_list(db, RunResult.run_id, ids, Integer), RunResult.status != "skipped",
               in_list(db, RunResult.test_key, keys))
    ).subquery()
    rows = db.execute(select(ranked.c.run_id, ranked.c.test_key, ranked.c.status, ranked.c.message)
                      .where(ranked.c.attempt == 1)).all()
    out = []
    for run_id, key, status, message in rows:
        run = by_id[run_id]
        passed = status == "passed"
        out.append(Outcome(key, run.branch, run_id, run.started_at, passed, None if passed else headline(message)))
    return out


def _tests_executed(db: Session, scope: Scope, counted: List[ScopedRun], context: Context) -> List[int]:
    """Distinct tests with a non-skipped result per bucket of the period: one count per bucket."""
    per_bucket: List[list] = [[] for _ in context.starts]
    for run in counted:
        index = _bucket_of(scope, context, run)
        if index is not None:
            per_bucket[index].append(run.id)
    out = []
    for ids in per_bucket:
        if not ids:
            out.append(0)
            continue
        out.append(int(db.execute(
            select(func.count(distinct(RunResult.test_key)))
            .where(in_list(db, RunResult.run_id, ids, Integer), RunResult.status != "skipped", *key_filter(db, scope))
        ).scalar() or 0))
    return out


def _serialise(item: dict, identity: Dict[str, tuple]) -> dict:
    suite, class_name, name = identity[item["test_key"]]
    out = {k: (iso(v) if isinstance(v, datetime) else v) for k, v in item.items()}
    out.update(suite=suite, class_name=class_name, name=name)
    return out


def regressions(db: Session, scope: Scope, runs: List[ScopedRun], context: Context) -> dict:
    counted = [r for r in runs if r.id in context.counted]
    by_id = {r.id: r for r in counted}
    ids = list(by_id)
    identity = _candidates(db, scope, ids) if ids else {}
    sequences = build_sequences(_outcomes(db, ids, sorted(identity), by_id))
    lists = classify_streaks(sequences, scope.period.start, scope.previous.start)

    def capped(name: str, cap: int) -> dict:
        items = lists[name]
        return {"total": len(items), "items": [_serialise(i, identity) for i in items[:cap]]}

    zone = scope.period.zone
    flips, flaky = flips_by_bucket(
        sequences, scope.period.start,
        lambda moment: bucket_index(local_day(moment, zone), context.starts, context.bucket), len(context.starts))
    executed = _tests_executed(db, scope, counted, context)
    return {
        "newly_failing": capped("newly_failing", MAX_NEWLY),
        "fixed": capped("fixed", MAX_FIXED),
        "longest_failing": capped("longest_failing", MAX_LONGEST),
        "time_to_fix": lists["time_to_fix"],
        "flakiness": [{"date": start.isoformat(), "tests_executed": executed[i], "flaky_tests": len(flaky[i]),
                       "flips": flips[i]} for i, start in enumerate(context.starts)],
    }


SECTION_BUILDERS["regressions"] = regressions
```

- [ ] **Step 4: Run the tests to verify they pass, then the suite**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add platforms/ingestion-service/src/ingestion/service/report_service.py platforms/ingestion-service/tests/integration/test_report_regressions.py
git commit -m "feat(ingestion): report regressions: newly failing, fixed, longest failing, time to fix, flips" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- platforms/ingestion-service/src/ingestion/service/report_service.py platforms/ingestion-service/tests/integration/test_report_regressions.py
```

---

### Task 21: `scripts/bench_report.py` and the README timing table

**Files:**
- Create: `scripts/bench_report.py`
- Modify: `platforms/ingestion-service/README.md` (a "Report timing" table under Analytics)

**Interfaces:**
- Consumes: `report_service.Scope`, `build_report`, `limit_statement_time`; `Period`, `choose_bucket`.
- Produces: a by-hand benchmark (not in CI) printing p50/p95 per section at sizes A and B.

- [ ] **Step 1: Write the script**

```python
"""One-off: how fast is each report section? Not part of CI (spec: Performance targets).

    SIZE=A docker compose exec -T -e SIZE=A ingestion-service python - < scripts/bench_report.py
    SIZE=B docker compose exec -T -e SIZE=B ingestion-service python - < scripts/bench_report.py

Seeds project 900002 (no such project exists in project-service) over 180 days -- the 90-day period plus its
90-day look-back -- times each section through report_service.build_report under the same 20 s statement
timeout as the endpoint, prints p50 and p95, then deletes everything it seeded. Run it in a throwaway stack.

    A: about 100,000 results per 90 days (about 1,500 runs, 1,000 tests): the expected size. Target p95 <= 1 s.
    B: the README benchmark, 2 million results per 90 days. Target <= 8 s each, never the 20 s timeout.
"""
import os
import random
import statistics
import time
from datetime import date, datetime, timedelta, timezone
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
REPEAT = 5 if SIZE == "A" else 3
STATUSES = ("passed", "failed", "errored", "skipped")
WEIGHTS = (95, 3, 1, 1)
MESSAGES = ["TimeoutError: locator('#pay-button') after {} ms", "AssertionError: expected {} got {}",
            "Error: connect ECONNREFUSED 10.0.0.{}:5432", None]

random.seed(11)
keys = [test_key("bench", f"Class{i // 50}", f"test_{i}") for i in range(TESTS)]
now = datetime.now(timezone.utc)
db = SessionLocal()


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
    db.execute(text("ANALYZE test_runs"))
    db.execute(text("ANALYZE test_results"))
    db.commit()
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


try:
    seed()
    sections = [name for name in ("summary", "failure_causes", "regressions", "tests", "duration")
                if name in report_service.SECTION_BUILDERS]
    for label, s in [
        ("90 days, every branch", scope(90)),
        ("90 days, main", scope(90, branch="main")),
        ("90 days, 300 test keys", scope(90, test_keys=keys[:300])),
        ("90 days, origin qeos (2,000 URLs)", scope(90, origin="qeos",
                                                    urls=[f"https://github.com/acme/obt/actions/runs/{i}" for i in range(2000)])),
        ("30 days, every branch", scope(30)),
    ]:
        for section in sections:
            timed(label, s, section)
finally:
    db.rollback()
    run_ids = select(Run.id).where(Run.project_id == PROJECT)
    db.execute(delete(RunResult).where(RunResult.run_id.in_(run_ids)))
    db.execute(delete(Run).where(Run.project_id == PROJECT))
    db.execute(delete(ApiKey).where(ApiKey.project_id == PROJECT))
    db.commit()
    db.close()
```

(`date` is imported for readers extending the script; remove it if a linter in the repo flags unused imports in `scripts/`.)

- [ ] **Step 2: Check the script imports and runs its scope builder against SQLite (no Docker needed)**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -c "import ast,sys; ast.parse(open('../../scripts/bench_report.py').read()); print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Measure on a throwaway stack**

Run (Docker required; this is the README benchmark's procedure):

```bash
SECRET_KEY=s INTERNAL_API_PASSWORD=p docker compose up -d --build --wait ingestion-service
docker compose exec -T -e SIZE=A ingestion-service python - < scripts/bench_report.py
docker compose exec -T -e SIZE=B ingestion-service python - < scripts/bench_report.py
docker compose down --volumes
```

Expected: A's p95 ≤ 1,000 ms per section; B ≤ 8,000 ms per section and never 20,000 (a timeout raises). If Docker is not available to the implementer, stop after Step 2, commit the script alone, and report "Bench not run: Docker unavailable" so the controller runs Step 3 before P2 ships.

- [ ] **Step 4: Record the numbers**

In `platforms/ingestion-service/README.md`, under the Analytics timing table, add:

```markdown
Report sections (`scripts/bench_report.py`, 90-day period plus 90 days of look-back, PostgreSQL 15 in Docker):

| Size | Filters | summary | failure_causes | regressions |
|---|---|---|---|---|
| A (~100k results / 90 days) | every branch | <p95> ms | <p95> ms | <p95> ms |
| B (~2M results / 90 days) | every branch | <p95> ms | <p95> ms | <p95> ms |
```

replacing each `<p95>` with the measured value (the main-branch, keys and origin rows go in too if they differ by more than 20%). Phase 3 adds the `tests` and `duration` columns.

- [ ] **Step 5: Commit**

```bash
git add scripts/bench_report.py platforms/ingestion-service/README.md
git commit -m "perf(ingestion): bench_report.py and measured report timings" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- scripts/bench_report.py platforms/ingestion-service/README.md
```

---

### Task 22: Section 2 `FailureCausesSection`

Invoke the `ui-ux-pro-max` skill before writing the component or editing `index.css`.

**Files:**
- Modify: `dashboard/src/api/report.ts` (types)
- Modify: `dashboard/src/pages/report/testFixtures.ts` (`CAUSES_REPORT`)
- Create: `dashboard/src/pages/report/sections/FailureCausesSection.tsx`
- Test: `dashboard/src/pages/report/sections/FailureCausesSection.test.tsx`
- Modify: `dashboard/src/index.css`

**Interfaces:**
- Consumes: Tasks 8–12 (`ReportSection`, `SectionQuery`, `Gate`, `testLabel`, `formatPeriod`), `StatusPill`, ChartKit, `toCsv`, `downloadCsv`.
- Produces:
  - Types: `CauseTest`, `CauseGroup`, `FailureCausesSection`; `Report.failure_causes?: FailureCausesSection`.
  - `FailureCausesSection({ projectId: number; gate: Gate; query: SectionQuery; branch: string | null; onResetFilters(): void })`; pure `causesCsv(r: Report): string`, `truncate(text: string, max: number): string`.

- [ ] **Step 1: Add the types**

Append to `dashboard/src/api/report.ts`, and add `failure_causes?: FailureCausesSection;` to `Report`:

```ts
export interface CauseTest extends ReportTestRef { occurrences: number; last_run_id: number }

export interface CauseGroup {
  signature: string;
  headline: string | null;
  occurrences: number;
  failed: number;
  errored: number;
  quarantined: number;
  tests: number;
  runs: number;
  status: "new" | "recurring";
  previous_occurrences: number;
  first_seen: string;
  first_seen_run_id: number;
  last_seen: string;
  last_seen_run_id: number;
  /** One count per bucket, aligned with summary.buckets */
  buckets: number[];
  top_tests: CauseTest[];
}

export interface FailureCausesSection {
  failures: number;
  groups_total: number;
  groups: CauseGroup[];
  other: { groups: number; occurrences: number };
  resolved: { signature: string; headline: string | null; previous_occurrences: number; last_seen: string }[];
}
```

- [ ] **Step 2: Add the fixture and write the failing tests**

Append to `testFixtures.ts`:

```ts
import type { CauseGroup } from "../../api/report";

const cause = (over: Partial<CauseGroup>): CauseGroup => ({
  signature: "9f2c1ab04e7d", headline: "TimeoutError: locator('#pay-button') after 30000 ms", occurrences: 412, failed: 400,
  errored: 12, quarantined: 0, tests: 18, runs: 66, status: "new", previous_occurrences: 0,
  first_seen: "2026-09-14T08:12:00Z", first_seen_run_id: 9012, last_seen: "2026-10-08T09:40:00Z", last_seen_run_id: 9433,
  buckets: [0, 41], top_tests: [{ test_key: "a".repeat(64), suite: "checkout", class_name: "Cart", name: "pays", occurrences: 40, last_run_id: 9433 }],
  ...over,
});

export const CAUSES_REPORT = {
  ...SUMMARY_REPORT,
  failure_causes: {
    failures: 2124, groups_total: 37,
    groups: [
      cause({}),
      cause({ signature: "11aa22bb33cc", headline: "AssertionError: expected 3 got 4", occurrences: 90, status: "recurring",
        previous_occurrences: 31, first_seen: "2026-08-12T10:00:00Z", buckets: [3, 2] }),
      cause({ signature: "none", headline: null, occurrences: 5, status: "recurring", previous_occurrences: 2 }),
    ],
    other: { groups: 34, occurrences: 1617 },
    resolved: [{ signature: "ffee", headline: "Error: connect ECONNREFUSED", previous_occurrences: 31, last_seen: "2026-09-02T10:00:00Z" }],
  },
};
```

`dashboard/src/pages/report/sections/FailureCausesSection.test.tsx`:

```tsx
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import type { Report } from "../../../api/report";
import type { Gate } from "../useReportRequest";
import { CAUSES_REPORT } from "../testFixtures";
import FailureCausesSection, { causesCsv, truncate } from "./FailureCausesSection";

const READY: Gate = { state: "ready", base: {} as never, key: [] };

function show(report: Report = CAUSES_REPORT) {
  render(
    <MemoryRouter>
      <FailureCausesSection projectId={42} gate={READY} branch="main" onResetFilters={vi.fn()}
        query={{ data: report, error: null, isPending: false, refetch: vi.fn() }} />
    </MemoryRouter>,
  );
}

test("the table tags New and Recurring in words and says when first seen is older than the data read", () => {
  show();
  const table = screen.getByRole("table", { name: /failure causes/i });
  const rows = within(table).getAllByRole("row");
  expect(rows[1]).toHaveTextContent("New");
  expect(rows[2]).toHaveTextContent("Recurring");
  expect(rows[2]).toHaveTextContent(/seen since at least/i);           // first seen in the previous period
  expect(within(rows[1]).getByRole("link", { name: /run #9433/i })).toHaveAttribute("href", "/projects/42/runs/9433");
  expect(within(table).getByText("(no message)")).toBeInTheDocument();
});

test("rows expand to their tests, each linking to its history on the branch", async () => {
  show();
  const toggle = screen.getAllByRole("button", { name: /show tests/i })[0];
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  await userEvent.click(toggle);
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  expect(screen.getByRole("link", { name: /checkout › Cart › pays/ })).toHaveAttribute(
    "href", `/projects/42/tests/${"a".repeat(64)}?branch=main`);
});

test("chart caption, other causes, resolved list and the sparkline's text", () => {
  show();
  expect(within(screen.getByRole("figure")).getByText(/2,124 failures from 37 causes; the largest is TimeoutError/)).toBeInTheDocument();
  expect(screen.getByText(/34 more causes with 1,617 failures/)).toBeInTheDocument();
  expect(within(screen.getByRole("list", { name: /resolved since the previous period/i })).getByText(/ECONNREFUSED/)).toBeInTheDocument();
  expect(screen.getAllByText(/per day: 0, 41/i).length).toBeGreaterThan(0);
});

test("without a previous period every cause is New, with a note", () => {
  show({ ...CAUSES_REPORT, scope: { ...CAUSES_REPORT.scope, previous_runs: 0 } });
  expect(screen.getByText(/no data in the previous period, so every cause is new/i)).toBeInTheDocument();
});

test("CSV columns and headline truncation", () => {
  const lines = causesCsv(CAUSES_REPORT).split("\r\n");
  expect(lines[0]).toBe("signature,headline,occurrences,failed,errored,tests,runs,status,previous_occurrences,first_seen,last_seen");
  expect(lines).toHaveLength(4);
  expect(truncate("x".repeat(100), 80)).toHaveLength(80);
  expect(truncate("short", 80)).toBe("short");
});
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd dashboard && npx vitest run src/pages/report/sections/FailureCausesSection.test.tsx`
Expected: FAIL (module missing).

- [ ] **Step 4: Write `FailureCausesSection.tsx`**

```tsx
import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, Download } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { type CauseGroup, type Report, testLabel } from "../../../api/report";
import { DataTableDisclosure, PATTERN } from "../../../components/ChartKit";
import StatusPill from "../../../components/StatusPill";
import { formatPointLabel } from "../../../lib/chartFormat";
import { downloadCsv, toCsv } from "../../../lib/csv";
import ReportSection, { type SectionQuery } from "../ReportSection";
import type { Gate } from "../useReportRequest";

const number = new Intl.NumberFormat();
const TOP_IN_CHART = 10;
const day = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" });

export function truncate(text: string, max: number): string {
  return text.length <= max ? text : `${text.slice(0, max - 1)}…`;
}

const headlineOf = (g: { headline: string | null }) => g.headline ?? "(no message)";

export function causesCsv(r: Report): string {
  return toCsv(
    ["signature", "headline", "occurrences", "failed", "errored", "tests", "runs", "status", "previous_occurrences", "first_seen", "last_seen"],
    r.failure_causes!.groups.map((g) => [g.signature, g.headline, g.occurrences, g.failed, g.errored, g.tests, g.runs, g.status,
      g.previous_occurrences, g.first_seen, g.last_seen]),
  );
}

/** A small line of the cause per bucket; the numbers are in its text equivalent, never only in the drawing. */
function Sparkline({ values, unit }: { values: number[]; unit: string }) {
  const max = Math.max(1, ...values);
  const width = 80;
  const height = 20;
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  const points = values.map((v, i) => `${(i * step).toFixed(1)},${(height - (v / max) * (height - 2) - 1).toFixed(1)}`).join(" ");
  return (
    <span className="sparkline">
      <svg width={width} height={height} aria-hidden="true" focusable="false">
        <polyline points={points} fill="none" stroke="var(--status-failed)" strokeWidth="1.5" />
      </svg>
      <span className="sr-only">per {unit}: {values.join(", ")}</span>
    </span>
  );
}

function StatusTag({ g }: { g: CauseGroup }) {
  return g.status === "new" ? <StatusPill tone="failed" label="New" /> : <StatusPill tone="neutral" label="Recurring" />;
}

interface Props {
  projectId: number;
  gate: Gate;
  query: SectionQuery;
  branch: string | null;
  onResetFilters: () => void;
}

/** Section 2 (spec: Section 2: Failure causes): the run view's signature groups over the period, new or recurring
 *  against the previous period. */
export default function FailureCausesSection({ projectId, gate, query, branch, onResetFilters }: Props) {
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set());
  const toggle = (sig: string) => setOpen((o) => {
    const next = new Set(o);
    if (next.has(sig)) next.delete(sig);
    else next.add(sig);
    return next;
  });
  const history = (key: string) => `/projects/${projectId}/tests/${encodeURIComponent(key)}${branch ? `?branch=${encodeURIComponent(branch)}` : ""}`;

  return (
    <ReportSection
      id="report-causes"
      title="Failure causes"
      gate={gate}
      query={query}
      height={360}
      onResetFilters={onResetFilters}
      actions={query.data?.failure_causes && query.data.scope.runs > 0 ? (
        <button type="button" onClick={() => downloadCsv(`report-${projectId}-${query.data!.period.from}-${query.data!.period.to}-causes.csv`, causesCsv(query.data!))}>
          <Download size={15} aria-hidden="true" /> Causes CSV
        </button>
      ) : undefined}
    >
      {(r) => {
        const c = r.failure_causes!;
        if (c.groups.length === 0) return <p className="muted">No failures in this period.</p>;
        const periodStart = Date.parse(r.period.start);
        const unit = r.bucket;
        const chart = c.groups.slice(0, TOP_IN_CHART).map((g) => ({
          label: `${g.status === "new" ? "New · " : ""}${truncate(headlineOf(g), 80)}`,
          occurrences: g.occurrences, status: g.status,
        }));
        const largest = c.groups[0];
        const caption = `${number.format(c.failures)} failures from ${number.format(c.groups_total)} causes; the largest is `
          + `${truncate(headlineOf(largest), 80)} with ${number.format(largest.occurrences)}`
          + `${largest.status === "new" ? ", new in this period" : ""}.`;
        return (
          <>
            {r.scope.previous_runs === 0 && (
              <p className="muted report-note">No data in the previous period, so every cause is new.</p>
            )}
            <figure className="chart-figure" aria-labelledby="report-causes">
              <figcaption className="sr-only">{caption}</figcaption>
              <ResponsiveContainer width="100%" height={Math.max(160, chart.length * 32)}>
                <BarChart data={chart} layout="vertical" margin={{ left: 8, right: 48 }} accessibilityLayer>
                  <CartesianGrid stroke="var(--grid)" horizontal={false} />
                  <XAxis type="number" allowDecimals={false} stroke="var(--text-muted)" tick={{ fill: "var(--text-secondary)", fontSize: 12 }} />
                  <YAxis type="category" dataKey="label" width={260} stroke="var(--text-muted)" tick={{ fill: "var(--text-secondary)", fontSize: 12 }} />
                  <Tooltip contentStyle={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 6 }} />
                  <Bar dataKey="occurrences" name="Occurrences" stroke="var(--surface-1)">
                    {chart.map((d) => (
                      <Cell key={d.label} fill={d.status === "new" ? `url(#${PATTERN.failed})` : "var(--status-failed)"} />
                    ))}
                    <LabelList dataKey="occurrences" position="right" fill="var(--text-secondary)" fontSize={12} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </figure>
            <p className="muted report-note">New causes are striped and tagged "New"; recurring ones are solid.</p>
            <DataTableDisclosure name="failure causes chart">
              <table className="data">
                <thead><tr><th scope="col">Cause</th><th scope="col" className="num">Occurrences</th><th scope="col">Status</th></tr></thead>
                <tbody>{c.groups.slice(0, TOP_IN_CHART).map((g) => (
                  <tr key={g.signature}><td className="wrap-anywhere">{headlineOf(g)}</td><td className="num">{number.format(g.occurrences)}</td><td>{g.status === "new" ? "New" : "Recurring"}</td></tr>
                ))}</tbody>
              </table>
            </DataTableDisclosure>

            <table className="data">
              <caption className="sr-only">Failure causes</caption>
              <thead><tr>
                <th scope="col">Cause</th><th scope="col" className="num">Occurrences</th>
                <th scope="col" className="num hide-narrow">Tests</th><th scope="col" className="num hide-narrow">Runs</th>
                <th scope="col">Status</th><th scope="col" className="hide-narrow">First seen</th><th scope="col">Last seen</th>
                <th scope="col" className="hide-narrow">Trend</th>
              </tr></thead>
              <tbody>
                {c.groups.map((g) => {
                  const expanded = open.has(g.signature);
                  const before = Date.parse(g.first_seen) < periodStart;
                  return (
                    <Fragment key={g.signature}>
                      <tr>
                        <td className="wrap-anywhere">
                          <button type="button" className="row-toggle" aria-expanded={expanded}
                            aria-label={`Show tests for ${truncate(headlineOf(g), 80)}`} onClick={() => toggle(g.signature)}>
                            <ChevronRight size={14} aria-hidden="true" className="chevron" />
                          </button>
                          {headlineOf(g)}
                          {g.quarantined > 0 && <span className="muted"> · {number.format(g.quarantined)} quarantined</span>}
                        </td>
                        <td className="num">{number.format(g.occurrences)}</td>
                        <td className="num hide-narrow">{number.format(g.tests)}</td>
                        <td className="num hide-narrow">{number.format(g.runs)}</td>
                        <td><StatusTag g={g} /></td>
                        <td className="hide-narrow">{before ? `seen since at least ${day.format(new Date(r.previous_period.start))}` : day.format(new Date(g.first_seen))}</td>
                        <td><Link to={`/projects/${projectId}/runs/${g.last_seen_run_id}`}>{day.format(new Date(g.last_seen))} (run #{g.last_seen_run_id})</Link></td>
                        <td className="hide-narrow"><Sparkline values={g.buckets} unit={unit} /></td>
                      </tr>
                      {expanded && (
                        <tr className="row-detail">
                          <td colSpan={8}>
                            <ul className="plain-list">
                              {g.top_tests.map((t) => (
                                <li key={t.test_key}>
                                  <Link to={history(t.test_key)}>{testLabel(t)}</Link>
                                  <span className="muted"> · {number.format(t.occurrences)} {t.occurrences === 1 ? "time" : "times"}</span>
                                </li>
                              ))}
                            </ul>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
            {c.other.groups > 0 && (
              <p className="muted report-note">And {number.format(c.other.groups)} more causes with {number.format(c.other.occurrences)} failures.</p>
            )}
            {c.resolved.length > 0 && (
              <>
                <h3 id="report-resolved">Resolved since the previous period</h3>
                <ul className="plain-list" aria-labelledby="report-resolved">
                  {c.resolved.map((x) => (
                    <li key={x.signature}>
                      <span className="wrap-anywhere">{headlineOf(x)}</span>
                      <span className="muted"> · {number.format(x.previous_occurrences)} before, last seen {formatPointLabel(x.last_seen.slice(0, 10), "day")}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        );
      }}
    </ReportSection>
  );
}
```

- [ ] **Step 5: Styles** (append to `index.css`; tokens only)

```css
.row-toggle { display: inline-flex; align-items: center; justify-content: center; min-width: 24px; min-height: 24px; margin-right: var(--space-1); padding: 0; border: 0; background: none; color: var(--text-secondary); }
.row-toggle[aria-expanded="true"] .chevron { transform: rotate(90deg); }
@media (pointer: coarse) { .row-toggle { min-width: 44px; min-height: 44px; } }
.row-detail td { background: var(--surface-2); }
.plain-list { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-1); }
.sparkline { display: inline-flex; align-items: center; }
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd dashboard && npx vitest run src/pages/report && npm run lint && npm run typecheck`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add dashboard/src/api/report.ts dashboard/src/pages/report/testFixtures.ts dashboard/src/pages/report/sections/FailureCausesSection.tsx dashboard/src/pages/report/sections/FailureCausesSection.test.tsx dashboard/src/index.css
git commit -m "feat(dashboard): report failure causes section" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard/src/api/report.ts dashboard/src/pages/report/testFixtures.ts dashboard/src/pages/report/sections/FailureCausesSection.tsx dashboard/src/pages/report/sections/FailureCausesSection.test.tsx dashboard/src/index.css
```

---

### Task 23: Section 4 `RegressionsSection`; the page loses the Flaky table

Invoke the `ui-ux-pro-max` skill before writing the component or changing the page.

**Files:**
- Modify: `dashboard/src/api/report.ts` (types)
- Modify: `dashboard/src/pages/report/testFixtures.ts` (`REGRESSIONS_REPORT`)
- Create: `dashboard/src/pages/report/sections/RegressionsSection.tsx`, `RegressionsSection.test.tsx`
- Modify: `dashboard/src/pages/report/ReportPage.tsx`, `ReportPage.test.tsx`
- Delete: `dashboard/src/pages/report/sections/FlakySection.tsx` (`git rm`)

**Interfaces:**
- Consumes: Tasks 8–14, 22.
- Produces:
  - Types: `RegressionItem`, `NewlyFailingItem`, `FixedItem`, `LongestFailingItem`, `RegressionsSection`; `Report.regressions?: RegressionsSection`.
  - `RegressionsSection({ projectId; gate; query; branch: string | null; onResetFilters })`; pure `formatSpan(ms: number | null): string`, `newlyCsv(r)`, `fixedCsv(r)`, `longestCsv(r)`.

- [ ] **Step 1: Add the types**

Append to `api/report.ts`, and add `regressions?: RegressionsSection;` to `Report`:

```ts
export interface RegressionItem extends ReportTestRef { branch: string | null }
export interface NewlyFailingItem extends RegressionItem {
  failing_since: string; failing_since_run_id: number; last_passed_at: string; last_passed_run_id: number;
  failures: number; headline: string | null;
}
export interface FixedItem extends RegressionItem {
  fixed_at: string; fixed_run_id: number; failing_since: string; failing_since_bounded: boolean; time_to_fix_ms: number;
}
export interface LongestFailingItem extends RegressionItem {
  failing_since: string; failing_since_bounded: boolean; consecutive_failures: number; last_run_id: number; headline: string | null;
}
export interface RegressionsSection {
  newly_failing: { total: number; items: NewlyFailingItem[] };
  fixed: { total: number; items: FixedItem[] };
  longest_failing: { total: number; items: LongestFailingItem[] };
  time_to_fix: { fixes: number; mean_ms: number | null; median_ms: number | null; p90_ms: number | null; bounded: number };
  flakiness: { date: string; tests_executed: number; flaky_tests: number; flips: number }[];
}
```

- [ ] **Step 2: Add the fixture and write the failing tests**

Append to `testFixtures.ts`:

```ts
const ref = (name: string) => ({ test_key: name.padEnd(64, "0"), suite: "checkout", class_name: "Cart", name, branch: "main" });

export const REGRESSIONS_REPORT = {
  ...SUMMARY_REPORT,
  regressions: {
    newly_failing: { total: 9, items: [{ ...ref("pays"), failing_since: "2026-10-02T10:00:00Z", failing_since_run_id: 9301,
      last_passed_at: "2026-09-25T10:00:00Z", last_passed_run_id: 9290, failures: 4, headline: "AssertionError: total" }] },
    fixed: { total: 5, items: [{ ...ref("ships"), fixed_at: "2026-10-04T10:00:00Z", fixed_run_id: 9400,
      failing_since: "2026-10-02T10:00:00Z", failing_since_bounded: true, time_to_fix_ms: 172_800_000 }] },
    longest_failing: { total: 12, items: [{ ...ref("refunds"), failing_since: "2026-09-08T23:00:00Z", failing_since_bounded: true,
      consecutive_failures: 31, last_run_id: 9433, headline: "Error: refund API down" }] },
    time_to_fix: { fixes: 23, mean_ms: 151_200_000, median_ms: 86_400_000, p90_ms: 432_000_000, bounded: 2 },
    flakiness: [{ date: "2026-10-07", tests_executed: 990, flaky_tests: 14, flips: 51 }, { date: "2026-10-08", tests_executed: 0, flaky_tests: 0, flips: 0 }],
  },
};
```

`RegressionsSection.test.tsx`:

```tsx
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { Gate } from "../useReportRequest";
import { REGRESSIONS_REPORT } from "../testFixtures";
import RegressionsSection, { fixedCsv, formatSpan, longestCsv, newlyCsv } from "./RegressionsSection";

const READY: Gate = { state: "ready", base: {} as never, key: [] };

function show() {
  render(
    <MemoryRouter>
      <RegressionsSection projectId={42} gate={READY} branch="main" onResetFilters={vi.fn()}
        query={{ data: REGRESSIONS_REPORT, error: null, isPending: false, refetch: vi.fn() }} />
    </MemoryRouter>,
  );
}

test("tiles: newly failing, fixed, still failing, median time to fix with the bounded count", () => {
  show();
  expect(screen.getByRole("group", { name: "Newly failing 9" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Fixed 5" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Still failing 12" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Median time to fix 1 day (2 at least)" })).toBeInTheDocument();
});

test("the instability chart is labelled flips and explains it differs from the Flaky page", () => {
  show();
  expect(screen.getByRole("heading", { name: /instability \(flips\)/i })).toBeInTheDocument();
  expect(screen.getByText(/same-commit rule/i)).toBeInTheDocument();
  expect(within(screen.getByRole("figure")).getByText(/14 flaky tests of 990/i)).toBeInTheDocument();
});

test("three tables link to the test history on its branch and to the run; bounded starts say at least", () => {
  show();
  const newly = screen.getByRole("table", { name: /newly failing/i });
  expect(within(newly).getByRole("link", { name: /checkout › Cart › pays/ })).toHaveAttribute(
    "href", `/projects/42/tests/${"pays".padEnd(64, "0")}?branch=main`);
  expect(within(newly).getByRole("link", { name: /run #9301/ })).toHaveAttribute("href", "/projects/42/runs/9301");
  expect(within(screen.getByRole("table", { name: /^fixed/i })).getByText(/at least since/i)).toBeInTheDocument();
  expect(within(screen.getByRole("table", { name: /longest failing/i })).getByText(/at least since/i)).toBeInTheDocument();
  expect(screen.getByText(/and 8 more/i)).toBeInTheDocument();       // newly failing: 9 total, 1 shown
});

test("spans and CSVs", () => {
  expect(formatSpan(null)).toBe("—");
  expect(formatSpan(90 * 60_000)).toBe("1.5 h");
  expect(formatSpan(86_400_000)).toBe("1 day");
  expect(formatSpan(432_000_000)).toBe("5 days");
  expect(newlyCsv(REGRESSIONS_REPORT).split("\r\n")[0]).toBe("suite,class_name,name,test_key,branch,failing_since,last_passed_at,failures,headline");
  expect(fixedCsv(REGRESSIONS_REPORT).split("\r\n")[0]).toBe("suite,class_name,name,test_key,branch,fixed_at,failing_since,failing_since_bounded,time_to_fix_ms");
  expect(longestCsv(REGRESSIONS_REPORT).split("\r\n")).toHaveLength(2);
});
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd dashboard && npx vitest run src/pages/report/sections/RegressionsSection.test.tsx`
Expected: FAIL (module missing).

- [ ] **Step 4: Write `RegressionsSection.tsx`**

```tsx
import { type ReactNode, useState } from "react";
import { Link } from "react-router-dom";
import { Download } from "lucide-react";
import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { type RegressionItem, type Report, testLabel } from "../../../api/report";
import { DataTableDisclosure, type LegendSeries, SeriesLegend } from "../../../components/ChartKit";
import { formatPointLabel, formatTick } from "../../../lib/chartFormat";
import { downloadCsv, toCsv } from "../../../lib/csv";
import DeltaTile from "../DeltaTile";
import ReportSection, { type SectionQuery } from "../ReportSection";
import type { Gate } from "../useReportRequest";

const number = new Intl.NumberFormat();
const when = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const axisTick = { fill: "var(--text-secondary)", fontSize: 12 } as const;
const LEGEND: LegendSeries[] = [
  { key: "flaky", label: "Flaky tests", paint: "var(--series-1)" },
  { key: "share", label: "Share of tests executed", paint: "var(--series-2)", line: { dash: "5 4" } },
];

/** A time to fix as people say it: minutes, hours to one decimal under two days, then whole days. */
export function formatSpan(ms: number | null): string {
  if (ms === null) return "—";
  const hours = ms / 3_600_000;
  if (hours < 1) return `${Math.round(ms / 60_000)} min`;
  if (hours < 24) return `${Math.round(hours * 10) / 10} h`;
  const days = Math.round(hours / 24);
  return `${days} ${days === 1 ? "day" : "days"}`;
}

const id = (t: RegressionItem) => [t.suite, t.class_name, t.name, t.test_key, t.branch];

export function newlyCsv(r: Report): string {
  return toCsv(["suite", "class_name", "name", "test_key", "branch", "failing_since", "last_passed_at", "failures", "headline"],
    r.regressions!.newly_failing.items.map((t) => [...id(t), t.failing_since, t.last_passed_at, t.failures, t.headline]));
}
export function fixedCsv(r: Report): string {
  return toCsv(["suite", "class_name", "name", "test_key", "branch", "fixed_at", "failing_since", "failing_since_bounded", "time_to_fix_ms"],
    r.regressions!.fixed.items.map((t) => [...id(t), t.fixed_at, t.failing_since, String(t.failing_since_bounded), t.time_to_fix_ms]));
}
export function longestCsv(r: Report): string {
  return toCsv(["suite", "class_name", "name", "test_key", "branch", "failing_since", "failing_since_bounded", "consecutive_failures", "headline"],
    r.regressions!.longest_failing.items.map((t) => [...id(t), t.failing_since, String(t.failing_since_bounded), t.consecutive_failures, t.headline]));
}

interface Props {
  projectId: number;
  gate: Gate;
  query: SectionQuery;
  branch: string | null;
  onResetFilters: () => void;
}

/** Section 4 (spec: Section 4: Regressions and stability). Outcomes are compared per (test, branch), so the help text
 *  recommends a branch filter; it is on the default branch unless the reader picks another. */
export default function RegressionsSection({ projectId, gate, query, branch, onResetFilters }: Props) {
  const [hidden, setHidden] = useState<ReadonlySet<string>>(new Set());
  const toggle = (key: string) => setHidden((h) => {
    const next = new Set(h);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    return next;
  });
  const history = (t: RegressionItem) =>
    `/projects/${projectId}/tests/${encodeURIComponent(t.test_key)}${t.branch ? `?branch=${encodeURIComponent(t.branch)}` : ""}`;
  const run = (runId: number, label: ReactNode) => <Link to={`/projects/${projectId}/runs/${runId}`}>{label}</Link>;
  const since = (iso: string, bounded: boolean) => `${bounded ? "at least since " : ""}${when.format(new Date(iso))}`;
  const more = (total: number, shown: number) => total > shown && <p className="muted report-note">And {number.format(total - shown)} more.</p>;
  const csv = (r: Report, part: string, make: (r: Report) => string) => (
    <button type="button" onClick={() => downloadCsv(`report-${projectId}-${r.period.from}-${r.period.to}-${part}.csv`, make(r))}>
      <Download size={15} aria-hidden="true" /> {part.replace("-", " ")} CSV
    </button>
  );

  return (
    <ReportSection
      id="report-regressions"
      title="Regressions and stability"
      gate={gate}
      query={query}
      height={420}
      onResetFilters={onResetFilters}
      note={<>Outcomes are compared per test and branch{branch ? ` (on ${branch})` : "; pick a branch for one story per test"}.</>}
      actions={query.data?.regressions && query.data.scope.runs > 0 ? (
        <>{csv(query.data, "newly-failing", newlyCsv)}{csv(query.data, "fixed", fixedCsv)}{csv(query.data, "longest-failing", longestCsv)}</>
      ) : undefined}
    >
      {(r) => {
        const g = r.regressions!;
        const unit = r.bucket;
        const ttf = g.time_to_fix;
        const median = `${formatSpan(ttf.median_ms)}${ttf.bounded > 0 ? ` (${ttf.bounded} at least)` : ""}`;
        const rows = g.flakiness.map((b) => ({
          date: b.date, flaky: b.flaky_tests,
          share: b.tests_executed > 0 ? Math.round((b.flaky_tests / b.tests_executed) * 1000) / 10 : null,
        }));
        const flaky = g.flakiness.reduce((n, b) => n + b.flaky_tests, 0);
        const busiest = [...g.flakiness].sort((a, b) => b.flaky_tests - a.flaky_tests)[0];
        const caption = busiest && busiest.flaky_tests > 0
          ? `${number.format(flaky)} flaky test-${unit}s; most on ${formatPointLabel(busiest.date, unit)}: ${number.format(busiest.flaky_tests)} flaky tests of ${number.format(busiest.tests_executed)}.`
          : "No flips in this period.";
        return (
          <>
            <ul className="kpi-tiles" aria-label="Regression figures">
              <li><DeltaTile title="Newly failing" value={number.format(g.newly_failing.total)} delta={null} noPrevious={false} /></li>
              <li><DeltaTile title="Fixed" value={number.format(g.fixed.total)} delta={null} noPrevious={false} /></li>
              <li><DeltaTile title="Still failing" value={number.format(g.longest_failing.total)} delta={null} noPrevious={false} /></li>
              <li><DeltaTile title="Median time to fix" value={median} delta={null} noPrevious={false} /></li>
            </ul>

            <h3 id="report-instability">Instability (flips) per {unit}</h3>
            <p className="muted report-note">
              A flip is a pass/fail change between a test's consecutive outcomes on one branch. This differs from the Flaky page's
              same-commit rule, which stays the reference for confirmed flaky tests.
            </p>
            <SeriesLegend series={LEGEND} hidden={hidden} onToggle={toggle} label="Show or hide a series" />
            <figure className="chart-figure" aria-labelledby="report-instability">
              <figcaption className="sr-only">{caption}</figcaption>
              <ResponsiveContainer width="100%" height={240}>
                <ComposedChart data={rows} accessibilityLayer>
                  <CartesianGrid stroke="var(--grid)" vertical={false} />
                  <XAxis dataKey="date" stroke="var(--text-muted)" tick={axisTick} tickLine={false} tickFormatter={(d: string) => formatTick(d, unit)} minTickGap={16} />
                  <YAxis yAxisId="count" allowDecimals={false} stroke="var(--text-muted)" tick={axisTick} tickLine={false} width={40} />
                  <YAxis yAxisId="share" orientation="right" domain={[0, "auto"]} tickFormatter={(v: number) => `${v}%`} stroke="var(--text-muted)" tick={axisTick} tickLine={false} width={44} />
                  <Tooltip contentStyle={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 6 }} labelFormatter={(d) => formatPointLabel(String(d), unit)} />
                  <Bar yAxisId="count" dataKey="flaky" name="Flaky tests" fill="var(--series-1)" hide={hidden.has("flaky")} radius={[4, 4, 0, 0]} />
                  <Line yAxisId="share" dataKey="share" name="Share of tests executed (%)" stroke="var(--series-2)" strokeWidth={2} strokeDasharray="5 4"
                    hide={hidden.has("share")} dot={{ r: 2.5, fill: "var(--series-2)", stroke: "var(--surface-1)" }} connectNulls={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </figure>
            <DataTableDisclosure name={`instability per ${unit}`}>
              <table className="data">
                <thead><tr><th scope="col">{unit === "day" ? "Date" : "Week of"}</th><th scope="col" className="num">Tests executed</th>
                  <th scope="col" className="num">Flaky tests</th><th scope="col" className="num">Flips</th></tr></thead>
                <tbody>{g.flakiness.map((b) => (
                  <tr key={b.date}><td>{formatPointLabel(b.date, unit)}</td><td className="num">{number.format(b.tests_executed)}</td>
                    <td className="num">{number.format(b.flaky_tests)}</td><td className="num">{number.format(b.flips)}</td></tr>
                ))}</tbody>
              </table>
            </DataTableDisclosure>

            <h3>Newly failing</h3>
            <table className="data">
              <caption className="sr-only">Newly failing tests</caption>
              <thead><tr><th scope="col">Test</th><th scope="col">Branch</th><th scope="col">Failing since</th>
                <th scope="col" className="hide-narrow">Last passed</th><th scope="col" className="num">Failures</th><th scope="col" className="hide-narrow">Headline</th></tr></thead>
              <tbody>{g.newly_failing.items.map((t) => (
                <tr key={`${t.test_key}|${t.branch}`}>
                  <td className="wrap-anywhere"><Link to={history(t)}>{testLabel(t)}</Link></td>
                  <td>{t.branch ?? <span className="muted">no branch</span>}</td>
                  <td>{run(t.failing_since_run_id, `${when.format(new Date(t.failing_since))} (run #${t.failing_since_run_id})`)}</td>
                  <td className="hide-narrow">{run(t.last_passed_run_id, when.format(new Date(t.last_passed_at)))}</td>
                  <td className="num">{number.format(t.failures)}</td>
                  <td className="wrap-anywhere hide-narrow">{t.headline ?? "(no message)"}</td>
                </tr>
              ))}</tbody>
            </table>
            {more(g.newly_failing.total, g.newly_failing.items.length)}

            <h3>Fixed</h3>
            <table className="data">
              <caption className="sr-only">Fixed tests</caption>
              <thead><tr><th scope="col">Test</th><th scope="col">Branch</th><th scope="col">Fixed at</th>
                <th scope="col" className="hide-narrow">Failing since</th><th scope="col" className="num">Time to fix</th></tr></thead>
              <tbody>{g.fixed.items.map((t) => (
                <tr key={`${t.test_key}|${t.branch}`}>
                  <td className="wrap-anywhere"><Link to={history(t)}>{testLabel(t)}</Link></td>
                  <td>{t.branch ?? <span className="muted">no branch</span>}</td>
                  <td>{run(t.fixed_run_id, `${when.format(new Date(t.fixed_at))} (run #${t.fixed_run_id})`)}</td>
                  <td className="hide-narrow">{since(t.failing_since, t.failing_since_bounded)}</td>
                  <td className="num">{t.failing_since_bounded ? "at least " : ""}{formatSpan(t.time_to_fix_ms)}</td>
                </tr>
              ))}</tbody>
            </table>
            {more(g.fixed.total, g.fixed.items.length)}

            <h3>Longest failing</h3>
            <table className="data">
              <caption className="sr-only">Longest failing tests</caption>
              <thead><tr><th scope="col">Test</th><th scope="col">Branch</th><th scope="col">Failing since</th>
                <th scope="col" className="num">Consecutive failures</th><th scope="col" className="hide-narrow">Headline</th></tr></thead>
              <tbody>{g.longest_failing.items.map((t) => (
                <tr key={`${t.test_key}|${t.branch}`}>
                  <td className="wrap-anywhere"><Link to={history(t)}>{testLabel(t)}</Link></td>
                  <td>{t.branch ?? <span className="muted">no branch</span>}</td>
                  <td>{since(t.failing_since, t.failing_since_bounded)}</td>
                  <td className="num">{run(t.last_run_id, number.format(t.consecutive_failures))}</td>
                  <td className="wrap-anywhere hide-narrow">{t.headline ?? "(no message)"}</td>
                </tr>
              ))}</tbody>
            </table>
            {more(g.longest_failing.total, g.longest_failing.items.length)}
          </>
        );
      }}
    </ReportSection>
  );
}
```

Note: the `fixedCsv` header test expects the table caption "Fixed tests" to match `/^fixed/i`; keep the caption text as written.

- [ ] **Step 5: Put both P2 sections on the page and remove the Flaky table**

In `ReportPage.tsx`:
- import `FailureCausesSection` and `RegressionsSection`; remove the `FlakySection` import.
- after `const summary = ...` add:

```tsx
  const causes = useReportSection(id, gate, "failure_causes");
  const regressions = useReportSection(id, gate, "regressions");
```

- change `busy` to `const busy = [summary, causes, regressions].some((q) => q.fetchStatus === "fetching");`
- in `refresh()`, drop `["report-flaky", id]` from the list.
- replace `<FlakySection ... />` with:

```tsx
      <FailureCausesSection projectId={id} gate={gate} query={causes} branch={effectiveBranch} onResetFilters={clearAll} />
      <RegressionsSection projectId={id} gate={gate} query={regressions} branch={effectiveBranch} onResetFilters={clearAll} />
```

Then `git rm dashboard/src/pages/report/sections/FlakySection.tsx`.

In `ReportPage.test.tsx`:
- in `serve()`, make the default report answer `HttpResponse.json({ ...SUMMARY_REPORT, ...CAUSES_REPORT, ...REGRESSIONS_REPORT })` (import both from `./testFixtures`), and drop the `/analytics/flaky` handler;
- the tests already read the summary's requests through `summaryBodies()`; keep `expect(bodies).toHaveLength(0)` in the "no linked tests" test (no section may be asked);
- in the area test, replace the Flaky assertion with
  `expect(within(screen.getByRole("region", { name: "Failure causes" })).getByText(/TimeoutError/)).toBeInTheDocument();`;
- add one test:

```tsx
test("every section is its own request, and an area filter sends the same keys to each", async () => {
  serve();
  renderPage("?area=feature:Booking");
  await screen.findByRole("region", { name: "Regressions and stability" });
  await vi.waitFor(() => expect(new Set(bodies.map((b) => b.sections[0]))).toEqual(new Set(["summary", "failure_causes", "regressions"])));
  expect(bodies.every((b) => b.test_keys?.[0] === "c".repeat(64))).toBe(true);
});
```

- [ ] **Step 6: Run the tests, then every dashboard check**

Run: `cd dashboard && npm run lint && npm run typecheck && npx vitest run --maxWorkers=4 && npm run build`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add dashboard/src/api/report.ts dashboard/src/pages/report/testFixtures.ts dashboard/src/pages/report/sections/RegressionsSection.tsx dashboard/src/pages/report/sections/RegressionsSection.test.tsx dashboard/src/pages/report/ReportPage.tsx dashboard/src/pages/report/ReportPage.test.tsx
git commit -m "feat(dashboard): report regressions and instability; the flaky table gives way" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard/src/api/report.ts dashboard/src/pages/report/testFixtures.ts dashboard/src/pages/report/sections/RegressionsSection.tsx dashboard/src/pages/report/sections/RegressionsSection.test.tsx dashboard/src/pages/report/ReportPage.tsx dashboard/src/pages/report/ReportPage.test.tsx dashboard/src/pages/report/sections/FlakySection.tsx
```

---

### Task 24: Phase 2 docs and the phase gate

**Files:**
- Modify: `platforms/ingestion-service/README.md` (the two sections; migration 016)
- Modify: `DESIGN.md` (Failure causes table, Regressions tables)

- [ ] **Step 1: README**

Extend the `### Report` subsection:

```markdown
- `failure_causes`: the failing rows of both periods grouped by the run view's signature (first line, ids and
  numbers replaced, SHA-1 to 12 characters; `none` without a message). The 50 biggest groups (ties: newer
  `last_seen`, then signature, `none` last) with `status` `new` or `recurring` against the previous period,
  `first_seen` over both periods, per-bucket counts, up to 10 tests each, `other` for the rest, and up to 20
  `resolved` signatures. Quarantined occurrences are flagged and still count.
- `regressions`: each test's last non-skipped attempt per run, as a sequence per (test, branch), for tests with a
  failing execution in either period: `newly_failing` and `fixed` (100 each), `longest_failing` (50; a streak older
  than the look-back is `failing_since_bounded`), `time_to_fix` (mean, median, p90; `bounded` counts lower bounds),
  and per bucket the tests executed, flaky tests and flips ("Instability (flips)", not the Flaky page's
  same-commit rule).
- Migration 016 adds `ix_test_results_failing` (partial, failing rows only), built `CONCURRENTLY` on PostgreSQL.
```

- [ ] **Step 2: DESIGN.md**

Under the Report entries from Task 15 add:

```markdown
### Report: Failure Causes and Regressions
Failure causes: horizontal bars of the 10 biggest causes (the headline cut to 80 characters; a new cause is striped and its label starts with "New ·", a recurring one is solid), then a table with a Status Pill per cause ("New" in the failed tone, "Recurring" neutral), "seen since at least <date>" when the first sighting is older than the data read, a sparkline with its numbers in off-screen text, and a 24px chevron (`aria-expanded`; 44px on coarse pointers) that opens the cause's tests on a Sidebar Mist band. Regressions: four plain tiles (Newly failing, Fixed, Still failing, Median time to fix with "(n at least)"), the "Instability (flips)" chart (bars of flaky tests, a dashed line for their share) with a note on how it differs from the Flaky page, and three tables whose test cells link to the history on that branch and whose dates link to the run. A start the look-back cut off reads "at least since".
```

- [ ] **Step 3: Phase gate**

Run:

```bash
cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest -q
cd ../test-management-service && SECRET_KEY=test .venv/Scripts/python -m pytest -q
cd ../../dashboard && npm run lint && npm run typecheck && npx vitest run --maxWorkers=4 && npm run build
node --test ../templates/github/qeos-run.test.mjs
```

Expected: all green; Task 21's measurements are in the README (P2 does not ship without them).

- [ ] **Step 4: Commit**

```bash
git add platforms/ingestion-service/README.md DESIGN.md
git commit -m "docs: report failure causes and regressions" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- platforms/ingestion-service/README.md DESIGN.md
```

Phase 2 ships here.

---

# Phase 3: by area, coverage and duration

### Task 25: Section `tests` (per-test numbers for the dashboard's area grouping)

**Files:**
- Modify: `platforms/ingestion-service/src/ingestion/analytics/report_streaks.py` (add `count_flips`)
- Modify: `platforms/ingestion-service/tests/unit/test_report_streaks.py` (append)
- Modify: `platforms/ingestion-service/src/ingestion/service/report_service.py`
- Test: `platforms/ingestion-service/tests/integration/test_report_tests_duration.py`

**Interfaces:**
- Consumes: Tasks 2–4, 19–20 (`_outcomes`, `build_sequences`).
- Produces: `report_streaks.count_flips(sequences) -> dict[str, int]` (flips summed over branches); `TESTS_COLUMNS` (the spec's column list), `TESTS_ROW_CAP = 50_000`; `tests_section(db, scope, runs, context) -> {"columns", "rows", "truncated"}` registered as `SECTION_BUILDERS["tests"]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_report_streaks.py`:

```python
from src.ingestion.analytics.report_streaks import count_flips


def test_flips_per_test_are_summed_over_branches():
    seqs = build_sequences([o("t1", 1, True), o("t1", 2, False), o("t1", 3, True),
                            o("t1", 1, True, branch="dev"), o("t1", 2, False, branch="dev"), o("t2", 1, True)])
    assert count_flips(seqs) == {"t1": 3, "t2": 0}
```

`tests/integration/test_report_tests_duration.py`:

```python
"""Sections tests and duration (spec: Section tests (P3), Section duration (P3))."""
from datetime import datetime, timezone

import pytest

from conftest import post_report, report_key


def at(month, day, hour=10):
    return datetime(2026, month, day, hour, tzinfo=timezone.utc)


@pytest.fixture
def seeded(project_role, report_now, seed_run):
    project_role()
    seed_run(at(9, 26), results=(("t1", "failed", 5),), duration_ms=5000)                       # previous period
    seed_run(at(10, 2), results=(("t1", "passed", 100), ("t2", "failed", 300), ("t3", "skipped", 0)), duration_ms=1000)
    seed_run(at(10, 3), results=(("t1", "failed", 120), ("t2", "passed", 200)), duration_ms=3000)
    seed_run(at(10, 3, 12), branch="dev", results=(("t1", "passed", 90),), duration_ms=2000)
    seed_run(at(10, 4), results=(("t1", "passed", 110),), duration_ms=4000)


def section(client, auth, name, **body):
    response = post_report(client, auth, sections=[name], **body)
    assert response.status_code == 200, response.text
    return response.json()[name]


def test_tests_rows_are_columnar(client, auth, seeded):
    t = section(client, auth, "tests")
    assert t["columns"] == ["test_key", "executions", "passed", "failed", "errored", "skipped", "flips", "pairs",
                            "duration_ms_sum", "last_status"]
    rows = {r[0]: dict(zip(t["columns"], r)) for r in t["rows"]}
    t1 = rows[report_key("t1")]
    # main: P(10-2) F(10-3) P(10-4) = 2 flips over 2 pairs; dev: one outcome = 0 pairs
    assert (t1["executions"], t1["passed"], t1["failed"], t1["flips"], t1["pairs"]) == (4, 3, 1, 2, 2)
    assert (t1["duration_ms_sum"], t1["last_status"]) == (420, "passed")
    t3 = rows[report_key("t3")]
    assert (t3["skipped"], t3["pairs"], t3["flips"], t3["last_status"]) == (1, 0, 0, "skipped")
    assert len(rows) == 3 and t["truncated"] is False
    assert [r[0] for r in t["rows"]] == sorted(rows)                    # by test key when not truncated


def test_tests_truncate_to_the_most_failing(client, auth, seeded, monkeypatch):
    from src.ingestion.service import report_service
    monkeypatch.setattr(report_service, "TESTS_ROW_CAP", 1)
    t = section(client, auth, "tests")
    assert t["truncated"] is True and len(t["rows"]) == 1
    assert t["rows"][0][0] in {report_key("t1"), report_key("t2")}      # a test with one failure, not t3


def test_tests_honour_test_keys(client, auth, seeded):
    assert [r[0] for r in section(client, auth, "tests", test_keys=[report_key("t2")])["rows"]] == [report_key("t2")]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/unit/test_report_streaks.py tests/integration/test_report_tests_duration.py -q`
Expected: FAIL (`count_flips` missing; `tests` is `null`).

- [ ] **Step 3: Implement**

Append to `report_streaks.py`:

```python
def count_flips(sequences: Dict[SequenceKey, List[Outcome]]) -> Dict[str, int]:
    """Flips per test, summed over its branches (the tests section's `flips`)."""
    out: Dict[str, int] = defaultdict(int)
    for (key, _), seq in sequences.items():
        out[key] += sum(1 for before, after in zip(seq, seq[1:]) if before.passed != after.passed)
    return dict(out)
```

Append to `report_service.py` (import `count_flips`):

```python
TESTS_COLUMNS = ["test_key", "executions", "passed", "failed", "errored", "skipped", "flips", "pairs",
                 "duration_ms_sum", "last_status"]
TESTS_ROW_CAP = 50_000


def _last_status(db: Session, scope: Scope, ids: list) -> Dict[str, str]:
    """Each test's newest result in the period (run start, run id, then the last attempt), skipped included."""
    ranked = (
        select(RunResult.test_key.label("test_key"), RunResult.status.label("status"),
               func.row_number().over(partition_by=RunResult.test_key,
                                      order_by=(Run.started_at.desc(), Run.id.desc(), RunResult.id.desc())).label("position"))
        .join(Run, Run.id == RunResult.run_id)
        .where(in_list(db, RunResult.run_id, ids, Integer), *key_filter(db, scope))
    ).subquery()
    return dict(db.execute(select(ranked.c.test_key, ranked.c.status).where(ranked.c.position == 1)).all())


def _pairs(db: Session, scope: Scope, ids: list) -> Dict[str, int]:
    """Sum over branches of (non-skipped outcomes - 1): the denominator of a flip rate."""
    rows = db.execute(
        select(RunResult.test_key, Run.branch, func.count(distinct(RunResult.run_id)))
        .join(Run, Run.id == RunResult.run_id)
        .where(in_list(db, RunResult.run_id, ids, Integer), RunResult.status != "skipped", *key_filter(db, scope))
        .group_by(RunResult.test_key, Run.branch)
    ).all()
    out: Dict[str, int] = {}
    for key, _, outcomes in rows:
        out[key] = out.get(key, 0) + max(int(outcomes) - 1, 0)
    return out


def tests_section(db: Session, scope: Scope, runs: List[ScopedRun], context: Context) -> dict:
    """One row per test executed in scope in the period, columnar (a key in every object would double the payload)."""
    current = {r.id: r for r in runs if r.current and r.id in context.counted}
    if not current:
        return {"columns": TESTS_COLUMNS, "rows": [], "truncated": False}
    ids = list(current)
    failures = _count(*FAILING)
    aggregated = db.execute(
        select(RunResult.test_key, func.count(RunResult.id), _count("passed"), _count("failed"), _count("errored"),
               _count("skipped"), func.sum(RunResult.duration_ms))
        .where(in_list(db, RunResult.run_id, ids, Integer), *key_filter(db, scope))
        .group_by(RunResult.test_key)
        .order_by(failures.desc(), RunResult.test_key)
        .limit(TESTS_ROW_CAP + 1)
    ).all()
    truncated = len(aggregated) > TESTS_ROW_CAP
    aggregated = aggregated[:TESTS_ROW_CAP]
    last = _last_status(db, scope, ids)
    pairs = _pairs(db, scope, ids)
    # Only a test with a failure can flip: the others have 0, so their sequences are never read
    failing = sorted(key for key, _, _, failed, errored, _, _ in aggregated if int(failed) + int(errored) > 0)
    flips = count_flips(build_sequences(_outcomes(db, ids, failing, current)))
    rows = [[key, n, int(p), int(f), int(e), int(s), flips.get(key, 0), pairs.get(key, 0), int(d or 0), last.get(key)]
            for key, n, p, f, e, s, d in aggregated]
    if not truncated:
        rows.sort(key=lambda row: row[0])
    return {"columns": TESTS_COLUMNS, "rows": rows, "truncated": truncated}


SECTION_BUILDERS["tests"] = tests_section
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/unit/test_report_streaks.py tests/integration/test_report_tests_duration.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add platforms/ingestion-service/src/ingestion/analytics/report_streaks.py platforms/ingestion-service/tests/unit/test_report_streaks.py platforms/ingestion-service/src/ingestion/service/report_service.py platforms/ingestion-service/tests/integration/test_report_tests_duration.py
git commit -m "feat(ingestion): report tests section, per-test numbers for the area grouping" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- platforms/ingestion-service/src/ingestion/analytics/report_streaks.py platforms/ingestion-service/tests/unit/test_report_streaks.py platforms/ingestion-service/src/ingestion/service/report_service.py platforms/ingestion-service/tests/integration/test_report_tests_duration.py
```

---

### Task 26: Section `duration`

**Files:**
- Modify: `platforms/ingestion-service/src/ingestion/service/report_service.py`
- Test: `platforms/ingestion-service/tests/integration/test_report_tests_duration.py` (append)

**Interfaces:**
- Consumes: Tasks 2–4 (`run_counts`, `_bucket_of`), Task 17 (`percentile`, `mean`).
- Produces: `duration_section(db, scope, runs, context) -> {"basis", "buckets", "previous"}` registered as `SECTION_BUILDERS["duration"]`.

- [ ] **Step 1: Write the failing tests** (append)

```python
def test_duration_is_run_wall_time_without_keys(client, auth, seeded):
    d = section(client, auth, "duration")
    assert d["basis"] == "run_wall_time" and len(d["buckets"]) == 7
    by_day = {b["date"]: b for b in d["buckets"]}
    assert by_day["2026-10-03"] == {"date": "2026-10-03", "runs": 2, "avg_ms": 2500, "p50_ms": 2500, "p90_ms": 2900, "max_ms": 3000}
    assert by_day["2026-10-01"] == {"date": "2026-10-01", "runs": 0, "avg_ms": None, "p50_ms": None, "p90_ms": None, "max_ms": None}
    assert d["previous"] == {"runs": 1, "avg_ms": 5000, "p50_ms": 5000, "p90_ms": 5000}


def test_duration_with_keys_is_time_in_those_tests(client, auth, seeded):
    d = section(client, auth, "duration", test_keys=[report_key("t1")])
    assert d["basis"] == "test_time"
    by_day = {b["date"]: b for b in d["buckets"]}
    assert (by_day["2026-10-03"]["runs"], by_day["2026-10-03"]["max_ms"]) == (2, 120)    # 120 on main, 90 on dev
    assert d["previous"]["avg_ms"] == 5


def test_duration_previous_is_null_without_runs(client, auth, seeded):
    assert section(client, auth, "duration", branch="dev")["previous"] is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest tests/integration/test_report_tests_duration.py -q`
Expected: FAIL (`duration` is `null`).

- [ ] **Step 3: Implement**

Append to `report_service.py` (import `mean, percentile` from `report_stats`):

```python
def duration_section(db: Session, scope: Scope, runs: List[ScopedRun], context: Context) -> dict:
    """Without test_keys: each run's wall time. With them: per run, the summed duration of the in-scope results --
    time in the selected tests, not wall time, since shards and workers run in parallel."""
    counted = [r for r in runs if r.id in context.counted]
    sums = run_counts(db, scope, counted) if scope.keys is not None else None

    def value(run: ScopedRun) -> int:
        return sums[run.id].duration_ms if sums is not None else run.duration_ms

    per_bucket: List[List[int]] = [[] for _ in context.starts]
    previous: List[int] = []
    for run in counted:
        if not run.current:
            previous.append(value(run))
            continue
        index = _bucket_of(scope, context, run)
        if index is not None:
            per_bucket[index].append(value(run))
    return {
        "basis": "run_wall_time" if scope.keys is None else "test_time",
        "buckets": [{"date": start.isoformat(), "runs": len(v), "avg_ms": mean(v), "p50_ms": percentile(v, 0.5),
                     "p90_ms": percentile(v, 0.9), "max_ms": max(v) if v else None}
                    for start, v in zip(context.starts, per_bucket)],
        "previous": {"runs": len(previous), "avg_ms": mean(previous), "p50_ms": percentile(previous, 0.5),
                     "p90_ms": percentile(previous, 0.9)} if previous else None,
    }


SECTION_BUILDERS["duration"] = duration_section
```

- [ ] **Step 4: Run the tests to verify they pass, then the suite**

Run: `cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add platforms/ingestion-service/src/ingestion/service/report_service.py platforms/ingestion-service/tests/integration/test_report_tests_duration.py
git commit -m "feat(ingestion): report duration section, wall time or time in the selected tests" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- platforms/ingestion-service/src/ingestion/service/report_service.py platforms/ingestion-service/tests/integration/test_report_tests_duration.py
```

---

### Task 27: `reportScope`: grouping by area, never-run cases, tests without a case

**Files:**
- Modify: `dashboard/src/api/report.ts` (types for `tests` and `duration`)
- Modify: `dashboard/src/lib/reportScope.ts`, `dashboard/src/lib/reportScope.test.ts` (append)

**Interfaces:**
- Consumes: Task 9 (`KeyScope`, `CaseAreas`, `CaseArea`).
- Produces:
  - Types: `TestsSection { columns: string[]; rows: (string | number | null)[][]; truncated: boolean }`, `DurationBucket`, `DurationSection { basis: "run_wall_time" | "test_time"; buckets: DurationBucket[]; previous: {...} | null }`; `Report.tests?`, `Report.duration?`.
  - `reportScope.ts`: `type Grouping = "feature" | "folder" | "label" | "suite"`, `GROUPINGS`, `interface TestRow { testKey; executions; passed; failed; errored; skipped; flips; pairs; durationMsSum; lastStatus: string | null }`, `decodeTests(t: TestsSection): TestRow[]`, `FEW_RUNS = 10`, `isFlaky(r: TestRow): boolean`, `interface AreaStats { key; label; linkedTests; testsRun; executions; passed; failed; errored; skipped; passRate: number | null; failures; failingTests; flakyTests; durationMsSum; fewRuns: boolean }`, `folderAtDepth(folder: string, depth: number): string`, `maxFolderDepth(areas): number`, `defaultFolderDepth(areas): number`, `groupsOf(c: CaseArea, grouping: Grouping, depth: number): { key: string; label: string }[]`, `groupByArea(areas, rows, grouping, depth): { groups: AreaStats[]; noCase: AreaStats | null }`, `sortWorstFirst(groups: AreaStats[]): AreaStats[]`, `neverRun(areas, rows, scope: KeyScope): CaseArea[]`, `unlinkedTestCount(areas, rows): number`.

- [ ] **Step 1: Add the types** (append to `api/report.ts`; add `tests?: TestsSection; duration?: DurationSection;` to `Report`)

```ts
/** Columnar per-test numbers (spec: Section tests); `reportScope.decodeTests` reads them by column name. */
export interface TestsSection { columns: string[]; rows: (string | number | null)[][]; truncated: boolean }

export interface DurationBucket {
  date: string; runs: number; avg_ms: number | null; p50_ms: number | null; p90_ms: number | null; max_ms: number | null;
}
export interface DurationSection {
  basis: "run_wall_time" | "test_time";
  buckets: DurationBucket[];
  previous: { runs: number; avg_ms: number | null; p50_ms: number | null; p90_ms: number | null } | null;
}
```

- [ ] **Step 2: Write the failing tests** (append to `lib/reportScope.test.ts`)

```ts
import type { TestsSection } from "../api/report";
import { decodeTests, defaultFolderDepth, folderAtDepth, groupByArea, isFlaky, neverRun, sortWorstFirst, unlinkedTestCount } from "./reportScope";

const COLUMNS = ["test_key", "executions", "passed", "failed", "errored", "skipped", "flips", "pairs", "duration_ms_sum", "last_status"];
const tests = (rows: (string | number | null)[][]): TestsSection => ({ columns: COLUMNS, rows, truncated: false });
// k(1) is linked from case 1 (Booking, features/booking, smoke, suite 12) and case 5 (Air); k(2) from case 2 (Air, .../air, suite 12)
const ROWS = tests([
  [k(1), 20, 18, 2, 0, 0, 6, 19, 4000, "passed"],
  [k(2), 4, 2, 2, 0, 0, 0, 3, 1000, "failed"],
  [k(9), 10, 10, 0, 0, 0, 0, 9, 500, "passed"],       // linked to no case
]);

test("rows decode by column name and flaky needs 5 outcomes and a flip rate of 0.3", () => {
  const [first] = decodeTests(ROWS);
  expect(first).toEqual({ testKey: k(1), executions: 20, passed: 18, failed: 2, errored: 0, skipped: 0, flips: 6, pairs: 19,
    durationMsSum: 4000, lastStatus: "passed" });
  expect(isFlaky(first)).toBe(true);                                       // 6 / 19 >= 0.3, 20 outcomes
  expect(isFlaky({ ...first, flips: 5 })).toBe(false);
  expect(isFlaky({ ...first, executions: 4, skipped: 0, flips: 3, pairs: 3 })).toBe(false);
});

test("folders cut to a depth; the default depth is the shallowest with two groups", () => {
  expect(folderAtDepth("features/booking/air", 2)).toBe("features/booking");
  expect(folderAtDepth("features", 3)).toBe("features");
  expect(defaultFolderDepth(AREAS)).toBe(2);                                // depth 1 is all "features"
});

test("by feature: a test linked from two features counts in both; unlinked tests form No case", () => {
  const { groups, noCase } = groupByArea(AREAS, decodeTests(ROWS), "feature", 1);
  const air = groups.find((g) => g.label === "Air")!;
  const booking = groups.find((g) => g.label === "Booking")!;
  expect(air).toMatchObject({ linkedTests: 2, testsRun: 2, executions: 24, failures: 4, failingTests: 2, flakyTests: 1, fewRuns: false });
  expect(air.passRate).toBeCloseTo(20 / 24);
  expect(booking).toMatchObject({ linkedTests: 2, testsRun: 1, executions: 20 });  // k(3) never ran
  expect(noCase).toMatchObject({ label: "No case", testsRun: 1, executions: 10 });
});

test("by label and by suite; by folder at a depth", () => {
  expect(groupByArea(AREAS, decodeTests(ROWS), "label", 1).groups.map((g) => g.label)).toEqual(["smoke"]);
  const suite = groupByArea(AREAS, decodeTests(ROWS), "suite", 1).groups;
  expect(suite.map((g) => [g.key, g.label, g.testsRun])).toEqual([["suite:12", "Regression", 2]]);
  const folders = groupByArea(AREAS, decodeTests(ROWS), "folder", 2).groups.map((g) => g.label).sort();
  expect(folders).toEqual(["features/booking", "features/bookingx"]);
});

test("worst first: lowest pass rate among areas with 10+ executions, then most failures; few runs last", () => {
  const a = { key: "a", label: "a", passRate: 0.9, executions: 50, failures: 5, fewRuns: false };
  const b = { key: "b", label: "b", passRate: 0.5, executions: 12, failures: 6, fewRuns: false };
  const c = { key: "c", label: "c", passRate: 0.0, executions: 3, failures: 3, fewRuns: true };
  const d = { key: "d", label: "d", passRate: 0.9, executions: 40, failures: 9, fewRuns: false };
  const sorted = sortWorstFirst([a, b, c, d].map((x) => ({ linkedTests: 0, testsRun: 0, passed: 0, failed: 0, errored: 0,
    skipped: 0, failingTests: 0, flakyTests: 0, durationMsSum: 0, ...x })));
  expect(sorted.map((g) => g.key)).toEqual(["b", "d", "a", "c"]);
});

test("automated cases never run, in scope; and the count of tests without a case", () => {
  const rows = decodeTests(ROWS);
  expect(neverRun(AREAS, rows, { kind: "all" }).map((c) => c.number)).toEqual([3]);
  expect(neverRun(AREAS, rows, { kind: "keys", keys: [k(1), k(2)] })).toEqual([]);
  expect(unlinkedTestCount(AREAS, rows)).toBe(1);
});
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd dashboard && npx vitest run src/lib/reportScope.test.ts`
Expected: FAIL (exports missing).

- [ ] **Step 4: Implement** (append to `lib/reportScope.ts`; add `import type { TestsSection } from "../api/report";`)

```ts
export type Grouping = "feature" | "folder" | "label" | "suite";
export const GROUPINGS: Grouping[] = ["feature", "folder", "label", "suite"];

export interface TestRow {
  testKey: string;
  executions: number;
  passed: number;
  failed: number;
  errored: number;
  skipped: number;
  flips: number;
  pairs: number;
  durationMsSum: number;
  lastStatus: string | null;
}

/** The tests section's rows, read by column name so a new column never shifts the others. */
export function decodeTests(t: TestsSection): TestRow[] {
  const at = (name: string) => t.columns.indexOf(name);
  const i = {
    key: at("test_key"), executions: at("executions"), passed: at("passed"), failed: at("failed"), errored: at("errored"),
    skipped: at("skipped"), flips: at("flips"), pairs: at("pairs"), duration: at("duration_ms_sum"), last: at("last_status"),
  };
  const n = (row: (string | number | null)[], index: number) => Number(row[index] ?? 0);
  return t.rows.map((row) => ({
    testKey: String(row[i.key]).toLowerCase(), executions: n(row, i.executions), passed: n(row, i.passed),
    failed: n(row, i.failed), errored: n(row, i.errored), skipped: n(row, i.skipped), flips: n(row, i.flips),
    pairs: n(row, i.pairs), durationMsSum: n(row, i.duration), lastStatus: row[i.last] === null ? null : String(row[i.last]),
  }));
}

/** The Flaky page's defaults applied to the flips signal (spec: Section 3; plan Ruling 7). */
const FLAKY_MIN_OUTCOMES = 5;
const FLAKY_MIN_FLIP_RATE = 0.3;
export const FEW_RUNS = 10;

export function isFlaky(r: TestRow): boolean {
  return r.executions - r.skipped >= FLAKY_MIN_OUTCOMES && r.pairs > 0 && r.flips / r.pairs >= FLAKY_MIN_FLIP_RATE;
}

export interface AreaStats {
  key: string;
  label: string;
  linkedTests: number;
  testsRun: number;
  executions: number;
  passed: number;
  failed: number;
  errored: number;
  skipped: number;
  passRate: number | null;
  failures: number;
  failingTests: number;
  flakyTests: number;
  durationMsSum: number;
  fewRuns: boolean;
}

export function folderAtDepth(folder: string, depth: number): string {
  return folder.split("/").slice(0, depth).join("/");
}

export function maxFolderDepth(areas: CaseAreas): number {
  return Math.max(1, ...areas.cases.filter((c) => c.folder).map((c) => c.folder!.split("/").length));
}

/** The shallowest depth that gives at least two folder groups; the deepest when none does. */
export function defaultFolderDepth(areas: CaseAreas): number {
  const deepest = maxFolderDepth(areas);
  for (let depth = 1; depth <= deepest; depth++) {
    const groups = new Set(areas.cases.filter((c) => c.folder).map((c) => folderAtDepth(c.folder!, depth)));
    if (groups.size >= 2) return depth;
  }
  return deepest;
}

export function groupsOf(c: CaseArea, grouping: Grouping, depth: number, suites: Map<number, string>): { key: string; label: string }[] {
  if (grouping === "feature") return c.feature ? [{ key: `feature:${c.feature}`, label: c.feature }] : [];
  if (grouping === "folder") {
    if (!c.folder) return [];
    const path = folderAtDepth(c.folder, depth);
    return [{ key: `folder:${path}`, label: path }];
  }
  if (grouping === "label") return c.labels.map((l) => ({ key: `label:${l}`, label: l }));
  return c.suiteIds.map((id) => ({ key: `suite:${id}`, label: suites.get(id) ?? `#${id}` }));
}

function empty(key: string, label: string): AreaStats {
  return { key, label, linkedTests: 0, testsRun: 0, executions: 0, passed: 0, failed: 0, errored: 0, skipped: 0,
    passRate: null, failures: 0, failingTests: 0, flakyTests: 0, durationMsSum: 0, fewRuns: true };
}

function add(stats: AreaStats, r: TestRow) {
  stats.testsRun += 1;
  stats.executions += r.executions;
  stats.passed += r.passed;
  stats.failed += r.failed;
  stats.errored += r.errored;
  stats.skipped += r.skipped;
  stats.failures += r.failed + r.errored;
  stats.failingTests += r.failed + r.errored > 0 ? 1 : 0;
  stats.flakyTests += isFlaky(r) ? 1 : 0;
  stats.durationMsSum += r.durationMsSum;
}

function finish(stats: AreaStats): AreaStats {
  const considered = stats.executions - stats.skipped;
  return { ...stats, passRate: considered > 0 ? stats.passed / considered : null, fewRuns: stats.executions < FEW_RUNS };
}

/** Ingestion's per-test rows grouped by the cases' areas. A test linked from cases in several groups (labels,
 *  suites, or two features) counts in each: the groups overlap and are not summed. */
export function groupByArea(areas: CaseAreas, rows: TestRow[], grouping: Grouping, depth: number):
  { groups: AreaStats[]; noCase: AreaStats | null } {
  const suites = new Map(areas.suites.map((s) => [s.id, s.name]));
  const groups = new Map<string, AreaStats>();
  const linked = new Map<string, Set<string>>();       // group key -> linked test keys
  const ofKey = new Map<string, Set<string>>();        // test key -> group keys
  const linkedKeys = new Set<string>();
  for (const c of areas.cases) {
    if (!c.testKey) continue;
    const key = c.testKey.toLowerCase();
    linkedKeys.add(key);
    for (const g of groupsOf(c, grouping, depth, suites)) {
      if (!groups.has(g.key)) groups.set(g.key, empty(g.key, g.label));
      if (!linked.has(g.key)) linked.set(g.key, new Set());
      linked.get(g.key)!.add(key);
      if (!ofKey.has(key)) ofKey.set(key, new Set());
      ofKey.get(key)!.add(g.key);
    }
  }
  let noCase: AreaStats | null = null;
  for (const r of rows) {
    if (!linkedKeys.has(r.testKey)) {
      noCase ??= empty("none", "No case");
      add(noCase, r);
      continue;
    }
    for (const g of ofKey.get(r.testKey) ?? []) add(groups.get(g)!, r);
  }
  const out = [...groups.values()].map((g) => finish({ ...g, linkedTests: linked.get(g.key)?.size ?? 0 }));
  return { groups: sortWorstFirst(out), noCase: noCase ? finish(noCase) : null };
}

/** Lowest pass rate first among areas with at least FEW_RUNS executions, then most failures; the others last. */
export function sortWorstFirst(groups: AreaStats[]): AreaStats[] {
  return [...groups].sort((a, b) => {
    if (a.fewRuns !== b.fewRuns) return a.fewRuns ? 1 : -1;
    const rate = (a.passRate ?? 2) - (b.passRate ?? 2);
    if (rate !== 0) return rate;
    if (a.failures !== b.failures) return b.failures - a.failures;
    return a.label.localeCompare(b.label);
  });
}

/** Automated cases (in the area and suite filters) whose test did not run in the period, by case number. */
export function neverRun(areas: CaseAreas, rows: TestRow[], scope: KeyScope): CaseArea[] {
  const ran = new Set(rows.map((r) => r.testKey));
  const inScope = scope.kind === "keys" ? new Set(scope.keys) : null;
  return areas.cases
    .filter((c) => c.testKey && !ran.has(c.testKey.toLowerCase()) && (!inScope || inScope.has(c.testKey.toLowerCase())))
    .sort((a, b) => a.number - b.number);
}

export function unlinkedTestCount(areas: CaseAreas, rows: TestRow[]): number {
  const linked = new Set(areas.cases.filter((c) => c.testKey).map((c) => c.testKey!.toLowerCase()));
  return rows.filter((r) => !linked.has(r.testKey)).length;
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd dashboard && npx vitest run src/lib/reportScope.test.ts && npm run lint && npm run typecheck`
Expected: PASS. (With `AREAS` from Task 9: k(1) is linked from cases 1 and 5, so "Air" holds k(1) and k(2); "Booking" holds k(1) and k(3).)

- [ ] **Step 6: Commit**

```bash
git add dashboard/src/api/report.ts dashboard/src/lib/reportScope.ts dashboard/src/lib/reportScope.test.ts
git commit -m "feat(dashboard): group the report's per-test rows by area; never-run and unlinked tests" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard/src/api/report.ts dashboard/src/lib/reportScope.ts dashboard/src/lib/reportScope.test.ts
```

---

### Task 28: Section 3 `AreaSection`

Invoke the `ui-ux-pro-max` skill before writing the component or editing `index.css`.

**Files:**
- Modify: `dashboard/src/pages/report/testFixtures.ts` (`TESTS_REPORT`, `AREAS_FIXTURE`)
- Create: `dashboard/src/pages/report/useGrouping.ts`
- Create: `dashboard/src/pages/report/sections/AreaSection.tsx`, `AreaSection.test.tsx`
- Modify: `dashboard/src/index.css`

**Interfaces:**
- Consumes: Tasks 9, 11, 27; `SortableTh`, `sortRows`, `nextSort`, `StatusPill`, `caseAreasMessage`.
- Produces:
  - `useGrouping(areas?: CaseAreas): { grouping: Grouping; depth: number; setGrouping(g: Grouping): void; setDepth(d: number): void }` (URL `group` and `depth`, view settings that "Clear all" keeps).
  - `AreaSection({ projectId; gate; query; caseAreas: { data?: CaseAreas; error: unknown; refetch(): unknown }; onResetFilters })`; pure `areasCsv(groups: AreaStats[], noCase: AreaStats | null): string`, `casesLink(projectId: number, g: AreaStats): string`.

- [ ] **Step 1: Fixtures and failing tests**

Append to `testFixtures.ts`:

```ts
import type { CaseAreas } from "../../api/cases";

const key = (n: number) => n.toString(16).padStart(64, "0");

export const AREAS_FIXTURE: CaseAreas = {
  generatedAt: "v1", counts: { cases: 4, linked: 3, manual: 1 },
  folders: ["features/booking", "features/payments"], features: ["Booking", "Payments"], labels: ["smoke"],
  suites: [{ id: 12, name: "Regression" }],
  cases: [
    { number: 1, title: "Book one-way", testKey: key(1), folder: "features/booking", feature: "Booking", labels: ["smoke"], suiteIds: [12] },
    { number: 2, title: "Pay by card", testKey: key(2), folder: "features/payments", feature: "Payments", labels: [], suiteIds: [12] },
    { number: 3, title: "Refund", testKey: key(3), folder: "features/payments", feature: "Payments", labels: [], suiteIds: [] },
    { number: 4, title: "Manual check", testKey: null, folder: null, feature: null, labels: [], suiteIds: [] },
  ],
};

export const TESTS_REPORT = {
  ...SUMMARY_REPORT,
  tests: {
    columns: ["test_key", "executions", "passed", "failed", "errored", "skipped", "flips", "pairs", "duration_ms_sum", "last_status"],
    rows: [[key(1), 30, 30, 0, 0, 0, 0, 29, 90000, "passed"], [key(2), 20, 10, 10, 0, 0, 8, 19, 400000, "failed"],
           [key(9), 5, 5, 0, 0, 0, 0, 4, 1000, "passed"]],
    truncated: false,
  },
  duration: {
    basis: "run_wall_time" as const,
    buckets: [{ date: "2026-10-07", runs: 41, avg_ms: 702000, p50_ms: 650000, p90_ms: 1100000, max_ms: 1500000 },
              { date: "2026-10-08", runs: 0, avg_ms: null, p50_ms: null, p90_ms: null, max_ms: null }],
    previous: { runs: 398, avg_ms: 690000, p50_ms: 640000, p90_ms: 1050000 },
  },
};
```

`AreaSection.test.tsx`:

```tsx
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import type { Gate } from "../useReportRequest";
import { AREAS_FIXTURE, TESTS_REPORT } from "../testFixtures";
import AreaSection, { areasCsv } from "./AreaSection";
import { decodeTests, groupByArea } from "../../../lib/reportScope";

const READY: Gate = { state: "ready", base: {} as never, key: [] };

function Search() {
  return <output data-testid="search">{useLocation().search}</output>;
}

function show(search = "", caseAreas = { data: AREAS_FIXTURE, error: null, refetch: vi.fn() }) {
  render(
    <MemoryRouter initialEntries={[`/projects/42/report${search}`]}>
      <Routes><Route path="/projects/:projectId/report" element={<>
        <AreaSection projectId={42} gate={READY} caseAreas={caseAreas} onResetFilters={vi.fn()}
          query={{ data: TESTS_REPORT, error: null, isPending: false, refetch: vi.fn() }} />
        <Search />
      </>} /></Routes>
    </MemoryRouter>,
  );
}

test("by feature, worst first, with links to the Cases list and the No case row", () => {
  show();
  const table = screen.getByRole("table", { name: /by area/i });
  const rows = within(table).getAllByRole("row");
  expect(rows[1]).toHaveTextContent("Payments");                       // 50% pass rate
  expect(within(rows[1]).getByRole("link", { name: "Payments" })).toHaveAttribute("href", "/projects/42/cases?feature=Payments");
  expect(rows[2]).toHaveTextContent("Booking");
  expect(rows[rows.length - 1]).toHaveTextContent(/tests without a case/i);
  expect(within(rows[1]).getAllByRole("cell")[7]).toHaveTextContent("1");   // Flaky tests: 8 flips over 19 pairs
});

test("the grouping is a pressed button kept in the URL; folder adds a depth; labels warn that groups overlap", async () => {
  show();
  await userEvent.click(screen.getByRole("button", { name: "Folder" }));
  expect(screen.getByTestId("search").textContent).toBe("?group=folder");
  expect(screen.getByRole("button", { name: "Folder" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByLabelText("Depth")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Label" }));
  expect(screen.getByText(/groups overlap and are not summed/i)).toBeInTheDocument();
});

test("columns sort with aria-sort", async () => {
  show();
  await userEvent.click(screen.getByRole("button", { name: "Executions" }));
  expect(screen.getByRole("columnheader", { name: /executions/i })).toHaveAttribute("aria-sort", "descending");
});

test("case-areas failing shows its error here", () => {
  show("", { data: undefined as never, error: new Error("x"), refetch: vi.fn() });
  expect(screen.getByText("Cases could not be loaded")).toBeInTheDocument();
});

test("the CSV has one row per area", () => {
  const { groups, noCase } = groupByArea(AREAS_FIXTURE, decodeTests(TESTS_REPORT.tests), "feature", 1);
  const lines = areasCsv(groups, noCase).split("\r\n");
  expect(lines[0]).toBe("area,linked_tests,tests_run,executions,pass_rate,failures,failing_tests,flaky_tests,few_runs");
  expect(lines).toHaveLength(4);                                       // Payments, Booking, No case
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd dashboard && npx vitest run src/pages/report/sections/AreaSection.test.tsx`
Expected: FAIL (modules missing).

- [ ] **Step 3: Write `useGrouping.ts`**

```ts
import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import type { CaseAreas } from "../../api/cases";
import { GROUPINGS, type Grouping, defaultFolderDepth, maxFolderDepth } from "../../lib/reportScope";

/** Sections 3 and 5 share one grouping, kept in the URL (`group`, `depth`) as a view setting: "Clear all" keeps it. */
export function useGrouping(areas?: CaseAreas) {
  const [params, setParams] = useSearchParams();
  const raw = params.get("group") ?? "";
  const grouping: Grouping = (GROUPINGS as string[]).includes(raw) ? (raw as Grouping) : "feature";
  const deepest = areas ? maxFolderDepth(areas) : 1;
  const asked = Number(params.get("depth"));
  const depth = Number.isInteger(asked) && asked >= 1 && asked <= deepest ? asked : areas ? defaultFolderDepth(areas) : 1;
  const set = useCallback((key: string, value: string) => setParams((prev) => {
    const next = new URLSearchParams(prev);
    if (value) next.set(key, value);
    else next.delete(key);
    return next;
  }), [setParams]);
  return {
    grouping,
    depth,
    deepest,
    setGrouping: (g: Grouping) => set("group", g === "feature" ? "" : g),
    setDepth: (d: number) => set("depth", String(d)),
  };
}
```

- [ ] **Step 4: Write `sections/AreaSection.tsx`**

```tsx
import { useState } from "react";
import { Link } from "react-router-dom";
import { Download } from "lucide-react";
import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatPassRate } from "../../../api/analytics";
import type { CaseAreas } from "../../../api/cases";
import { DataTableDisclosure } from "../../../components/ChartKit";
import SortableTh from "../../../components/SortableTh";
import { downloadCsv, toCsv } from "../../../lib/csv";
import { type AreaStats, GROUPINGS, type Grouping, decodeTests, groupByArea } from "../../../lib/reportScope";
import { type SortState, nextSort, sortRows } from "../../../lib/sort";
import ReportSection, { type SectionQuery } from "../ReportSection";
import { useGrouping } from "../useGrouping";
import { type Gate, caseAreasMessage } from "../useReportRequest";

const number = new Intl.NumberFormat();
const NAMES: Record<Grouping, string> = { feature: "Feature", folder: "Folder", label: "Label", suite: "Suite" };
const WORST_IN_CHART = 15;
type Col = "label" | "linkedTests" | "testsRun" | "executions" | "passRate" | "failures" | "failingTests" | "flakyTests";
const TEXT_COLS: Col[] = ["label"];

export function casesLink(projectId: number, g: AreaStats): string {
  const [kind, ...rest] = g.key.split(":");
  const value = rest.join(":");
  if (kind === "suite") return `/projects/${projectId}/suites/${value}`;
  return `/projects/${projectId}/cases?${kind}=${encodeURIComponent(value)}`;
}

export function areasCsv(groups: AreaStats[], noCase: AreaStats | null): string {
  return toCsv(["area", "linked_tests", "tests_run", "executions", "pass_rate", "failures", "failing_tests", "flaky_tests", "few_runs"],
    [...groups, ...(noCase ? [noCase] : [])].map((g) => [g.label, g.linkedTests, g.testsRun, g.executions, g.passRate,
      g.failures, g.failingTests, g.flakyTests, String(g.fewRuns)]));
}

/** The grouping control shared by Sections 3 and 5: a segmented group of pressed buttons, plus a depth for folders. */
export function GroupingControl({ areas }: { areas?: CaseAreas }) {
  const { grouping, depth, deepest, setGrouping, setDepth } = useGrouping(areas);
  return (
    <div className="report-grouping no-print">
      <div role="group" aria-labelledby="report-group-by" className="segmented">
        <span id="report-group-by" className="segmented-label">Group by</span>
        {GROUPINGS.map((g) => (
          <button key={g} type="button" aria-pressed={grouping === g} onClick={() => setGrouping(g)}>{NAMES[g]}</button>
        ))}
      </div>
      {grouping === "folder" && (
        <label>Depth
          <select value={depth} onChange={(e) => setDepth(Number(e.target.value))}>
            {Array.from({ length: deepest }, (_, i) => i + 1).map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </label>
      )}
    </div>
  );
}

interface Props {
  projectId: number;
  gate: Gate;
  query: SectionQuery;
  caseAreas: { data?: CaseAreas; error: unknown; refetch: () => unknown };
  onResetFilters: () => void;
}

/** Section 3 (spec: Section 3: By area): ingestion's per-test rows grouped by the cases' feature, folder, label or
 *  suite in the dashboard (ADR-026). */
export default function AreaSection({ projectId, gate, query, caseAreas, onResetFilters }: Props) {
  const { grouping, depth } = useGrouping(caseAreas.data);
  const [sort, setSort] = useState<SortState<Col> | null>(null);
  const blocked = caseAreas.error != null;
  const sectionGate: Gate = blocked
    ? { state: "blocked", message: caseAreasMessage(caseAreas.error), error: caseAreas.error, retry: () => void caseAreas.refetch() }
    : !caseAreas.data && gate.state === "ready" ? { state: "wait" } : gate;

  return (
    <ReportSection
      id="report-areas"
      title="By area"
      gate={sectionGate}
      query={query}
      height={380}
      onResetFilters={onResetFilters}
      actions={<GroupingControl areas={caseAreas.data} />}
    >
      {(r) => {
        const areas = caseAreas.data!;
        const { groups, noCase } = groupByArea(areas, decodeTests(r.tests!), grouping, depth);
        const shown = sort ? sortRows(groups, sort, (g, k) => g[k]) : groups;
        const worst = groups.filter((g) => !g.fewRuns && g.passRate !== null).slice(0, WORST_IN_CHART);
        const chart = worst.map((g) => ({ label: g.label, rate: Math.round((g.passRate ?? 0) * 1000) / 10, failures: g.failures }));
        const caption = worst.length
          ? `${worst.length} areas with at least 10 executions; the lowest pass rate is ${worst[0].label} at ${formatPassRate(worst[0].passRate)} with ${number.format(worst[0].failures)} failures.`
          : "No area has 10 or more executions in this period.";
        const onSort = (key: Col) => setSort(nextSort(sort ?? { key: "passRate", dir: "asc" }, key, TEXT_COLS.includes(key) ? "asc" : "desc"));
        return (
          <>
            {(grouping === "label" || grouping === "suite") && (
              <p className="muted report-note">A test in several {grouping === "label" ? "labels" : "suites"} counts in each: the groups overlap and are not summed.</p>
            )}
            {r.tests!.truncated && <p className="muted report-note">More than 50,000 tests ran; only the 50,000 with the most failures are grouped.</p>}
            <figure className="chart-figure" aria-labelledby="report-areas">
              <figcaption className="sr-only">{caption}</figcaption>
              <ResponsiveContainer width="100%" height={Math.max(160, chart.length * 28)}>
                <BarChart data={chart} layout="vertical" margin={{ left: 8, right: 64 }} accessibilityLayer>
                  <CartesianGrid stroke="var(--grid)" horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} stroke="var(--text-muted)" tick={{ fill: "var(--text-secondary)", fontSize: 12 }} />
                  <YAxis type="category" dataKey="label" width={200} stroke="var(--text-muted)" tick={{ fill: "var(--text-secondary)", fontSize: 12 }} />
                  <Tooltip contentStyle={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 6 }} />
                  <Bar dataKey="rate" name="Pass rate (%)" fill="var(--series-1)" radius={[0, 4, 4, 0]}>
                    <LabelList dataKey="failures" position="right" fill="var(--text-secondary)" fontSize={12}
                      formatter={(v: number) => `${number.format(v)} failures`} />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </figure>
            <DataTableDisclosure name="pass rate of the worst areas">
              <table className="data">
                <thead><tr><th scope="col">Area</th><th scope="col" className="num">Pass rate</th><th scope="col" className="num">Failures</th></tr></thead>
                <tbody>{worst.map((g) => <tr key={g.key}><td>{g.label}</td><td className="num">{formatPassRate(g.passRate)}</td><td className="num">{number.format(g.failures)}</td></tr>)}</tbody>
              </table>
            </DataTableDisclosure>
            <div className="button-row no-print">
              <button type="button" onClick={() => downloadCsv(`report-${projectId}-${r.period.from}-${r.period.to}-areas.csv`, areasCsv(groups, noCase))}>
                <Download size={15} aria-hidden="true" /> Areas CSV
              </button>
            </div>
            <table className="data">
              <caption className="sr-only">By area ({NAMES[grouping].toLowerCase()})</caption>
              <thead><tr>
                <SortableTh label="Area" sortKey="label" sort={sort} onSort={onSort} />
                <SortableTh label="Linked tests" sortKey="linkedTests" sort={sort} onSort={onSort} className="num hide-narrow" />
                <SortableTh label="Tests run" sortKey="testsRun" sort={sort} onSort={onSort} className="num hide-narrow" />
                <SortableTh label="Executions" sortKey="executions" sort={sort} onSort={onSort} className="num" />
                <SortableTh label="Pass rate" sortKey="passRate" sort={sort} onSort={onSort} className="num" />
                <SortableTh label="Failures" sortKey="failures" sort={sort} onSort={onSort} className="num" />
                <SortableTh label="Failing tests" sortKey="failingTests" sort={sort} onSort={onSort} className="num hide-narrow" />
                <SortableTh label="Flaky tests" sortKey="flakyTests" sort={sort} onSort={onSort} className="num hide-narrow" />
              </tr></thead>
              <tbody>
                {shown.map((g) => (
                  <tr key={g.key}>
                    <td className="wrap-anywhere">
                      <Link to={casesLink(projectId, g)}>{g.label}</Link>
                      {g.fewRuns && <span className="muted"> · few runs</span>}
                    </td>
                    <td className="num hide-narrow">{number.format(g.linkedTests)}</td>
                    <td className="num hide-narrow">{number.format(g.testsRun)}</td>
                    <td className="num">{number.format(g.executions)}</td>
                    <td className="num">{formatPassRate(g.passRate)}</td>
                    <td className="num">{number.format(g.failures)}</td>
                    <td className="num hide-narrow">{number.format(g.failingTests)}</td>
                    <td className="num hide-narrow">{number.format(g.flakyTests)}</td>
                  </tr>
                ))}
                {noCase && (
                  <tr>
                    <td><span className="muted">Tests without a case</span></td>
                    <td className="num hide-narrow">—</td>
                    <td className="num hide-narrow">{number.format(noCase.testsRun)}</td>
                    <td className="num">{number.format(noCase.executions)}</td>
                    <td className="num">{formatPassRate(noCase.passRate)}</td>
                    <td className="num">{number.format(noCase.failures)}</td>
                    <td className="num hide-narrow">{number.format(noCase.failingTests)}</td>
                    <td className="num hide-narrow">{number.format(noCase.flakyTests)}</td>
                  </tr>
                )}
              </tbody>
            </table>
            <p className="muted report-note">A flaky test here has at least 5 outcomes and flips in at least 30% of consecutive pairs.</p>
          </>
        );
      }}
    </ReportSection>
  );
}
```

Notes for the implementer:
- `NarrowMeta` must bring back the `hide-narrow` columns on phones (DESIGN.md, Narrow Meta): add `<NarrowMeta items={[{ label: "Tests run", value: ... }, { label: "Failing tests", value: ... }, { label: "Flaky tests", value: ... }]} />` in the first cell of each row, as in `SummarySection`.
- The first column is headed "Area", not the grouping's name, so its sort button never shares a name with a "Group by" button.
- The `Bar` `LabelList` formatter's parameter type comes from Recharts; if the typecheck rejects `(v: number)`, type it as `(v: unknown) => \`${number.format(Number(v))} failures\``.

- [ ] **Step 5: Styles** (append to `index.css`)

```css
.report-grouping { display: flex; gap: var(--space-3); align-items: flex-end; flex-wrap: wrap; }
.report-grouping label { display: flex; flex-direction: column; gap: var(--space-1); font-size: 13px; font-weight: 500; color: var(--text-secondary); }
.segmented { display: inline-flex; align-items: center; gap: 0; }
.segmented-label { font-size: 13px; font-weight: 500; color: var(--text-secondary); margin-right: var(--space-2); }
.segmented button { border-radius: 0; margin-left: -1px; }
.segmented button:first-of-type { border-radius: var(--radius-sm) 0 0 var(--radius-sm); }
.segmented button:last-of-type { border-radius: 0 var(--radius-sm) var(--radius-sm) 0; }
.segmented button[aria-pressed="true"] { border-color: var(--accent); color: var(--accent-text); background: var(--accent-soft); font-weight: 600; position: relative; }
@media (pointer: coarse) { .segmented button { min-height: 44px; } }
```

If the Cases page's "Group by" segmented control (DESIGN.md: "Cases: Group by Feature or Scenario") already has CSS classes, reuse those instead of adding `.segmented`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd dashboard && npx vitest run src/pages/report && npm run lint && npm run typecheck`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add dashboard/src/pages/report/testFixtures.ts dashboard/src/pages/report/useGrouping.ts dashboard/src/pages/report/sections/AreaSection.tsx dashboard/src/pages/report/sections/AreaSection.test.tsx dashboard/src/index.css
git commit -m "feat(dashboard): report by area: feature, folder, label or suite, worst first" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard/src/pages/report/testFixtures.ts dashboard/src/pages/report/useGrouping.ts dashboard/src/pages/report/sections/AreaSection.tsx dashboard/src/pages/report/sections/AreaSection.test.tsx dashboard/src/index.css
```

---

### Task 29: Section 5 `CoverageDurationSection`; the page loads case-areas always

Invoke the `ui-ux-pro-max` skill before writing the component or changing the page.

**Files:**
- Create: `dashboard/src/pages/report/sections/CoverageDurationSection.tsx`, `CoverageDurationSection.test.tsx`
- Modify: `dashboard/src/pages/report/ReportPage.tsx`, `ReportPage.test.tsx`

**Interfaces:**
- Consumes: Tasks 27–28 (`groupByArea`, `neverRun`, `unlinkedTestCount`, `folderAtDepth`, `useGrouping`, `GroupingControl`), `resolveScope`, `formatDuration`.
- Produces: `CoverageDurationSection({ projectId; gate; testsQuery: SectionQuery; durationQuery: SectionQuery; caseAreas; filters: ReportFilters; onResetFilters })`; pure `neverRunCsv(cases: CaseArea[]): string`, `durationCsv(r: Report): string`, `slowestAreasCsv(groups: AreaStats[]): string`, `coverageGroups(areas, grouping, depth): { label: string; linked: number; manual: number }[]`.

- [ ] **Step 1: Write the failing tests**

```tsx
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { parseReportFilters } from "../useReportFilters";
import type { Gate } from "../useReportRequest";
import { AREAS_FIXTURE, TESTS_REPORT } from "../testFixtures";
import CoverageDurationSection, { coverageGroups, durationCsv, neverRunCsv } from "./CoverageDurationSection";

const READY: Gate = { state: "ready", base: {} as never, key: [] };
const filters = (q = "") => parseReportFilters(new URLSearchParams(q), "2026-10-08").filters;
const q = { data: TESTS_REPORT, error: null, isPending: false, refetch: vi.fn() };

function show(report = TESTS_REPORT, f = filters()) {
  render(
    <MemoryRouter>
      <CoverageDurationSection projectId={42} gate={READY} testsQuery={{ ...q, data: report }} durationQuery={{ ...q, data: report }}
        caseAreas={{ data: AREAS_FIXTURE, error: null, refetch: vi.fn() }} filters={f} onResetFilters={vi.fn()} />
    </MemoryRouter>,
  );
}

test("coverage tiles and the never-run table under the current filters", () => {
  show();
  expect(screen.getByRole("group", { name: "Active cases 4" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Linked (automated) 3" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Manual 1" })).toBeInTheDocument();
  expect(screen.getByRole("group", { name: "Automated, not run in this period 1" })).toBeInTheDocument();
  const table = screen.getByRole("table", { name: /automated, not run in this period/i });
  expect(within(table).getByRole("link", { name: "TC-3" })).toHaveAttribute("href", "/projects/42/cases/3");
  expect(screen.getByText(/under the current filters/i)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /1 test without a case/i })).toHaveAttribute("href", "/projects/42/tests");
});

test("the duration chart names its basis", () => {
  show();
  expect(screen.getByRole("heading", { name: "Run time (wall clock)" })).toBeInTheDocument();
  const timed = { ...TESTS_REPORT, duration: { ...TESTS_REPORT.duration, basis: "test_time" as const } };
  show(timed, filters("area=feature:Payments"));
  expect(screen.getByRole("heading", { name: "Time in selected tests (summed)" })).toBeInTheDocument();
});

test("slowest areas by total test time", () => {
  show();
  const rows = within(screen.getByRole("table", { name: /slowest areas/i })).getAllByRole("row");
  expect(rows[1]).toHaveTextContent("Payments");                       // 400,000 ms beats Booking's 90,000
});

test("CSVs and coverage groups", () => {
  expect(neverRunCsv(AREAS_FIXTURE.cases.slice(2, 3)).split("\r\n")).toEqual(["case,title,folder,feature", "TC-3,Refund,features/payments,Payments"]);
  expect(durationCsv(TESTS_REPORT).split("\r\n")[0]).toBe("date,runs,avg_ms,p50_ms,p90_ms,max_ms");
  expect(coverageGroups(AREAS_FIXTURE, "feature", 1)).toEqual([
    { label: "Payments", linked: 2, manual: 0 }, { label: "Booking", linked: 1, manual: 0 }, { label: "No feature", linked: 0, manual: 1 },
  ]);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd dashboard && npx vitest run src/pages/report/sections/CoverageDurationSection.test.tsx`
Expected: FAIL (module missing).

- [ ] **Step 3: Write `CoverageDurationSection.tsx`**

```tsx
import { Link } from "react-router-dom";
import { Download } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatDuration } from "../../../api/analytics";
import type { CaseArea, CaseAreas } from "../../../api/cases";
import type { Report } from "../../../api/report";
import { DataTableDisclosure } from "../../../components/ChartKit";
import { formatPointLabel, formatTick } from "../../../lib/chartFormat";
import { downloadCsv, toCsv } from "../../../lib/csv";
import { type AreaStats, type Grouping, decodeTests, folderAtDepth, groupByArea, neverRun, resolveScope, unlinkedTestCount } from "../../../lib/reportScope";
import DeltaTile from "../DeltaTile";
import ReportSection, { type SectionQuery } from "../ReportSection";
import { GroupingControl } from "./AreaSection";
import { useGrouping } from "../useGrouping";
import type { ReportFilters } from "../useReportFilters";
import { type Gate, caseAreasMessage } from "../useReportRequest";

const number = new Intl.NumberFormat();
const NEVER_RUN_SHOWN = 200;
const LARGEST_GROUPS = 15;
const axisTick = { fill: "var(--text-secondary)", fontSize: 12 } as const;

export function coverageGroups(areas: CaseAreas, grouping: Grouping, depth: number): { label: string; linked: number; manual: number }[] {
  // Coverage follows Section 3's grouping for feature and folder; labels and suites overlap, so they fall back to feature
  const byFolder = grouping === "folder";
  const counts = new Map<string, { label: string; linked: number; manual: number }>();
  for (const c of areas.cases) {
    const label = byFolder ? (c.folder ? folderAtDepth(c.folder, depth) : "No folder") : (c.feature ?? "No feature");
    const row = counts.get(label) ?? { label, linked: 0, manual: 0 };
    if (c.testKey) row.linked += 1;
    else row.manual += 1;
    counts.set(label, row);
  }
  return [...counts.values()].sort((a, b) => (b.linked + b.manual) - (a.linked + a.manual) || a.label.localeCompare(b.label));
}

export function neverRunCsv(cases: CaseArea[]): string {
  return toCsv(["case", "title", "folder", "feature"], cases.map((c) => [`TC-${c.number}`, c.title, c.folder, c.feature]));
}

export function durationCsv(r: Report): string {
  return toCsv(["date", "runs", "avg_ms", "p50_ms", "p90_ms", "max_ms"],
    r.duration!.buckets.map((b) => [b.date, b.runs, b.avg_ms, b.p50_ms, b.p90_ms, b.max_ms]));
}

export function slowestAreasCsv(groups: AreaStats[]): string {
  return toCsv(["area", "duration_ms_sum", "executions", "avg_ms_per_execution"],
    groups.map((g) => [g.label, g.durationMsSum, g.executions, g.executions ? Math.round(g.durationMsSum / g.executions) : null]));
}

interface Props {
  projectId: number;
  gate: Gate;
  testsQuery: SectionQuery;
  durationQuery: SectionQuery;
  caseAreas: { data?: CaseAreas; error: unknown; refetch: () => unknown };
  filters: ReportFilters;
  onResetFilters: () => void;
}

/** Section 5 (spec: Section 5: Coverage and duration). */
export default function CoverageDurationSection({ projectId, gate, testsQuery, durationQuery, caseAreas, filters, onResetFilters }: Props) {
  const { grouping, depth } = useGrouping(caseAreas.data);
  const sectionGate: Gate = caseAreas.error != null
    ? { state: "blocked", message: caseAreasMessage(caseAreas.error), error: caseAreas.error, retry: () => void caseAreas.refetch() }
    : !caseAreas.data && gate.state === "ready" ? { state: "wait" } : gate;
  // One frame over both requests: an error or loading in either shows here
  const query: SectionQuery = {
    data: testsQuery.data && durationQuery.data ? { ...testsQuery.data, duration: durationQuery.data.duration } : undefined,
    error: testsQuery.error ?? durationQuery.error,
    isPending: testsQuery.isPending || durationQuery.isPending,
    refetch: () => { void testsQuery.refetch(); void durationQuery.refetch(); },
  };
  const file = (r: Report, part: string) => `report-${projectId}-${r.period.from}-${r.period.to}-${part}.csv`;

  return (
    <ReportSection id="report-coverage" title="Coverage and duration" gate={sectionGate} query={query} height={520}
      onResetFilters={onResetFilters} actions={<GroupingControl areas={caseAreas.data} />}>
      {(r) => {
        const areas = caseAreas.data!;
        const rows = decodeTests(r.tests!);
        const scope = resolveScope(areas, filters.area, filters.suite);
        const missing = neverRun(areas, rows, scope);
        const unlinked = unlinkedTestCount(areas, rows);
        const coverage = coverageGroups(areas, grouping, depth).slice(0, LARGEST_GROUPS);
        const { groups } = groupByArea(areas, rows, grouping, depth);
        const slowest = [...groups].filter((g) => g.executions > 0).sort((a, b) => b.durationMsSum - a.durationMsSum);
        const d = r.duration!;
        const title = d.basis === "run_wall_time" ? "Run time (wall clock)" : "Time in selected tests (summed)";
        const unit = r.bucket;
        const longest = [...d.buckets].filter((b) => b.avg_ms !== null).sort((a, b) => (b.avg_ms ?? 0) - (a.avg_ms ?? 0))[0];
        const durationCaption = longest
          ? `Average ${title.toLowerCase()} per ${unit}; the longest is ${formatPointLabel(longest.date, unit)} at ${formatDuration(longest.avg_ms)}`
            + (d.previous ? `, against ${formatDuration(d.previous.avg_ms)} on average in the previous period.` : ".")
          : "No runs to time in this period.";
        return (
          <>
            <ul className="kpi-tiles" aria-label="Coverage figures">
              <li><DeltaTile title="Active cases" value={number.format(areas.counts.cases)} delta={null} noPrevious={false} /></li>
              <li><DeltaTile title="Linked (automated)" value={number.format(areas.counts.linked)} delta={null} noPrevious={false} /></li>
              <li><DeltaTile title="Manual" value={number.format(areas.counts.manual)} delta={null} noPrevious={false} /></li>
              <li><DeltaTile title="Automated, not run in this period" value={number.format(missing.length)} delta={null} noPrevious={false} /></li>
            </ul>

            <h3 id="report-coverage-chart">Linked and manual cases by {grouping === "folder" ? "folder" : "feature"}</h3>
            <svg width="0" height="0" aria-hidden="true" focusable="false" style={{ position: "absolute" }}>
              <defs>
                <pattern id="qeos-pat-manual" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                  <rect width="6" height="6" fill="var(--series-2)" />
                  <rect width="2" height="6" fill="var(--surface-1)" />
                </pattern>
              </defs>
            </svg>
            <figure className="chart-figure" aria-labelledby="report-coverage-chart">
              <figcaption className="sr-only">{`${number.format(areas.counts.linked)} linked and ${number.format(areas.counts.manual)} manual cases; the largest group is ${coverage[0]?.label ?? "none"}.`}</figcaption>
              <ResponsiveContainer width="100%" height={Math.max(160, coverage.length * 28)}>
                <BarChart data={coverage} layout="vertical" margin={{ left: 8, right: 24 }} accessibilityLayer>
                  <CartesianGrid stroke="var(--grid)" horizontal={false} />
                  <XAxis type="number" allowDecimals={false} stroke="var(--text-muted)" tick={axisTick} />
                  <YAxis type="category" dataKey="label" width={200} stroke="var(--text-muted)" tick={axisTick} />
                  <Tooltip contentStyle={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 6 }} />
                  <Bar dataKey="linked" name="Linked (automated)" stackId="c" fill="var(--series-1)" stroke="var(--surface-1)" />
                  <Bar dataKey="manual" name="Manual (striped)" stackId="c" fill="url(#qeos-pat-manual)" stroke="var(--surface-1)" />
                </BarChart>
              </ResponsiveContainer>
            </figure>
            <DataTableDisclosure name="linked and manual cases by group">
              <table className="data">
                <thead><tr><th scope="col">Group</th><th scope="col" className="num">Linked</th><th scope="col" className="num">Manual</th></tr></thead>
                <tbody>{coverage.map((g) => <tr key={g.label}><td>{g.label}</td><td className="num">{number.format(g.linked)}</td><td className="num">{number.format(g.manual)}</td></tr>)}</tbody>
              </table>
            </DataTableDisclosure>

            <h3>Automated, not run in this period <span className="muted">(under the current filters)</span></h3>
            {missing.length === 0 ? <p className="muted">Every automated case ran.</p> : (
              <>
                <table className="data">
                  <caption className="sr-only">Automated, not run in this period</caption>
                  <thead><tr><th scope="col">Case</th><th scope="col">Title</th><th scope="col" className="hide-narrow">Folder</th><th scope="col" className="hide-narrow">Feature</th></tr></thead>
                  <tbody>{missing.slice(0, NEVER_RUN_SHOWN).map((c) => (
                    <tr key={c.number}>
                      <td><Link to={`/projects/${projectId}/cases/${c.number}`}>TC-{c.number}</Link></td>
                      <td className="wrap-anywhere">{c.title}</td>
                      <td className="hide-narrow">{c.folder ?? "—"}</td>
                      <td className="hide-narrow">{c.feature ?? "—"}</td>
                    </tr>
                  ))}</tbody>
                </table>
                {missing.length > NEVER_RUN_SHOWN && <p className="muted report-note">And {number.format(missing.length - NEVER_RUN_SHOWN)} more (in the CSV).</p>}
                <div className="button-row no-print">
                  <button type="button" onClick={() => downloadCsv(file(r, "never-run"), neverRunCsv(missing))}><Download size={15} aria-hidden="true" /> Never-run CSV</button>
                </div>
              </>
            )}
            <p><Link to={`/projects/${projectId}/tests`}>{number.format(unlinked)} {unlinked === 1 ? "test" : "tests"} without a case</Link> ran in this period.</p>

            <h3 id="report-duration">{title}</h3>
            <figure className="chart-figure" aria-labelledby="report-duration">
              <figcaption className="sr-only">{durationCaption}</figcaption>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={d.buckets} accessibilityLayer>
                  <CartesianGrid stroke="var(--grid)" vertical={false} />
                  <XAxis dataKey="date" stroke="var(--text-muted)" tick={axisTick} tickLine={false} tickFormatter={(v: string) => formatTick(v, unit)} minTickGap={16} />
                  <YAxis stroke="var(--text-muted)" tick={axisTick} tickLine={false} width={64} tickFormatter={(v: number) => formatDuration(v)} />
                  <Tooltip contentStyle={{ background: "var(--surface-1)", border: "1px solid var(--border)", borderRadius: 6 }}
                    labelFormatter={(v) => formatPointLabel(String(v), unit)} formatter={(v) => formatDuration(Number(v))} />
                  {d.previous?.avg_ms != null && (
                    <ReferenceLine y={d.previous.avg_ms} stroke="var(--text-muted)" strokeDasharray="2 4"
                      label={{ value: "Previous average", fill: "var(--text-secondary)", fontSize: 12, position: "insideTopRight" }} />
                  )}
                  <Line dataKey="avg_ms" name="Average" stroke="var(--series-1)" strokeWidth={2} dot={{ r: 2.5, fill: "var(--series-1)", stroke: "var(--surface-1)" }} connectNulls={false} />
                  <Line dataKey="p90_ms" name="p90" stroke="var(--series-2)" strokeWidth={2} strokeDasharray="5 4" dot={{ r: 2.5, fill: "var(--series-2)", stroke: "var(--surface-1)" }} connectNulls={false} />
                </LineChart>
              </ResponsiveContainer>
            </figure>
            <DataTableDisclosure name={title.toLowerCase()}>
              <table className="data">
                <thead><tr><th scope="col">{unit === "day" ? "Date" : "Week of"}</th><th scope="col" className="num">Runs</th><th scope="col" className="num">Average</th>
                  <th scope="col" className="num">p50</th><th scope="col" className="num">p90</th><th scope="col" className="num">Max</th></tr></thead>
                <tbody>{d.buckets.map((b) => (
                  <tr key={b.date}><td>{formatPointLabel(b.date, unit)}</td><td className="num">{number.format(b.runs)}</td><td className="num">{formatDuration(b.avg_ms)}</td>
                    <td className="num">{formatDuration(b.p50_ms)}</td><td className="num">{formatDuration(b.p90_ms)}</td><td className="num">{formatDuration(b.max_ms)}</td></tr>
                ))}</tbody>
              </table>
            </DataTableDisclosure>
            <div className="button-row no-print">
              <button type="button" onClick={() => downloadCsv(file(r, "duration"), durationCsv(r))}><Download size={15} aria-hidden="true" /> Duration CSV</button>
              <button type="button" onClick={() => downloadCsv(file(r, "slowest-areas"), slowestAreasCsv(slowest))}><Download size={15} aria-hidden="true" /> Slowest areas CSV</button>
            </div>

            <h3>Slowest areas</h3>
            <table className="data">
              <caption className="sr-only">Slowest areas</caption>
              <thead><tr><th scope="col">Area</th><th scope="col" className="num">Total test time</th><th scope="col" className="num hide-narrow">Executions</th>
                <th scope="col" className="num">Average per execution</th></tr></thead>
              <tbody>{slowest.map((g) => (
                <tr key={g.key}><td className="wrap-anywhere">{g.label}</td><td className="num">{formatDuration(g.durationMsSum)}</td>
                  <td className="num hide-narrow">{number.format(g.executions)}</td>
                  <td className="num">{formatDuration(Math.round(g.durationMsSum / g.executions))}</td></tr>
              ))}</tbody>
            </table>
          </>
        );
      }}
    </ReportSection>
  );
}
```

Note: as in Task 28, put a `NarrowMeta` in the first cell of rows that hide columns (never-run: Folder, Feature; slowest areas: Executions).

- [ ] **Step 4: The page: case-areas always, Sections 3 and 5**

In `ReportPage.tsx`:
- `useReportRequest(id, filters, tz, { loadCaseAreas: true })` (spec: P3 always loads case-areas); the `formOpened` state and `onFormOpen` stay harmless; remove them if nothing else needs them (keep `onFormOpen={() => undefined}` for the bar's prop).
- add `const tests = useReportSection(id, gate, "tests");` and `const duration = useReportSection(id, gate, "duration");`, and include both in `busy`.
- render in spec order: Summary, `<FailureCausesSection …/>`, `<AreaSection projectId={id} gate={gate} query={tests} caseAreas={caseAreas} onResetFilters={clearAll} />`, `<RegressionsSection …/>`, `<CoverageDurationSection projectId={id} gate={gate} testsQuery={tests} durationQuery={duration} caseAreas={caseAreas} filters={filters} onResetFilters={clearAll} />`.

In `ReportPage.test.tsx`:
- the default report answer adds `...TESTS_REPORT`; the case-areas handler answers this wire form (case 1 keeps the key `"c".repeat(64)` the area tests expect, and Booking stays its feature):

```ts
    http.get(`${P}/case-areas`, () => HttpResponse.json({
      generated_at: "v1", counts: { cases: 3, linked: 2, manual: 1 },
      folders: ["features/booking", "features/payments"], features: ["Booking", "Payments"], labels: ["smoke"],
      suites: [{ id: 12, name: "Regression" }],
      cases: [
        { n: 1, t: "Book one-way", k: "c".repeat(64), fo: 0, fe: 0, l: [0], s: [0] },
        { n: 2, t: "Pay by card", k: "d".repeat(64), fo: 1, fe: 1, l: [], s: [0] },
        { n: 4, t: "Manual check", k: null, fo: null, fe: null, l: [], s: [] },
      ],
    })),
```
- add a test: "case-areas failing blocks By area and Coverage, while Summary still loads without an area filter":

```tsx
test("case-areas failing: sections 3 and 5 show the error, the others still load", async () => {
  serve();
  server.use(http.get(`${P}/case-areas`, () => HttpResponse.json({ detail: "down" }, { status: 500 })));
  renderPage();
  expect(await screen.findByRole("group", { name: /^Pass rate/ })).toBeInTheDocument();
  expect(await within(screen.getByRole("region", { name: "By area" })).findByText("Cases could not be loaded")).toBeInTheDocument();
  expect(within(screen.getByRole("region", { name: "Coverage and duration" })).getByText("Cases could not be loaded")).toBeInTheDocument();
});
```

- [ ] **Step 5: Run every dashboard check**

Run: `cd dashboard && npm run lint && npm run typecheck && npx vitest run --maxWorkers=4 && npm run build`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add dashboard/src/pages/report/sections/CoverageDurationSection.tsx dashboard/src/pages/report/sections/CoverageDurationSection.test.tsx dashboard/src/pages/report/ReportPage.tsx dashboard/src/pages/report/ReportPage.test.tsx
git commit -m "feat(dashboard): report coverage and duration; by area on the page" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard/src/pages/report/sections/CoverageDurationSection.tsx dashboard/src/pages/report/sections/CoverageDurationSection.test.tsx dashboard/src/pages/report/ReportPage.tsx dashboard/src/pages/report/ReportPage.test.tsx
```

---

### Task 30: Measure size B with every section; covering index only if needed; Phase 3 docs and gate

**Files:**
- Modify: `platforms/ingestion-service/README.md`
- Modify: `DESIGN.md`
- Create only if Step 2 says so: `platforms/ingestion-service/alembic/versions/017_report_covering_index.py` (+ model declaration and a migration test)

- [ ] **Step 1: Re-run the bench with all five sections**

Run (Docker required; `bench_report.py` picks up `tests` and `duration` from `SECTION_BUILDERS`):

```bash
SECRET_KEY=s INTERNAL_API_PASSWORD=p docker compose up -d --build --wait ingestion-service
docker compose exec -T -e SIZE=A ingestion-service python - < scripts/bench_report.py
docker compose exec -T -e SIZE=B ingestion-service python - < scripts/bench_report.py
```

Expected: A p95 ≤ 1 s and B ≤ 8 s per section. Add the `tests` and `duration` columns to the README table from Task 21.

- [ ] **Step 2: Only if a size-B section exceeds 8 s: the covering index (spec: Indexes, "Measured before it is added")**

`platforms/ingestion-service/alembic/versions/017_report_covering_index.py`:

```python
"""covering index for index-only report scans; added because size B missed 8 s (see README)

Revision ID: 017
Revises: 016
Create Date: <today>
"""
from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None

NAME = "ix_test_results_run_covering"


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.create_index(NAME, "test_results", ["run_id"], postgresql_include=["test_key", "status", "duration_ms"],
                            postgresql_concurrently=True)
    else:
        op.create_index(NAME, "test_results", ["run_id"])


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.drop_index(NAME, table_name="test_results", postgresql_concurrently=True)
    else:
        op.drop_index(NAME, table_name="test_results")
```

Declare it on `RunResult` (`Index("ix_test_results_run_covering", "run_id", postgresql_include=["test_key", "status", "duration_ms"])`), add a `test_migration.py` test asserting the index exists after `upgrade head` and is gone after `downgrade 016`, re-run the bench, and record before and after. If B still misses 8 s, stop and report: the next step (a daily per-test rollup) is a design change for the user, not this plan.

If every section meets its target, skip this step and write "Covering index: not needed at size B (measured <date>)." under the table.

- [ ] **Step 3: README and DESIGN.md**

README `### Report`, add:

```markdown
- `tests`: one row per test executed in scope in the period, columnar (`columns` + `rows`): executions, the four
  counts, `flips` and `pairs` summed over branches (flips only computed for tests with a failure), summed duration
  and the last status. At most 50,000 rows (then `truncated`, most failing first). The dashboard groups these rows by
  the cases' feature, folder, label or suite (ADR-026).
- `duration`: per bucket the runs and average, p50, p90 and maximum, and the previous period's figures. Without
  test keys the basis is `run_wall_time` (`test_runs.duration_ms`); with them `test_time`, the summed duration of
  the selected tests per run.
```

DESIGN.md, after the P2 entry:

```markdown
### Report: By Area, Coverage and Duration
A "Group by" segmented control (Feature, Folder, Label, Suite; `aria-pressed`, 44px on coarse pointers) is shared by By area and Coverage and kept in the URL (`group`, `depth`); Folder adds a Depth select whose default is the shallowest depth with two groups. By area: horizontal pass-rate bars for the 15 worst areas with the failure count as a text label, then a sortable table (`SortableTh`) worst first, areas under 10 executions last and marked "few runs", each area linking to the Cases list (or the suite) with that filter; labels and suites carry a note that groups overlap. Coverage: four plain tiles, stacked linked and manual bars (manual striped), the "Automated, not run in this period (under the current filters)" table of up to 200 cases, and a link to the tests without a case. Duration: average (solid) and p90 (dashed, with markers) lines with the previous average as a reference line, titled by its basis ("Run time (wall clock)" or "Time in selected tests (summed)"), and the slowest areas by total test time.
```

- [ ] **Step 4: Phase gate**

Run:

```bash
cd platforms/ingestion-service && SECRET_KEY=test .venv/Scripts/python -m pytest -q
cd ../test-management-service && SECRET_KEY=test .venv/Scripts/python -m pytest -q
cd ../../dashboard && npm run lint && npm run typecheck && npx vitest run --maxWorkers=4 && npm run build
node --test ../templates/github/qeos-run.test.mjs
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add platforms/ingestion-service/README.md DESIGN.md
git commit -m "docs: report by area, coverage and duration; size B measured" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- platforms/ingestion-service/README.md DESIGN.md
```

(If Step 2 added migration 017, add its file, `models/run.py` and `tests/unit/test_migration.py` to the same `git add` and `--` lists.)

Phase 3 ships here.

---

## Spec coverage (self-review)

| Spec requirement | Task |
|---|---|
| Filters in the URL (period presets and custom, branch, environment, CI, origin, area, suite), AND, invalid params dropped with a notice | 10, 13, 14 |
| Area and suite resolve to keys; 0 keys and >20,000 keys never call ingestion | 9, 11 |
| Run origin by Play URL, `run-urls` with `since`, known limits in help text | 3, 6, 11, 13 |
| `POST analytics/report`: roles, body rules, envelope, sections on request, statement timeout, read-only | 2, 3 |
| Section `summary` (deltas, buckets, top failing, slowest, branches, facets) | 4, 12 |
| Section `failure_causes` | 17, 18, 22 |
| Section `regressions` (lists, time to fix, flakiness per bucket) | 19, 20, 23 |
| Section `tests`, truncation | 25, 27, 28 |
| Section `duration`, basis | 26, 29 |
| Migration 016 (partial, concurrently; checked on PostgreSQL) | 16 |
| `case-areas` (dictionaries, counts, cap 409, timing) | 5 |
| Gateway route and gzip on two locations only; smoke checks; login not compressed | 7 |
| Dashboard structure, requests per phase, caching key, Refresh | 11, 14, 23, 29 |
| Empty and error states (no runs + suggestions, previous empty, case-areas fail/409, run-urls fail, 503, 422, loading) | 11, 12, 13, 14, 22, 28, 29 |
| Print / Save as PDF (print header, `.no-print`, page breaks, details open on `beforeprint`) | 14 |
| Accessibility (figures with captions, `accessibilityLayer`, data tables, words not colour, `aria-expanded`, `SortableTh`, `NarrowMeta`, live region) | 12, 13, 14, 22, 23, 28, 29 |
| Decisions 1–4 (default branch, URL origin + TODO, "Instability (flips)", ADR-026 with P1) | 11, 13, 15, 23 |
| Performance targets and `bench_report.py`; covering index only if B misses | 21, 30 |
| Docs per phase (READMEs, DESIGN.md, ADR-026) | 15, 24, 30 |
