# Shared Package Extraction — Design

**Scope:** new `shared/` package at the repository root, retrofitted into
`platforms/auth-service/auth-service` and `platforms/organization-service`.
**Status:** approved for planning

## Problem

auth-service and organization-service have each independently reimplemented the same
service boilerplate. The roadmap's Phase 1 calls for project-service, api-gateway and
monitoring-service next, so without a shared home the third, fourth and fifth copies are
already scheduled.

The duplication is small in line count but has already produced real divergence:

| | auth-service | organization-service |
|---|---|---|
| `database_url` return type | `PostgresDsn` | `str` |
| DSN construction | `PostgresDsn.build(...)` — raises on `:` or `/` in the password instead of escaping it | f-string — **does not** encode |
| `SECRET_KEY` | required, no default | defaults to the literal `"your-secret-key-here"` |
| `db/base.py` | `Base = declarative_base()` | byte-identical |
| `db/session.py` | engine + sessionmaker + `get_db` generator | near-identical |

Three of those rows are defects, not merely inconsistencies:

1. **Neither service can handle a password containing `@`, `/` or `:`.**
   organization-service's f-string produces a malformed URL, and auth-service's
   `PostgresDsn.build` does no better: it raises `ValidationError: invalid port number`
   on the same password instead of escaping it.
2. **The return types are incompatible in a way that is one copy-paste from breaking.**
   `organization/alembic/env.py` line 28 calls `settings.database_url.replace("%", "%%")`
   — a `str` method. Run that same line against auth's `PostgresDsn` and it raises
   `AttributeError`. The two services' alembic setups are not interchangeable today, and
   nothing signals that.
3. **organization-service starts successfully on a publicly-known secret.** auth-service
   deliberately has no default so a missing `SECRET_KEY` stops startup.

## Design

### Package shape

```
shared/
  pyproject.toml            # name = "qav-shared", setuptools backend
  qav_shared/
    __init__.py
    config.py               # BaseServiceSettings
    db.py                   # make_session_factory, make_get_db
  tests/
    test_config.py
    test_db.py
```

Distribution name `qav-shared`, import name `qav_shared`. `requires-python = ">=3.11"`
(both service venvs are 3.11.9). Dependencies are declared as lower bounds —
`pydantic>=2.7`, `pydantic-settings>=2.2`, `sqlalchemy>=2.0` — matching what both services
already pin exactly (`pydantic[email]==2.7.0`, `pydantic-settings==2.2.1`,
`SQLAlchemy==2.0.29`). Lower bounds here, exact pins in each service's `requirements.txt`:
the shared package states what it needs to work, the services state what they were tested
against.

### Consumption mechanism

Each service adds one line to `requirements.txt`:

```
-e ../../../shared      # auth-service (platforms/auth-service/auth-service/)
-e ../../shared         # organization-service (platforms/organization-service/)
```

For that relative path to resolve identically inside a container, each Dockerfile mirrors
the repository layout rather than flattening the service into `/app`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY shared/ ./shared/
COPY platforms/auth-service/auth-service/requirements.txt ./platforms/auth-service/auth-service/
WORKDIR /app/platforms/auth-service/auth-service
RUN pip install --no-cache-dir -r requirements.txt     # -e ../../../shared -> /app/shared
COPY platforms/auth-service/auth-service/src/ ./src/
# then each service's remaining artifacts, unchanged from today apart from the path
# prefix: organization-service also copies alembic/ and alembic.ini; both keep their
# existing CMD.
```

The build context moves to the repository root, so each `docker-compose.yml` changes from
`build: .` to:

```yaml
    build:
      context: ../../..
      dockerfile: platforms/auth-service/auth-service/Dockerfile
```

This keeps `requirements.txt` the single source of truth for what gets installed. The
rejected alternative — omitting `shared` from requirements and adding a separate
`RUN pip install -e ./shared` — gives two places to declare one dependency, and they drift.

The base image also moves from `python:3.9-slim` to `python:3.11-slim`. Both Dockerfiles
currently specify 3.9 while both venvs are 3.11.9; the code is developed and tested
against 3.11 and has never run on 3.9 in CI (there is no CI beyond CodeQL). Since this
work edits both Dockerfiles anyway, the mismatch is closed here rather than left as a
latent surprise for whoever first deploys a container.

### `qav_shared/config.py`

```python
from typing import Optional
from urllib.parse import quote

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """Settings every QA Vision service needs. Subclass it and add your own."""

    APP_NAME: str = "QA Vision Service"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    API_V1_STR: str = "/api/v1"

    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "postgres"
    DATABASE_URL: Optional[PostgresDsn] = None

    # No default, deliberately: a service that cannot find a secret must refuse to start
    # rather than run on a predictable one. organization-service previously defaulted this
    # to the literal "your-secret-key-here".
    SECRET_KEY: str
    ALGORITHM: str = "HS256"

    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env")

    @property
    def database_url(self) -> str:
        """Always a str.

        Every consumer either hands this to create_engine or, in alembic's env.py, calls
        a str method on it -- organization-service's env.py does
        `.replace("%", "%%")`, which raises AttributeError against a PostgresDsn object.
        auth-service returned PostgresDsn and organization-service returned str; unifying
        on str removes a trap rather than picking a favourite.

        The components path escapes user and password. Neither service's original
        components path was correct: organization-service's f-string didn't encode at
        all, and auth-service's `PostgresDsn.build` raised on a password containing `:`
        or `/` instead of escaping it. `quote(value, safe="")` is used rather than
        `quote_plus` because `quote_plus` turns a space into `+`, which a URL parser
        then decodes back as a literal `+` instead of a space -- corrupting the password.
        """
        if self.DATABASE_URL:
            return str(self.DATABASE_URL)
        user = quote(self.POSTGRES_USER, safe="")
        password = quote(self.POSTGRES_PASSWORD, safe="")
        return f"postgresql://{user}:{password}@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"
