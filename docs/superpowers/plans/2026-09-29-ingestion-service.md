# Ingestion Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `platforms/ingestion-service` — project API keys for CI, `POST /collect/runs` that validates and stores one test run with its results, a small read API, Prometheus metrics — and wire it into the root stack, the gateway and CI.

**Architecture:** A FastAPI service mirroring project-service, on `qav-shared`, with its own `ingestion_db`. The collector authenticates with a SHA-256-hashed project API key looked up locally (no other service on the upload path). People authenticate with their JWT; their role comes from project-service's `GET /projects/{id}` (`my_role`), called with their own token.

**Tech Stack:** Python 3.11, FastAPI 0.104, Pydantic v2, SQLAlchemy 2.0, Alembic, PostgreSQL (SQLite in tests), PyJWT, httpx + respx, prometheus_client, pytest, Docker, NGINX.

**Spec:** `docs/superpowers/specs/2026-09-29-ingestion-service-design.md`

**Branch:** `feat/ingestion-service`, stacked on `feat/api-gateway` (PR #8 — root compose stack, gateway, smoke script).

## Global Constraints

- Integer ids everywhere; `project_id` / `organization_id` carry no foreign key.
- Tables `api_keys`, `test_runs`, `test_results`. ORM classes `ApiKey`, `Run`, `RunResult` — never `Test…` (pytest would try to collect them).
- Key format `qav_` + `secrets.token_urlsafe(32)`; `key_prefix` = first 12 characters; `key_hash` = SHA-256 hex, unique. The full key is returned only by the create endpoint and never stored or logged.
- `ci_provider` ∈ `github_actions, gitlab_ci, jenkins, other, local`; result `status` ∈ `passed, failed, skipped, errored` (input `error` → stored `errored`).
- `test_key` = SHA-256 hex of `suite + "\0" + class_name + "\0" + name`.
- `UNIQUE (project_id, idempotency_key)` named `uq_test_runs_project_idempotency`; NULL idempotency keys never collide.
- Limits: `MAX_RESULTS_PER_RUN = 20000`; `MAX_TEXT_BYTES = 65536` (message/details truncated at a UTF-8 character boundary, `truncated = true`, never rejected); `finished_at ≥ started_at`, `finished_at ≤ now + 1 h`; `commit_sha` `^[0-9a-fA-F]{7,40}$`; `Idempotency-Key` 1–255 printable ASCII (`^[\x21-\x7e]+$`).
- `POST /collect/runs`: 201 stored; 200 replay (same key + same `request_hash`); 409 `{"detail":"Idempotency-Key reused with a different payload"}`; 401 `{"detail":"Invalid API key"}` + `WWW-Authenticate: Bearer`; 422 validation. Never calls another service.
- Roles: create/revoke keys = owner, admin, member; list keys, list runs, get run = all five roles. Non-member → 404; project-service unreachable / 5xx / malformed 200 → 503.
- Defaults: `PROJECT_SERVICE_URL=http://localhost:8002`, `PROJECT_SERVICE_TIMEOUT_SECONDS=3.0`; list `limit` default 50, max 100.
- Metrics (own registry, `/metrics`, not routed by the gateway): `qav_ingest_runs_total`, `qav_ingest_results_total`, `qav_ingest_rejected_total{reason=auth|validation|conflict}`, `qav_ingest_duration_seconds`.
- Service compose: app host port **8003**, db **5436**. Root stack: `ingestion_db`, `ingestion-migrate`, `ingestion-service`, gateway routes `~ ^/api/v1/projects/[0-9]+/(api-keys|runs)(/|$)`, `/api/v1/runs`, `/api/v1/collect` (zone `collect` 10 r/s burst 20), `= /health/ingestion`.

## Review Focus

- **Clock skew between CI runner and server** — a `finished_at` a few minutes ahead must be accepted, a day ahead rejected; pinned in Task 4 (`test_finished_at_slightly_in_the_future_is_accepted`).
- **Multi-byte text at the truncation boundary** — cutting a 4-byte emoji in half must not produce invalid UTF-8 or a 500; pinned in Task 4 (`test_truncation_never_splits_a_character`).
- **A collector retrying after a timeout that actually succeeded** — must get 200 with the same run id, not a second run; pinned in Task 4.
- **Invalid key AND invalid body** — must answer 401 (not 422), so an unauthenticated caller learns nothing about the schema; pinned in Task 4.
- **The smoke test run twice on the same volume** — it creates organizations/projects; fixed ids like 1 would then belong to the smoke user and flip "non-member" checks to 200. Task 7 moves those checks to id 999999 and gives created names a unique suffix.

---

### Task 1: Service skeleton — config, models, migration, health, metrics endpoint, container, CI

**Files:**
- Create: `platforms/ingestion-service/requirements.txt`, `.gitignore`, `.env.example`
- Create: `platforms/ingestion-service/src/__init__.py`, `src/ingestion/__init__.py`, `src/ingestion/{api,api/v1,api/v1/endpoints,core,db,models,schemas,service,utils}/__init__.py`
- Create: `src/ingestion/core/config.py`, `src/ingestion/db/base.py`, `src/ingestion/db/session.py`
- Create: `src/ingestion/models/api_key.py`, `src/ingestion/models/run.py` (and fill `models/__init__.py`)
- Create: `src/ingestion/utils/tokens.py`, `src/ingestion/utils/metrics.py`
- Create: `src/ingestion/api/v1/api.py`, `src/ingestion/api/main.py`
- Create: `alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/README`, `alembic/versions/001_create_ingestion_tables.py`
- Create: `tests/conftest.py`, `tests/unit/test_migration.py`, `tests/unit/test_tokens.py`, `tests/integration/test_health_and_metrics.py`
- Create: `Dockerfile`, `docker-compose.yml`
- Modify: `.github/workflows/ci.yml` (one entry in `tests`, one in `smoke`)

All paths below are relative to `platforms/ingestion-service/` unless they start at the repository root.

**Interfaces:**
- Produces: `settings` (fields in Step 4); `Base`; `get_db`, `SessionLocal`; models `ApiKey`, `Run`, `RunResult` (columns in Steps 5–6, exported from `src.ingestion.models`); `decode_token(token) -> dict` (raises `ValueError`); `metrics` module with `RUNS`, `RESULTS`, `REJECTED`, `DURATION`, `render() -> bytes`, `CONTENT_TYPE`; `api_router` (empty); fixtures `db`, `client`, `auth`, `http`; helper `make_token(user_id, **claims)` in conftest.

- [ ] **Step 1: Dependencies, ignore file, env example, venv**

`requirements.txt`:
```
fastapi==0.104.1
uvicorn[standard]==0.27.0
pydantic[email]==2.7.0
pydantic-settings==2.2.1
SQLAlchemy==2.0.29
psycopg2-binary==2.9.9
alembic==1.13.1
PyJWT==2.8.0
python-dotenv==1.0.0
httpx==0.27.0
respx==0.21.1
prometheus-client==0.20.0
pytest==8.1.1
# Relative path, resolved from this file's directory. The Dockerfile mirrors the repo
# layout so this same path resolves inside the image.
-e ../../shared
```

Run (repository root):
```bash
cp platforms/project-service/.gitignore platforms/ingestion-service/.gitignore
```
(project-service's `.gitignore` already ends with the `test.db` line.)

`.env.example`:
```
# Environment variables for the Ingestion Service
APP_NAME=Ingestion Service
DEBUG=False
API_V1_STR=/api/v1

# Must equal auth-service's SECRET_KEY: this service verifies the JWTs auth-service issues
SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256

POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=ingestion_db

PROJECT_SERVICE_URL=http://localhost:8002
PROJECT_SERVICE_TIMEOUT_SECONDS=3.0
MAX_RESULTS_PER_RUN=20000
MAX_TEXT_BYTES=65536
```

Create every `__init__.py` listed under **Files** as an empty file. Then:
```bash
cd platforms/ingestion-service
py -3.11 -m venv .venv          # Python 3.11: psycopg2-binary has no wheel for newer versions here
.venv/Scripts/python.exe -m pip install -r requirements.txt
```
Expected: ends with `Successfully installed ... prometheus-client-0.20.0 ... qav-shared-0.1.0 ...`. (If `py -3.11` is unavailable, use whichever Python 3.11 created `platforms/project-service/.venv`.)

- [ ] **Step 2: Write the failing tests**

`tests/conftest.py`:
```python
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.ingestion.api.main import app
from src.ingestion.core.config import settings
from src.ingestion.db.base import Base
from src.ingestion.db.session import get_db
from src.ingestion.models import ApiKey, Run, RunResult  # noqa: F401  registers tables

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def make_token(user_id: int, **claims) -> str:
    payload = {"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(minutes=5), **claims}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth():
    """auth(user_id) -> headers carrying a valid access token for that user."""

    def _auth(user_id: int = 1) -> dict:
        return {"Authorization": f"Bearer {make_token(user_id)}"}

    return _auth


@pytest.fixture
def http():
    """A respx router active for the test; any outgoing request without a route raises."""
    with respx.mock(assert_all_called=False) as router:
        yield router
```

`tests/unit/test_tokens.py`:
```python
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from src.ingestion.core.config import settings
from src.ingestion.utils.tokens import decode_token


def _encode(**claims) -> str:
    payload = {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5), **claims}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def test_valid_access_token_decodes():
    assert decode_token(_encode())["sub"] == "1"


def test_refresh_token_is_rejected():
    with pytest.raises(ValueError):
        decode_token(_encode(token_type="refresh"))


def test_token_signed_with_another_key_is_rejected():
    with pytest.raises(ValueError):
        decode_token(jwt.encode({"sub": "1"}, "not-the-secret", algorithm=settings.ALGORITHM))
```

`tests/integration/test_health_and_metrics.py`:
```python
def test_health_needs_no_token(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_metrics_are_prometheus_text(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    for name in ("qav_ingest_runs_total", "qav_ingest_results_total",
                 "qav_ingest_rejected_total", "qav_ingest_duration_seconds"):
        assert name in response.text
```

`tests/unit/test_migration.py`:
```python
"""Runs the real Alembic migration against a throwaway SQLite DB (the rest of the suite uses
create_all), catching model/migration drift and exercising the constraints."""
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from src.ingestion.db.base import Base
from src.ingestion.models import ApiKey, Run, RunResult  # noqa: F401  registers tables

SERVICE_ROOT = Path(__file__).resolve().parents[2]

KEY = (
    "INSERT INTO api_keys (project_id, organization_id, name, key_prefix, key_hash, created_by)"
    " VALUES (1, 1, 'k', 'qav_abcdefgh', :hash, 1)"
)
RUN = (
    "INSERT INTO test_runs (project_id, api_key_id, idempotency_key, request_hash, ci_provider,"
    " started_at, finished_at, duration_ms, total, passed, failed, skipped, errored)"
    " VALUES (1, 1, :idem, 'h', :provider, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:01+00:00',"
    " 1000, 0, 0, 0, 0, 0)"
)


@pytest.fixture
def migrated_engine(tmp_path):
    url = f"sqlite:///{(tmp_path / 'migration_test.db').as_posix()}"
    cfg = Config()  # no ini file: env.py would otherwise reconfigure logging for the whole test run
    cfg.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    try:
        yield engine
    finally:
        engine.dispose()


def test_migration_creates_model_tables(migrated_engine):
    tables = set(inspect(migrated_engine).get_table_names())
    assert {"api_keys", "test_runs", "test_results"} <= set(Base.metadata.tables)
    assert set(Base.metadata.tables) <= tables


def test_migration_columns_match_models(migrated_engine):
    inspector = inspect(migrated_engine)
    for table_name, table in Base.metadata.tables.items():
        migrated = {col["name"] for col in inspector.get_columns(table_name)}
        assert {col.name for col in table.columns} == migrated, f"column drift in {table_name}"


def test_key_hash_is_unique(migrated_engine):
    with migrated_engine.begin() as conn:
        conn.execute(text(KEY), {"hash": "a" * 64})
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as conn:
            conn.execute(text(KEY), {"hash": "a" * 64})


def test_ci_provider_check(migrated_engine):
    with migrated_engine.begin() as conn:
        conn.execute(text(KEY), {"hash": "b" * 64})
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as conn:
            conn.execute(text(RUN), {"idem": None, "provider": "travis"})


def test_idempotency_key_unique_per_project_but_nulls_do_not_collide(migrated_engine):
    with migrated_engine.begin() as conn:
        conn.execute(text(KEY), {"hash": "c" * 64})
        conn.execute(text(RUN), {"idem": None, "provider": "local"})
        conn.execute(text(RUN), {"idem": None, "provider": "local"})  # must not raise
        conn.execute(text(RUN), {"idem": "run-1", "provider": "local"})
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as conn:
            conn.execute(text(RUN), {"idem": "run-1", "provider": "local"})


def test_result_status_check(migrated_engine):
    with migrated_engine.begin() as conn:
        conn.execute(text(KEY), {"hash": "d" * 64})
        conn.execute(text(RUN), {"idem": None, "provider": "local"})
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO test_results (run_id, test_key, suite, class_name, name, status, duration_ms, truncated)"
                " VALUES (1, :k, '', '', 't', 'error', 0, 0)"
            ), {"k": "e" * 64})
```

- [ ] **Step 3: Run to verify failure**

Run (from `platforms/ingestion-service`): `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q`
Expected: collection error — `ModuleNotFoundError: No module named 'src.ingestion.api.main'` (or `…core.config`).

- [ ] **Step 4: Config, db, tokens**

`src/ingestion/core/config.py`:
```python
"""Configuration management for Ingestion Service."""
from qav_shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    APP_NAME: str = "Ingestion Service"
    APP_VERSION: str = "0.1.0"

    POSTGRES_DB: str = "ingestion_db"

    # People's roles come from project-service's GET /projects/{id} (my_role)
    PROJECT_SERVICE_URL: str = "http://localhost:8002"
    PROJECT_SERVICE_TIMEOUT_SECONDS: float = 3.0

    # One upload is one transaction; these keep it bounded
    MAX_RESULTS_PER_RUN: int = 20000
    MAX_TEXT_BYTES: int = 65536


settings = Settings()
```

`src/ingestion/db/base.py`:
```python
from sqlalchemy.orm import declarative_base

# Deliberately per-service (not in qav_shared): a declarative base is a global registry of
# mapped classes, and sharing one would mix services' tables into a single metadata.
Base = declarative_base()
```

`src/ingestion/db/session.py`:
```python
from qav_shared.db import make_get_db, make_session_factory

from src.ingestion.core.config import settings

SessionLocal = make_session_factory(settings.database_url)
get_db = make_get_db(SessionLocal)
```

`src/ingestion/utils/tokens.py`:
```python
from jwt import InvalidTokenError, decode

from src.ingestion.core.config import settings


def decode_token(token: str) -> dict:
    try:
        payload = decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except InvalidTokenError:
        raise ValueError("Could not validate credentials")
    # auth-service signs refresh tokens with the same key and `sub`; only `token_type` tells them
    # apart. Refresh tokens are long-lived and must not reach the API.
    if payload.get("token_type") == "refresh":
        raise ValueError("refresh tokens cannot be used for API access")
    return payload
```

- [ ] **Step 5: `ApiKey` model**

`src/ingestion/models/api_key.py`:
```python
from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from src.ingestion.db.base import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    # No FKs: projects and organizations live in other services' databases
    project_id = Column(Integer, nullable=False, index=True)
    organization_id = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    key_prefix = Column(String(12), nullable=False)  # "qav_" + 8, shown in listings
    key_hash = Column(String(64), nullable=False)    # SHA-256 hex of the full key
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),)
```

- [ ] **Step 6: `Run` and `RunResult` models, exports**

`src/ingestion/models/run.py`:
```python
from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, false,
)
from sqlalchemy.sql import func

from src.ingestion.db.base import Base

CI_PROVIDERS = ("github_actions", "gitlab_ci", "jenkins", "other", "local")
STATUSES = ("passed", "failed", "skipped", "errored")


class Run(Base):
    """One upload: one CI job's test results. Table test_runs. (Not named TestRun: pytest would
    try to collect any imported class whose name starts with Test.)"""

    __tablename__ = "test_runs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, nullable=False)
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=False)
    idempotency_key = Column(String(255), nullable=True)
    request_hash = Column(String(64), nullable=False)
    ci_provider = Column(String(20), nullable=False)
    ci_run_url = Column(String(2048), nullable=True)
    commit_sha = Column(String(40), nullable=True)
    branch = Column(String(255), nullable=True)
    environment = Column(String(100), nullable=True)
    agent_version = Column(String(50), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=False)
    duration_ms = Column(Integer, nullable=False)
    # Computed by the server from the results, never taken from the payload
    total = Column(Integer, nullable=False)
    passed = Column(Integer, nullable=False)
    failed = Column(Integer, nullable=False)
    skipped = Column(Integer, nullable=False)
    errored = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("project_id", "idempotency_key", name="uq_test_runs_project_idempotency"),
        CheckConstraint(
            "ci_provider IN ('github_actions','gitlab_ci','jenkins','other','local')", name="chk_test_runs_ci_provider"
        ),
        Index("ix_test_runs_project_created", "project_id", "created_at"),
        Index("ix_test_runs_project_branch", "project_id", "branch"),
    )


class RunResult(Base):
    """One test case's outcome within a run. Table test_results."""

    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    test_key = Column(String(64), nullable=False, index=True)  # sha256(suite \0 class_name \0 name)
    suite = Column(String(500), nullable=False, default="")
    class_name = Column(String(500), nullable=False, default="")
    name = Column(String(1000), nullable=False)
    status = Column(String(10), nullable=False)
    duration_ms = Column(Integer, nullable=False)
    message = Column(Text, nullable=True)
    details = Column(Text, nullable=True)
    truncated = Column(Boolean, nullable=False, default=False, server_default=false())
    file = Column(String(1000), nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('passed','failed','skipped','errored')", name="chk_test_results_status"),
    )
```

`src/ingestion/models/__init__.py` (replace the empty file):
```python
from src.ingestion.models.api_key import ApiKey
from src.ingestion.models.run import Run, RunResult

__all__ = ["ApiKey", "Run", "RunResult"]
```

- [ ] **Step 7: Metrics, router, app**

`src/ingestion/utils/metrics.py`:
```python
"""Prometheus metrics, on their own registry so /metrics shows only what this service defines.
Served inside the Docker network; the gateway does not route /metrics."""
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest

REGISTRY = CollectorRegistry()

RUNS = Counter("qav_ingest_runs", "Test runs stored", registry=REGISTRY)
RESULTS = Counter("qav_ingest_results", "Test results stored", registry=REGISTRY)
REJECTED = Counter("qav_ingest_rejected", "Uploads rejected", ["reason"], registry=REGISTRY)
DURATION = Histogram("qav_ingest_duration_seconds", "Time to handle POST /collect/runs", registry=REGISTRY)

# Pre-create each reason's series so it is visible (at 0) before the first rejection
for _reason in ("auth", "validation", "conflict"):
    REJECTED.labels(reason=_reason)

CONTENT_TYPE = CONTENT_TYPE_LATEST


def render() -> bytes:
    return generate_latest(REGISTRY)
```

`src/ingestion/api/v1/api.py`:
```python
from fastapi import APIRouter

api_router = APIRouter()

__all__ = ["api_router"]
```

`src/ingestion/api/main.py`:
```python
from fastapi import FastAPI, Response
from starlette.middleware.cors import CORSMiddleware

from src.ingestion.api.v1.api import api_router
from src.ingestion.core.config import settings
from src.ingestion.utils import metrics

app = FastAPI(
    title=settings.APP_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/metrics")
def metrics_endpoint():
    return Response(content=metrics.render(), media_type=metrics.CONTENT_TYPE)
```

- [ ] **Step 8: Alembic**

Run:
```bash
cd platforms/ingestion-service
cp ../project-service/alembic.ini alembic.ini
mkdir -p alembic/versions
cp ../project-service/alembic/script.py.mako alembic/script.py.mako
cp ../project-service/alembic/README alembic/README
```
In `alembic.ini`, change `src.project.core.config.settings` to `src.ingestion.core.config.settings` in the comment above `sqlalchemy.url =`. Nothing else.

`alembic/env.py`:
```python
from logging.config import fileConfig
import os
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

# Put the service root on the path so "src.ingestion...." resolves the same way the app does.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ingestion.core.config import settings  # noqa: E402
from src.ingestion.db.base import Base  # noqa: E402
import src.ingestion.models  # noqa: F401,E402  registers every model on Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# A URL passed in explicitly (e.g. by the migration test) wins; otherwise use the runtime settings.
if not config.get_main_option("sqlalchemy.url", None):
    # escape '%' so ConfigParser does not try to interpolate it out of a password
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

`alembic/versions/001_create_ingestion_tables.py`:
```python
"""create api_keys, test_runs and test_results

Revision ID: 001
Revises:
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )
    op.create_index("ix_api_keys_id", "api_keys", ["id"])
    op.create_index("ix_api_keys_project_id", "api_keys", ["project_id"])

    op.create_table(
        "test_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("api_key_id", sa.Integer(), sa.ForeignKey("api_keys.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("ci_provider", sa.String(20), nullable=False),
        sa.Column("ci_run_url", sa.String(2048), nullable=True),
        sa.Column("commit_sha", sa.String(40), nullable=True),
        sa.Column("branch", sa.String(255), nullable=True),
        sa.Column("environment", sa.String(100), nullable=True),
        sa.Column("agent_version", sa.String(50), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("errored", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "idempotency_key", name="uq_test_runs_project_idempotency"),
        sa.CheckConstraint(
            "ci_provider IN ('github_actions','gitlab_ci','jenkins','other','local')", name="chk_test_runs_ci_provider"
        ),
    )
    op.create_index("ix_test_runs_id", "test_runs", ["id"])
    op.create_index("ix_test_runs_project_created", "test_runs", ["project_id", "created_at"])
    op.create_index("ix_test_runs_project_branch", "test_runs", ["project_id", "branch"])

    op.create_table(
        "test_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("test_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("test_key", sa.String(64), nullable=False),
        sa.Column("suite", sa.String(500), nullable=False, server_default=""),
        sa.Column("class_name", sa.String(500), nullable=False, server_default=""),
        sa.Column("name", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("truncated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("file", sa.String(1000), nullable=True),
        sa.CheckConstraint("status IN ('passed','failed','skipped','errored')", name="chk_test_results_status"),
    )
    op.create_index("ix_test_results_id", "test_results", ["id"])
    op.create_index("ix_test_results_run_id", "test_results", ["run_id"])
    op.create_index("ix_test_results_test_key", "test_results", ["test_key"])


def downgrade() -> None:
    op.drop_table("test_results")
    op.drop_table("test_runs")
    op.drop_table("api_keys")
```

- [ ] **Step 9: Run the tests to verify they pass**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q`
Expected: 11 passed (3 tokens + 2 health/metrics + 6 migration). The only acceptable warning is the known httpx `app` shortcut DeprecationWarning; a pytest "cannot collect test class" warning means a model is named `Test…` — rename it.

- [ ] **Step 10: Dockerfile and service compose**

`Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# The repo layout is mirrored inside the image so that requirements.txt's
# `-e ../../shared` resolves to /app/shared, exactly as it does in a checkout.
COPY shared/ ./shared/
COPY platforms/ingestion-service/requirements.txt ./platforms/ingestion-service/

WORKDIR /app/platforms/ingestion-service
RUN pip install --no-cache-dir -r requirements.txt

COPY platforms/ingestion-service/src/ ./src/
COPY platforms/ingestion-service/alembic/ ./alembic/
COPY platforms/ingestion-service/alembic.ini ./alembic.ini

EXPOSE 8000

CMD ["uvicorn", "src.ingestion.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`docker-compose.yml` (for developing this service alone; the root stack is Task 7):
```yaml
services:
  ingestion-service:
    # Context is the repo root so the image can COPY shared/ alongside this service.
    build:
      context: ../..
      dockerfile: platforms/ingestion-service/Dockerfile
    # auth 8000, organization 8001, project 8002
    ports:
      - "8003:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/ingestion_db
      # No fallback, and it must equal auth-service's SECRET_KEY so its JWTs verify here.
      - SECRET_KEY=${SECRET_KEY:?set SECRET_KEY (same value as auth-service)}
      - ALGORITHM=HS256
      # project-service runs in its own compose stack, published on the host's 8002
      - PROJECT_SERVICE_URL=${PROJECT_SERVICE_URL:-http://host.docker.internal:8002}
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)"]
      interval: 5s
      timeout: 5s
      retries: 12
      start_period: 10s

  db:
    image: postgres:15
    environment:
      POSTGRES_DB: ingestion_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d ingestion_db -h 127.0.0.1"]
      interval: 3s
      timeout: 3s
      retries: 20
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      # auth 5433, organization 5434, project 5435
      - "5436:5432"

volumes:
  postgres_data:
```

Run (from `platforms/ingestion-service`):
```bash
SECRET_KEY=local-smoke docker compose up --build --detach --wait --wait-timeout 180
curl --fail -sS http://localhost:8003/health; echo
SECRET_KEY=local-smoke docker compose down
```
Expected: both containers healthy, then `{"status":"healthy"}`. Plain `down` (no `--volumes`).

- [ ] **Step 11: CI entries**

In `.github/workflows/ci.yml`, append to the `tests` job's `matrix.include`:
```yaml
          - service: ingestion-service
            path: platforms/ingestion-service
            extra_tests: ""
```
and to the `smoke` job's `matrix.include`:
```yaml
          - service: ingestion-service
            path: platforms/ingestion-service
            port: 8003
```

- [ ] **Step 12: Commit**

```bash
git add platforms/ingestion-service .github/workflows/ci.yml
git status --short   # no .venv, __pycache__, test.db, *.egg-info staged
git commit -m "feat(ingestion-service): skeleton with models, migration, health, metrics, container and CI"
```

---

### Task 2: project-service client and people's authorization

**Files:**
- Create: `src/ingestion/utils/project_client.py`
- Create: `src/ingestion/api/deps.py`
- Modify: `tests/conftest.py` (add fixture `project_role`)
- Create: `tests/unit/test_project_client.py`
- Create: `tests/integration/test_deps.py`

**Interfaces:**
- Consumes: `settings.PROJECT_SERVICE_URL`, `settings.PROJECT_SERVICE_TIMEOUT_SECONDS`; `decode_token`; fixtures `http`, `auth`, `db`.
- Produces:
  - `project_client.ROLES = ("owner", "admin", "member", "viewer", "billing_manager")`
  - `project_client.ProjectInfo(role: str, organization_id: int)` (NamedTuple)
  - `project_client.get_project(project_id: int, token: str) -> ProjectInfo`, raising `ProjectNotFound`, `InvalidCredentials`, `ProjectServiceUnavailable`
  - `deps.READ_ROLES = ROLES`, `deps.EDIT_ROLES = ("owner", "admin", "member")`
  - `deps.Caller(user_id: int, token: str)`, `deps.get_caller`
  - `deps.ProjectAccess(project_id: int, organization_id: int, user_id: int, role: str)`
  - `deps.check_project_role(project_id: int, caller: Caller, roles: tuple, not_found_detail: str) -> ProjectAccess`
  - `deps.require_project_role(*roles)` → dependency taking path param `project_id`, returning `ProjectAccess`
  - `deps.get_db` (re-export)
  - fixture `project_role(role="owner", project_id=1, organization_id=10, status_code=200, body=None, exc=None)`

- [ ] **Step 1: The fixture**

Append to `tests/conftest.py`:
```python


PROJECT_URL = "{base}/api/v1/projects/{project_id}"


def project_body(project_id: int, organization_id: int, role: str) -> dict:
    """The shape project-service's GET /projects/{id} returns (ProjectOut)."""
    return {
        "id": project_id, "organization_id": organization_id, "name": f"P{project_id}", "slug": f"p{project_id}",
        "description": None,
        "settings": {"result_retention_days": 90, "default_environment": None, "notify_on_failure": False},
        "created_by": 1, "created_at": "2026-09-29T00:00:00Z", "updated_at": None, "my_role": role,
    }


@pytest.fixture
def project_role(http):
    """Mock project-service's GET /projects/{id} for one project; calling it again for the same
    project replaces the answer (respx replaces routes that share a name)."""
    import httpx

    def _set(role="owner", project_id=1, organization_id=10, status_code=200, body=None, exc=None):
        route = http.get(
            PROJECT_URL.format(base=settings.PROJECT_SERVICE_URL, project_id=project_id),
            name=f"project-{project_id}",
        )
        if exc is not None:
            return route.mock(side_effect=exc)
        payload = project_body(project_id, organization_id, role) if body is None else body
        return route.mock(return_value=httpx.Response(status_code, json=payload))

    return _set
```

- [ ] **Step 2: Failing client tests**

`tests/unit/test_project_client.py`:
```python
import httpx
import pytest

from conftest import project_body
from src.ingestion.utils import project_client


def test_returns_role_and_organization_and_forwards_only_the_callers_token(project_role):
    route = project_role("admin", project_id=7, organization_id=42)
    info = project_client.get_project(7, "caller-token")
    assert info == project_client.ProjectInfo(role="admin", organization_id=42)
    assert route.calls.last.request.headers["Authorization"] == "Bearer caller-token"


def test_404_is_project_not_found(project_role):
    project_role(project_id=7, status_code=404, body={"detail": "Project not found"})
    with pytest.raises(project_client.ProjectNotFound):
        project_client.get_project(7, "t")


def test_401_is_invalid_credentials(project_role):
    project_role(project_id=7, status_code=401, body={"detail": "Could not validate credentials"})
    with pytest.raises(project_client.InvalidCredentials):
        project_client.get_project(7, "t")


@pytest.mark.parametrize("status_code", [403, 500, 502, 503])
def test_other_statuses_are_unavailable(project_role, status_code):
    project_role(project_id=7, status_code=status_code, body={"detail": "x"})
    with pytest.raises(project_client.ProjectServiceUnavailable):
        project_client.get_project(7, "t")


@pytest.mark.parametrize("exc", [httpx.ReadTimeout("slow"), httpx.ConnectError("refused")])
def test_network_failures_are_unavailable(project_role, exc):
    project_role(project_id=7, exc=exc)
    with pytest.raises(project_client.ProjectServiceUnavailable):
        project_client.get_project(7, "t")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b.update(my_role="superuser"),
        lambda b: b.pop("my_role"),
        lambda b: b.update(organization_id="42"),
        lambda b: b.update(organization_id=True),
        lambda b: b.pop("organization_id"),
    ],
)
def test_200_outside_the_contract_is_unavailable(project_role, mutate):
    body = project_body(7, 42, "admin")
    mutate(body)
    project_role(project_id=7, body=body)
    with pytest.raises(project_client.ProjectServiceUnavailable):
        project_client.get_project(7, "t")


