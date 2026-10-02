"""TOTP MFA: enrollment, the login challenge, recovery codes, disable.
SSO sign-ins never hit the challenge — the identity provider owns that factor."""

import pyotp

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
    assert "qav_refresh=" in verify.headers.get("set-cookie", "")


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
    assert confirm.status_code == 401

    login = client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "securepassword123"})
    assert "access_token" in login.json()  # MFA never became active


def test_disable_requires_a_valid_code_and_restores_plain_login(client, register_and_verify):
    tokens = register_and_verify(EMAIL)
    secret, _ = _enroll_and_confirm(client, tokens)

    bad = client.post("/api/v1/auth/mfa/disable", json={"code": "000000"}, headers=_auth(tokens))
    assert bad.status_code == 401

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
