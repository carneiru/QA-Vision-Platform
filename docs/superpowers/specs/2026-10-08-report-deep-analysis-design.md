# Report: filters and deep analysis

Today the Report page (`dashboard/src/pages/ReportPage.tsx`) has one control, the period (7, 30 or
90 days). It shows a summary, a weekly pass-rate table, the 10 most failing and slowest tests,
flaky tests and branches, and prints to PDF. Each table comes from a different analytics endpoint,
and none of them can be narrowed to a branch, an environment or a part of the product.

On 2026-10-08 the user approved this design:

- **Filters at the top of the page, kept in the URL:**
  - period (7/30/90-day presets, or a custom from–to range);
  - branch, environment and CI provider;
  - area (a Gherkin feature, a folder, or a case label);
  - suite;
  - run origin: started by CI, or requested from QEOS with Play.
- **Five sections, each with a chart and a table**, and a CSV export where it makes sense:
  1. Summary, with changes against the previous period of the same length.
  2. Failure causes.
  3. By area.
  4. Regressions and stability.
  5. Coverage and duration.
- **ADR-022 holds: services never call each other, and the dashboard joins.** Ingestion gets one
  report endpoint. Test-management gets a compact `case-areas` endpoint. The dashboard turns area
  and suite filters into test keys and groups ingestion's per-test numbers by area.
- **Print / Save as PDF keeps working**, and the printed header lists the active filters.
- **Delivery in three phases:**
  - P1: filters and summary;
  - P2: failure causes, and regressions and stability;
  - P3: by area, and coverage and duration.

## Terms used below

| Term | Meaning |
|---|---|
| Execution | One row of `test_results`. A retry is another row with the same `test_key` in the same run. Counts (executions, failures, pass rate) count rows, as `/trends` and `/tests` already do. |
| Outcome of a test in a run | Its **last attempt** in that run (highest `test_results.id`). This is the "later rows win" rule of run compare. Regressions and streaks use it. |
| Failing | `failed` or `errored`. Skipped results never change an outcome sequence, as on the Flaky page. |
| Pass rate | passed ÷ (executions − skipped). This is the existing `pass_rate()`. |
| Period | The dates the user picked, on their local calendar (`tz`). It starts at local midnight of `from` and ends at local midnight after `to`, so the end is exclusive. |
| Previous period | The same number of days immediately before the period. It is used for deltas, for "new or recurring", and as look-back for streaks. |
| In scope | A run that matches the run filters (branch, environment, CI provider, origin), and a result whose `test_key` is in `test_keys` when area or suite filters are set. |

## Filters

### What each filter means

| Filter | URL parameter | Rule | Applied by |
|---|---|---|---|
| Period, preset | `period=7`, `30` or `90` (default `30`) | `to` = today in `tz`; `from` = `to` − (days − 1). This is the same window `trends` uses (`window_start`). | Dashboard turns it into `from` and `to` |
| Period, custom | `from=2026-09-01&to=2026-09-30` | ISO dates, inclusive. `from` ≤ `to`. At most 90 days. `to` is no later than today. `from` is no more than 400 days ago. | Dashboard and ingestion both check it |
| Branch | `branch=main` | Exact match on `test_runs.branch`. | Ingestion |
| Environment | `env=staging` | Exact match on `test_runs.environment`. | Ingestion |
| CI provider | `ci=github_actions` | One of `CI_PROVIDERS` (`models/run.py`). | Ingestion |
| Origin | `origin=ci` or `origin=qeos` (default: any) | See "Run origin" below. | Dashboard and ingestion |
| Area | `area=feature:Booking`, `area=folder:features/booking`, or `area=label:smoke` | One area at a time. A folder includes its subfolders, as the Cases folder filter does (`source_path` starts with `<folder>/`). | Dashboard resolves test keys from `case-areas` |
| Suite | `suite=12` | The cases in that test-management suite. | Dashboard resolves test keys from `case-areas` |

- **Filters combine with AND.** Area and suite together use the keys in both, so a suite narrowed to
  one feature works.
- **The area and suite filters only see automated tests linked to a case.** A test with no case
  (`automated_test_key` on no active case) drops out when either filter is on. The filter chip says
  so in its tooltip, and the Coverage section counts these tests.
- **When the area or suite filter resolves to no keys,** the dashboard does not call ingestion. Every
  section shows "No automated tests are linked to cases in this area".
- **When it resolves to more than 20,000 keys,** the dashboard does not call ingestion. It shows
  "This selection has more than 20,000 automated tests. Narrow it with another filter." This is
  the cap of `/cases/search`, and it cannot be hit at today's sizes.

### Run origin

A Play request is in test-management's `run_requests`. It stores the GitHub run as
`github_run_url`, which is GitHub's `html_url`, for example
`https://github.com/owner/repo/actions/runs/123`. The collector stores
`{GITHUB_SERVER_URL}/{GITHUB_REPOSITORY}/actions/runs/{GITHUB_RUN_ID}` as `test_runs.ci_run_url`.
That is the same URL. Run-from-QEOS already pairs a request with its test run this way: it
compares the two URLs without regard to case, among runs with `ci_provider = github_actions`.

**Rule:**

- A run is **requested from QEOS** when `ci_provider = 'github_actions'` and
  `lower(ci_run_url)` is in the lower-cased list of Play request URLs from the right time window.
- Every other run is **CI**, including runs with no `ci_run_url`.

- **The dashboard gets the URLs from test-management** through a new compact endpoint (below). It
  asks for requests made since `from` of the previous period minus one day, because a run starts
  after its request. It sends the URLs to ingestion as `requested_run_urls` only when the origin
  filter is set.
- **Shards and GitHub re-run attempts share one run URL,** so they all count as requested. That is
  correct: they belong to the same Play.
