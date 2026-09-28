# Project Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `platforms/project-service` — projects owned by organizations, repositories with a public reachability check, merge-patched settings — plus the `members/me` endpoint in organization-service that it authorizes against.

**Architecture:** A FastAPI service mirroring organization-service's layout, on `qav-shared` for settings and sessions, with its own `project_db`. Every request's role comes from organization-service's `GET /organizations/{id}/members/me`, called with the caller's own JWT. Repository URL parsing and provider verification are separate pure/IO units so each is testable in isolation.

**Tech Stack:** Python 3.11, FastAPI 0.104, Pydantic v2, SQLAlchemy 2.0, Alembic, PostgreSQL (SQLite in tests), PyJWT, httpx + respx, pytest, Docker.

**Spec:** `docs/superpowers/specs/2026-09-28-project-service-design.md`

**Precondition:** PR #7 (`ci/test-and-smoke`, which adds `.github/workflows/ci.yml`) is merged into `master`, and this branch (`feat/project-service`) is rebased onto it: `git fetch origin && git rebase origin/master`. Task 2 edits `ci.yml`.

## Global Constraints

- IDs are Integer everywhere (not the schema doc's UUID).
- `projects` uniqueness is among live rows only: partial unique indexes `uq_project_org_name` on `(organization_id, name)` and `uq_project_org_slug` on `(organization_id, slug)`, both `WHERE deleted_at IS NULL`.
- `repositories.provider` ∈ `('github','gitlab')`; `verification_status` ∈ `('verified','not_found','unchecked')`, default `unchecked`; `UNIQUE(project_id, provider, full_name_key)` named `uq_repo_project_provider_key`.
- Accepted repository hosts are exactly `github.com` and `gitlab.com` (`www.` stripped). Everything else → 422.
- The verifier requests only `https://api.github.com/repos/{owner}/{name}` and `https://gitlab.com/api/v4/projects/{url-encoded owner/name}`, sends no credentials, and follows no redirects.
- `members/me` contract: 200 → body exactly `{"role": <owner|admin|member|viewer|billing_manager>}`; 404 → not an active member or organization deleted; 401 → bad token.
- Role → permission: create/rename/delete project = owner, admin; edit settings and repositories = owner, admin, member; read = all five roles.
- Org-service unreachable, 5xx, timeout, or a 200 not matching the contract → **503**; never guess a role. Non-member → **404** (never 403).
- Defaults: `ORGANIZATION_SERVICE_URL=http://localhost:8001`, `ORGANIZATION_SERVICE_TIMEOUT_SECONDS=3.0`, `REPO_VERIFY_TIMEOUT_SECONDS=3.0`, `REPO_VERIFY_COOLDOWN_SECONDS=60`; list `limit` default 50, max 100.
- Settings: `result_retention_days` int 1–365 default 90; `default_environment` optional str ≤ 50; `notify_on_failure` bool default false; unknown keys rejected.
- Host ports: project-service app **8002**, db **5435**.
- `Base = declarative_base()` stays in the service's own `db/base.py`.
- organization-service's existing 80 tests stay green.

## Review Focus

- **SQLite hands back naive datetimes** for `DateTime(timezone=True)`, so comparing a stored `verified_at` against an aware `now` raises `TypeError` — the cooldown must normalise; Task 6's cooldown tests run on SQLite and pin it.
- **Names that slugify to nothing** (`"!!!"`, `"   "`) must give 422 with a clear message, not a 500 or an empty slug; pinned in Task 5.
- **Renaming onto a live project's name** must give 409 and leave the session usable for the next request (rollback after `IntegrityError`); renaming onto a *deleted* project's name must succeed. Pinned in Task 5.
- **Repository URLs copied from a browser** carry `?tab=readme`, `#readme` or `/blob/main/README.md`; they must parse to the same repository. Pinned in Task 3.
- **A 200 from organization-service with an unexpected body** (extra key, unknown role, non-JSON) must be a 503, not a crash or a granted role. Pinned in Task 4.

---

### Task 1: organization-service `members/me`

**Files:**
- Modify: `platforms/organization-service/src/organization/schemas/member.py`
- Modify: `platforms/organization-service/src/organization/api/v1/endpoints/members.py`
- Create: `platforms/organization-service/tests/integration/test_members_me.py`

**Interfaces:**
- Produces: `GET /api/v1/organizations/{org_id}/members/me` → `{"role": str}` per the contract. Consumed by Task 4.

- [ ] **Step 1: Write the failing tests**

`platforms/organization-service/tests/integration/test_members_me.py`:
```python
"""The members/me contract project-service depends on.

docs/superpowers/specs/2026-09-28-project-service-design.md pins this response shape; project-service
treats any other 200 body as "organization service unavailable". Do not add keys without changing both.
"""
import jwt
import pytest
from datetime import datetime, timedelta, timezone
from src.organization.core.config import settings
from src.organization.models.member import OrganizationMember


def _auth(user_id: int) -> dict:
    token = jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


def _make_org(client, owner_id: int = 1) -> int:
    response = client.post(
        "/api/v1/organizations",
        json={"name": "Acme", "slug": "acme", "plan_tier": "free"},
        headers=_auth(owner_id),
    )
    assert response.status_code == 201
    return response.json()["id"]


def _add_member(db, org_id: int, user_id: int, role: str, status: str = "active") -> None:
    db.add(OrganizationMember(organization_id=org_id, user_id=user_id, role=role, status=status))
    db.commit()


@pytest.mark.parametrize("role", OrganizationMember.ROLES)
def test_active_member_gets_exactly_their_role(client, db, role):
    org_id = _make_org(client, owner_id=1)
    if role != "owner":
        _add_member(db, org_id, user_id=2, role=role)
    caller = 1 if role == "owner" else 2

    response = client.get(f"/api/v1/organizations/{org_id}/members/me", headers=_auth(caller))

    assert response.status_code == 200
    assert response.json() == {"role": role}


def test_non_member_gets_404(client):
    org_id = _make_org(client, owner_id=1)
    response = client.get(f"/api/v1/organizations/{org_id}/members/me", headers=_auth(99))
    assert response.status_code == 404


def test_suspended_member_gets_404(client, db):
    org_id = _make_org(client, owner_id=1)
    _add_member(db, org_id, user_id=2, role="admin", status="suspended")
    response = client.get(f"/api/v1/organizations/{org_id}/members/me", headers=_auth(2))
    assert response.status_code == 404


def test_deleted_organization_gets_404_even_for_owner(client):
    org_id = _make_org(client, owner_id=1)
    assert client.delete(f"/api/v1/organizations/{org_id}", headers=_auth(1)).status_code == 204
    response = client.get(f"/api/v1/organizations/{org_id}/members/me", headers=_auth(1))
    assert response.status_code == 404


def test_missing_token_gets_401(client):
    org_id = _make_org(client, owner_id=1)
    response = client.get(f"/api/v1/organizations/{org_id}/members/me")
    assert response.status_code == 401
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `platforms/organization-service`): `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/integration/test_members_me.py -v`
Expected: FAIL — the route does not exist, so requests return 404/405 and `test_active_member_gets_exactly_their_role` fails for every role. (`test_non_member_gets_404` and `test_deleted_organization…` may pass by accident; that is fine — they pin behaviour once the route exists.)

If `DELETE /organizations/{id}` does not return 204 in this codebase, check `src/organization/api/v1/endpoints/organizations.py` and use the status it returns; do not change that endpoint.

- [ ] **Step 3: Add the response schema**

Append to `platforms/organization-service/src/organization/schemas/member.py`:
```python


class MyRoleOut(BaseModel):
    """Contract with project-service: exactly this one key. See the project-service design spec."""

    role: str
```

- [ ] **Step 4: Add the route**

In `platforms/organization-service/src/organization/api/v1/endpoints/members.py`, change the schema import line to:
```python
from src.organization.schemas.member import MemberCreate, MemberOut, MyRoleOut
```
and add this route directly after `list_members`:
```python
@router.get("/me", response_model=MyRoleOut)
def my_role(
    org_id: int,
    # require_org_role already 404s on a soft-deleted org and on anyone who is not an *active* member
    role: str = Depends(require_org_role(*OrganizationMember.ROLES)),
):
    return {"role": role}
```

- [ ] **Step 5: Run the new tests, then the whole suite**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/integration/test_members_me.py -v`
Expected: 9 passed (5 roles + 4).

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q`
Expected: 89 passed (80 existing + 9).

- [ ] **Step 6: Commit**

```bash
git add platforms/organization-service/src/organization/schemas/member.py \
        platforms/organization-service/src/organization/api/v1/endpoints/members.py \
        platforms/organization-service/tests/integration/test_members_me.py
git commit -m "feat(organization-service): add members/me for project-service authorization"
```

---

### Task 2: project-service skeleton — config, models, migration, health, container, CI

**Files:**
- Create: `platforms/project-service/requirements.txt`
- Create: `platforms/project-service/.gitignore` (copy of organization-service's)
- Create: `platforms/project-service/.env.example`
- Create: `platforms/project-service/src/__init__.py`, `src/project/__init__.py`, `src/project/api/__init__.py`, `src/project/api/v1/__init__.py`, `src/project/api/v1/endpoints/__init__.py`, `src/project/core/__init__.py`, `src/project/db/__init__.py`, `src/project/models/__init__.py`, `src/project/schemas/__init__.py`, `src/project/service/__init__.py`, `src/project/utils/__init__.py`
- Create: `platforms/project-service/src/project/core/config.py`
- Create: `platforms/project-service/src/project/db/base.py`, `db/session.py`
- Create: `platforms/project-service/src/project/models/project.py`, `models/repository.py`
- Create: `platforms/project-service/src/project/utils/tokens.py`
- Create: `platforms/project-service/src/project/api/v1/api.py`, `api/main.py`
- Create: `platforms/project-service/alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/README`, `alembic/versions/001_create_projects_and_repositories.py`
- Create: `platforms/project-service/tests/conftest.py`, `tests/unit/test_migration.py`, `tests/unit/test_tokens.py`, `tests/integration/test_health.py`
- Create: `platforms/project-service/Dockerfile`, `platforms/project-service/docker-compose.yml`
- Modify: `.github/workflows/ci.yml` (one matrix entry in each job)

**Interfaces:**
- Produces: `src.project.core.config.settings` (fields listed in Step 3); `src.project.db.session.get_db`, `SessionLocal`; `src.project.db.base.Base`; models `Project`, `Repository` (columns in Steps 5–6) exported from `src.project.models`; `src.project.utils.tokens.decode_token(token: str) -> dict` (raises `ValueError`); `src.project.api.v1.api.api_router` (an empty `APIRouter` that Tasks 5–6 add to); pytest fixtures `db`, `client`, `auth`, `http`.

- [ ] **Step 1: Dependencies, ignore file, env example, package markers**

`platforms/project-service/requirements.txt` (the exact pins organization-service uses):
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
pytest==8.1.1
# Relative path, resolved from this file's directory. The Dockerfile mirrors the repo
# layout so this same path resolves inside the image.
-e ../../shared
```

Run:
```bash
cp platforms/organization-service/.gitignore platforms/project-service/.gitignore
printf '\n# SQLite file the test suite creates\ntest.db\n' >> platforms/project-service/.gitignore
```

`platforms/project-service/.env.example`:
```
# Environment variables for the Project Service
APP_NAME=Project Service
DEBUG=False
API_V1_STR=/api/v1

# Must equal auth-service's SECRET_KEY: this service verifies the JWTs auth-service issues
SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256

POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=project_db

ORGANIZATION_SERVICE_URL=http://localhost:8001
ORGANIZATION_SERVICE_TIMEOUT_SECONDS=3.0
REPO_VERIFY_TIMEOUT_SECONDS=3.0
REPO_VERIFY_COOLDOWN_SECONDS=60
```

Create each `__init__.py` listed under **Files** as an empty file.

Create the virtualenv and install:
```bash
cd platforms/project-service
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```
Expected: ends with `Successfully installed ... qav-shared-0.1.0 ...`.

- [ ] **Step 2: Write the failing health, token and migration tests**

`platforms/project-service/tests/conftest.py`:
```python
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.project.api.main import app
from src.project.core.config import settings
from src.project.db.base import Base
from src.project.db.session import get_db
from src.project.models import Project, Repository  # noqa: F401  registers tables

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
    """A respx router active for the test. Any outgoing request without a matching route
    raises, so a test can never silently reach the real network."""
    with respx.mock(assert_all_called=False) as router:
        yield router
```

`platforms/project-service/tests/integration/test_health.py`:
```python
def test_health_needs_no_token(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
```

`platforms/project-service/tests/unit/test_tokens.py`:
```python
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from src.project.core.config import settings
from src.project.utils.tokens import decode_token


def _encode(**claims) -> str:
    payload = {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5), **claims}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def test_valid_access_token_decodes():
    assert decode_token(_encode())["sub"] == "1"


def test_refresh_token_is_rejected():
    with pytest.raises(ValueError):
        decode_token(_encode(token_type="refresh"))


def test_token_signed_with_another_key_is_rejected():
    forged = jwt.encode({"sub": "1"}, "not-the-secret", algorithm=settings.ALGORITHM)
    with pytest.raises(ValueError):
        decode_token(forged)
```

`platforms/project-service/tests/unit/test_migration.py`:
```python
"""Runs the real Alembic migration against a throwaway SQLite DB, so model/migration drift
and the partial unique indexes are exercised (the rest of the suite uses create_all)."""
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from src.project.db.base import Base
from src.project.models import Project, Repository  # noqa: F401  registers tables

SERVICE_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def migrated_engine(tmp_path):
    url = f"sqlite:///{(tmp_path / 'migration_test.db').as_posix()}"
    cfg = Config(str(SERVICE_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVICE_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    try:
        yield engine
    finally:
        engine.dispose()


def _insert_project(conn, name, slug, deleted=False):
    conn.execute(
        text(
            "INSERT INTO projects (organization_id, name, slug, settings, created_by, deleted_at)"
            " VALUES (1, :name, :slug, '{}', 1, :deleted_at)"
        ),
        {"name": name, "slug": slug, "deleted_at": "2026-01-01T00:00:00+00:00" if deleted else None},
    )


def test_migration_creates_model_tables(migrated_engine):
    tables = set(inspect(migrated_engine).get_table_names())
    assert {"projects", "repositories"} <= set(Base.metadata.tables)
    assert set(Base.metadata.tables) <= tables


def test_migration_columns_match_models(migrated_engine):
    inspector = inspect(migrated_engine)
    for table_name, table in Base.metadata.tables.items():
        migrated = {col["name"] for col in inspector.get_columns(table_name)}
        assert {col.name for col in table.columns} == migrated, f"column drift in {table_name}"


def test_migration_creates_partial_unique_indexes(migrated_engine):
    names = {index["name"] for index in inspect(migrated_engine).get_indexes("projects")}
    assert {"uq_project_org_name", "uq_project_org_slug"} <= names


def test_live_duplicate_name_is_rejected(migrated_engine):
    with migrated_engine.begin() as conn:
        _insert_project(conn, "Checkout", "checkout")
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as conn:
            _insert_project(conn, "Checkout", "checkout-2")


def test_deleted_projects_name_and_slug_can_be_reused(migrated_engine):
    with migrated_engine.begin() as conn:
        _insert_project(conn, "Checkout", "checkout", deleted=True)
        _insert_project(conn, "Checkout", "checkout")  # must not raise


def test_repository_provider_check(migrated_engine):
    with migrated_engine.begin() as conn:
        _insert_project(conn, "P", "p")
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO repositories (project_id, provider, owner, name, full_name_key, url,"
                    " default_branch, default_branch_is_user_set, verification_status)"
                    " VALUES (1, 'bitbucket', 'a', 'b', 'a/b', 'https://bitbucket.org/a/b', 'main', 0, 'unchecked')"
                )
            )


def test_repository_unique_per_project_provider_key(migrated_engine):
    insert = text(
        "INSERT INTO repositories (project_id, provider, owner, name, full_name_key, url,"
        " default_branch, default_branch_is_user_set, verification_status)"
        " VALUES (1, 'github', :owner, 'shop', 'acme/shop', 'https://github.com/acme/shop', 'main', 0, 'unchecked')"
    )
    with migrated_engine.begin() as conn:
        _insert_project(conn, "P", "p")
        conn.execute(insert, {"owner": "acme"})
    with pytest.raises(IntegrityError):
        with migrated_engine.begin() as conn:
            conn.execute(insert, {"owner": "Acme"})
```

- [ ] **Step 3: Run the tests to verify they fail**

Run (from `platforms/project-service`): `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q`
Expected: FAIL at collection with `ModuleNotFoundError: No module named 'src.project.api.main'` (or `...config`).

- [ ] **Step 4: Config, db, tokens**

`platforms/project-service/src/project/core/config.py`:
```python
"""Configuration management for Project Service."""
from qav_shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    APP_NAME: str = "Project Service"
    APP_VERSION: str = "0.1.0"

    POSTGRES_DB: str = "project_db"

    # Every request's role comes from organization-service's members/me
    ORGANIZATION_SERVICE_URL: str = "http://localhost:8001"
    ORGANIZATION_SERVICE_TIMEOUT_SECONDS: float = 3.0

    # Public-API reachability check for repositories (GitHub allows 60 unauthenticated
    # requests per hour per server IP, shared by every user of the platform)
    REPO_VERIFY_TIMEOUT_SECONDS: float = 3.0
    REPO_VERIFY_COOLDOWN_SECONDS: int = 60


settings = Settings()
```

`platforms/project-service/src/project/db/base.py`:
```python
from sqlalchemy.ext.declarative import declarative_base

# Deliberately per-service (not in qav_shared): a declarative base is a global registry of
# mapped classes, and sharing one would mix services' tables into a single metadata.
Base = declarative_base()
```

`platforms/project-service/src/project/db/session.py`:
```python
from qav_shared.db import make_get_db, make_session_factory

from src.project.core.config import settings

SessionLocal = make_session_factory(settings.database_url)
get_db = make_get_db(SessionLocal)
```

`platforms/project-service/src/project/utils/tokens.py`:
```python
from jwt import InvalidTokenError, decode

from src.project.core.config import settings


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

- [ ] **Step 5: `Project` model**

`platforms/project-service/src/project/models/project.py`:
```python
from sqlalchemy import JSON, Column, DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from src.project.db.base import Base

# JSONB on PostgreSQL, plain JSON on SQLite (tests)
SettingsJSON = JSON().with_variant(JSONB(), "postgresql")

_LIVE = text("deleted_at IS NULL")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    # No FK: organizations live in organization-service's database
    organization_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    # Only explicitly-set keys are stored; defaults come from schemas.settings.ProjectSettings.
    # Always assign a new dict -- SQLAlchemy does not see in-place mutation of a JSON value.
    settings = Column(SettingsJSON, nullable=False, default=dict)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # Unique among live projects only, so a deleted project's name and slug can be reused
        Index(
            "uq_project_org_name", "organization_id", "name",
            unique=True, sqlite_where=_LIVE, postgresql_where=_LIVE,
        ),
        Index(
            "uq_project_org_slug", "organization_id", "slug",
            unique=True, sqlite_where=_LIVE, postgresql_where=_LIVE,
        ),
    )
