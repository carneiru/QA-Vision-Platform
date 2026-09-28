# Project Service — Design

**Date:** 2026-09-28
**Status:** Draft — awaiting review
**Scope:** A new `platforms/project-service`: test projects owned by organizations, repositories attached to projects with a public reachability check, and basic project settings. Plus one small read endpoint in `organization-service` that project-service depends on.

## Problem

The roadmap's Phase 1 order is auth → organization → **project** → API gateway, and its 30-day success metrics include "able to create organization and project" and "configure a repository". Auth and organization are built; nothing can hold a project yet. Every later phase (collector, ingestion, dashboards) attributes test results to a project.

This is also the first service built on `qav-shared` from its first commit, which tests whether that extraction pays off.

## Decisions (agreed during brainstorming)

| Question | Decision |
|---|---|
| What does "configure a repository" mean? | Record the repository and check it is reachable through the provider's public API. No credentials, no webhooks. |
| What if the check fails? | Save anyway. Record `verification_status` (`verified` / `not_found` / `unchecked`) and `verified_at`; offer a re-verify endpoint. |
| How does project-service learn a user's org role? | Ask organization-service on each request via a new `GET /organizations/{id}/members/me`, forwarding the caller's own JWT. |
| Do projects have their own members? | No. Access follows the organization role. |

## Architecture

Mirror `organization-service` exactly: FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL with its own `project_db`, JWTs issued by auth-service verified locally with the shared `SECRET_KEY` (HS256).

```
platforms/project-service/
  src/project/
    api/{main.py, deps.py, v1/api.py, v1/endpoints/{projects.py, repositories.py}}
    core/config.py            # Settings(BaseServiceSettings) + ORGANIZATION_SERVICE_URL
    db/{base.py, session.py}  # session.py uses qav_shared.db; Base stays local
    models/{project.py, repository.py}
    schemas/{project.py, repository.py, settings.py}
    service/{project_service.py, repository_service.py}
    utils/{tokens.py, org_client.py, repo_url.py, repo_verifier.py}
  alembic/
  tests/{unit, integration}/
  Dockerfile  docker-compose.yml  requirements.txt  README.md  .env.example
```

`core/config.py`:

```python
class Settings(BaseServiceSettings):
    APP_NAME: str = "Project Service"
    POSTGRES_DB: str = "project_db"
    ORGANIZATION_SERVICE_URL: str = "http://localhost:8001"
    ORGANIZATION_SERVICE_TIMEOUT_SECONDS: float = 3.0
    REPO_VERIFY_TIMEOUT_SECONDS: float = 3.0
    REPO_VERIFY_COOLDOWN_SECONDS: int = 60
```

## Data model

IDs are Integer, not the UUID in `2026-07-13-qa-vision-database-schema.md` §2, to match the real `organizations.id` (the same deviation organization-service made).

### `projects`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `organization_id` | Integer, not null, indexed | No FK: the organization lives in another service's database |
| `name` | String(255), not null | |
| `slug` | String(100), not null | Generated from `name` if not supplied: lower-case, non-alphanumerics collapsed to `-`, trimmed, max 100 |
| `description` | Text, nullable | |
| `settings` | JSON (JSONB on PostgreSQL), not null, default `{}` | Only explicitly set keys are stored; see Settings |
| `created_by` | Integer, not null | JWT `sub` of the creator |
| `created_at`, `updated_at` | timestamptz | |
| `deleted_at` | timestamptz, nullable | Soft delete |

Uniqueness among **live** projects only, as partial unique indexes (supported by both PostgreSQL and SQLite):

- `uq_project_org_name` on `(organization_id, name) WHERE deleted_at IS NULL`
- `uq_project_org_slug` on `(organization_id, slug) WHERE deleted_at IS NULL`

A deleted project's name and slug can therefore be reused.

### `repositories`

