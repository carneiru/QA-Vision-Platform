# Email Verification for Password Registration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the registration-squatting hole by making `POST /auth/register` create an unclaimed, expiring `PendingRegistration` instead of a `User` — an address is not permanently blocked for anyone until someone actually proves control of that mailbox by clicking the verification link.

**Architecture:** A new `pending_registrations` table (opaque token, 24h expiry, same shape as `refresh_tokens`) holds registration attempts. `POST /auth/register` writes to it and emails a link; `GET /auth/verify-email` turns a valid, unexpired row into a real `User` and auto-logs in; `POST /auth/resend-verification` rotates the token. Google SSO is untouched — its `email_verified` claim is already equivalent proof.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, pytest, `smtplib` (stdlib, no new dependency).

**Spec:** `docs/superpowers/specs/2026-09-24-auth-service-email-verification-design.md`

## Global Constraints

- Opaque tokens only (`secrets.token_urlsafe(32)`), never JWTs — matches this service's existing refresh-token pattern.
- `PendingRegistration.email` and `.token` are both `UNIQUE`.
- A second `/auth/register` for a still-pending address **rotates** (delete + recreate), never errors.
- `EmailSender` must never fail closed: when `SMTP_HOST` is unset (the default), log the link instead of raising or silently dropping it.
- SSO (`sso.py`, `sso_service.py`) is not modified by this plan.
- Every existing test that registers a user (18 call sites across `test_auth_endpoints.py`, `test_user_isolation.py`, `test_sso_endpoints.py`) must be updated to the new flow — the suite must be green at the end of every task from Task 3 onward.

---

### Task 1: `PendingRegistration` model, config settings, migration

**Files:**
- Create: `src/auth/models/pending_registration.py`
- Modify: `src/auth/config.py` (add two settings after the SMTP block)
- Create: `alembic/versions/005_add_pending_registrations_table.py`
- Create: `tests/unit/test_pending_registration.py`

**Interfaces:**
- Produces: `PendingRegistration` (SQLAlchemy model) with columns `id, email, hashed_password, full_name, token, expires_at, created_at`. `settings.EMAIL_VERIFICATION_EXPIRE_HOURS: int` (default `24`), `settings.BASE_URL: str` (default `"http://localhost:8000"`).

- [ ] **Step 1: Write the model**

`src/auth/models/pending_registration.py`:
```python
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from src.auth.db.base import Base


class PendingRegistration(Base):
    __tablename__ = "pending_registrations"

    id = Column(Integer, primary_key=True, index=True)
    # UNIQUE: a second registration attempt for the same still-pending address rotates this
    # row (deleted and replaced) rather than creating a competing one or erroring -- nothing
    # is claimed yet, so refusing would only leak that someone already tried this address.
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    token = Column(String(255), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: Add the two settings to `config.py`**

Insert immediately after the existing SMTP block (after `EMAILS_FROM_NAME: str = ""` and before `# SSO Providers`):
```python
    # Email verification (registration). BASE_URL has no other purpose in this service --
    # it exists so the verification link in the email points somewhere real. Defaulting to
    # localhost:8000 matches this service's own default port.
    EMAIL_VERIFICATION_EXPIRE_HOURS: int = 24
    BASE_URL: str = "http://localhost:8000"
```

- [ ] **Step 3: Write the migration**

`alembic/versions/005_add_pending_registrations_table.py`:
```python
"""add pending_registrations table

Revision ID: 005
Revises: 004
Create Date: 2026-09-24

Backs email verification at registration: POST /auth/register no longer creates a User
directly, it creates a row here. The address is not claimed by anyone until GET
/auth/verify-email turns this row into a User -- see
docs/superpowers/specs/2026-09-24-auth-service-email-verification-design.md.
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_registrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(
        op.f("ix_pending_registrations_id"), "pending_registrations", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_pending_registrations_email"), "pending_registrations", ["email"], unique=True
    )
    op.create_index(
        op.f("ix_pending_registrations_token"), "pending_registrations", ["token"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_pending_registrations_token"), table_name="pending_registrations")
    op.drop_index(op.f("ix_pending_registrations_email"), table_name="pending_registrations")
    op.drop_index(op.f("ix_pending_registrations_id"), table_name="pending_registrations")
    op.drop_table("pending_registrations")
```

- [ ] **Step 4: Write the failing test**

`tests/unit/test_pending_registration.py`:
```python
from datetime import datetime, timedelta, timezone

from src.auth.models.pending_registration import PendingRegistration


def test_pending_registration_round_trips_through_the_orm(db):
    row = PendingRegistration(
        email="person@example.com",
        hashed_password="not-a-real-hash",
        full_name="A Person",
        token="test-token-value",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    fetched = db.query(PendingRegistration).filter(
        PendingRegistration.email == "person@example.com"
    ).first()
    assert fetched is not None
    assert fetched.token == "test-token-value"
    assert fetched.full_name == "A Person"


def test_email_is_unique(db):
    from sqlalchemy.exc import IntegrityError

    db.add(PendingRegistration(
        email="dup@example.com", hashed_password="x", token="token-a",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    ))
    db.commit()

    db.add(PendingRegistration(
        email="dup@example.com", hashed_password="y", token="token-b",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    ))
    try:
        db.commit()
        assert False, "expected an IntegrityError on duplicate email"
    except IntegrityError:
        db.rollback()
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/unit/test_pending_registration.py -v`
Expected: `ModuleNotFoundError: No module named 'src.auth.models.pending_registration'` (the file from Step 1 must exist as written for this to pass, so if Step 1 was already applied, instead run this against a git stash of that one file to see the intended failure — the point is confirming the test actually exercises the model, not a typo in the test itself).