```

- [ ] **Step 6: `Repository` model and exports**

`platforms/project-service/src/project/models/repository.py`:
```python
from sqlalchemy import (
    Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, false,
)
from sqlalchemy.sql import func

from src.project.db.base import Base


class Repository(Base):
    __tablename__ = "repositories"

    PROVIDERS = ("github", "gitlab")
    STATUSES = ("verified", "not_found", "unchecked")

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(20), nullable=False)
    owner = Column(String(255), nullable=False)          # as displayed; GitLab: full namespace
    name = Column(String(255), nullable=False)           # as displayed
    full_name_key = Column(String(511), nullable=False)  # lower(owner/name), for uniqueness
    url = Column(Text, nullable=False)                   # canonical https URL
    default_branch = Column(String(255), nullable=False)
    default_branch_is_user_set = Column(Boolean, nullable=False, default=False, server_default=false())
    verification_status = Column(String(20), nullable=False, default="unchecked", server_default="unchecked")
    verified_at = Column(DateTime(timezone=True), nullable=True)  # last check, whatever its result
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("project_id", "provider", "full_name_key", name="uq_repo_project_provider_key"),
        CheckConstraint("provider IN ('github','gitlab')", name="chk_repo_provider"),
        CheckConstraint(
            "verification_status IN ('verified','not_found','unchecked')", name="chk_repo_verification_status"
        ),
    )
```

`platforms/project-service/src/project/models/__init__.py` (replace the empty file):
```python
from src.project.models.project import Project
from src.project.models.repository import Repository

__all__ = ["Project", "Repository"]
```

- [ ] **Step 7: App entry point and router**

`platforms/project-service/src/project/api/v1/api.py`:
```python
from fastapi import APIRouter

api_router = APIRouter()

__all__ = ["api_router"]
```

`platforms/project-service/src/project/api/main.py`:
```python
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.project.api.v1.api import api_router
from src.project.core.config import settings

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
```

- [ ] **Step 8: Alembic**

Run:
```bash
cd platforms/project-service
cp ../organization-service/alembic.ini alembic.ini
mkdir -p alembic/versions
cp ../organization-service/alembic/script.py.mako alembic/script.py.mako
cp ../organization-service/alembic/README alembic/README
```
In `alembic.ini`, change the comment line `# Left blank on purpose: alembic/env.py fills this in from src.organization.core.config.settings` to `# Left blank on purpose: alembic/env.py fills this in from src.project.core.config.settings`. Change nothing else.

