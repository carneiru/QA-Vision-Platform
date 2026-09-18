"""THROWAWAY probe tests - delete before finishing."""
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
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class _StubKey:
        key = private_key.public_key()

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", TEST_CLIENT_ID)
    monkeypatch.setattr(
        sso_service._jwks_client, "get_signing_key_from_jwt", lambda token: _StubKey()
    )
    return private_key


def _id_token(key, sub="google-user-1", email="person@example.com", **overrides):
    import time
    claims = {
        "iss": "https://accounts.google.com",
        "aud": TEST_CLIENT_ID,
        "sub": sub,
        "email": email,
        "email_verified": True,
        "name": "Person",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    claims.update(overrides)
    return pyjwt.encode(claims, key, algorithm="RS256")


def _register(client, email, password="testpassword1"):
    r = client.post("/api/v1/auth/register",
                    json={"email": email, "password": password, "full_name": "X"})
    assert r.status_code == 200, r.text
    return r


def _login(client, email, password="testpassword1"):
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


# ---- PROBE 1: email change collides with an existing user -> uncaught IntegrityError
def test_probe_email_change_collision(client):
    _register(client, "a@example.com")
    _register(client, "b@example.com")
    tok = _login(client, "a@example.com")
    r = client.put("/api/v1/users/me", json={"email": "b@example.com"},
                   headers={"Authorization": f"Bearer {tok['access_token']}"})
    print("PROBE1 status:", r.status_code)


# ---- PROBE 2: unverified email change squats an address -> permanent SSO lockout
def test_probe_email_squat_locks_out_sso_victim(client, db, google_key):
    _register(client, "attacker@example.com")
    tok = _login(client, "attacker@example.com")
    r = client.put("/api/v1/users/me", json={"email": "person@example.com"},
                   headers={"Authorization": f"Bearer {tok['access_token']}"})
    print("PROBE2 put status:", r.status_code, r.json().get("email"))
    sso = client.post("/api/v1/sso/google", json={"credential": _id_token(google_key)})
    print("PROBE2 victim sso status:", sso.status_code, sso.text[:120])
    # attacker still logs in with their password on the victim's address
    a = client.post("/api/v1/auth/login",
                    json={"email": "person@example.com", "password": "testpassword1"})
    print("PROBE2 attacker login as victim address:", a.status_code)


# ---- PROBE 3: password change w/o current password, no min length, sessions survive
def test_probe_password_change(client):
    _register(client, "a@example.com")
    tok = _login(client, "a@example.com")
    auth = {"Authorization": f"Bearer {tok['access_token']}"}
    r = client.put("/api/v1/users/me", json={"password": "x"}, headers=auth)
    print("PROBE3 set 1-char password status:", r.status_code)
    n = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "x"})
    print("PROBE3 login with 1-char password:", n.status_code)
    # old refresh token still valid after password change?
    rt = client.post("/api/v1/auth/refresh-token", json={"refresh_token": tok["refresh_token"]})
    print("PROBE3 old refresh token after password change:", rt.status_code)


# ---- PROBE 4: deactivated user can still obtain tokens via SSO
def test_probe_deactivated_user_sso(client, db, google_key):
    first = client.post("/api/v1/sso/google", json={"credential": _id_token(google_key)})
    assert first.status_code == 200
    u = db.query(User).filter(User.email == "person@example.com").first()
    u.is_active = False
    db.commit()
    again = client.post("/api/v1/sso/google", json={"credential": _id_token(google_key)})
    print("PROBE4 deactivated user sso status:", again.status_code)
    print("PROBE4 got access token:", "access_token" in again.json())
    # compare with password login, which does check is_active
    _register(client, "b@example.com")
    ub = db.query(User).filter(User.email == "b@example.com").first()
    ub.is_active = False
    db.commit()
    pw = client.post("/api/v1/auth/login",
                     json={"email": "b@example.com", "password": "testpassword1"})
    print("PROBE4 deactivated password login status:", pw.status_code)


# ---- PROBE 5: register with is_superuser true (schema accepts the field)
def test_probe_register_superuser(client, db):
    r = client.post("/api/v1/auth/register",
                    json={"email": "sup@example.com", "password": "testpassword1",
                          "is_superuser": True, "is_active": True})
    print("PROBE5 register status:", r.status_code, r.json().get("is_superuser"))
    u = db.query(User).filter(User.email == "sup@example.com").first()
    print("PROBE5 db is_superuser:", u.is_superuser)


# ---- PROBE 6: SSO-created passwordless user, second Google sub, after link deleted
def test_probe_sso_user_sets_password_then_relogin(client, db, google_key):
    first = client.post("/api/v1/sso/google", json={"credential": _id_token(google_key)})
    assert first.status_code == 200
    tok = first.json()
    r = client.put("/api/v1/users/me", json={"password": "newpassword1"},
                   headers={"Authorization": f"Bearer {tok['access_token']}"})
    print("PROBE6 sso user sets password:", r.status_code)
    again = client.post("/api/v1/sso/google", json={"credential": _id_token(google_key)})
    print("PROBE6 sso re-login after setting password:", again.status_code)
