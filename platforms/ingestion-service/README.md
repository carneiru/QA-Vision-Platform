# Ingestion Service

Receives test results from CI. Design: `docs/superpowers/specs/2026-09-29-ingestion-service-design.md`.

## For a CI pipeline

1. A project owner, admin or member creates a key (shown once — store it as a CI secret):

   ```bash
   curl -k -X POST https://localhost:8443/api/v1/projects/<project_id>/api-keys \
     -H "Authorization: Bearer <your login token>" -H "Content-Type: application/json" \
     -d '{"name":"GitHub Actions - main"}'
   ```

2. The pipeline uploads one run per job:

   ```bash
   curl -k -X POST https://localhost:8443/api/v1/collect/runs \
     -H "Authorization: Bearer $QAV_API_KEY" -H "Idempotency-Key: $CI_RUN_ID-$CI_JOB" \
     -H "Content-Type: application/json" -d @run.json
   ```

   `run.json`:
   ```json
   {"run": {"ci_provider": "github_actions", "branch": "main", "commit_sha": "3f2a9c1",
            "started_at": "2026-09-29T10:00:00Z", "finished_at": "2026-09-29T10:04:12Z"},
    "results": [{"suite": "checkout", "class_name": "CartTest", "name": "adds item",
                 "status": "passed", "duration_ms": 812}]}
   ```

   `201` returns the run id and counts. Retrying with the same `Idempotency-Key` returns `200` and
   the same run — never a duplicate. The same key with a different body is `409`.

## Limits

- Up to 20,000 results per run (`422` beyond: split the run).
- `message` and `details` over 64 KB are truncated (the result's `truncated` is true), never rejected.
- `status`: `passed`, `failed`, `skipped`, `errored` (`error` is accepted as `errored`).
- `finished_at` may be at most 1 hour ahead of the server clock.
- Through the gateway, uploads are limited to 10 per second per IP (burst 20).

## Reading results

- `GET /api/v1/projects/<id>/runs?branch=&limit=&offset=` — newest first, with counts.
- `GET /api/v1/runs/<run_id>?status=failed` — one run with its results.

Every project role can read; roles come from project-service.

## Masking

Before a result is stored, its `message` and `details` are masked, and so is a password inside
the run's `ci_run_url`. Each masked value becomes `[REDACTED:<kind>]`; the text around it stays
readable. Test names, suites, classes, files and branches are never changed.

| Kind | Matches |
|---|---|
| `private_key` | `-----BEGIN … PRIVATE KEY-----` blocks (to the end of the text if unterminated) |
| `authorization` | the value of an `Authorization` / `Proxy-Authorization` header (the scheme word is kept) |
| `url_password` | the password in `scheme://user:password@` |
| `jwt` | JSON Web Tokens |
| `github_token`, `gitlab_token`, `aws_access_key`, `slack_token`, `stripe_key`, `google_api_key`, `npm_token`, `qav_key` | well-known token formats |
| `password`, `secret`, `token`, `api_key`, `access_key`, `client_secret`, `private_key`, `credentials` | the value in `key=value`, `key: value`, `key => value`, `"key": "value"` (also escaped inside a log line) when the key ends with one of these names (`DB_PASSWORD`, `SECRET_KEY`, `X-Api-Key`, `accessToken`, …); also `curl -u user:pw`, `--password pw` and `<password>pw</password>` |
| `cookie` | the value of a `Cookie:` / `Set-Cookie:` header |
| `email` | email addresses |
| `card_number` | 13–19 digit card numbers with a card prefix that pass the Luhn check |

- **Project patterns:** `GET/POST /api/v1/projects/{id}/masking-patterns`, `DELETE …/{pattern_id}`
  (owner/admin/member; viewers read), and `POST …/preview` `{name, pattern, sample}` → the sample as
  it would be stored plus this pattern's match count. Up to 20 per project; RE2 syntax (no
  backreferences or lookarounds), so no pattern can stall ingestion (ADR-020); a pattern that
  matches empty text is refused. They run after the built-in rules, never inside an existing
  marker, and produce `[REDACTED:<name>]`; metrics count them as `kind="custom"`.
- Masking happens before the 64 KB cut, so a secret on the boundary is never half-stored.
- Each result has a `redacted` flag; `qav_ingest_redactions_total{kind}` counts results by kind.
- Results stored before masking existed (or before a new rule) are re-masked on demand:
  `python -m src.ingestion.jobs.remask [--dry-run] [--project ID] [--batch-size N]`
  (`docker compose exec ingestion-service python -m src.ingestion.jobs.remask --dry-run`). It
  walks results by id in committed batches, prints a JSON summary (`results_scanned`,
  `results_changed`, `runs_changed`, `kinds`), and is safe to repeat: masked text is skipped.
  Text that masking makes longer than 64 KB is cut back and marked `truncated`.

## Retention

`python -m src.ingestion.jobs.retention [--dry-run] [--loop]` (the `ingestion-retention` compose
service runs it with `--loop`):

- Gets every project's `result_retention_days` from project-service's
  `GET /internal/v1/projects/retention`, with the HTTP Basic credentials in
  `PROJECT_SERVICE_INTERNAL_URL` (`http://ingestion-service:<password>@project-service:8000`;
  percent-encode special characters).