| Column | Type | Notes |
|---|---|---|
| `id` | Integer PK | |
| `project_id` | Integer FK → `projects.id`, `ON DELETE CASCADE`, indexed | |
| `provider` | String(20), not null | CHECK `provider IN ('github','gitlab')` |
| `owner` | String(255), not null | As displayed. For GitLab, the full namespace (`group/subgroup`) |
| `name` | String(255), not null | As displayed |
| `full_name_key` | String(511), not null | `lower(owner + "/" + name)`, for uniqueness |
| `url` | Text, not null | Canonical: `https://github.com/{owner}/{name}` or `https://gitlab.com/{owner}/{name}` |
| `default_branch` | String(255), not null | See precedence below |
| `default_branch_is_user_set` | Boolean, not null, default false | True when the user supplied `default_branch`; a provider value never replaces it |
| `verification_status` | String(20), not null, default `unchecked` | CHECK `IN ('verified','not_found','unchecked')` |
| `verified_at` | timestamptz, nullable | When the last check ran, whatever its result |
| `created_at`, `updated_at` | timestamptz | |

- `uq_repo_project_provider_key` on `(project_id, provider, full_name_key)`. The same repository may belong to several projects; it may not appear twice in one project, regardless of letter case.
- **Default branch precedence:** the value the user supplied, else the provider's default branch when verification succeeded, else `main`. A provider value never overwrites a user-supplied one.
- `webhook_id` / `webhook_secret` from the schema doc are omitted; they belong to the real provider connection.
- Repositories of a soft-deleted project are unreachable through every route, because every repository route first resolves its live project.

## Organization-service change: `members/me`

`GET /api/v1/organizations/{org_id}/members/me`, added to `organization-service`'s `members.py`. It uses the existing `require_org_role(*OrganizationMember.ROLES)` dependency, which already returns 404 for a soft-deleted organization or a caller who is not an **active** member (`get_role` filters on `status == "active"`).

**Contract** — both services test against this exact shape:

| Case | Status | Body |
|---|---|---|
| Caller is an active member | 200 | `{"role": "<owner\|admin\|member\|viewer\|billing_manager>"}` (exactly this one key) |
| Not a member, suspended/removed, or organization deleted | 404 | FastAPI's `{"detail": "..."}` |
| Missing or invalid token | 401 | FastAPI's `{"detail": "..."}` |

organization-service asserts it produces exactly this; project-service's `respx` mocks return exactly this. The contract is written down here so neither side changes it silently.

## Endpoints

All under `/api/v1`, all require `Authorization: Bearer <JWT>` except `/health`.

| Method and path | owner / admin | member | viewer / billing_manager |
|---|---|---|---|
| `POST /organizations/{org_id}/projects` | ✓ | — | — |
| `GET /organizations/{org_id}/projects?limit=&offset=` | ✓ | ✓ | ✓ |
| `GET /projects/{project_id}` | ✓ | ✓ | ✓ |
| `PATCH /projects/{project_id}` (name, slug, description) | ✓ | — | — |
| `PATCH /projects/{project_id}/settings` | ✓ | ✓ | — |
| `DELETE /projects/{project_id}` (soft delete) | ✓ | — | — |
| `GET /projects/{project_id}/repositories` | ✓ | ✓ | ✓ |
| `POST /projects/{project_id}/repositories` | ✓ | ✓ | — |
| `POST /projects/{project_id}/repositories/{repo_id}/verify` | ✓ | ✓ | — |
| `DELETE /projects/{project_id}/repositories/{repo_id}` (hard delete) | ✓ | ✓ | — |
| `GET /health` (no auth) | — | — | — |

- Only create and list are nested under `/organizations/{org_id}`. Every other route takes a project id and derives the organization from the project row, so a URL cannot pair one organization's id with another organization's project.
- `limit` defaults to 50, maximum 100; `offset` defaults to 0. Projects are ordered by `id`.
- Project responses (single and in lists) include `"my_role"`, the caller's organization role, so a client can hide actions it cannot perform.
- `POST /projects/{id}/repositories` takes `{"url": "...", "default_branch": "..." (optional)}` and returns 201 with the saved repository, whatever the verification outcome.

