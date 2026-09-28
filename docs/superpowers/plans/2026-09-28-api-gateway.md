# API Gateway and Root Compose Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the whole platform with one command — auth, organization and project services behind an NGINX gateway, on one network, one PostgreSQL, one `SECRET_KEY`, migrations applied automatically.

**Architecture:** A repository-root `docker-compose.yml` with `postgres`, an idempotent `db-init` job, one `*-migrate` job per service, the three services (no host ports), and a `gateway` built from `gateway/` (NGINX, config file only). NGINX handles routing (a regex location for the `organizations/{id}/projects` overlap), per-IP rate limiting, self-signed TLS, JSON errors and a JSON access log. A shell smoke test drives every route through the gateway and runs in CI.

**Tech Stack:** Docker Compose v2, NGINX 1.27 (alpine), PostgreSQL 15, Alembic, bash + curl, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-28-api-gateway-design.md`

## Global Constraints

- Only the gateway is published on the host: `${GATEWAY_HTTPS_PORT:-8443}:443` and `${GATEWAY_HTTP_PORT:-8080}:80`. No host ports for services or Postgres.
- `SECRET_KEY` is `${SECRET_KEY:?set SECRET_KEY}` — required, no default, shared by all three services. `POSTGRES_PASSWORD` defaults to `postgres`.
- One `postgres:15` container, volume `qav_postgres_data`, databases `auth_db`, `organization_db`, `project_db`; created by the `db-init` job on every `up`, only if missing.
- Service-to-service URLs: `AUTH_SERVICE_URL=http://auth-service:8000`, `ORGANIZATION_SERVICE_URL=http://organization-service:8000`. auth-service `BASE_URL=https://localhost:${GATEWAY_HTTPS_PORT:-8443}`.
- Routing: `~ ^/api/v1/organizations/[0-9]+/projects(/|$)` and `/api/v1/projects` → project-service; `/api/v1/organizations`, `/api/v1/invitations` → organization-service; `/api/v1/auth`, `/api/v1/users`, `/api/v1/sso` → auth-service; `= /health` → gateway; `= /health/{auth,organizations,projects}` → that service's `/health`; anything else → `404 {"detail":"Not Found"}`.
- Rate limits keyed on `$binary_remote_addr`: zone `api` 20 r/s burst 40 on every `/api/v1/…`; zone `auth` 5 r/s burst 10 additionally on `= /api/v1/auth/{login,register,forgot-password,reset-password,resend-verification}`; `429 {"detail":"Too Many Requests"}` with `Retry-After: 1`; no limit on `/health*`.
- TLS 1.2/1.3 on 443; port 80 → `301 https://$host:${GATEWAY_HTTPS_PORT}$request_uri`; self-signed certificate (`CN=localhost`, SAN `DNS:localhost,IP:127.0.0.1`, 825 days) generated once into volume `qav_gateway_certs`; no HSTS; `server_tokens off`.
- `X-Forwarded-For` is **overwritten** with `$remote_addr`; `X-Request-ID` is the client's or NGINX's `$request_id`, forwarded upstream and echoed on every response.
- `client_max_body_size 10m`; `proxy_connect_timeout 3s`; `proxy_read_timeout 30s`; `proxy_intercept_errors off`; NGINX-generated 404/413/429/502/504 are JSON.
- `resolver 127.0.0.11 valid=10s ipv6=off;` with `set $upstream …; proxy_pass $upstream;` so a recreated container is found without restarting the gateway.
- Per-service compose files are not modified. No service routes, CMDs or business logic change, except auth-service's `alembic/env.py` and `alembic.ini`.

## Review Focus

- **Windows line endings in shell scripts copied into Linux containers** (`entrypoint.sh`, `postgres-init.sh`) turn `#!/bin/sh` into `/bin/sh\r: not found`, and the container dies at start. A `.gitattributes` forcing LF, and a byte check, are pinned in Task 2 and Task 3.
- **`docker compose up --wait` and one-shot jobs:** exited `db-init`/`*-migrate` containers must not make `--wait` report failure. The plan always waits on named long-running services (`--wait auth-service …` / `--wait gateway`), and Task 2 verifies it.
- **Restarting one service while the gateway runs** must not leave the gateway returning 502 for that route. Task 3 recreates project-service and checks the route recovers within ~10 s.
- **A client-supplied `X-Forwarded-For`** must not reach the services or change which rate-limit bucket the client is in. Task 3 checks the header the upstream receives.
- **Running `up` a second time on an existing volume** must be a no-op: db-init reports "exists", migrations report nothing to do, every service comes back healthy. Pinned in Task 2.

---

### Task 1: auth-service Alembic reads its URL from settings

**Files:**
- Modify: `platforms/auth-service/auth-service/alembic/env.py`
- Modify: `platforms/auth-service/auth-service/alembic.ini` (the `sqlalchemy.url` line)
- Create: `platforms/auth-service/auth-service/tests/unit/test_alembic_env.py`

