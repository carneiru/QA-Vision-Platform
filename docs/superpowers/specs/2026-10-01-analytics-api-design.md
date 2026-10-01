# Analytics API — Design

**Date:** 2026-10-01
**Status:** Draft — awaiting review
**Scope:** read-only analytics endpoints in ingestion-service over the stored runs and results: a daily trend per project, a list of tests, one test's history, and flaky-test detection. Plus two indexes, the gateway route, smoke checks, a one-off performance measurement and docs. Stacked on `feat/data-privacy`.

## Problem

The platform collects test runs (collector → ingestion) but only lets a team list runs and read one run. The roadmap's Phase 3 asks for "historical trend analysis", "basic flaky test detection (same test failing/passing inconsistently)" and "execution time trend analysis", with exit criteria "historical trends available for at least 90 days", "flaky test detection with <5% false positive rate" and "dashboard loads in <3 seconds for typical datasets". This step provides the read API a dashboard will use; there is no UI yet.

## Decisions (agreed during brainstorming)

| Question | Decision |
|---|---|
| Where | In ingestion-service, under its own path and module, so it can move to an `analytics-service` later without changing URLs |
| How numbers are computed | On request, with SQL aggregates (no summary tables, no jobs) |
| What counts as flaky | Both rules, with the reason given: `same_commit` (confirmed) and `flips` (suspected) |
| Refinements | Day boundaries in a requested time zone; `same_commit` per commit **and** environment; window caps and two indexes |

## Endpoints

All are `GET`, under `/api/v1/projects/{project_id}/analytics/`, guarded by the same check as the run endpoints (`require_project_role(*READ_ROLES)`: owner, admin, member, viewer; a non-member or missing project → 404; project-service unavailable → 503; bad token → 401).

Definitions used throughout:
- **pass_rate** = passed ÷ (total − skipped), where errored counts as not passed; `null` when total − skipped is 0.
- **window**: runs whose `started_at` falls in the last N days.
- **execution**: one result row (one test in one run).

### 1. `trends`

`GET …/analytics/trends?days=30&tz=UTC&branch=&environment=`

- `days` 1–365 (default 30); `tz` an IANA zone name (default `UTC`; unknown → 422); `branch`, `environment` optional exact filters.
- The window starts at local midnight `days − 1` days before today in `tz` and ends now.
- Response:

```json
{"tz": "Europe/Lisbon", "days": [
  {"date": "2026-09-30", "runs": 3, "total": 120, "passed": 110, "failed": 6, "errored": 1, "skipped": 3,
   "pass_rate": 0.9402, "avg_run_duration_ms": 61200, "max_run_duration_ms": 90500}
]}
```

- Exactly `days` entries, oldest first, **including days without runs** (counts 0, `pass_rate`, `avg_run_duration_ms`, `max_run_duration_ms` null).
- A run belongs to the local date of its `started_at` in `tz`. `pass_rate` is rounded to 4 decimals; averages to whole milliseconds.

### 2. `tests`

`GET …/analytics/tests?days=30&sort=failures&search=&limit=50&offset=0`

- `days` 1–90 (default 30); `sort` one of `failures` (failed + errored, descending), `duration` (average duration, descending), `name` (ascending); ties broken by `test_key`. `search` (≤ 200 characters): case-insensitive substring of `name`, with `%`, `_` and `\` matched literally. `limit` 1–200 (default 50), `offset` ≥ 0.
- Response: a list of

```json
{"test_key": "…64 hex…", "suite": "checkout", "class_name": "CartTest", "name": "adds item",
 "runs": 40, "passed": 37, "failed": 2, "errored": 1, "skipped": 0, "pass_rate": 0.925,
 "avg_duration_ms": 512, "last_status": "passed", "last_seen": "2026-09-30T21:04:00Z"}
```

- `runs` counts executions in the window; `last_status` and `last_seen` are those of the latest execution (by `started_at`, then run id).

### 3. `history`

`GET …/analytics/tests/{test_key}/history?days=30&branch=&limit=100`

- `test_key` must be 64 lowercase hex characters (else 422). `days` 1–90 (default 30); `branch` optional; `limit` 1–500 (default 100).
- 404 `{"detail": "Test not found"}` when the test was never seen in this project (in any window). A known test with no executions in the window answers 200 with zero counts and an empty list.
- Response:

```json
{"test_key": "…", "suite": "checkout", "class_name": "CartTest", "name": "adds item",
 "summary": {"runs": 40, "passed": 37, "failed": 2, "errored": 1, "skipped": 0, "pass_rate": 0.925, "avg_duration_ms": 512},
 "executions": [
   {"run_id": 812, "started_at": "2026-09-30T21:04:00Z", "branch": "main", "commit_sha": "3f2a9c1",
    "environment": "staging", "status": "failed", "duration_ms": 640, "message": "expected 3 but was 2"}
 ]}