def test_non_json_200_is_unavailable(http):
    from src.ingestion.core.config import settings

    http.get(f"{settings.PROJECT_SERVICE_URL}/api/v1/projects/7", name="project-7").mock(
        return_value=httpx.Response(200, text="<html>")
    )
    with pytest.raises(project_client.ProjectServiceUnavailable):
        project_client.get_project(7, "t")


def test_trailing_slash_in_the_configured_url(http, monkeypatch):
    from src.ingestion.core.config import settings

    monkeypatch.setattr(settings, "PROJECT_SERVICE_URL", "http://projects.test/")
    route = http.get("http://projects.test/api/v1/projects/7").mock(
        return_value=httpx.Response(200, json=project_body(7, 42, "viewer"))
    )
    assert project_client.get_project(7, "t").role == "viewer"
    assert route.called
```

- [ ] **Step 3: Run to verify failure**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/unit/test_project_client.py -q`
Expected: FAIL — `ImportError: cannot import name 'project_client'`.

- [ ] **Step 4: Implement the client**

`src/ingestion/utils/project_client.py`:
```python
"""The caller's role in a project, from project-service's GET /projects/{id}.

Contract (see the ingestion-service design spec): on 200 the body is a JSON object with an integer
`organization_id` and `my_role` in ROLES. Anything else on a 200 is treated as the service being
unavailable, so a changed or broken response can never be read as a granted role.
"""
from typing import NamedTuple

import httpx

from src.ingestion.core.config import settings

ROLES = ("owner", "admin", "member", "viewer", "billing_manager")


class ProjectInfo(NamedTuple):
    role: str
    organization_id: int


class ProjectServiceUnavailable(Exception):
    """project-service could not give a trustworthy answer."""


class ProjectNotFound(Exception):
    """The project does not exist, is deleted, or the caller may not see it."""


class InvalidCredentials(Exception):
    """project-service rejected the caller's token."""


def get_project(project_id: int, token: str) -> ProjectInfo:
    url = f"{settings.PROJECT_SERVICE_URL.rstrip('/')}/api/v1/projects/{int(project_id)}"
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=settings.PROJECT_SERVICE_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise ProjectServiceUnavailable(f"could not reach project-service: {exc}") from exc

    if response.status_code == 404:
        raise ProjectNotFound()
    if response.status_code == 401:
        raise InvalidCredentials()
    if response.status_code != 200:
        raise ProjectServiceUnavailable(f"unexpected project-service status {response.status_code}")
    try:
        body = response.json()
    except ValueError as exc:
        raise ProjectServiceUnavailable("project-service returned a non-JSON body") from exc

    if not isinstance(body, dict):
        raise ProjectServiceUnavailable("project-service response is not an object")
    role, organization_id = body.get("my_role"), body.get("organization_id")
    # bool is a subclass of int; it is not a valid id
    if role not in ROLES or not isinstance(organization_id, int) or isinstance(organization_id, bool):
        raise ProjectServiceUnavailable("project-service response does not match the expected contract")
    return ProjectInfo(role=role, organization_id=organization_id)
```

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/unit/test_project_client.py -q`
Expected: 16 passed.

- [ ] **Step 5: Failing dependency tests**

`tests/integration/test_deps.py`:
```python
import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from conftest import make_token
from src.ingestion.api.deps import (
    EDIT_ROLES, Caller, ProjectAccess, check_project_role, get_caller, get_db, require_project_role,
)

