# Organization Invitations — Design

**Date:** 2026-09-17
**Status:** Approved
**Scope:** `organization_invitations` — deferred out of scope in `2026-09-16-organization-service-core-design.md` §"Out of scope". First of two follow-up sub-projects from that deferral list (the second, `organization_settings`/SSO-MFA config, is a separate spec).

## Problem

There is currently no way to add someone to an organization unless you already know their `user_id` (`POST /organizations/{org_id}/members` requires it directly). Real usage requires inviting people by email who may not even have a platform account yet, without organization-service needing to know anything about auth-service's user table beyond what it already knows (nothing, by email).

## Constraints Established During Brainstorming

- **No email delivery exists anywhere in the platform.** `auth-service` declares SMTP config fields (`SMTP_HOST`, `SMTP_USER`, etc.) but has zero actual sending code. Decision: this feature is **API-only** — it creates/validates/consumes invite tokens and returns the invite link in the API response. Actually emailing that link is out of scope (a future frontend or notification-service's job).
- **auth-service JWTs carry only `sub` (user id), no email.** Verifying that the person accepting an invite has the actual invited email address would require a new cross-service lookup. Decision: **token possession is the security boundary**, not email matching. Whoever is logged in and presents a valid, unexpired, unused invite token is added with the invite's role. This avoids adding a new cross-service dependency for this feature.

### Added after the final whole-branch review — decisions this spec originally left unmade

- **The raw token appears ONLY in the create (201) response, never in list responses.** The original spec decided the token goes in the create response and then simply never said whether `GET /invitations` should echo it; the first implementation resolved that silently by reusing one schema for both, and the final review demonstrated a working exploit: a plain **admin** lists invitations, reads a pending *owner*-role invite's token, hands it to an account they control, and that account becomes an owner — routing straight around the owner-only grant policy the whole feature depends on. The list endpoint therefore uses a separate `InvitationSummary` schema with every field except `token`.

  Note this is deliberately **narrower than** the "token possession is the security boundary" decision above. That decision was about not checking the *accepter's* email; it assumed the token reaches only the person the inviter chose. Broadcasting it to every admin widens the possession set past that assumption, so the two decisions are consistent only if the token stays scarce.

- **Claiming the invitation and creating the member row happen in ONE transaction, and the claim is a conditional `UPDATE`, not a read-then-write check.** The original spec prescribed "create the member row → set `accepted_at`" as two steps and never addressed atomicity. The final review verified both failure modes that produced: (a) with two separate commits, a crash between them left membership granted while the token stayed reusable, so one owner-role invite yielded two owners; and (b) even with a single transaction, a read-then-write `accepted_at is None` check lets two concurrent accepts by *different* users both pass (the `uq_org_member` constraint does not stop them — different `user_id`s). Single-use is therefore enforced at the database by an `UPDATE ... WHERE token = ? AND accepted_at IS NULL` whose row count decides whether the accept proceeds. Expiry is checked *before* the claim, so a failed accept never marks an expired invitation accepted, and a rollback on any downstream failure un-claims it so the invitation stays usable.

- **Accepted risk: the token travels in the URL path** (`POST /invitations/{token}/accept`), so it can land in access logs, proxy logs, `Referer` headers and browser history. This is standard invite-link practice and is accepted deliberately rather than silently; accepting via request body would avoid it if this ever needs tightening.
- Because invites are created by email (not `user_id`), organization-service **cannot check "is this email already a member"** at invite-creation time — it only learns the real `user_id` when the invitee logs in and accepts. That check happens at accept time instead, via the existing `add_member` duplicate-membership check.

## Architecture

Follows the same layering already established in `organization-service`: model → schema → service → endpoint, same JWT bearer auth, same `require_org_role` dependency for role-gated routes.

```
src/organization/
  models/invitation.py          # OrganizationInvitation
  schemas/invitation.py          # InvitationCreate, InvitationOut
  service/invitation_service.py  # create/list/revoke/accept_invitation
  service/member_service.py      # MODIFIED: split into _assert_can_grant_role() + _create_member_row(), both reused by invitation_service
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
- `POST /api/v1/invitations/{token}/accept` — **top-level, not org-nested.** The accepter isn't a member yet and may not know the `org_id`; the token alone resolves it. Requires only a valid JWT (`get_current_user_id`), no org role check. Internally: validate token (exists, not expired, not already accepted) → create the member row (see Security Integration below for exactly which function it calls and why) → set `accepted_at`.

## Security Integration — Reuse, Don't Duplicate

**Self-review finding (fixed before implementation):** the obvious approach — accept just calls the existing `add_member(db, org_id, user_id, role, granter_role)` — doesn't fit. `add_member`'s current signature requires a `granter_role` because it enforces "only an owner may grant owner/admin." At accept time there is no granter — the invitee is adding themselves — and that policy check was already correctly applied once, against the *inviter's* role, when the invitation was created. Calling `add_member` as-is would force either a wrong re-check (blocking a legitimate accept, or requiring a fake `granter_role="owner"` passed in — which would silently defeat the whole policy for a specially-crafted case later) or an awkward bypass flag bolted onto a security-critical function.

**Fix: split policy from mechanism.** `member_service.py` currently has, inline in `add_member`:
```python
if role in ("owner", "admin") and granter_role != "owner":
    raise PermissionError(...)
```
Refactor into:
- `_assert_can_grant_role(granter_role: str, target_role: str) -> None` — the policy check, extracted as its own function. Called by `add_member` (with the caller's resolved role) and by `invitation_service.create_invitation` (with the inviter's resolved role) — each enforces the policy once, against the actual granter in its own flow.
- `_create_member_row(db, org_id, user_id, role) -> OrganizationMember` — the mechanism only: role-format validation, `user_exists` check, duplicate-membership check, insert, commit, refresh. No policy check inside it.
- `add_member(db, org_id, user_id, role, granter_role)` becomes: `_assert_can_grant_role(granter_role, role)` → `_create_member_row(...)`.
- `invitation_service.accept_invitation` calls `_create_member_row(...)` directly — it inherits the duplicate-membership check for free, and correctly does NOT re-run (or bypass) a grant-policy check that already happened once, at invite-creation time, in `create_invitation`.

This is the same "one function, one place to get it right" principle the design already called for — refined after re-reading the actual current `add_member` implementation (`platforms/organization-service/src/organization/service/member_service.py:20-38`) rather than the earlier description of it from memory.

## Error Handling

- Expired / already-accepted / nonexistent token at accept time → **404** (not 410, to avoid leaking which specific condition applies — matches the existing "don't leak internals via response" posture from `require_org_role`'s 404-vs-403 split).
- `create_invitation` with an invalid `role` string → 422 (reuse the `ValueError` → 422 convention already established).
- `create_invitation` granting owner/admin without being an owner → 403 (`PermissionError` → 403, same convention as `add_member`).
- Accepting into a soft-deleted organization → 404 (accept resolves the org the same way `require_org_role` does — via `organization_service.get_organization`, which already filters `deleted_at`).

## Testing

Same `tests/unit` + `tests/integration` split as the rest of the service. Real HTTP requests through `TestClient` (no calling service functions directly, per the pattern this service's reviews have consistently required). Cases: create (success, 403 non-owner-granting-owner, 422 bad role), list (only pending shown), revoke, accept (success — member created with correct role; 404 expired; 404 already-accepted; 404 nonexistent token; 404 org soft-deleted; **accepting an owner/admin-role invite created by a legitimate owner succeeds even though the accepter is not, themselves, an owner** — proves the split-out policy/mechanism refactor works, not just that it compiles); and one test proving `_assert_can_grant_role` is genuinely shared (not copy-pasted) between `add_member` and `create_invitation`.

## Out of Scope

- Actually sending the invite email (see Constraints above) — the API returns the token/link, delivery is a separate concern.
- Email-match verification at accept time (see Constraints above).
- Resend/reminder scheduling, invite templates, or any notification-service integration.
- `organization_settings` (SSO/MFA/session config) — separate spec, follows this one.