`platforms/project-service/alembic/env.py`:
```python
from logging.config import fileConfig
import os
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

# Put the service root on the path so "src.project...." resolves the same way the app does.
# Importing Base by any other path would build a second, empty MetaData.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.project.core.config import settings  # noqa: E402
from src.project.db.base import Base  # noqa: E402
import src.project.models  # noqa: F401,E402  registers every model on Base.metadata

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

`platforms/project-service/alembic/versions/001_create_projects_and_repositories.py`:
```python
"""create projects and repositories

Revision ID: 001
Revises:
Create Date: 2026-09-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "001"
down_revision = None
branch_labels = None
depends_on = None

LIVE = sa.text("deleted_at IS NULL")


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "settings", sa.JSON().with_variant(JSONB(), "postgresql"),
            nullable=False, server_default=sa.text("'{}'"),
        ),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_projects_id", "projects", ["id"])
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"])
    op.create_index(
        "uq_project_org_name", "projects", ["organization_id", "name"],
        unique=True, sqlite_where=LIVE, postgresql_where=LIVE,
    )
    op.create_index(
        "uq_project_org_slug", "projects", ["organization_id", "slug"],
        unique=True, sqlite_where=LIVE, postgresql_where=LIVE,
    )

    op.create_table(
        "repositories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("owner", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("full_name_key", sa.String(511), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("default_branch", sa.String(255), nullable=False),
        sa.Column("default_branch_is_user_set", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verification_status", sa.String(20), nullable=False, server_default="unchecked"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("project_id", "provider", "full_name_key", name="uq_repo_project_provider_key"),
        sa.CheckConstraint("provider IN ('github','gitlab')", name="chk_repo_provider"),
        sa.CheckConstraint(
            "verification_status IN ('verified','not_found','unchecked')", name="chk_repo_verification_status"
        ),
    )
    op.create_index("ix_repositories_id", "repositories", ["id"])
    op.create_index("ix_repositories_project_id", "repositories", ["project_id"])


def downgrade() -> None:
    op.drop_table("repositories")
    op.drop_index("uq_project_org_slug", table_name="projects")
    op.drop_index("uq_project_org_name", table_name="projects")
    op.drop_table("projects")
```

- [ ] **Step 9: Run the tests to verify they pass**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q`
Expected: 11 passed (1 health + 3 tokens + 7 migration), no warnings from this service's own code.

- [ ] **Step 10: Dockerfile and compose**

`platforms/project-service/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# The repo layout is mirrored inside the image so that requirements.txt's
# `-e ../../shared` resolves to /app/shared, exactly as it does in a checkout.
COPY shared/ ./shared/
COPY platforms/project-service/requirements.txt ./platforms/project-service/

WORKDIR /app/platforms/project-service
RUN pip install --no-cache-dir -r requirements.txt

COPY platforms/project-service/src/ ./src/
COPY platforms/project-service/alembic/ ./alembic/
COPY platforms/project-service/alembic.ini ./alembic.ini

EXPOSE 8000

CMD ["uvicorn", "src.project.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`platforms/project-service/docker-compose.yml`:
```yaml
services:
  project-service:
    # Context is the repo root so the image can COPY shared/ alongside this service.
    build:
      context: ../..
      dockerfile: platforms/project-service/Dockerfile
    # auth-service publishes 8000 and organization-service 8001
    ports:
      - "8002:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:password@db:5432/project_db
      # No fallback, and it must equal auth-service's SECRET_KEY so its JWTs verify here.
      - SECRET_KEY=${SECRET_KEY:?set SECRET_KEY (same value as auth-service)}
      - ALGORITHM=HS256
      # organization-service runs in its own compose stack, published on the host's 8001
      - ORGANIZATION_SERVICE_URL=${ORGANIZATION_SERVICE_URL:-http://host.docker.internal:8001}
    # Docker Desktop defines host.docker.internal itself; Linux (including CI runners) needs this
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
      POSTGRES_DB: project_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d project_db"]
      interval: 3s
      timeout: 3s
      retries: 20
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      # auth-service's compose publishes 5433 and organization-service's 5434
      - "5435:5432"

volumes:
  postgres_data:
```

Run (from `platforms/project-service`):
```bash
SECRET_KEY=local-smoke docker compose up --build --detach --wait --wait-timeout 180
curl --fail -sS http://localhost:8002/health
SECRET_KEY=local-smoke docker compose down
```
Expected: both containers `Healthy`, then `{"status":"healthy"}`. Use `down` **without** `--volumes` locally.

- [ ] **Step 11: CI entries**

In `.github/workflows/ci.yml`, in the `tests` job's `matrix.include` list, append:
```yaml
          - service: project-service
            path: platforms/project-service
            extra_tests: ""
```
and in the `smoke` job's `matrix.include` list, append:
```yaml
          - service: project-service
            path: platforms/project-service
            port: 8002
```
Change nothing else in the file.

- [ ] **Step 12: Commit**

```bash
git add platforms/project-service .github/workflows/ci.yml
git status --short   # confirm no .venv, __pycache__, test.db or *.egg-info is staged
git commit -m "feat(project-service): skeleton with models, migration, health, container and CI"
```

---

### Task 3: Repository URL parsing and provider verification

**Files:**
- Create: `platforms/project-service/src/project/utils/repo_url.py`
- Create: `platforms/project-service/src/project/utils/repo_verifier.py`
- Create: `platforms/project-service/tests/unit/test_repo_url.py`
- Create: `platforms/project-service/tests/unit/test_repo_verifier.py`

**Interfaces:**
- Produces:
  - `repo_url.ParsedRepo` — frozen dataclass `(provider: str, owner: str, name: str, full_name_key: str, url: str)`
  - `repo_url.parse_repo_url(raw: str) -> ParsedRepo` — raises `ValueError(user-facing message)`
  - `repo_verifier.VerificationResult` — frozen dataclass `(status: str, default_branch: Optional[str])`
  - `repo_verifier.verify(provider: str, owner: str, name: str, timeout: float) -> VerificationResult` — never raises for provider/network failures
- Consumed by Task 6.

- [ ] **Step 1: Write the failing parser tests**

`platforms/project-service/tests/unit/test_repo_url.py`:
```python
import pytest

from src.project.utils.repo_url import parse_repo_url


@pytest.mark.parametrize(
    "raw",
    [
        "https://github.com/acme/shop",
        "https://github.com/acme/shop/",
        "https://github.com/acme/shop.git",
        "http://github.com/acme/shop",
        "https://www.github.com/acme/shop",
        "https://GitHub.com/acme/shop",
        "https://github.com/acme/shop/tree/main",
        "https://github.com/acme/shop/blob/main/README.md",
        "https://github.com/acme/shop?tab=readme-ov-file",
        "https://github.com/acme/shop#readme",
        "git@github.com:acme/shop.git",
        "git@github.com:acme/shop",
        "  https://github.com/acme/shop  ",
    ],
)
def test_github_forms_parse_to_the_same_repository(raw):
    parsed = parse_repo_url(raw)
    assert parsed.provider == "github"
    assert (parsed.owner, parsed.name) == ("acme", "shop")
    assert parsed.full_name_key == "acme/shop"
    assert parsed.url == "https://github.com/acme/shop"


def test_case_is_kept_for_display_but_not_for_the_key():
    parsed = parse_repo_url("https://github.com/Acme/Shop")
    assert (parsed.owner, parsed.name) == ("Acme", "Shop")
    assert parsed.full_name_key == "acme/shop"
    assert parsed.url == "https://github.com/Acme/Shop"


@pytest.mark.parametrize(
    "raw, owner, name",
    [
        ("https://gitlab.com/group/project", "group", "project"),
        ("https://gitlab.com/group/sub/project", "group/sub", "project"),
        ("https://gitlab.com/group/sub/project/-/tree/main", "group/sub", "project"),
        ("https://gitlab.com/group/sub/project.git", "group/sub", "project"),
        ("git@gitlab.com:group/sub/project.git", "group/sub", "project"),
    ],
)
def test_gitlab_forms(raw, owner, name):
    parsed = parse_repo_url(raw)
    assert parsed.provider == "gitlab"
    assert (parsed.owner, parsed.name) == (owner, name)
    assert parsed.url == f"https://gitlab.com/{owner}/{name}"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "github.com/acme/shop",                     # no scheme
        "ftp://github.com/acme/shop",
        "https://bitbucket.org/acme/shop",
        "https://gitlab.example.com/acme/shop",     # self-hosted GitLab is out of scope
        "https://github.com.evil.com/acme/shop",
        "https://evil.com/github.com/acme/shop",
        "https://127.0.0.1/acme/shop",
        "https://github.com:8443/acme/shop",
        "https://user@github.com/acme/shop",
        "https://user:pw@github.com/acme/shop",
        "https://github.com/acme",                  # no repository name
        "https://github.com/",
        "https://github.com/../shop",
        "https://github.com/acme/..",
        "https://github.com/acme/sh%2Fop",
        "https://github.com/ac me/shop",
        "https://github.com//shop",
        "https://gitlab.com/project",               # GitLab needs a namespace
        "https://gitlab.com/" + "/".join(["g"] * 21) + "/p",   # more than 20 segments
        "git@evil.com:acme/shop.git",
    ],
)
def test_rejected_inputs(raw):
    with pytest.raises(ValueError):
        parse_repo_url(raw)


def test_rejection_message_names_the_supported_hosts():
    with pytest.raises(ValueError, match="github.com and gitlab.com"):
        parse_repo_url("https://bitbucket.org/acme/shop")
```

- [ ] **Step 2: Run to verify failure**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/unit/test_repo_url.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.project.utils.repo_url'`.

- [ ] **Step 3: Implement the parser**

`platforms/project-service/src/project/utils/repo_url.py`:
```python
"""Turn whatever a user pasted into a canonical repository identity. No network access."""
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

HOSTS = {"github.com": "github", "gitlab.com": "gitlab"}
MAX_GITLAB_SEGMENTS = 20

_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
_SSH = re.compile(r"^git@([^:/]+):(.+)$")

UNSUPPORTED_HOST = "Only github.com and gitlab.com repositories are supported"


@dataclass(frozen=True)
class ParsedRepo:
    provider: str
    owner: str
    name: str
    full_name_key: str
    url: str


def parse_repo_url(raw: str) -> ParsedRepo:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("A repository URL is required")
    raw = raw.strip()

    ssh = _SSH.match(raw)
    if ssh:
        host, path = ssh.group(1), ssh.group(2)
    else:
        parts = urlsplit(raw)
        if parts.scheme.lower() not in ("http", "https"):
            raise ValueError("The repository URL must start with https://, http:// or git@")
        if parts.username is not None or parts.password is not None:
            raise ValueError("The repository URL must not contain credentials")
        try:
            port = parts.port
        except ValueError:
            raise ValueError(UNSUPPORTED_HOST)
        if port is not None:
            raise ValueError("The repository URL must not specify a port")
        host = parts.hostname or ""
        path = parts.path  # query and fragment (?tab=..., #readme) are dropped on purpose

    host = host.lower()
    if host.startswith("www."):
        host = host[len("www."):]
    provider = HOSTS.get(host)
    if provider is None:
        raise ValueError(UNSUPPORTED_HOST)

    segments = _repository_segments(provider, path)
    if segments[-1].endswith(".git"):
        segments[-1] = segments[-1][: -len(".git")]
    for segment in segments:
        if not segment or segment in (".", "..") or not _SEGMENT.match(segment):
            raise ValueError("The repository path contains characters that are not allowed")

    owner, name = "/".join(segments[:-1]), segments[-1]
    return ParsedRepo(
        provider=provider,
        owner=owner,
        name=name,
        full_name_key=f"{owner}/{name}".lower(),
        url=f"https://{host}/{owner}/{name}",
    )


def _repository_segments(provider: str, path: str) -> list[str]:
    path = path.strip("/")
    if provider == "gitlab" and "/-/" in f"/{path}/":
        # GitLab puts every non-repository page under /-/ (tree, blob, merge_requests, ...)
        path = f"/{path}/".split("/-/")[0].strip("/")
    segments = path.split("/") if path else []

    if provider == "github":
        if len(segments) < 2:
            raise ValueError("A GitHub repository URL needs an owner and a repository name")
        return segments[:2]  # anything after owner/name is a page inside the repository
    if len(segments) < 2:
        raise ValueError("A GitLab repository URL needs a group and a project name")
    if len(segments) > MAX_GITLAB_SEGMENTS:
        raise ValueError("The GitLab repository path is too deep")
    return segments
```

- [ ] **Step 4: Run to verify the parser passes**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/unit/test_repo_url.py -q`
Expected: 42 passed (13 + 1 + 5 + 22 + 1).

- [ ] **Step 5: Write the failing verifier tests**

`platforms/project-service/tests/unit/test_repo_verifier.py`:
```python
import httpx
import pytest

from src.project.utils.repo_verifier import verify

GITHUB = "https://api.github.com/repos/acme/shop"
GITLAB = "https://gitlab.com/api/v4/projects/group%2Fsub%2Fproject"


def test_github_200_is_verified_with_default_branch(http):
    http.get(GITHUB).mock(return_value=httpx.Response(200, json={"default_branch": "develop"}))
    result = verify("github", "acme", "shop", timeout=3.0)
    assert (result.status, result.default_branch) == ("verified", "develop")


def test_gitlab_uses_the_url_encoded_full_path(http):
    route = http.get(GITLAB).mock(return_value=httpx.Response(200, json={"default_branch": "main"}))
    result = verify("gitlab", "group/sub", "project", timeout=3.0)
    assert route.called
    assert (result.status, result.default_branch) == ("verified", "main")


def test_verified_without_a_default_branch(http):
    # an empty GitLab project reports default_branch: null
    http.get(GITHUB).mock(return_value=httpx.Response(200, json={"default_branch": None}))
    assert verify("github", "acme", "shop", timeout=3.0).default_branch is None


def test_404_is_not_found(http):
    http.get(GITHUB).mock(return_value=httpx.Response(404, json={"message": "Not Found"}))
    assert verify("github", "acme", "shop", timeout=3.0).status == "not_found"


@pytest.mark.parametrize("status_code", [403, 429, 500, 502, 503])
def test_rate_limit_and_server_errors_are_unchecked(http, status_code):
    http.get(GITHUB).mock(return_value=httpx.Response(status_code))
    assert verify("github", "acme", "shop", timeout=3.0).status == "unchecked"


def test_redirect_is_not_followed(http):
    # GitHub answers 301 for a renamed repository; following redirects would let a response
    # send this server anywhere, so it is reported as unchecked instead
    http.get(GITHUB).mock(return_value=httpx.Response(301, headers={"Location": "https://example.com/"}))
    assert verify("github", "acme", "shop", timeout=3.0).status == "unchecked"


def test_timeout_is_unchecked(http):
    http.get(GITHUB).mock(side_effect=httpx.ConnectTimeout("slow"))
    assert verify("github", "acme", "shop", timeout=3.0).status == "unchecked"


def test_non_json_200_is_unchecked(http):
    http.get(GITHUB).mock(return_value=httpx.Response(200, text="<html>"))
    assert verify("github", "acme", "shop", timeout=3.0).status == "unchecked"


def test_no_credentials_are_sent(http):
    route = http.get(GITHUB).mock(return_value=httpx.Response(200, json={"default_branch": "main"}))
    verify("github", "acme", "shop", timeout=3.0)
    assert "authorization" not in {key.lower() for key in route.calls.last.request.headers.keys()}


def test_unknown_provider_is_a_programming_error():
    with pytest.raises(ValueError):
        verify("bitbucket", "acme", "shop", timeout=3.0)
```

- [ ] **Step 6: Run to verify failure**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/unit/test_repo_verifier.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.project.utils.repo_verifier'`.

- [ ] **Step 7: Implement the verifier**

`platforms/project-service/src/project/utils/repo_verifier.py`:
```python
"""Check a repository is publicly reachable. Unauthenticated, so a private repository and a
missing one look the same (404). Provider and network failures never raise."""
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import httpx

VERIFIED, NOT_FOUND, UNCHECKED = "verified", "not_found", "unchecked"


@dataclass(frozen=True)
class VerificationResult:
    status: str
    default_branch: Optional[str]


def _api_url(provider: str, owner: str, name: str) -> str:
    # The host is fixed here and never taken from user input; every path part is encoded.
    if provider == "github":
        return f"https://api.github.com/repos/{quote(owner, safe='')}/{quote(name, safe='')}"
    if provider == "gitlab":
        return f"https://gitlab.com/api/v4/projects/{quote(f'{owner}/{name}', safe='')}"
    raise ValueError(f"unsupported provider: {provider}")


def verify(provider: str, owner: str, name: str, timeout: float) -> VerificationResult:
    url = _api_url(provider, owner, name)
    try:
        response = httpx.get(
            url, timeout=timeout, follow_redirects=False, headers={"Accept": "application/json"}
        )
    except httpx.HTTPError:
        return VerificationResult(UNCHECKED, None)

    if response.status_code == 404:
        return VerificationResult(NOT_FOUND, None)
    if response.status_code != 200:
        # 403/429 are rate limits; 3xx/5xx are not something to retry from a request handler
        return VerificationResult(UNCHECKED, None)
    try:
        body = response.json()
    except ValueError:
        return VerificationResult(UNCHECKED, None)
    if not isinstance(body, dict):
        return VerificationResult(UNCHECKED, None)
    branch = body.get("default_branch")
    return VerificationResult(VERIFIED, branch if isinstance(branch, str) and branch else None)
```

- [ ] **Step 8: Run both unit files**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/unit/test_repo_url.py tests/unit/test_repo_verifier.py -q`
Expected: 56 passed (42 + 14).

- [ ] **Step 9: Commit**

```bash
git add platforms/project-service/src/project/utils/repo_url.py \
        platforms/project-service/src/project/utils/repo_verifier.py \
        platforms/project-service/tests/unit/test_repo_url.py \
        platforms/project-service/tests/unit/test_repo_verifier.py
git commit -m "feat(project-service): parse repository URLs and verify them against public APIs"
```

---

### Task 4: organization-service client and authorization dependencies

**Files:**
- Create: `platforms/project-service/src/project/utils/org_client.py`
- Create: `platforms/project-service/src/project/api/deps.py`
- Modify: `platforms/project-service/tests/conftest.py` (add `org_role` and `make_project` fixtures)
- Create: `platforms/project-service/tests/unit/test_org_client.py`
- Create: `platforms/project-service/tests/integration/test_deps.py`

**Interfaces:**
- Consumes: `settings.ORGANIZATION_SERVICE_URL`, `settings.ORGANIZATION_SERVICE_TIMEOUT_SECONDS`; `Project` model; `decode_token`; fixtures `db`, `http`, `auth`.
- Produces:
  - `org_client.ORG_ROLES: tuple[str, ...]` = `("owner", "admin", "member", "viewer", "billing_manager")`
  - `org_client.get_my_role(org_id: int, token: str) -> str`, raising `org_client.NotAMember`, `org_client.InvalidCredentials`, `org_client.OrgServiceUnavailable`
  - `deps.MANAGE_ROLES = ("owner", "admin")`, `deps.EDIT_ROLES = ("owner", "admin", "member")`, `deps.READ_ROLES = org_client.ORG_ROLES`
  - `deps.OrgAccess(org_id: int, user_id: int, role: str)` and `deps.ProjectAccess(project: Project, user_id: int, role: str)` — NamedTuples
  - `deps.require_org_role(*roles)` → FastAPI dependency taking path param `org_id`, returning `OrgAccess`
  - `deps.require_project_role(*roles)` → FastAPI dependency taking path param `project_id`, returning `ProjectAccess`
  - `deps.get_db` (re-export)
  - fixtures `org_role(role="owner", org_id=1, status_code=200, body=None, exc=None)` and `make_project(org_id=1, name="Checkout E2E", slug=None, created_by=1) -> Project`

- [ ] **Step 1: Add the fixtures**

Append to `platforms/project-service/tests/conftest.py`:
```python


ORG_ME_URL = "{base}/api/v1/organizations/{org_id}/members/me"


@pytest.fixture
def org_role(http):
    """Mock organization-service's members/me for one org. Calling it again for the same org
    replaces the previous answer (respx replaces routes that share a name)."""
    import httpx

    def _set(role="owner", org_id=1, status_code=200, body=None, exc=None):
        route = http.get(
            ORG_ME_URL.format(base=settings.ORGANIZATION_SERVICE_URL, org_id=org_id), name=f"org-me-{org_id}"
        )
        if exc is not None:
            return route.mock(side_effect=exc)
        # Exactly the contract shape from the design spec, unless a test overrides the body
        return route.mock(return_value=httpx.Response(status_code, json={"role": role} if body is None else body))

    return _set


@pytest.fixture
def make_project(db):
    """Insert a live project directly, bypassing the API and its role checks."""

    def _make(org_id=1, name="Checkout E2E", slug=None, created_by=1):
        project = Project(
            organization_id=org_id,
            name=name,
            slug=slug or name.lower().replace(" ", "-"),
            settings={},
            created_by=created_by,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    return _make
```

- [ ] **Step 2: Write the failing client tests**

`platforms/project-service/tests/unit/test_org_client.py`:
```python
import httpx
import pytest

from src.project.utils import org_client


def test_returns_the_role_and_forwards_only_the_callers_token(org_role):
    route = org_role("admin", org_id=7)
    assert org_client.get_my_role(7, "caller-token") == "admin"
    assert route.calls.last.request.headers["Authorization"] == "Bearer caller-token"


def test_404_is_not_a_member(org_role):
    org_role(org_id=7, status_code=404, body={"detail": "Not a member of this organization"})
    with pytest.raises(org_client.NotAMember):
        org_client.get_my_role(7, "t")


def test_401_is_invalid_credentials(org_role):
    org_role(org_id=7, status_code=401, body={"detail": "Could not validate credentials"})
    with pytest.raises(org_client.InvalidCredentials):
        org_client.get_my_role(7, "t")


@pytest.mark.parametrize("status_code", [403, 500, 502, 503])
def test_other_statuses_are_unavailable(org_role, status_code):
    org_role(org_id=7, status_code=status_code, body={"detail": "x"})
    with pytest.raises(org_client.OrgServiceUnavailable):
        org_client.get_my_role(7, "t")


def test_timeout_is_unavailable(org_role):
    org_role(org_id=7, exc=httpx.ReadTimeout("slow"))
    with pytest.raises(org_client.OrgServiceUnavailable):
        org_client.get_my_role(7, "t")


def test_connection_error_is_unavailable(org_role):
    org_role(org_id=7, exc=httpx.ConnectError("refused"))
    with pytest.raises(org_client.OrgServiceUnavailable):
        org_client.get_my_role(7, "t")


@pytest.mark.parametrize(
    "body",
    [
        {"role": "superuser"},                   # not one of the five roles
        {"role": "admin", "extra": True},        # not exactly one key
        {"member_role": "admin"},                # renamed key
        ["admin"],                               # not an object
    ],
)
def test_200_outside_the_contract_is_unavailable(org_role, body):
    org_role(org_id=7, body=body)
    with pytest.raises(org_client.OrgServiceUnavailable):
        org_client.get_my_role(7, "t")


def test_200_with_non_json_body_is_unavailable(http):
    from src.project.core.config import settings

    http.get(
        f"{settings.ORGANIZATION_SERVICE_URL}/api/v1/organizations/7/members/me", name="org-me-7"
    ).mock(return_value=httpx.Response(200, text="<html>oops</html>"))
    with pytest.raises(org_client.OrgServiceUnavailable):
        org_client.get_my_role(7, "t")
```

- [ ] **Step 3: Run to verify failure**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/unit/test_org_client.py -q`
Expected: FAIL — `ImportError: cannot import name 'org_client'`.

- [ ] **Step 4: Implement the client**

`platforms/project-service/src/project/utils/org_client.py`:
```python
"""The caller's role in an organization, from organization-service's members/me.