**Interfaces:**
- Produces: `alembic upgrade head` run from `platforms/auth-service/auth-service` (locally or in the image's working directory `/app/platforms/auth-service/auth-service`) targets `settings.database_url`, i.e. the `DATABASE_URL` environment variable. Consumed by Task 2's `auth-migrate` job.

- [ ] **Step 1: Write the failing tests**

`platforms/auth-service/auth-service/tests/unit/test_alembic_env.py`:
```python
"""alembic/env.py must take the database URL from the service settings, so migrations run
wherever the service runs -- the root docker-compose stack runs them in a one-shot container
whose only source of truth is DATABASE_URL. Offline mode renders the SQL without connecting,
so these tests need no database. (The migrations use now() defaults, which SQLite rejects, so
an online SQLite run is not an option here.)"""
from pathlib import Path

from alembic import command
from alembic.config import Config

from src.auth.config import settings

SERVICE_ROOT = Path(__file__).resolve().parents[2]


def _config() -> Config:
    cfg = Config(str(SERVICE_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    return cfg


def test_alembic_ini_does_not_hardcode_a_database_url():
    assert not Config(str(SERVICE_ROOT / "alembic.ini")).get_main_option("sqlalchemy.url")


def test_env_py_falls_back_to_the_settings_url(monkeypatch, capsys):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://svc:pw@dbhost:5432/auth_db")
    cfg = _config()
    cfg.set_main_option("sqlalchemy.url", "")  # nothing passed explicitly: env.py must use settings

    command.upgrade(cfg, "head", sql=True)

    sql = capsys.readouterr().out
    assert "CREATE TABLE users" in sql
    assert "CREATE TABLE pending_registrations" in sql
```

- [ ] **Step 2: Run to verify they fail**

Run (from `platforms/auth-service/auth-service`): `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/unit/test_alembic_env.py -v`
Expected: both FAIL — the first because `alembic.ini` still holds `postgresql://postgres:password@localhost:5433/auth_db`; the second with an Alembic/SQLAlchemy error about an empty or missing URL (env.py never consults settings).

- [ ] **Step 3: Blank the URL in `alembic.ini`**

Replace the line
```
sqlalchemy.url = postgresql://postgres:password@localhost:5433/auth_db
```
with
```
# Left blank on purpose: alembic/env.py fills this in from src.auth.config.settings (DATABASE_URL,
# or the POSTGRES_* components), so the URL is never duplicated here. A URL set explicitly on the
# Config object (e.g. by a test) still wins.
sqlalchemy.url =
```

- [ ] **Step 4: Read settings in `env.py`**

Replace the top of `platforms/auth-service/auth-service/alembic/env.py` — from the first line down to and including `target_metadata = Base.metadata` — with:
```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

# The service root, so "src.auth...." resolves the same way the app does (settings), and the src
# directory, which the existing Base import below relies on.
SERVICE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, SERVICE_ROOT)
sys.path.append(os.path.join(SERVICE_ROOT, "src"))

from src.auth.config import settings  # noqa: E402
from auth.db.base import Base  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# alembic.ini leaves the URL blank; take it from the runtime settings unless one was set
# explicitly. Escape '%' so ConfigParser does not try to interpolate it out of a password.
if not config.get_main_option("sqlalchemy.url", None):
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata
```
Leave `run_migrations_offline`, `run_migrations_online` and the bottom dispatch unchanged.

- [ ] **Step 5: Run the new tests, then the whole suite**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/unit/test_alembic_env.py -v`
Expected: 2 passed.

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q`
Expected: 62 passed (60 existing + 2). Delete `test.db` afterwards.

- [ ] **Step 6: Prove it against a real PostgreSQL**

Run (from `platforms/auth-service/auth-service`):
```bash
docker run -d --rm --name qav-auth-migrate-check -e POSTGRES_PASSWORD=check -e POSTGRES_DB=auth_db -p 55433:5432 postgres:15
until docker exec qav-auth-migrate-check pg_isready -U postgres -d auth_db >/dev/null 2>&1; do sleep 1; done
DATABASE_URL=postgresql://postgres:check@localhost:55433/auth_db SECRET_KEY=x .venv/Scripts/python.exe -m alembic upgrade head
docker exec qav-auth-migrate-check psql -U postgres -d auth_db -c '\dt'
docker stop qav-auth-migrate-check
```
Expected: five `Running upgrade` lines (001 → 005), then `alembic_version`, `oauth_accounts`, `pending_registrations`, `refresh_tokens`, `users` listed.

- [ ] **Step 7: Commit**

```bash
git add platforms/auth-service/auth-service/alembic/env.py \
        platforms/auth-service/auth-service/alembic.ini \
        platforms/auth-service/auth-service/tests/unit/test_alembic_env.py
git commit -m "fix(auth-service): take the Alembic database URL from settings, not alembic.ini"
```

---

### Task 2: Root compose stack — Postgres, db-init, migrations, services

**Files:**
- Create: `docker-compose.yml` (repository root)
- Create: `scripts/postgres-init.sh`
- Create: `.gitattributes` (repository root)

**Interfaces:**
- Consumes: Task 1's settings-driven auth migrations; each service's existing Dockerfile (repository-root context) and `/health`.
- Produces: compose services `postgres`, `db-init`, `auth-migrate`, `organization-migrate`, `project-migrate`, `auth-service`, `organization-service`, `project-service` on the default network, reachable by those names on port 8000 (services) / 5432 (postgres). Task 3 adds `gateway` to this file. Volume `qav_postgres_data`. Compose project name `qa-vision`.

- [ ] **Step 1: Line endings**

Create `.gitattributes` at the repository root:
```
# Shell scripts and the NGINX template are copied into Linux containers; a CRLF there turns
# "#!/bin/sh" into "/bin/sh\r: not found". Force LF regardless of a contributor's autocrlf.
*.sh                    text eol=lf
*.template              text eol=lf
```

- [ ] **Step 2: The db-init script**

`scripts/postgres-init.sh`:
```sh
#!/bin/sh
# Creates each service database that does not exist yet. The root docker-compose stack runs this
# on EVERY `up` (job `db-init`): Postgres's own /docker-entrypoint-initdb.d scripts run only on an
# empty volume, so a database added for a new service would otherwise never be created on an
# existing one. Connection comes from PGHOST / PGUSER / PGPASSWORD.
set -eu

for db in auth_db organization_db project_db; do
  if psql -tAc "SELECT 1 FROM pg_database WHERE datname = '$db'" | grep -q 1; then
    echo "database $db exists"
  else
    psql -c "CREATE DATABASE \"$db\""
    echo "database $db created"
  fi
done
```

- [ ] **Step 3: The compose file**

`docker-compose.yml` (repository root):
```yaml
# The whole platform on one host: `SECRET_KEY=... docker compose up -d --build --wait gateway`.
# Each service's own docker-compose.yml under platforms/ still works for developing it alone;
# this stack uses its own volumes and never touches theirs.
name: qa-vision

x-app-healthcheck: &app-healthcheck
  # The slim images have no curl; probe with Python's stdlib
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"]
  interval: 5s
  timeout: 5s
  retries: 12
  start_period: 10s

# Each service and its -migrate job share one environment block, so they cannot drift apart.
x-auth-env: &auth-env
  DATABASE_URL: postgresql://postgres:${POSTGRES_PASSWORD:-postgres}@postgres:5432/auth_db
  SECRET_KEY: ${SECRET_KEY:?set SECRET_KEY (shared by every service)}
  # Links in verification emails must point at the gateway, the only published entry point
  BASE_URL: https://localhost:${GATEWAY_HTTPS_PORT:-8443}

x-organization-env: &organization-env
  DATABASE_URL: postgresql://postgres:${POSTGRES_PASSWORD:-postgres}@postgres:5432/organization_db
  SECRET_KEY: ${SECRET_KEY:?set SECRET_KEY (shared by every service)}
  AUTH_SERVICE_URL: http://auth-service:8000
  # Adding a member calls auth-service's GET /users/{id}, which needs a superuser token
  # (known limitation, see TODO.md "Gateway follow-ups"). Empty means member-adds fail.
  AUTH_SERVICE_TOKEN: ${AUTH_SERVICE_TOKEN:-}

x-project-env: &project-env
  DATABASE_URL: postgresql://postgres:${POSTGRES_PASSWORD:-postgres}@postgres:5432/project_db
  SECRET_KEY: ${SECRET_KEY:?set SECRET_KEY (shared by every service)}
  ORGANIZATION_SERVICE_URL: http://organization-service:8000

x-auth-build: &auth-build
  context: .
  dockerfile: platforms/auth-service/auth-service/Dockerfile

x-organization-build: &organization-build
  context: .
  dockerfile: platforms/organization-service/Dockerfile

x-project-build: &project-build
  context: .
  dockerfile: platforms/project-service/Dockerfile

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
    volumes:
      - qav_postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 3s
      timeout: 3s
      retries: 20
    # No ports: inspect with `docker compose exec postgres psql -U postgres -d project_db`

  db-init:
    image: postgres:15
    environment:
      PGHOST: postgres
      PGUSER: postgres
      PGPASSWORD: ${POSTGRES_PASSWORD:-postgres}
    volumes:
      - ./scripts/postgres-init.sh:/postgres-init.sh:ro
    entrypoint: ["sh", "/postgres-init.sh"]
    depends_on:
      postgres:
        condition: service_healthy

  auth-migrate:
    # Same image as auth-service, which builds it; never pulled from a registry
    image: qa-vision/auth-service:local
    pull_policy: never
    environment: *auth-env
    command: ["alembic", "upgrade", "head"]
    depends_on:
      db-init:
        condition: service_completed_successfully

  organization-migrate:
    # Same image as organization-service, which builds it; never pulled from a registry
    image: qa-vision/organization-service:local
    pull_policy: never
    environment: *organization-env
    command: ["alembic", "upgrade", "head"]
    depends_on:
      db-init:
        condition: service_completed_successfully

  project-migrate:
    # Same image as project-service, which builds it; never pulled from a registry
    image: qa-vision/project-service:local
    pull_policy: never
    environment: *project-env
    command: ["alembic", "upgrade", "head"]
    depends_on:
      db-init:
        condition: service_completed_successfully

  auth-service:
    build: *auth-build
    image: qa-vision/auth-service:local
    environment: *auth-env
    healthcheck: *app-healthcheck
    depends_on:
      auth-migrate:
        condition: service_completed_successfully

  organization-service:
    build: *organization-build
    image: qa-vision/organization-service:local
    environment: *organization-env
    healthcheck: *app-healthcheck
    depends_on:
      organization-migrate:
        condition: service_completed_successfully

  project-service:
    build: *project-build
    image: qa-vision/project-service:local
    environment: *project-env
    healthcheck: *app-healthcheck
    depends_on:
      project-migrate:
        condition: service_completed_successfully

volumes:
  qav_postgres_data:
```

- [ ] **Step 4: Validate the file before starting anything**

Run (repository root): `SECRET_KEY=local-check docker compose config -q && echo ok`
Expected: `ok`.

Run: `env -u SECRET_KEY docker compose config -q`
Expected: fails with `required variable SECRET_KEY is missing a value`.

Run: `grep -c $'\r' scripts/postgres-init.sh .gitattributes`
Expected: `0` for both files (no CR bytes).

- [ ] **Step 5: Bring the stack up on a fresh volume**

Run:
```bash
SECRET_KEY=local-check docker compose up -d --build --wait --wait-timeout 300 auth-service organization-service project-service
docker compose ps -a --format '{{.Service}} {{.Status}}'
docker compose logs db-init auth-migrate organization-migrate project-migrate
```
Expected:
- the `up` command exits 0;
- `db-init` and the three `*-migrate` show `Exited (0)`; the three services show `Up … (healthy)`; `postgres` `Up … (healthy)`;
- db-init logs `database auth_db created` (and the other two); each migrate log ends with its `Running upgrade … -> <head>` lines.

The `*-migrate` jobs have no `build:` of their own — they reuse the image their service builds (`pull_policy: never`), so each image is built once. If compose reports a missing image for a `-migrate` job, report it rather than adding a second `build:`.

Waiting on the named long-running services (not a bare `--wait`) is deliberate: it keeps exited one-shot jobs from being judged as "not running". If a bare `docker compose up -d --wait` also succeeds here, note that in the report; the documented form stays the named one.

- [ ] **Step 6: Each service answers on the shared network**

Run:
```bash
for svc in auth-service organization-service project-service; do
  docker compose exec -T project-service python -c "import urllib.request; print('$svc', urllib.request.urlopen('http://$svc:8000/health', timeout=3).read().decode())"
done
docker compose exec -T postgres psql -U postgres -c '\l' | grep -E 'auth_db|organization_db|project_db'
docker compose exec -T postgres psql -U postgres -d project_db -c '\dt'
```
Expected: three `{"status":"healthy"}` lines; the three databases listed; `projects`, `repositories`, `alembic_version` in `project_db`.

- [ ] **Step 7: A second `up` on the existing volume is a no-op**

Run:
```bash
SECRET_KEY=local-check docker compose up -d --wait --wait-timeout 300 auth-service organization-service project-service
docker compose logs --no-log-prefix db-init | tail -3
docker compose run --rm db-init
SECRET_KEY=local-check docker compose down
```
Expected: `up` exits 0; db-init prints `database auth_db exists` (and the other two), both in the logs and in the extra `run`. `down` without `--volumes` — the root stack's data stays for Task 3.

- [ ] **Step 8: Commit**

```bash
git add .gitattributes docker-compose.yml scripts/postgres-init.sh
git status --short   # nothing else staged; no stray files
git commit -m "feat: repository-root compose stack with one Postgres, db-init and migration jobs"
```

---

### Task 3: The NGINX gateway

**Files:**
- Create: `gateway/Dockerfile`
- Create: `gateway/nginx.conf.template`
- Create: `gateway/entrypoint.sh`
- Modify: `docker-compose.yml` (add the `gateway` service and the `qav_gateway_certs` volume)

**Interfaces:**
- Consumes: Task 2's compose services and names; `.gitattributes` (forces LF on `*.sh`, `*.template`).
- Produces: compose service `gateway`, published on `${GATEWAY_HTTPS_PORT:-8443}` (HTTPS) and `${GATEWAY_HTTP_PORT:-8080}` (HTTP → 301). Image tag `qa-vision/gateway:local`. `docker run --rm <image> nginx -t` validates the config (the entrypoint execs its arguments). Consumed by Task 4.

- [ ] **Step 1: Dockerfile and entrypoint**

`gateway/Dockerfile`:
```dockerfile
FROM nginx:1.27-alpine

# openssl: self-signed certificate on first start; gettext: envsubst for the config template;
# curl: the compose healthcheck
RUN apk add --no-cache openssl gettext curl

COPY nginx.conf.template /etc/qav/nginx.conf.template
COPY entrypoint.sh /usr/local/bin/qav-gateway-entrypoint
RUN chmod +x /usr/local/bin/qav-gateway-entrypoint

EXPOSE 80 443

# Replaces the stock nginx entrypoint on purpose: it would otherwise also render
# /etc/nginx/templates/* into conf.d and run its own scripts.
ENTRYPOINT ["/usr/local/bin/qav-gateway-entrypoint"]
CMD ["nginx", "-g", "daemon off;"]
```

`gateway/entrypoint.sh`:
```sh
#!/bin/sh
# Renders the NGINX config, makes sure a TLS certificate exists, then runs the given command
# (nginx by default; `nginx -t` to validate the configuration).
set -eu

: "${GATEWAY_HTTPS_PORT:=8443}"
export GATEWAY_HTTPS_PORT

# Substitute ONLY this variable, so NGINX's own $host, $request_uri, ... are left alone
envsubst '${GATEWAY_HTTPS_PORT}' < /etc/qav/nginx.conf.template > /etc/nginx/nginx.conf

CERT_DIR=/etc/nginx/certs
mkdir -p "$CERT_DIR"
if [ ! -s "$CERT_DIR/tls.crt" ] || [ ! -s "$CERT_DIR/tls.key" ]; then
  echo "qav-gateway: generating a self-signed certificate for localhost"
  openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
    -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
    -keyout "$CERT_DIR/tls.key" -out "$CERT_DIR/tls.crt" 2>/dev/null
fi

exec "$@"
```

- [ ] **Step 2: The NGINX configuration**

`gateway/nginx.conf.template`:
```nginx
# QA Vision gateway. Rendered by entrypoint.sh; only ${GATEWAY_HTTPS_PORT} is substituted.
# Routing, limits and TLS are specified in docs/superpowers/specs/2026-09-28-api-gateway-design.md.

worker_processes auto;
error_log /dev/stderr warn;

events {
    worker_connections 1024;
}

http {
    server_tokens off;
    default_type application/json;
    client_max_body_size 10m;

    # The client's X-Request-ID if it sent one, else NGINX's own
    map $http_x_request_id $req_id {
        default $http_x_request_id;
        ""      $request_id;
    }

    log_format json escape=json '{'
        '"time":"$time_iso8601",'
        '"request_id":"$req_id",'
        '"remote_addr":"$remote_addr",'
        '"method":"$request_method",'
        '"uri":"$request_uri",'
        '"status":$status,'
        '"upstream":"$upstream_addr",'
        '"upstream_response_time":"$upstream_response_time",'
        '"request_time":$request_time,'
        '"bytes_sent":$bytes_sent'
    '}';
    access_log /dev/stdout json;

    # Keyed on the TCP peer, never on a header a client could set
    limit_req_zone $binary_remote_addr zone=api:10m rate=20r/s;
    limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/s;
    limit_req_status 429;

    # Docker's embedded DNS; with `proxy_pass $upstream` a recreated container (new IP) is found
    # within 10 s instead of the gateway returning 502 until it is restarted
    resolver 127.0.0.11 valid=10s ipv6=off;

    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_set_header Host $host;
    # Overwritten, not appended: the gateway is the edge, so a client-supplied value is discarded
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Request-ID $req_id;
    proxy_connect_timeout 3s;
    proxy_read_timeout 30s;
    # The services' own error responses (JSON) pass through untouched
    proxy_intercept_errors off;

    server {
        listen 80;
        server_name _;

        location / {
            return 301 https://$host:${GATEWAY_HTTPS_PORT}$request_uri;
        }
    }

    server {
        listen 443 ssl;
        server_name _;

        ssl_certificate     /etc/nginx/certs/tls.crt;
        ssl_certificate_key /etc/nginx/certs/tls.key;
        ssl_protocols       TLSv1.2 TLSv1.3;
        # No HSTS: on localhost with a self-signed certificate it would force HTTPS for every
        # localhost port in the browser.

        add_header X-Request-ID $req_id always;

        # NGINX's own errors as JSON. Each named location repeats X-Request-ID because an
        # add_header inside a location replaces the server-level ones.
        error_page 404 @not_found;
        error_page 413 @too_large;
        error_page 429 @too_many_requests;
        error_page 502 @bad_gateway;
        error_page 504 @gateway_timeout;

        location @not_found {
            add_header X-Request-ID $req_id always;
            return 404 '{"detail":"Not Found"}';
        }
        location @too_large {
            add_header X-Request-ID $req_id always;
            return 413 '{"detail":"Request Entity Too Large"}';
        }
        location @too_many_requests {
            add_header X-Request-ID $req_id always;
            add_header Retry-After 1 always;
            return 429 '{"detail":"Too Many Requests"}';
        }
        location @bad_gateway {
            add_header X-Request-ID $req_id always;
            return 502 '{"detail":"Bad Gateway"}';
        }
        location @gateway_timeout {
            add_header X-Request-ID $req_id always;
            return 504 '{"detail":"Gateway Timeout"}';
        }

        # ---- health (never rate-limited) ----
        location = /health {
            return 200 '{"status":"healthy"}';
        }
        location = /health/auth {
            set $upstream http://auth-service:8000;
            proxy_pass $upstream/health;
        }
        location = /health/organizations {
            set $upstream http://organization-service:8000;
            proxy_pass $upstream/health;
        }
        location = /health/projects {
            set $upstream http://project-service:8000;
            proxy_pass $upstream/health;
        }

        # ---- project-service ----
        # A regex location wins over prefix locations, so this takes
        # /api/v1/organizations/{id}/projects[...] away from organization-service below.
        location ~ ^/api/v1/organizations/[0-9]+/projects(/|$) {
            limit_req zone=api burst=40 nodelay;
            set $upstream http://project-service:8000;
            proxy_pass $upstream;
        }
        location /api/v1/projects {
            limit_req zone=api burst=40 nodelay;
            set $upstream http://project-service:8000;
            proxy_pass $upstream;
        }

        # ---- organization-service ----
        location /api/v1/organizations {
            limit_req zone=api burst=40 nodelay;
            set $upstream http://organization-service:8000;
            proxy_pass $upstream;
        }
        location /api/v1/invitations {
            limit_req zone=api burst=40 nodelay;
            set $upstream http://organization-service:8000;
            proxy_pass $upstream;
        }

        # ---- auth-service ----
        # Endpoints that take a password or send an email get the stricter zone as well
        location = /api/v1/auth/login {
            limit_req zone=api burst=40 nodelay;
            limit_req zone=auth burst=10 nodelay;
            set $upstream http://auth-service:8000;
            proxy_pass $upstream;
        }
        location = /api/v1/auth/register {
            limit_req zone=api burst=40 nodelay;
            limit_req zone=auth burst=10 nodelay;
            set $upstream http://auth-service:8000;
            proxy_pass $upstream;
        }
        location = /api/v1/auth/forgot-password {
            limit_req zone=api burst=40 nodelay;
            limit_req zone=auth burst=10 nodelay;
            set $upstream http://auth-service:8000;
            proxy_pass $upstream;
        }
        location = /api/v1/auth/reset-password {
            limit_req zone=api burst=40 nodelay;
            limit_req zone=auth burst=10 nodelay;
            set $upstream http://auth-service:8000;
            proxy_pass $upstream;
        }
        location = /api/v1/auth/resend-verification {
            limit_req zone=api burst=40 nodelay;
            limit_req zone=auth burst=10 nodelay;
            set $upstream http://auth-service:8000;
            proxy_pass $upstream;
        }
        location /api/v1/auth {
            limit_req zone=api burst=40 nodelay;
            set $upstream http://auth-service:8000;
            proxy_pass $upstream;
        }
        location /api/v1/users {
            limit_req zone=api burst=40 nodelay;
            set $upstream http://auth-service:8000;
            proxy_pass $upstream;
        }
        location /api/v1/sso {
            limit_req zone=api burst=40 nodelay;
            set $upstream http://auth-service:8000;
            proxy_pass $upstream;
        }

        # ---- everything else ----
        location / {
            return 404;
        }
    }
}
```

With a variable and no URI part, `proxy_pass $upstream;` forwards the original request URI unchanged; the health locations use `$upstream/health` to replace it.

- [ ] **Step 3: Validate the configuration**

Run (repository root):
```bash
grep -c $'\r' gateway/entrypoint.sh gateway/nginx.conf.template   # expect 0 and 0
docker build -t qa-vision/gateway:local gateway
docker run --rm qa-vision/gateway:local nginx -t
```
Expected: `0` for both files; the build succeeds; `nginx: configuration file /etc/nginx/nginx.conf test is successful`.

- [ ] **Step 4: Add the gateway to the compose file**

In `docker-compose.yml`, add this service after `project-service`:
```yaml
  gateway:
    build: ./gateway
    image: qa-vision/gateway:local
    ports:
      - "${GATEWAY_HTTPS_PORT:-8443}:443"
      - "${GATEWAY_HTTP_PORT:-8080}:80"
    environment:
      # Must equal the published HTTPS port: the HTTP -> HTTPS redirect is built from it
      GATEWAY_HTTPS_PORT: ${GATEWAY_HTTPS_PORT:-8443}
    volumes:
      - qav_gateway_certs:/etc/nginx/certs
    healthcheck:
      test: ["CMD", "curl", "-fsk", "https://localhost/health"]
      interval: 5s
      timeout: 5s
      retries: 12
    depends_on:
      auth-service:
        condition: service_healthy
      organization-service:
        condition: service_healthy
      project-service:
        condition: service_healthy
```
and add `qav_gateway_certs:` under `volumes:` next to `qav_postgres_data:`.

- [ ] **Step 5: Start the stack and check the gateway by hand**

Run:
```bash
SECRET_KEY=local-check docker compose up -d --build --wait --wait-timeout 300 gateway
curl -ks https://localhost:8443/health; echo
curl -ks https://localhost:8443/health/projects; echo
curl -ks -o /dev/null -w '%{http_code} %{redirect_url}\n' http://localhost:8080/api/v1/projects/1
curl -ks https://localhost:8443/no/such/path; echo
docker compose logs --no-log-prefix gateway | tail -3
```
Expected: `{"status":"healthy"}` twice; `301 https://localhost:8443/api/v1/projects/1`; `{"detail":"Not Found"}`; JSON access-log lines.

- [ ] **Step 6: A client-supplied X-Forwarded-For changes nothing**

Run:
```bash
docker compose exec -T gateway grep -n 'X-Forwarded-For' /etc/nginx/nginx.conf
docker compose exec -T gateway curl -sk -o /dev/null -w '%{http_code}\n' -H 'X-Forwarded-For: 6.6.6.6' https://localhost/health/projects
docker compose logs --no-log-prefix gateway | tail -1
```
Expected: the directive reads `proxy_set_header X-Forwarded-For $remote_addr;` (set, not `$proxy_add_x_forwarded_for`); `200`; the last access-log line shows `"remote_addr":"127.0.0.1"`, not `6.6.6.6` — the address the rate limit keys on and the value the upstream receives both come from the TCP peer.

- [ ] **Step 7: A recreated service is found again without restarting the gateway**

Run:
```bash
SECRET_KEY=local-check docker compose up -d --force-recreate --no-deps --wait project-service
for i in $(seq 1 15); do code=$(curl -ks -o /dev/null -w '%{http_code}' https://localhost:8443/health/projects); echo "$i $code"; [ "$code" = 200 ] && break; sleep 1; done
SECRET_KEY=local-check docker compose down
```
Expected: `200` within ~10 attempts. Plain `down` (no `--volumes`).

- [ ] **Step 8: Commit**

```bash
git add gateway/Dockerfile gateway/nginx.conf.template gateway/entrypoint.sh docker-compose.yml
git status --short
git commit -m "feat(gateway): NGINX gateway with routing, per-IP rate limits, self-signed TLS"
```

---

### Task 4: Smoke test and CI job

**Files:**
- Create: `scripts/smoke_gateway.sh`
- Modify: `.github/workflows/ci.yml` (add job `gateway`)

**Interfaces:**
- Consumes: the running stack from Tasks 2–3 (`docker compose up -d --build --wait gateway`), compose service `auth-service` (for minting a token with PyJWT and `SECRET_KEY`).
- Produces: `bash scripts/smoke_gateway.sh` — exits 0 when every check passes, 1 otherwise, printing `ok …` / `FAIL …` per check.

- [ ] **Step 1: The smoke script**

`scripts/smoke_gateway.sh`:
```bash
#!/usr/bin/env bash
# End-to-end checks through the gateway, one per routing rule and gateway feature.
# Run from anywhere after:  SECRET_KEY=... docker compose up -d --build --wait gateway
set -uo pipefail
cd "$(dirname "$0")/.."

HTTPS_PORT="${GATEWAY_HTTPS_PORT:-8443}"
HTTP_PORT="${GATEWAY_HTTP_PORT:-8080}"
BASE="https://localhost:${HTTPS_PORT}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
failures=0

pass() { printf 'ok    %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1"; failures=$((failures + 1)); }

# check NAME EXPECTED_STATUS METHOD URL [curl args...]; body -> $TMP/body, headers -> $TMP/headers
check() {
  local name="$1" expected="$2" method="$3" url="$4"
  shift 4
  local status
  status="$(curl -ks -o "$TMP/body" -D "$TMP/headers" -w '%{http_code}' -X "$method" "$@" "$url")"
  if [ "$status" = "$expected" ]; then
    pass "$name ($status)"
  else
    fail "$name: expected $expected, got $status: $(head -c 300 "$TMP/body")"
  fi
}

# body_has NAME TEXT -- the last response body contains TEXT
body_has() {
  if grep -qF -- "$2" "$TMP/body"; then pass "$1"; else fail "$1: body was $(head -c 300 "$TMP/body")"; fi
}

# A valid access token for a user id that is a member of nothing, signed with the stack's key
TOKEN="$(docker compose exec -T auth-service python -c '
import datetime, os, jwt
exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)
print(jwt.encode({"sub": "999999", "exp": exp}, os.environ["SECRET_KEY"], algorithm="HS256"))
' | tr -d '\r\n')"
if [ -z "$TOKEN" ]; then
  echo "FAIL  could not mint a token inside auth-service"; exit 1
fi
AUTH=(-H "Authorization: Bearer ${TOKEN}")

# ---- gateway and health ----
check "gateway /health" 200 GET "$BASE/health"
body_has "gateway /health body" '{"status":"healthy"}'
for svc in auth organizations projects; do
  check "/health/$svc reaches the service" 200 GET "$BASE/health/$svc"
done

# ---- one real call per routing rule ----
check "/api/v1/users/me with a bad token -> auth-service" 401 GET "$BASE/api/v1/users/me" \
  -H "Authorization: Bearer not-a-token"
check "/api/v1/organizations/1/members/me for a non-member -> organization-service" 404 GET \
  "$BASE/api/v1/organizations/1/members/me" "${AUTH[@]}"
check "/api/v1/organizations/1/projects -> project-service (overlap route)" 404 GET \
  "$BASE/api/v1/organizations/1/projects" "${AUTH[@]}"
body_has "... answered only after organization-service said 404 (shared network works)" \
  '"Organization not found"'
check "/api/v1/projects/1 -> project-service" 404 GET "$BASE/api/v1/projects/1" "${AUTH[@]}"
body_has "... answered by project-service" '"Project not found"'

# ---- gateway behaviour ----
check "unknown path" 404 GET "$BASE/no/such/path"
body_has "unknown path answers JSON" '{"detail":"Not Found"}'
if grep -qi '^x-request-id: ' "$TMP/headers"; then pass "X-Request-ID on responses"; else fail "no X-Request-ID header"; fi

check "client X-Request-ID is echoed" 200 GET "$BASE/health" -H "X-Request-ID: smoke-123"
if grep -qi '^x-request-id: smoke-123' "$TMP/headers"; then pass "X-Request-ID echo value"; else fail "X-Request-ID not echoed"; fi

redirect_status="$(curl -s -o /dev/null -D "$TMP/redirect" -w '%{http_code}' "http://localhost:${HTTP_PORT}/health")"
if [ "$redirect_status" = 301 ] && grep -qi "^location: https://localhost:${HTTPS_PORT}/health" "$TMP/redirect"; then
  pass "HTTP redirects to HTTPS on port ${HTTPS_PORT}"
else
  fail "HTTP redirect: got $redirect_status, $(grep -i '^location' "$TMP/redirect")"
fi

# ---- rate limiting last: it leaves this client's auth bucket drained for a few seconds ----
limited=0
for _ in $(seq 1 30); do
  code="$(curl -ks -o "$TMP/rl_body" -D "$TMP/rl_headers" -w '%{http_code}' -X POST "$BASE/api/v1/auth/login")"
  if [ "$code" = 429 ]; then
    limited=$((limited + 1))
    cp "$TMP/rl_body" "$TMP/body"; cp "$TMP/rl_headers" "$TMP/headers"
  fi
done
if [ "$limited" -gt 0 ]; then
  pass "rate limit on /api/v1/auth/login ($limited of 30 got 429)"
  body_has "429 answers JSON" '{"detail":"Too Many Requests"}'
  if grep -qi '^retry-after: 1' "$TMP/headers"; then pass "429 carries Retry-After: 1"; else fail "429 without Retry-After"; fi
else
  fail "rate limit on /api/v1/auth/login: 30 rapid requests, none got 429"
fi

if [ "$failures" -gt 0 ]; then
  echo "$failures check(s) failed"
  exit 1
fi
echo "all gateway checks passed"
```

- [ ] **Step 2: Watch it fail against a stack without the gateway**

Run (repository root):
```bash
SECRET_KEY=local-check docker compose up -d --build --wait --wait-timeout 300 auth-service organization-service project-service
bash scripts/smoke_gateway.sh; echo "exit=$?"
```
Expected: `FAIL` lines (connection refused → status `000`) and `exit=1` — the script does detect a missing gateway.

- [ ] **Step 3: Run it against the full stack**

Run:
```bash
SECRET_KEY=local-check docker compose up -d --build --wait --wait-timeout 300 gateway
bash scripts/smoke_gateway.sh; echo "exit=$?"
```
Expected: every line `ok`, `all gateway checks passed`, `exit=0`.

If a check fails, fix the gateway/compose (Task 3/Task 2 files), not the check — unless the check itself contradicts the spec, in which case report it.

- [ ] **Step 4: A deliberately broken route is caught**

Temporarily change the project regex location in `gateway/nginx.conf.template` to proxy to `organization-service` instead of `project-service`, rebuild and rerun:
```bash
SECRET_KEY=local-check docker compose up -d --build --wait gateway
bash scripts/smoke_gateway.sh; echo "exit=$?"
```
Expected: the "(overlap route)" check or its body check FAILs, `exit=1`. Revert the change (`git checkout gateway/nginx.conf.template`), rebuild, rerun: `exit=0`. Then `SECRET_KEY=local-check docker compose down` (no `--volumes`).

- [ ] **Step 5: CI job**

In `.github/workflows/ci.yml`, append this job at the end of `jobs:` (same indentation as `tests:` and `smoke:`):
```yaml
  gateway:
    name: Gateway and full stack
    runs-on: ubuntu-latest
    env:
      # docker-compose.yml requires SECRET_KEY and has no fallback
      SECRET_KEY: ci-gateway-secret
    steps:
      - uses: actions/checkout@v7

      - name: Check the NGINX configuration
        run: |
          docker build -t qa-vision/gateway:ci gateway
          docker run --rm qa-vision/gateway:ci nginx -t

      # Waiting on the gateway waits on everything it depends on: postgres, db-init, the three
      # migrations and the three services. The one-shot jobs are not waited on themselves.
      - name: Start the platform
        run: docker compose up -d --build --wait --wait-timeout 300 gateway

      - name: Smoke-test through the gateway
        run: bash scripts/smoke_gateway.sh

      - name: Show logs on failure
        if: failure()
        run: docker compose logs

      - name: Tear down
        if: always()
        run: docker compose down --volumes
```
Change nothing else in the file. Validate: `python -c "import yaml,sys; print(list(yaml.safe_load(open('.github/workflows/ci.yml'))['jobs']))"` (with any venv that has PyYAML, e.g. `platforms/organization-service/.venv/Scripts/python.exe`) → `['tests', 'smoke', 'gateway']`.

- [ ] **Step 6: Commit**

```bash
git add scripts/smoke_gateway.sh .github/workflows/ci.yml
git status --short
git commit -m "ci: smoke-test every gateway route against the full stack"
```

---

### Task 5: Documentation and follow-ups

**Files:**
- Create: `gateway/README.md`
- Modify: `README.md` (repository root)
- Modify: `platforms/project-service/README.md` (one command)
- Modify: `TODO.md`

**Interfaces:** none (docs only).

- [ ] **Step 1: `gateway/README.md`**

````markdown
# Gateway

NGINX in front of every QA Vision service. Configuration only — no code.
Design: `docs/superpowers/specs/2026-09-28-api-gateway-design.md`.

## Routes

| Path | Service |
|---|---|
| `/api/v1/organizations/{id}/projects…` | project-service |
| `/api/v1/projects…` | project-service |
| `/api/v1/organizations…`, `/api/v1/invitations…` | organization-service |
| `/api/v1/auth…`, `/api/v1/users…`, `/api/v1/sso…` | auth-service |
| `/health` | the gateway itself |
| `/health/auth`, `/health/organizations`, `/health/projects` | that service's `/health` |
| anything else | `404 {"detail":"Not Found"}` |

The first row is a regex location: NGINX checks regex locations before prefix ones, which is
what takes `/organizations/{id}/projects` away from organization-service.

## Limits

- Per client IP: 20 requests/s (burst 40) on every `/api/v1` route; additionally 5 requests/s
  (burst 10) on `login`, `register`, `forgot-password`, `reset-password`, `resend-verification`.
  Over the limit: `429 {"detail":"Too Many Requests"}` with `Retry-After: 1`. Health routes are
  never limited.
- Request bodies up to 10 MB; upstream connect timeout 3 s, read timeout 30 s.
- NGINX's own errors (404, 413, 429, 502, 504) are JSON; the services' errors pass through.

## TLS

HTTPS on host port `${GATEWAY_HTTPS_PORT:-8443}`; HTTP on `${GATEWAY_HTTP_PORT:-8080}` redirects
to it. On first start the entrypoint generates a self-signed certificate for `localhost` into the
`qav_gateway_certs` volume. Use `curl -k`, or trust it once:
`docker compose cp gateway:/etc/nginx/certs/tls.crt ./qav-localhost.crt`.
To use your own, put `tls.crt` and `tls.key` in that volume before starting.

## Requests and logs

Every response carries `X-Request-ID` (yours if you sent one); the same id is forwarded to the
service. `docker compose logs gateway` shows one JSON line per request.

## Adding a service

1. In `nginx.conf.template`, add a `location` for its path prefix with
   `limit_req zone=api burst=40 nodelay;`, `set $upstream http://<service>:8000;` and
   `proxy_pass $upstream;` — plus a `= /health/<name>` location.
2. In the root `docker-compose.yml`, add the service, its `-migrate` job, its database to
   `scripts/postgres-init.sh`, and a `depends_on` entry under `gateway`.
3. Add a routing check and a `/health/<name>` check to `scripts/smoke_gateway.sh`.
````

- [ ] **Step 2: Root README — running the platform**

In the repository root `README.md`, add this section immediately before `## Project Structure`:
````markdown
## Running the platform

Everything — auth, organization and project services, one PostgreSQL, and the gateway — from the
repository root:

```bash
export SECRET_KEY=<a long random value>        # required; shared by every service
docker compose up -d --build --wait gateway
curl -k https://localhost:8443/health          # {"status":"healthy"}
```

- All API calls go through `https://localhost:8443/api/v1/...` (see `gateway/README.md` for the
  routes). The certificate is self-signed: use `curl -k`, or trust
  `docker compose cp gateway:/etc/nginx/certs/tls.crt ./qav-localhost.crt` once.
- Databases are created and migrated automatically on every `up`.
- Inspect a database: `docker compose exec postgres psql -U postgres -d project_db`.
- Stop: `docker compose down`. Wipe all data: `docker compose down --volumes`.
- Ports: `GATEWAY_HTTPS_PORT` (default 8443) and `GATEWAY_HTTP_PORT` (default 8080).
- Adding members to an organization needs `AUTH_SERVICE_TOKEN` set to a superuser's token (a
  known limitation; see `TODO.md`).

