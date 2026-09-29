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