- [ ] **Step 6: Run the test to verify it passes**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/unit/test_pending_registration.py -v`
Expected: `2 passed`

- [ ] **Step 7: Verify the migration applies**

This service's test suite creates its schema via `Base.metadata.create_all()` directly (see `tests/conftest.py`), not via Alembic, so no existing test exercises migration files at all. Confirm this one is at least syntactically correct and consistent with the model:

Run: `.venv/Scripts/python.exe -c "import importlib.util; spec = importlib.util.spec_from_file_location('m', 'alembic/versions/005_add_pending_registrations_table.py'); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); print(m.revision, m.down_revision)"`
Expected: `005 004`

If a reachable database is configured, additionally run `alembic upgrade head` and confirm it completes without error, then `alembic downgrade -1` to confirm the downgrade path also works.

- [ ] **Step 8: Commit**

```bash
git add src/auth/models/pending_registration.py src/auth/config.py alembic/versions/005_add_pending_registrations_table.py tests/unit/test_pending_registration.py
git commit -m "feat(auth-service): add pending_registrations table for email verification"
```

---

### Task 2: `EmailSender`

**Files:**
- Create: `src/auth/service/email_sender.py`
- Create: `tests/unit/test_email_sender.py`

**Interfaces:**
- Consumes: `settings.SMTP_HOST`, `settings.SMTP_PORT`, `settings.SMTP_TLS`, `settings.SMTP_USER`, `settings.SMTP_PASSWORD`, `settings.EMAILS_FROM_EMAIL` (all pre-existing in `config.py`).
- Produces: `EmailSender.send_verification_email(to_email: str, verification_link: str) -> None`, used by Task 3 and Task 4.

- [ ] **Step 1: Write the failing tests**

`tests/unit/test_email_sender.py`:
```python
import logging
from unittest.mock import MagicMock, patch

from src.auth.config import settings
from src.auth.service.email_sender import EmailSender


def test_logs_the_link_when_smtp_is_not_configured(caplog, monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "")
    with caplog.at_level(logging.INFO):
        EmailSender.send_verification_email(
            "person@example.com", "http://example.com/verify?token=abc"
        )
    assert "http://example.com/verify?token=abc" in caplog.text
    assert "person@example.com" in caplog.text


def test_sends_via_smtp_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_TLS", True)
    monkeypatch.setattr(settings, "SMTP_USER", "user")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "pass")
    monkeypatch.setattr(settings, "EMAILS_FROM_EMAIL", "no-reply@example.com")

    mock_server = MagicMock()
    mock_server.__enter__.return_value = mock_server
    with patch(
        "src.auth.service.email_sender.smtplib.SMTP", return_value=mock_server
    ) as mock_smtp:
        EmailSender.send_verification_email(
            "person@example.com", "http://example.com/verify?token=abc"
        )

    mock_smtp.assert_called_once_with("smtp.example.com", 587)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("user", "pass")
    mock_server.send_message.assert_called_once()
    sent_message = mock_server.send_message.call_args[0][0]
    assert sent_message["To"] == "person@example.com"
    assert "http://example.com/verify?token=abc" in sent_message.get_content()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/unit/test_email_sender.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.auth.service.email_sender'`

- [ ] **Step 3: Write the implementation**

`src/auth/service/email_sender.py`:
```python
"""Sends the email-verification link.

SMTP_HOST and friends already existed in config.py, unread. Unlike Google SSO (which fails
closed with 503 when unconfigured -- verifying without an audience would be a worse hole
than refusing), this cannot fail closed: every development and test environment lacking a
real SMTP server would be unable to register at all, which is unacceptable for a control
this central. When SMTP_HOST is empty (the default), the link is logged instead of sent.
"""
import logging
import smtplib
from email.message import EmailMessage

from src.auth.config import settings

logger = logging.getLogger(__name__)


class EmailSender:
    @staticmethod
    def send_verification_email(to_email: str, verification_link: str) -> None:
        body = (
            f"Click the link below to complete your registration:\n\n{verification_link}\n\n"
            "This link expires in 24 hours."
        )

        if not settings.SMTP_HOST:
            logger.info(
                "Verification email for %s (SMTP not configured, logging instead): %s",
                to_email, verification_link,
            )
            return

        message = EmailMessage()
        message["Subject"] = "Verify your email"
        message["From"] = settings.EMAILS_FROM_EMAIL or "no-reply@example.com"
        message["To"] = to_email
        message.set_content(body)

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_TLS:
                server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/unit/test_email_sender.py -v`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add src/auth/service/email_sender.py tests/unit/test_email_sender.py