```

- Identity fields come from the latest execution. Executions are newest first (`started_at`, then run id), at most `limit`; `message` is the stored (already masked) message cut to its first 500 characters. The summary covers the whole window with the branch filter, not just the returned executions.

### 4. `flaky`

`GET …/analytics/flaky?window_days=14&min_runs=5&min_flip_rate=0.3&branch=`

- `window_days` 1–90 (default 14); `min_runs` 2–1000 (default 5); `min_flip_rate` 0–1 (default 0.3); `branch` optional.
- Executions considered: status `passed`, `failed` or `errored` (skipped is ignored). Outcome classes: **pass** (`passed`) and **fail** (`failed`, `errored`).
- **`same_commit` (confirmed):** a test has, for some `(commit_sha, environment)` with `commit_sha` not null, at least one pass and at least one fail. `environment` null is its own value. Up to 5 such commits are reported (most recent first).
- **`flips` (suspected):** only for tests without a `same_commit` finding. Per branch (null branch is its own group), executions ordered by `started_at` then run id; a flip is a change of outcome class between consecutive executions. `flips` and `pairs` (executions − 1) are summed across the test's branches; `flip_rate` = flips ÷ pairs. Reported when total executions ≥ `min_runs` and `flip_rate` ≥ `min_flip_rate`.
- Response: a list (at most 100) of

```json
{"test_key": "…", "suite": "…", "class_name": "…", "name": "…", "reason": "same_commit",
 "commits": [{"commit_sha": "3f2a9c1", "environment": null}], "flips": null, "flip_rate": null,
 "runs": 12, "last_status": "failed", "last_seen": "2026-09-30T21:04:00Z"}
```

  For `flips` items, `commits` is `[]` and `flips`/`flip_rate` are set (`flip_rate` rounded to 4 decimals).
- Order: `same_commit` first, then by `flip_rate` descending; ties by `last_seen` descending, then `test_key`.
- Known limit: matrix legs that do not set `QAV_ENVIRONMENT` share the null environment, so an environment-specific failure can show as `same_commit`. The README tells teams to set it per leg.

## Computation

Code in ingestion-service:

| File | Responsibility |
|---|---|
| `src/ingestion/api/v1/endpoints/analytics.py` | Routes, parameter validation, role check |
| `src/ingestion/schemas/analytics.py` | Response models |
| `src/ingestion/service/analytics_service.py` | Database queries |
| `src/ingestion/analytics/trends.py` | Pure: window start and grouping run rows into local days |
| `src/ingestion/analytics/flaky.py` | Pure: the two flaky rules over plain execution rows |

- **trends:** select the window's run rows (`started_at`, `total`, `passed`, `failed`, `errored`, `skipped`, `duration_ms`) with the filters; group in Python with `zoneinfo`. Portable between PostgreSQL and SQLite (tests).
- **tests:** one `GROUP BY test_key` over results joined to runs in the window (per-status `SUM(CASE …)`, `AVG(duration_ms)`, `MAX(started_at)`, identity via `MAX()`), sorted and paged in SQL; a second query fetches the latest execution of just that page's keys for `last_status`.
- **history:** the executions query (results joined to runs on `test_key` and project, window, branch, newest first, `limit`) and one aggregate query for the summary; one existence query for the 404.
- **flaky:** a query for candidate test keys (at least one `failed`/`errored` execution in the window, with the branch filter), then the executions of only those keys (non-skipped, ordered), passed to the pure function.
- **Indexes** (migration 003): `ix_test_results_test_key_run` on `test_results(test_key, run_id)` and `ix_test_runs_project_started` on `test_runs(project_id, started_at)`.

### Performance

- Target: each endpoint well under 3 s for a typical project over its maximum window.
- Expected: about 1 s for `tests` over 90 days with ~2 million result rows on PostgreSQL; `trends` reads only run rows. Ten times more data needs summary tables (TODO).
- A one-off script (`scripts/analytics_benchmark.py`, not in CI) seeds a project with ~2 million results in a running stack and times each endpoint through the gateway; the numbers go into the ingestion-service README.

## Errors

| Case | Answer |
|---|---|
| Parameter out of range, unknown `tz`, unknown `sort`, malformed `test_key` | 422 |
| Test never seen in the project (`history`) | 404 `{"detail": "Test not found"}` |
| Not a member / project missing or deleted | 404 (as the run endpoints) |
| Bad or missing token | 401 |
| project-service unavailable | 503 |

## Gateway

`gateway/nginx.conf.template`: the regex location `^/api/v1/projects/[0-9]+/(api-keys|runs)(/|$)` becomes `^/api/v1/projects/[0-9]+/(api-keys|runs|analytics)(/|$)`. Without it, project-service would answer these paths (404).

## Testing

- **Pure functions (unit):**
  - trends: grouping in `UTC` and `Europe/Lisbon` (23:30 UTC lands on the next local day), a daylight-saving change, empty days zero-filled, `pass_rate` null when nothing ran, skipped excluded from `pass_rate`, the window start.
  - flaky: same commit + same environment confirmed; different environments not; null commit never `same_commit`; errored → failed is not a flip; skipped ignored; flips counted per branch and summed; `min_runs` and `min_flip_rate` thresholds; a confirmed test not listed again as `flips`; ordering; at most 5 commits.
- **Endpoints (integration, SQLite):** each endpoint for every read role; role failures (missing project, non-member, project-service down) as for runs; another project's runs never included; branch and environment filters; `tests` sort, search with `%` and `_` in the term, paging; `history` order, `limit`, the 500-character message, 404 for an unknown key, empty list for a known key outside the window; `flaky` end to end on seeded runs; every 422 case.
- **Migration:** a test that both indexes exist after `upgrade head` (the drift test already covers columns).
- **Smoke (through the gateway):** with the run the smoke test already uploads: `trends` → 200 and today's entry counts it; `tests` lists `fails`; that test's `history` → 200; `flaky` → 200.

## Documentation

- `platforms/ingestion-service/README.md`: an "Analytics" section — the endpoints, parameters, flaky rules and limits (set `QAV_ENVIRONMENT` per matrix leg), measured timings.
- `TODO.md`: Phase 3 items for trends, flaky detection and execution-time trends done; the out-of-scope items below added.

## Out of scope (TODO.md)

- Summary tables, when live queries get slow.
- Weekly and monthly views.
- Branch comparison.
- Muting or acknowledging a flaky test.
- CSV export.
- The dashboard UI.