The response shape is a contract pinned in docs/superpowers/specs/2026-09-28-project-service-design.md:
200 -> exactly {"role": <one of ORG_ROLES>}. Anything else on a 200 is treated as the service being
unavailable, so a changed or broken response can never be read as a granted role.
"""
import httpx

from src.project.core.config import settings

ORG_ROLES = ("owner", "admin", "member", "viewer", "billing_manager")


class OrgServiceUnavailable(Exception):
    """organization-service could not give a trustworthy answer."""


class NotAMember(Exception):
    """The caller is not an active member, or the organization does not exist or is deleted."""


class InvalidCredentials(Exception):
    """organization-service rejected the caller's token."""


def get_my_role(org_id: int, token: str) -> str:
    url = f"{settings.ORGANIZATION_SERVICE_URL}/api/v1/organizations/{int(org_id)}/members/me"
    try:
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=settings.ORGANIZATION_SERVICE_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise OrgServiceUnavailable(f"could not reach organization-service: {exc}") from exc

    if response.status_code == 404:
        raise NotAMember()
    if response.status_code == 401:
        raise InvalidCredentials()
    if response.status_code != 200:
        raise OrgServiceUnavailable(f"unexpected organization-service status {response.status_code}")
    try:
        body = response.json()
    except ValueError as exc:
        raise OrgServiceUnavailable("organization-service returned a non-JSON body") from exc
    if not isinstance(body, dict) or set(body) != {"role"} or body["role"] not in ORG_ROLES:
        raise OrgServiceUnavailable("organization-service response does not match the members/me contract")
    return body["role"]
