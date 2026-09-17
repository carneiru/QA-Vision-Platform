# Organization Invitations — Design

**Date:** 2026-09-17
**Status:** Approved
**Scope:** `organization_invitations` — deferred out of scope in `2026-09-16-organization-service-core-design.md` §"Out of scope". First of two follow-up sub-projects from that deferral list (the second, `organization_settings`/SSO-MFA config, is a separate spec).

## Problem

There is currently no way to add someone to an organization unless you already know their `user_id` (`POST /organizations/{org_id}/members` requires it directly). Real usage requires inviting people by email who may not even have a platform account yet, without organization-service needing to know anything about auth-service's user table beyond what it already knows (nothing, by email).

## Constraints Established During Brainstorming

- **No email delivery exists anywhere in the platform.** `auth-service` declares SMTP config fields (`SMTP_HOST`, `SMTP_USER`, etc.) but has zero actual sending code. Decision: this feature is **API-only** — it creates/validates/consumes invite tokens and returns the invite link in the API response. Actually emailing that link is out of scope (a future frontend or notification-service's job).
- **auth-service JWTs carry only `sub` (user id), no email.** Verifying that the person accepting an invite has the actual invited email address would require a new cross-service lookup. Decision: **token possession is the security boundary**, not email matching. Whoever is logged in and presents a valid, unexpired, unused invite token is added with the invite's role. This avoids adding a new cross-service dependency for this feature.
- Because invites are created by email (not `user_id`), organization-service **cannot check "is this email already a member"** at invite-creation time — it only learns the real `user_id` when the invitee logs in and accepts. That check happens at accept time instead, via the existing `add_member` duplicate-membership check.

## Architecture

Follows the same layering already established in `organization-service`: model → schema → service → endpoint, same JWT bearer auth, same `require_org_role` dependency for role-gated routes.

```
src/organization/
  models/invitation.py          # OrganizationInvitation
  schemas/invitation.py          # InvitationCreate, InvitationOut
  service/invitation_service.py  # create/list/revoke/accept_invitation
  service/member_service.py      # MODIFIED: extract _can_grant_role() helper, reuse in invitation_service
  api/v1/endpoints/invitations.py  # org-scoped: create/list/revoke
  api/v1/endpoints/invitation_accept.py  # top-level: accept by token
  api/v1/api.py                  # MODIFIED: wire both new routers
alembic/versions/003_add_organization_invitations.py
tests/{unit,integration}/*invitation*
```

## Data Model

New table, `organization_invitations` (Integer ids, matching this service's established convention — the original `2026-07-13-qa-vision-database-schema.md` §1 UUID design was already overridden the same way for `organizations`/`organization_members` in the core-service pass):

- `id` (Integer, PK)
- `organization_id` (Integer, FK → `organizations.id`, `ondelete="CASCADE"`)
- `email` (String, not null)
- `role` (String, CHECK against the same `OrganizationMember.ROLES` tuple)
- `invited_by_user_id` (Integer, not null — the inviter's user id; not a member-row FK, consistent with `organization_members.user_id` being a plain cross-service Integer reference)
- `token` (String, unique, not null — `secrets.token_urlsafe(32)`)
- `expires_at` (DateTime, not null — default 7 days from creation)
- `created_at` (DateTime, server default now)
- `accepted_at` (DateTime, nullable — set on accept)

No uniqueness constraint on `(organization_id, email)` — a second invite to an already-pending email is allowed (creates a new token; simplest resend story, matches how most real products behave).

## Endpoints

- `POST /organizations/{org_id}/invitations` — create. Gated `require_org_role("owner", "admin")`. Enforces the same "only an owner may invite as owner/admin" rule `add_member` already enforces (see below) — 403 if an admin tries to invite someone as `owner`/`admin`.
- `GET /organizations/{org_id}/invitations` — list pending (not accepted, not expired) invitations for the org. Same role gate as create.
- `DELETE /organizations/{org_id}/invitations/{invitation_id}` — revoke (hard delete the row). Same role gate.
- `POST /api/v1/invitations/{token}/accept` — **top-level, not org-nested.** The accepter isn't a member yet and may not know the `org_id`; the token alone resolves it. Requires only a valid JWT (`get_current_user_id`), no org role check. Internally: validate token (exists, not expired, not already accepted) → call the existing `member_service.add_member(db, org.id, user_id, invitation.role)` (inherits its atomicity and "already a member" duplicate check for free) → set `accepted_at`.

## Security Integration — Reuse, Don't Duplicate

`member_service.add_member` currently has this inline (from the earlier privilege-escalation fix):
```python
if role in ("owner", "admin") and granter_role != "owner":
    raise PermissionError(...)
```
This check gets extracted into a small shared helper (e.g. `member_service._assert_can_grant_role(granter_role, target_role)`) that both `add_member` and `invitation_service.create_invitation` call. Duplicating this policy inline in two places is exactly the kind of drift the final review already caught once this session (the 409-message drift across the revert/restore cycle) — one function, one place to get it right.

## Error Handling

- Expired / already-accepted / nonexistent token at accept time → **404** (not 410, to avoid leaking which specific condition applies — matches the existing "don't leak internals via response" posture from `require_org_role`'s 404-vs-403 split).
- `create_invitation` with an invalid `role` string → 422 (reuse the `ValueError` → 422 convention already established).
- `create_invitation` granting owner/admin without being an owner → 403 (`PermissionError` → 403, same convention as `add_member`).
- Accepting into a soft-deleted organization → 404 (accept resolves the org the same way `require_org_role` does — via `organization_service.get_organization`, which already filters `deleted_at`).

## Testing

Same `tests/unit` + `tests/integration` split as the rest of the service. Real HTTP requests through `TestClient` (no calling service functions directly, per the pattern this service's reviews have consistently required). Cases: create (success, 403 non-owner-granting-owner, 422 bad role), list (only pending shown), revoke, accept (success — member created with correct role; 404 expired; 404 already-accepted; 404 nonexistent token; 404 org soft-deleted); and one test proving `_assert_can_grant_role` is genuinely shared (not copy-pasted) between `add_member` and `create_invitation`.

## Out of Scope

- Actually sending the invite email (see Constraints above) — the API returns the token/link, delivery is a separate concern.
- Email-match verification at accept time (see Constraints above).
- Resend/reminder scheduling, invite templates, or any notification-service integration.
- `organization_settings` (SSO/MFA/session config) — separate spec, follows this one.