- Deletes runs uploaded (`created_at`) more than that many days ago. A deleted project's API keys
  are revoked at once; its runs are all deleted once it has been deleted for more than
  `RETENTION_DELETED_GRACE_DAYS` (default 7) — until then a soft delete can still be undone.
- A project on **legal hold** (`legal_hold: true` in the answer) loses nothing, whatever its age
  or deletion; its keys are still revoked if it is deleted (that deletes no data). Each pass
  reports `projects_held`. The field is required: an answer without it is untrustworthy.
- Without a trustworthy answer (unreachable, not 200, unexpected body) it deletes nothing and
  exits 1. Projects missing from the answer are never touched.

## Export

`GET /api/v1/projects/{id}/export` (owners and admins) streams everything stored for a project
as NDJSON (`application/x-ndjson`, `attachment`): an `export` header line (`format: 1`), then each
run (`type: run`, with its `changed_files` and `components`) followed by its results
(`type: result`). Text is exported as stored, masked. For a legal request, or before deleting
a project. The dashboard's Settings → Data has a download button.
- `RETENTION_INTERVAL_HOURS` (default 24) between passes with `--loop`; `RETENTION_BATCH_SIZE`
  (default 500) runs per transaction. One pass at a time (PostgreSQL advisory lock).
- Logs one JSON line per pass; the password is never logged (`user:***@host`).

## Analytics

Read-only, under `/api/v1/projects/{project_id}/analytics/`, for every role that can read runs:

| Endpoint | Returns |
|---|---|
| `GET /trends?days=30&tz=UTC&branch=&environment=` | One entry per local day (`days` 1–365, zone `tz`), oldest first, empty days zero-filled: runs, counts, `pass_rate`, average and maximum run duration |
| `GET /tests?days=30&sort=failures&search=&limit=50&offset=0` | One row per test in the window (`days` 1–90): counts, `pass_rate`, average duration, last status and when last seen; `sort` is `failures`, `duration` or `name`; `search` matches the name literally, case-insensitively |
| `GET /tests/{test_key}/history?days=30&branch=&limit=100` | One test: a summary over the window and its executions, newest first, with the message cut to 500 characters. 404 if the test was never seen in this project |
| `GET /flaky?window_days=14&min_runs=5&min_flip_rate=0.3&branch=` | At most 100 flaky tests (`window_days` 1–90) |

- `pass_rate` = passed ÷ (total − skipped); errored counts as not passed; `null` when nothing ran.
- An empty filter (`?branch=`) means no filter; `tz` must be a zone name from the IANA list.
- **Flaky, confirmed (`same_commit`):** the test both passed and failed (or errored) on the same commit **in the same environment**, with the pass and the fail in two different runs of that commit. Set `QAV_ENVIRONMENT` (or `--environment`) per CI matrix leg: legs that do not set it share one environment, so a failure specific to one leg shows as confirmed.
- **Flaky, suspected (`flips`):** for other tests, the share of consecutive executions on a branch whose outcome (pass vs failed/errored) changed, over at least `min_runs` executions; skipped results are ignored.
- Computed on request; migration 003 adds the indexes the queries use.

Measured on a throwaway stack with 1,980 runs × 1,000 tests (about 2 million results over 90 days, two runs per commit like CI shards), PostgreSQL 15 in Docker:

| Query | Time |
|---|---|
| trends, 365 days | 15 ms |
| tests, 90 days, sort=failures | 1,280 ms |
| tests, 90 days, search | 514 ms |
| history, 90 days | 16 ms |
| flaky, 14 days, live scan | 2,130 ms |
| flaky, 30 days, live scan | 3,229 ms |
| flaky, 90 days, live scan | 11,305 ms |
| rollup backfill, 90 days (one-off) | 34,828 ms |
| flaky, 14 days, from rollups | 833 ms |
| flaky, 90 days, from rollups | 3,887 ms |

Regenerate with `docker compose exec -T ingestion-service python - < scripts/analytics_benchmark.py` in a throwaway stack.

The flaky window goes up to 90 days. Flip counting recombines from the `flaky_daily` rollups the `analytics-rollup` job keeps current (backfill on start, then yesterday + today every 6 hours); a project the job has not visited yet falls back to the live scan with identical results (equivalence is pinned by `tests/unit/test_flaky_rollup.py`). Confirmed same-commit detection stays on the live failure-driven pass at every window — it rides the `(test_key, run_id)` index and dominates the remaining 90-day cost. The data is deliberately hard: failures are spread randomly, so nearly every test is a candidate.

## Operations

- `GET /health`; `GET /metrics` (Prometheus, inside the Docker network only — not routed by the
  gateway): `qav_ingest_runs_total`, `qav_ingest_results_total`, `qav_ingest_rejected_total{reason}`,
  `qav_ingest_duration_seconds`.
- Uploads never call another service; key management and reads need project-service (503 if it is down).

## Known limitations

- Deleting a project does not revoke its keys; revoke them first.
- JSON only — parsing JUnit XML and other formats is the collector's job.

## Running locally

```bash
py -3.11 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # also installs ../../shared
cp .env.example .env                                         # set SECRET_KEY = auth-service's
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m uvicorn src.ingestion.api.main:app --reload --port 8003
```

Tests: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q`