```

- [ ] **Step 5: Run to verify the client passes**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/unit/test_org_client.py -q`
Expected: 14 passed.

- [ ] **Step 6: Write the failing dependency tests**

These mount the dependencies on a throwaway app so they are tested before any real route exists.

`platforms/project-service/tests/integration/test_deps.py`:
```python
import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from conftest import make_token
from src.project.api.deps import (
    EDIT_ROLES, MANAGE_ROLES, OrgAccess, ProjectAccess, get_db, require_org_role, require_project_role,
)

probe_app = FastAPI()


@probe_app.get("/orgs/{org_id}/probe")
def org_probe(access: OrgAccess = Depends(require_org_role(*MANAGE_ROLES))):
    return {"org_id": access.org_id, "user_id": access.user_id, "role": access.role}


@probe_app.get("/projects/{project_id}/probe")
def project_probe(access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES))):
    return {"project_id": access.project.id, "user_id": access.user_id, "role": access.role}


@pytest.fixture
def probe(db):
    probe_app.dependency_overrides[get_db] = lambda: db
    with TestClient(probe_app) as c:
        yield c
    probe_app.dependency_overrides.clear()


def test_missing_token_is_401_without_calling_org_service(probe, http):
    assert probe.get("/orgs/1/probe").status_code == 401
    assert not http.calls


def test_refresh_token_is_401(probe):
    headers = {"Authorization": f"Bearer {make_token(1, token_type='refresh')}"}
    assert probe.get("/orgs/1/probe", headers=headers).status_code == 401


def test_allowed_org_role_passes_through(probe, auth, org_role):
    org_role("admin", org_id=1)
    response = probe.get("/orgs/1/probe", headers=auth(5))
    assert response.status_code == 200
    assert response.json() == {"org_id": 1, "user_id": 5, "role": "admin"}


def test_insufficient_org_role_is_403(probe, auth, org_role):
    org_role("member", org_id=1)
    assert probe.get("/orgs/1/probe", headers=auth()).status_code == 403


def test_non_member_of_org_is_404(probe, auth, org_role):
    org_role(org_id=1, status_code=404, body={"detail": "Not a member"})
    response = probe.get("/orgs/1/probe", headers=auth())
    assert response.status_code == 404
    assert response.json()["detail"] == "Organization not found"


def test_org_service_401_is_401(probe, auth, org_role):
    org_role(org_id=1, status_code=401, body={"detail": "bad"})
    assert probe.get("/orgs/1/probe", headers=auth()).status_code == 401


def test_org_service_down_is_503(probe, auth, org_role):
    org_role(org_id=1, exc=httpx.ConnectError("refused"))
    response = probe.get("/orgs/1/probe", headers=auth())
    assert response.status_code == 503
    assert response.json()["detail"] == "Organization service unavailable"


def test_project_role_is_checked_against_the_projects_own_org(probe, auth, org_role, make_project):
    project = make_project(org_id=42)
    route = org_role("member", org_id=42)
    response = probe.get(f"/projects/{project.id}/probe", headers=auth(3))
    assert response.status_code == 200
    assert response.json() == {"project_id": project.id, "user_id": 3, "role": "member"}
    assert route.called


def test_member_of_another_org_cannot_reach_the_project(probe, auth, org_role, make_project):
    project = make_project(org_id=42)
    org_role("owner", org_id=1)                                            # caller owns org 1 ...
    org_role(org_id=42, status_code=404, body={"detail": "Not a member"})  # ... but not org 42
    response = probe.get(f"/projects/{project.id}/probe", headers=auth())
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


def test_missing_project_is_404_without_calling_org_service(probe, auth, http):
    assert probe.get("/projects/999/probe", headers=auth()).status_code == 404
    assert not http.calls


def test_soft_deleted_project_is_404_even_for_owner(probe, auth, org_role, make_project, db):
    from datetime import datetime, timezone

    project = make_project()
    project.deleted_at = datetime.now(timezone.utc)
    db.commit()
    org_role("owner")
    assert probe.get(f"/projects/{project.id}/probe", headers=auth()).status_code == 404


def test_insufficient_project_role_is_403(probe, auth, org_role, make_project):
    project = make_project()
    org_role("viewer")
    assert probe.get(f"/projects/{project.id}/probe", headers=auth()).status_code == 403
```

- [ ] **Step 7: Run to verify failure**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/integration/test_deps.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.project.api.deps'`.

If `from conftest import make_token` fails to import, run with `-p no:cacheprovider` to confirm it is the import and not the cache; pytest's default `prepend` import mode puts `tests/` on `sys.path` because `tests/conftest.py` has no `__init__.py`, so the import is expected to work.

- [ ] **Step 8: Implement the dependencies**

`platforms/project-service/src/project/api/deps.py`:
```python
from typing import NamedTuple

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.project.db.session import get_db
from src.project.models.project import Project
from src.project.utils import org_client
from src.project.utils.tokens import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

MANAGE_ROLES = ("owner", "admin")
EDIT_ROLES = ("owner", "admin", "member")
READ_ROLES = org_client.ORG_ROLES


class Caller(NamedTuple):
    user_id: int
    token: str


class OrgAccess(NamedTuple):
    org_id: int
    user_id: int
    role: str


class ProjectAccess(NamedTuple):
    project: Project
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


def _role_in(org_id: int, caller: Caller, not_found_detail: str) -> str:
    try:
        return org_client.get_my_role(org_id, caller.token)
    except org_client.NotAMember:
        # never 403: a non-member must not learn that the organization or project exists
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)
    except org_client.InvalidCredentials:
        raise _unauthorized()
    except org_client.OrgServiceUnavailable:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Organization service unavailable")


def _forbidden() -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")


def require_org_role(*roles: str):
    def dependency(org_id: int, caller: Caller = Depends(get_caller)) -> OrgAccess:
        role = _role_in(org_id, caller, "Organization not found")
        if role not in roles:
            raise _forbidden()
        return OrgAccess(org_id=org_id, user_id=caller.user_id, role=role)

    return dependency


def require_project_role(*roles: str):
    def dependency(
        project_id: int,
        db: Session = Depends(get_db),
        caller: Caller = Depends(get_caller),
    ) -> ProjectAccess:
        project = (
            db.query(Project).filter(Project.id == project_id, Project.deleted_at.is_(None)).first()
        )
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        # The organization comes from the project row, never from the URL
        role = _role_in(project.organization_id, caller, "Project not found")
        if role not in roles:
            raise _forbidden()
        return ProjectAccess(project=project, user_id=caller.user_id, role=role)

    return dependency


__all__ = [
    "get_db", "get_caller", "require_org_role", "require_project_role",
    "OrgAccess", "ProjectAccess", "MANAGE_ROLES", "EDIT_ROLES", "READ_ROLES",
]
```

- [ ] **Step 9: Run the whole suite**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q`
Expected: 93 passed (11 + 56 + 14 + 12).

- [ ] **Step 10: Commit**

```bash
git add platforms/project-service/src/project/utils/org_client.py \
        platforms/project-service/src/project/api/deps.py \
        platforms/project-service/tests/conftest.py \
        platforms/project-service/tests/unit/test_org_client.py \
        platforms/project-service/tests/integration/test_deps.py
git commit -m "feat(project-service): authorize every request against organization-service members/me"
```

---

### Task 5: Project endpoints and settings

**Files:**
- Create: `platforms/project-service/src/project/schemas/settings.py`
- Create: `platforms/project-service/src/project/schemas/project.py`
- Create: `platforms/project-service/src/project/service/project_service.py`
- Create: `platforms/project-service/src/project/api/v1/endpoints/projects.py`
- Modify: `platforms/project-service/src/project/api/v1/api.py`
- Create: `platforms/project-service/tests/unit/test_settings.py`
- Create: `platforms/project-service/tests/integration/test_projects_endpoints.py`

**Interfaces:**
- Consumes: `deps.require_org_role`, `deps.require_project_role`, `deps.MANAGE_ROLES/EDIT_ROLES/READ_ROLES`, `OrgAccess`, `ProjectAccess`, `Project`; fixtures `client`, `db`, `auth`, `org_role`, `make_project`, `http`.
- Produces:
  - `schemas.settings.ProjectSettings`; `settings_view(stored: dict | None) -> ProjectSettings`; `merge_settings(stored: dict | None, patch: dict) -> dict` (raises `ValueError` for unknown keys, `pydantic.ValidationError` for bad values)
  - `service.project_service.slugify(name: str) -> str`; `DuplicateProject(Exception)`
  - Routers `projects.org_router` (mounted at `/organizations/{org_id}/projects`) and `projects.router` (mounted at `/projects`). Task 6 mounts its router at `/projects/{project_id}/repositories` in the same `api.py`.

- [ ] **Step 1: Write the failing settings tests**

`platforms/project-service/tests/unit/test_settings.py`:
```python
import pytest
from pydantic import ValidationError

from src.project.schemas.settings import merge_settings, settings_view


def test_view_fills_every_default():
    assert settings_view({}).model_dump() == {
        "result_retention_days": 90,
        "default_environment": None,
        "notify_on_failure": False,
    }
    assert settings_view(None).result_retention_days == 90


def test_merge_stores_only_explicit_keys():
    assert merge_settings({}, {"notify_on_failure": True}) == {"notify_on_failure": True}


def test_merge_keeps_absent_keys():
    assert merge_settings({"result_retention_days": 30}, {"notify_on_failure": True}) == {
        "result_retention_days": 30,
        "notify_on_failure": True,
    }


def test_null_reverts_a_key_to_its_default():
    assert merge_settings({"result_retention_days": 30}, {"result_retention_days": None}) == {}


def test_values_are_stored_coerced():
    assert merge_settings({}, {"result_retention_days": "30"}) == {"result_retention_days": 30}


def test_unknown_key_is_rejected():
    with pytest.raises(ValueError, match="retention_dayz"):
        merge_settings({}, {"retention_dayz": 5})


@pytest.mark.parametrize(
    "patch",
    [
        {"result_retention_days": 0},
        {"result_retention_days": 366},
        {"default_environment": "x" * 51},
        {"notify_on_failure": "definitely"},
    ],
)
def test_invalid_values_are_rejected(patch):
    with pytest.raises(ValidationError):
        merge_settings({}, patch)


def test_merge_does_not_mutate_the_stored_dict():
    stored = {"result_retention_days": 30}
    merge_settings(stored, {"result_retention_days": 60})
    assert stored == {"result_retention_days": 30}
```

- [ ] **Step 2: Run to verify failure**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/unit/test_settings.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.project.schemas.settings'`.

- [ ] **Step 3: Implement settings**

`platforms/project-service/src/project/schemas/settings.py`:
```python
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProjectSettings(BaseModel):
    # unknown keys are rejected so a typo surfaces instead of being silently stored
    model_config = ConfigDict(extra="forbid")

    result_retention_days: int = Field(90, ge=1, le=365)
    default_environment: Optional[str] = Field(None, max_length=50)
    notify_on_failure: bool = False


def settings_view(stored: Optional[dict]) -> ProjectSettings:
    """The full settings, with defaults for every key that was never set."""
    return ProjectSettings.model_validate(stored or {})


def merge_settings(stored: Optional[dict], patch: dict) -> dict:
    """Merge-patch: present keys replace, null removes (reverting to the default), absent keys stay.

    Returns a new dict holding only explicitly-set keys, with their validated values, so adding a
    setting with a default later needs no data migration.
    """
    unknown = set(patch) - set(ProjectSettings.model_fields)
    if unknown:
        raise ValueError(f"Unknown setting(s): {', '.join(sorted(unknown))}")

    merged = dict(stored or {})
    for key, value in patch.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value

    validated = ProjectSettings.model_validate(merged)
    return {key: getattr(validated, key) for key in merged}
```

