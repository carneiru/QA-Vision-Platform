# Microsoft (Entra ID) SSO Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** auth-service signs people in with a Microsoft work/school ID token from an allowlist of tenants, with Google's account rules, lets a signed-in user link a Microsoft identity, and hardens signing-key fetching for both providers.

**Architecture:** A `ThrottledJWKClient` (PyJWKClient subclass) serves both providers' keys; `SSOService.validate_microsoft_token` verifies Microsoft ID tokens; `sso.py` gets one provider-neutral error mapping and one sign-in helper used by `/sso/google` and `/sso/microsoft`; `users.py` gets one link helper used by `/users/me/link/google` and `/users/me/link/microsoft`.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, PyJWT 2.8 (`PyJWKClient`), cryptography (test keys), pytest; NGINX gateway; bash smoke script.

**Spec:** `docs/superpowers/specs/2026-10-01-microsoft-sso-design.md`

## Global Constraints

- Provider name `microsoft`; `provider_user_id` = `f"{tid}:{oid}"`; routes `POST /api/v1/sso/microsoft` and `POST /api/v1/users/me/link/microsoft`. `POST /api/v1/sso/azure` and `AzureLoginRequest` are removed.
- Settings: `AZURE_CLIENT_ID` (required `aud`), `AZURE_ALLOWED_TENANTS` (comma-separated; empty → `AZURE_TENANT_ID` as a one-entry list). Missing client id or tenants → 503 `"Microsoft SSO is not configured"`.
- Verification: RS256 only; require `exp`, `nbf`, `iss`, `aud`, `tid`, `oid`; `ver == "2.0"`; `tid` (lower-cased) in the allowlist, else refused and the tenant id logged at warning level; `iss == f"https://login.microsoftonline.com/{tid}/v2.0"`; email = `email` or `preferred_username`, must match `^[^@\s]+@[^@\s]+$`, else 400 `"Microsoft account has no email address"`.
- Error mapping (both providers): not configured → 503 `"<Provider> SSO is not configured"`; `PyJWKClientConnectionError` → 503 `"<Provider> sign-in is temporarily unavailable"`; any other failure → 400 `"Invalid <Provider> token"`.
- Key client: timeout 5 s; key set cached 300 s; an unknown `kid` forces a re-fetch at most once per 300 s.
- Google's behaviour and messages are unchanged; the existing Google tests pass unchanged, except the 501 test for `azure`, which keeps only `github`.
- Gateway: `location /api/v1/sso` adds `limit_req zone=auth burst=10 nodelay;`.
- Tests run from `platforms/auth-service/auth-service`: `SECRET_KEY=x .venv/Scripts/python -m pytest tests/ -q` (Git Bash on Windows; `.venv/bin/python` elsewhere). `$PY` below means that interpreter.
- No test contacts Microsoft or Google.
- Git: commit as carneiru; `git status --short` before every `git add`; never commit stray/empty files; never push tags.

## Review Focus

1. **A token from an allowed tenant whose `iss` names a different tenant** (keys are shared across tenants): must be refused. Pinned by `test_refused_tokens[iss_other_tenant]` (Task 2).
2. **A tenant id written in upper case in `AZURE_ALLOWED_TENANTS`**: tokens carry lower-case ids; it must still match. Pinned by `test_allowed_tenants_are_case_insensitive` (Task 2).
3. **Made-up key ids** (`kid` not in the key set): must not cause a provider fetch per request. Pinned by `test_an_unknown_kid_forces_at_most_one_refresh_per_interval` (Task 1).
4. **The same `oid` in two allowed tenants**: two different identities, never merged. Pinned by `test_the_same_oid_in_another_tenant_is_another_identity` (Task 2).
5. **A provider key outage**: must read as 503, not "invalid token", for Google too. Pinned by `test_google_key_outage_is_503` (Task 1) and `test_microsoft_key_outage_is_503` (Task 2).

---

### Task 1: Hardened key client and provider-neutral error mapping

**Files:**
- Modify: `platforms/auth-service/auth-service/src/auth/service/sso_service.py`
- Modify: `platforms/auth-service/auth-service/src/auth/api/v1/endpoints/sso.py` (only `verify_google_credential` and imports)
- Test: `platforms/auth-service/auth-service/tests/unit/test_jwk_client.py`, `platforms/auth-service/auth-service/tests/integration/test_sso_endpoints.py` (one added test)

**Interfaces:**
- Produces:
  - `sso_service.ThrottledJWKClient(uri: str, *, timeout: int = 5, refresh_interval: float = 300, clock: Callable[[], float] = time.monotonic)` with `get_signing_key(kid)` / inherited `get_signing_key_from_jwt(token)`.
  - `sso_service._jwks_client` is now a `ThrottledJWKClient` (Google tests monkeypatch its `get_signing_key_from_jwt`, which keeps working).
  - `sso_service.SSOIdentityError(Exception)` — valid token, unusable identity; message is safe to show.
  - `sso.verify_credential(credential: str, validate: Callable[[str], dict], label: str) -> dict` (raises the HTTPExceptions above); `sso.verify_google_credential(credential) -> dict` unchanged in signature.

- [ ] **Step 1: Write the failing tests**

`platforms/auth-service/auth-service/tests/unit/test_jwk_client.py`:

```python
import json

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWKClientError
from jwt.algorithms import RSAAlgorithm

from src.auth.service.sso_service import ThrottledJWKClient


def make_client(now):
    client = ThrottledJWKClient("https://keys.example.test/", clock=lambda: now[0])
    public = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key()
    jwk = json.loads(RSAAlgorithm.to_jwk(public))
    jwk.update({"kid": "k1", "use": "sig", "alg": "RS256"})
    fetches = []

    def fake_fetch():
        fetches.append(1)
        data = {"keys": [jwk]}
        client.jwk_set_cache.put(data)
        return data

    client.fetch_data = fake_fetch
    return client, fetches


def test_a_known_kid_is_served_from_the_cache():
    client, fetches = make_client([1000.0])
    assert client.get_signing_key("k1").key_id == "k1"
    assert client.get_signing_key("k1").key_id == "k1"
    assert len(fetches) == 1


def test_an_unknown_kid_forces_at_most_one_refresh_per_interval():
    now = [1000.0]
    client, fetches = make_client(now)
    client.get_signing_key("k1")
    assert len(fetches) == 1

    with pytest.raises(PyJWKClientError):
        client.get_signing_key("made-up-1")
    assert len(fetches) == 2  # one forced refresh

    with pytest.raises(PyJWKClientError):
        client.get_signing_key("made-up-2")
    assert len(fetches) == 2  # refused without contacting the provider

    now[0] += 301
    with pytest.raises(PyJWKClientError):
        client.get_signing_key("made-up-3")
    assert len(fetches) == 3


def test_the_fetch_timeout_is_short():
    assert ThrottledJWKClient("https://keys.example.test/").timeout == 5
```

Add to `platforms/auth-service/auth-service/tests/integration/test_sso_endpoints.py` (at the end):

```python
def test_google_key_outage_is_503(client, monkeypatch):
    """A Google outage used to read as "Invalid Google token" (400)."""
    from jwt import PyJWKClientConnectionError

    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", TEST_CLIENT_ID)

    def unreachable(token):
        raise PyJWKClientConnectionError("Fail to fetch data from the url")

    monkeypatch.setattr(sso_service._jwks_client, "get_signing_key_from_jwt", unreachable)
    response = client.post("/api/v1/sso/google", json={"credential": "anything"})
    assert response.status_code == 503
    assert response.json() == {"detail": "Google sign-in is temporarily unavailable"}
```

- [ ] **Step 2: Run the tests to see them fail**

Run (from `platforms/auth-service/auth-service`): `SECRET_KEY=x $PY -m pytest tests/unit/test_jwk_client.py tests/integration/test_sso_endpoints.py -q`
Expected: `test_jwk_client.py` collection error `ImportError: cannot import name 'ThrottledJWKClient'`; run `tests/integration/test_sso_endpoints.py` alone and `test_google_key_outage_is_503` fails with `400 != 503`.

- [ ] **Step 3: The key client and identity error**

In `platforms/auth-service/auth-service/src/auth/service/sso_service.py`, replace

```python
import jwt
from jwt import PyJWKClient

from src.auth.config import settings
```

with

```python
import logging
import re
import time
from typing import Callable, Optional

import jwt
from jwt import PyJWK, PyJWKClient, PyJWKClientError

from src.auth.config import settings

logger = logging.getLogger(__name__)

KEY_FETCH_TIMEOUT_SECONDS = 5
KEY_REFRESH_INTERVAL_SECONDS = 300


class ThrottledJWKClient(PyJWKClient):
    """PyJWKClient with a short timeout and a limit on forced key-set refreshes.

    PyJWKClient re-fetches the key set whenever a token names a key id it has not cached, so a
    token with a made-up `kid` made us call the provider on every request (and wait up to 30 s,
    PyJWT's default timeout). Here an unknown key id forces a re-fetch at most once per refresh
    interval; otherwise it is refused without contacting the provider.
    """

    def __init__(
        self,
        uri: str,
        *,
        timeout: int = KEY_FETCH_TIMEOUT_SECONDS,
        refresh_interval: float = KEY_REFRESH_INTERVAL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ):
        super().__init__(uri, cache_jwk_set=True, lifespan=300, timeout=timeout)
        self._refresh_interval = refresh_interval
        self._clock = clock
        self._last_forced_refresh: Optional[float] = None

    def get_signing_key(self, kid: str) -> PyJWK:
        signing_key = self.match_kid(self.get_signing_keys(), kid)
        if signing_key is None:
            now = self._clock()
            recently = (
                self._last_forced_refresh is not None
                and now - self._last_forced_refresh < self._refresh_interval
            )
            if recently:
                raise PyJWKClientError(f'Unable to find a signing key that matches: "{kid}"')
            self._last_forced_refresh = now
            signing_key = self.match_kid(self.get_signing_keys(refresh=True), kid)
            if signing_key is None:
                raise PyJWKClientError(f'Unable to find a signing key that matches: "{kid}"')
        return signing_key


class SSOIdentityError(Exception):
    """The token is genuine but its identity cannot be used. The message is shown to the caller."""
```

and replace

```python
_jwks_client = PyJWKClient(GOOGLE_CERTS_URL)
```

with

```python
_jwks_client = ThrottledJWKClient(GOOGLE_CERTS_URL)
```

- [ ] **Step 4: One error mapping for every provider**

