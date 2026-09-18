"""Cross-user isolation.

`UserService.get_user_by_id` once read `filter(user_id == user_id)` -- a Python tautology,
so SQLAlchemy emitted `WHERE true` and returned the first row in `users` for every id. That
made /auth/refresh-token hand out an access token for users.id == 1, and PUT /users/me
overwrite that account. The pre-existing suite could not see it because every test used a
single-user database.
"""

def _register(client, email):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "securepassword123", "full_name": email},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _login(client, email):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepassword123"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_refresh_returns_a_token_for_the_same_user(client):
    _register(client, "first@example.com")
    _register(client, "second@example.com")
    second = _login(client, "second@example.com")

    refreshed = client.post(
        "/api/v1/auth/refresh-token", json={"refresh_token": second["refresh_token"]}
    )
    assert refreshed.status_code == 200, refreshed.text

    me = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "second@example.com", "refresh must not switch identity"


def test_updating_me_does_not_touch_another_user(client):
    first = _register(client, "first@example.com")
    _register(client, "second@example.com")
    second = _login(client, "second@example.com")

    updated = client.put(
        "/api/v1/users/me",
        json={"full_name": "Renamed By Second"},
        headers={"Authorization": f"Bearer {second['access_token']}"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["email"] == "second@example.com"

    # the first account must be untouched, and must still be able to log in
    still_first = _login(client, "first@example.com")
    me = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {still_first['access_token']}"},
    )
    assert me.json()["email"] == "first@example.com"
    assert me.json()["full_name"] == first["full_name"]


def test_user_responses_never_include_password_hashes(client):
    _register(client, "first@example.com")
    tokens = _login(client, "first@example.com")

    me = client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert me.status_code == 200
    assert "hashed_password" not in me.json()


def test_logout_cannot_revoke_another_users_session(client):
    _register(client, "first@example.com")
    _register(client, "second@example.com")
    first = _login(client, "first@example.com")
    second = _login(client, "second@example.com")

    # second tries to revoke first's refresh token
    response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": first["refresh_token"]},
        headers={"Authorization": f"Bearer {second['access_token']}"},
    )
    assert response.status_code != 200

    # first's session still works
    refreshed = client.post(
        "/api/v1/auth/refresh-token", json={"refresh_token": first["refresh_token"]}
    )
    assert refreshed.status_code == 200
