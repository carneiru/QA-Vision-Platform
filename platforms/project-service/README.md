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
docker compose up -d --build
docker compose exec project-service alembic upgrade head  # first run, and after every pull that adds a migration
```

## Known limitations

- Response codes reveal whether a project id exists: a non-member gets 404 without organization-service
  being contacted, while a member gets 404/503 only after it answers. Project ids are sequential and no
  project data is exposed, so this is not treated as an information leak.
- Each request holds its database connection open while it waits on organization-service (up to 3s) and,
  when adding or re-verifying a repository, on the provider too (up to 3s more).
- Any database integrity error on project create or rename is reported as a name/slug conflict (409).

## Tests

```bash
rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q
```

Every outgoing HTTP call in the suite is mocked with `respx`; an unmocked request fails the test.
