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


def test_register_commit_race_returns_a_clean_400(client, db, monkeypatch):
    """Two concurrent POST /auth/register for the same address can both pass the
    existing-pending check before either commits -- the loser's INSERT then violates
    PendingRegistration.email's UNIQUE constraint. Without a guard on register_user's
    commit, that would 500 instead of failing gracefully. A true race can't be produced in
    a single-threaded test, so it's simulated directly: a conflicting row is inserted first,
    then the existing-pending lookup is patched to miss it (as it would under a genuine
    race), forcing the final commit itself to be what fails."""
    racer = PendingRegistration(
        email="racer@example.com",
        hashed_password="irrelevant",
        token="irrelevant-token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(racer)
    db.commit()

    original_query = db.query

    def query_missing_the_race(model, *args, **kwargs):
        if model is PendingRegistration:
            class _EmptyQuery:
                def filter(self, *a, **k):
                    return self

                def first(self):
                    return None

            return _EmptyQuery()
        return original_query(model, *args, **kwargs)

    monkeypatch.setattr(db, "query", query_missing_the_race)

    response = client.post(
        "/api/v1/auth/register",
        json={"email": "racer@example.com", "password": "securepassword123"},
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Email already registered"


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
    pending_token = pending.token

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

    response = client.get(f"/api/v1/auth/verify-email?token={pending_token}")
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