git commit -m "feat(auth-service): add EmailSender with a dev-safe logging fallback"
```

---

### Task 3: Register + verify-email endpoints, and the full test-suite migration

This is the largest task: it changes `/auth/register`'s response contract, so every existing
test that registers a user must move to the new flow in the same commit that makes the
change, or the suite is red in between.

**Files:**
- Modify: `src/auth/schemas/auth.py` (add nothing yet — no new schema needed; `RegisterRequest` is unchanged)
- Modify: `src/auth/api/v1/endpoints/auth.py` (rewrite `register_user`, add `verify_email`)
- Modify: `tests/conftest.py` (add the `register_and_verify` fixture)
- Modify: `tests/integration/test_auth_endpoints.py` (rewrite)
- Modify: `tests/integration/test_user_isolation.py` (rewrite)
- Modify: `tests/integration/test_sso_endpoints.py` (update 5 call sites)

**Interfaces:**
- Consumes: `PendingRegistration` (Task 1), `EmailSender.send_verification_email` (Task 2), `settings.EMAIL_VERIFICATION_EXPIRE_HOURS`, `settings.BASE_URL`.
- Produces: `POST /auth/register` → `202 {"message": "Check your email to complete registration"}`. `GET /auth/verify-email?token=...` → `200 Token` (`access_token`, `refresh_token`, `token_type`) on success; `400` on invalid/expired token; `409` if the email is already a real `User`. A pytest fixture `register_and_verify(email, password="securepassword123", full_name=None) -> dict` (Token-shaped), available to every test in `tests/integration/` via `conftest.py`.

- [ ] **Step 1: Add the `register_and_verify` fixture to `tests/conftest.py`**

Add this to the end of `tests/conftest.py` (the existing `db`/`client` fixtures above are unchanged):
```python
@pytest.fixture
def register_and_verify(client, db):
    """Completes password registration end to end: POST /auth/register, then GET
    /auth/verify-email with the token from the resulting PendingRegistration row. Returns
    the Token dict (access_token, refresh_token, token_type) from the auto-login.

    Reads the token from the database rather than the log line EmailSender writes -- that
    is what a real client would extract from the URL in the email; the token is what
    matters, and the logging path is exercised on its own in test_email_sender.py.
    """
    from src.auth.models.pending_registration import PendingRegistration

    def _do(email, password="securepassword123", full_name=None):
        payload = {"email": email, "password": password}
        if full_name is not None:
            payload["full_name"] = full_name
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 202, response.text

        pending = db.query(PendingRegistration).filter(
            PendingRegistration.email == email
        ).first()
        assert pending is not None, f"no pending registration was created for {email}"

        verified = client.get(f"/api/v1/auth/verify-email?token={pending.token}")
        assert verified.status_code == 200, verified.text
        return verified.json()

    return _do
```

- [ ] **Step 2: Rewrite `register_user` and add `verify_email` in `auth.py`**

Replace the top of `src/auth/api/v1/endpoints/auth.py` (imports and the `register_user`
function) with:
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import logging
import secrets
from src.auth.api import deps
from src.auth.service.auth_service import AuthService
from src.auth.service.user_service import UserService
from src.auth.service.email_sender import EmailSender
from src.auth.schemas.auth import (
    LoginRequest, Token, PasswordResetRequest, PasswordResetConfirm, RefreshTokenRequest,
)
from src.auth.schemas.user import RegisterRequest
from src.auth.models.pending_registration import PendingRegistration
from src.auth.models.user import User
from src.auth.utils.password import get_password_hash
from src.auth.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register", status_code=status.HTTP_202_ACCEPTED)
def register_user(
    user_in: RegisterRequest,
    db: Session = Depends(deps.get_db)
):
    """
    Begin registration. Creates a PendingRegistration rather than a User -- the address is
    not claimed until the verification link is used. See
    docs/superpowers/specs/2026-09-24-auth-service-email-verification-design.md.
    """
    if UserService.get_user_by_email(db, user_in.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    existing_pending = db.query(PendingRegistration).filter(
        PendingRegistration.email == user_in.email
    ).first()
    if existing_pending is not None:
        # Rotate rather than error: nothing is claimed yet, and erroring would leak that
        # someone already tried this address. flush (not commit) so the DELETE is visible
        # to the INSERT below within the same transaction, without ending it early.
        db.delete(existing_pending)
        db.flush()

    token = secrets.token_urlsafe(32)
    pending = PendingRegistration(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        token=token,
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS),
    )
    db.add(pending)
    db.commit()

    verification_link = (
        f"{settings.BASE_URL}{settings.API_V1_STR}/auth/verify-email?token={token}"
    )
    EmailSender.send_verification_email(user_in.email, verification_link)

    return {"message": "Check your email to complete registration"}


@router.get("/verify-email", response_model=Token)
def verify_email(token: str, db: Session = Depends(deps.get_db)):
    """
    Complete registration: turn a valid, unexpired PendingRegistration into a User and
    auto-login.
    """
    pending = db.query(PendingRegistration).filter(
        PendingRegistration.token == token
    ).first()
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    expires_at = pending.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        # Worthless once expired -- deleting it releases the address for a clean retry
        # rather than leaving a dead row a future registration has to keep rotating past.
        db.delete(pending)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )

    if UserService.get_user_by_email(db, pending.email) is not None:
        # The address was claimed by another path -- most likely Google SSO, whose
        # email_verified claim is already equivalent proof -- while this registration sat
        # unverified. The stale attempt is discarded; the real account is untouched.
        db.delete(pending)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already registered",
        )

    user = User(
        email=pending.email,
        hashed_password=pending.hashed_password,
        full_name=pending.full_name,
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.delete(pending)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race against a concurrent claim of this email between the check above and
        # this commit.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This email is already registered",
        )
    db.refresh(user)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = AuthService.create_access_token_for_user(
        user, expires_delta=access_token_expires
    )
    refresh_token = AuthService.create_user_session(db, user).token

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
```

Leave `login_access_token`, `refresh_access_token`, `logout_user`, `initiate_password_reset`
and `reset_password` in the rest of the file exactly as they are.

- [ ] **Step 3: Rewrite `tests/integration/test_auth_endpoints.py`**

