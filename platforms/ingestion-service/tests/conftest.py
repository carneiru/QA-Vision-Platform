from datetime import datetime, timedelta, timezone

import jwt
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.ingestion.api.main import app
from src.ingestion.core.config import settings
from src.ingestion.db.base import Base
from src.ingestion.db.session import get_db
from src.ingestion.models import ApiKey, Run, RunResult  # noqa: F401  registers tables

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def make_token(user_id: int, **claims) -> str:
    payload = {"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(minutes=5), **claims}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@pytest.fixture(scope="function")
def db():
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
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth():
    """auth(user_id) -> headers carrying a valid access token for that user."""

    def _auth(user_id: int = 1) -> dict:
        return {"Authorization": f"Bearer {make_token(user_id)}"}

    return _auth


@pytest.fixture
def http():
    """A respx router active for the test; any outgoing request without a route raises."""
    with respx.mock(assert_all_called=False) as router:
        yield router
