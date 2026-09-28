# API Gateway and Root Compose Stack — Design

**Date:** 2026-09-28
**Status:** Draft — awaiting review
**Scope:** An NGINX gateway (`gateway/`) and a repository-root `docker-compose.yml` that runs auth-service, organization-service and project-service behind it on one network, with one PostgreSQL, one `SECRET_KEY`, and migrations applied automatically. Plus the one service change that requires: auth-service's Alembic `env.py` reads its database URL from settings.

## Problem

The roadmap's Phase 1 order is auth → organization → project → **API gateway**, and its 30-day success metrics include "all core services deployable via Docker Compose" and "basic monitoring showing service health". Today each service has its own compose stack with its own database and hand-picked host ports (8000/8001/8002, 5433/5434/5435); project-service reaches organization-service through `host.docker.internal`; nothing runs migrations; and there is no single entry point for the future frontend or the Phase 2 collector agent.

## Decisions (agreed during brainstorming)

| Question | Decision |
|---|---|
| Where must it run? | Local and single-host Docker Compose. Self-signed TLS, in-memory rate limiting. A Kubernetes ingress replaces or fronts it later. |
| Built from what? | NGINX with a configuration file — no gateway code. |
| Databases? | One PostgreSQL container holding `auth_db`, `organization_db`, `project_db`. |

## Architecture

```
                 host :8443 (HTTPS)   host :8080 (301 → HTTPS)
                          │
                    ┌─────▼─────┐
                    │  gateway  │  nginx:1.27-alpine
                    └─┬───┬───┬─┘
         ┌────────────┘   │   └────────────┐
   auth-service   organization-service   project-service     (no host ports)
         └────────────┐   │   ┌────────────┘
                    ┌─▼───▼───▼─┐
                    │ postgres  │  auth_db · organization_db · project_db  (no host port)
                    └───────────┘
```

Files:

```
docker-compose.yml            # repository root — the whole platform
gateway/
  Dockerfile                  # FROM nginx:1.27-alpine; adds openssl, gettext (envsubst), the config and entrypoint
  nginx.conf.template         # rendered at start with envsubst (only ${GATEWAY_HTTPS_PORT})
  entrypoint.sh               # renders the config, generates a self-signed certificate on first start, runs nginx
  README.md
scripts/
  postgres-init.sh            # creates missing databases; run by the db-init job
  smoke_gateway.sh            # end-to-end checks through the gateway
```

The per-service `docker-compose.yml` files stay unchanged, for working on one service in isolation. They use their own volumes; the root stack never touches them.

## Root compose stack

### Services

| Service | Image / build | Role |
|---|---|---|
| `postgres` | `postgres:15` | One server, volume `qav_postgres_data`, `pg_isready` healthcheck, **no host port** |
| `db-init` | `postgres:15`, one-shot | Runs `scripts/postgres-init.sh` against `postgres` on **every** `up`; creates each of the three databases only if missing |
| `auth-migrate`, `organization-migrate`, `project-migrate` | the service's own image, one-shot | `alembic upgrade head`, then exit |
| `auth-service`, `organization-service`, `project-service` | each service's Dockerfile (repository-root context, as today) | The app, with its existing `/health` healthcheck; **no host ports** |
| `gateway` | `gateway/Dockerfile` (based on `nginx:1.27-alpine`) | The only service published on the host |

### Start order

`postgres` healthy → `db-init` completed → each `*-migrate` completed → each service healthy → `gateway` started. Expressed with `depends_on` conditions `service_healthy` and `service_completed_successfully`, so `docker compose up -d --build --wait` returns only when every route is usable, and fails if any migration fails.

### Why `db-init` instead of `/docker-entrypoint-initdb.d`

Postgres runs init scripts only when its data directory is empty. A database added for a fourth service later would silently never be created on anyone's existing volume. `db-init` runs every time and is idempotent:

```sh
for db in auth_db organization_db project_db; do
  psql -tc "SELECT 1 FROM pg_database WHERE datname = '$db'" | grep -q 1 \
    || psql -c "CREATE DATABASE \"$db\""
done
```

(with `PGHOST=postgres`, `PGUSER=postgres`, `PGPASSWORD` from the environment).

### Environment

Defined once per service with YAML anchors and shared by the service and its `-migrate` job, so the two cannot drift:

```yaml
x-auth-env: &auth-env
  DATABASE_URL: postgresql://postgres:${POSTGRES_PASSWORD:-postgres}@postgres:5432/auth_db
  SECRET_KEY: ${SECRET_KEY:?set SECRET_KEY}
  BASE_URL: https://localhost:${GATEWAY_HTTPS_PORT:-8443}
x-organization-env: &organization-env
  DATABASE_URL: postgresql://postgres:${POSTGRES_PASSWORD:-postgres}@postgres:5432/organization_db
  SECRET_KEY: ${SECRET_KEY:?set SECRET_KEY}
  AUTH_SERVICE_URL: http://auth-service:8000
  AUTH_SERVICE_TOKEN: ${AUTH_SERVICE_TOKEN:-}
x-project-env: &project-env
  DATABASE_URL: postgresql://postgres:${POSTGRES_PASSWORD:-postgres}@postgres:5432/project_db
  SECRET_KEY: ${SECRET_KEY:?set SECRET_KEY}
  ORGANIZATION_SERVICE_URL: http://organization-service:8000
```

- `SECRET_KEY` is required with no default: it signs real tokens, and every service must share it.
- `POSTGRES_PASSWORD` defaults to `postgres`: the database has no host port, so the password only guards the Docker network.
- `GATEWAY_HTTPS_PORT` (default 8443) and `GATEWAY_HTTP_PORT` (default 8080) are overridable.
- Services reach each other by service name. `ORGANIZATION_SERVICE_URL` replaces project-service's `host.docker.internal` default inside this stack.

Database access for inspection: `docker compose exec postgres psql -U postgres -d project_db`.

## auth-service migration fix

`platforms/auth-service/auth-service/alembic.ini` hardcodes `sqlalchemy.url = postgresql://postgres:password@localhost:5433/auth_db`, and `alembic/env.py` never reads the service's settings, so `alembic upgrade head` cannot run inside a container. Change `env.py` to follow organization-service's pattern:

- put the service root on `sys.path` and import `from src.auth.config import settings`;
- if no URL was passed explicitly, `config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))`;
- blank `sqlalchemy.url` in `alembic.ini`, with a comment saying `env.py` fills it in.

`Base` import and migration scripts are unchanged. The `auth-migrate` job completing successfully on a fresh database is the test.

## Gateway

### Routing

NGINX picks a regex location before prefix locations, and the longest prefix among prefixes. Paths are forwarded unchanged — every service already serves under `/api/v1`.

| Location | Upstream |
|---|---|
| `~ ^/api/v1/organizations/[0-9]+/projects(/\|$)` | project-service |
| `/api/v1/projects` | project-service |
| `/api/v1/organizations` | organization-service |
| `/api/v1/invitations` | organization-service |
| `/api/v1/auth` | auth-service |
| `/api/v1/users` | auth-service |
| `/api/v1/sso` | auth-service |
| `= /health` | answered by the gateway: `200 {"status":"healthy"}` |
| `= /health/auth`, `= /health/organizations`, `= /health/projects` | that service's `/health` |
| everything else | `404 {"detail":"Not Found"}` |

The first row exists because project-service serves `/api/v1/organizations/{org_id}/projects` while organization-service serves the rest of `/api/v1/organizations/…`.

Service API docs (`/docs`, `/openapi.json`) are not routed.

### Upstream resolution

`resolver 127.0.0.11 valid=10s ipv6=off;` and, in each location, `set $upstream http://<service>:8000; proxy_pass $upstream;` — so a recreated container (new IP) is found within 10 s instead of the gateway returning 502 until restarted. With a variable and no URI part in `proxy_pass`, the original request URI is forwarded unchanged.

