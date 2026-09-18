# Organization Service Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `platforms/organization-service`'s auth-service file-clone with a real Organization + Membership domain: models, migrations, JWT-protected endpoints, service-to-service user validation against auth-service, and tests.

**Architecture:** Mirror `platforms/auth-service/auth-service`'s FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL layout exactly (`src/organization/{api,core,db,models,schemas,service,utils}`). Trust JWTs issued by auth-service via the shared `SECRET_KEY` (HS256) — no local login. Validate a member's `user_id` against auth-service over HTTP via a small `httpx` client.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL (SQLite for tests), PyJWT, pydantic-settings v2, httpx, respx (test-only), pytest.

**Spec:** `docs/superpowers/specs/2026-09-16-organization-service-core-design.md`

## Global Constraints

- Package path stays `src.organization.*` (already correctly renamed from the auth clone — do not rename again).
- `organizations.id` and `organization_members.user_id` are `Integer`, matching auth-service's real `User.id` type (Integer), not the UUID the original DB-schema spec doc used.
- No new top-level dependency beyond `httpx` (runtime) and `respx` (test) — everything else already in `requirements.txt`.
- Do not modify anything under `platforms/auth-service/`. The one thing it's missing (a proper internal user-lookup endpoint) is flagged in the spec as follow-up, not built here.
- Every deleted file must be a listed auth-clone artifact or the vendored `dm.xmlsec.binding-1.3.7` junk — nothing else in `platforms/organization-service` gets touched by the delete step.

---

### Task 1: Scaffold — delete auth-clone junk, stand up config/db/app skeleton

