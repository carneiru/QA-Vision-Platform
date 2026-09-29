# Ingestion Service — Design

**Date:** 2026-09-29
**Status:** Draft — awaiting review
**Scope:** A new `platforms/ingestion-service`: project API keys for CI, a JSON endpoint that validates and stores one test run with its results, a small read API, and Prometheus metrics. Plus its place in the root compose stack and the gateway, and one contract test in project-service. The collector agent that calls this API is a separate, later spec.

## Problem

The roadmap's Phase 2 starts with "data ingestion API and validation", and the 30-day plan's week 3 asks for a secure endpoint for collector data, basic schema validation, initial storage in PostgreSQL, and health and metrics endpoints — so that a team can "install the collector agent in a CI pipeline", "submit test results from a simple test suite" and "view basic submission confirmation in the API". Nothing in the platform can receive a test result yet.

## Decisions (agreed during brainstorming)

| Question | Decision |
|---|---|
| How does the collector authenticate? | Project API keys (`qav_…`), created by project members and stored — hashed — in ingestion-service. The key alone identifies the project. |
| Synchronous or queued? | Synchronous: validate and store the whole run in one transaction, answer `201` with the run id and counts. |
| Reading data back? | A small read API: list a project's runs, get one run with its results. Every result carries a `test_key` for per-test history later. |

Parsing JUnit XML (or anything else) happens in the collector; this API accepts one JSON format.

## Architecture

Mirror project-service: FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL with its own `ingestion_db`, settings and sessions from `qav-shared`, JWTs from auth-service verified locally with the shared `SECRET_KEY`.

```
platforms/ingestion-service/
  src/ingestion/
    api/{main.py, deps.py, v1/api.py, v1/endpoints/{api_keys.py, collect.py, runs.py}}
    core/config.py
    db/{base.py, session.py}
    models/{api_key.py, run.py}
    schemas/{api_key.py, collect.py, run.py}
    service/{api_key_service.py, ingest_service.py, run_service.py}
    utils/{tokens.py, project_client.py, keys.py, metrics.py}
  alembic/  tests/{unit,integration}/
  Dockerfile  docker-compose.yml  requirements.txt  README.md  .env.example
```

`core/config.py`:

```python
class Settings(BaseServiceSettings):
    APP_NAME: str = "Ingestion Service"
    POSTGRES_DB: str = "ingestion_db"
    PROJECT_SERVICE_URL: str = "http://localhost:8002"
    PROJECT_SERVICE_TIMEOUT_SECONDS: float = 3.0
    MAX_RESULTS_PER_RUN: int = 20000
    MAX_TEXT_BYTES: int = 65536
```

## Data model

Integer ids, as in the other services. `project_id` and `organization_id` have no foreign key — they live in other services' databases.

### `api_keys`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `project_id` | Integer, not null, indexed | |
| `organization_id` | Integer, not null | From project-service at creation time |
| `name` | String(255), not null | e.g. "GitHub Actions – main" |
| `key_prefix` | String(12), not null | The first 12 characters (`qav_` + 8), shown in listings |
| `key_hash` | String(64), not null, **unique** | SHA-256 hex of the full key |
| `created_by` | Integer, not null | JWT `sub` |
| `created_at` | timestamptz | |
| `last_used_at` | timestamptz, nullable | Set on each successful upload |
| `revoked_at` | timestamptz, nullable | Set once; a revoked key is rejected |