- **Known limits, written in the filter's help text:**
  - A Play whose GitHub run was never matched has no `github_run_url`, so its results count as CI.
  - A run outside GitHub Actions is always CI. Play only dispatches to GitHub today.
- **Rejected options:**
  - A marker in the upload, such as a new `origin` column filled from a Play workflow input. It
    needs a collector release, a new template version, an ingestion migration and a backfill.
    That is worth it only if the URL match turns out unreliable. It is listed under "Out of scope".
  - Inferring origin from `ci_provider`. A Play run is a normal `github_actions` run, so it cannot
    be told apart this way.

### Filter bar (UI)

- **Above the sections there is one row:**
  - quick chips for the period (7 / 30 / 90 days and "Custom…");
  - chips for the filters that are applied;
  - an "Add filter" button that opens the filter form (`FilterChips`, `FiltersDisclosure`,
    `FilterSelect` and `FolderSelect`, as on Runs and Cases).
- **The form fields:**
  - **Branch:** a text field with a datalist. The list is the period's 50 busiest branches, from
    `summary.facets`.
  - **Environment:** the same, from `summary.facets`.
  - **CI provider:** a `FilterSelect` that uses `CI_LABELS`.
  - **Origin:** a select with "Any", "CI" and "Requested from QEOS".
  - **Area:** a two-step control. First the kind (Feature, Folder, Label), then the value. Feature
    and label use a searchable `FilterSelect`. Folder uses `FolderSelect`, the tree.
  - **Suite:** a searchable `FilterSelect`.
  - Area and suite options come from `case-areas`, so they need no extra request.
- **Each chip** reads "Branch: main" and has a remove button named "Remove filter Branch: main".
  After a chip is removed, focus moves to the next chip, or to "Add filter" if no chip is left.
  "Clear all" resets everything except the period.
- **URL state:** the filters are in the URL query (`useSearchParams`). The page can be bookmarked
  and shared, and Back undoes a filter change. Parameters that are invalid (an unknown CI provider,
  a range of more than 90 days, a malformed area) are dropped, and a dismissible notice says
  "Some filters in the link were not valid and were removed".
- **A polite live region** says "Report updated" once all requested sections have loaded after a
  filter change.

## ingestion: `POST /api/v1/projects/{id}/analytics/report`

It sits under `/analytics/`, which the gateway already routes to ingestion. It is a POST because
`test_keys` can hold 20,000 keys (about 1.4 MB). That is under the gateway's 10 MB body limit.

### Roles

Every project role (`READ_ROLES`). A non-member gets 404, as on the other analytics endpoints.

### Request body

```json
{
  "from": "2026-09-09",
  "to": "2026-10-08",
  "tz": "Europe/Lisbon",
  "branch": "main",
  "environment": null,
  "ci_provider": null,
  "origin": "any",
  "requested_run_urls": null,
  "test_keys": null,
  "sections": ["summary"],
  "bucket": "auto"
}
```

| Field | Rule |
|---|---|
| `from`, `to` | ISO dates. `from` ≤ `to`. Span (`to` − `from` + 1) ≤ 90 days. `to` ≤ today in `tz` + 1 day, which allows for clock skew. `from` ≥ today − 400 days. Otherwise 422 with a message naming the rule. |
| `tz` | Checked against the zone list. This is the existing `_zone()`, which returns 422 for an unknown zone. |
| `branch` | ≤ 255 characters, no NUL, optional. An empty string means no filter, as elsewhere. |
| `environment` | ≤ 100 characters, no NUL, optional. |
| `ci_provider` | One of `CI_PROVIDERS`, optional. |
| `origin` | `any` (default), `ci` or `qeos`. |
| `requested_run_urls` | Required when `origin` is not `any`; otherwise 422 "requested_run_urls is required with origin". Each URL ≤ 2,048 characters with no NUL. At most 5,000 URLs. An empty list is allowed: `qeos` then matches nothing, and `ci` matches everything. Ignored when `origin = any`. |
| `test_keys` | Optional. 1–20,000 keys, each 64 hexadecimal characters, lower-cased by the server. Duplicates are removed. `null` means no key filter. An empty list is a 422: the dashboard never sends one. |
| `sections` | 1–5 unique values from `summary`, `failure_causes`, `regressions`, `tests`, `duration`. |
| `bucket` | `auto` (default), `day` or `week`. `auto` is `day` when the span is 31 days or less, and `week` otherwise. Weeks start on Monday on the local calendar, as in `bucketed()`. |

The model uses `extra="forbid"`. An unknown field is a 422.

### Response envelope

```json
{
  "period":          {"from": "2026-09-09", "to": "2026-10-08", "days": 30,
                      "start": "2026-09-08T23:00:00Z", "end": "2026-10-08T23:00:00Z"},
  "previous_period": {"from": "2026-08-10", "to": "2026-09-08", "days": 30,
                      "start": "...", "end": "..."},
  "tz": "Europe/Lisbon",
  "bucket": "day",
  "generated_at": "2026-10-08T14:02:11Z",
  "scope": {"runs": 412, "previous_runs": 398, "test_keys": null},
  "summary": { ... },
  "failure_causes": { ... }
}
```

- The response has only the sections that were asked for.
- `scope.test_keys` is the number of keys after duplicates were removed, or `null`.

### Section `summary` (P1)

