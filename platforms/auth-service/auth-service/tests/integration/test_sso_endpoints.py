"""SSO endpoint tests.

Before this was fixed, `SSOService` ignored the credential entirely and returned a hardcoded
identity, and the endpoint then minted real access and refresh tokens for it -- any string
would have logged you in as user@gmail.com, creating that account if absent.

The tests that matter here are the ones that actually reach signature verification. An
earlier version of this file only ever exercised the unconfigured-client-id guard, so the
verification code was never executed by any test -- which is exactly how two bugs in it
(an issuer check that rejected every real token, and a missing import that 500'd every
first-time user) shipped unnoticed. `signing_key` below exists to prevent that recurring:
it substitutes a locally-generated RSA key for Google's, so the full decode path runs
offline and deterministically.
"""
import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from src.auth.config import settings
from src.auth.models.oauth import OAuthAccount
from src.auth.models.user import User
from src.auth.service import sso_service

TEST_CLIENT_ID = "test-client-id.apps.googleusercontent.com"


@pytest.fixture
def google_key(monkeypatch):
    """Stand in for Google's signing key so verification runs without network access."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class _StubKey:
        key = private_key.public_key()

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", TEST_CLIENT_ID)
    monkeypatch.setattr(
        sso_service._jwks_client, "get_signing_key_from_jwt", lambda token: _StubKey()
    )
    return private_key


def _id_token(private_key, **overrides):
    from datetime import datetime, timedelta, timezone

    claims = {
        "iss": "https://accounts.google.com",
        "aud": TEST_CLIENT_ID,
        "sub": "google-user-1",
        "email": "person@example.com",
        "email_verified": True,
        "name": "A Person",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    claims.update(overrides)
    return pyjwt.encode(claims, private_key, algorithm="RS256")


# --- the happy path: this is what proves verification actually works ------------------

def test_valid_google_token_logs_in_and_creates_user(client, db, google_key):
    response = client.post("/api/v1/sso/google", json={"credential": _id_token(google_key)})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["access_token"] and body["refresh_token"]

    created = db.query(User).filter(User.email == "person@example.com").first()
    assert created is not None
    assert created.hashed_password is None, "an SSO user must not get a usable password"


def test_returning_google_user_does_not_duplicate(client, db, google_key):
    first = client.post("/api/v1/sso/google", json={"credential": _id_token(google_key)})
    assert first.status_code == 200
    second = client.post("/api/v1/sso/google", json={"credential": _id_token(google_key)})
    assert second.status_code == 200

    assert db.query(User).filter(User.email == "person@example.com").count() == 1


# --- rejections, all reaching real verification ----------------------------------------

def test_token_signed_by_someone_else_is_rejected(client, db, google_key):
    """The core of the fix: a well-formed token Google did not sign must not authenticate."""
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = _id_token(attacker_key, email="attacker@example.com")

    response = client.post("/api/v1/sso/google", json={"credential": forged})

    assert response.status_code != 200
    assert db.query(User).filter(User.email == "attacker@example.com").first() is None


def test_token_for_a_different_google_client_is_rejected(client, db, google_key):
    """Correctly signed by Google, but minted for another application's client id."""
    wrong_aud = _id_token(google_key, aud="someone-elses-app.apps.googleusercontent.com")

    response = client.post("/api/v1/sso/google", json={"credential": wrong_aud})

    assert response.status_code != 200
    assert db.query(User).filter(User.email == "person@example.com").first() is None


def test_expired_token_is_rejected(client, db, google_key):
    from datetime import datetime, timedelta, timezone

    expired = _id_token(google_key, exp=datetime.now(timezone.utc) - timedelta(minutes=1))

    response = client.post("/api/v1/sso/google", json={"credential": expired})

    assert response.status_code != 200
    assert db.query(User).filter(User.email == "person@example.com").first() is None


def test_token_from_an_unexpected_issuer_is_rejected(client, db, google_key):
    impostor = _id_token(google_key, iss="https://accounts.evil.example")

    response = client.post("/api/v1/sso/google", json={"credential": impostor})

    assert response.status_code != 200
    assert db.query(User).filter(User.email == "person@example.com").first() is None


@pytest.mark.parametrize("email_verified", [False, "false", None, 0])
def test_unverified_email_is_rejected(client, db, google_key, email_verified):
    """Only an explicit boolean true counts. An absent claim, or the string "false" that
    some Google surfaces emit, must not be read as verified."""
    claims = {"email_verified": email_verified} if email_verified is not None else {}
    token = _id_token(google_key, **claims) if claims else _id_token(google_key)
    if not claims:
        # rebuild without the claim entirely
        token = pyjwt.encode(
            {k: v for k, v in pyjwt.decode(token, options={"verify_signature": False}).items()
             if k != "email_verified"},
            google_key, algorithm="RS256",
        )

    response = client.post("/api/v1/sso/google", json={"credential": token})

    assert response.status_code != 200
    assert db.query(User).filter(User.email == "person@example.com").first() is None


# --- account linking --------------------------------------------------------------------

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

    assert response.status_code == 409, response.text
    assert "access_token" not in response.json()
    assert db.query(OAuthAccount).count() == 0, "no link may be created for a password account"


def test_a_different_google_identity_cannot_claim_a_linked_account(client, db, google_key):
    """A recycled or aliased mailbox presenting a new Google `sub` must not displace the
    identity already linked to the account."""
    first = client.post("/api/v1/sso/google", json={"credential": _id_token(google_key)})
    assert first.status_code == 200

    impostor = _id_token(google_key, sub="google-user-2")
    response = client.post("/api/v1/sso/google", json={"credential": impostor})

    assert response.status_code == 409, response.text
    links = db.query(OAuthAccount).all()
    assert [link.provider_user_id for link in links] == ["google-user-1"]


# --- guards that do not reach verification ---------------------------------------------

def test_garbage_google_credential_is_rejected(client, db):
    """A junk credential must not produce a token, and must not create a user."""
    response = client.post("/api/v1/sso/google", json={"credential": "not-a-real-token"})

    assert response.status_code != 200
    body = response.json()
    assert "access_token" not in body
    assert "refresh_token" not in body
    assert db.query(User).filter(User.email == "user@gmail.com").first() is None


def test_google_sso_fails_closed_when_client_id_unconfigured(client, db, monkeypatch):
    """With no GOOGLE_CLIENT_ID we refuse outright rather than verify without an audience --
    an empty audience would accept ID tokens minted for any other Google app."""
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")

    response = client.post("/api/v1/sso/google", json={"credential": "anything"})

    assert response.status_code != 200
    assert "access_token" not in response.json()


@pytest.mark.parametrize("provider", ["github", "azure"])
def test_unimplemented_providers_report_501(client, provider):
    """These previously returned hardcoded identities. They must now fail honestly rather
    than either pretending or crashing with a 500."""
    response = client.post(f"/api/v1/sso/{provider}", json={"code": "irrelevant"})

    assert response.status_code == 501