In `platforms/auth-service/auth-service/src/auth/api/v1/endpoints/sso.py`, replace the imports block

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from src.auth.api import deps
import logging
from src.auth.service.sso_service import SSOService, SSOConfigurationError
```

with

```python
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from jwt import PyJWKClientConnectionError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from src.auth.api import deps
import logging
from src.auth.service.sso_service import SSOService, SSOConfigurationError, SSOIdentityError
```

and replace the whole `verify_google_credential` function with

```python
def verify_credential(credential: str, validate: Callable[[str], dict], label: str) -> dict:
    """Verify an ID token with `validate`, raising the HTTPExceptions every SSO endpoint raises.

    Shared by the sign-in and link endpoints of every provider, so they fail the same way.
    """
    try:
        identity = validate(credential)
    except SSOConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{label} SSO is not configured",
        )
    except PyJWKClientConnectionError:
        # The provider's key set could not be fetched: our problem, not the caller's token.
        logger.warning("%s signing keys could not be fetched", label, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{label} sign-in is temporarily unavailable",
        )
    except SSOIdentityError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception:
        # Deliberately opaque: the underlying text carries JWKS URLs and internal state.
        logger.warning("%s ID token verification failed", label, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {label} token",
        )

    if not identity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid {label} token")
    return identity


def verify_google_credential(credential: str) -> dict:
    """Verify a Google ID token, raising the same HTTPExceptions /sso/google raises."""
    import asyncio

    return verify_credential(credential, lambda c: asyncio.run(SSOService.validate_google_token(c)), "Google")
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `SECRET_KEY=x $PY -m pytest tests/ -q`
Expected: all pass (the existing Google tests unchanged).

- [ ] **Step 6: Commit**

```bash
cd ../../..   # repository root
git status --short
git add platforms/auth-service/auth-service/src/auth/service/sso_service.py platforms/auth-service/auth-service/src/auth/api/v1/endpoints/sso.py platforms/auth-service/auth-service/tests/unit/test_jwk_client.py platforms/auth-service/auth-service/tests/integration/test_sso_endpoints.py
git commit -m "fix(auth): harden signing-key fetching; a key outage is 503, not an invalid token

A ThrottledJWKClient (5 s timeout instead of PyJWT's 30 s) refuses a
made-up key id without contacting the provider more than once per 5
minutes. Errors from every SSO provider go through one mapping, which
now answers 503 when the provider's keys cannot be fetched.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Microsoft token verification and sign-in

**Files:**
- Modify: `platforms/auth-service/auth-service/src/auth/config.py`
- Modify: `platforms/auth-service/auth-service/src/auth/service/sso_service.py`
- Modify: `platforms/auth-service/auth-service/src/auth/schemas/auth.py`
- Modify: `platforms/auth-service/auth-service/src/auth/api/v1/endpoints/sso.py`
- Test: `platforms/auth-service/auth-service/tests/integration/test_microsoft_sso.py`, `platforms/auth-service/auth-service/tests/integration/test_sso_endpoints.py` (501 test)

**Interfaces:**
- Consumes: `ThrottledJWKClient`, `SSOIdentityError`, `verify_credential` (Task 1).
- Produces:
  - `settings.AZURE_ALLOWED_TENANTS: str`; `settings.azure_allowed_tenants -> list[str]` (lower-cased, fallback `AZURE_TENANT_ID`).
  - `sso_service._microsoft_jwks_client` (a `ThrottledJWKClient`); `SSOService.validate_microsoft_token(token: str) -> dict` (sync) returning `{"email", "full_name", "provider": "microsoft", "provider_user_id": "<tid>:<oid>"}`.
  - `sso.verify_microsoft_credential(credential) -> dict`; `sso.sso_sign_in(db, identity: dict, label: str, *, existing_account_detail: str) -> dict` (the token pair); route `POST /api/v1/sso/microsoft`.
  - Schemas `MicrosoftLoginRequest(credential: str)` and `LinkMicrosoftRequest(credential: str, current_password: Optional[str] = None)`; `AzureLoginRequest` removed.

- [ ] **Step 1: Write the failing tests**

`platforms/auth-service/auth-service/tests/integration/test_microsoft_sso.py`:

```python
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
        "email": "ann@corp.test",
        "preferred_username": "ann@corp.test",
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
    user = db.query(User).filter(User.email == "ann@corp.test").one()
    assert user.hashed_password is None and user.full_name == "Ann Example"
    link = db.query(OAuthAccount).filter(OAuthAccount.user_id == user.id).one()
    assert (link.provider, link.provider_user_id) == ("microsoft", f"{TENANT}:{OID}")


def test_a_returning_user_is_found_by_identity_even_if_the_email_changed(client, db, microsoft_key):
    assert sign_in(client, ms_token(microsoft_key)).status_code == 200
    again = sign_in(client, ms_token(microsoft_key, email="ann.renamed@corp.test"))

    assert again.status_code == 200, again.text
    assert db.query(User).count() == 1
    assert db.query(User).one().email == "ann@corp.test"  # not written back


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
    response = sign_in(client, ms_token(microsoft_key, email=DROP, preferred_username="ann@corp.test"))
    assert response.status_code == 200, response.text
    assert db.query(User).one().email == "ann@corp.test"