Replace the file's full contents with:
```python
from datetime import datetime, timedelta, timezone

from src.auth.models.pending_registration import PendingRegistration
from src.auth.models.user import User


def test_register_verify_and_login(client, db):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "securepassword123",
            "full_name": "Test User",
        },
    )
    assert response.status_code == 202, response.text
    assert db.query(User).filter(User.email == "test@example.com").first() is None
    pending = db.query(PendingRegistration).filter(
        PendingRegistration.email == "test@example.com"
    ).first()
    assert pending is not None

    verified = client.get(f"/api/v1/auth/verify-email?token={pending.token}")
    assert verified.status_code == 200, verified.text
    token_data = verified.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert db.query(PendingRegistration).filter(
        PendingRegistration.email == "test@example.com"
    ).first() is None

    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
    )
    assert response.status_code == 200
    user_info = response.json()
    assert user_info["email"] == "test@example.com"
    assert user_info["full_name"] == "Test User"


def test_registering_twice_rotates_the_pending_token(client, db):
    client.post(
        "/api/v1/auth/register",
        json={"email": "rotate@example.com", "password": "securepassword123"},
    )
    first_pending = db.query(PendingRegistration).filter(
        PendingRegistration.email == "rotate@example.com"
    ).first()
    first_token = first_pending.token

    client.post(
        "/api/v1/auth/register",
        json={"email": "rotate@example.com", "password": "securepassword123"},
    )
    assert db.query(PendingRegistration).filter(
        PendingRegistration.email == "rotate@example.com"
    ).count() == 1, "a second registration must rotate, not duplicate"

    stale = client.get(f"/api/v1/auth/verify-email?token={first_token}")
    assert stale.status_code == 400, stale.text


def test_expired_verification_token_is_refused_and_releases_the_address(client, db):
    client.post(
        "/api/v1/auth/register",
        json={"email": "expired@example.com", "password": "securepassword123"},
    )
    pending = db.query(PendingRegistration).filter(
        PendingRegistration.email == "expired@example.com"
    ).first()
    pending.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()

    response = client.get(f"/api/v1/auth/verify-email?token={pending.token}")
    assert response.status_code == 400, response.text

    retry = client.post(
        "/api/v1/auth/register",
        json={"email": "expired@example.com", "password": "anotherpassword1"},
    )
    assert retry.status_code == 202, retry.text


def test_verifying_after_the_address_was_claimed_by_sso_is_refused(client, db, monkeypatch):
    """The scenario the design exists for: an attacker's pending registration must not
    matter once the real owner has claimed the address through any path -- here, Google SSO
    racing ahead of a stale, unverified password registration. Builds a minimal local Google
    token rather than depending on test_sso_endpoints.py's fixtures, keeping this file's
    dependency on that module's internals at zero."""
    import jwt as pyjwt
    from cryptography.hazmat.primitives.asymmetric import rsa
    from src.auth.config import settings
    from src.auth.service import sso_service

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class _StubKey:
        key = private_key.public_key()

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    monkeypatch.setattr(
        sso_service._jwks_client, "get_signing_key_from_jwt", lambda token: _StubKey()
    )

    client.post(
        "/api/v1/auth/register",
        json={"email": "person@example.com", "password": "attackerpassword1"},
    )
    pending = db.query(PendingRegistration).filter(
        PendingRegistration.email == "person@example.com"
    ).first()

    claims = {
        "iss": "https://accounts.google.com",
        "aud": "test-client-id.apps.googleusercontent.com",
        "sub": "google-user-1",
        "email": "person@example.com",
        "email_verified": True,
        "name": "Real Owner",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    credential = pyjwt.encode(claims, private_key, algorithm="RS256")
    sso_response = client.post("/api/v1/sso/google", json={"credential": credential})
    assert sso_response.status_code == 200, sso_response.text

    response = client.get(f"/api/v1/auth/verify-email?token={pending.token}")
    assert response.status_code == 409, response.text
    assert db.query(User).filter(User.email == "person@example.com").count() == 1
    assert db.query(PendingRegistration).filter(
        PendingRegistration.email == "person@example.com"
    ).first() is None


def test_refresh_token(client, register_and_verify):
    tokens = register_and_verify("test2@example.com")

    response = client.post(
        "/api/v1/auth/refresh-token",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 200
    new_tokens = response.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    response = client.post(
        "/api/v1/auth/refresh-token",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert response.status_code == 401


def test_password_reset_reports_not_implemented(client):
    """Both handlers used to return success without doing anything -- /reset-password even
    answered "Password has been reset successfully" while leaving the password untouched.
    Until a reset-token model and a mail transport exist, they must say so."""
    forgot = client.post(
        "/api/v1/auth/forgot-password", json={"email": "nobody@example.com"}
    )
    assert forgot.status_code == 501, forgot.text

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "anything", "password": "newpassword123"},
    )
    assert reset.status_code == 501, reset.text
```

- [ ] **Step 4: Rewrite `tests/integration/test_user_isolation.py`**

