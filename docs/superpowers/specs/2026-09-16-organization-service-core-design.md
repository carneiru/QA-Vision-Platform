# Organization Service — Core Implementation Design

**Date:** 2026-09-16
**Status:** Approved
**Scope:** First real implementation pass for `platforms/organization-service`, currently a literal file-copy of `auth-service` with zero organization/team domain logic (verified: identical 46 `.py` files, `User`/`Session`/`OAuthAccount` models, `auth.py`/`sso.py` endpoints, one git commit in history — the mass reorg copy).

## Problem

`ARCHITECTURE_EVOLUTION_SUMMARY.md` marks Organization/Project/User/Team/Billing services "✅ Complete." They are not — they are unmodified auth-service clones. This spec covers building real domain logic for `organization-service` first, since `project-service`/`team-service`/`billing-service` all depend on `organization_id`.

## Architecture

Mirror `auth-service`'s existing layout and stack exactly (FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL, own `organization_db`), same JWT bearer scheme (shared `SECRET_KEY`, HS256, `python-jose`) so tokens issued by auth-service are trusted here without a second login flow.

```
src/organization/
  api/{main.py, deps.py, v1/api.py, v1/endpoints/organizations.py, v1/endpoints/members.py}
  core/config.py
  db/{base.py, session.py}
  models/{organization.py, member.py}
  schemas/{organization.py, member.py}
  service/{organization_service.py, member_service.py}
  utils/auth_client.py
tests/{unit,integration}/
```

## Data Model

Core subset of `docs/superpowers/specs/2026-07-13-qa-vision-database-schema.md` §1 (Invitations and `organization_settings` deferred — out of scope this pass):

- `organizations`: `id` (Integer — matches auth-service's real `User.id` type, not the UUID the original schema doc specifies), `name`, `slug` (unique), `plan_tier`, `created_at`, `updated_at`, `deleted_at` (soft delete)
- `organization_members`: `id`, `organization_id` (FK), `user_id` (Integer, external reference to auth-service's user table — no local FK, cross-service), `role` (CHECK: owner/admin/member/viewer/billing_manager), `status` (pending/active/suspended/removed), timestamps

## Cross-Service User Validation

Adding a member requires confirming the `user_id` exists in auth-service. auth-service's `GET /users/{id}` (`platforms/auth-service/auth-service/src/auth/api/v1/endpoints/users.py:50-67`) only permits the caller to fetch themselves or requires the caller to already be a superuser — there is no clean internal/service-to-service contract.

Decision: build `organization-service`'s `utils/auth_client.py` as an `httpx`-based client calling that endpoint with a configurable service-account bearer token (`AUTH_SERVICE_URL`, `AUTH_SERVICE_TOKEN` settings). This works but is a workaround, not a proper fix.

**Flagged for follow-up (not built in this pass):** `platforms/auth-service/auth-service/src/auth/api/v1/endpoints/users.py` needs a dedicated internal endpoint (e.g. API-key-authenticated `GET /internal/users/{id}/exists`) instead of reusing the superuser/self path for service-to-service calls.

## Endpoints

- `POST /organizations`, `GET /organizations/{id}`, `PATCH /organizations/{id}`, `DELETE /organizations/{id}` (soft delete) — creator becomes `owner` member automatically, identified from the JWT `sub`, no external call needed for this step
- `POST /organizations/{id}/members`, `GET /organizations/{id}/members`, `DELETE /organizations/{id}/members/{member_id}` — owner/admin only, enforced via a role-checking FastAPI dependency; `POST` validates `user_id` via `auth_client`

## Testing

Mirror auth-service's `tests/unit` + `tests/integration` split. Use `respx` (MIT license) to mock the `auth_client` HTTP call in tests — real request/response assertions, not empty stubs.

## Cleanup (in this change)

Delete from `organization-service`: `models/{user,session,oauth}.py`, `api/v1/endpoints/{auth,sso}.py`, `service/{auth_service,sso_service}.py`, auth-table alembic migrations (`001_create_users_table.py`, `002_add_sessions_table.py`, `003_add_oauth_tables.py`), and the vendored `dm.xmlsec.binding-1.3.7/` directory plus both `.tar.gz` copies.

## Out of scope (separate follow-up sub-projects)

- `organization_invitations`, `organization_settings` (SSO/MFA config)
- `project-service`, `team-service`, `billing-service`, and the intelligence/* stub services — same clone problem, same treatment needed later
- Fixing auth-service's own bugs found while reading it for this design (not touched, listed below for the record):
  - `src/auth/api/main.py` imports `settings.PROJECT_NAME` / `settings.API_V1_STR` / `settings.BACKEND_CORS_ORIGINS` from `src/auth/core/config.py`, but that `Settings` class only defines `SECRET_KEY`/`ALGORITHM`/token expiry/`DATABASE_URL` — missing attributes, so this entrypoint would raise `AttributeError` at import time. The real, complete settings live in the sibling `src/auth/config.py` instead. Two divergent config modules; `core/config.py` looks dead/stale.