probe_app = FastAPI()


@probe_app.get("/projects/{project_id}/probe")
def probe(access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES))):
    return access._asdict()


@probe_app.get("/things/{project_id}")
def thing(project_id: int, caller: Caller = Depends(get_caller)):
    return check_project_role(project_id, caller, EDIT_ROLES, "Thing not found")._asdict()


@pytest.fixture
def probe_client(db):
    probe_app.dependency_overrides[get_db] = lambda: db
    with TestClient(probe_app) as c:
        yield c
    probe_app.dependency_overrides.clear()


def test_missing_token_is_401_without_calling_project_service(probe_client, http):
    assert probe_client.get("/projects/1/probe").status_code == 401
    assert not http.calls


def test_refresh_token_is_401(probe_client):
    headers = {"Authorization": f"Bearer {make_token(1, token_type='refresh')}"}
    assert probe_client.get("/projects/1/probe", headers=headers).status_code == 401


def test_allowed_role_passes_with_organization(probe_client, auth, project_role):
    project_role("member", project_id=1, organization_id=10)
    response = probe_client.get("/projects/1/probe", headers=auth(5))
    assert response.status_code == 200
    assert response.json() == {"project_id": 1, "organization_id": 10, "user_id": 5, "role": "member"}


def test_insufficient_role_is_403(probe_client, auth, project_role):
    project_role("viewer")
    assert probe_client.get("/projects/1/probe", headers=auth()).status_code == 403