### Authorization flow

One dependency, `require_project_role(*roles)` (and `require_org_role(*roles)` for the two org-nested routes, which skip step 2):

1. Decode the JWT locally. Missing or invalid → **401**.
2. Load the project; missing or soft-deleted → **404 "Project not found"**.
3. `org_client.get_my_role(org_id, token)` — `GET {ORGANIZATION_SERVICE_URL}/api/v1/organizations/{org_id}/members/me` forwarding only the caller's `Authorization` header, timeout `ORGANIZATION_SERVICE_TIMEOUT_SECONDS`.
   - 200 → the role.
   - 404 → **404 "Project not found"** on project routes (non-members cannot learn a project exists), **404 "Organization not found"** on the org-nested routes.
   - 401 → **401**.
   - Timeout, connection error, 5xx, or a 200 whose body does not match the contract → **503 "Organization service unavailable"**. Never guess a role.
4. Role not in `roles` → **403 "Insufficient role"**.

### Other errors

- Duplicate live project name or slug in the organization → **409**.
- Repository already in the project (case-insensitive) → **409**.
- Unparseable repository URL, or a host other than `github.com` / `gitlab.com` → **422** with the reason.
- Invalid settings → **422** naming the field.

## Settings

`schemas/settings.py`:

```python
class ProjectSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    result_retention_days: int = Field(90, ge=1, le=365)
    default_environment: Optional[str] = Field(None, max_length=50)
    notify_on_failure: bool = False
```

- **Read:** responses always contain the full settings with defaults applied. The column stores only keys that were explicitly set, so adding a setting with a default later needs no data migration.
- **Update:** `PATCH /projects/{id}/settings` is a merge. Keys present in the body replace stored values; a key set to `null` is removed from storage (reverting to its default); absent keys are untouched. The merged result is validated as `ProjectSettings`; unknown keys and out-of-range values → 422.

## Repository URL parsing — `utils/repo_url.py`

Pure function, no I/O: `parse_repo_url(raw: str) -> ParsedRepo(provider, owner, name, full_name_key, url)`, raising `ValueError` with a user-facing message.

Accepted forms (for both hosts):

- `https://{host}/{owner}/{name}`, with optional trailing `/`, `.git`, or extra path such as `/tree/main` or `/-/tree/main` (GitHub: only the first two path segments are the repository; GitLab: everything before `/-/`, or the whole path)
- `http://` is accepted and normalised to `https://`
- `git@{host}:{owner}/{name}(.git)`

Rules:

- Host must be exactly `github.com` or `gitlab.com` (case-insensitive). `www.github.com` is normalised to `github.com`. Anything else — including `github.com.evil.com`, IP addresses, userinfo (`user@github.com`), explicit ports — is rejected.
- Each path segment must match `^[A-Za-z0-9._-]+$` and must not be `.` or `..`. Percent-encoded characters, spaces and empty segments are rejected.
- GitHub requires exactly `owner/name`. GitLab requires at least `group/name`, at most 20 segments.

## Repository verification — `utils/repo_verifier.py`

`verify(provider, owner, name) -> VerificationResult(status, default_branch | None)`.

The only URLs this module ever requests, with each path segment URL-encoded:

- GitHub: `https://api.github.com/repos/{owner}/{name}`
- GitLab: `https://gitlab.com/api/v4/projects/{url-encoded "owner/name"}`

The host is never taken from user input, and the caller's JWT is never sent to a provider. No credentials of any kind are sent.

| Provider response | Status | Notes |
|---|---|---|
| 200 | `verified` | Returns the provider's `default_branch` |
| 404 | `not_found` | Missing or private — indistinguishable without credentials |
| 403 or 429 (rate limit), 5xx, timeout, network error, unexpected body | `unchecked` | Never raised; never retried in a loop |