Replace the file's full contents with:
```python
"""Cross-user isolation.

`UserService.get_user_by_id` once read `filter(user_id == user_id)` -- a Python tautology,
so SQLAlchemy emitted `WHERE true` and returned the first row in `users` for every id. That
made /auth/refresh-token hand out an access token for users.id == 1, and PUT /users/me
overwrite that account. The pre-existing suite could not see it because every test used a
single-user database.
"""

def _login(client, email):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword123"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_refresh_returns_a_token_for_the_same_user(client, register_and_verify):
    register_and_verify("first@example.com", full_name="first@example.com")
    register_and_verify("second@example.com", full_name="second@example.com")
    second = _login(client, "second@example.com")

    refreshed = client.post(
        "/api/v1/auth/refresh-token", json={"refresh_token": second["refresh_token"]}
    )
    assert refreshed.status_code == 200, refreshed.text

    me = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "second@example.com", "refresh must not switch identity"


def test_updating_me_does_not_touch_another_user(client, register_and_verify):
    register_and_verify("first@example.com", full_name="first@example.com")
    register_and_verify("second@example.com", full_name="second@example.com")
    second = _login(client, "second@example.com")

    updated = client.put(
        "/api/v1/users/me",
        json={"full_name": "Renamed By Second"},
        headers={"Authorization": f"Bearer {second['access_token']}"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["email"] == "second@example.com"

    # the first account must be untouched, and must still be able to log in
    still_first = _login(client, "first@example.com")
    me = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {still_first['access_token']}"},
    )
    assert me.json()["email"] == "first@example.com"
    assert me.json()["full_name"] == "first@example.com"


def test_user_responses_never_include_password_hashes(client, register_and_verify):
    register_and_verify("first@example.com")
    tokens = _login(client, "first@example.com")

    me = client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    assert "hashed_password" not in me.json()


def test_user_cannot_promote_themselves_to_superuser(client, register_and_verify):
    """PUT /users/me accepted the full UserUpdate and setattr'd whatever arrived, so any
    user could send {"is_superuser": true} and then read /users/."""
    register_and_verify("first@example.com")
    register_and_verify("second@example.com")
    second = _login(client, "second@example.com")
    auth = {"Authorization": f"Bearer {second['access_token']}"}

    assert client.get("/api/v1/users/", headers=auth).status_code == 403

    response = client.put(
        "/api/v1/users/me", json={"is_superuser": True, "full_name": "Sneaky"}, headers=auth
    )
    assert response.status_code in (200, 422)
    if response.status_code == 200:
        assert response.json().get("is_superuser") is not True

    assert client.get("/api/v1/users/", headers=auth).status_code == 403, (
        "self-update must not grant superuser"
    )


def test_user_cannot_deactivate_another_account_via_self_update(client, register_and_verify):
    """is_active is equally privileged -- flipping it is a self-inflicted lockout at best
    and a tampering vector at worst."""
    register_and_verify("first@example.com")
    first = _login(client, "first@example.com")
    auth = {"Authorization": f"Bearer {first['access_token']}"}

    response = client.put("/api/v1/users/me", json={"is_active": False}, headers=auth)
    assert response.status_code in (200, 422)

    assert _login(client, "first@example.com")["access_token"]


def test_logout_cannot_revoke_another_users_session(client, register_and_verify):
    register_and_verify("first@example.com")
    register_and_verify("second@example.com")
    first = _login(client, "first@example.com")
    second = _login(client, "second@example.com")

    response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": first["refresh_token"]},
        headers={"Authorization": f"Bearer {second['access_token']}"},
    )
    assert response.status_code != 200

    refreshed = client.post(
        "/api/v1/auth/refresh-token", json={"refresh_token": first["refresh_token"]}
    )
    assert refreshed.status_code == 200


def test_password_change_requires_the_current_password(client, register_and_verify):
    """A stolen access token is a bearer credential with a multi-day life. Without this
    check, a minute's use of one is enough to replace the password and own the account."""
    register_and_verify("first@example.com")
    first = _login(client, "first@example.com")
    auth = {"Authorization": f"Bearer {first['access_token']}"}

    refused = client.put(
        "/api/v1/users/me", json={"password": "attackerchosen1"}, headers=auth
    )
    assert refused.status_code == 400, refused.text

    wrong = client.put(
        "/api/v1/users/me",
        json={"password": "attackerchosen1", "current_password": "notmypassword"},
        headers=auth,
    )
    assert wrong.status_code == 400, wrong.text

    assert _login(client, "first@example.com")["access_token"]


def test_password_change_revokes_existing_sessions(client, register_and_verify):
    register_and_verify("first@example.com")
    first = _login(client, "first@example.com")
    stolen_refresh = first["refresh_token"]

    changed = client.put(
        "/api/v1/users/me",
        json={"password": "brandnewpassword1", "current_password": "securepassword123"},
        headers={"Authorization": f"Bearer {first['access_token']}"},
    )
    assert changed.status_code == 200, changed.text

    reused = client.post(
        "/api/v1/auth/refresh-token", json={"refresh_token": stolen_refresh}
    )
    assert reused.status_code == 401, "sessions must not outlive the password they were issued under"


def test_short_password_is_refused_on_self_update(client, register_and_verify):
    register_and_verify("first@example.com")
    first = _login(client, "first@example.com")

    response = client.put(
        "/api/v1/users/me",
        json={"password": "x", "current_password": "securepassword123"},
        headers={"Authorization": f"Bearer {first['access_token']}"},
    )
    assert response.status_code == 422, response.text


def test_null_password_is_a_client_error_not_a_crash(client, register_and_verify):
    """`password` is Optional, so an explicit null passed validation and reached
    get_password_hash(None), which raises."""
    register_and_verify("first@example.com")
    first = _login(client, "first@example.com")

    response = client.put(
        "/api/v1/users/me",
        json={"password": None, "current_password": "securepassword123"},
        headers={"Authorization": f"Bearer {first['access_token']}"},
    )
    assert response.status_code == 400, response.text

    assert _login(client, "first@example.com")["access_token"]


def test_registration_rejects_privileged_fields_in_the_body(client):
    """An earlier version of this asserted the field was *ignored*, which passed against the
    code it was written to guard -- Pydantic silently drops unknown fields, so a 200 proved
    nothing. Input schemas now reject them, which is a difference a test can see."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "sneaky@example.com",
            "password": "securepassword123",
            "is_superuser": True,
        },
    )
    assert response.status_code == 422, response.text

    assert client.post(
        "/api/v1/auth/login",
        json={"email": "sneaky@example.com", "password": "securepassword123"},
    ).status_code == 401, "the account must not have been created"


def test_self_update_cannot_change_email(client, register_and_verify):
    """Changing an address needed no password and no proof of owning the new one, so any
    authenticated user could take any unregistered address in a single request. Its real
    owner is then locked out permanently: registration answers 400, Google SSO answers 409."""
    attacker = register_and_verify("attacker@example.com")

    response = client.put(
        "/api/v1/users/me",
        json={"email": "ceo@example.com"},
        headers={"Authorization": f"Bearer {attacker['access_token']}"},
    )
    assert response.status_code == 422, response.text

    # the address is still free for its real owner -- registration now only begins the
    # flow, so 202 proves the address is unclaimed, not that a full account was made
    claimed = client.post(
        "/api/v1/auth/register",
        json={"email": "ceo@example.com", "password": "securepassword123"},
    )
    assert claimed.status_code == 202, claimed.text


def test_replaying_a_rotated_refresh_token_ends_every_session(client, register_and_verify):
    """Rotation alone does not survive theft: the thief rotates the stolen token and it is
    the owner's next refresh that fails, leaving the thief's chain live. A replay is treated
    as a compromised chain instead."""
    first = register_and_verify("first@example.com")
    stolen = first["refresh_token"]

    thief = client.post("/api/v1/auth/refresh-token", json={"refresh_token": stolen})
    assert thief.status_code == 200
    thief_chain = thief.json()["refresh_token"]

    replay = client.post("/api/v1/auth/refresh-token", json={"refresh_token": stolen})
    assert replay.status_code == 401

    assert client.post(
        "/api/v1/auth/refresh-token", json={"refresh_token": thief_chain}
    ).status_code == 401, "a replay must revoke every session, the thief's included"


def test_non_superuser_reading_another_id_is_forbidden_not_a_bad_request(client, register_and_verify):
    """Answered before the id is looked up, so a non-superuser cannot probe which ids exist;
    and 403 rather than the 400 this used to return."""
    first = register_and_verify("first@example.com")

    response = client.get(
        "/api/v1/users/999999",
        headers={"Authorization": f"Bearer {first['access_token']}"},
    )
    assert response.status_code == 403, response.text
```