@pytest.mark.parametrize("overrides", [
    {"email": DROP, "preferred_username": DROP},
    {"email": DROP, "preferred_username": "ann"},
    {"email": "not an email", "preferred_username": DROP},
])
def test_an_account_without_an_email_is_refused(client, db, microsoft_key, overrides):
    response = sign_in(client, ms_token(microsoft_key, **overrides))
    assert response.status_code == 400
    assert response.json() == {"detail": "Microsoft account has no email address"}
    assert db.query(User).count() == 0


def test_an_existing_account_with_the_email_is_not_taken_over(client, db, microsoft_key, register_and_verify):
    register_and_verify("ann@corp.test")
    response = sign_in(client, ms_token(microsoft_key))

    assert response.status_code == 409
    assert "/api/v1/users/me/link/microsoft" in response.json()["detail"]
    assert db.query(OAuthAccount).count() == 0


def test_the_same_oid_in_another_tenant_is_another_identity(client, db, microsoft_key):
    assert sign_in(client, ms_token(microsoft_key)).status_code == 200
    other = sign_in(client, ms_token(microsoft_key, tid=OTHER_TENANT, email="ann@other.test"))

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
```

In `platforms/auth-service/auth-service/tests/integration/test_sso_endpoints.py`, change

```python
@pytest.mark.parametrize("provider", ["github", "azure"])
```

to

```python
@pytest.mark.parametrize("provider", ["github"])  # azure was replaced by /sso/microsoft
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `SECRET_KEY=x $PY -m pytest tests/integration/test_microsoft_sso.py -q`
Expected: errors in the `microsoft_key` fixture (`AttributeError: ... has no attribute '_microsoft_jwks_client'` / `AZURE_ALLOWED_TENANTS`) and `test_the_old_azure_route_is_gone` failing (501 ≠ 404).

- [ ] **Step 3: Settings**

In `platforms/auth-service/auth-service/src/auth/config.py`, after `AZURE_CLIENT_SECRET: str = ""`, add:

```python
    # Microsoft (Entra ID) sign-in: the tenants allowed to sign in, comma-separated tenant ids.
    # Empty falls back to AZURE_TENANT_ID as a one-entry list.
    AZURE_ALLOWED_TENANTS: str = ""
```

and after the `redis_url` property (at the end of the class), add:

```python
    @property
    def azure_allowed_tenants(self) -> list[str]:
        """Tenant ids are GUIDs; tokens carry them lower-cased."""
        raw = self.AZURE_ALLOWED_TENANTS or self.AZURE_TENANT_ID
        return [tenant.strip().lower() for tenant in raw.split(",") if tenant.strip()]
```

- [ ] **Step 4: Verification**

In `platforms/auth-service/auth-service/src/auth/service/sso_service.py`, after `_jwks_client = ThrottledJWKClient(GOOGLE_CERTS_URL)`, add:

```python
# One key set for every Entra tenant; which tenant issued a token is checked from its claims
MICROSOFT_KEYS_URL = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
_microsoft_jwks_client = ThrottledJWKClient(MICROSOFT_KEYS_URL)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+$")
```

and add this method to `SSOService` (after `validate_google_token`):

```python
    @staticmethod
    def validate_microsoft_token(token: str) -> dict:
        """Verify a Microsoft (Entra ID) v2.0 ID token from an allowed tenant.

        Every tenant's tokens are signed with the same key set, so the signature alone does not
        say which tenant issued a token: `tid` must be allowed and `iss` must name that tenant.
        """
        tenants = settings.azure_allowed_tenants
        if not settings.AZURE_CLIENT_ID or not tenants:
            # Fail closed, as for Google: without an audience, tokens for any app would pass
            raise SSOConfigurationError("AZURE_CLIENT_ID and AZURE_ALLOWED_TENANTS must be set")

        signing_key = _microsoft_jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.AZURE_CLIENT_ID,
            options={"require": ["exp", "nbf", "iss", "aud", "tid", "oid"]},
        )
        if claims.get("ver") != "2.0":
            raise ValueError("not a v2.0 ID token")
        tid = str(claims["tid"])
        if tid.lower() not in tenants:
            # Logged so onboarding a customer's tenant is a matter of copying this id
            logger.warning("Microsoft sign-in refused: tenant %s is not in AZURE_ALLOWED_TENANTS", tid)
            raise ValueError("tenant is not allowed")
        if claims["iss"] != f"https://login.microsoftonline.com/{tid}/v2.0":
            raise ValueError("issuer does not match the token's tenant")

        email = claims.get("email") or claims.get("preferred_username")
        if not isinstance(email, str) or not _EMAIL.match(email):
            raise SSOIdentityError("Microsoft account has no email address")
        return {
            "email": email,
            "full_name": claims.get("name"),
            "provider": "microsoft",
            # oid is unique only within a tenant
            "provider_user_id": f"{tid}:{claims['oid']}",
        }
```

- [ ] **Step 5: Schemas**

In `platforms/auth-service/auth-service/src/auth/schemas/auth.py`, replace

```python
class AzureLoginRequest(BaseModel):
    code: str
    tenant_id: str
```

with

```python
class MicrosoftLoginRequest(BaseModel):
    credential: str  # the ID token MSAL returns


class LinkMicrosoftRequest(BaseModel):
    credential: str
    # Same rule as LinkGoogleRequest: required when the account has a password
    current_password: Optional[str] = None
```

