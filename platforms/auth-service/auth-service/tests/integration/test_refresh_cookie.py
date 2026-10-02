"""The refresh token also travels as an httpOnly cookie so the SPA never has
to store it in JavaScript-readable storage. The JSON body stays supported for
API clients."""

from src.auth.models.pending_registration import PendingRegistration

COOKIE = "qav_refresh"


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
