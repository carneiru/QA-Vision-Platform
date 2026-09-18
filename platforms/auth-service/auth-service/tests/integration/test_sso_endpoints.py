"""SSO endpoint tests.

The point of this file is the first test: before this was fixed, `SSOService` ignored the
credential entirely and returned a hardcoded identity, and the endpoint then minted real
access and refresh tokens for it. Any string -- or no valid token at all -- would have
logged you in as user@gmail.com, creating that account if it did not exist.
"""
import pytest
from src.auth.config import settings
from src.auth.models.user import User


def test_garbage_google_credential_is_rejected(client, db):
    """A junk credential must not produce a token, and must not create a user."""
    response = client.post("/api/v1/sso/google", json={"credential": "not-a-real-token"})

    assert response.status_code != 200, "a garbage credential must never authenticate"
    body = response.json()
    assert "access_token" not in body
    assert "refresh_token" not in body

    # The old mock would have created this account as a side effect of "logging in".
    assert db.query(User).filter(User.email == "user@gmail.com").first() is None


def test_google_sso_fails_closed_when_client_id_unconfigured(client, db, monkeypatch):
    """With no GOOGLE_CLIENT_ID we must refuse outright rather than verify without an
    audience -- an empty audience would accept ID tokens minted for any other Google app."""
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")

    response = client.post("/api/v1/sso/google", json={"credential": "anything"})

    assert response.status_code != 200
    assert "access_token" not in response.json()
    assert db.query(User).filter(User.email == "user@gmail.com").first() is None


def test_google_sso_rejects_a_structurally_valid_but_unsigned_jwt(client, db):
    """A well-formed JWT that Google did not sign must still be rejected -- verification has
    to check the signature against Google's keys, not merely parse the token."""
    import jwt as pyjwt

    forged = pyjwt.encode(
        {"sub": "1", "email": "attacker@example.com", "aud": "whatever", "iss": "https://accounts.google.com"},
        "a-key-google-does-not-have",
        algorithm="HS256",
    )

    response = client.post("/api/v1/sso/google", json={"credential": forged})

    assert response.status_code != 200
    assert db.query(User).filter(User.email == "attacker@example.com").first() is None


@pytest.mark.parametrize("provider", ["github", "azure"])
def test_unimplemented_providers_report_501(client, provider):
    """These previously returned hardcoded identities. They must now fail honestly rather
    than either pretending or crashing with a 500."""
    response = client.post(f"/api/v1/sso/{provider}", json={"code": "irrelevant"})

    assert response.status_code == 501