- Key format: `qav_` + `secrets.token_urlsafe(32)` (43 characters) — 256 bits of randomness.
- SHA-256, not bcrypt (the 2026-07-13 schema doc's choice): bcrypt protects guessable passwords; a 256-bit random key cannot be guessed, and SHA-256 permits the indexed lookup every upload needs, where bcrypt would cost ~100 ms per request and cannot be looked up by index.
- The full key is returned only by the create endpoint and never stored or logged.

### `test_runs`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `project_id` | Integer, not null | From the API key |
| `api_key_id` | Integer FK → `api_keys.id`, not null | |
| `idempotency_key` | String(255), nullable | From the `Idempotency-Key` header |
| `request_hash` | String(64), not null | SHA-256 of the canonical request body (keys sorted, no whitespace) |
| `ci_provider` | String(20), not null | CHECK `IN ('github_actions','gitlab_ci','jenkins','other','local')` |
| `ci_run_url` | String(2048), nullable | |
| `commit_sha` | String(40), nullable | |
| `branch` | String(255), nullable | |
| `environment` | String(100), nullable | |
| `agent_version` | String(50), nullable | |
| `started_at`, `finished_at` | timestamptz, not null | |
| `duration_ms` | Integer, not null | `finished_at − started_at`, computed |
| `total`, `passed`, `failed`, `skipped`, `errored` | Integer, not null | Computed by the server from the results, never taken from the payload |
| `created_at` | timestamptz | |

- `UNIQUE (project_id, idempotency_key)` (NULLs do not collide, so uploads without the header are never deduplicated).
- Index `(project_id, created_at DESC)` for the run listing; index `(project_id, branch)`.

### `test_results`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `run_id` | Integer FK → `test_runs.id`, `ON DELETE CASCADE`, indexed | |
| `test_key` | String(64), not null, indexed | SHA-256 hex of `suite + "\0" + class_name + "\0" + name` |
| `suite` | String(500), not null, default `""` | |
| `class_name` | String(500), not null, default `""` | |
| `name` | String(1000), not null | |
| `status` | String(10), not null | CHECK `IN ('passed','failed','skipped','errored')` |
| `duration_ms` | Integer, not null | ≥ 0 |
| `message` | Text, nullable | At most `MAX_TEXT_BYTES` UTF-8 bytes after truncation |
| `details` | Text, nullable | Same limit |
| `truncated` | Boolean, not null, default false | True when `message` or `details` was cut |
| `file` | String(1000), nullable | |

## Endpoints

All under `/api/v1`.

### Collector (API key)

`POST /collect/runs` with `Authorization: Bearer qav_…` and optionally `Idempotency-Key: <1–255 printable ASCII>`.

Request body:

```json
{
  "run": {
    "ci_provider": "github_actions",
    "ci_run_url": "https://github.com/acme/shop/actions/runs/123",
    "commit_sha": "3f2a9c1",
    "branch": "main",
    "environment": "staging",
    "agent_version": "0.1.0",
    "started_at": "2026-09-29T10:00:00Z",
    "finished_at": "2026-09-29T10:04:12Z"
  },
  "results": [
    {"suite": "checkout", "class_name": "CartTest", "name": "adds item",
     "status": "failed", "duration_ms": 812,
     "message": "expected 2, got 1", "details": "Traceback ...", "file": "tests/cart_test.py"}
  ]
}
```

Validation (Pydantic, `extra="forbid"` at every level — an unknown field is a 422 naming it):

- `run.ci_provider` in the five values; `run.started_at`, `run.finished_at` timezone-aware ISO 8601; `finished_at ≥ started_at`; `finished_at` at most 1 hour in the future.
- `run.commit_sha` matches `^[0-9a-fA-F]{7,40}$`; `ci_run_url` is `http(s)://…`, ≤ 2048; other strings capped at their column length.
- `results`: 1 to `MAX_RESULTS_PER_RUN` items.
- `results[].name` required, non-blank; `suite`, `class_name` default `""`; `status` in `passed`, `failed`, `skipped`, `errored`, `error` — `error` is stored as `errored` (JUnit uses both); `duration_ms` integer ≥ 0 (default 0).
- `message` and `details` longer than `MAX_TEXT_BYTES` UTF-8 bytes are cut at a character boundary and the result's `truncated` is set — never rejected.
- Duplicate test identities within one run are stored as-is.

Responses:

| Case | Status | Body |
|---|---|---|
| Stored | 201 | `{"id", "project_id", "total", "passed", "failed", "skipped", "errored", "created_at"}` |
| Same `Idempotency-Key` and same `request_hash` as a stored run | 200 | The stored run's body; nothing new is written |
| Same `Idempotency-Key`, different `request_hash` | 409 | `{"detail":"Idempotency-Key reused with a different payload"}` |
| Missing, malformed, unknown or revoked key | 401 | `{"detail":"Invalid API key"}` with `WWW-Authenticate: Bearer` |
| Validation failure | 422 | FastAPI's error list |

This endpoint never calls another service. On success it sets the key's `last_used_at`. The run and all its results are written in one transaction; any failure writes nothing.

Two uploads racing with the same `Idempotency-Key`: the loser's insert violates `UNIQUE (project_id, idempotency_key)`; it rolls back, re-reads the winner's run, and answers 200 or 409 by comparing `request_hash` — exactly as if it had arrived second.

### People (JWT)

| Method and path | Roles |
|---|---|
| `POST /projects/{project_id}/api-keys` `{"name"}` → 201 `{"id","name","key_prefix","key","created_at"}` | owner, admin, member |
| `GET /projects/{project_id}/api-keys` → `[{"id","name","key_prefix","created_at","last_used_at","revoked_at"}]` | all five roles |
| `DELETE /projects/{project_id}/api-keys/{key_id}` → 204 (again 204 if already revoked; 404 if the key is not this project's) | owner, admin, member |
| `GET /projects/{project_id}/runs?limit=&offset=&branch=` → runs newest first, with counts | all five roles |
| `GET /runs/{run_id}?status=` → the run with its results (optionally one status) | all five roles |

- `limit` default 50, max 100; `offset` ≥ 0. Results in `GET /runs/{run_id}` are ordered by `id`.
- **Authorization:** `project_client.get_my_role(project_id, token)` calls project-service `GET /api/v1/projects/{project_id}` with the caller's own `Authorization` header, timeout `PROJECT_SERVICE_TIMEOUT_SECONDS`:
  - 200 with a body whose `my_role` is one of the five roles and whose `organization_id` is an integer → the role (and organization id, used when creating a key);
  - 404 → **404** "Project not found"; 401 → **401**;
  - timeout, connection error, 5xx, or a 200 that does not match → **503** "Project service unavailable".
- `GET /runs/{run_id}` loads the run first (404 if missing), then authorizes against the run's `project_id`; a caller who is not a member of that project gets 404 "Run not found".
- Key listings never include `key` or `key_hash`.

### Operations

- `GET /health` → `{"status":"healthy"}` (no auth; routed by the gateway as `/health/ingestion`).
- `GET /metrics` → Prometheus text (`prometheus_client`), **not routed by the gateway**; scraped inside the Docker network:
  - `qav_ingest_runs_total` (counter), `qav_ingest_results_total` (counter),
  - `qav_ingest_rejected_total{reason}` (counter; `auth`, `validation`, `conflict`),
  - `qav_ingest_duration_seconds` (histogram of `POST /collect/runs` handling time).

## Contract with project-service

ingestion-service relies on project-service's `GET /api/v1/projects/{id}` returning, on 200, a JSON object with integer `organization_id` and `my_role` in the five roles. project-service gains one test asserting both fields are present with those types; ingestion-service's mocks return exactly that shape plus the other `ProjectOut` fields.

## Gateway and root stack

- `scripts/postgres-init.sh` also creates `ingestion_db`.
- `docker-compose.yml`: `x-ingestion-env` (`DATABASE_URL`, `SECRET_KEY`, `PROJECT_SERVICE_URL=http://project-service:8000`), `ingestion-migrate`, `ingestion-service` (healthcheck), and `gateway` depends on it being healthy.
- `gateway/nginx.conf.template`:
  - `~ ^/api/v1/projects/[0-9]+/(api-keys|runs)(/|$)` → ingestion-service — a regex location, like the organizations/projects overlap, placed before project-service's locations;
  - `/api/v1/runs` → ingestion-service (zone `api`);
  - `/api/v1/collect` → ingestion-service with its own zone `collect` — 10 r/s per IP, burst 20 — in place of `api`;
  - `= /health/ingestion` → ingestion-service `/health`;
  - `/metrics` is not routed.
- Service compose file (for developing it alone): app on host port **8003**, database on **5436**, `PROJECT_SERVICE_URL` defaulting to `http://host.docker.internal:8002` with `extra_hosts: host-gateway`.

## Testing

Unit and integration, as in project-service; SQLite in tests; `respx` for project-service with every outgoing call mocked.

- **Keys:** key format and length; only the hash is stored; create returns the key once and listings never do; revoke is repeatable; a revoked key → 401 on upload; a key from project A cannot be revoked through project B's URL (404).
- **Collect:** 201 with server-computed counts (payload counts ignored — there are none in the schema); `error` → `errored`; each validation rule → 422; text over the limit truncated at a character boundary with `truncated` true (multi-byte characters included); 20,001 results → 422; idempotent replay → 200 with the same id and one stored run; same key, different body → 409; a failure mid-write stores nothing; no outgoing HTTP call on this path; `last_used_at` set.
- **Reads:** every route × every role against the table above; non-member → 404; project-service down → 503; a malformed project-service 200 → 503; run of another project → 404; `branch` and `status` filters; pagination bounds.
- **Metrics:** counters move on success and on each rejection reason; `/metrics` returns Prometheus text.
- **Migration:** `alembic upgrade head` matches the models (SQLite), and runs on PostgreSQL in the root stack.
- **Contract:** project-service test for `organization_id` and `my_role` on `GET /projects/{id}`.
- **Gateway smoke** (`scripts/smoke_gateway.sh`): `/health/ingestion` 200; create a key through the gateway (needs a project the token's user can manage — the smoke test creates an organization and a project first through the gateway); upload a run → 201; replay → 200 same id; read it back; revoke the key → next upload 401; each new overlap route reaches ingestion-service; `/metrics` is 404 through the gateway.

## Deployment

Dockerfile with the repository-root context and `uvicorn src.ingestion.api.main:app`; the root stack runs `ingestion-migrate`. CI: one entry in each of the `tests` and `smoke` matrices; the `gateway` job runs the extended smoke script. `platforms/ingestion-service/README.md`; root README project structure and route table; `TODO.md`.

## Out of scope (recorded in TODO.md)

- The collector agent (next spec).
- Queue-based processing (Redis/Kafka) for 1000+ events/second.
- PII detection and redaction; retention policies.
- mTLS between agent and platform.
- Artifacts (screenshots, videos, traces, logs).
- Per-test history endpoints (the `test_key` index is in place).
- Revoking a project's keys when the project is deleted.
- Formats other than this JSON (JUnit XML parsing lives in the collector).