- [ ] **Step 4: Run to verify the settings tests pass**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/unit/test_settings.py -q`
Expected: 11 passed.

- [ ] **Step 5: Write the failing endpoint tests**

`platforms/project-service/tests/integration/test_projects_endpoints.py`:
```python
from datetime import datetime, timezone

import httpx
import pytest

ALL_ROLES = ("owner", "admin", "member", "viewer", "billing_manager")

# (method, path, body, roles allowed, success status) -- the endpoint table in the design spec
ROUTES = [
    ("POST", "/api/v1/organizations/1/projects", {"name": "New Project"}, ("owner", "admin"), 201),
    ("GET", "/api/v1/organizations/1/projects", None, ALL_ROLES, 200),
    ("GET", "/api/v1/projects/{pid}", None, ALL_ROLES, 200),
    ("PATCH", "/api/v1/projects/{pid}", {"description": "updated"}, ("owner", "admin"), 200),
    ("PATCH", "/api/v1/projects/{pid}/settings", {"notify_on_failure": True}, ("owner", "admin", "member"), 200),
    ("DELETE", "/api/v1/projects/{pid}", None, ("owner", "admin"), 204),
]


@pytest.mark.parametrize("method, path, body, allowed, ok", ROUTES)
@pytest.mark.parametrize("role", ALL_ROLES)
def test_role_matrix(client, auth, org_role, make_project, method, path, body, allowed, ok, role):
    project = make_project()
    org_role(role)
    response = client.request(method, path.format(pid=project.id), json=body, headers=auth())
    assert response.status_code == (ok if role in allowed else 403)