```json
{
  "current":  {"runs": 412, "executions": 98234, "passed": 95010, "failed": 2011, "errored": 113,
               "skipped": 1100, "pass_rate": 0.9781, "tests": 1003, "failing_tests": 61,
               "avg_run_duration_ms": 734000},
  "previous": { ...same fields... } ,
  "buckets": [{"date": "2026-09-09", "runs": 14, "executions": 3301, "passed": 3200, "failed": 70,
               "errored": 3, "skipped": 28, "pass_rate": 0.9776}],
  "top_failing": [{"test_key": "...", "suite": "...", "class_name": "...", "name": "...",
                   "executions": 30, "failures": 12, "pass_rate": 0.6}],
  "slowest":     [{"test_key": "...", "suite": "...", "class_name": "...", "name": "...",
                   "executions": 30, "avg_duration_ms": 81000}],
  "branches":    [{"branch": "main", "runs": 120, "executions": 30120, "failures": 400,
                   "pass_rate": 0.986}],
  "facets": {"branches": ["main", "release/2.4"], "environments": ["staging"],
             "ci_providers": ["github_actions", "jenkins"]}
}
```

- **`runs`** counts in-scope runs. With `test_keys`, it counts in-scope runs that have at least one
  result for those keys.
- **`avg_run_duration_ms`** is the mean of `test_runs.duration_ms` (wall time) over those runs.
- **`tests`** is the number of distinct test keys executed. **`failing_tests`** is the number with
  at least one failing execution.
- **`previous`** is `null` when the previous period has no in-scope runs. The dashboard then shows
  "No data in the previous period" instead of deltas.
- **`buckets`** covers every bucket in the period, with zeros where there were no runs.
- **`top_failing`** is the 10 tests with the most failures, and only tests with at least one.
  **`slowest`** is the 10 tests with the highest average duration. Both use the same ordering and
  tie-break as `/tests`.
- **`branches`** is the 10 branches with the most in-scope runs.
- **`facets`** lists up to 50 values each, busiest first. It is computed over the period's runs and
  **ignores the other filters**, so it can offer ways out of an empty result.

### Section `failure_causes` (P2)

This extends the run-level failure groups (`run_service.failure_groups`, `analytics/signature.py`)
from one run to a period. The signature is unchanged: the first line of the message, with ids,
hexadecimal values and numbers replaced by placeholders, then SHA-1 cut to 12 characters. `none`
is the signature of failures without a message.

```json
{
  "failures": 2124,
  "groups_total": 37,
  "groups": [{
    "signature": "9f2c1ab04e7d",
    "headline": "TimeoutError: locator('#pay-button') ...",
    "occurrences": 412, "failed": 400, "errored": 12, "quarantined": 0,
    "tests": 18, "runs": 66,
    "status": "new",
    "previous_occurrences": 0,
    "first_seen": "2026-09-14T08:12:00Z", "first_seen_run_id": 9012,
    "last_seen": "2026-10-08T09:40:00Z",  "last_seen_run_id": 9433,
    "buckets": [0, 0, 3, 41],
    "top_tests": [{"test_key": "...", "suite": "...", "class_name": "...", "name": "...",
                   "occurrences": 40, "last_run_id": 9433}]
  }],
  "other": {"groups": 0, "occurrences": 0},
  "resolved": [{"signature": "...", "headline": "...", "previous_occurrences": 31,
                "last_seen": "2026-09-02T10:00:00Z"}]
}
```

- **`groups`** holds the 50 biggest groups by occurrences. Ties go to the newer `last_seen`, then
  to the signature, and `none` sorts last among equals. **`other`** sums the rest.
- **`tests` and `runs`** are distinct counts within the period.
- **`status`:**
  - `new`: the signature does not occur in the previous period;
  - `recurring`: it does.
- **`first_seen`** is the earliest occurrence in the previous period plus the period. When that
  falls in the previous period, the UI shows "seen since at least <date>", because older data is
  not read.
- **`buckets`** aligns with `summary.buckets`. It is the data for the sparkline.
- **`top_tests`** holds up to 10 tests per group.
- **`resolved`** holds up to 20 signatures that occurred in the previous period and not in this one,
  most previous occurrences first.
- **`quarantined`** counts occurrences from muted tests, as the run view does. The failures still
  count.
- **Query:** read the failing rows of in-scope runs in the previous period plus the period. The new
  partial index below serves this read. Only `substr(message, 1, 2000)` is selected, which bounds
  memory, and `headline()` needs only the first line. Signatures are computed in Python, as today.

### Section `regressions` (P2)

The outcome sequence is per **(test, branch)**: a test can fail on a feature branch while it passes
on `main`, and those are separate stories. Each list row carries its branch. With a branch filter
there is one sequence per test. The section's help text recommends the branch filter.

- **Candidates:** tests with at least one failing execution in scope, in the previous period plus
  the period. A test that never failed cannot regress, be fixed or flip. This is the same
  narrowing `flaky_inputs` uses.
- **Sequence:** the candidates' last-attempt outcomes per run, ordered by
  `(started_at, run id)`, ignoring skipped results.

| List | Rule |
|---|---|
| Newly failing | Failing at the end of the period. The current failing streak started inside the period. A passing outcome came before it, in the period or in the previous period. |
| Fixed | Passing at the end of the period. The current passing streak started inside the period. A failing outcome came just before it. |
| Longest failing | Failing at the end of the period, oldest streak start first. If the streak began before the previous period, `failing_since` is the start of the previous period and `failing_since_bounded` is `true`. The UI shows "at least since". |
| Time to fix | Every failing streak that ended inside the period, meaning a pass that follows one or more failures. The time is from the first failing run's `started_at` to the first passing run's `started_at`. A streak cut off by the look-back counts as a lower bound and is counted in `bounded`. |

