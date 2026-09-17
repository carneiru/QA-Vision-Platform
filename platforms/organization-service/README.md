# Organization Service

Manages organizations (tenants) and their memberships for QA Vision Platform.

## Responsibilities

- Organization CRUD (`/api/v1/organizations`)
- Membership management (`/api/v1/organizations/{org_id}/members`) with roles:
  `owner`, `admin`, `member`, `viewer`, `billing_manager`
- Validates member `user_id`s against auth-service over HTTP before adding them

Known limitation: the `user_id` existence check assumes auth-service returns `404` for an
unknown user id, which it does not yet do cleanly — resolving it requires a change in
auth-service and is tracked as a follow-up.

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
