# Email Verification for Password Registration — Design

**Service:** `platforms/auth-service/auth-service`
**Status:** approved for planning

## Problem

`POST /auth/register` creates a `User` row immediately, before anyone has proven they
control the address they're registering. That row permanently occupies the email:

- A second registration for the same address gets `400 Email already registered`.
- Google SSO for that address gets `409` (the account-linking guard added earlier — a
  password account is never auto-linked, by design).

So an attacker who registers `ceo@corp.com` with a password they never use — and never
proves they own the mailbox — permanently locks the real `ceo@corp.com` out of both the
password and the Google path, forever. Nothing about the account being unused or the
attacker never logging in ever releases the address.

This is why the SSO-linking fix (an earlier, separate piece of work) turned the original
*takeover* into a *lockout* rather than eliminating the underlying issue: the address was
never verified as belonging to whoever claimed it, only structurally protected once claimed.

Google SSO does not have this problem — Google's `email_verified` claim is cryptographic
proof of mailbox control, checked in `sso_service.py` before a login or account creation
ever happens. This spec closes the equivalent gap for password registration only. SSO's
`_link_or_create_user` is unchanged.

## Design

### Core decision: no `User` row until verified

Registration does not create a `User`. It creates a `PendingRegistration` — an unclaimed
record with a verification token. The email is not "taken" in any way another registration
or SSO login can observe until someone completes verification by clicking the link, which
requires access to that mailbox.

An attacker can request as many pending registrations as they want for an address. None of
them do anything: no row exists in `users`, `/auth/register` for that address from someone
else does not error, and Google SSO for that address is completely unaffected (it only ever
queries `users`, never `pending_registrations`). Whoever actually controls the mailbox and
completes verification is whoever ends up owning the account — including via Google SSO
racing ahead of a pending password verification, which this design treats as a legitimate
outcome, not a case to prevent.

### Data model

New table, structured like `RefreshToken` (opaque, DB-backed, revocable by deletion):

```python
# src/auth/models/pending_registration.py
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from src.auth.db.base import Base

class PendingRegistration(Base):
    __tablename__ = "pending_registrations"

    id = Column(Integer, primary_key=True, index=True)
    # UNIQUE: a second registration attempt for the same still-pending address rotates
    # this row (new token, new expiry) instead of creating a competing one or erroring.
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    token = Column(String(255), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

Migration: new Alembic revision creating this table, chained after `004_make_tenant_id_nullable`.

### Token

Opaque, `secrets.token_urlsafe(32)`, matching the refresh-token pattern already established
in this service (`auth_service.py`) rather than a signed JWT — consistent with this
codebase's existing preference for revocable, DB-backed tokens over self-contained ones.

Expiry: 24 hours from creation, configurable via a new `EMAIL_VERIFICATION_EXPIRE_HOURS:
int = 24` setting in `config.py`, following the pattern of `REFRESH_TOKEN_EXPIRE_DAYS`.

### Endpoints

**`POST /auth/register`** — behavior change, not additive:

1. Validate the body via `RegisterRequest` (unchanged schema — email, password, full_name).
2. If a `User` with this email already exists → `400 Email already registered` (unchanged
   from today).
3. If a `PendingRegistration` with this email already exists → delete it (rotating: a fresh
   token and expiry replace it, rather than erroring or leaving two live tokens for one
   address).
4. Hash the password (reuses `get_password_hash`), create the `PendingRegistration` row,
   commit.
5. Send the verification email (see Mail delivery below) containing the backend link
   directly — no frontend exists to route through, so the email contains the URL this
   service itself answers: `{settings.API_V1_STR}/auth/verify-email?token=<token>` resolved
   against the deployment's own base URL (there is no `BASE_URL` setting today; add one,
   defaulting to `http://localhost:8000`, alongside the other settings this feature adds).
6. Return `202 Accepted`, `{"message": "Check your email to complete registration"}`.

No `User`, no tokens, no `id` in the response. This is the behavior change: today's
`response_model=User` at `200` becomes a message at `202`.

**`GET /auth/verify-email?token=...`**:

1. Look up `PendingRegistration` by token. Not found → `400 Invalid or expired verification
   token`.
2. Expired (`expires_at <= now`, timezone-normalized the same way `verify_refresh_token`
   already handles SQLite's naive datetimes) → same `400`, and the row is deleted (an
   expired pending registration is worthless; deleting it lets the address be re-registered
   cleanly rather than accumulating dead rows a future registration has to keep rotating).
3. **A `User` with this email now exists** (the race case — most likely because the real
   owner completed a Google SSO signup for this address while this pending registration sat
   unverified) → delete the stale pending row, `409 This email is already registered`. The
   attacker's password is discarded; nothing about their pending registration ever touched
   the real account.