def test_create_sets_creator_slug_defaults_and_my_role(client, auth, org_role):
    org_role("admin")
    response = client.post(
        "/api/v1/organizations/1/projects",
        json={"name": "Checkout E2E", "description": "web checkout"},
        headers=auth(7),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["organization_id"] == 1
    assert body["slug"] == "checkout-e2e"
    assert body["created_by"] == 7
    assert body["my_role"] == "admin"
    assert body["settings"] == {"result_retention_days": 90, "default_environment": None, "notify_on_failure": False}


def test_explicit_slug_is_kept(client, auth, org_role):
    org_role("owner")
    response = client.post(
        "/api/v1/organizations/1/projects", json={"name": "Checkout", "slug": "co-web"}, headers=auth()
    )
    assert response.json()["slug"] == "co-web"


@pytest.mark.parametrize("slug", ["Has Space", "UPPER", "-lead", "trail-", "double--dash", "x" * 101])
def test_invalid_explicit_slug_is_422(client, auth, org_role, slug):
    org_role("owner")
    response = client.post("/api/v1/organizations/1/projects", json={"name": "P", "slug": slug}, headers=auth())
    assert response.status_code == 422


@pytest.mark.parametrize("name", ["!!!", "***"])
def test_name_that_slugifies_to_nothing_is_422(client, auth, org_role, name):
    org_role("owner")
    response = client.post("/api/v1/organizations/1/projects", json={"name": name}, headers=auth())
    assert response.status_code == 422
    assert "slug" in response.text


@pytest.mark.parametrize("name", ["", "   "])
def test_blank_name_is_422(client, auth, org_role, name):
    org_role("owner")
    response = client.post("/api/v1/organizations/1/projects", json={"name": name}, headers=auth())
    assert response.status_code == 422


def test_duplicate_name_in_same_org_is_409_and_session_recovers(client, auth, org_role, make_project):
    make_project(name="Checkout", slug="checkout")
    org_role("owner")
    response = client.post(
        "/api/v1/organizations/1/projects", json={"name": "Checkout", "slug": "other"}, headers=auth()
    )
    assert response.status_code == 409
    # the next request on the same session still works (the failed insert was rolled back)
    assert client.get("/api/v1/organizations/1/projects", headers=auth()).status_code == 200


def test_same_name_in_another_org_is_fine(client, auth, org_role, make_project):
    make_project(org_id=2, name="Checkout", slug="checkout")
    org_role("owner", org_id=1)
    response = client.post("/api/v1/organizations/1/projects", json={"name": "Checkout"}, headers=auth())
    assert response.status_code == 201


def test_deleted_projects_name_can_be_reused(client, auth, org_role, make_project):
    project = make_project(name="Checkout", slug="checkout")
    org_role("owner")
    assert client.delete(f"/api/v1/projects/{project.id}", headers=auth()).status_code == 204
    response = client.post("/api/v1/organizations/1/projects", json={"name": "Checkout"}, headers=auth())
    assert response.status_code == 201


def test_rename_onto_a_live_name_is_409(client, auth, org_role, make_project):
    make_project(name="Taken", slug="taken")
    project = make_project(name="Mine", slug="mine")
    org_role("owner")
    response = client.patch(f"/api/v1/projects/{project.id}", json={"name": "Taken"}, headers=auth())
    assert response.status_code == 409
    assert client.get(f"/api/v1/projects/{project.id}", headers=auth()).json()["name"] == "Mine"


def test_rename_onto_a_deleted_name_is_allowed(client, auth, org_role, make_project, db):
    gone = make_project(name="Old", slug="old")
    gone.deleted_at = datetime.now(timezone.utc)
    db.commit()
    project = make_project(name="Mine", slug="mine")
    org_role("owner")
    response = client.patch(f"/api/v1/projects/{project.id}", json={"name": "Old", "slug": "old"}, headers=auth())
    assert response.status_code == 200
    assert response.json()["slug"] == "old"


@pytest.mark.parametrize("field", ["name", "slug"])
def test_patch_cannot_null_a_required_field(client, auth, org_role, make_project, field):
    project = make_project()
    org_role("owner")
    response = client.patch(f"/api/v1/projects/{project.id}", json={field: None}, headers=auth())
    assert response.status_code == 422


def test_patch_can_clear_description(client, auth, org_role, make_project):
    project = make_project()
    org_role("owner")
    client.patch(f"/api/v1/projects/{project.id}", json={"description": "x"}, headers=auth())
    response = client.patch(f"/api/v1/projects/{project.id}", json={"description": None}, headers=auth())
    assert response.json()["description"] is None


def test_list_only_this_orgs_live_projects_in_id_order(client, auth, org_role, make_project, db):
    first = make_project(name="A", slug="a")
    second = make_project(name="B", slug="b")
    deleted = make_project(name="C", slug="c")
    deleted.deleted_at = datetime.now(timezone.utc)
    db.commit()
    make_project(org_id=2, name="Other", slug="other")
    org_role("viewer")
    body = client.get("/api/v1/organizations/1/projects", headers=auth()).json()
    assert [p["id"] for p in body] == [first.id, second.id]
    assert all(p["my_role"] == "viewer" for p in body)


def test_list_pagination(client, auth, org_role, make_project):
    for i in range(5):
        make_project(name=f"P{i}", slug=f"p{i}")
    org_role("viewer")
    page = client.get("/api/v1/organizations/1/projects?limit=2&offset=2", headers=auth()).json()
    assert [p["name"] for p in page] == ["P2", "P3"]


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_list_rejects_bad_pagination(client, auth, org_role, query):
    org_role("viewer")
    assert client.get(f"/api/v1/organizations/1/projects?{query}", headers=auth()).status_code == 422


def test_settings_patch_merges_and_null_reverts(client, auth, org_role, make_project):
    project = make_project()
    org_role("member")
    url = f"/api/v1/projects/{project.id}/settings"
    client.patch(url, json={"result_retention_days": 30}, headers=auth())
    client.patch(url, json={"notify_on_failure": True}, headers=auth())
    body = client.get(f"/api/v1/projects/{project.id}", headers=auth()).json()["settings"]
    assert body == {"result_retention_days": 30, "default_environment": None, "notify_on_failure": True}

    reverted = client.patch(url, json={"result_retention_days": None}, headers=auth()).json()["settings"]
    assert reverted["result_retention_days"] == 90


@pytest.mark.parametrize(
    "patch", [{"retention_dayz": 5}, {"result_retention_days": 0}, {"result_retention_days": "lots"}]
)
def test_invalid_settings_are_422_and_nothing_is_stored(client, auth, org_role, make_project, patch):
    project = make_project()
    org_role("member")
    response = client.patch(f"/api/v1/projects/{project.id}/settings", json=patch, headers=auth())
    assert response.status_code == 422
    assert client.get(f"/api/v1/projects/{project.id}", headers=auth()).json()["settings"]["result_retention_days"] == 90


def test_settings_body_must_be_an_object(client, auth, org_role, make_project):
    project = make_project()
    org_role("member")
    response = client.patch(f"/api/v1/projects/{project.id}/settings", json=[1, 2], headers=auth())
    assert response.status_code == 422


def test_deleted_project_is_gone_for_everyone(client, auth, org_role, make_project):
    project = make_project()
    org_role("owner")
    client.delete(f"/api/v1/projects/{project.id}", headers=auth())
    assert client.get(f"/api/v1/projects/{project.id}", headers=auth()).status_code == 404


def test_org_service_down_is_503(client, auth, org_role, make_project):
    project = make_project()
    org_role(exc=httpx.ConnectError("refused"))
    assert client.get(f"/api/v1/projects/{project.id}", headers=auth()).status_code == 503
```

- [ ] **Step 6: Run to verify failure**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/integration/test_projects_endpoints.py -q`
Expected: FAIL — the routes do not exist yet (404s), e.g. `test_create_sets_creator_slug_defaults_and_my_role` fails with `assert 404 == 201`.

- [ ] **Step 7: Schemas**

`platforms/project-service/src/project/schemas/project.py`:
```python
from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, StringConstraints, model_validator

from src.project.schemas.settings import ProjectSettings

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Slug = Annotated[str, StringConstraints(max_length=100, pattern=SLUG_PATTERN)]


class ProjectCreate(BaseModel):
    name: Name
    slug: Optional[Slug] = None
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[Name] = None
    slug: Optional[Slug] = None
    description: Optional[str] = None

    @model_validator(mode="after")
    def _required_fields_cannot_be_nulled(self):
        for field in ("name", "slug"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ProjectOut(BaseModel):
    id: int
    organization_id: int
    name: str
    slug: str
    description: Optional[str] = None
    settings: ProjectSettings
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    my_role: str
```

- [ ] **Step 8: Service**

`platforms/project-service/src/project/service/project_service.py`:
```python
import re
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.project.models.project import Project
from src.project.schemas.project import ProjectCreate, ProjectUpdate
from src.project.schemas.settings import merge_settings


class DuplicateProject(Exception):
    pass


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:100].rstrip("-")


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        # roll back so the session stays usable for the rest of the request and the next one
        db.rollback()
        raise DuplicateProject("A project with this name or slug already exists in the organization")


def create_project(db: Session, org_id: int, user_id: int, data: ProjectCreate) -> Project:
    slug = data.slug or slugify(data.name)
    if not slug:
        raise ValueError("Could not derive a slug from the project name; supply one")
    project = Project(
        organization_id=org_id,
        name=data.name,
        slug=slug,
        description=data.description,
        settings={},
        created_by=user_id,
    )
    db.add(project)
    _commit(db)
    db.refresh(project)
    return project


def list_projects(db: Session, org_id: int, limit: int, offset: int) -> list[Project]:
    return (
        db.query(Project)
        .filter(Project.organization_id == org_id, Project.deleted_at.is_(None))
        .order_by(Project.id)
        .offset(offset)
        .limit(limit)
        .all()
    )


def update_project(db: Session, project: Project, data: ProjectUpdate) -> Project:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    _commit(db)
    db.refresh(project)
    return project


def update_settings(db: Session, project: Project, patch: dict) -> Project:
    # merge_settings returns a new dict, which is what makes SQLAlchemy see the change
    project.settings = merge_settings(project.settings, patch)
    db.commit()
    db.refresh(project)
    return project


def soft_delete(db: Session, project: Project) -> None:
    project.deleted_at = datetime.now(timezone.utc)
    db.commit()
```

- [ ] **Step 9: Endpoints and router**

`platforms/project-service/src/project/api/v1/endpoints/projects.py`:
```python
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from src.project.api.deps import (
    EDIT_ROLES, MANAGE_ROLES, READ_ROLES, OrgAccess, ProjectAccess, get_db, require_org_role, require_project_role,
)
from src.project.models.project import Project
from src.project.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate
from src.project.schemas.settings import settings_view
from src.project.service import project_service

org_router = APIRouter()   # mounted at /organizations/{org_id}/projects
router = APIRouter()       # mounted at /projects


def _out(project: Project, role: str) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        organization_id=project.organization_id,
        name=project.name,
        slug=project.slug,
        description=project.description,
        settings=settings_view(project.settings),
        created_by=project.created_by,
        created_at=project.created_at,
        updated_at=project.updated_at,
        my_role=role,
    )


@org_router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    access: OrgAccess = Depends(require_org_role(*MANAGE_ROLES)),
):
    try:
        project = project_service.create_project(db, access.org_id, access.user_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except project_service.DuplicateProject as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return _out(project, access.role)


@org_router.get("", response_model=list[ProjectOut])
def list_projects(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    access: OrgAccess = Depends(require_org_role(*READ_ROLES)),
):
    projects = project_service.list_projects(db, access.org_id, limit, offset)
    return [_out(project, access.role) for project in projects]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(access: ProjectAccess = Depends(require_project_role(*READ_ROLES))):
    return _out(access.project, access.role)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*MANAGE_ROLES)),
):
    try:
        project = project_service.update_project(db, access.project, payload)
    except project_service.DuplicateProject as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return _out(project, access.role)


@router.patch("/{project_id}/settings", response_model=ProjectOut)
def update_settings(
    patch: dict = Body(...),
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    try:
        project = project_service.update_settings(db, access.project, patch)
    except ValidationError as exc:
        db.rollback()
        detail = [{"loc": list(error["loc"]), "msg": error["msg"]} for error in exc.errors()]
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return _out(project, access.role)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*MANAGE_ROLES)),
):
    project_service.soft_delete(db, access.project)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

Note: `pydantic.ValidationError` is a subclass of `ValueError`, which is why it is caught first.

Replace `platforms/project-service/src/project/api/v1/api.py` with:
```python
from fastapi import APIRouter

from src.project.api.v1.endpoints import projects

api_router = APIRouter()
api_router.include_router(projects.org_router, prefix="/organizations/{org_id}/projects", tags=["projects"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])

__all__ = ["api_router"]
```

- [ ] **Step 10: Run the whole suite**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q`
Expected: 166 passed — 93 from earlier tasks + 11 settings + 62 in the endpoint file (30 role-matrix cases + 32 others). If the count differs, report the actual number; the requirement is that every test passes.

- [ ] **Step 11: Commit**

```bash
git add platforms/project-service/src/project/schemas \
        platforms/project-service/src/project/service/project_service.py \
        platforms/project-service/src/project/api/v1 \
        platforms/project-service/tests/unit/test_settings.py \
        platforms/project-service/tests/integration/test_projects_endpoints.py
git commit -m "feat(project-service): project CRUD, merge-patched settings, org-role permissions"
```

---

### Task 6: Repository endpoints

**Files:**
- Create: `platforms/project-service/src/project/schemas/repository.py`
- Create: `platforms/project-service/src/project/service/repository_service.py`
- Create: `platforms/project-service/src/project/api/v1/endpoints/repositories.py`
- Modify: `platforms/project-service/src/project/api/v1/api.py`
- Create: `platforms/project-service/tests/integration/test_repositories_endpoints.py`

**Interfaces:**
- Consumes: `repo_url.parse_repo_url`, `ParsedRepo`; `repo_verifier.verify`, `VerificationResult`; `deps.require_project_role`, `EDIT_ROLES`, `READ_ROLES`, `ProjectAccess`; `Repository`; `settings.REPO_VERIFY_TIMEOUT_SECONDS`, `settings.REPO_VERIFY_COOLDOWN_SECONDS`; fixtures `client`, `db`, `auth`, `org_role`, `make_project`, `http`.
- Produces: router `repositories.router` mounted at `/projects/{project_id}/repositories`.

- [ ] **Step 1: Write the failing tests**

`platforms/project-service/tests/integration/test_repositories_endpoints.py`:
```python
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from src.project.core.config import settings
from src.project.models.repository import Repository

ALL_ROLES = ("owner", "admin", "member", "viewer", "billing_manager")
EDITORS = ("owner", "admin", "member")
GITHUB_API = "https://api.github.com/repos/acme/shop"


@pytest.fixture
def github(http):
    """Mock the GitHub API for acme/shop; github(status, branch) replaces the previous answer."""

    def _set(status_code=200, branch="main"):
        body = {"default_branch": branch} if status_code == 200 else {"message": "x"}
        return http.get(GITHUB_API, name="github-acme-shop").mock(return_value=httpx.Response(status_code, json=body))

    return _set


@pytest.fixture
def add_repo(db):
    def _add(project, **overrides):
        values = dict(
            project_id=project.id, provider="github", owner="acme", name="shop", full_name_key="acme/shop",
            url="https://github.com/acme/shop", default_branch="main", default_branch_is_user_set=False,
            verification_status="unchecked", verified_at=None,
        )
        values.update(overrides)
        repo = Repository(**values)
        db.add(repo)
        db.commit()
        db.refresh(repo)
        return repo

    return _add


@pytest.mark.parametrize("role", ALL_ROLES)
def test_list_is_open_to_every_role(client, auth, org_role, make_project, role):
    project = make_project()
    org_role(role)
    assert client.get(f"/api/v1/projects/{project.id}/repositories", headers=auth()).status_code == 200


@pytest.mark.parametrize("role", ALL_ROLES)
def test_add_is_for_editors(client, auth, org_role, make_project, github, role):
    project = make_project()
    org_role(role)
    github()
    response = client.post(
        f"/api/v1/projects/{project.id}/repositories", json={"url": "https://github.com/acme/shop"}, headers=auth()
    )
    assert response.status_code == (201 if role in EDITORS else 403)


@pytest.mark.parametrize("role", ALL_ROLES)
def test_verify_is_for_editors(client, auth, org_role, make_project, add_repo, github, role):
    project = make_project()
    repo = add_repo(project)
    org_role(role)
    github()
    response = client.post(f"/api/v1/projects/{project.id}/repositories/{repo.id}/verify", headers=auth())
    assert response.status_code == (200 if role in EDITORS else 403)


@pytest.mark.parametrize("role", ALL_ROLES)
def test_delete_is_for_editors(client, auth, org_role, make_project, add_repo, role):
    project = make_project()
    repo = add_repo(project)
    org_role(role)
    response = client.delete(f"/api/v1/projects/{project.id}/repositories/{repo.id}", headers=auth())
    assert response.status_code == (204 if role in EDITORS else 403)


def test_add_verified_repository(client, auth, org_role, make_project, github):
    project = make_project()
    org_role("member")
    github(branch="develop")
    response = client.post(
        f"/api/v1/projects/{project.id}/repositories",
        json={"url": "git@github.com:acme/shop.git"},
        headers=auth(),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["provider"] == "github"
    assert (body["owner"], body["name"]) == ("acme", "shop")
    assert body["url"] == "https://github.com/acme/shop"
    assert body["verification_status"] == "verified"
    assert body["verified_at"] is not None
    assert body["default_branch"] == "develop"
    assert body["default_branch_is_user_set"] is False


def test_user_branch_wins_over_provider(client, auth, org_role, make_project, github):
    project = make_project()
    org_role("member")
    github(branch="develop")
    body = client.post(
        f"/api/v1/projects/{project.id}/repositories",
        json={"url": "https://github.com/acme/shop", "default_branch": "release"},
        headers=auth(),
    ).json()
    assert body["default_branch"] == "release"
    assert body["default_branch_is_user_set"] is True


@pytest.mark.parametrize("status_code, expected", [(404, "not_found"), (403, "unchecked"), (500, "unchecked")])
def test_failed_check_still_saves_with_main_fallback(client, auth, org_role, make_project, github, status_code, expected):
    project = make_project()
    org_role("member")
    github(status_code=status_code)
    response = client.post(
        f"/api/v1/projects/{project.id}/repositories", json={"url": "https://github.com/acme/shop"}, headers=auth()
    )
    assert response.status_code == 201
    assert response.json()["verification_status"] == expected
    assert response.json()["default_branch"] == "main"


def test_provider_timeout_still_saves_unchecked(client, auth, org_role, make_project, http):
    project = make_project()
    org_role("member")
    http.get(GITHUB_API).mock(side_effect=httpx.ReadTimeout("slow"))
    response = client.post(
        f"/api/v1/projects/{project.id}/repositories", json={"url": "https://github.com/acme/shop"}, headers=auth()
    )
    assert response.status_code == 201
    assert response.json()["verification_status"] == "unchecked"


@pytest.mark.parametrize(
    "url", ["https://bitbucket.org/acme/shop", "https://github.com.evil.com/acme/shop", "not a url"]
)
def test_unsupported_url_is_422_and_no_provider_call(client, auth, org_role, make_project, http, url):
    project = make_project()
    route = org_role("member")
    response = client.post(f"/api/v1/projects/{project.id}/repositories", json={"url": url}, headers=auth())
    assert response.status_code == 422
    # only the members/me call happened
    assert [call.request.url.host for call in http.calls] == [route.calls.last.request.url.host]


def test_duplicate_in_same_project_is_409_regardless_of_case(client, auth, org_role, make_project, add_repo, http):
    project = make_project()
    add_repo(project)
    org_role("member")
    response = client.post(
        f"/api/v1/projects/{project.id}/repositories", json={"url": "https://github.com/ACME/Shop"}, headers=auth()
    )
    assert response.status_code == 409
    # the duplicate is caught before spending provider quota
    assert all(call.request.url.host != "api.github.com" for call in http.calls)


def test_same_repository_in_two_projects_is_allowed(client, auth, org_role, make_project, add_repo, github):
    first = make_project(name="A", slug="a")
    add_repo(first)
    second = make_project(name="B", slug="b")
    org_role("member")
    github()
    response = client.post(
        f"/api/v1/projects/{second.id}/repositories", json={"url": "https://github.com/acme/shop"}, headers=auth()
    )
    assert response.status_code == 201


def test_verify_within_cooldown_does_not_call_the_provider(client, auth, org_role, make_project, add_repo, github):
    project = make_project()
    repo = add_repo(project, verification_status="not_found", verified_at=datetime.now(timezone.utc))
    org_role("member")
    route = github()
    response = client.post(f"/api/v1/projects/{project.id}/repositories/{repo.id}/verify", headers=auth())
    assert response.status_code == 200
    assert response.json()["verification_status"] == "not_found"
    assert not route.called


def test_verify_after_cooldown_updates_status_and_provider_branch(client, auth, org_role, make_project, add_repo, github):
    project = make_project()
    stale = datetime.now(timezone.utc) - timedelta(seconds=settings.REPO_VERIFY_COOLDOWN_SECONDS + 5)
    repo = add_repo(project, verification_status="unchecked", verified_at=stale)
    org_role("member")
    route = github(branch="develop")
    body = client.post(f"/api/v1/projects/{project.id}/repositories/{repo.id}/verify", headers=auth()).json()
    assert route.called
    assert body["verification_status"] == "verified"
    assert body["default_branch"] == "develop"


def test_verify_never_overwrites_a_user_branch(client, auth, org_role, make_project, add_repo, github):
    project = make_project()
    repo = add_repo(project, default_branch="release", default_branch_is_user_set=True)
    org_role("member")
    github(branch="develop")
    body = client.post(f"/api/v1/projects/{project.id}/repositories/{repo.id}/verify", headers=auth()).json()
    assert body["default_branch"] == "release"


def test_failed_check_also_starts_the_cooldown(client, auth, org_role, make_project, add_repo, github):
    project = make_project()
    repo = add_repo(project)
    org_role("member")
    first = github(status_code=500)
    client.post(f"/api/v1/projects/{project.id}/repositories/{repo.id}/verify", headers=auth())
    assert first.call_count == 1
    client.post(f"/api/v1/projects/{project.id}/repositories/{repo.id}/verify", headers=auth())
    assert first.call_count == 1


def test_repository_of_another_project_is_404(client, auth, org_role, make_project, add_repo):
    mine = make_project(name="A", slug="a")
    other = make_project(name="B", slug="b")
    repo = add_repo(other)
    org_role("member")
    assert client.delete(f"/api/v1/projects/{mine.id}/repositories/{repo.id}", headers=auth()).status_code == 404
    assert client.post(f"/api/v1/projects/{mine.id}/repositories/{repo.id}/verify", headers=auth()).status_code == 404


def test_repositories_of_a_deleted_project_are_unreachable(client, auth, org_role, make_project, add_repo):
    project = make_project()
    add_repo(project)
    org_role("owner")
    client.delete(f"/api/v1/projects/{project.id}", headers=auth())
    assert client.get(f"/api/v1/projects/{project.id}/repositories", headers=auth()).status_code == 404


def test_delete_removes_the_repository(client, auth, org_role, make_project, add_repo):
    project = make_project()
    repo = add_repo(project)
    org_role("member")
    client.delete(f"/api/v1/projects/{project.id}/repositories/{repo.id}", headers=auth())
    assert client.get(f"/api/v1/projects/{project.id}/repositories", headers=auth()).json() == []


def test_blank_branch_is_422(client, auth, org_role, make_project):
    project = make_project()
    org_role("member")
    response = client.post(
        f"/api/v1/projects/{project.id}/repositories",
        json={"url": "https://github.com/acme/shop", "default_branch": "  "},
        headers=auth(),
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Run to verify failure**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/integration/test_repositories_endpoints.py -q`
Expected: FAIL — routes missing, e.g. `assert 404 == 201` in `test_add_verified_repository`.

- [ ] **Step 3: Schemas**

`platforms/project-service/src/project/schemas/repository.py`:
```python
from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Branch = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255, pattern=r"^\S+$")]


class RepositoryCreate(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    default_branch: Optional[Branch] = None


class RepositoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    provider: str
    owner: str
    name: str
    url: str
    default_branch: str
    default_branch_is_user_set: bool
    verification_status: str
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
```

- [ ] **Step 4: Service**

`platforms/project-service/src/project/service/repository_service.py`:
```python
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.project.core.config import settings
from src.project.models.project import Project
from src.project.models.repository import Repository
from src.project.schemas.repository import RepositoryCreate
from src.project.utils import repo_verifier
from src.project.utils.repo_url import parse_repo_url


class DuplicateRepository(Exception):
    pass


DUPLICATE_MESSAGE = "This repository is already attached to the project"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(moment: datetime) -> datetime:
    # SQLite returns naive datetimes even for DateTime(timezone=True); treat them as UTC
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def _check(repo: Repository) -> None:
    result = repo_verifier.verify(
        repo.provider, repo.owner, repo.name, timeout=settings.REPO_VERIFY_TIMEOUT_SECONDS
    )
    repo.verification_status = result.status
    repo.verified_at = _now()  # set whatever the outcome, so the cooldown covers failed checks too
    if result.status == repo_verifier.VERIFIED and result.default_branch and not repo.default_branch_is_user_set:
        repo.default_branch = result.default_branch


def add_repository(db: Session, project: Project, data: RepositoryCreate) -> Repository:
    parsed = parse_repo_url(data.url)  # ValueError -> 422 in the endpoint

    # Checked before calling the provider, so a duplicate spends none of the shared rate limit
    existing = (
        db.query(Repository)
        .filter_by(project_id=project.id, provider=parsed.provider, full_name_key=parsed.full_name_key)
        .first()
    )
    if existing is not None:
        raise DuplicateRepository(DUPLICATE_MESSAGE)

    repo = Repository(
        project_id=project.id,
        provider=parsed.provider,
        owner=parsed.owner,
        name=parsed.name,
        full_name_key=parsed.full_name_key,
        url=parsed.url,
        default_branch=data.default_branch or "main",
        default_branch_is_user_set=data.default_branch is not None,
    )
    _check(repo)
    db.add(repo)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # a concurrent insert of the same repository won the race
        raise DuplicateRepository(DUPLICATE_MESSAGE)
    db.refresh(repo)
    return repo


def list_repositories(db: Session, project: Project) -> list[Repository]:
    return db.query(Repository).filter_by(project_id=project.id).order_by(Repository.id).all()


def get_repository(db: Session, project: Project, repo_id: int) -> Optional[Repository]:
    return db.query(Repository).filter_by(project_id=project.id, id=repo_id).first()


def reverify(db: Session, repo: Repository) -> Repository:
    cooldown = timedelta(seconds=settings.REPO_VERIFY_COOLDOWN_SECONDS)
    if repo.verified_at is not None and _now() - _aware(repo.verified_at) < cooldown:
        return repo
    _check(repo)
    db.commit()
    db.refresh(repo)
    return repo


def delete_repository(db: Session, repo: Repository) -> None:
    db.delete(repo)
    db.commit()
```

- [ ] **Step 5: Endpoints and router**

`platforms/project-service/src/project/api/v1/endpoints/repositories.py`:
```python
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from src.project.api.deps import EDIT_ROLES, READ_ROLES, ProjectAccess, get_db, require_project_role
from src.project.schemas.repository import RepositoryCreate, RepositoryOut
from src.project.service import repository_service

router = APIRouter()  # mounted at /projects/{project_id}/repositories


def _repository_or_404(db: Session, access: ProjectAccess, repo_id: int):
    repo = repository_service.get_repository(db, access.project, repo_id)
    if repo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return repo


@router.get("", response_model=list[RepositoryOut])
def list_repositories(
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*READ_ROLES)),
):
    return repository_service.list_repositories(db, access.project)


@router.post("", response_model=RepositoryOut, status_code=status.HTTP_201_CREATED)
def add_repository(
    payload: RepositoryCreate,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    try:
        return repository_service.add_repository(db, access.project, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except repository_service.DuplicateRepository as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/{repo_id}/verify", response_model=RepositoryOut)
def verify_repository(
    repo_id: int,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    return repository_service.reverify(db, _repository_or_404(db, access, repo_id))


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_repository(
    repo_id: int,
    db: Session = Depends(get_db),
    access: ProjectAccess = Depends(require_project_role(*EDIT_ROLES)),
):
    repository_service.delete_repository(db, _repository_or_404(db, access, repo_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

Replace `platforms/project-service/src/project/api/v1/api.py` with:
```python
from fastapi import APIRouter

from src.project.api.v1.endpoints import projects, repositories

api_router = APIRouter()
api_router.include_router(projects.org_router, prefix="/organizations/{org_id}/projects", tags=["projects"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(
    repositories.router, prefix="/projects/{project_id}/repositories", tags=["repositories"]
)

__all__ = ["api_router"]
```

- [ ] **Step 6: Run the whole suite**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q`
Expected: 205 passed — Task 5's 166 plus this file's 39 (20 role-matrix cases + 19 others). Report the exact count.

- [ ] **Step 7: Commit**

```bash
git add platforms/project-service/src/project/schemas/repository.py \
        platforms/project-service/src/project/service/repository_service.py \
        platforms/project-service/src/project/api/v1 \
        platforms/project-service/tests/integration/test_repositories_endpoints.py
git commit -m "feat(project-service): attach, verify and remove repositories"
```

---

### Task 7: Documentation

**Files:**
- Create: `platforms/project-service/README.md`
- Modify: `README.md` (repository root — Project Structure block)
- Modify: `TODO.md` (Phase 3: Project Service items)

**Interfaces:** none (docs only).

- [ ] **Step 1: Service README**

`platforms/project-service/README.md`:
````markdown
# Project Service

Test projects owned by organizations, the repositories attached to them, and per-project settings.

Design: `docs/superpowers/specs/2026-09-28-project-service-design.md`.

## How access works

There are no project-level members. Every request asks organization-service for the caller's role
(`GET /api/v1/organizations/{org_id}/members/me`, forwarding the caller's own token):

| | owner / admin | member | viewer / billing_manager |
|---|---|---|---|
| Create, rename, delete projects | ✓ | | |
| Change settings, add/verify/remove repositories | ✓ | ✓ | |
| Read projects and repositories | ✓ | ✓ | ✓ |

Non-members get 404, never 403. If organization-service cannot answer, requests get 503.

## Repositories

Only `github.com` and `gitlab.com` URLs are accepted. On save, the service checks the repository
through the provider's public API and records `verification_status`:

- `verified` — reachable; the provider's default branch is used unless you supplied one
- `not_found` — missing **or private** (the check is unauthenticated, so the two look the same)
- `unchecked` — the provider was unreachable or rate-limited

The repository is saved in every case. `POST .../repositories/{id}/verify` re-checks it, at most
once per `REPO_VERIFY_COOLDOWN_SECONDS` (default 60): GitHub allows 60 anonymous requests per hour
per server IP, shared by every user.

## Running locally

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # also installs ../../shared
cp .env.example .env                                         # set SECRET_KEY = auth-service's
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m uvicorn src.project.api.main:app --reload --port 8002
```

API docs: http://localhost:8002/docs

With Docker (organization-service running in its own stack on host port 8001):

```bash
export SECRET_KEY=<same value as auth-service and organization-service>
docker compose up --build
```

## Tests

```bash
rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q
```

Every outgoing HTTP call in the suite is mocked with `respx`; an unmocked request fails the test.
````

- [ ] **Step 2: Root README project structure**

In the repository root `README.md`, inside the `## Project Structure` code block, find the lines for `platforms/`'s children (`auth-service/auth-service/` and `organization-service/`). Directly after the organization-service entry (and any lines nested under it), add a sibling entry at the same indentation as `organization-service/`:
```
│   ├── project-service/            # Projects, repositories, settings (implemented)
```
Match the tree characters (`│`, `├──`, `└──`) and comment column used by the neighbouring lines; if organization-service's entry uses `└──` because it was last, change it to `├──` and give project-service the `└──`.

- [ ] **Step 3: TODO.md**

In `TODO.md`, under `### Phase 3: Project Service`, change these items from `[ ]` to `[x]`: 40, 41, 45, 46, 47, 48, 49, 50. Leave 42, 43 and 44 unchecked, and append to each an explanation in italics:
- 42: ` *(deferred: access follows organization roles; see the project-service design spec)*`
- 43: ` *(not started)*`
- 44: ` *(not started)*`

Also correct the stray non-English word in item 43: `tagging系统` → `tagging system`.

- [ ] **Step 4: Commit**

```bash
git add platforms/project-service/README.md README.md TODO.md
git commit -m "docs(project-service): service README, repo structure, TODO status"
```
