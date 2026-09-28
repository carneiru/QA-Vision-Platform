# qav-shared

Configuration and database wiring shared by QA Vision Platform services.

## What's here

- `BaseServiceSettings` — the settings every service needs: app metadata, `API_V1_STR`,
  Postgres connection components, `SECRET_KEY`/`ALGORITHM`, CORS origins, and a
  `database_url` property that always returns a `str` and escapes the user and password.
- `make_session_factory(url)` / `make_get_db(factory)` — the engine, sessionmaker and
  FastAPI dependency each service would otherwise rewrite.

## What's deliberately not here

- **`Base = declarative_base()`.** A declarative base is a mutable global registry of
  mapped classes; sharing one instance would put separate services' models into a single
  `Base.metadata`. Each service keeps its own `db/base.py`.
- **Logging and exception modules.** No service configures logging or defines a custom
  exception hierarchy today, so there is nothing to consolidate — only new abstraction to
  invent against zero real usage.

## Using it

Add to your service's `requirements.txt`, as a path relative to that file:

```
-e ../../shared
```

Then:

```python
from qav_shared.config import BaseServiceSettings
from qav_shared.db import make_get_db, make_session_factory


class Settings(BaseServiceSettings):
    APP_NAME: str = "Your Service"
    POSTGRES_DB: str = "your_db"


settings = Settings()
SessionLocal = make_session_factory(settings.database_url)
get_db = make_get_db(SessionLocal)
```

`SECRET_KEY` has no default. A service without one in its environment will not start.

## Dockerfiles

Mirror the repo layout inside the image so the relative path in `requirements.txt`
resolves there too — see either service's Dockerfile for the pattern. The build context
must be the repository root.

## Tests

The suite needs `pytest` and `psycopg2` in addition to the package's own dependencies.
The simplest way to run it is with a service venv that already has both, e.g. on Windows:

```bash
cd shared && ../platforms/organization-service/.venv/Scripts/python.exe -m pytest tests/ -v
```