### Headers

- To upstream: `Host $host`; `X-Forwarded-For $remote_addr` (**overwritten**, not appended — the gateway is the edge, so a client-supplied value is discarded); `X-Forwarded-Proto $scheme`; `X-Request-ID $req_id`, where `$req_id` is the client's `X-Request-ID` if present, else NGINX's `$request_id`.
- To client: `X-Request-ID` echoed on every response.
- `Authorization` passes through untouched; each service still validates the token.
- `server_tokens off`.
- No HSTS: on `localhost` with a self-signed certificate it would force HTTPS for every localhost port in the browser.

### Rate limiting

Keyed on `$binary_remote_addr` (the TCP peer), never on a header.

| Zone | Rate | Burst | Applied to |
|---|---|---|---|
| `api` | 20 r/s | 40 (`nodelay`) | every `/api/v1/…` location |
| `auth` | 5 r/s | 10 (`nodelay`) | `= /api/v1/auth/login`, `/register`, `/forgot-password`, `/reset-password`, `/resend-verification` (exact-match locations, in addition to `api`) |

- Rejected requests: `429` with body `{"detail":"Too Many Requests"}` and header `Retry-After: 1` (`limit_req_status 429` plus a named error page).
- `/health*` locations have no limit, so monitoring cannot lock itself out.

### TLS

- `listen 443 ssl` (host `${GATEWAY_HTTPS_PORT:-8443}`), `ssl_protocols TLSv1.2 TLSv1.3`.
- `listen 80` (host `${GATEWAY_HTTP_PORT:-8080}`) returns `301 https://$host:${GATEWAY_HTTPS_PORT}$request_uri`. NGINX inside the container only sees port 443, so the host-side HTTPS port is substituted into the config at start (below); `$host` carries no port.
- `gateway/entrypoint.sh`:
  1. render `/etc/nginx/nginx.conf` from `nginx.conf.template` with `envsubst '${GATEWAY_HTTPS_PORT}'` — only that variable, so NGINX's own `$host`, `$request_uri`, … are left alone;
  2. if `/etc/nginx/certs/tls.crt` or `tls.key` is missing, generate a self-signed certificate for `CN=localhost` with `subjectAltName=DNS:localhost,IP:127.0.0.1`, 825-day validity, via `openssl`;
  3. `exec nginx -g 'daemon off;'`.
- Certificates live in named volume `qav_gateway_certs`, so they are generated once. Mounting your own `tls.crt`/`tls.key` there skips generation.
- `GATEWAY_HTTPS_PORT` is passed to the gateway container with the same default (8443) used for the port mapping, so the redirect always matches the published port.

### Limits and errors

- `client_max_body_size 10m`.
- `proxy_connect_timeout 3s`, `proxy_read_timeout 30s`.
- NGINX's own errors are JSON (named `error_page` locations with `default_type application/json`): 404 `{"detail":"Not Found"}`, 413 `{"detail":"Request Entity Too Large"}`, 429 as above, 502 `{"detail":"Bad Gateway"}`, 504 `{"detail":"Gateway Timeout"}`. Upstream error responses (the services' own 4xx/5xx JSON) pass through unchanged (`proxy_intercept_errors off`).

### Logging

JSON access log to stdout, one object per request: `time`, `request_id`, `remote_addr`, `method`, `uri`, `status`, `upstream` (service address), `upstream_response_time`, `request_time`, `bytes_sent`. Error log to stderr at `warn`. Visible with `docker compose logs gateway`.

## Testing

- **Config:** build the gateway image and run it with `nginx -t` in place of `nginx` (the entrypoint renders the template and generates a throwaway certificate first) — fails fast on a syntax error.
- **Smoke test,** `scripts/smoke_gateway.sh`, run after `docker compose up -d --build --wait` at the repository root; uses `curl -k` against `https://localhost:${GATEWAY_HTTPS_PORT:-8443}` and exits non-zero on the first failed check:

| Check | Expected |
|---|---|
| `GET /health` | 200, `{"status":"healthy"}` |
| `GET /health/auth`, `/health/organizations`, `/health/projects` | 200 each |
| `GET /api/v1/users/me` with an invalid token | 401 (auth-service) |
| `GET /api/v1/organizations/1/members/me` with a valid token for a non-member | 404 (organization-service) |
| `GET /api/v1/organizations/1/projects` with that token | 404, `detail` = `"Organization not found"` — project-service produces that text only after organization-service's `members/me` answered 404, so this one check proves both the overlap route and the project → organization call over the shared network |
| `GET /api/v1/projects/1` with that token | 404, `detail` = `"Project not found"` — proves the `/api/v1/projects` route (answered locally; no project exists) |
| `GET http://localhost:${GATEWAY_HTTP_PORT:-8080}/health` | 301, `Location` on HTTPS |
| `GET /no/such/path` | 404, `{"detail":"Not Found"}` |
| any response | carries an `X-Request-ID` header |
| 30 rapid `POST /api/v1/auth/login` | at least one 429 |

The valid token is minted with PyJWT inside the `auth-service` container (`docker compose exec -T auth-service python -c …`) using the stack's `SECRET_KEY`, so no user or seed data is needed.

- **Migrations:** every `*-migrate` job must complete successfully on a fresh volume, or `--wait` fails.
- **Existing suites:** unchanged; auth-service's 60 tests must stay green after the `env.py` change.

## CI

New job `gateway` in `.github/workflows/ci.yml`: `nginx -t`; `docker compose up -d --build --wait --wait-timeout 300` at the repository root with `SECRET_KEY=ci-gateway-secret`; `scripts/smoke_gateway.sh`; `docker compose logs` on failure; `docker compose down --volumes` always. The existing `tests` and `smoke` jobs are unchanged.

## Documentation

- Root `README.md`: a "Running the platform" section — `export SECRET_KEY=…`, `docker compose up -d --build --wait`, the URLs (`https://localhost:8443/…`), how to trust or skip the self-signed certificate, `psql` access, `docker compose down` (and `-v` to wipe data).
- `gateway/README.md`: the routing table, rate limits, TLS behaviour, and how to add a service (location block, upstream variable, compose entries, smoke-test check).
- `platforms/project-service/README.md`: `docker compose up --build` → `docker compose up -d --build`, so the following migration command is reachable (a residual from the project-service review).
- `TODO.md`: mark the gateway items, and add a **Gateway follow-ups** block:

| Follow-up | When it's needed |
|---|---|
| Monitoring dashboards (Prometheus/Grafana) | Phase 1 — "Basic monitoring stack" |
| Kubernetes ingress; real certificates | Phase 1 infra — when a cluster exists |
| Service-to-service token so organization-service can check users in auth-service | Soon — adding a member through the full stack needs a superuser `AUTH_SERVICE_TOKEN` until then |
| Shared rate limits in Redis | When more than one gateway instance runs |
| JWT validation and per-user limits at the gateway | When the gateway should reject bad tokens itself |
| API docs through the gateway | When a frontend or partner needs browsable docs |
| WebSockets | Phase 3 — real-time features |

## Build order

1. auth-service `env.py` fix (its suite stays green; migration runs against a real Postgres).
2. Root compose stack: `postgres`, `db-init`, `*-migrate`, the three services — verified with `up --wait` and each service's `/health` via `docker compose exec`.
3. Gateway: `Dockerfile`, `nginx.conf.template`, `entrypoint.sh`, compose entry.
4. Smoke script and CI job.
5. Documentation and TODO follow-ups.

## Out of scope

Everything in the Gateway follow-ups table above. Also: changing any service's routes, CMD or business logic; the per-service compose files.