Each service's own `docker-compose.yml` under `platforms/` still works for developing it alone.
````
Also, inside the `## Project Structure` code block, add after the `├── shared/` line:
```
├── gateway/                        # NGINX gateway: routing, rate limits, TLS
```
Change nothing else in README.md.

- [ ] **Step 3: project-service README**

In `platforms/project-service/README.md`, in the "With Docker" block, change `docker compose up --build` to `docker compose up -d --build` so the migration command on the next line is reachable.

- [ ] **Step 4: TODO.md**

In `TODO.md`, directly after the Phase 3: Project Service block (after item 50.2), add:
```markdown
### API Gateway and full stack
- [x] NGINX gateway: routing, per-IP rate limits, self-signed TLS, JSON errors, request ids, JSON access log
- [x] Repository-root docker-compose: one Postgres, db-init, per-service migration jobs, shared SECRET_KEY
- [x] CI: full-stack smoke test through the gateway

### Gateway follow-ups
- [ ] Monitoring dashboards (Prometheus/Grafana) — *Phase 1, "Basic monitoring stack"*
- [ ] Kubernetes ingress; real certificates — *Phase 1 infra, when a cluster exists*
- [ ] Service-to-service token so organization-service can check users in auth-service — *soon: adding a member through the full stack needs a superuser `AUTH_SERVICE_TOKEN` until then*
- [ ] Shared rate limits in Redis — *when more than one gateway instance runs*
- [ ] JWT validation and per-user limits at the gateway — *when the gateway should reject bad tokens itself*
- [ ] API docs through the gateway — *when a frontend or partner needs browsable docs*
- [ ] WebSockets — *Phase 3, real-time features*
```

- [ ] **Step 5: Commit**

```bash
git add gateway/README.md README.md platforms/project-service/README.md TODO.md
git status --short
git commit -m "docs: running the full platform, gateway reference, follow-ups"
```
