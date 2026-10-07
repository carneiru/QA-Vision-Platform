"""The refresh token also travels as an httpOnly cookie so the SPA never has
to store it in JavaScript-readable storage. The JSON body stays supported for
API clients."""

from src.auth.models.pending_registration import PendingRegistration

COOKIE = "qeos_refresh"
LEGACY_COOKIE = "qav_refresh"  # the name before the QEOS rename; still read


def _make_user(client, db, email="cookie@example.com"):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "securepassword123", "full_name": "Cookie User"},
    )
    pending = db.query(PendingRegistration).filter(PendingRegistration.email == email).first()
    verified = client.get(f"/api/v1/auth/verify-email?token={pending.token}")
    assert verified.status_code == 200
    return verified.json()


def _login(client, email="cookie@example.com"):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword123"},
    )
    assert response.status_code == 200, response.text
    return response


def test_login_sets_httponly_refresh_cookie(client, db):
    _make_user(client, db)
    response = _login(client)
    set_cookie = response.headers.get("set-cookie", "")
    assert f"{COOKIE}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie
    assert "SameSite=strict" in set_cookie.lower() or "samesite=strict" in set_cookie.lower()
    # The cookie matches the body token.
    assert response.json()["refresh_token"] in set_cookie


def test_refresh_works_from_cookie_alone_and_rotates_it(client, db):
    _make_user(client, db)
    login = _login(client)
    old_refresh = login.json()["refresh_token"]

    # TestClient carries the cookie jar; empty JSON body must succeed.
    response = client.post("/api/v1/auth/refresh-token", json={})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["refresh_token"] != old_refresh
    assert body["refresh_token"] in response.headers.get("set-cookie", "")

    # The old token was rotated away: replaying it is rejected.
    replay = client.post("/api/v1/auth/refresh-token", json={"refresh_token": old_refresh})
    assert replay.status_code == 401


def test_refresh_with_body_still_works(client, db):
    _make_user(client, db)
    login = _login(client)
    client.cookies.clear()  # simulate a non-browser API client
    response = client.post(
        "/api/v1/auth/refresh-token",
        json={"refresh_token": login.json()["refresh_token"]},
    )
    assert response.status_code == 200, response.text


def test_refresh_without_cookie_or_body_is_401(client, db):
    _make_user(client, db)
    client.cookies.clear()
    response = client.post("/api/v1/auth/refresh-token", json={})
    assert response.status_code == 401


def test_logout_from_cookie_revokes_and_clears_it(client, db):
    _make_user(client, db)
    login = _login(client)
    access = login.json()["access_token"]
    refresh = login.json()["refresh_token"]

    response = client.post(
        "/api/v1/auth/logout",
        json={},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 200, response.text
    set_cookie = response.headers.get("set-cookie", "")
    assert f'{COOKIE}="";' in set_cookie or f"{COOKIE}=;" in set_cookie  # cleared

    # The revoked token no longer refreshes.
    client.cookies.clear()
    replay = client.post("/api/v1/auth/refresh-token", json={"refresh_token": refresh})
    assert replay.status_code == 401


def _cleared(set_cookies, name):
    return any(c.startswith(f'{name}="";') or c.startswith(f"{name}=;") for c in set_cookies)


def test_refresh_from_legacy_cookie_reissues_new_and_clears_old(client, db):
    _make_user(client, db)
    old_refresh = _login(client).json()["refresh_token"]
    client.cookies.clear()

    response = client.post(
        "/api/v1/auth/refresh-token", json={}, headers={"Cookie": f"{LEGACY_COOKIE}={old_refresh}"}
    )
    assert response.status_code == 200, response.text
    set_cookies = response.headers.get_list("set-cookie")
    new_refresh = response.json()["refresh_token"]
    assert any(c.startswith(f"{COOKIE}={new_refresh}") for c in set_cookies)
    assert _cleared(set_cookies, LEGACY_COOKIE)


def test_refresh_prefers_new_cookie_over_legacy(client, db):
    _make_user(client, db)
    current = _login(client).json()["refresh_token"]
    client.cookies.clear()

    response = client.post(
        "/api/v1/auth/refresh-token",
        json={},
        headers={"Cookie": f"{COOKIE}={current}; {LEGACY_COOKIE}=stale-token"},
    )
    assert response.status_code == 200, response.text


def test_every_token_issue_clears_a_stale_legacy_cookie(client, db):
    _make_user(client, db)
    login = _login(client)
    assert _cleared(login.headers.get_list("set-cookie"), LEGACY_COOKIE)
    response = client.post("/api/v1/auth/refresh-token", json={})
    assert response.status_code == 200, response.text
    assert _cleared(response.headers.get_list("set-cookie"), LEGACY_COOKIE)


def test_logout_with_both_cookies_revokes_both_sessions(client, db):
    _make_user(client, db)
    first = _login(client).json()
    second = _login(client).json()
    client.cookies.clear()

    response = client.post(
        "/api/v1/auth/logout",
        json={},
        headers={"Authorization": f"Bearer {second['access_token']}",
                 "Cookie": f"{COOKIE}={second['refresh_token']}; {LEGACY_COOKIE}={first['refresh_token']}"},
    )
    assert response.status_code == 200, response.text
    for token in (first["refresh_token"], second["refresh_token"]):
        assert client.post("/api/v1/auth/refresh-token", json={"refresh_token": token}).status_code == 401


def test_logout_with_legacy_cookie_revokes_it_and_clears_both(client, db):
    _make_user(client, db)
    login = _login(client)
    access, refresh = login.json()["access_token"], login.json()["refresh_token"]
    client.cookies.clear()

    response = client.post(
        "/api/v1/auth/logout",
        json={},
        headers={"Authorization": f"Bearer {access}", "Cookie": f"{LEGACY_COOKIE}={refresh}"},
    )
    assert response.status_code == 200, response.text
    set_cookies = response.headers.get_list("set-cookie")
    assert _cleared(set_cookies, COOKIE)
    assert _cleared(set_cookies, LEGACY_COOKIE)

    replay = client.post("/api/v1/auth/refresh-token", json={"refresh_token": refresh})
    assert replay.status_code == 401