def test_non_member_is_404(probe_client, auth, project_role):
    project_role(status_code=404, body={"detail": "Project not found"})
    response = probe_client.get("/projects/1/probe", headers=auth())
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


def test_custom_not_found_detail(probe_client, auth, project_role):
    project_role(project_id=3, status_code=404, body={"detail": "Project not found"})
    response = probe_client.get("/things/3", headers=auth())
    assert response.status_code == 404
    assert response.json()["detail"] == "Thing not found"


def test_project_service_401_is_401(probe_client, auth, project_role):
    project_role(status_code=401, body={"detail": "bad"})
    assert probe_client.get("/projects/1/probe", headers=auth()).status_code == 401


def test_project_service_down_is_503(probe_client, auth, project_role):
    project_role(exc=httpx.ConnectError("refused"))
    response = probe_client.get("/projects/1/probe", headers=auth())
    assert response.status_code == 503
    assert response.json()["detail"] == "Project service unavailable"
```

- [ ] **Step 6: Run to verify failure**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/integration/test_deps.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ingestion.api.deps'`.

- [ ] **Step 7: Implement the dependencies**

`src/ingestion/api/deps.py`:
```python
from typing import NamedTuple

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from src.ingestion.db.session import get_db
from src.ingestion.utils import project_client
from src.ingestion.utils.tokens import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

READ_ROLES = project_client.ROLES
EDIT_ROLES = ("owner", "admin", "member")


class Caller(NamedTuple):
    user_id: int
    token: str


class ProjectAccess(NamedTuple):
    project_id: int
    organization_id: int
    user_id: int
    role: str


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_caller(token: str = Depends(oauth2_scheme)) -> Caller:
    if token is None:
        raise _unauthorized()
    try:
        return Caller(user_id=int(decode_token(token)["sub"]), token=token)
    except (ValueError, KeyError, TypeError):
        raise _unauthorized()


def check_project_role(project_id: int, caller: Caller, roles: tuple, not_found_detail: str) -> ProjectAccess:
    try:
        info = project_client.get_project(project_id, caller.token)
    except project_client.ProjectNotFound:
        # never 403: a non-member must not learn that the project (or its data) exists
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)
    except project_client.InvalidCredentials:
        raise _unauthorized()
    except project_client.ProjectServiceUnavailable:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Project service unavailable")
    if info.role not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    return ProjectAccess(
        project_id=project_id, organization_id=info.organization_id, user_id=caller.user_id, role=info.role
    )


def require_project_role(*roles: str):
    def dependency(project_id: int, caller: Caller = Depends(get_caller)) -> ProjectAccess:
        return check_project_role(project_id, caller, roles, "Project not found")

    return dependency


__all__ = [
    "get_db", "get_caller", "check_project_role", "require_project_role",
    "Caller", "ProjectAccess", "READ_ROLES", "EDIT_ROLES",
]
```

- [ ] **Step 8: Run the whole suite**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q`
Expected: 35 passed (11 + 16 + 8).

- [ ] **Step 9: Commit**

```bash
git add platforms/ingestion-service/src/ingestion/utils/project_client.py \
        platforms/ingestion-service/src/ingestion/api/deps.py \
        platforms/ingestion-service/tests
git commit -m "feat(ingestion-service): authorize people through project-service's my_role"
```

---

### Task 3: API keys — generation, storage, endpoints

**Files:**
- Create: `src/ingestion/utils/keys.py`
- Create: `src/ingestion/schemas/api_key.py`
- Create: `src/ingestion/service/api_key_service.py`
- Create: `src/ingestion/api/v1/endpoints/api_keys.py`
- Modify: `src/ingestion/api/v1/api.py`
- Modify: `tests/conftest.py` (add fixture `make_key`)
- Create: `tests/unit/test_keys.py`, `tests/integration/test_api_keys_endpoints.py`

**Interfaces:**
- Consumes: `ApiKey`; `deps.require_project_role`, `EDIT_ROLES`, `READ_ROLES`, `ProjectAccess`; fixtures `client`, `db`, `auth`, `project_role`.
- Produces:
  - `keys.PREFIX = "qav_"`; `keys.generate_key() -> str`; `keys.hash_key(key: str) -> str`; `keys.display_prefix(key: str) -> str`
  - `api_key_service.create_key(db, access: ProjectAccess, name: str) -> tuple[ApiKey, str]`; `list_keys(db, project_id) -> list[ApiKey]`; `revoke_key(db, project_id, key_id) -> bool`
  - fixture `make_key(project_id=1, organization_id=10, name="ci", revoked=False) -> tuple[ApiKey, str]`
  - router `api_keys.router` mounted at `/projects/{project_id}/api-keys`

- [ ] **Step 1: Failing key-utility tests**

`tests/unit/test_keys.py`:
```python
import hashlib
import re

from src.ingestion.utils.keys import PREFIX, display_prefix, generate_key, hash_key


def test_keys_have_the_prefix_and_256_bits():
    key = generate_key()
    assert key.startswith(PREFIX)
    assert re.fullmatch(r"qav_[A-Za-z0-9_-]{43}", key)


def test_keys_are_unique():
    assert len({generate_key() for _ in range(100)}) == 100


def test_hash_is_sha256_hex_of_the_whole_key():
    key = generate_key()
    assert hash_key(key) == hashlib.sha256(key.encode()).hexdigest()


def test_display_prefix_is_the_first_12_characters():
    key = generate_key()
    assert display_prefix(key) == key[:12]
    assert len(display_prefix(key)) == 12
```

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/unit/test_keys.py -q` — expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 2: Implement key utilities**

`src/ingestion/utils/keys.py`:
```python
"""Project API keys: `qav_` + 32 random bytes (URL-safe base64, 43 characters).

Stored as a SHA-256 hash. A 256-bit random key cannot be guessed, so a slow password hash
(bcrypt) buys nothing, and a fast hash allows the indexed lookup every upload needs.
"""
import hashlib
import secrets

PREFIX = "qav_"


def generate_key() -> str:
    return PREFIX + secrets.token_urlsafe(32)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def display_prefix(key: str) -> str:
    return key[:12]
```

Run the same command — expect 4 passed.

- [ ] **Step 3: The `make_key` fixture**

Append to `tests/conftest.py`:
```python


@pytest.fixture
def make_key(db):
    """Insert an API key directly; returns (row, plaintext key)."""
    from datetime import datetime, timezone

    from src.ingestion.utils.keys import display_prefix, generate_key, hash_key

    def _make(project_id=1, organization_id=10, name="ci", revoked=False):
        key = generate_key()
        row = ApiKey(
            project_id=project_id, organization_id=organization_id, name=name,
            key_prefix=display_prefix(key), key_hash=hash_key(key), created_by=1,
            revoked_at=datetime.now(timezone.utc) if revoked else None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row, key

    return _make
```

- [ ] **Step 4: Failing endpoint tests**

`tests/integration/test_api_keys_endpoints.py`:
```python
import pytest

from src.ingestion.models import ApiKey
from src.ingestion.utils.keys import hash_key

ALL_ROLES = ("owner", "admin", "member", "viewer", "billing_manager")
EDITORS = ("owner", "admin", "member")
BASE = "/api/v1/projects/1/api-keys"


@pytest.mark.parametrize("role", ALL_ROLES)
def test_create_is_for_editors(client, auth, project_role, role):
    project_role(role)
    response = client.post(BASE, json={"name": "GitHub Actions"}, headers=auth())
    assert response.status_code == (201 if role in EDITORS else 403)


@pytest.mark.parametrize("role", ALL_ROLES)
def test_list_is_for_every_role(client, auth, project_role, role):
    project_role(role)
    assert client.get(BASE, headers=auth()).status_code == 200


@pytest.mark.parametrize("role", ALL_ROLES)
def test_revoke_is_for_editors(client, auth, project_role, make_key, role):
    row, _ = make_key()
    project_role(role)
    response = client.delete(f"{BASE}/{row.id}", headers=auth())
    assert response.status_code == (204 if role in EDITORS else 403)


def test_create_returns_the_key_once_and_stores_only_its_hash(client, auth, project_role, db):
    project_role("admin", organization_id=77)
    body = client.post(BASE, json={"name": "GitHub Actions"}, headers=auth(9)).json()
    assert body["key"].startswith("qav_")
    assert body["key_prefix"] == body["key"][:12]
    row = db.query(ApiKey).one()
    assert row.key_hash == hash_key(body["key"])
    assert body["key"] not in {row.key_hash, row.key_prefix, row.name}
    assert (row.project_id, row.organization_id, row.created_by) == (1, 77, 9)

    listed = client.get(BASE, headers=auth()).json()
    assert listed[0]["key_prefix"] == body["key_prefix"]
    assert "key" not in listed[0] and "key_hash" not in listed[0]


@pytest.mark.parametrize("name", ["", "   ", "x" * 256])
def test_invalid_name_is_422(client, auth, project_role, name):
    project_role("owner")
    assert client.post(BASE, json={"name": name}, headers=auth()).status_code == 422


def test_unknown_field_is_422(client, auth, project_role):
    project_role("owner")
    assert client.post(BASE, json={"name": "k", "scopes": ["all"]}, headers=auth()).status_code == 422


def test_list_shows_only_this_projects_keys(client, auth, project_role, make_key):
    make_key(project_id=1, name="mine")
    make_key(project_id=2, name="theirs")
    project_role("viewer")
    assert [k["name"] for k in client.get(BASE, headers=auth()).json()] == ["mine"]


def test_revoke_sets_revoked_at_and_is_repeatable(client, auth, project_role, make_key, db):
    row, _ = make_key()
    project_role("member")
    assert client.delete(f"{BASE}/{row.id}", headers=auth()).status_code == 204
    db.refresh(row)
    first = row.revoked_at
    assert first is not None
    assert client.delete(f"{BASE}/{row.id}", headers=auth()).status_code == 204
    db.refresh(row)
    assert row.revoked_at == first


def test_revoking_another_projects_key_is_404(client, auth, project_role, make_key, db):
    row, _ = make_key(project_id=2)
    project_role("owner", project_id=1)
    assert client.delete(f"{BASE}/{row.id}", headers=auth()).status_code == 404
    db.refresh(row)
    assert row.revoked_at is None


def test_non_member_is_404(client, auth, project_role):
    project_role(status_code=404, body={"detail": "Project not found"})
    assert client.get(BASE, headers=auth()).status_code == 404
```

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/integration/test_api_keys_endpoints.py -q` — expect FAIL (404s: routes missing).

- [ ] **Step 5: Schemas, service, endpoints, router**

`src/ingestion/schemas/api_key.py`:
```python
from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class ApiKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    key_prefix: str
    created_at: datetime
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None


class ApiKeyCreated(BaseModel):
    """The only response that ever carries the full key."""

    id: int
    name: str
    key_prefix: str
    key: str
    created_at: datetime
```

`src/ingestion/service/api_key_service.py`:
```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.ingestion.api.deps import ProjectAccess
from src.ingestion.models import ApiKey
from src.ingestion.utils.keys import display_prefix, generate_key, hash_key


def create_key(db: Session, access: ProjectAccess, name: str) -> tuple[ApiKey, str]:
    key = generate_key()
    row = ApiKey(
        project_id=access.project_id,
        organization_id=access.organization_id,
        name=name,
        key_prefix=display_prefix(key),
        key_hash=hash_key(key),
        created_by=access.user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, key


def list_keys(db: Session, project_id: int) -> list[ApiKey]:
    return db.query(ApiKey).filter(ApiKey.project_id == project_id).order_by(ApiKey.id).all()


def revoke_key(db: Session, project_id: int, key_id: int) -> bool:
    """False if the key does not exist in this project. Revoking twice keeps the first time."""
    row = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.project_id == project_id).first()
    if row is None:
        return False
    if row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return True