Run: `grep -rn "AzureLoginRequest" platforms/auth-service/auth-service/src` (repository root)
Expected: no output.

- [ ] **Step 6: The shared sign-in path and the route**

In `platforms/auth-service/auth-service/src/auth/api/v1/endpoints/sso.py`:

Change `from src.auth.schemas.auth import GoogleLoginRequest, Token` to
`from src.auth.schemas.auth import GoogleLoginRequest, MicrosoftLoginRequest, Token`.

After `verify_google_credential`, add:

```python
def verify_microsoft_credential(credential: str) -> dict:
    """Verify a Microsoft ID token, raising the same HTTPExceptions /sso/microsoft raises."""
    return verify_credential(credential, SSOService.validate_microsoft_token, "Microsoft")


GOOGLE_EXISTING_ACCOUNT = (
    "An account with this email already exists. Linking Google to an existing "
    "account is not supported yet."
)
MICROSOFT_EXISTING_ACCOUNT = (
    "An account with this email already exists. Sign in to it and link Microsoft "
    "with POST /api/v1/users/me/link/microsoft."
)
```

Replace the signature and the provider-specific strings of `_link_or_create_user`:
- `def _link_or_create_user(db: Session, google_data: dict, email: str, provider: str,` / `provider_user_id: str):` becomes
  `def _link_or_create_user(db: Session, identity: dict, email: str, provider: str, provider_user_id: str,` / `label: str, existing_account_detail: str):`
- `full_name=google_data.get("full_name"),` → `full_name=identity.get("full_name"),`
- `detail="This Google account is already linked",` → `detail=f"This {label} account is already linked",`
- `"Google sub mismatch for user %s: linked %s, presented %s",` / `user.id, existing_link.provider_user_id, provider_user_id,` → `"%s identity mismatch for user %s: linked %s, presented %s",` / `label, user.id, existing_link.provider_user_id, provider_user_id,`
- `detail="This account is linked to a different Google identity",` → `detail=f"This account is linked to a different {label} identity",`
- the final `detail=( "An account with this email already exists. Linking Google to an existing " "account is not supported yet." ),` → `detail=existing_account_detail,`
- the docstring's first line → `"""Resolve an SSO identity that is not yet linked to any account.`

Replace the whole `google_login` function with:

```python
def sso_sign_in(db: Session, identity: dict, label: str, *, existing_account_detail: str) -> dict:
    """Sign in with a verified SSO identity: find its account, or create one, and issue tokens."""
    email = identity["email"]
    provider = identity["provider"]
    provider_user_id = identity["provider_user_id"]

    # Resolve by the provider identity first. (provider, provider_user_id) is UNIQUE, so it is
    # the actual identity key here; the email is a mutable attribute of it. Looking up by email
    # first meant a user whose provider address had changed fell through to the create branch,
    # which committed a new user row and only then hit uix_provider_user -- a 500 with an
    # orphaned account left behind.
    linked = db.query(OAuthAccount).filter(
        OAuthAccount.provider == provider,
        OAuthAccount.provider_user_id == provider_user_id,
    ).first()

    if linked:
        # Known identity. The address on the token may have changed since; that does not
        # matter, and is deliberately not written back onto the account.
        user = UserService.get_user_by_id(db, linked.user_id)
        if not user:
            logger.error("OAuth link %s points at missing user %s", linked.id, linked.user_id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Account is in an inconsistent state",
            )
    else:
        user = _link_or_create_user(
            db, identity, email, provider, provider_user_id, label, existing_account_detail
        )

    # Password login refuses a deactivated account; SSO did not, so disabling someone left
    # them a working way in for as long as their provider account existed.
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = AuthService.create_access_token_for_user(user, expires_delta=access_token_expires)
    refresh_token = AuthService.create_user_session(db, user).token

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/google", response_model=Token)
def google_login(
    *,
    db: Session = Depends(deps.get_db),
    request: GoogleLoginRequest
):
    """
    Authenticate with Google ID token.
    """
    identity = verify_google_credential(request.credential)
    return sso_sign_in(db, identity, "Google", existing_account_detail=GOOGLE_EXISTING_ACCOUNT)


@router.post("/microsoft", response_model=Token)
def microsoft_login(
    *,
    db: Session = Depends(deps.get_db),
    request: MicrosoftLoginRequest
):
    """
    Authenticate with a Microsoft (Entra ID) ID token from an allowed tenant.
    """
    identity = verify_microsoft_credential(request.credential)
    return sso_sign_in(db, identity, "Microsoft", existing_account_detail=MICROSOFT_EXISTING_ACCOUNT)
```

Delete the `azure_login` route (the `@router.post("/azure", ...)` function) and update the comment above the GitHub route to say: `# GitHub SSO is not implemented. It previously called an SSOService method that did not exist and contained a syntax error, so this module never imported. Rather than resurrect a mock handler that returned a hardcoded identity, it fails honestly until a real OAuth exchange is built. (Azure was replaced by /sso/microsoft.)`

- [ ] **Step 7: Run the tests to see them pass**

Run: `SECRET_KEY=x $PY -m pytest tests/ -q`
Expected: all pass, the Google tests included.

- [ ] **Step 8: Commit**

