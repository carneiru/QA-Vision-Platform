def test_register_and_login(client):
    # Register new user
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "securepassword123",
            "full_name": "Test User"
        }
    )
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["email"] == "test@example.com"
    assert user_data["full_name"] == "Test User"
    assert "id" in user_data
    
    # Login with new user
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "test@example.com",
            "password": "securepassword123"
        }
    )
    assert response.status_code == 200
    token_data = response.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "bearer"
    
    # Use access token to get user info
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"}
    )
    assert response.status_code == 200
    user_info = response.json()
    assert user_info["email"] == "test@example.com"

def test_refresh_token(client):
    # Register and login
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "test2@example.com",
            "password": "securepassword123",
            "full_name": "Test User 2"
        }
    )
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "test2@example.com",
            "password": "securepassword123"
        }
    )
    tokens = login_response.json()
    
    # Refresh token
    response = client.post(
        "/api/v1/auth/refresh-token",
        json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 200
    new_tokens = response.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens
    assert new_tokens["refresh_token"] != tokens["refresh_token"]  # Should be new token
    
    # Old refresh token should now be invalid
    response = client.post(
        "/api/v1/auth/refresh-token",
        json={"refresh_token": tokens["refresh_token"]}
    )
    assert response.status_code == 401  # Should be unauthorized


def test_password_reset_reports_not_implemented(client):
    """Both handlers used to return success without doing anything -- /reset-password even
    answered "Password has been reset successfully" while leaving the password untouched.
    Until a reset-token model and a mail transport exist, they must say so."""
    forgot = client.post(
        "/api/v1/auth/forgot-password", json={"email": "nobody@example.com"}
    )
    assert forgot.status_code == 501, forgot.text

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "anything", "password": "newpassword123"},
    )
    assert reset.status_code == 501, reset.text