- **On create**, verification runs inline with `REPO_VERIFY_TIMEOUT_SECONDS`; any failure yields `unchecked` and the repository is still saved.
- **Re-verify cooldown:** `POST …/verify` within `REPO_VERIFY_COOLDOWN_SECONDS` of `verified_at` returns the stored result without calling the provider. This protects GitHub's unauthenticated limit (60 requests/hour per server IP), which every user of the platform shares.
- Every check — on create or re-verify, whatever its outcome — sets `verification_status` and `verified_at`, so the cooldown applies after failed checks too.
- A successful check sets `default_branch` from the provider only when `default_branch_is_user_set` is false.

## Testing

Unit and integration split, as in organization-service. SQLite in tests, `SECRET_KEY=test-secret`. `respx` for every outgoing HTTP call; any unmocked outgoing request fails the test.

- **URL parsing:** every accepted form; mixed case yields the same `full_name_key`; each rejection rule (other hosts, `github.com.evil.com`, IPs, ports, userinfo, `..`, `%2F`, spaces, empty segments, wrong segment counts).
- **Verification:** each row of the verification table; requests go only to the two fixed URLs; no `Authorization` header is sent to providers; the cooldown suppresses a second call.
- **Authorization:** every route × every role against the endpoint table; non-member → 404; organization-service timeout → 503; 5xx → 503; malformed 200 body → 503; 401 from organization-service → 401; soft-deleted project → 404 even for its owner; a project id from organization A with a caller who is only a member of B → 404.
- **Data rules:** duplicate name → 409; same name reusable after soft delete; same repository in two projects allowed; same repository twice in one project with different case → 409; default-branch precedence in all three branches.
- **Settings:** defaults on read; merge on PATCH; `null` reverts; unknown key → 422; out of range → 422.
- **Migration:** `alembic upgrade head` on a fresh database produces tables and columns matching the models, including both partial unique indexes (pattern: organization-service's `tests/unit/test_migration.py`).
- **organization-service:** tests for `members/me` asserting the exact contract body for each role, and 404 for non-member, suspended member and deleted organization. Its existing 80 tests stay green.

## Deployment

- **Dockerfile:** the same repository-root-context pattern as the other two services; `COPY shared/`, the service's `requirements.txt`, `src/`, `alembic/`, `alembic.ini`; `CMD ["uvicorn", "src.project.api.main:app", "--host", "0.0.0.0", "--port", "8000"]`.
- **docker-compose.yml:** app published on host port **8002**, database on **5435**; app healthcheck on `/health` and `pg_isready` on the database, with the app waiting for a healthy database; `SECRET_KEY=${SECRET_KEY:?...}`; `ORGANIZATION_SERVICE_URL=${ORGANIZATION_SERVICE_URL:-http://host.docker.internal:8001}` with `extra_hosts: ["host.docker.internal:host-gateway"]`, so the default reaches a separately running organization-service stack on Docker Desktop and on Linux (including CI runners) alike.
- **CI:** one entry each in the `tests` and `smoke` matrices of `.github/workflows/ci.yml` (smoke port 8002). `/health` needs neither organization-service nor a provider.
- **Docs:** `platforms/project-service/README.md`; add `project-service` to the root README's Project Structure; tick the corresponding items in `TODO.md` truthfully.

## Build order

1. organization-service `members/me` with its contract tests — its own reviewed step, since everything after it depends on it.
2. project-service skeleton: config, db, models, migration, `/health`, Dockerfile, compose, CI entries.
3. `repo_url` parsing and `repo_verifier`, as pure units.
4. `org_client` and the authorization dependencies.
5. Project endpoints and settings.
6. Repository endpoints.
7. Documentation.

## Out of scope (each its own spec later)

- Real GitHub/GitLab connection (GitHub App or OAuth, per-repository tokens, webhooks, private-repository verification).
- Project-level membership and private projects.
- Self-hosted GitLab, Bitbucket, Azure DevOps.
- Caching `members/me` results.
- Removing projects when their organization is deleted (they are already unreachable, because `members/me` returns 404 for a deleted organization).
- A repository-root compose file and the API gateway (next roadmap item).
- organization-service's known `auth_client.py` limitation; project-service never calls auth-service.
