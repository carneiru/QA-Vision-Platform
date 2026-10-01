"""Microsoft (Entra ID) SSO. A locally generated RSA key stands in for Microsoft's, so the full
verification path runs offline, as the Google tests do."""
import logging
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWKClientConnectionError

from src.auth.config import settings
from src.auth.models.oauth import OAuthAccount
from src.auth.models.user import User
from src.auth.service import sso_service

SIGN_IN = "/api/v1/sso/microsoft"
CLIENT_ID = "11111111-2222-3333-4444-555555555555"
TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER_TENANT = "99999999-8888-7777-6666-555555555555"
OID = "00000000-0000-0000-0000-000000000001"
DROP = object()


@pytest.fixture
def microsoft_key(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    class _StubKey:
        key = private_key.public_key()

    monkeypatch.setattr(settings, "AZURE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(settings, "AZURE_ALLOWED_TENANTS", f"{TENANT},{OTHER_TENANT}")
    monkeypatch.setattr(settings, "AZURE_TENANT_ID", "")
    monkeypatch.setattr(sso_service._microsoft_jwks_client, "get_signing_key_from_jwt", lambda token: _StubKey())
    return private_key


def ms_token(private_key, key=None, algorithm="RS256", **overrides):
    now = datetime.now(timezone.utc)
    tid = overrides.pop("tid", TENANT)
    claims = {
        "ver": "2.0",
        "iss": f"https://login.microsoftonline.com/{TENANT if tid is DROP else tid}/v2.0",
        "aud": CLIENT_ID,
        "tid": tid,
        "oid": OID,
        "sub": "pairwise-subject",
        "email": "ann@example.com",
        "preferred_username": "ann@example.com",
        "name": "Ann Example",
        "nbf": now - timedelta(minutes=1),
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    claims = {name: value for name, value in claims.items() if value is not DROP}
    return pyjwt.encode(claims, private_key if key is None else key, algorithm=algorithm)


def sign_in(client, token):
    return client.post(SIGN_IN, json={"credential": token})


def test_a_valid_token_signs_in_and_creates_a_passwordless_user(client, db, microsoft_key):
    response = sign_in(client, ms_token(microsoft_key))

    assert response.status_code == 200, response.text
    assert response.json()["access_token"] and response.json()["refresh_token"]
    user = db.query(User).filter(User.email == "ann@example.com").one()
    assert user.hashed_password is None and user.full_name == "Ann Example"
    link = db.query(OAuthAccount).filter(OAuthAccount.user_id == user.id).one()
    assert (link.provider, link.provider_user_id) == ("microsoft", f"{TENANT}:{OID}")


def test_a_returning_user_is_found_by_identity_even_if_the_email_changed(client, db, microsoft_key):
    assert sign_in(client, ms_token(microsoft_key)).status_code == 200
    again = sign_in(client, ms_token(microsoft_key, email="ann.renamed@example.com"))

    assert again.status_code == 200, again.text
    assert db.query(User).count() == 1
    assert db.query(User).one().email == "ann@example.com"  # not written back


@pytest.mark.parametrize("case, overrides", [
    ("wrong_audience", {"aud": "someone-elses-app"}),
    ("expired", {"exp": datetime.now(timezone.utc) - timedelta(minutes=1)}),
    ("not_yet_valid", {"nbf": datetime.now(timezone.utc) + timedelta(minutes=10)}),
    ("tenant_not_allowed", {"tid": "12345678-0000-0000-0000-000000000000"}),
    ("iss_other_tenant", {"iss": f"https://login.microsoftonline.com/{OTHER_TENANT}/v2.0"}),
    ("v1_token", {"ver": "1.0"}),
    ("v1_issuer", {"iss": f"https://sts.windows.net/{TENANT}/"}),
    ("missing_tid", {"tid": DROP}),
    ("missing_oid", {"oid": DROP}),
    ("missing_nbf", {"nbf": DROP}),
])
def test_refused_tokens(client, db, microsoft_key, case, overrides):
    response = sign_in(client, ms_token(microsoft_key, **overrides))

    assert response.status_code == 400, response.text
    assert response.json() == {"detail": "Invalid Microsoft token"}
    assert db.query(User).count() == 0


@pytest.mark.parametrize("case", ["hs256", "none", "other_key", "garbage"])
def test_forged_tokens_are_refused(client, db, microsoft_key, case):
    if case == "hs256":
        token = ms_token(microsoft_key, key="a-shared-secret", algorithm="HS256")
    elif case == "none":
        token = pyjwt.encode({"tid": TENANT, "oid": OID, "aud": CLIENT_ID}, None, algorithm="none")
    elif case == "other_key":
        token = ms_token(rsa.generate_private_key(public_exponent=65537, key_size=2048))
    else:
        token = "not-a-jwt"

    response = sign_in(client, token)
    assert response.status_code == 400
    assert db.query(User).count() == 0


def test_a_refused_tenant_is_logged(client, microsoft_key, caplog):
    stranger = "12345678-0000-0000-0000-000000000000"
    with caplog.at_level(logging.WARNING, logger="src.auth.service.sso_service"):
        sign_in(client, ms_token(microsoft_key, tid=stranger))
    assert stranger in caplog.text


def test_allowed_tenants_are_case_insensitive(client, monkeypatch, microsoft_key):
    monkeypatch.setattr(settings, "AZURE_ALLOWED_TENANTS", TENANT.upper())
    assert sign_in(client, ms_token(microsoft_key)).status_code == 200


def test_azure_tenant_id_is_the_fallback_allowlist(client, monkeypatch, microsoft_key):
    monkeypatch.setattr(settings, "AZURE_ALLOWED_TENANTS", "")
    monkeypatch.setattr(settings, "AZURE_TENANT_ID", TENANT)
    assert sign_in(client, ms_token(microsoft_key)).status_code == 200


@pytest.mark.parametrize("setting", ["AZURE_CLIENT_ID", "AZURE_ALLOWED_TENANTS"])
def test_not_configured_is_503(client, monkeypatch, microsoft_key, setting):
    monkeypatch.setattr(settings, setting, "")
    response = sign_in(client, ms_token(microsoft_key))
    assert response.status_code == 503
    assert response.json() == {"detail": "Microsoft SSO is not configured"}


def test_microsoft_key_outage_is_503(client, monkeypatch, microsoft_key):
    def unreachable(token):
        raise PyJWKClientConnectionError("Fail to fetch data from the url")

    monkeypatch.setattr(sso_service._microsoft_jwks_client, "get_signing_key_from_jwt", unreachable)
    response = sign_in(client, ms_token(microsoft_key))
    assert response.status_code == 503
    assert response.json() == {"detail": "Microsoft sign-in is temporarily unavailable"}


def test_preferred_username_is_used_without_an_email_claim(client, db, microsoft_key):
    response = sign_in(client, ms_token(microsoft_key, email=DROP, preferred_username="ann@example.com"))
    assert response.status_code == 200, response.text
    assert db.query(User).one().email == "ann@example.com"


@pytest.mark.parametrize("overrides", [
    {"email": DROP, "preferred_username": DROP},
    {"email": DROP, "preferred_username": "ann"},
    {"email": "not an email", "preferred_username": DROP},
    # Passes a naive check but not the user model's EmailStr: used to be a 500
    {"email": "ann@corp.local", "preferred_username": DROP},
])
def test_an_account_without_an_email_is_refused(client, db, microsoft_key, overrides):
    response = sign_in(client, ms_token(microsoft_key, **overrides))
    assert response.status_code == 400
    assert response.json() == {"detail": "Microsoft account has no email address"}
    assert db.query(User).count() == 0


def test_an_existing_account_with_the_email_is_not_taken_over(client, db, microsoft_key, register_and_verify):
    register_and_verify("ann@example.com")
    response = sign_in(client, ms_token(microsoft_key))

    assert response.status_code == 409
    assert "/api/v1/users/me/link/microsoft" in response.json()["detail"]
    assert db.query(OAuthAccount).count() == 0


def test_the_same_oid_in_another_tenant_is_another_identity(client, db, microsoft_key):
    assert sign_in(client, ms_token(microsoft_key)).status_code == 200
    other = sign_in(client, ms_token(microsoft_key, tid=OTHER_TENANT, email="ann@other.example.com"))

    assert other.status_code == 200, other.text
    ids = sorted(link.provider_user_id for link in db.query(OAuthAccount))
    assert ids == sorted([f"{TENANT}:{OID}", f"{OTHER_TENANT}:{OID}"])
    assert db.query(User).count() == 2


def test_an_inactive_user_is_refused(client, db, microsoft_key):
    assert sign_in(client, ms_token(microsoft_key)).status_code == 200
    user = db.query(User).one()
    user.is_active = False
    db.commit()

    response = sign_in(client, ms_token(microsoft_key))
    assert response.status_code == 400
    assert response.json() == {"detail": "Inactive user"}


def test_the_old_azure_route_is_gone(client):
    assert client.post("/api/v1/sso/azure", json={"code": "x", "tenant_id": "y"}).status_code == 404