4. Otherwise: create the `User` (active, not superuser, `hashed_password` from the pending
   row), delete the `PendingRegistration`, issue access + refresh tokens the same way
   `/auth/login` does, return `Token`. This is the auto-login case.

**`POST /auth/resend-verification`**, body `{"email": str}`:

Always returns the same generic `200 {"message": "If a pending registration exists for
this email, a new verification link has been sent"}` regardless of whether a pending
registration exists — matching the existing enumeration-prevention pattern in
`/auth/forgot-password`. If one exists, rotates its token and expiry and resends. If the
email belongs to a completed `User` instead, or to nothing at all, the response is
identical.

### Mail delivery

`SMTP_HOST`/`SMTP_PORT`/`SMTP_USER`/`SMTP_PASSWORD`/`EMAILS_FROM_EMAIL`/`EMAILS_FROM_NAME`
already exist in `config.py`, marked as unread — same situation `FIRST_SUPERUSER` was in
before this session's earlier work.

Unlike Google SSO (which fails closed with `503` when unconfigured, because verifying
without an audience would be a worse hole than refusing), email delivery cannot fail closed
here: every development and test environment lacking a real SMTP server would be unable to
register at all, which is unacceptable for a control this central.

`src/auth/service/email_sender.py`:

```python
class EmailSender:
    @staticmethod
    def send_verification_email(to_email: str, verification_link: str) -> None:
        if not settings.SMTP_HOST:
            # Dev-safe default: nothing is silently dropped, and a test can read the link
            # straight out of caplog instead of standing up a fake mail server.
            logger.info(
                "Verification email for %s (SMTP not configured, logging instead): %s",
                to_email, verification_link,
            )
            return
        # real smtplib.SMTP(...) send, using SMTP_TLS/SMTP_PORT/SMTP_USER/SMTP_PASSWORD
        ...
```

### What this does not do

- Does not touch SSO. `_link_or_create_user` in `sso.py` is unmodified; Google's
  `email_verified` claim is already equivalent proof, checked at `sso_service.py`.
- Does not add verification to existing accounts retroactively — every `User` row that
  exists today (created before this feature) has no `is_email_verified` concept at all,
  because the design doesn't add that column to `User`. Verification is a gate on *becoming*
  a `User`, not a property tracked on one afterward. This is a deliberate simplification:
  it avoids a migration that would need to decide what `True`/`False` means for the
  existing rows, and avoids leaking a verification check into every other endpoint that
  loads a `User` (login, SSO, `/users/me`, etc. — none of them change).
- Does not implement a background cleanup job for expired `pending_registrations` rows.
  They are deleted lazily: on a successful verify, on an expired verify attempt, or on a
  rotation via a repeated `/auth/register`. A row that is never touched again (attacker
  registers, never returns, real owner never tries either) sits inert forever — harmless,
  since it blocks nothing, but worth a follow-up if the table needs periodic trimming at
  scale.

## Testing

- Register → `202`, no `User` row created, a `PendingRegistration` row exists, the log
  captures the verification link (via `caplog`, no SMTP mock needed).
- Register twice for the same address → the second call rotates the token; the first
  token no longer verifies.
- Verify with a valid token → `User` created, `PendingRegistration` deleted, response is
  `Token`-shaped, and a subsequent `/auth/login` with the original password succeeds.
- Verify with an expired token → `400`, row deleted, and a fresh `/auth/register` for the
  same address succeeds cleanly afterward (proves the squat is actually released).
- Verify after the address has since become a real `User` via Google SSO → `409`, stale
  pending row deleted, and the real `User` (created by SSO) is untouched — this is the
  scenario the spec's Problem section exists to close, so it needs to be proven concretely.
- Resend: identical response for a pending address, a fully-registered address, and a
  nonexistent one.
- Existing test suite: every test using the register-then-login helper pattern (18 call
  sites across `test_auth_endpoints.py`, `test_user_isolation.py`, `test_sso_endpoints.py`)
  needs its helper updated to register → verify (extracting the token from `caplog` or a
  test-only DB query) → then proceed as before. This is the largest mechanical cost of this
  change and should be done as its own early task in the plan, before any new endpoint
  logic, so every later task's tests can rely on the updated helper.

## Migration / compatibility note

This changes `/auth/register`'s response contract (`200` + `User` body → `202` + message).
No real client exists yet — this is the same category of change as the SSO endpoint moving
from a mock to real verification earlier in this service's repair. Documented in the
service README's API section and its "Fully Implemented" summary, both of which currently
describe registration as immediately usable.