- [ ] **Step 5: Update the 5 register call sites in `tests/integration/test_sso_endpoints.py`**

Leave the rest of the file untouched (fixtures `google_key`, `_id_token`, and every other
test). Apply these five replacements:

Replace:
```python
def test_google_does_not_take_over_a_password_account(client, db, google_key):
    """Pre-registration takeover: someone registers the victim's address with a password
    before the victim ever signs up. When the victim then arrives via Google, linking on a
    matching email alone would hand them the attacker's account, password and all."""
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": "person@example.com",
            "password": "attackerpassword1",
            "full_name": "Squatter",
        },
    )
    assert registered.status_code == 200, registered.text

    response = client.post("/api/v1/sso/google", json={"credential": _id_token(google_key)})
```
with:
```python
def test_google_does_not_take_over_a_password_account(client, db, register_and_verify, google_key):
    """Pre-registration takeover: someone registers the victim's address with a password
    before the victim ever signs up. When the victim then arrives via Google, linking on a
    matching email alone would hand them the attacker's account, password and all."""
    register_and_verify("person@example.com", password="attackerpassword1", full_name="Squatter")

    response = client.post("/api/v1/sso/google", json={"credential": _id_token(google_key)})
```

Replace:
```python
def test_link_google_to_a_password_account(client, db, google_key):
    """The remedy /sso/google's 409 for a password account points at, and previously did
    not have. After linking, the same Google identity logs the account straight in."""
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": "person@example.com", "password": "securepassword123"},
    )
    assert registered.status_code == 200, registered.text
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "person@example.com", "password": "securepassword123"},
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
```
with:
```python
def test_link_google_to_a_password_account(client, db, register_and_verify, google_key):
    """The remedy /sso/google's 409 for a password account points at, and previously did
    not have. After linking, the same Google identity logs the account straight in."""
    login = register_and_verify("person@example.com")
    auth = {"Authorization": f"Bearer {login['access_token']}"}
```

Replace:
```python
def test_link_google_requires_the_current_password(client, db, google_key):
    """A stolen bearer token linking a new, durable login method to the account is exactly
    the backdoor the password-change guard already exists to prevent; this is the same
    class of mutation."""
    client.post(
        "/api/v1/auth/register",
        json={"email": "person@example.com", "password": "securepassword123"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "person@example.com", "password": "securepassword123"},
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
```
with:
```python
def test_link_google_requires_the_current_password(client, db, register_and_verify, google_key):
    """A stolen bearer token linking a new, durable login method to the account is exactly
    the backdoor the password-change guard already exists to prevent; this is the same
    class of mutation."""
    login = register_and_verify("person@example.com")
    auth = {"Authorization": f"Bearer {login['access_token']}"}
```

Replace:
```python
def test_link_google_refuses_an_identity_linked_elsewhere(client, db, google_key):
    client.post(
        "/api/v1/sso/google", json={"credential": _id_token(google_key)}
    )  # creates person@example.com via SSO, linked to google-user-1

    client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "securepassword123"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "other@example.com", "password": "securepassword123"},
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
```
with:
```python
def test_link_google_refuses_an_identity_linked_elsewhere(client, db, register_and_verify, google_key):
    client.post(
        "/api/v1/sso/google", json={"credential": _id_token(google_key)}
    )  # creates person@example.com via SSO, linked to google-user-1

    login = register_and_verify("other@example.com")
    auth = {"Authorization": f"Bearer {login['access_token']}"}
```

Replace:
```python
def test_link_google_refuses_a_second_link_on_the_same_account(client, db, google_key):
    client.post(
        "/api/v1/auth/register",
        json={"email": "person@example.com", "password": "securepassword123"},
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "person@example.com", "password": "securepassword123"},
    )
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
```
with:
```python
def test_link_google_refuses_a_second_link_on_the_same_account(client, db, register_and_verify, google_key):
    login = register_and_verify("person@example.com")
    auth = {"Authorization": f"Bearer {login['access_token']}"}
```