```json
{
  "newly_failing":   {"total": 9, "items": [{"test_key": "...", "suite": "...", "class_name": "...",
                       "name": "...", "branch": "main", "failing_since": "...", "failing_since_run_id": 9301,
                       "last_passed_at": "...", "last_passed_run_id": 9290, "failures": 4,
                       "headline": "AssertionError: ..."}]},
  "fixed":           {"total": 5, "items": [{"...": "...", "branch": "main", "fixed_at": "...",
                       "fixed_run_id": 9400, "failing_since": "...", "time_to_fix_ms": 172800000}]},
  "longest_failing": {"total": 12, "items": [{"...": "...", "branch": "main", "failing_since": "...",
                       "failing_since_bounded": false, "consecutive_failures": 31, "last_run_id": 9433,
                       "headline": "..."}]},
  "time_to_fix": {"fixes": 23, "mean_ms": 151200000, "median_ms": 86400000, "p90_ms": 432000000,
                  "bounded": 2},
  "flakiness": [{"date": "2026-09-08", "tests_executed": 990, "flaky_tests": 14, "flips": 51}]
}
```

- **List sizes:** `newly_failing` and `fixed` return up to 100 items; `longest_failing` up to 50.
  `total` is always the full count.
- **`time_to_fix`:** all values are `null` when `fixes` is 0.
- **`flakiness`** has one entry per bucket.
  - A **flip** is an outcome change between consecutive outcomes on one branch. It is counted in
    the bucket of the later outcome.
  - **`flaky_tests`** is the number of tests with at least one flip in that bucket.
  - **`tests_executed`** is the number of distinct tests with a non-skipped outcome in that bucket.
  - This is a weekly view of the "flips" signal. It does not use the Flaky page's same-commit rule,
    and the help text says so.