```bash
cd ../../..
git status --short
git add platforms/auth-service/auth-service/src platforms/auth-service/auth-service/tests/integration/test_microsoft_sso.py platforms/auth-service/auth-service/tests/integration/test_sso_endpoints.py
git commit -m "feat(auth): sign in with Microsoft (Entra ID) from an allowlist of tenants

POST /api/v1/sso/microsoft verifies a v2.0 ID token (RS256, audience,
nbf/exp, tid in AZURE_ALLOWED_TENANTS, iss matching tid) and signs in
through the sign-in path now shared with Google: identity tid:oid first,
new passwordless users in one transaction, no linking by email, inactive
users refused. A refused tenant is logged. /sso/azure (always 501) is gone.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Linking Microsoft to an existing account

**Files:**
- Modify: `platforms/auth-service/auth-service/src/auth/api/v1/endpoints/users.py`
- Test: `platforms/auth-service/auth-service/tests/integration/test_microsoft_sso.py` (added tests)

**Interfaces:**
- Consumes: `verify_google_credential`, `verify_microsoft_credential` (Tasks 1–2); `LinkGoogleRequest`, `LinkMicrosoftRequest` (Task 2); fixtures `microsoft_key`, `ms_token`, `register_and_verify`.
- Produces: `POST /api/v1/users/me/link/microsoft` → `User`; `users._link_identity(db, current_user, credential, current_password, verify, label) -> UserModel`.

- [ ] **Step 1: Write the failing tests**

Add to `platforms/auth-service/auth-service/tests/integration/test_microsoft_sso.py`:

```python
LINK = "/api/v1/users/me/link/microsoft"


def bearer(login):
    return {"Authorization": f"Bearer {login['access_token']}"}


def test_link_microsoft_to_a_password_account(client, db, microsoft_key, register_and_verify):
    login = register_and_verify("bob@corp.test")
    linked = client.post(LINK, json={"credential": ms_token(microsoft_key), "current_password": "securepassword123"},
                         headers=bearer(login))

    assert linked.status_code == 200, linked.text
    assert db.query(OAuthAccount).filter(OAuthAccount.user_id == linked.json()["id"]).one().provider == "microsoft"
    # That Microsoft identity now signs in to this account, whatever its email says
    assert sign_in(client, ms_token(microsoft_key)).status_code == 200
    assert db.query(User).count() == 1


@pytest.mark.parametrize("password", [None, "wrong-password"])
def test_link_microsoft_requires_the_current_password(client, db, microsoft_key, register_and_verify, password):
    login = register_and_verify("bob@corp.test")
    body = {"credential": ms_token(microsoft_key)}
    if password is not None:
        body["current_password"] = password

    response = client.post(LINK, json=body, headers=bearer(login))
    assert response.status_code == 400
    assert response.json() == {"detail": "current_password is incorrect"}
    assert db.query(OAuthAccount).count() == 0


def test_link_microsoft_refuses_an_identity_linked_elsewhere(client, db, microsoft_key, register_and_verify):
    assert sign_in(client, ms_token(microsoft_key)).status_code == 200  # ann@corp.test owns it
    login = register_and_verify("bob@corp.test")

    response = client.post(LINK, json={"credential": ms_token(microsoft_key), "current_password": "securepassword123"},
                           headers=bearer(login))
    assert response.status_code == 409
    assert response.json() == {"detail": "This Microsoft account is already linked to a different user"}


def test_link_microsoft_refuses_a_second_link_on_the_same_account(client, db, microsoft_key, register_and_verify):
    login = register_and_verify("bob@corp.test")
    first = client.post(LINK, json={"credential": ms_token(microsoft_key), "current_password": "securepassword123"},
                        headers=bearer(login))
    assert first.status_code == 200
    second = client.post(LINK, json={"credential": ms_token(microsoft_key, oid="another-oid"),
                                     "current_password": "securepassword123"}, headers=bearer(login))
    assert second.status_code == 409
    assert second.json() == {"detail": "A Microsoft account is already linked to this account"}


def test_link_microsoft_requires_sign_in(client, microsoft_key):
    assert client.post(LINK, json={"credential": ms_token(microsoft_key)}).status_code == 401
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `SECRET_KEY=x $PY -m pytest tests/integration/test_microsoft_sso.py -q -k link`
Expected: failures with 404 for `/api/v1/users/me/link/microsoft` (and 405/404 for the unauthenticated case).

- [ ] **Step 3: The shared link helper and the route**

In `platforms/auth-service/auth-service/src/auth/api/v1/endpoints/users.py`:

Change `from src.auth.schemas.auth import LinkGoogleRequest` to
`from src.auth.schemas.auth import LinkGoogleRequest, LinkMicrosoftRequest` and
`from src.auth.api.v1.endpoints.sso import verify_google_credential` to
`from src.auth.api.v1.endpoints.sso import verify_google_credential, verify_microsoft_credential`.

Replace the whole `link_google_account` function (decorator included) with:

```python
def _link_identity(db: Session, current_user: UserModel, credential: str, current_password, verify, label: str):
    """Link a verified SSO identity to the current, authenticated account.

    The remedy the sign-in endpoints' 409 ("account already exists") points at.
    """
    if current_user.hashed_password is not None:
        # A short-lived bearer token can be stolen; requiring the password before attaching a
        # new, durable login method is the same guard PUT /users/me's password change uses,
        # for the same reason. Nothing to confirm for a passwordless (pure-SSO) account.
        if not current_password or not verify_password(current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="current_password is incorrect",
            )

    identity = verify(credential)
    provider = identity["provider"]
    provider_user_id = identity["provider_user_id"]

    # At most one link per provider per user, enforced here rather than only relied on: the
    # sign-in path's existing_link lookup picks arbitrarily via .first() if a user held two.
    if db.query(OAuthAccount).filter(
        OAuthAccount.user_id == current_user.id,
        OAuthAccount.provider == provider,
    ).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A {label} account is already linked to this account",
        )

    db.add(OAuthAccount(
        user_id=current_user.id, provider=provider, provider_user_id=provider_user_id,
    ))
    try:
        db.commit()
    except IntegrityError:
        # This exact identity is already linked to a different account -- the constraint is
        # the backstop; the pre-check above is what usually catches it first.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This {label} account is already linked to a different user",
        )

    db.refresh(current_user)
    return current_user


@router.post("/me/link/google", response_model=User)
def link_google_account(
    *,
    db: Session = Depends(deps.get_db),
    request: LinkGoogleRequest,
    current_user: UserModel = Depends(deps.get_current_active_user),
):
    """Link a Google identity to the current, authenticated account."""
    return _link_identity(db, current_user, request.credential, request.current_password,
                          verify_google_credential, "Google")


@router.post("/me/link/microsoft", response_model=User)
def link_microsoft_account(
    *,
    db: Session = Depends(deps.get_db),
    request: LinkMicrosoftRequest,
    current_user: UserModel = Depends(deps.get_current_active_user),
):
    """Link a Microsoft (Entra ID) identity to the current, authenticated account."""
    return _link_identity(db, current_user, request.credential, request.current_password,
                          verify_microsoft_credential, "Microsoft")
```

Before replacing, read the current `link_google_account` and confirm the helper keeps every check and message it had (the Google link tests assert them); if the current function differs from the shape above in any check, keep the current check and record a ledger ruling.

- [ ] **Step 4: Run the tests to see them pass**

Run: `SECRET_KEY=x $PY -m pytest tests/ -q`
Expected: all pass, the Google link tests included.

- [ ] **Step 5: Commit**

