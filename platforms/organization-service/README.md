# Organization Service

Manages organizations (tenants) and their memberships for QEOS.

## Responsibilities

- Organization CRUD (`/api/v1/organizations`)
- Membership management (`/api/v1/organizations/{org_id}/members`) with roles:
  `owner`, `admin`, `member`, `viewer`, `billing_manager`. Only an owner may grant or
  remove a member with the `owner`/`admin` role. The member list carries each member's email,
  read from auth-service (best effort: blank when auth-service does not answer).
  `GET /api/v1/organizations/{org_id}/members/me` returns the caller's role; project-service,
  ingestion-service and test-management-service authorize through it.
- Email-based invitations (`/api/v1/organizations/{org_id}/invitations` to create/list/revoke,
  `GET /api/v1/invitations/{token}` for a signed-in user to preview it,
  `/api/v1/invitations/{token}/accept` to accept; valid 7 days, single use). This service does
  not send email -- the
  create response includes the invite `token`; delivering it is a separate concern (a
  frontend or notification-service's job). Whoever holds a valid, unexpired, unused invite
  token and is logged in may accept it; there is no email-match check against the invitee.
- Validates member `user_id`s against auth-service's internal API
  (`/internal/v1/users/{id}`, HTTP Basic with `INTERNAL_API_USERNAME`/`INTERNAL_API_PASSWORD`)
  before adding them: `404` means no such user; any other answer is a `502`, never a silent yes
  or no.
- Prometheus metrics at `/metrics` (not routed by the gateway).

## Auth model

This service does not issue tokens. It trusts JWTs signed by auth-service
(shared `SECRET_KEY`/`HS256`) and reads the user id from the `sub` claim.

## Out of scope (see docs/superpowers/specs/2026-09-16-organization-service-core-design.md)

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