- **Query:**
  - one pass for the candidates, served by the new partial index;
  - one pass for the sequence (`lag`/`lead` over each test and branch ordered by start, run, `id`; a run's last attempt is the row whose next row is in another run, kept only when it or a neighbour outcome fails, `_outcomes` in `report_service.py`);
  - the streak and flip logic runs in Python over the ordered rows.
  - At reference size A there are a few thousand candidate rows.

### Section `tests` (P3)

Per-test numbers for the dashboard's area grouping. It is columnar to keep the payload small: a
key repeated in every object would double it.

```json
{
  "columns": ["test_key", "executions", "passed", "failed", "errored", "skipped",
              "flips", "pairs", "duration_ms_sum", "last_status"],
  "rows": [["<64 hex>", 30, 27, 2, 0, 1, 3, 28, 912000, "passed"]],
  "truncated": false
}
```

- **Coverage:** one row per test executed in scope in the period, previous period not included.
- **`flips` and `pairs`** are summed over branches. `pairs` is the sum over branches of
  (non-skipped outcomes − 1). Flips are computed only for tests with a failure, because all other
  tests have 0.
- **Limit:** at most 50,000 rows, by test key. Above that, `truncated` is `true`, the dashboard
  shows a notice, and the rows are ordered by failures descending. This cannot happen at today's
  sizes.
- **Size:** at 20,000 tests this is about 2 MB uncompressed, about 0.4 MB with gzip (see Gateway).

### Section `duration` (P3)

```json
{
  "basis": "run_wall_time",
  "buckets": [{"date": "2026-09-08", "runs": 41, "avg_ms": 702000, "p50_ms": 650000,
               "p90_ms": 1100000, "max_ms": 1500000}],
  "previous": {"runs": 398, "avg_ms": 690000, "p50_ms": 640000, "p90_ms": 1050000}
}
```

- **Without `test_keys`,** the basis is `run_wall_time`: `test_runs.duration_ms`.
- **With `test_keys`,** the basis is `test_time`: per run, the sum of `duration_ms` of the in-scope
  results. This is the time spent in the selected tests, not wall time, because shards and
  workers run in parallel. The chart title says which basis it shows.
- **Percentiles** are computed in Python from the per-run values. That is a few thousand numbers,
  and SQLite in the tests has no `percentile_cont`.

### Query strategy

- **One scoped-runs subquery feeds every section.** It reads `test_runs` where
  `project_id = :p AND started_at >= :previous_start AND started_at < :end` through
  `ix_test_runs_project_started`, plus the run filters.
  - Branch, environment, CI provider and origin are checked on these few thousand rows. They need
    no index.
  - The origin test is `lower(ci_run_url) = ANY(:urls)`, with `ci_provider = 'github_actions'`.
  - The subquery returns `id, started_at, branch, duration_ms`, plus a flag for "in the period" or
    "in the previous period".
- **Results join through `test_results.run_id`,** which is indexed.
- **`test_keys` filtering:**
  - On PostgreSQL, `test_key = ANY(CAST(:keys AS varchar[]))`, which is one array parameter. An
    expanded `IN` with 20,000 bind parameters is not used.
  - On SQLite (tests only), an expanding `IN`.
  - The service hides the difference in one helper.
- **Separate requests per section.** The dashboard sends one request per section so each section
  loads and fails on its own, as the current page does. Sections that share a scan in one request
  share the subquery. The cost of repeating the cheap run subquery is small next to the result
  scans.
- **Statement timeout.** Every report query runs under `SET LOCAL statement_timeout = '20s'`, below
  the gateway's 30 s `proxy_read_timeout`. A timeout returns 503
  `{"code": "report_timeout", "detail": "This report took too long. Narrow the period or the filters."}`
  instead of a gateway 504 with no explanation.
- **Read-only.** The handler never writes, and it ends its transaction before returning.

### Indexes: migration `016_report_indexes`

- **New:** `ix_test_results_failing` on `test_results (run_id, test_key)`, partial,
  `WHERE status IN ('failed','errored')`. Use `postgresql_where`, and `sqlite_where` for the tests.
  - Failure causes and the regression candidates read only failing rows. That is a few percent of
    the table, and today it is reached only by filtering every result of every run.
  - The index is small, because it covers only failing rows.
  - It is created with `CREATE INDEX CONCURRENTLY` on PostgreSQL, using
    `op.get_context().autocommit_block()`, so uploads are not blocked on a large table.
  - Downgrade drops it.
- **Existing indexes, used as they are:**
  - `ix_test_runs_project_started`, for the window;
  - `test_results.run_id`, for the result scans;
  - `ix_test_results_test_key_run`, for key-filtered scans when the key list is small.
- **Measured before it is added, not now:** a covering index
  `test_results (run_id) INCLUDE (test_key, status, duration_ms)` for index-only summary and
  per-test scans. It is added in a later migration only if reference size B misses its target
  (below). Wide `name` and `suite` columns make the heap reads the likely cost.

### Performance targets

They are measured with a new script, `scripts/bench_report.py`, on a throwaway PostgreSQL 15 stack,
as the README's Analytics table was. Results go into that table.

| Data | Each section request, 90 days plus 90 days of look-back | Whole page |
|---|---|---|
| A: about 100,000 results over 90 days (about 1,500 runs, 1,000 tests), the expected size | p95 ≤ 1 s | All sections shown within 2.5 s |
| B: the README benchmark, 2 million results over 90 days | ≤ 8 s each, never at the 20 s statement timeout | Sections appear as they finish |

- **If B misses its target:**
  1. First, add the covering index.
  2. Then, a daily per-test rollup. `flaky_daily` would gain `passed`, `skipped` and
     `duration_ms_sum`. A rollup works only for UTC days and branch filters, so the live path
     stays for the other filters.
  - Measured 2026-10-09 (`scripts/bench_report.py`): the reshaped regressions query brought B to
    p95 7.9 s, so B meets its target without either step. A covering index was tried at B and the
    planner ignored it or it ran slower (a sequential scan reads the table in about 0.3 s; the cost
    is the sort and window). The next step if B misses is therefore the rollup; the covering index
    stays an option only for a short window over a large mixed table.
- **ClickHouse is not adopted.** Its adoption trigger in the blueprint is "rollup tables stop
  holding", and it has not fired. Redis is not adopted either: its trigger is a second gateway
  instance.

### Caching

- **There is no server-side cache.** Results arrive all the time, a cache would need invalidating
  on every upload, and there is no shared cache store yet (no Redis, see above).
- **Dashboard:**
  - React Query, `staleTime` 5 minutes.
  - The key is `["report", projectId, section, filters, caseAreasVersion]`. `filters` is the
    normalised URL filter object. `caseAreasVersion` is `case-areas.generated_at`.
  - The 20,000 keys are never part of the query key. They are derived from the filters and the
    `case-areas` version.
  - A "Refresh" button refetches every section.

## test-management: `GET /api/v1/projects/{id}/case-areas` (P1)

This is one response with every active case, for joining in the dashboard. It does not page.
Paging would make the dashboard fetch every page anyway before it could resolve an area, and the
response is small once encoded with dictionaries.

- **Roles:** every project role (`READ_ROLES`).
- **Cases included:** cases with `status != 'archived'`, including drafts, in the same set the
  folder and feature counts use.

```json
{
  "generated_at": "2026-10-08T14:02:11Z",
  "counts": {"cases": 1042, "linked": 870, "manual": 172},
  "folders":  ["features/booking", "features/booking/air"],
  "features": ["Air booking"],
  "labels":   ["smoke", "ado-1234"],
  "suites":   [{"id": 12, "name": "Regression"}],
  "cases": [
    {"n": 12, "t": "Book a one-way flight", "k": "<64 hex or null>",
     "fo": 1, "fe": 0, "l": [0, 1], "s": [0]}
  ]
}
```

- **Dictionaries:** `folders`, `features`, `labels` and `suites` are sorted, and cases point into
  them by index. `fo` and `fe` are `null` when there is no folder or no feature.
- **Field names are short on purpose** (`n` number, `t` title, `k` automated test key, `fo` folder,
  `fe` feature, `l` labels, `s` suites). At 20,000 cases this keeps the payload near 2.5 MB raw and
  0.5 MB with gzip. The dashboard's `api/cases.ts` maps them to readable names in one place.
- **Folder** is the directory part of `source_path`, the same rule as `folder_counts`. Parent
  folders are not listed per case. The dashboard checks the prefix (`folder + "/"`) for the
  folder filter and cuts the path to a depth for grouping.
- **Linked and manual:**
  - `counts.linked` counts cases with `automated_test_key` set.
  - `counts.manual` counts the rest, whether the case is imported or written by hand.
  - This matches the Cases list's "linked" filter.
- **Cap:** at most 50,000 cases. Above that, the endpoint returns 409
  `{"code": "too_many_cases"}`. The dashboard then disables the area and suite filters and the P3
  area sections, and says why. The sections that do not need it keep working.
- **Queries:** three, with no new index. `cases` by `project_id` (indexed). `case_labels` joined on
  `case_id` (indexed). `suite_cases` joined on `case_id` (indexed), with `suites` by project.
  Target: ≤ 300 ms at 20,000 cases.
- **Gateway:** add `case-areas` to the test-management location regex in `nginx.conf.template`
  (`(cases|case-labels|case-folders|case-features|case-areas|suites|ci-target|run-requests)`).

## test-management: `GET /api/v1/projects/{id}/run-requests/run-urls?since=<ISO datetime>` (P1)

- **Roles:** every project role.
- **Response:** `{"urls": ["https://github.com/owner/repo/actions/runs/123"], "truncated": false}`.
  - It lists the `github_run_url` values that are not null, from requests with
    `requested_at >= since`, newest first.
  - At most 5,000 URLs; `truncated` is `true` above that.
  - Play allows one active request per project, so a 180-day window holds hundreds at most.
- **`since`** is required and at most 400 days back; otherwise 422.
- **Route order:** register the route **before** `/{request_id}`. Otherwise `run-urls` is parsed
  as an integer id and returns 422.

## Gateway: gzip for the two large responses (P1)

Add `gzip on; gzip_proxied any; gzip_types application/json; gzip_min_length 1024;` **only** inside
two locations: one new exact-match location for `/api/v1/projects/{id}/case-areas`, and one for
`/api/v1/projects/{id}/analytics/report`. It is not turned on server-wide.

- **Why only there:** these responses hold no secrets and reflect no input. Compressing responses
  that do, such as login or token responses, opens the BREACH class of attacks.

## Dashboard

### Structure

- **`pages/report/ReportPage.tsx`** holds the filter bar, the header, the print header and the
  sections. The route in `App.tsx` stays `report`.
- **`pages/report/useReportFilters.ts`** keeps the URL state. It parses, validates and normalises
  the filters, and turns a preset into `from` and `to` in the user's `tz`.
- **`lib/reportScope.ts`** is pure and unit-tested:
  - it resolves the area and suite filters to keys from `case-areas`;
  - it groups the `tests` rows by feature, folder (at a depth), label or suite;
  - it finds the automated cases never run in the period;
  - it puts tests not linked to any case into one "No case" group.
- **API modules:** `api/report.ts` (`postReport`), `getCaseAreas` in `api/cases.ts`, and
  `getRunUrls` in `api/runRequests.ts`.
- **One section component per section** under `pages/report/sections/`. Each keeps today's
  `Section` behaviour: an error shows as an `ErrorBanner` with Retry, never as an empty period.
- **Reused as they are:** `ChartKit` (`ChartPatternDefs`, `SeriesLegend`, `DataTableDisclosure`),
  `SortableTh`, `NarrowMeta`, `lib/csv.ts`, `lib/chartFormat.ts`.

### Requests per phase

| Phase | Requests on load |
|---|---|
| P1 | `project`; `case-areas` (only when an area or suite filter is set, or the form is opened); `run-urls` (only when origin is set); `report{summary}`; the existing `getFlaky` (see the P1 note in Section 1). |
| P2 | Adds `report{failure_causes}` and `report{regressions}`. |
| P3 | Adds `report{tests}` and `report{duration}`. `case-areas` is now always loaded, because sections 3 and 5 need it. |

### Section 1: Summary (P1)

- **Header line:** "<Project>: quality report. 9 Sep – 8 Oct 2026 (30 days), Europe/Lisbon.
  Generated <time>." The filters follow, as text.
- **Tiles:** Runs, Executions, Pass rate, Failures, Failing tests and Average run time. Each has a
  delta against the previous period.
  - The delta is written in words and is never only an arrow or a colour. Examples: "▲ 1.2 pts vs
    previous 30 days" and "▼ 14% vs previous 30 days".
  - The tile's accessible name includes the delta.
  - Pass rate deltas are in percentage points; counts and durations are relative.
  - Whether a change is good is decided per metric: pass rate up is good, failures and duration up
    are bad, and runs are neutral. Good and bad get a word ("better" or "worse") as well as
    colour.
- **Chart:** stacked bars per bucket (passed, failed, errored and skipped, with the existing
  textures). A pass-rate line for this period sits over them, and a dashed `series-2` line shows the
  previous period aligned bucket by bucket. The data table holds the buckets.
- **Tables:** most failing (top 10), slowest (top 10) and branches (top 10). They now honour every
  filter, because they come from `summary`.
- **CSV exports:** buckets; top failing and slowest; branches.
- **Flaky tests in P1:** the existing Flaky section stays.
  - It uses `getFlaky` with period days and branch, and the dashboard filters it by `test_keys`
    when an area or suite filter is on.
  - A note names the filters it cannot apply: environment, CI provider and origin.
  - In P2, this section is replaced by the flakiness trend in Section 4. In P3, it is also
    replaced by flakiness per area.
- The page-level "Download CSV" button is removed. Each section exports its own data.

### Section 2: Failure causes (P2)

- **Chart:** horizontal bars of the 10 biggest causes by occurrences.
  - The bar label is the headline, cut to 80 characters with the full text in the table.
  - A "New" cause gets the text tag "New" and a hatched fill; a recurring cause is solid.
- **Table columns:** cause (headline), occurrences, tests, runs, status (New or Recurring),
  first seen, last seen, a sparkline per bucket with a text equivalent, and a link to the last run.
- **Rows expand** to show `top_tests`, each linking to the test's history.
- **"Resolved since the previous period"** is a short list under the table.
- **CSV columns:** signature, headline, occurrences, failed, errored, tests, runs, status,
  previous occurrences, first seen, last seen.

### Section 3: By area (P3)

- **Grouping control:** Feature, Folder, Label or Suite.
  - Folder has a depth select. The default depth is the shallowest one that gives at least two
    groups.
  - A test in several labels or suites counts in each group. A note says that the groups overlap
    and are not summed.
- **Per area:** linked tests, tests run, executions, pass rate, failures, failing tests and flaky
  tests.
  - A flaky test here is one with at least 5 non-skipped outcomes and flips ÷ pairs ≥ 0.3. These
    are the Flaky page's defaults, applied to the flips signal only.
- **Sort order:** worst first, meaning lowest pass rate among areas with at least 10 executions,
  then most failures. Areas with fewer executions come last and are marked "few runs". All columns
  can be sorted with `SortableTh`.
- **Chart:** horizontal bars of pass rate for the 15 worst areas, with the failure count as a text
  label.
- **Links:** each area row goes to the Cases list with that area's filter. Folder and feature use
  the Cases filters of the same name; label uses the label filter.
- **CSV:** one row per area.

### Section 4: Regressions and stability (P2)

- **Tiles:** Newly failing, Fixed, Still failing (`longest_failing.total`), and Median time to fix.
  When `bounded` > 0, the time-to-fix tile adds "(n at least)".
- **Chart:** flaky tests per bucket (bars) and the flaky share of tests executed (line). The data
  table has every value.
- **Three tables:**
  - newly failing: test, branch, failing since, last passed, failures, headline;
  - fixed: test, branch, fixed at, failing since, time to fix;
  - longest failing: test, branch, failing since, consecutive failures, headline.
  - Each row links to the test history, filtered to its branch, and to the run.
- **CSV:** one per table.

### Section 5: Coverage and duration (P3)

- **Coverage:**
  - Tiles: active cases, linked (automated), manual, and automated but not run in this period.
  - Chart: stacked bars of linked and manual cases per feature (or per folder, following
    Section 3's grouping), the 15 largest groups. Textures tell the series apart.
  - "Automated, not run in this period": a table of TC number, title, folder and feature, up to
    200 rows, with "and N more" and a full CSV export. The header says "under the current filters",
    because a branch or environment filter changes the answer.
  - "Tests without a case": the count of tests in `tests` whose key is linked to no case, with a
    link to the Tests page.
- **Duration:**
  - A line chart of average and p90 per bucket. The p90 line is dashed. The previous period's
    average is a reference line.
  - The title names the basis: "Run time (wall clock)" or "Time in selected tests (summed)".
  - The "Slowest areas" table lists total test time (`duration_ms_sum`), executions and average per
    execution, by the Section 3 grouping, slowest first.
- **CSV:** never-run cases; duration buckets; slowest areas.

### Empty and error states

| Situation | What shows |
|---|---|
| No in-scope runs in the period | Each section shows "No runs match these filters in this period". The Summary section adds buttons: "Clear filters", and up to three facet suggestions such as "Try branch main". |
| Previous period empty | Tiles show values with "No data in the previous period" instead of a delta. Causes are all "New", with a note. |
| Area or suite resolves to 0 keys, or more than 20,000 | The messages under Filters. Ingestion is not called. |
| `case-areas` fails | Area and suite filters are disabled ("Cases could not be loaded", Retry). Sections 3 and 5 show the error. Sections 1, 2 and 4 work as long as no area or suite filter is set; if one is set, they show the same error, because their keys cannot be resolved. |
| `case-areas` returns 409 `too_many_cases` | As above, with "This project has more cases than the report can join (50,000)". |
| `run-urls` fails | The origin filter shows the error with Retry. While it is set, the sections wait and are not sent unfiltered. |
| A section returns 503 `report_timeout` | That section shows the message with Retry. The other sections are not affected. |
| A section returns 422 | "These filters are not valid: <detail>", with "Reset filters". This only happens with a hand-edited URL that passed the client checks. |
| Loading | A `Skeleton` with the section's height. The filter bar stays usable, and a new filter change cancels the requests in flight through React Query's abort signal. |

### Print / Save as PDF

- **A print-only header** (`.print-only`) sits under the page title. It lists the period (dates
  and `tz`), every active filter as "Label: value", the previous period used for deltas, and when
  the report was generated.
- **The filter bar, chips, buttons and grouping controls** are `.no-print`, as today.
- **Each section** has `break-inside: avoid` on its chart and on its table header. Long tables may
  break between rows, and the header row repeats (`thead { display: table-header-group }`).
- **Charts print as their SVG,** with the textures. Every `DataTableDisclosure` prints open
  (`details` is forced open in print through the `beforeprint` event), so the numbers are on
  paper as well.

### Accessibility

These follow DESIGN.md's chart rules.

- **Charts:**
  - Each chart is a `figure` with an off-screen caption giving the totals and the notable point,
    for example "Failures rose from 1,804 to 2,124; the largest cause is TimeoutError…".
  - Recharts' `accessibilityLayer` lets arrow keys step through the points.
  - Each chart has a "Show data table" disclosure, and no chart has `role="img"`.
- **Colour is never the only signal:**
  - status series use the shared textures;
  - "New" and "Recurring" have text tags;
  - deltas are written in words;
  - comparison lines use a dash and markers.
- **Structure:** sections are `section` elements with an `h2`. Tables have captions, `th scope`,
  and `aria-sort` through `SortableTh`.
- **Keyboard:** everything is reachable by keyboard: the chips, the area two-step control, row
  expansion (a button with `aria-expanded`) and the links in tables. The focus order follows the
  page order.
- **Narrow screens:** columns that drop below 640px come back through `NarrowMeta`.
- **Live region:** the "Report updated" region from Filters. It does not announce each section, to
  avoid noise.

## Delivery

| Phase | Ingestion | Test-management | Gateway | Dashboard |
|---|---|---|---|---|
| P1 | `POST analytics/report`, with the envelope, validation, scoped runs, origin, `test_keys` and the `summary` section; statement timeout | `case-areas`, `run-requests/run-urls` | `case-areas` route; gzip on the two locations | Filter bar and URL state, `reportScope` key resolution, Section 1, print header, P1 Flaky note |
| P2 | Migration 016 (partial index); `failure_causes`, `regressions`; `bench_report.py` and README numbers | — | — | Sections 2 and 4; the flaky section is replaced by the flakiness trend |
| P3 | `tests`, `duration`; measure B; covering index only if needed | — | — | Sections 3 and 5 |

Each phase ships on its own: full suites pass, and the pre-push steps mirror `ci.yml`.

**Docs updated with each phase:**

- ingestion and test-management READMEs (the endpoints, and the Analytics timing table);
- DESIGN.md: the filter-bar pattern, delta tiles, and the print header;
- ADR-026, "Report joins in the dashboard; run origin is matched by CI run URL". It records the
  origin rule and the rejected upload marker.

No blueprint adoption trigger fires, so the blueprint itself does not change.

## Testing

### ingestion

- **Unit (pure functions):**
  - Period arithmetic: presets, custom ranges, the previous period, a DST change inside the
    period, `auto` bucket choice, Monday-start weeks.
  - Origin matching: case-insensitive, `github_actions` only, an empty list.
  - Signature grouping: `new`, `recurring` and `resolved`; `none` sorts last; the cap of 50 and
    `other`.
  - Streak classification:
    - newly failing, fixed and still failing;
    - a retry where a later row wins;
    - skipped outcomes ignored;
    - per-branch sequences;
    - streaks cut off by the look-back are bounded.
  - Time to fix: mean, median and p90; `null` when there are no fixes.
  - Flips per bucket.
  - Percentiles.
- **Integration (SQLite, and PostgreSQL in CI where the other analytics tests run):**
  - Every 422: span over 90 days, `from` after `to`, `from` too old, unknown `tz`, malformed or
    more than 20,000 keys, an empty key list, origin without URLs, more than 5,000 URLs, duplicate
    or unknown sections, an extra field.
  - Roles: each project role gets 200, a non-member gets 404, no token gets 401.
  - Isolation: another project's runs never count.
  - Each filter alone and combined. `test_keys` changes `runs` to "runs with an in-scope result".
  - Deltas against a seeded previous period; `previous` is `null` when empty.
  - Bucket zero-fill.
  - Every section's shape, and only the sections asked for are present.
  - `tests` truncation at the cap, with a lowered cap in the test.
  - Statement timeout maps to 503 `report_timeout`, with the timeout forced in the test.
- **Migration:** 016 upgrades and downgrades. On PostgreSQL the index is partial (checked through
  `pg_indexes.indexdef`).
- **Performance:** `scripts/bench_report.py` seeds sizes A and B and prints p50 and p95 per
  section. It is run by hand before P2 and P3 ship, and the numbers go into the README. CI does
  not run it.

### test-management

- **`case-areas`:**
  - archived cases are excluded;
  - folder derivation, including `source_path` at the root;
  - dictionary indexes are consistent and sorted;
  - labels and suite membership, including a case in two suites;
  - linked and manual counts;
  - `null` folder and feature;
  - roles, and isolation from other projects;
  - the 409 above the cap, with a lowered cap in the test;
  - a timing check at 20,000 seeded cases.
- **`run-urls`:**
  - the `since` filter, null URLs left out, newest first, truncation;
  - the route is not caught by `/{request_id}`;
  - roles, and `since` validation.

### Gateway

- A config test or a smoke check that `case-areas` and `analytics/report` reach the right service
  and come back gzip-encoded when the request sends `Accept-Encoding: gzip`.
- A check that a login response is **not** compressed.

### Dashboard (Vitest and Testing Library)

- **`useReportFilters`:**
  - URL round trip for every filter;
  - a preset turns into `from` and `to` in a given `tz`;
  - invalid parameters are dropped, with the notice;
  - Back restores the previous filters.
- **`reportScope`:**
  - feature, folder (with subfolders), label and suite resolution;
  - area combined with suite;
  - unlinked tests;
  - 0 keys and more than 20,000 keys;
  - grouping by folder depth and the default-depth rule;
  - overlapping labels;
  - never-run cases;
  - the worst-first sort with the "few runs" rule.
- **Filter bar:** adding and removing chips; focus moves after a removal; Clear all keeps the
  period; the area two-step control works by keyboard.
- **Each section:** loading, empty, error with Retry, and data.
  - Delta text and its accessible name.
  - The New and Recurring tags.
  - The bounded "at least" wording.
  - The basis title in the duration chart.
- **CSV:** headers and rows of each export.
- **Print:** the print header lists every active filter and the period. Disclosures open on
  `beforeprint`.
- **Before every push:** `npm run lint`, `typecheck` and `build`, as the pre-push hook runs them.


## Decisions confirmed by the user (2026-10-08)

1. **Regressions default to the main branch.** The branch filter starts on the project's default branch, as known to project-service. When there is none, it starts on `main`. So "newly failing" and "fixed" mean "on main" unless the user picks another branch. The filter chip shows this default.
2. **Run origin is matched by URL in v1.** A Play whose GitHub run never matched counts as CI. A stored origin marker on uploads is a TODO item, not part of this work.
3. **The report's flakiness is labelled "Instability (flips)".** A short note explains that it counts pass/fail flips and differs from the Flaky page's same-commit rule.
4. **ADR-026** records the origin rule and the report joins. It is written with phase 1.

## Out of scope

- **A stored origin marker on runs.** That would be a Play workflow input, then the collector, then
  an ingestion column. It is the fallback if the URL match proves unreliable.
- **Origin for providers other than GitHub Actions,** until Play dispatches to them.
- **Several areas at once,** or OR between filters. There is one area and one suite, and filters
  combine with AND.
- **Server-side caching, Redis, ClickHouse and materialised report tables.** None of their adoption
  triggers has fired. A per-test daily rollup is the planned next step if size B misses its target.
- **Scheduled or emailed reports,** and saved report presets. The URL is the preset. The weekly
  summary job stays as it is.
- **Comparing two arbitrary periods or two branches side by side.** The previous period is the only
  comparison.
- **The same-commit flaky rule in report sections.** Report flakiness uses flips only, and the Flaky
  page stays the reference for the full rule.
- **Clustering failure causes beyond the existing signature,** for example by similarity or AI.
  Failure causes reuse `signature.py` unchanged.
- **Changing the Overview, Trends, Tests or Flaky pages** to use the new endpoint.
- **A server-generated PDF.** Print / Save as PDF stays in the browser.
