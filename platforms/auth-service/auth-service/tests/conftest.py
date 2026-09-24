import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.auth.db.base import Base
from src.auth.db.session import get_db
from src.auth.main import app
from fastapi.testclient import TestClient
import os

# Use test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    # Function-scoped with a fresh schema per test. It was session-scoped, so every test
    # inherited rows from the previous one -- three unit tests each create test@example.com
    # and only the first could succeed.
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def register_and_verify(client, db):
    """Completes password registration end to end: POST /auth/register, then GET
    /auth/verify-email with the token from the resulting PendingRegistration row. Returns
    the Token dict (access_token, refresh_token, token_type) from the auto-login.

    Reads the token from the database rather than the log line EmailSender writes -- that
    is what a real client would extract from the URL in the email; the token is what
    matters, and the logging path is exercised on its own in test_email_sender.py.
    """
    from src.auth.models.pending_registration import PendingRegistration

    def _do(email, password="securepassword123", full_name=None):
        payload = {"email": email, "password": password}
        if full_name is not None:
            payload["full_name"] = full_name
        response = client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 202, response.text

        pending = db.query(PendingRegistration).filter(
            PendingRegistration.email == email
        ).first()
        assert pending is not None, f"no pending registration was created for {email}"

        verified = client.get(f"/api/v1/auth/verify-email?token={pending.token}")
        assert verified.status_code == 200, verified.text
        return verified.json()

    return _do