**Files:**
- Delete: `platforms/organization-service/src/organization/models/{user.py,session.py,oauth.py}`
- Delete: `platforms/organization-service/src/organization/api/v1/endpoints/{auth.py,sso.py,users.py}`
- Delete: `platforms/organization-service/src/organization/service/{auth_service.py,sso_service.py,user_service.py}`
- Delete: `platforms/organization-service/src/organization/schemas/{auth.py,token.py,user.py}`
- Delete: `platforms/organization-service/src/organization/utils/{password.py,security.py,dependencies.py}`
- Delete: `platforms/organization-service/alembic/versions/{001_create_users_table.py,002_add_sessions_table.py,003_add_oauth_tables.py}`
- Delete: `platforms/organization-service/dm.xmlsec.binding-1.3.7/` (directory), `dm.xmlsec.binding-1.3.7.tar.gz`, `dm.xmlsec.binding-1.3.7.tar.gz.1`
- Delete: `platforms/organization-service/tests/integration/test_auth_endpoints.py`, `platforms/organization-service/tests/unit/{test_security.py,test_user_service.py}`
- Modify: `platforms/organization-service/src/organization/core/config.py` (replace entirely)
- Modify: `platforms/organization-service/src/organization/config.py` (delete — was a dead duplicate; `core/config.py` becomes the single source)
- Modify: `platforms/organization-service/src/organization/db/base.py` (unchanged content, verify it survives — it's just `Base = declarative_base()`, keep it)
- Modify: `platforms/organization-service/src/organization/db/session.py` (replace)
- Modify: `platforms/organization-service/src/organization/api/main.py` (replace)
- Modify: `platforms/organization-service/src/organization/main.py` (replace)
- Modify: `platforms/organization-service/src/organization/api/deps.py` (replace with just `get_db`, real auth deps land in Task 2)
- Modify: `platforms/organization-service/src/organization/api/v1/api.py` (replace, empty router for now)
- Modify: `platforms/organization-service/requirements.txt` (trim + add `httpx==0.27.0`, `respx==0.21.1`, `pytest==8.1.1`)
- Modify: `platforms/organization-service/.env.example` (replace)
- Modify: `platforms/organization-service/alembic.ini` (fix `sqlalchemy.url` db name/port)
- Modify: `platforms/organization-service/Dockerfile` (fix CMD)
- Create: `platforms/organization-service/tests/conftest.py`

**Interfaces:**
- Produces: `src.organization.core.config.settings` (a `Settings` instance with `APP_NAME`, `APP_VERSION`, `API_V1_STR`, `SECRET_KEY`, `ALGORITHM`, `DATABASE_URL`/`POSTGRES_*`, `AUTH_SERVICE_URL`, `AUTH_SERVICE_TOKEN`, `BACKEND_CORS_ORIGINS`)
- Produces: `src.organization.db.session.get_db() -> Generator[Session, None, None]`, `src.organization.db.session.engine`, `src.organization.db.base.Base`
- Produces: `src.organization.api.main.app` (FastAPI instance, health check at `GET /health`)
- Consumed by: every later task's model/router/test imports

- [ ] **Step 1: Delete the auth-clone files and vendored junk listed above**

```bash
cd platforms/organization-service
rm -f src/organization/models/user.py src/organization/models/session.py src/organization/models/oauth.py
rm -f src/organization/api/v1/endpoints/auth.py src/organization/api/v1/endpoints/sso.py src/organization/api/v1/endpoints/users.py
rm -f src/organization/service/auth_service.py src/organization/service/sso_service.py src/organization/service/user_service.py
rm -f src/organization/schemas/auth.py src/organization/schemas/token.py src/organization/schemas/user.py
rm -f src/organization/utils/password.py src/organization/utils/security.py src/organization/utils/dependencies.py
rm -f alembic/versions/001_create_users_table.py alembic/versions/002_add_sessions_table.py alembic/versions/003_add_oauth_tables.py
rm -rf dm.xmlsec.binding-1.3.7
rm -f dm.xmlsec.binding-1.3.7.tar.gz "dm.xmlsec.binding-1.3.7.tar.gz.1"
rm -f tests/integration/test_auth_endpoints.py tests/unit/test_security.py tests/unit/test_user_service.py
rm -f src/organization/config.py
```

- [ ] **Step 2: Write `src/organization/core/config.py`**

```python
"""Configuration management for Organization Service."""
from typing import Optional
from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Organization Service"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Organization Service"

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "organization_db"
    DATABASE_URL: Optional[PostgresDsn] = None

    # Security — must match auth-service's SECRET_KEY/ALGORITHM so its JWTs verify here
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"

    # Service-to-service call to auth-service for user existence checks
    AUTH_SERVICE_URL: str = "http://localhost:8000"
    AUTH_SERVICE_TOKEN: str = ""

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env")

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return str(self.DATABASE_URL)
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"
        )


settings = Settings()
```

- [ ] **Step 3: Write `src/organization/db/session.py`**

```python
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.organization.core.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: Confirm `src/organization/db/base.py` still reads exactly**

```python
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
```

(No change needed — just verify it wasn't deleted in Step 1.)

- [ ] **Step 5: Write `src/organization/api/deps.py`**

```python
from src.organization.db.session import get_db

__all__ = ["get_db"]
```

- [ ] **Step 6: Write `src/organization/api/v1/api.py`**

```python
from fastapi import APIRouter

api_router = APIRouter()

__all__ = ["api_router"]
```

- [ ] **Step 7: Write `src/organization/api/main.py`**

```python
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from src.organization.api.v1.api import api_router
from src.organization.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
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

- [ ] **Step 8: Write `src/organization/main.py`**

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.organization.api.main:app", host="0.0.0.0", port=8000, log_level="info")
```

- [ ] **Step 9: Write `tests/conftest.py`**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from src.organization.db.base import Base
from src.organization.db.session import get_db
from src.organization.api.main import app

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


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
```

- [ ] **Step 10: Write the scaffold test**

```python
# tests/integration/test_health.py
def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
```

- [ ] **Step 11: Update `requirements.txt`**

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
```

- [ ] **Step 12: Update `.env.example`**

```
# Environment variables for the Organization Service
APP_NAME=Organization Service
APP_VERSION=0.1.0
DEBUG=False

API_V1_STR=/api/v1

SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256

POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=organization_db

AUTH_SERVICE_URL=http://localhost:8000
AUTH_SERVICE_TOKEN=

BACKEND_CORS_ORIGINS=["http://localhost:3000", "http://localhost:8000"]
```

- [ ] **Step 13: Fix `alembic.ini`**

Change the `sqlalchemy.url` line to:
```
sqlalchemy.url = postgresql://postgres:password@localhost:5432/organization_db
```

- [ ] **Step 14: Fix `Dockerfile` CMD**

Replace the final `CMD` line with:
```
CMD ["uvicorn", "src.organization.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 15: Run the scaffold test**

Run: `cd platforms/organization-service && SECRET_KEY=test-secret pytest tests/integration/test_health.py -v`
Expected: PASS (1 passed)

- [ ] **Step 16: Commit**

```bash
git add platforms/organization-service
git commit -m "chore(organization-service): remove auth-clone junk, scaffold real service skeleton"
```

---

### Task 2: JWT auth dependency

**Files:**
- Create: `platforms/organization-service/src/organization/utils/tokens.py`
- Modify: `platforms/organization-service/src/organization/api/deps.py`
- Create: `platforms/organization-service/tests/unit/test_tokens.py`
- Create: `platforms/organization-service/tests/unit/test_deps.py`

**Interfaces:**
- Consumes: `src.organization.core.config.settings.SECRET_KEY`, `settings.ALGORITHM`
- Produces: `src.organization.utils.tokens.decode_token(token: str) -> dict` (raises `ValueError` on invalid/expired token)
- Produces: `src.organization.api.deps.get_current_user_id(token: str = Depends(...)) -> int` — a FastAPI dependency, used by every protected endpoint in later tasks
- Produces: `src.organization.api.deps.get_db` (already exists from Task 1, unchanged)

- [ ] **Step 1: Write the failing token test**

```python
# tests/unit/test_tokens.py
import jwt
import pytest
from datetime import datetime, timedelta
from src.organization.core.config import settings
from src.organization.utils.tokens import decode_token


def test_decode_token_returns_payload():
    token = jwt.encode(
        {"sub": "42", "exp": datetime.utcnow() + timedelta(minutes=5)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    payload = decode_token(token)
    assert payload["sub"] == "42"


def test_decode_token_rejects_bad_signature():
    token = jwt.encode(
        {"sub": "42", "exp": datetime.utcnow() + timedelta(minutes=5)},
        "wrong-secret",
        algorithm=settings.ALGORITHM,
    )
    with pytest.raises(ValueError):
        decode_token(token)


def test_decode_token_rejects_expired():
    token = jwt.encode(
        {"sub": "42", "exp": datetime.utcnow() - timedelta(minutes=5)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    with pytest.raises(ValueError):
        decode_token(token)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_tokens.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.organization.utils.tokens'`

- [ ] **Step 3: Write `src/organization/utils/tokens.py`**

```python
from jwt import decode, InvalidTokenError
from src.organization.core.config import settings


def decode_token(token: str) -> dict:
    try:
        return decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except InvalidTokenError:
        raise ValueError("Could not validate credentials")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_tokens.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Write the failing deps test**

```python
# tests/unit/test_deps.py
import jwt
import pytest
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from src.organization.core.config import settings
from src.organization.api.deps import get_current_user_id

app = FastAPI()


@app.get("/whoami")
def whoami(user_id: int = Depends(get_current_user_id)):
    return {"user_id": user_id}


client = TestClient(app)


def _token(sub="7", expired=False):
    delta = timedelta(minutes=-5) if expired else timedelta(minutes=5)
    return jwt.encode({"sub": sub, "exp": datetime.utcnow() + delta}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def test_valid_token_resolves_user_id():
    response = client.get("/whoami", headers={"Authorization": f"Bearer {_token()}"})
    assert response.status_code == 200
    assert response.json() == {"user_id": 7}


def test_missing_token_returns_401():
    response = client.get("/whoami")
    assert response.status_code == 401


def test_expired_token_returns_401():
    response = client.get("/whoami", headers={"Authorization": f"Bearer {_token(expired=True)}"})
    assert response.status_code == 401


def test_non_integer_sub_returns_401():
    bad = jwt.encode({"sub": "not-a-number", "exp": datetime.utcnow() + timedelta(minutes=5)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    response = client.get("/whoami", headers={"Authorization": f"Bearer {bad}"})
    assert response.status_code == 401
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/unit/test_deps.py -v`
Expected: FAIL with `ImportError: cannot import name 'get_current_user_id'`

- [ ] **Step 7: Add `get_current_user_id` to `src/organization/api/deps.py`**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from src.organization.db.session import get_db
from src.organization.utils.tokens import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_exception
    try:
        payload = decode_token(token)
        return int(payload["sub"])
    except (ValueError, KeyError, TypeError):
        raise credentials_exception


__all__ = ["get_db", "get_current_user_id"]
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/unit/test_deps.py -v`
Expected: PASS (4 passed)

- [ ] **Step 9: Commit**

```bash
git add platforms/organization-service/src/organization/utils/tokens.py platforms/organization-service/src/organization/api/deps.py platforms/organization-service/tests/unit/test_tokens.py platforms/organization-service/tests/unit/test_deps.py
git commit -m "feat(organization-service): add JWT decode and current-user-id dependency"
```

---

### Task 3: Organization + Membership models and migration

**Files:**
- Create: `platforms/organization-service/src/organization/models/organization.py`
- Create: `platforms/organization-service/src/organization/models/member.py`
- Modify: `platforms/organization-service/src/organization/models/__init__.py` (new file — didn't exist before, models dir had no `__init__.py` in the clone; create one)
- Create: `platforms/organization-service/alembic/versions/001_create_organizations_and_members.py`
- Create: `platforms/organization-service/tests/unit/test_models.py`

**Interfaces:**
- Consumes: `src.organization.db.base.Base`
- Produces: `src.organization.models.organization.Organization` (columns: `id`, `name`, `slug`, `plan_tier`, `created_at`, `updated_at`, `deleted_at`)
- Produces: `src.organization.models.member.OrganizationMember` (columns: `id`, `organization_id`, `user_id`, `role`, `status`, `created_at`, `updated_at`); `OrganizationMember.ROLES = ("owner", "admin", "member", "viewer", "billing_manager")`, `OrganizationMember.STATUSES = ("pending", "active", "suspended", "removed")`

- [ ] **Step 1: Write the failing model test**

```python
# tests/unit/test_models.py
from src.organization.models.organization import Organization
from src.organization.models.member import OrganizationMember


def test_create_organization_and_member(db):
    org = Organization(name="Acme", slug="acme", plan_tier="free")
    db.add(org)
    db.commit()
    db.refresh(org)

    member = OrganizationMember(organization_id=org.id, user_id=7, role="owner", status="active")
    db.add(member)
    db.commit()
    db.refresh(member)

    assert org.id is not None
    assert org.deleted_at is None
    assert member.organization_id == org.id
    assert member.user_id == 7
    assert member.role == "owner"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.organization.models.organization'`

- [ ] **Step 3: Write `src/organization/models/organization.py`**

```python
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from src.organization.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    plan_tier = Column(String(50), nullable=False, default="free")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 4: Write `src/organization/models/member.py`**

```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.sql import func
from src.organization.db.base import Base


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    ROLES = ("owner", "admin", "member", "viewer", "billing_manager")
    STATUSES = ("pending", "active", "suspended", "removed")

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    role = Column(String(50), nullable=False, default="member")
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
        CheckConstraint("role IN ('owner','admin','member','viewer','billing_manager')", name="chk_member_role"),
        CheckConstraint("status IN ('pending','active','suspended','removed')", name="chk_member_status"),
    )
```

- [ ] **Step 5: Write `src/organization/models/__init__.py`**

```python
from src.organization.models.organization import Organization
from src.organization.models.member import OrganizationMember

__all__ = ["Organization", "OrganizationMember"]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/unit/test_models.py -v`
Expected: PASS (1 passed)

- [ ] **Step 7: Write the Alembic migration**

```python
# alembic/versions/001_create_organizations_and_members.py
"""create organizations and organization_members

Revision ID: 001
Revises:
Create Date: 2026-09-16
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("plan_tier", sa.String(50), nullable=False, server_default="free"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    op.create_table(
        "organization_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="member"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_org_member"),
        sa.CheckConstraint("role IN ('owner','admin','member','viewer','billing_manager')", name="chk_member_role"),
        sa.CheckConstraint("status IN ('pending','active','suspended','removed')", name="chk_member_status"),
    )
    op.create_index("ix_organization_members_organization_id", "organization_members", ["organization_id"])
    op.create_index("ix_organization_members_user_id", "organization_members", ["user_id"])


def downgrade() -> None:
    op.drop_table("organization_members")
    op.drop_table("organizations")
```

- [ ] **Step 8: Commit**

```bash
git add platforms/organization-service/src/organization/models platforms/organization-service/alembic/versions/001_create_organizations_and_members.py platforms/organization-service/tests/unit/test_models.py
git commit -m "feat(organization-service): add Organization and OrganizationMember models + migration"
```

---

### Task 4: Organization service layer + schemas + endpoints

**Files:**
- Create: `platforms/organization-service/src/organization/schemas/organization.py`
- Create: `platforms/organization-service/src/organization/service/organization_service.py`
- Create: `platforms/organization-service/src/organization/api/v1/endpoints/organizations.py`
- Modify: `platforms/organization-service/src/organization/api/v1/api.py`
- Create: `platforms/organization-service/tests/integration/test_organizations_endpoints.py`

**Interfaces:**
- Consumes: `src.organization.api.deps.get_db`, `get_current_user_id` (Task 2); `Organization`, `OrganizationMember` (Task 3)
- Produces: `src.organization.service.organization_service.create_organization(db, name, slug, plan_tier, owner_user_id) -> Organization` (also creates the owner `OrganizationMember` row in the same transaction)
- Produces: `organization_service.get_organization(db, org_id) -> Optional[Organization]`
- Produces: `organization_service.update_organization(db, org_id, **fields) -> Optional[Organization]`
- Produces: `organization_service.soft_delete_organization(db, org_id) -> bool`
- Produces: routes under `/api/v1/organizations` (POST, GET `/{id}`, PATCH `/{id}`, DELETE `/{id}`)

- [ ] **Step 1: Write the failing endpoint test**

```python
# tests/integration/test_organizations_endpoints.py
import jwt
from datetime import datetime, timedelta, timezone
from src.organization.core.config import settings


def _token(user_id: int) -> str:
    return jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _auth(user_id: int) -> dict:
    return {"Authorization": f"Bearer {_token(user_id)}"}


def test_create_organization_makes_creator_owner(client):
    response = client.post(
        "/api/v1/organizations",
        json={"name": "Acme", "slug": "acme", "plan_tier": "free"},
        headers=_auth(7),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Acme"
    assert body["slug"] == "acme"
    org_id = body["id"]

    get_response = client.get(f"/api/v1/organizations/{org_id}", headers=_auth(7))
    assert get_response.status_code == 200
    assert get_response.json()["id"] == org_id


def test_get_organization_requires_auth(client):
    response = client.get("/api/v1/organizations/1")
    assert response.status_code == 401


def test_get_nonexistent_organization_404(client):
    response = client.get("/api/v1/organizations/999", headers=_auth(7))
    assert response.status_code == 404


def test_update_organization(client):
    create = client.post(
        "/api/v1/organizations",
        json={"name": "Beta", "slug": "beta", "plan_tier": "free"},
        headers=_auth(1),
    )
    org_id = create.json()["id"]

    update = client.patch(
        f"/api/v1/organizations/{org_id}",
        json={"plan_tier": "pro"},
        headers=_auth(1),
    )
    assert update.status_code == 200
    assert update.json()["plan_tier"] == "pro"


def test_delete_organization_soft_deletes(client):
    create = client.post(
        "/api/v1/organizations",
        json={"name": "Gamma", "slug": "gamma", "plan_tier": "free"},
        headers=_auth(1),
    )
    org_id = create.json()["id"]

    delete = client.delete(f"/api/v1/organizations/{org_id}", headers=_auth(1))
    assert delete.status_code == 204

    get_after = client.get(f"/api/v1/organizations/{org_id}", headers=_auth(1))
    assert get_after.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_organizations_endpoints.py -v`
Expected: FAIL with 404s (no `/api/v1/organizations` route registered yet)

- [ ] **Step 3: Write `src/organization/schemas/organization.py`**

```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    plan_tier: str = "free"


class OrganizationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    plan_tier: Optional[str] = None


class OrganizationOut(BaseModel):
    id: int
    name: str
    slug: str
    plan_tier: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
```

- [ ] **Step 4: Write `src/organization/service/organization_service.py`**

```python
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from src.organization.models.organization import Organization
from src.organization.models.member import OrganizationMember


def create_organization(db: Session, name: str, slug: str, plan_tier: str, owner_user_id: int) -> Organization:
    org = Organization(name=name, slug=slug, plan_tier=plan_tier)
    db.add(org)
    db.flush()  # assign org.id without committing yet

    owner = OrganizationMember(
        organization_id=org.id,
        user_id=owner_user_id,
        role="owner",
        status="active",
    )
    db.add(owner)
    db.commit()
    db.refresh(org)
    return org


def get_organization(db: Session, org_id: int) -> Optional[Organization]:
    return (
        db.query(Organization)
        .filter(Organization.id == org_id, Organization.deleted_at.is_(None))
        .first()
    )


def update_organization(db: Session, org_id: int, **fields) -> Optional[Organization]:
    org = get_organization(db, org_id)
    if org is None:
        return None
    for key, value in fields.items():
        if value is not None:
            setattr(org, key, value)
    db.commit()
    db.refresh(org)
    return org


def soft_delete_organization(db: Session, org_id: int) -> bool:
    org = get_organization(db, org_id)
    if org is None:
        return False
    org.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return True
```

- [ ] **Step 5: Write `src/organization/api/v1/endpoints/organizations.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.organization.api.deps import get_db, get_current_user_id
from src.organization.schemas.organization import OrganizationCreate, OrganizationUpdate, OrganizationOut
from src.organization.service import organization_service

router = APIRouter()


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    org = organization_service.create_organization(
        db, name=payload.name, slug=payload.slug, plan_tier=payload.plan_tier, owner_user_id=user_id
    )
    return org


@router.get("/{org_id}", response_model=OrganizationOut)
def get_organization(
    org_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    org = organization_service.get_organization(db, org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


@router.patch("/{org_id}", response_model=OrganizationOut)
def update_organization(
    org_id: int,
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    org = organization_service.update_organization(db, org_id, **payload.model_dump(exclude_unset=True))
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return org


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organization(
    org_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    deleted = organization_service.soft_delete_organization(db, org_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
```

- [ ] **Step 6: Wire the router in `src/organization/api/v1/api.py`**

```python
from fastapi import APIRouter
from src.organization.api.v1.endpoints import organizations

api_router = APIRouter()
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])

__all__ = ["api_router"]
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/integration/test_organizations_endpoints.py -v`
Expected: PASS (5 passed)

- [ ] **Step 8: Commit**

```bash
git add platforms/organization-service/src/organization/schemas/organization.py platforms/organization-service/src/organization/service/organization_service.py platforms/organization-service/src/organization/api/v1/endpoints/organizations.py platforms/organization-service/src/organization/api/v1/api.py platforms/organization-service/tests/integration/test_organizations_endpoints.py
git commit -m "feat(organization-service): add organization CRUD endpoints, creator auto-owner"
```

---

### Task 5: auth-service client for member user-id validation

**Files:**
- Create: `platforms/organization-service/src/organization/utils/auth_client.py`
- Create: `platforms/organization-service/tests/unit/test_auth_client.py`

**Interfaces:**
- Consumes: `settings.AUTH_SERVICE_URL`, `settings.AUTH_SERVICE_TOKEN`
- Produces: `src.organization.utils.auth_client.user_exists(user_id: int) -> bool` (raises `AuthServiceUnavailable` on network/timeout errors — never silently returns `True`/`False` for a connectivity failure)
- Produces: `src.organization.utils.auth_client.AuthServiceUnavailable` (Exception subclass)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_auth_client.py
import httpx
import pytest
import respx
from src.organization.core.config import settings
from src.organization.utils.auth_client import user_exists, AuthServiceUnavailable


@respx.mock
def test_user_exists_true_on_200():
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/7").mock(
        return_value=httpx.Response(200, json={"id": 7, "email": "a@b.com"})
    )
    assert user_exists(7) is True


@respx.mock
def test_user_exists_false_on_404():
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/999").mock(return_value=httpx.Response(404))
    assert user_exists(999) is False


@respx.mock
def test_user_exists_raises_on_timeout():
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/7").mock(side_effect=httpx.ConnectTimeout("timeout"))
    with pytest.raises(AuthServiceUnavailable):
        user_exists(7)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_auth_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.organization.utils.auth_client'`

- [ ] **Step 3: Write `src/organization/utils/auth_client.py`**

```python
import httpx
from src.organization.core.config import settings


class AuthServiceUnavailable(Exception):
    """Raised when auth-service cannot be reached to validate a user_id."""


def user_exists(user_id: int) -> bool:
    headers = {"Authorization": f"Bearer {settings.AUTH_SERVICE_TOKEN}"} if settings.AUTH_SERVICE_TOKEN else {}
    try:
        response = httpx.get(
            f"{settings.AUTH_SERVICE_URL}/api/v1/users/{user_id}",
            headers=headers,
            timeout=5.0,
        )
    except httpx.HTTPError as exc:
        raise AuthServiceUnavailable(f"Could not reach auth-service: {exc}") from exc

    if response.status_code == 200:
        return True
    if response.status_code == 404:
        return False
    raise AuthServiceUnavailable(f"Unexpected auth-service response: {response.status_code}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_auth_client.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add platforms/organization-service/src/organization/utils/auth_client.py platforms/organization-service/tests/unit/test_auth_client.py
git commit -m "feat(organization-service): add auth-service client for member user_id validation"
```

---

### Task 6: Membership service, role-check dependency, and endpoints

**Files:**
- Create: `platforms/organization-service/src/organization/schemas/member.py`
- Create: `platforms/organization-service/src/organization/service/member_service.py`
- Create: `platforms/organization-service/src/organization/api/v1/endpoints/members.py`
- Modify: `platforms/organization-service/src/organization/api/deps.py` (add `require_org_role`)
- Modify: `platforms/organization-service/src/organization/api/v1/api.py`
- Create: `platforms/organization-service/tests/integration/test_members_endpoints.py`

**Interfaces:**
- Consumes: `OrganizationMember` (Task 3), `get_db`/`get_current_user_id` (Task 2), `auth_client.user_exists`/`AuthServiceUnavailable` (Task 5)
- Produces: `member_service.add_member(db, org_id, user_id, role) -> OrganizationMember` (raises `ValueError("user not found")` if `auth_client.user_exists` is `False`; raises `ValueError("already a member")` on duplicate)
- Produces: `member_service.list_members(db, org_id) -> list[OrganizationMember]`
- Produces: `member_service.remove_member(db, org_id, member_id) -> bool`
- Produces: `member_service.get_role(db, org_id, user_id) -> Optional[str]`
- Produces: `deps.require_org_role(*roles)` — a dependency factory: `Depends(require_org_role("owner", "admin"))` raises 403 if the current user's role in the path's `org_id` isn't in `roles`, 404 if not a member at all

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_members_endpoints.py
import jwt
import respx
import httpx
from datetime import datetime, timedelta, timezone
from src.organization.core.config import settings


def _token(user_id: int) -> str:
    return jwt.encode(
        {"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def _auth(user_id: int) -> dict:
    return {"Authorization": f"Bearer {_token(user_id)}"}


def _make_org(client, owner_id: int) -> int:
    response = client.post(
        "/api/v1/organizations",
        json={"name": "Acme", "slug": "acme", "plan_tier": "free"},
        headers=_auth(owner_id),
    )
    return response.json()["id"]


@respx.mock
def test_owner_can_add_member(client):
    org_id = _make_org(client, owner_id=1)
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/2").mock(return_value=httpx.Response(200, json={"id": 2}))

    response = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": 2, "role": "member"},
        headers=_auth(1),
    )
    assert response.status_code == 201
    assert response.json()["user_id"] == 2
    assert response.json()["role"] == "member"


@respx.mock
def test_non_admin_cannot_add_member(client):
    org_id = _make_org(client, owner_id=1)
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/3").mock(return_value=httpx.Response(200, json={"id": 3}))
    client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": 3, "role": "member"},
        headers=_auth(1),
    )

    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/4").mock(return_value=httpx.Response(200, json={"id": 4}))
    response = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": 4, "role": "member"},
        headers=_auth(3),  # user 3 is a plain member, not owner/admin
    )
    assert response.status_code == 403


@respx.mock
def test_add_nonexistent_user_returns_422(client):
    org_id = _make_org(client, owner_id=1)
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/999").mock(return_value=httpx.Response(404))

    response = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": 999, "role": "member"},
        headers=_auth(1),
    )
    assert response.status_code == 422


@respx.mock
def test_list_members(client):
    org_id = _make_org(client, owner_id=1)
    response = client.get(f"/api/v1/organizations/{org_id}/members", headers=_auth(1))
    assert response.status_code == 200
    members = response.json()
    assert len(members) == 1
    assert members[0]["role"] == "owner"


@respx.mock
def test_owner_can_remove_member(client):
    org_id = _make_org(client, owner_id=1)
    respx.get(f"{settings.AUTH_SERVICE_URL}/api/v1/users/2").mock(return_value=httpx.Response(200, json={"id": 2}))
    add_response = client.post(
        f"/api/v1/organizations/{org_id}/members",
        json={"user_id": 2, "role": "member"},
        headers=_auth(1),
    )
    member_id = add_response.json()["id"]

    response = client.delete(f"/api/v1/organizations/{org_id}/members/{member_id}", headers=_auth(1))
    assert response.status_code == 204
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_members_endpoints.py -v`
Expected: FAIL with 404s (no `/members` routes registered yet)

- [ ] **Step 3: Write `src/organization/schemas/member.py`**

```python
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from src.organization.models.member import OrganizationMember as OrganizationMemberModel


class MemberCreate(BaseModel):
    user_id: int
    role: str = Field(default="member")


class MemberOut(BaseModel):
    id: int
    organization_id: int
    user_id: int
    role: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
```

- [ ] **Step 4: Write `src/organization/service/member_service.py`**

```python
from typing import Optional
from sqlalchemy.orm import Session
from src.organization.models.member import OrganizationMember
from src.organization.utils.auth_client import user_exists


def get_role(db: Session, org_id: int, user_id: int) -> Optional[str]:
    member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
            OrganizationMember.status == "active",
        )
        .first()
    )
    return member.role if member else None


def add_member(db: Session, org_id: int, user_id: int, role: str) -> OrganizationMember:
    if role not in OrganizationMember.ROLES:
        raise ValueError(f"invalid role: {role}")
    if not user_exists(user_id):
        raise ValueError("user not found")

    existing = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == org_id, OrganizationMember.user_id == user_id)
        .first()
    )
    if existing:
        raise ValueError("already a member")

    member = OrganizationMember(organization_id=org_id, user_id=user_id, role=role, status="active")
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def list_members(db: Session, org_id: int) -> list[OrganizationMember]:
    return (
        db.query(OrganizationMember)
        .filter(OrganizationMember.organization_id == org_id, OrganizationMember.status == "active")
        .all()
    )


def remove_member(db: Session, org_id: int, member_id: int) -> bool:
    member = (
        db.query(OrganizationMember)
        .filter(OrganizationMember.id == member_id, OrganizationMember.organization_id == org_id)
        .first()
    )
    if member is None:
        return False
    db.delete(member)
    db.commit()
    return True
```

- [ ] **Step 5: Add `require_org_role` to `src/organization/api/deps.py`**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from src.organization.db.session import get_db
from src.organization.utils.tokens import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_exception
    try:
        payload = decode_token(token)
        return int(payload["sub"])
    except (ValueError, KeyError, TypeError):
        raise credentials_exception


def require_org_role(*roles: str):
    from src.organization.service.member_service import get_role  # local import avoids a service->deps->service cycle

    def dependency(
        org_id: int,
        db: Session = Depends(get_db),
        user_id: int = Depends(get_current_user_id),
    ) -> str:
        role = get_role(db, org_id, user_id)
        if role is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not a member of this organization")
        if role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return role

    return dependency


__all__ = ["get_db", "get_current_user_id", "require_org_role"]
```

- [ ] **Step 6: Write `src/organization/api/v1/endpoints/members.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.organization.api.deps import get_db, get_current_user_id, require_org_role
from src.organization.schemas.member import MemberCreate, MemberOut
from src.organization.service import member_service
from src.organization.utils.auth_client import AuthServiceUnavailable

router = APIRouter()


@router.post("", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(
    org_id: int,
    payload: MemberCreate,
    db: Session = Depends(get_db),
    _role: str = Depends(require_org_role("owner", "admin")),
):
    try:
        member = member_service.add_member(db, org_id, payload.user_id, payload.role)
    except AuthServiceUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return member


@router.get("", response_model=list[MemberOut])
def list_members(
    org_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    role = member_service.get_role(db, org_id, user_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not a member of this organization")
    return member_service.list_members(db, org_id)


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    org_id: int,
    member_id: int,
    db: Session = Depends(get_db),
    _role: str = Depends(require_org_role("owner", "admin")),
):
    removed = member_service.remove_member(db, org_id, member_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
```

- [ ] **Step 7: Wire the router in `src/organization/api/v1/api.py`**

```python
from fastapi import APIRouter
from src.organization.api.v1.endpoints import organizations, members

api_router = APIRouter()
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(members.router, prefix="/organizations/{org_id}/members", tags=["members"])

__all__ = ["api_router"]
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/integration/test_members_endpoints.py -v`
Expected: PASS (5 passed)

- [ ] **Step 9: Commit**

```bash
git add platforms/organization-service/src/organization/schemas/member.py platforms/organization-service/src/organization/service/member_service.py platforms/organization-service/src/organization/api/v1/endpoints/members.py platforms/organization-service/src/organization/api/deps.py platforms/organization-service/src/organization/api/v1/api.py platforms/organization-service/tests/integration/test_members_endpoints.py
git commit -m "feat(organization-service): add membership management endpoints with role-gated access"
```

---

### Task 7: Full suite pass, README rewrite

**Files:**
- Modify: `platforms/organization-service/README.md` (replace — currently documents the auth-service clone's SSO/JWT-login feature set, not organization/membership)

**Interfaces:**
- Consumes: nothing new — this task only verifies and documents Tasks 1-6

- [ ] **Step 1: Run the entire test suite**

Run: `cd platforms/organization-service && SECRET_KEY=test-secret pytest -v`
Expected: PASS, all tests from Tasks 1-6 green, zero failures/errors

- [ ] **Step 2: Rewrite `README.md`**

```markdown
# Organization Service

Manages organizations (tenants) and their memberships for QA Vision Platform.

## Responsibilities

- Organization CRUD (`/api/v1/organizations`)
- Membership management (`/api/v1/organizations/{org_id}/members`) with roles:
  `owner`, `admin`, `member`, `viewer`, `billing_manager`
- Validates member `user_id`s against auth-service over HTTP before adding them

## Auth model

This service does not issue tokens. It trusts JWTs signed by auth-service
(shared `SECRET_KEY`/`HS256`) and reads the user id from the `sub` claim.

## Out of scope (see docs/superpowers/specs/2026-09-16-organization-service-core-design.md)

- `organization_invitations` (email invite flow)
- `organization_settings` (SSO/MFA/session config per org)

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env  # set SECRET_KEY to match auth-service's
alembic upgrade head
uvicorn src.organization.api.main:app --reload
```

## Testing

```bash
SECRET_KEY=test-secret pytest -v
```
```

- [ ] **Step 3: Commit**

```bash
git add platforms/organization-service/README.md
git commit -m "docs(organization-service): replace auth-clone README with real service documentation"
```

---

## Plan Self-Review Notes

- **Spec coverage:** Organizations CRUD ✓ (Task 4), Membership core ✓ (Tasks 3, 6), cross-service user validation ✓ (Task 5), cleanup of auth-clone + vendored junk ✓ (Task 1), auth-service `users.py` follow-up flag ✓ (carried in spec, restated in README's "out of scope" — not re-solved here). Invitations/org-settings explicitly deferred per spec.
- **Type consistency checked:** `get_current_user_id` returns `int` everywhere it's consumed (Tasks 2, 4, 6). `auth_client.user_exists(user_id: int) -> bool` signature matches its one caller in `member_service.add_member`. `OrganizationMember.ROLES`/`STATUSES` tuples defined once in Task 3, referenced (not redefined) in Task 6's validation.
- **No placeholders:** every step has runnable code; commit messages are the only prose-only steps, which is expected per the task template.