```

### `qav_shared/db.py`

```python
from typing import Callable, Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def make_session_factory(database_url: str) -> sessionmaker:
    """Engine + sessionmaker for one service's database.

    create_engine does not connect; the first connection happens on first use. That
    laziness matters: both services' conftest.py import their db.session module (for
    get_db) while pointed at a Postgres URL that does not exist in the test environment.
    """
    engine = create_engine(database_url)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def make_get_db(session_factory: sessionmaker) -> Callable[[], Generator[Session, None, None]]:
    """Build the FastAPI dependency that yields a session and always closes it."""

    def get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    return get_db
```

### What deliberately does NOT go in `shared/`

- **`Base = declarative_base()` stays per-service.** A declarative base is a mutable
  global registry of mapped classes. Sharing one instance across services would put
  separate databases' models into a single `Base.metadata`, which is how a
  `create_all()` in one service's test suite starts creating another service's tables.
  The three identical lines in each `db/base.py` are correct isolation, not duplication.
- **No logging module.** Neither service configures logging today — there is no
  `basicConfig` anywhere, only module-level `getLogger` calls. A shared logging setup
  would be new, unproven abstraction rather than consolidation.
- **No exceptions module.** Same reason: both services raise `HTTPException` inline and
  neither has a custom exception hierarchy to extract.

Both are reasonable additions later, once a second consumer demonstrates what shape they
should be. Adding them now would mean designing an interface against zero real usage.

### Per-service result

`platforms/organization-service/src/organization/db/session.py` in full:

```python
from qav_shared.db import make_get_db, make_session_factory
from src.organization.core.config import settings

SessionLocal = make_session_factory(settings.database_url)
get_db = make_get_db(SessionLocal)
```

`src/organization/core/config.py` keeps only what is organization-specific:

```python
from qav_shared.config import BaseServiceSettings


class Settings(BaseServiceSettings):
    APP_NAME: str = "Organization Service"
    PROJECT_NAME: str = "Organization Service"
    POSTGRES_DB: str = "organization_db"

    AUTH_SERVICE_URL: str = "http://localhost:8000"
    AUTH_SERVICE_TOKEN: str = ""


settings = Settings()
```

auth-service's `Settings` keeps its ~30 remaining fields (Redis, token lifetimes,
`FIRST_SUPERUSER*`, SMTP, `EMAIL_VERIFICATION_EXPIRE_HOURS`, `BASE_URL`, SSO providers)
and drops only the fields and the `database_url`/`redis_url` boilerplate the base now
provides. `redis_url` is auth-only and stays in auth-service.

## Behavioral changes, stated explicitly

1. **organization-service will refuse to start without `SECRET_KEY` in its environment.**
   Its `docker-compose.yml` and `.env.example` must set one. This is the point of the
   change, not a side effect.
2. **auth-service's `settings.database_url` changes type** from `PostgresDsn` to `str`.
   Its one consumer (`db/session.py`) already wrapped it in `str()`; that wrapper goes
   away, and the module-level `SQLALCHEMY_DATABASE_URL` constant it assigned goes with it
   — nothing imports that name (verified: the only cross-module imports from
   `db/session.py` in either service are `SessionLocal` and `get_db`).
3. **Both services' DSNs now escape user and password.** For auth-service this is
   equivalent to what `PostgresDsn.build` already did; for organization-service it is a
   fix.
4. **Container images move to Python 3.11 and a repo-root build context.** Anything that
   builds these images by `cd`-ing into the service directory and running `docker build .`
   stops working and must pass the new context.

## Testing

`shared/tests/` — its own suite, run from `shared/`:

- `database_url` returns the explicit `DATABASE_URL` when set, ignoring components.
- `database_url` builds from components when `DATABASE_URL` is absent.
- A password containing `@` and `:` is escaped such that the result parses back to the
  original password (the organization-service defect; must fail against a naive f-string).
- Omitting `SECRET_KEY` raises `pydantic.ValidationError`.
- `make_get_db` yields a session and closes it on the happy path.
- `make_get_db` closes the session when the consumer raises.

Retrofit safety net: `auth-service` 60 tests and `organization-service` 80 tests must be
green after the change, with no test edits beyond what the `SECRET_KEY` requirement forces
(their conftests construct their own SQLite engines and override `get_db`, so they do not
exercise `make_session_factory`'s runtime path — a green suite proves the wiring, not the
Postgres path, which nothing tests today either).

## Out of scope

- project-service itself. It is the next spec, and it consumes `shared/` from its first
  commit rather than being retrofitted.
- The other ~28 scaffold directories. None of them run; none get retrofitted.
- CI. There is none beyond CodeQL, and adding it is its own piece of work.
- The `SECRET_KEY=your-secret-key-here` value hard-coded in auth-service's
  `docker-compose.yml`. Making the field required does not fix a bad value that is
  explicitly supplied; secret management is a separate concern.