- [ ] **Step 6: Run the full suite**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -v`
Expected: every test passes. Count them: the previous total was 49; Task 1 added 2, Task 2
added 2. `test_auth_endpoints.py` goes from 3 tests to 6 (its old `test_register_and_login`
is replaced by four new ones, net +3), and `test_user_isolation.py` and
`test_sso_endpoints.py` keep the same test count (their existing tests are rewritten in
place, none added or removed). Total: 49 + 2 + 2 + 3 = 56.

- [ ] **Step 7: Verify each new guard actually discriminates**

Following this branch's established practice, prove at least the two guards most likely to
be silently vacuous:

Temporarily remove the expiry check in `verify_email` (delete the `if expires_at <=
datetime.now(timezone.utc):` block and its body) and confirm
`test_expired_verification_token_is_refused_and_releases_the_address` fails. Restore it.

Temporarily remove the `if UserService.get_user_by_email(db, pending.email) is not None:`
race-check block in `verify_email` and confirm
`test_verifying_after_the_address_was_claimed_by_sso_is_refused` fails (it should now error
with an uncaught `IntegrityError`, not merely fail an assertion — that is the crash this
guard exists to prevent). Restore it.

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q`
Expected after restoring both: `56 passed`.

- [ ] **Step 8: Commit**

```bash
git add src/auth/api/v1/endpoints/auth.py tests/conftest.py tests/integration/test_auth_endpoints.py tests/integration/test_user_isolation.py tests/integration/test_sso_endpoints.py
git commit -m "feat(auth-service): require email verification to complete registration"
```

---

### Task 4: Resend verification

**Files:**
- Modify: `src/auth/schemas/auth.py` (add `ResendVerificationRequest`)
- Modify: `src/auth/api/v1/endpoints/auth.py` (add `resend_verification`)
- Test: `tests/integration/test_auth_endpoints.py` (append)

**Interfaces:**
- Consumes: `PendingRegistration`, `EmailSender.send_verification_email` (both from earlier tasks).
- Produces: `POST /auth/resend-verification` → always `200 {"message": "If a pending registration exists for this email, a new verification link has been sent"}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/integration/test_auth_endpoints.py`:
```python
def test_resend_verification_rotates_the_token(client, db):
    client.post(
        "/api/v1/auth/register",
        json={"email": "resend@example.com", "password": "securepassword123"},
    )
    first_pending = db.query(PendingRegistration).filter(
        PendingRegistration.email == "resend@example.com"
    ).first()
    first_token = first_pending.token

    response = client.post(
        "/api/v1/auth/resend-verification", json={"email": "resend@example.com"}
    )
    assert response.status_code == 200, response.text

    stale = client.get(f"/api/v1/auth/verify-email?token={first_token}")
    assert stale.status_code == 400, stale.text

    refreshed_pending = db.query(PendingRegistration).filter(
        PendingRegistration.email == "resend@example.com"
    ).first()
    verified = client.get(f"/api/v1/auth/verify-email?token={refreshed_pending.token}")
    assert verified.status_code == 200, verified.text


def test_resend_verification_answers_identically_regardless_of_state(client, register_and_verify):
    """Matches /forgot-password's enumeration-prevention: the same response for a pending
    registration, a completed account, and an address nobody has ever used."""
    register_and_verify("completed@example.com")
    client.post(
        "/api/v1/auth/register",
        json={"email": "pending@example.com", "password": "securepassword123"},
    )

    responses = [
        client.post("/api/v1/auth/resend-verification", json={"email": "pending@example.com"}),
        client.post("/api/v1/auth/resend-verification", json={"email": "completed@example.com"}),
        client.post("/api/v1/auth/resend-verification", json={"email": "nobody@example.com"}),
    ]
    bodies = {r.status_code for r in responses}
    messages = {r.json()["message"] for r in responses}
    assert bodies == {200}
    assert len(messages) == 1
```

- [ ] **Step 2: Run to verify they fail**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/integration/test_auth_endpoints.py -v -k resend`
Expected: FAIL with `404 Not Found` (the route does not exist yet)

- [ ] **Step 3: Add the schema**

Append to `src/auth/schemas/auth.py`:
```python
class ResendVerificationRequest(BaseModel):
    email: EmailStr
```

- [ ] **Step 4: Add the endpoint**

Add the import to `src/auth/api/v1/endpoints/auth.py`'s existing `from src.auth.schemas.auth
import (...)` line (append `ResendVerificationRequest` to that tuple), then add this
function anywhere after `verify_email`:
```python
@router.post("/resend-verification")
def resend_verification(request: ResendVerificationRequest, db: Session = Depends(deps.get_db)):
    """
    Resend a verification link. Always answers the same way regardless of whether a
    pending registration exists, matching /forgot-password's enumeration-prevention.
    """
    pending = db.query(PendingRegistration).filter(
        PendingRegistration.email == request.email
    ).first()
    if pending is not None:
        pending.token = secrets.token_urlsafe(32)
        pending.expires_at = datetime.now(timezone.utc) + timedelta(
            hours=settings.EMAIL_VERIFICATION_EXPIRE_HOURS
        )
        db.commit()
        verification_link = (
            f"{settings.BASE_URL}{settings.API_V1_STR}/auth/verify-email?token={pending.token}"
        )
        EmailSender.send_verification_email(request.email, verification_link)

    return {
        "message": "If a pending registration exists for this email, a new verification link has been sent"
    }