```

`src/ingestion/api/v1/endpoints/api_keys.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from src.ingestion.api.deps import EDIT_ROLES, READ_ROLES, ProjectAccess, get_db, require_project_role
from src.ingestion.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from src.ingestion.service import api_key_service

router = APIRouter()  # mounted at /projects/{project_id}/api-keys


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_api_key(
    payload: ApiKeyCreate,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    row, key = api_key_service.create_key(db, access, payload.name)
    return ApiKeyCreated(id=row.id, name=row.name, key_prefix=row.key_prefix, key=key, created_at=row.created_at)


@router.get("", response_model=list[ApiKeyOut])
def list_api_keys(
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    return api_key_service.list_keys(db, access.project_id)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: int,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    if not api_key_service.revoke_key(db, access.project_id, key_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

Replace `src/ingestion/api/v1/api.py`:
```python
from fastapi import APIRouter

from src.ingestion.api.v1.endpoints import api_keys

api_router = APIRouter()
api_router.include_router(api_keys.router, prefix="/projects/{project_id}/api-keys", tags=["api-keys"])

__all__ = ["api_router"]
```

- [ ] **Step 6: Run the whole suite**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q`
Expected: 63 passed (35 + 4 + 24: 15 role-matrix + 9 others).

- [ ] **Step 7: Commit**

```bash
git add platforms/ingestion-service/src platforms/ingestion-service/tests
git commit -m "feat(ingestion-service): project API keys, shown once and stored hashed"
```

---

### Task 4: `POST /collect/runs`

**Files:**
- Create: `src/ingestion/schemas/collect.py`
- Create: `src/ingestion/service/ingest_service.py`
- Create: `src/ingestion/api/key_auth.py`
- Create: `src/ingestion/api/v1/endpoints/collect.py`
- Modify: `src/ingestion/api/v1/api.py`, `src/ingestion/api/main.py` (validation-rejection metric)
- Create: `tests/unit/test_collect_schema.py`, `tests/unit/test_ingest_service.py`, `tests/integration/test_collect_endpoint.py`

**Interfaces:**
- Consumes: `ApiKey`, `Run`, `RunResult`; `keys.hash_key`, `keys.PREFIX`; `metrics`; `settings.MAX_RESULTS_PER_RUN`, `settings.MAX_TEXT_BYTES`; fixtures `client`, `db`, `make_key`, `http`.
- Produces:
  - `schemas.collect.RunUpload` (`run: RunIn`, `results: list[ResultIn]`), `RunReceipt`
  - `ingest_service.IdempotencyConflict`; `ingest_service.ingest(db, key: ApiKey, upload: RunUpload, idempotency_key: str | None) -> tuple[Run, bool]` (`bool` = newly created); `ingest_service.truncate_utf8(text, limit) -> tuple[str, bool]`; `ingest_service.test_key(suite, class_name, name) -> str`
  - `key_auth.get_api_key` dependency → `ApiKey`
  - router `collect.router` mounted at `/collect`
  - test helper `upload_body(**overrides) -> dict` defined in `tests/integration/test_collect_endpoint.py`

- [ ] **Step 1: Failing schema tests**

`tests/unit/test_collect_schema.py`:
```python
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from src.ingestion.schemas.collect import RunUpload

NOW = datetime.now(timezone.utc)


def body(run=None, results=None):
    r = {"ci_provider": "github_actions", "started_at": (NOW - timedelta(minutes=5)).isoformat(),
         "finished_at": NOW.isoformat()}
    r.update(run or {})
    return {"run": r, "results": results if results is not None else [{"name": "t", "status": "passed"}]}


def test_minimal_upload_is_valid_with_defaults():
    upload = RunUpload.model_validate(body())
    result = upload.results[0]
    assert (result.suite, result.class_name, result.duration_ms) == ("", "", 0)


def test_error_status_becomes_errored():
    upload = RunUpload.model_validate(body(results=[{"name": "t", "status": "error"}]))
    assert upload.results[0].status == "errored"


@pytest.mark.parametrize(
    "run",
    [
        {"ci_provider": "travis"},
        {"started_at": "2026-09-29T10:00:00"},                              # no timezone
        {"started_at": NOW.isoformat(), "finished_at": (NOW - timedelta(seconds=1)).isoformat()},
        {"finished_at": (NOW + timedelta(days=1)).isoformat()},
        {"commit_sha": "xyz1234"},
        {"commit_sha": "abc12"},
        {"ci_run_url": "javascript:alert(1)"},
        {"branch": "b" * 256},
        {"unexpected": "field"},
    ],
)
def test_invalid_run_fields(run):
    with pytest.raises(ValidationError):
        RunUpload.model_validate(body(run=run))


def test_finished_at_slightly_in_the_future_is_accepted():
    RunUpload.model_validate(body(run={"finished_at": (NOW + timedelta(minutes=10)).isoformat()}))


@pytest.mark.parametrize(
    "result",
    [
        {"status": "passed"},                        # no name
        {"name": "   ", "status": "passed"},
        {"name": "t", "status": "flaky"},
        {"name": "t", "status": "passed", "duration_ms": -1},
        {"name": "t", "status": "passed", "extra": 1},
        {"name": "n" * 1001, "status": "passed"},
    ],
)
def test_invalid_results(result):
    with pytest.raises(ValidationError):
        RunUpload.model_validate(body(results=[result]))


def test_empty_results_are_rejected():
    with pytest.raises(ValidationError):
        RunUpload.model_validate(body(results=[]))


def test_too_many_results_are_rejected(monkeypatch):
    from src.ingestion.core.config import settings

    too_many = [{"name": f"t{i}", "status": "passed"} for i in range(settings.MAX_RESULTS_PER_RUN + 1)]
    with pytest.raises(ValidationError):
        RunUpload.model_validate(body(results=too_many))


def test_long_text_is_accepted_by_the_schema():
    # truncation is the service's job; the schema must not reject long text
    RunUpload.model_validate(body(results=[{"name": "t", "status": "failed", "details": "x" * 200_000}]))
```

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/unit/test_collect_schema.py -q` — expect FAIL (`ModuleNotFoundError`).

- [ ] **Step 2: Implement the schemas**

`src/ingestion/schemas/collect.py`:
```python
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal, Optional

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from src.ingestion.core.config import settings

# A CI runner's clock can drift a little; a day ahead means a broken clock or a bad payload
MAX_CLOCK_SKEW = timedelta(hours=1)


def _text(max_length: int):
    return Annotated[str, StringConstraints(max_length=max_length)]


class RunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ci_provider: Literal["github_actions", "gitlab_ci", "jenkins", "other", "local"]
    ci_run_url: Optional[Annotated[str, StringConstraints(max_length=2048, pattern=r"^https?://\S+$")]] = None
    commit_sha: Optional[Annotated[str, StringConstraints(pattern=r"^[0-9a-fA-F]{7,40}$")]] = None
    branch: Optional[_text(255)] = None
    environment: Optional[_text(100)] = None
    agent_version: Optional[_text(50)] = None
    started_at: AwareDatetime
    finished_at: AwareDatetime

    @model_validator(mode="after")
    def _times_make_sense(self):
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must not be before started_at")
        if self.finished_at > datetime.now(timezone.utc) + MAX_CLOCK_SKEW:
            raise ValueError("finished_at is too far in the future")
        return self


class ResultIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suite: _text(500) = ""
    class_name: _text(500) = ""
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    # JUnit reports both "error" and "errored"; both are stored as errored
    status: Literal["passed", "failed", "skipped", "errored", "error"]
    duration_ms: int = Field(0, ge=0, le=2_147_483_647)
    message: Optional[str] = None   # long text is truncated by the service, never rejected
    details: Optional[str] = None
    file: Optional[_text(1000)] = None

    @field_validator("status")
    @classmethod
    def _normalise_status(cls, value: str) -> str:
        return "errored" if value == "error" else value


class RunUpload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run: RunIn
    results: list[ResultIn] = Field(min_length=1, max_length=settings.MAX_RESULTS_PER_RUN)


class RunReceipt(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    total: int
    passed: int
    failed: int
    skipped: int
    errored: int
    created_at: datetime
```

Run the schema tests — expect 21 passed.

- [ ] **Step 3: Failing service tests**

`tests/unit/test_ingest_service.py`:
```python
import hashlib

from src.ingestion.service.ingest_service import test_key as make_test_key
from src.ingestion.service.ingest_service import truncate_utf8


def test_short_text_is_untouched():
    assert truncate_utf8("hello", 10) == ("hello", False)


def test_long_text_is_cut_to_the_byte_limit():
    text, cut = truncate_utf8("x" * 100, 10)
    assert (text, cut) == ("x" * 10, True)


def test_truncation_never_splits_a_character():
    # each 😀 is 4 bytes; a 10-byte limit fits two, and must not keep half of the third
    text, cut = truncate_utf8("😀😀😀", 10)
    assert cut is True
    assert text == "😀😀"
    text.encode("utf-8")  # valid UTF-8


def test_none_stays_none():
    assert truncate_utf8(None, 10) == (None, False)


def test_test_key_is_sha256_of_the_three_parts():
    expected = hashlib.sha256("checkout\0CartTest\0adds item".encode()).hexdigest()
    assert make_test_key("checkout", "CartTest", "adds item") == expected


def test_test_key_separator_prevents_collisions():
    assert make_test_key("a", "bc", "d") != make_test_key("ab", "c", "d")
```

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/unit/test_ingest_service.py -q` — expect FAIL.

(`test_key` is imported under an alias so pytest does not collect the production function as a test.)

- [ ] **Step 4: Implement the service**

`src/ingestion/service/ingest_service.py`:
```python
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.ingestion.core.config import settings
from src.ingestion.models import ApiKey, Run, RunResult
from src.ingestion.schemas.collect import RunUpload


class IdempotencyConflict(Exception):
    pass


def truncate_utf8(text: Optional[str], limit: int) -> tuple[Optional[str], bool]:
    """Cut to at most `limit` UTF-8 bytes without splitting a character."""
    if text is None:
        return None, False
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text, False
    return encoded[:limit].decode("utf-8", errors="ignore"), True


def test_key(suite: str, class_name: str, name: str) -> str:
    """Stable identity of a test across runs; the NUL separator keeps ("a","bc") and ("ab","c") apart."""
    return hashlib.sha256(f"{suite}\0{class_name}\0{name}".encode("utf-8")).hexdigest()


test_key.__test__ = False  # not a pytest test, despite the name


def _request_hash(upload: RunUpload) -> str:
    canonical = json.dumps(upload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _existing(db: Session, project_id: int, idempotency_key: str) -> Optional[Run]:
    return db.query(Run).filter(Run.project_id == project_id, Run.idempotency_key == idempotency_key).first()


def _replay(run: Run, request_hash: str) -> tuple[Run, bool]:
    if run.request_hash != request_hash:
        raise IdempotencyConflict()
    return run, False


def ingest(db: Session, key: ApiKey, upload: RunUpload, idempotency_key: Optional[str]) -> tuple[Run, bool]:
    request_hash = _request_hash(upload)
    if idempotency_key is not None:
        existing = _existing(db, key.project_id, idempotency_key)
        if existing is not None:
            return _replay(existing, request_hash)

    counts = Counter(result.status for result in upload.results)
    meta = upload.run
    run = Run(
        project_id=key.project_id,
        api_key_id=key.id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        ci_provider=meta.ci_provider,
        ci_run_url=meta.ci_run_url,
        commit_sha=meta.commit_sha,
        branch=meta.branch,
        environment=meta.environment,
        agent_version=meta.agent_version,
        started_at=meta.started_at,
        finished_at=meta.finished_at,
        duration_ms=int((meta.finished_at - meta.started_at).total_seconds() * 1000),
        total=len(upload.results),
        passed=counts["passed"],
        failed=counts["failed"],
        skipped=counts["skipped"],
        errored=counts["errored"],
    )
    try:
        db.add(run)
        db.flush()  # assigns run.id inside the transaction

        rows = []
        for result in upload.results:
            message, cut_message = truncate_utf8(result.message, settings.MAX_TEXT_BYTES)
            details, cut_details = truncate_utf8(result.details, settings.MAX_TEXT_BYTES)
            rows.append({
                "run_id": run.id,
                "test_key": test_key(result.suite, result.class_name, result.name),
                "suite": result.suite,
                "class_name": result.class_name,
                "name": result.name,
                "status": result.status,
                "duration_ms": result.duration_ms,
                "message": message,
                "details": details,
                "truncated": cut_message or cut_details,
                "file": result.file,
            })
        db.execute(insert(RunResult), rows)  # one executemany, not 20,000 ORM objects

        key.last_used_at = datetime.now(timezone.utc)
        db.commit()
    except IntegrityError:
        db.rollback()
        # Two uploads raced with the same Idempotency-Key and this one lost: answer as if it had
        # arrived second
        if idempotency_key is not None:
            existing = _existing(db, key.project_id, idempotency_key)
            if existing is not None:
                return _replay(existing, request_hash)
        raise
    db.refresh(run)
    return run, True
```

Run the service tests — expect 6 passed.

- [ ] **Step 5: Failing endpoint tests**

`tests/integration/test_collect_endpoint.py`:
```python
from datetime import datetime, timedelta, timezone

import pytest

from src.ingestion.models import Run, RunResult
from src.ingestion.utils import metrics

URL = "/api/v1/collect/runs"


def upload_body(results=None, **run):
    now = datetime.now(timezone.utc)
    meta = {"ci_provider": "github_actions", "branch": "main", "commit_sha": "3f2a9c1",
            "started_at": (now - timedelta(seconds=30)).isoformat(), "finished_at": now.isoformat()}
    meta.update(run)
    return {"run": meta, "results": results if results is not None else [
        {"suite": "checkout", "class_name": "CartTest", "name": "adds item", "status": "passed", "duration_ms": 5},
        {"suite": "checkout", "class_name": "CartTest", "name": "removes item", "status": "failed",
         "message": "expected 1", "details": "Traceback"},
        {"name": "flaky one", "status": "error"},
        {"name": "later", "status": "skipped"},
    ]}


def key_headers(key, idem=None):
    headers = {"Authorization": f"Bearer {key}"}
    if idem is not None:
        headers["Idempotency-Key"] = idem
    return headers


def rejected(reason):
    return metrics.REGISTRY.get_sample_value("qav_ingest_rejected_total", {"reason": reason}) or 0.0


def test_upload_is_stored_with_server_computed_counts(client, make_key, db):
    row, key = make_key(project_id=7)
    response = client.post(URL, json=upload_body(), headers=key_headers(key))
    assert response.status_code == 201
    body = response.json()
    assert (body["project_id"], body["total"], body["passed"], body["failed"], body["skipped"], body["errored"]) \
        == (7, 4, 1, 1, 1, 1)
    run = db.get(Run, body["id"])
    assert run.api_key_id == row.id and run.duration_ms >= 29_000
    statuses = {r.name: r.status for r in db.query(RunResult).filter_by(run_id=run.id)}
    assert statuses["flaky one"] == "errored"


def test_upload_never_calls_another_service(client, make_key, http):
    _, key = make_key()
    assert client.post(URL, json=upload_body(), headers=key_headers(key)).status_code == 201
    assert not http.calls


def test_last_used_at_is_set(client, make_key, db):
    row, key = make_key()
    client.post(URL, json=upload_body(), headers=key_headers(key))
    db.refresh(row)
    assert row.last_used_at is not None


@pytest.mark.parametrize("header", [None, "Bearer", "Bearer ", "Bearer not-a-qav-key", "Basic dXNlcjpwdw=="])
def test_missing_or_malformed_key_is_401(client, header):
    headers = {} if header is None else {"Authorization": header}
    response = client.post(URL, json=upload_body(), headers=headers)
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid API key"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_unknown_key_is_401(client, db):
    assert client.post(URL, json=upload_body(), headers=key_headers("qav_" + "A" * 43)).status_code == 401


def test_revoked_key_is_401(client, make_key):
    _, key = make_key(revoked=True)
    assert client.post(URL, json=upload_body(), headers=key_headers(key)).status_code == 401


def test_invalid_key_and_invalid_body_is_401_not_422(client):
    response = client.post(URL, json={"nonsense": True}, headers=key_headers("qav_" + "B" * 43))
    assert response.status_code == 401


def test_a_key_writes_only_into_its_own_project(client, make_key, db):
    _, key = make_key(project_id=5)
    body = client.post(URL, json=upload_body(), headers=key_headers(key)).json()
    assert db.get(Run, body["id"]).project_id == 5


def test_idempotent_replay_returns_the_same_run_once(client, make_key, db):
    _, key = make_key()
    payload = upload_body()
    first = client.post(URL, json=payload, headers=key_headers(key, "ci-run-123"))
    second = client.post(URL, json=payload, headers=key_headers(key, "ci-run-123"))
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]
    assert db.query(Run).count() == 1


def test_same_idempotency_key_different_payload_is_409(client, make_key, db):
    _, key = make_key()
    client.post(URL, json=upload_body(), headers=key_headers(key, "ci-run-123"))
    before = rejected("conflict")
    response = client.post(URL, json=upload_body(branch="other"), headers=key_headers(key, "ci-run-123"))
    assert response.status_code == 409
    assert response.json() == {"detail": "Idempotency-Key reused with a different payload"}
    assert rejected("conflict") == before + 1
    assert db.query(Run).count() == 1


def test_same_idempotency_key_in_another_project_is_independent(client, make_key, db):
    _, key_a = make_key(project_id=1)
    _, key_b = make_key(project_id=2)
    assert client.post(URL, json=upload_body(), headers=key_headers(key_a, "same")).status_code == 201
    assert client.post(URL, json=upload_body(), headers=key_headers(key_b, "same")).status_code == 201


def test_without_idempotency_key_every_upload_is_new(client, make_key, db):
    _, key = make_key()
    payload = upload_body()
    client.post(URL, json=payload, headers=key_headers(key))
    client.post(URL, json=payload, headers=key_headers(key))
    assert db.query(Run).count() == 2


@pytest.mark.parametrize("idem", ["", "has space", "x" * 256, "tab\there"])
def test_invalid_idempotency_key_is_422(client, make_key, idem):
    _, key = make_key()
    assert client.post(URL, json=upload_body(), headers=key_headers(key, idem)).status_code == 422


def test_invalid_payload_is_422_and_counted(client, make_key, db):
    _, key = make_key()
    before = rejected("validation")
    response = client.post(URL, json=upload_body(ci_provider="travis"), headers=key_headers(key))
    assert response.status_code == 422
    assert rejected("validation") == before + 1
    assert db.query(Run).count() == 0


def test_auth_rejection_is_counted(client):
    before = rejected("auth")
    client.post(URL, json=upload_body(), headers=key_headers("qav_" + "C" * 43))
    assert rejected("auth") == before + 1


def test_success_counters_move(client, make_key):
    _, key = make_key()
    runs = metrics.REGISTRY.get_sample_value("qav_ingest_runs_total") or 0.0
    results = metrics.REGISTRY.get_sample_value("qav_ingest_results_total") or 0.0
    client.post(URL, json=upload_body(), headers=key_headers(key))
    assert metrics.REGISTRY.get_sample_value("qav_ingest_runs_total") == runs + 1
    assert metrics.REGISTRY.get_sample_value("qav_ingest_results_total") == results + 4


def test_long_text_is_stored_truncated_and_flagged(client, make_key, db):
    from src.ingestion.core.config import settings

    _, key = make_key()
    results = [{"name": "big", "status": "failed", "details": "é" * settings.MAX_TEXT_BYTES}]
    body = client.post(URL, json=upload_body(results=results), headers=key_headers(key)).json()
    stored = db.query(RunResult).filter_by(run_id=body["id"]).one()
    assert stored.truncated is True
    assert len(stored.details.encode("utf-8")) <= settings.MAX_TEXT_BYTES


def test_a_failed_write_stores_nothing(client, make_key, db, monkeypatch):
    from src.ingestion.service import ingest_service

    _, key = make_key()

    def explode(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(ingest_service, "test_key", explode)
    with pytest.raises(RuntimeError):
        client.post(URL, json=upload_body(), headers=key_headers(key))
    db.rollback()
    assert db.query(Run).count() == 0
```

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/integration/test_collect_endpoint.py -q` — expect FAIL (404: route missing).

- [ ] **Step 6: Key authentication, endpoint, validation metric**

`src/ingestion/api/key_auth.py`:
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from src.ingestion.db.session import get_db
from src.ingestion.models import ApiKey
from src.ingestion.utils import metrics
from src.ingestion.utils.keys import PREFIX, hash_key

bearer = HTTPBearer(auto_error=False)


def _invalid() -> HTTPException:
    metrics.REJECTED.labels(reason="auth").inc()
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> ApiKey:
    """Resolved before the body is validated, so an unauthenticated caller gets 401, not 422."""
    if credentials is None or not credentials.credentials.startswith(PREFIX):
        raise _invalid()
    key = db.query(ApiKey).filter(ApiKey.key_hash == hash_key(credentials.credentials)).first()
    if key is None or key.revoked_at is not None:
        raise _invalid()
    return key
```

`src/ingestion/api/v1/endpoints/collect.py`:
```python
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session

from src.ingestion.api.deps import get_db
from src.ingestion.api.key_auth import get_api_key
from src.ingestion.models import ApiKey
from src.ingestion.schemas.collect import RunReceipt, RunUpload
from src.ingestion.service import ingest_service
from src.ingestion.utils import metrics

router = APIRouter()  # mounted at /collect


@router.post("/runs", response_model=RunReceipt, status_code=status.HTTP_201_CREATED)
def collect_run(
    upload: RunUpload,
    response: Response,
    db: Session = Depends(get_db),
    key: ApiKey = Depends(get_api_key),
    idempotency_key: Optional[str] = Header(
        None, alias="Idempotency-Key", min_length=1, max_length=255, pattern=r"^[\x21-\x7e]+$"
    ),
):
    with metrics.DURATION.time():
        try:
            run, created = ingest_service.ingest(db, key, upload, idempotency_key)
        except ingest_service.IdempotencyConflict:
            metrics.REJECTED.labels(reason="conflict").inc()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Idempotency-Key reused with a different payload"
            )
    if created:
        metrics.RUNS.inc()
        metrics.RESULTS.inc(run.total)
    else:
        response.status_code = status.HTTP_200_OK
    return run
```

Replace `src/ingestion/api/v1/api.py`:
```python
from fastapi import APIRouter

from src.ingestion.api.v1.endpoints import api_keys, collect

api_router = APIRouter()
api_router.include_router(api_keys.router, prefix="/projects/{project_id}/api-keys", tags=["api-keys"])
api_router.include_router(collect.router, prefix="/collect", tags=["collect"])

__all__ = ["api_router"]
```

In `src/ingestion/api/main.py`, change the first import line to:
```python
from fastapi import FastAPI, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
```
and add after `app.include_router(...)`:
```python


@app.exception_handler(RequestValidationError)
async def count_rejected_uploads(request: Request, exc: RequestValidationError):
    # Count 422s on the upload endpoint; every other route keeps FastAPI's default behaviour
    if request.url.path == f"{settings.API_V1_STR}/collect/runs":
        metrics.REJECTED.labels(reason="validation").inc()
    return await request_validation_exception_handler(request, exc)
```

- [ ] **Step 7: Run the whole suite**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q`
Expected: all pass — 63 + 21 + 6 + 25 = 115. Report the actual count.

If `test_invalid_key_and_invalid_body_is_401_not_422` fails with 422, FastAPI is validating the body before resolving `get_api_key` in this version: report it rather than working around it — it decides whether unauthenticated callers can probe the schema.

- [ ] **Step 8: Commit**

```bash
git add platforms/ingestion-service/src platforms/ingestion-service/tests
git commit -m "feat(ingestion-service): POST /collect/runs with key auth, validation, idempotency, metrics"
```

---

### Task 5: Read API — list runs, get a run

**Files:**
- Create: `src/ingestion/schemas/run.py`
- Create: `src/ingestion/service/run_service.py`
- Create: `src/ingestion/api/v1/endpoints/runs.py`
- Modify: `src/ingestion/api/v1/api.py`
- Create: `tests/integration/test_runs_endpoints.py`

**Interfaces:**
- Consumes: `Run`, `RunResult`; `deps.require_project_role`, `check_project_role`, `get_caller`, `READ_ROLES`; fixtures `client`, `db`, `auth`, `project_role`, `make_key`.
- Produces: routers `runs.project_router` (mounted at `/projects/{project_id}/runs`) and `runs.router` (mounted at `/runs`).

- [ ] **Step 1: Failing tests**

`tests/integration/test_runs_endpoints.py`:
```python
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from src.ingestion.models import Run, RunResult

ALL_ROLES = ("owner", "admin", "member", "viewer", "billing_manager")


@pytest.fixture
def make_run(db, make_key):
    key_row, _ = make_key()

    def _make(project_id=1, branch="main", statuses=("passed", "failed"), minutes_ago=0):
        now = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        run = Run(project_id=project_id, api_key_id=key_row.id, request_hash="h", ci_provider="local",
                  branch=branch, started_at=now - timedelta(seconds=1), finished_at=now, duration_ms=1000,
                  total=len(statuses), passed=statuses.count("passed"), failed=statuses.count("failed"),
                  skipped=statuses.count("skipped"), errored=statuses.count("errored"), created_at=now)
        db.add(run)
        db.flush()
        for i, st in enumerate(statuses):
            db.add(RunResult(run_id=run.id, test_key=f"{i:064d}", name=f"t{i}", status=st, duration_ms=1))
        db.commit()
        db.refresh(run)
        return run

    return _make


@pytest.mark.parametrize("role", ALL_ROLES)
def test_every_role_can_list_runs(client, auth, project_role, role):
    project_role(role)
    assert client.get("/api/v1/projects/1/runs", headers=auth()).status_code == 200


@pytest.mark.parametrize("role", ALL_ROLES)
def test_every_role_can_get_a_run(client, auth, project_role, make_run, role):
    run = make_run()
    project_role(role)
    assert client.get(f"/api/v1/runs/{run.id}", headers=auth()).status_code == 200


def test_list_is_newest_first_this_project_only_with_counts(client, auth, project_role, make_run):
    older = make_run(minutes_ago=10)
    newer = make_run(minutes_ago=1)
    make_run(project_id=2)
    project_role("viewer")
    body = client.get("/api/v1/projects/1/runs", headers=auth()).json()
    assert [r["id"] for r in body] == [newer.id, older.id]
    assert (body[0]["total"], body[0]["passed"], body[0]["failed"]) == (2, 1, 1)
    assert "results" not in body[0]


def test_list_filters_by_branch(client, auth, project_role, make_run):
    make_run(branch="main")
    feature = make_run(branch="feature/x")
    project_role("viewer")
    body = client.get("/api/v1/projects/1/runs?branch=feature/x", headers=auth()).json()
    assert [r["id"] for r in body] == [feature.id]


def test_list_pagination(client, auth, project_role, make_run):
    runs = [make_run(minutes_ago=m) for m in (5, 4, 3, 2, 1)]
    project_role("viewer")
    page = client.get("/api/v1/projects/1/runs?limit=2&offset=1", headers=auth()).json()
    assert [r["id"] for r in page] == [runs[3].id, runs[2].id]


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_list_rejects_bad_pagination(client, auth, project_role, query):
    project_role("viewer")
    assert client.get(f"/api/v1/projects/1/runs?{query}", headers=auth()).status_code == 422


def test_get_run_returns_results_in_order(client, auth, project_role, make_run):
    run = make_run(statuses=("passed", "failed", "skipped"))
    project_role("viewer")
    body = client.get(f"/api/v1/runs/{run.id}", headers=auth()).json()
    assert [r["name"] for r in body["results"]] == ["t0", "t1", "t2"]
    assert body["results"][1]["status"] == "failed"
    assert set(body["results"][0]) >= {"test_key", "suite", "class_name", "name", "status", "duration_ms",
                                       "message", "details", "truncated", "file"}


def test_get_run_filters_by_status(client, auth, project_role, make_run):
    run = make_run(statuses=("passed", "failed", "failed"))
    project_role("viewer")
    body = client.get(f"/api/v1/runs/{run.id}?status=failed", headers=auth()).json()
    assert [r["status"] for r in body["results"]] == ["failed", "failed"]
    assert body["total"] == 3  # the run's counts are unaffected by the filter


def test_get_run_invalid_status_filter_is_422(client, auth, project_role, make_run):
    run = make_run()
    project_role("viewer")
    assert client.get(f"/api/v1/runs/{run.id}?status=flaky", headers=auth()).status_code == 422


def test_missing_run_is_404_without_calling_project_service(client, auth, http):
    assert client.get("/api/v1/runs/999", headers=auth()).status_code == 404
    assert not http.calls


def test_run_of_a_project_the_caller_cannot_see_is_404(client, auth, project_role, make_run):
    run = make_run(project_id=3)
    project_role(project_id=3, status_code=404, body={"detail": "Project not found"})
    response = client.get(f"/api/v1/runs/{run.id}", headers=auth())
    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found"


def test_project_service_down_is_503(client, auth, project_role, make_run):
    run = make_run()
    project_role(exc=httpx.ConnectError("refused"))
    assert client.get(f"/api/v1/runs/{run.id}", headers=auth()).status_code == 503
    assert client.get("/api/v1/projects/1/runs", headers=auth()).status_code == 503


def test_non_member_listing_is_404(client, auth, project_role):
    project_role(status_code=404, body={"detail": "Project not found"})
    assert client.get("/api/v1/projects/1/runs", headers=auth()).status_code == 404


def test_missing_token_is_401(client):
    assert client.get("/api/v1/projects/1/runs").status_code == 401
    assert client.get("/api/v1/runs/1").status_code == 401
```

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/integration/test_runs_endpoints.py -q` — expect FAIL (404s).

- [ ] **Step 2: Schemas, service, endpoints, router**

`src/ingestion/schemas/run.py`:
```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    ci_provider: str
    ci_run_url: Optional[str] = None
    commit_sha: Optional[str] = None
    branch: Optional[str] = None
    environment: Optional[str] = None
    agent_version: Optional[str] = None
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    total: int
    passed: int
    failed: int
    skipped: int
    errored: int
    created_at: datetime


class ResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    test_key: str
    suite: str
    class_name: str
    name: str
    status: str
    duration_ms: int
    message: Optional[str] = None
    details: Optional[str] = None
    truncated: bool
    file: Optional[str] = None


class RunDetail(RunOut):
    results: list[ResultOut]
```

`src/ingestion/service/run_service.py`:
```python
from typing import Optional

from sqlalchemy.orm import Session

from src.ingestion.models import Run, RunResult


def list_runs(db: Session, project_id: int, limit: int, offset: int, branch: Optional[str]) -> list[Run]:
    query = db.query(Run).filter(Run.project_id == project_id)
    if branch is not None:
        query = query.filter(Run.branch == branch)
    return query.order_by(Run.created_at.desc(), Run.id.desc()).offset(offset).limit(limit).all()


def get_run(db: Session, run_id: int) -> Optional[Run]:
    return db.get(Run, run_id)


def list_results(db: Session, run_id: int, status: Optional[str]) -> list[RunResult]:
    query = db.query(RunResult).filter(RunResult.run_id == run_id)
    if status is not None:
        query = query.filter(RunResult.status == status)
    return query.order_by(RunResult.id).all()
```

`src/ingestion/api/v1/endpoints/runs.py`:
```python
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.ingestion.api.deps import (
    READ_ROLES, Caller, ProjectAccess, check_project_role, get_caller, get_db, require_project_role,
)
from src.ingestion.schemas.run import ResultOut, RunDetail, RunOut
from src.ingestion.service import run_service

project_router = APIRouter()  # mounted at /projects/{project_id}/runs
router = APIRouter()          # mounted at /runs


@project_router.get("", response_model=list[RunOut])
def list_runs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    branch: Optional[str] = Query(None, max_length=255),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    return run_service.list_runs(db, access.project_id, limit, offset, branch)


@router.get("/{run_id}", response_model=RunDetail)
def get_run(
    run_id: int,
    status_filter: Optional[Literal["passed", "failed", "skipped", "errored"]] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    caller: Caller = Depends(get_caller),
):
    run = run_service.get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    # The project comes from the run row, never from the URL
    check_project_role(run.project_id, caller, READ_ROLES, "Run not found")
    results = run_service.list_results(db, run.id, status_filter)
    return RunDetail(
        **RunOut.model_validate(run).model_dump(),
        results=[ResultOut.model_validate(result) for result in results],
    )
```

Replace `src/ingestion/api/v1/api.py`:
```python
from fastapi import APIRouter

from src.ingestion.api.v1.endpoints import api_keys, collect, runs

api_router = APIRouter()
api_router.include_router(api_keys.router, prefix="/projects/{project_id}/api-keys", tags=["api-keys"])
api_router.include_router(runs.project_router, prefix="/projects/{project_id}/runs", tags=["runs"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
api_router.include_router(collect.router, prefix="/collect", tags=["collect"])

__all__ = ["api_router"]
```

- [ ] **Step 3: Run the whole suite**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q`
Expected: all pass — 115 + 24 = 139 (10 role-matrix + 14 others). Report the actual count.

- [ ] **Step 4: Commit**

```bash
git add platforms/ingestion-service/src platforms/ingestion-service/tests
git commit -m "feat(ingestion-service): list a project's runs and read one run's results"
```

---

### Task 6: Contract test in project-service

**Files:**
- Create: `platforms/project-service/tests/integration/test_project_contract.py`

**Interfaces:**
- Consumes: project-service fixtures `client`, `auth`, `org_role`, `make_project`.
- Produces: a test that fails if `GET /api/v1/projects/{id}` stops returning an integer `organization_id` or a valid `my_role` — the two fields ingestion-service relies on.

- [ ] **Step 1: The test**

`platforms/project-service/tests/integration/test_project_contract.py`:
```python
"""Contract with ingestion-service (docs/superpowers/specs/2026-09-29-ingestion-service-design.md):
GET /projects/{id} must return an integer organization_id and my_role in the five roles.
ingestion-service treats any other 200 body as "project service unavailable"."""
import pytest

ROLES = ("owner", "admin", "member", "viewer", "billing_manager")


@pytest.mark.parametrize("role", ROLES)
def test_get_project_carries_organization_id_and_my_role(client, auth, org_role, make_project, role):
    project = make_project(org_id=42)
    org_role(role, org_id=42)
    body = client.get(f"/api/v1/projects/{project.id}", headers=auth()).json()
    assert isinstance(body["organization_id"], int) and not isinstance(body["organization_id"], bool)
    assert body["organization_id"] == 42
    assert body["my_role"] == role
```

- [ ] **Step 2: Run it, and prove it can fail**

Run (from `platforms/project-service`): `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/integration/test_project_contract.py -q`
Expected: 5 passed (the contract already holds — this test pins it).

Then temporarily rename `my_role` to `role` in `src/project/schemas/project.py`'s `ProjectOut` **and** in `_out()` in `src/project/api/v1/endpoints/projects.py`; rerun: expected 5 failed. Revert with `git checkout platforms/project-service/src`; rerun: 5 passed. Then the full suite: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q` → 223 passed (218 + 5).

- [ ] **Step 3: Commit**

```bash
git add platforms/project-service/tests/integration/test_project_contract.py
git commit -m "test(project-service): pin the GET /projects/{id} fields ingestion-service relies on"
```

---

### Task 7: Root stack, gateway routes, smoke checks

**Files:**
- Modify: `scripts/postgres-init.sh` (repository root)
- Modify: `docker-compose.yml` (repository root)
- Modify: `gateway/nginx.conf.template`
- Modify: `scripts/smoke_gateway.sh`

**Interfaces:**
- Consumes: the ingestion-service image and endpoints from Tasks 1–5; the root stack and gateway from PR #8.
- Produces: `ingestion-service` in the root stack behind the gateway; smoke checks for every new route.

- [ ] **Step 1: The smoke checks first (they must fail)**

In `scripts/smoke_gateway.sh`:

1. Change the three fixed-id checks so they stay true when the smoke test has run before on the same volume (this script now creates organizations and projects): replace `organizations/1/members/me` with `organizations/999999/members/me`, `organizations/1/projects` with `organizations/999999/projects` (both the URL and the check name), and `projects/1` with `projects/999999`.

2. Change `for svc in auth organizations projects; do` to `for svc in auth organizations projects ingestion; do`.

3. Insert this block immediately before the `# ---- gateway behaviour ----` line:
```bash
# ---- ingestion: key -> upload -> replay -> read -> revoke, through the gateway ----
# The smoke user creates its own organization and project, so it may manage an API key.
# Unique names: the script must also pass when run again on the same volume.
SUFFIX="$(date +%s)-$$"
check "create an organization" 201 POST "$BASE/api/v1/organizations" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Smoke $SUFFIX\",\"slug\":\"smoke-$SUFFIX\",\"plan_tier\":\"free\"}"
ORG_ID="$(grep -o '"id":[0-9]*' "$TMP/body" | head -1 | cut -d: -f2)"
check "create a project" 201 POST "$BASE/api/v1/organizations/$ORG_ID/projects" "${AUTH[@]}" \
  -H "Content-Type: application/json" -d "{\"name\":\"Smoke $SUFFIX\"}"
PROJECT_ID="$(grep -o '"id":[0-9]*' "$TMP/body" | head -1 | cut -d: -f2)"
check "create an API key -> ingestion-service (overlap route)" 201 POST \
  "$BASE/api/v1/projects/$PROJECT_ID/api-keys" "${AUTH[@]}" -H "Content-Type: application/json" -d '{"name":"smoke"}'
API_KEY="$(sed -n 's/.*"key":"\(qav_[^"]*\)".*/\1/p' "$TMP/body")"
KEY_ID="$(grep -o '"id":[0-9]*' "$TMP/body" | head -1 | cut -d: -f2)"
check "list API keys -> ingestion-service" 200 GET "$BASE/api/v1/projects/$PROJECT_ID/api-keys" "${AUTH[@]}"
body_has "... listing hides the key" "\"key_prefix\""
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
RUN_BODY="{\"run\":{\"ci_provider\":\"local\",\"branch\":\"smoke\",\"started_at\":\"$NOW\",\"finished_at\":\"$NOW\"},\"results\":[{\"name\":\"passes\",\"status\":\"passed\"},{\"name\":\"fails\",\"status\":\"failed\",\"message\":\"boom\"}]}"
check "upload a run -> /api/v1/collect" 201 POST "$BASE/api/v1/collect/runs" \
  -H "Authorization: Bearer $API_KEY" -H "Idempotency-Key: smoke-$SUFFIX" -H "Content-Type: application/json" \
  -d "$RUN_BODY"
body_has "... counts computed by the server" '"failed":1'
RUN_ID="$(grep -o '"id":[0-9]*' "$TMP/body" | head -1 | cut -d: -f2)"
check "replay with the same Idempotency-Key" 200 POST "$BASE/api/v1/collect/runs" \
  -H "Authorization: Bearer $API_KEY" -H "Idempotency-Key: smoke-$SUFFIX" -H "Content-Type: application/json" \
  -d "$RUN_BODY"
body_has "... returns the same run" "\"id\":$RUN_ID"
check "list runs -> ingestion-service (overlap route)" 200 GET "$BASE/api/v1/projects/$PROJECT_ID/runs" "${AUTH[@]}"
body_has "... includes the run" "\"id\":$RUN_ID"
check "read the run -> /api/v1/runs" 200 GET "$BASE/api/v1/runs/$RUN_ID?status=failed" "${AUTH[@]}"
body_has "... with the failed result" '"name":"fails"'
check "revoke the key" 204 DELETE "$BASE/api/v1/projects/$PROJECT_ID/api-keys/$KEY_ID" "${AUTH[@]}"
check "a revoked key is rejected" 401 POST "$BASE/api/v1/collect/runs" \
  -H "Authorization: Bearer $API_KEY" -H "Content-Type: application/json" -d "$RUN_BODY"
check "/metrics is not exposed through the gateway" 404 GET "$BASE/metrics"
```

Run (repository root) against the **current** stack (no ingestion-service yet):
```bash
export SECRET_KEY=local-check GATEWAY_HTTP_PORT=18080   # 18080 only if 8080 is taken on this machine
docker compose up -d --build --wait --wait-timeout 300 gateway
bash scripts/smoke_gateway.sh; echo "exit=$?"
```
Expected: `FAIL` lines for `/health/ingestion`, the API-key, upload, runs and revoke checks (404 from project-service or the gateway), `exit=1`.

- [ ] **Step 2: Database and compose**

In `scripts/postgres-init.sh`, change the loop line to:
```sh
for db in auth_db organization_db project_db ingestion_db; do
```

In the root `docker-compose.yml`:

Add after the `x-project-env` block:
```yaml
x-ingestion-env: &ingestion-env
  DATABASE_URL: postgresql://postgres:${POSTGRES_PASSWORD:-postgres}@postgres:5432/ingestion_db
  SECRET_KEY: ${SECRET_KEY:?set SECRET_KEY (shared by every service)}
  PROJECT_SERVICE_URL: http://project-service:8000
```
Add after the `x-project-build` block:
```yaml
x-ingestion-build: &ingestion-build
  context: .
  dockerfile: platforms/ingestion-service/Dockerfile
```
Add after the `project-migrate` service:
```yaml
  ingestion-migrate:
    # Same image as ingestion-service, which builds it; never pulled from a registry
    image: qa-vision/ingestion-service:local
    pull_policy: never
    environment: *ingestion-env
    command: ["alembic", "upgrade", "head"]
    depends_on:
      db-init:
        condition: service_completed_successfully
```
Add after the `project-service` service:
```yaml
  ingestion-service:
    build: *ingestion-build
    image: qa-vision/ingestion-service:local
    environment: *ingestion-env
    healthcheck: *app-healthcheck
    depends_on:
      ingestion-migrate:
        condition: service_completed_successfully
```
And in `gateway.depends_on`, add:
```yaml
      ingestion-service:
        condition: service_healthy
```

- [ ] **Step 3: Gateway routes**

In `gateway/nginx.conf.template`:

After the `limit_req_zone … zone=auth …` line add:
```nginx
    limit_req_zone $binary_remote_addr zone=collect:10m rate=10r/s;
```

After the `location = /health/projects { … }` block add:
```nginx
        location = /health/ingestion {
            set $upstream http://ingestion-service:8000;
            proxy_pass $upstream/health;
        }
```

Immediately before the `# ---- project-service ----` comment add:
```nginx
        # ---- ingestion-service ----
        # Regex locations are tried in file order, so this one must come before project-service's:
        # it takes /api/v1/projects/{id}/api-keys and /runs away from project-service's prefix.
        location ~ ^/api/v1/projects/[0-9]+/(api-keys|runs)(/|$) {
            limit_req zone=api burst=40 nodelay;
            set $upstream http://ingestion-service:8000;
            proxy_pass $upstream;
        }
        location /api/v1/runs {
            limit_req zone=api burst=40 nodelay;
            set $upstream http://ingestion-service:8000;
            proxy_pass $upstream;
        }
        # CI uploads get their own, lower limit, which also bounds a leaked key
        location /api/v1/collect {
            limit_req zone=collect burst=20 nodelay;
            set $upstream http://ingestion-service:8000;
            proxy_pass $upstream;
        }
```
(`/metrics` is deliberately not routed: it falls through to `location /` → 404.)

- [ ] **Step 4: Run it against the new stack**

Run:
```bash
docker build -q -t qa-vision/gateway:local gateway >/dev/null && docker run --rm qa-vision/gateway:local nginx -t
docker compose up -d --build --wait --wait-timeout 300 gateway
docker compose logs --no-log-prefix db-init | tail -4
docker compose logs --no-log-prefix ingestion-migrate | grep 'Running upgrade'
bash scripts/smoke_gateway.sh; echo "exit=$?"
bash scripts/smoke_gateway.sh | tail -1; echo "second run exit=${PIPESTATUS[0]}"
docker compose down
```
Expected: `nginx -t` successful; `database ingestion_db created` (or `exists`); `Running upgrade -> 001`; every smoke line `ok`, `exit=0`; the second run on the same volume also `all gateway checks passed` (the Review Focus's rerun case). Plain `down`.

- [ ] **Step 5: Commit**

```bash
git add scripts/postgres-init.sh docker-compose.yml gateway/nginx.conf.template scripts/smoke_gateway.sh
git status --short
git commit -m "feat: ingestion-service in the root stack and behind the gateway, with smoke checks"
```

---

### Task 8: Documentation

**Files:**
- Create: `platforms/ingestion-service/README.md`
- Modify: `README.md` (repository root — Project Structure block and the "Running the platform" section)
- Modify: `gateway/README.md` (routes table)
- Modify: `TODO.md`

- [ ] **Step 1: Service README**

`platforms/ingestion-service/README.md`:
````markdown
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
````

- [ ] **Step 2: Root README, gateway README**

In the root `README.md`:
- in the "Running the platform" first bullet, change "auth, organization and project services" in the section's opening sentence to "auth, organization, project and ingestion services";
- in the `## Project Structure` tree, change the `project-service` line's `└──` to `├──` and add after it `│   └── ingestion-service/          # Test results from CI: API keys, uploads, runs (implemented)`;
- change "Only the three under `platforms/` are implemented" to "Only the four under `platforms/` are implemented".

In `gateway/README.md`'s routes table, add these rows before the `/api/v1/projects…` row:
```
| `/api/v1/projects/{id}/api-keys…`, `/api/v1/projects/{id}/runs…` | ingestion-service |
| `/api/v1/runs…`, `/api/v1/collect…` | ingestion-service |
```
and add `/health/ingestion` to the health row; in "Limits", add: "`/api/v1/collect` has its own limit instead: 10 requests/s per IP (burst 20)."

- [ ] **Step 3: TODO.md**

In `TODO.md`, after the "Gateway follow-ups" block, add:
```markdown
### Ingestion (Phase 2, step 1)
- [x] ingestion-service: project API keys, POST /collect/runs (validation, idempotency, truncation), run read API, Prometheus metrics
- [x] In the root stack and behind the gateway; smoke-tested end to end

### Ingestion follow-ups
- [ ] Collector agent MVP (JUnit XML parser, uploader with retry) — *next spec*
- [ ] Queue-based processing for 1000+ events/second — *Phase 2 exit criterion*
- [ ] PII detection and redaction; retention policies
- [ ] mTLS between agent and platform
- [ ] Artifacts (screenshots, videos, traces, logs)
- [ ] Per-test history endpoints (test_key is already indexed)
- [ ] Revoke a project's API keys when the project is deleted
```

- [ ] **Step 4: Commit**

```bash
git add platforms/ingestion-service/README.md README.md gateway/README.md TODO.md
git commit -m "docs(ingestion-service): service README, routes, structure, follow-ups"
```
