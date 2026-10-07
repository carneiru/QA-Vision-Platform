# Organization Service

Manages organizations (tenants) and their memberships for QEOS.

## Responsibilities

- Organization CRUD (`/api/v1/organizations`)
- Membership management (`/api/v1/organizations/{org_id}/members`) with roles:
  `owner`, `admin`, `member`, `viewer`, `billing_manager`. Only an owner may grant or
  remove a member with the `owner`/`admin` role.
- Email-based invitations (`/api/v1/organizations/{org_id}/invitations` to create/list/revoke,
  `/api/v1/invitations/{token}/accept` to accept). This service does not send email -- the
  create response includes the invite `token`; delivering it is a separate concern (a
  frontend or notification-service's job). Whoever holds a valid, unexpired, unused invite
  token and is logged in may accept it; there is no email-match check against the invitee.
- Validates member `user_id`s against auth-service over HTTP before adding them

Known limitation: the `user_id` existence check assumes auth-service returns `404` for an
unknown user id, which it does not yet do cleanly — resolving it requires a change in
auth-service and is tracked as a follow-up.

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