```

- [ ] **Step 5: Run to verify they pass**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q`
Expected: `58 passed`

- [ ] **Step 6: Commit**

```bash
git add src/auth/schemas/auth.py src/auth/api/v1/endpoints/auth.py tests/integration/test_auth_endpoints.py
git commit -m "feat(auth-service): add POST /auth/resend-verification"
```

---

### Task 5: Documentation

**Files:**
- Modify: `platforms/auth-service/auth-service/README.md`

**Interfaces:** none (docs only).

- [ ] **Step 1: Update the top-of-file summary bullet**

Find:
```
- **Email/Password Authentication**: registration, login, logout
```
Replace with:
```
- **Email/Password Authentication**: registration (gated on email verification), login, logout
```

- [ ] **Step 2: Update the endpoint list**

In the `### Authentication` section, change:
```
- `POST /api/v1/auth/register` - Register new user account
```
to:
```
- `POST /api/v1/auth/register` - Begin registration. Creates an unclaimed, expiring pending record and emails a verification link -- returns `202`, not a user. The address is not reserved until verified.
- `GET /api/v1/auth/verify-email?token=...` - Complete registration: creates the account and returns `Token` (auto-login). `400` if the token is invalid or expired; `409` if the address was claimed by another path (e.g. Google SSO) in the meantime.
- `POST /api/v1/auth/resend-verification` - Resend the verification link. Always answers identically regardless of whether the address has a pending registration, a completed account, or neither.
```

- [ ] **Step 3: Replace the "Registration can still squat" limitation**

There are two places this same limitation is described; both are stale after this task and
must be updated together, or the README contradicts itself.

Find this line (in the "📝 Not built" summary section):
```
- **Registration can still squat an unregistered address** (no email verification), which the SSO 409 turns into a lockout the same way. Linking Google to an existing account is now built (see SSO Security below); email verification at registration is not.
```
Replace it with:
```
- **Registering an address now requires proving control of it.** `/auth/register` no longer creates an account -- it creates an expiring, unclaimed record and emails a link. Nothing is reserved until that link is used, so an attacker who never verifies has claimed nothing: a later registration or Google SSO for that address proceeds normally.
```

Find this paragraph (in the `### SSO Security` section, right after the account-linking
bullet — it predates both this task and the account-linking endpoint, and describes both
as still open):
```
**Known limitation:** email addresses are never verified. Self-service email changes are therefore not accepted at all (422) — allowing them let any authenticated user take any unregistered address in one request and lock out its real owner, since registration then answers 400 and Google SSO answers 409. Registration can still squat an unregistered address, which the same 409 turns into a lockout. Closing that needs address verification at registration, plus the link endpoint.
```
Replace it with:
```
**Remaining limitation:** self-service email *changes* on `PUT /users/me` are still not accepted at all (422). Verifying a new address the same way registration now does is not built, so allowing changes would reopen the address-squatting problem registration itself no longer has — see Email Verification below.
```

- [ ] **Step 4: Fix the SMTP section header and add a mail delivery note**

This section's header is now wrong in a way this task makes worse if left alone: password
reset returns `501` and sends no mail at all, while email verification is the one real
consumer of these settings.

Find:
```
### SMTP Configuration (For Password Reset Emails)
- `SMTP_TLS`: Enable TLS (default: True)
- `SMTP_PORT`: SMTP port (default: 587)
- `SMTP_HOST`: SMTP hostname
- `SMTP_USER`: SMTP username
- `SMTP_PASSWORD`: SMTP password
- `EMAILS_FROM_EMAIL`: Sender email address
- `EMAILS_FROM_NAME`: Sender name
```
Replace with:
```
### SMTP Configuration (For Email Verification)
- `SMTP_TLS`: Enable TLS (default: True)
- `SMTP_PORT`: SMTP port (default: 587)
- `SMTP_HOST`: SMTP hostname
- `SMTP_USER`: SMTP username
- `SMTP_PASSWORD`: SMTP password
- `EMAILS_FROM_EMAIL`: Sender email address
- `EMAILS_FROM_NAME`: Sender name
- `EMAIL_VERIFICATION_EXPIRE_HOURS`: hours a registration's verification link stays valid (default: 24)
- `BASE_URL`: base URL used to build the verification link in the email (default: `http://localhost:8000`)

When `SMTP_HOST` is unset (the default), verification links are logged rather than emailed -- this keeps registration usable in development and tests without a real mail server. Configure `SMTP_HOST` to send real email. Password reset does not use these settings: it returns 501 and sends nothing.
```

- [ ] **Step 5: Retitle the matching troubleshooting section**

Same staleness, in the troubleshooting section further down: this heading and its advice
are about SMTP connectivity, which now belongs to email verification, not password reset.

Find:
```
**Email/Password Reset Issues**
- Verify SMTP server connectivity and credentials
- Check `EMAILS_FROM_EMAIL` and `EMAILS_FROM_NAME` settings
- Test email delivery independently of application
```
Replace with:
```
**Email Verification Issues**
- Verify SMTP server connectivity and credentials
- Check `EMAILS_FROM_EMAIL` and `EMAILS_FROM_NAME` settings
- Test email delivery independently of application
- With `SMTP_HOST` unset, verification links are logged instead -- check application logs at INFO level rather than a mail server
```

- [ ] **Step 6: Run the full suite one last time**

Run: `rm -f test.db && SECRET_KEY=test-secret .venv/Scripts/python.exe -m pytest tests/ -q`
Expected: `58 passed`

- [ ] **Step 7: Commit**

```bash
git add platforms/auth-service/auth-service/README.md
git commit -m "docs(auth-service): document email verification at registration"
```
