# Test Management Service

Written test cases and suites for a project, and the link from each case to the automated test
that implements it.

- Decision: `docs/architecture/adr/ADR-022-test-management-service.md`
- Design: `docs/superpowers/specs/2026-10-06-test-management-design.md`

## Run

In the platform stack: `docker compose up -d test-management-service`. That also runs
`test-management-migrate` (`alembic upgrade head`) against `testmgmt_db`. The gateway routes
`/api/v1/projects/{id}/(cases|case-labels|suites)` here.

On its own, for the container smoke test: `SECRET_KEY=… docker compose up --build`. It answers on
port 8004, and its database is on 5437.

## Tests

```
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt   # Python 3.11
SECRET_KEY=test .venv/Scripts/python -m pytest -q
```

The integration tests use SQLite. `tests/unit/test_migration.py` runs the real migration.

## API (under `/api/v1/projects/{project_id}`)

Every project role reads. Owner, admin and member edit. A project the caller cannot see answers
404.

| Method | Path | |
|---|---|---|
| `GET` | `/cases?search=&label=&label=&status=&priority=&include_archived=&limit=&offset=` | `{total, items}`; archived hidden unless asked |
| `POST` | `/cases` | `title`, `description`, `steps[{action, expected}]`, `labels`, `priority`, `status`, `automated_test_key`, `automated_name` |
| `GET` / `PATCH` | `/cases/{number}` | the single read also lists the case's suites; `automated_test_key: null` unlinks |
| `GET` | `/case-labels` | labels in use (archived cases left out), with counts |
| `GET` / `POST` | `/suites` | name unique per project (409) |
| `GET` / `PATCH` / `DELETE` | `/suites/{id}` | detail lists the cases in order; delete keeps the cases |
| `PUT` | `/suites/{id}/cases` | `{"cases": [3, 1, 2]}` replaces the ordered list |

Limits:

- Title: 200 characters.
- Steps: 50, each up to 2 000 characters.
- Labels: 20, each matching `[A-Za-z0-9._-]{1,40}` and stored lower-case.
- Suite cases: 1 000.