```bash
cd ../../..
git status --short
git add platforms/auth-service/auth-service/src/auth/api/v1/endpoints/users.py platforms/auth-service/auth-service/tests/integration/test_microsoft_sso.py
git commit -m "feat(auth): link a Microsoft identity to an existing account

POST /api/v1/users/me/link/microsoft, through a link helper now shared
with Google: the current password when the account has one, at most one
link per provider, never an identity linked elsewhere.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Gateway, smoke check and docs

**Files:**
- Modify: `gateway/nginx.conf.template`
- Modify: `scripts/smoke_gateway.sh`
- Modify: `platforms/auth-service/auth-service/README.md`, `platforms/auth-service/auth-service/.env.example`, `README.md`, `TODO.md`

**Interfaces:**
- Consumes: the routes from Tasks 2–3.
- Produces: the strict rate limit on `/api/v1/sso`; one smoke check; docs.

- [ ] **Step 1: Gateway**

In `gateway/nginx.conf.template`, replace

```nginx
        location /api/v1/sso {
            limit_req zone=api burst=40 nodelay;
            set $upstream http://auth-service:8000;
```

with

```nginx
        location /api/v1/sso {
            limit_req zone=api burst=40 nodelay;
            # Sign-in endpoints all get the stricter zone, like /api/v1/auth/login
            limit_req zone=auth burst=10 nodelay;
            set $upstream http://auth-service:8000;
```

Run (repository root): `docker build -q -t qa-vision/gateway:check gateway && docker run --rm qa-vision/gateway:check nginx -t`
Expected: `nginx: configuration file /etc/nginx/nginx.conf test is successful`.

- [ ] **Step 2: Smoke check**

In `scripts/smoke_gateway.sh`, insert immediately before the line `check "/api/v1/organizations/999999/members/me for a non-member -> organization-service" 404 GET \`:

```bash
# The stack has no Microsoft configuration: 503 proves the request reached auth-service
check "/api/v1/sso/microsoft -> auth-service (not configured)" 503 POST "$BASE/api/v1/sso/microsoft" \
  -H "Content-Type: application/json" -d '{"credential":"not-a-token"}'
```

Run: `bash -n scripts/smoke_gateway.sh && echo syntax-ok`
Expected: `syntax-ok`.

Then run the stack and the smoke test (Git Bash, port 8080 is taken on this machine):

```bash
export SECRET_KEY=local-smoke-secret GATEWAY_HTTP_PORT=18080
docker compose up -d --build --wait --wait-timeout 300 gateway
bash scripts/smoke_gateway.sh
docker compose down
```

Expected: every line `ok`, including `ok    /api/v1/sso/microsoft -> auth-service (not configured) (503)`; last line `all gateway checks passed`.

- [ ] **Step 3: auth-service README**

In `platforms/auth-service/auth-service/README.md`:

- After the line starting `- **Google SSO**: ID tokens verified against Google's JWKS`, add:
  `- **Microsoft SSO (Entra ID)**: v2.0 ID tokens from an allowlist of tenants, verified against Microsoft's JWKS (RS256, audience, tenant, issuer, expiry); identity is tenant id + object id`
- Delete the line `- **Azure AD SSO**: requires an Azure AD code exchange that does not exist`.
- Replace the block from `The settings below are accepted by the config module but nothing reads them yet` through `- \`SAML_SETTINGS\`` with:

```markdown
- `AZURE_CLIENT_ID`: the Entra app registration's client id (the required token audience)
- `AZURE_ALLOWED_TENANTS`: comma-separated tenant ids allowed to sign in (empty: `AZURE_TENANT_ID`, if set)

Without both, `POST /sso/microsoft` answers 503. The settings below are accepted by the config
module but nothing reads them yet:
- `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` (GitHub SSO returns 501)
- `AZURE_CLIENT_SECRET` (the ID-token flow needs no secret)
- `SAML_SETTINGS`

#### Setting up Microsoft sign-in

1. In Entra ID, register an application as a **single-page application** with your frontend's
   redirect URI, and enable **ID tokens**. Its *Application (client) ID* is `AZURE_CLIENT_ID`.
2. Put your tenant id (and each customer tenant you onboard) in `AZURE_ALLOWED_TENANTS`. A
   sign-in from any other tenant is refused and its tenant id is logged — copy it from there.
3. In the frontend, get an ID token with MSAL and post it:

```js
const msal = new PublicClientApplication({ auth: { clientId: "<AZURE_CLIENT_ID>",
  authority: "https://login.microsoftonline.com/organizations" } });
await msal.initialize();
const { idToken } = await msal.loginPopup({ scopes: ["openid", "profile", "email"] });
await fetch("/api/v1/sso/microsoft", { method: "POST",
  headers: { "Content-Type": "application/json" }, body: JSON.stringify({ credential: idToken }) });
```
```

- In "### SSO Authentication", replace `- \`POST /api/v1/sso/azure\` - **501, not implemented**` with:
  `- \`POST /api/v1/sso/microsoft\` - Authenticate with a Microsoft (Entra ID) ID token from an allowed tenant` and, after it,
  `- \`POST /api/v1/users/me/link/microsoft\` - Link a Microsoft identity to the signed-in account (requires \`current_password\` when the account has one)`
- In "### SSO Security", after the Google paragraph, add:

```markdown
- **Microsoft** follows the same account rules (identity first, no linking by email, inactive users refused). Its tokens must be v2.0, signed with Microsoft's keys (RS256), meant for `AZURE_CLIENT_ID`, from a tenant in `AZURE_ALLOWED_TENANTS`, with `iss` naming that same tenant — all tenants share one key set, so the signature alone does not prove the tenant. The identity key is `tid:oid` (an object id is unique only within its tenant). The account email is the `email` claim, else `preferred_username`; with a trusted tenant allowlist that is acceptable, and existing accounts are still never adopted by email.
- Signing keys (Google and Microsoft) are fetched with a 5 s timeout and cached; a token naming an unknown key id forces at most one re-fetch per 5 minutes. A provider outage answers 503, not "invalid token".
```

Note: the nested MSAL ```` ```js ```` fence sits inside this plan's markdown block; when editing the README, write it as an ordinary fenced block.

- [ ] **Step 4: .env.example, root README, TODO**

In `platforms/auth-service/auth-service/.env.example`, after `AZURE_CLIENT_SECRET=`, add `AZURE_ALLOWED_TENANTS=`.

In `README.md`, replace `- **Google SSO** - ID tokens verified against Google's JWKS. GitHub and Azure AD return 501; they were previously mocks that accepted any input.` with
`- **Google and Microsoft SSO** - ID tokens verified against each provider's JWKS; Microsoft (Entra ID) sign-in is limited to an allowlist of tenants. GitHub returns 501; it was previously a mock that accepted any input.`
and replace `- **SSO**: Google ID token verification via PyJWT. Authlib and python-jose are in \`requirements.txt\` but unused.` with
`- **SSO**: Google and Microsoft ID token verification via PyJWT. Authlib and python-jose are in \`requirements.txt\` but unused.`

In `TODO.md`, insert immediately before the line `### Phase 4: Test Management`:

```markdown
### Microsoft SSO
- [x] Sign in with Microsoft (Entra ID) ID tokens from an allowlist of tenants; link to an existing account
- [x] Signing-key fetch hardened for Google and Microsoft (timeout, throttled refresh); outages answer 503
- [ ] Personal Microsoft accounts (outlook.com)
- [ ] Map Entra groups / app roles to organization roles
- [ ] SCIM provisioning and deprovisioning
- [ ] GitHub SSO
- [ ] Single sign-out

```

Run: `grep -n "Microsoft" README.md TODO.md platforms/auth-service/auth-service/README.md | head` — Expected: the new lines.

- [ ] **Step 5: Commit**

```bash
git status --short
git add gateway/nginx.conf.template scripts/smoke_gateway.sh platforms/auth-service/auth-service/README.md platforms/auth-service/auth-service/.env.example README.md TODO.md
git commit -m "feat: strict rate limit for SSO; Microsoft sign-in smoke check and docs

/api/v1/sso gets the gateway's auth zone, like password login. The
smoke test checks /api/v1/sso/microsoft reaches auth-service. The
auth-service README explains the Entra app registration, the tenant
allowlist and the MSAL call.

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```
