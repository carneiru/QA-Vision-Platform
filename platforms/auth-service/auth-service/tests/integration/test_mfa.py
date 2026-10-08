"""TOTP MFA: enrollment, the login challenge, recovery codes, disable.
SSO sign-ins never hit the challenge — the identity provider owns that factor."""

import pyotp
import pytest

EMAIL = "mfa@example.com"


def _auth(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def _enroll_and_confirm(client, tokens):
    enroll = client.post("/api/v1/auth/mfa/enroll", headers=_auth(tokens))
    assert enroll.status_code == 200, enroll.text
    secret = enroll.json()["secret"]
    assert enroll.json()["otpauth_uri"].startswith("otpauth://totp/")

    code = pyotp.TOTP(secret).now()
    confirm = client.post("/api/v1/auth/mfa/confirm", json={"code": code}, headers=_auth(tokens))
    assert confirm.status_code == 200, confirm.text
    recovery = confirm.json()["recovery_codes"]
    assert len(recovery) == 8
    return secret, recovery


def test_enroll_confirm_then_login_requires_a_code(client, register_and_verify):
    tokens = register_and_verify(EMAIL)
    secret, _ = _enroll_and_confirm(client, tokens)

    login = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "securepassword123"})
    assert login.status_code == 200, login.text
    body = login.json()
    assert body.get("mfa_required") is True
    assert "access_token" not in body
    assert "set-cookie" not in {k.lower() for k in login.headers}  # no session yet

    verify = client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_token": body["mfa_token"], "code": pyotp.TOTP(secret).now()},
    )
    assert verify.status_code == 200, verify.text
    assert "access_token" in verify.json()
    assert "qeos_refresh=" in verify.headers.get("set-cookie", "")


def test_wrong_code_is_rejected_and_token_reusable_until_expiry(client, register_and_verify):
    tokens = register_and_verify(EMAIL)
    _enroll_and_confirm(client, tokens)
    login = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "securepassword123"})
    mfa_token = login.json()["mfa_token"]

    bad = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": mfa_token, "code": "000000"})
    assert bad.status_code == 401


def test_recovery_code_signs_in_once(client, register_and_verify):
    tokens = register_and_verify(EMAIL)
    _, recovery = _enroll_and_confirm(client, tokens)
    code = recovery[0]

    login = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "securepassword123"})
    mfa_token = login.json()["mfa_token"]
    first = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": mfa_token, "code": code})
    assert first.status_code == 200, first.text

    login2 = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "securepassword123"})
    second = client.post(
        "/api/v1/auth/mfa/verify", json={"mfa_token": login2.json()["mfa_token"], "code": code},
    )
    assert second.status_code == 401  # single use


def test_confirm_with_a_wrong_code_does_not_enable(client, register_and_verify):
    tokens = register_and_verify(EMAIL)
    client.post("/api/v1/auth/mfa/enroll", headers=_auth(tokens))
    confirm = client.post("/api/v1/auth/mfa/confirm", json={"code": "000000"}, headers=_auth(tokens))
    # 400, not 401: the caller is signed in, only the code is wrong. A 401 reads as an
    # expired session, and the dashboard would refresh and resubmit the code
    assert confirm.status_code == 400

    login = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "securepassword123"})
    assert "access_token" in login.json()  # MFA never became active


def test_disable_requires_a_valid_code_and_restores_plain_login(client, register_and_verify):
    tokens = register_and_verify(EMAIL)
    secret, _ = _enroll_and_confirm(client, tokens)

    bad = client.post("/api/v1/auth/mfa/disable", json={"code": "000000"}, headers=_auth(tokens))
    assert bad.status_code == 400

    ok = client.post(
        "/api/v1/auth/mfa/disable",
        json={"code": pyotp.TOTP(secret).now()},
        headers=_auth(tokens),
    )
    assert ok.status_code == 200, ok.text

    login = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "securepassword123"})
    assert "access_token" in login.json()


def test_mfa_verify_rejects_a_garbage_token(client):
    response = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": "nonsense", "code": "123456"})
    assert response.status_code == 401


def _signed(claims):
    from datetime import datetime, timedelta, timezone
    import jwt
    from src.auth.config import settings
    claims = {"exp": datetime.now(timezone.utc) + timedelta(minutes=5), **claims}
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def test_the_mfa_challenge_token_is_not_an_access_token(client, register_and_verify):
    tokens = register_and_verify(EMAIL)
    _enroll_and_confirm(client, tokens)
    login = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "securepassword123"})
    mfa_token = login.json()["mfa_token"]

    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {mfa_token}"})
    assert me.status_code == 401




@pytest.mark.parametrize("extra", [{"purpose": "mfa"}, {"token_type": "service"}, {"purpose": "password_reset"}])
def test_tokens_with_purpose_or_token_type_are_401_on_users_me(client, register_and_verify, extra):
    tokens = register_and_verify(EMAIL)
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    user_id = me.json()["id"]
    forged = _signed({"sub": str(user_id), **extra})
    assert client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_users_me_reports_whether_two_factor_is_on(client, register_and_verify):
    tokens = register_and_verify(EMAIL)
    me = client.get("/api/v1/users/me", headers=_auth(tokens))
    assert me.json()["mfa_enabled"] is False
    _enroll_and_confirm(client, tokens)
    me = client.get("/api/v1/users/me", headers=_auth(tokens))
    assert me.json()["mfa_enabled"] is True
    # The secret itself is never part of the response
    assert "mfa_secret" not in me.json()
