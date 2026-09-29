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


PROJECT_URL = "{base}/api/v1/projects/{project_id}"


def project_body(project_id: int, organization_id: int, role: str) -> dict:
    """The shape project-service's GET /projects/{id} returns (ProjectOut)."""
    return {
        "id": project_id, "organization_id": organization_id, "name": f"P{project_id}", "slug": f"p{project_id}",
        "description": None,
        "settings": {"result_retention_days": 90, "default_environment": None, "notify_on_failure": False},
        "created_by": 1, "created_at": "2026-09-29T00:00:00Z", "updated_at": None, "my_role": role,
    }


@pytest.fixture
def project_role(http):
    """Mock project-service's GET /projects/{id} for one project; calling it again for the same
    project replaces the answer (respx replaces routes that share a name)."""
    import httpx

    def _set(role="owner", project_id=1, organization_id=10, status_code=200, body=None, exc=None):
        route = http.get(
            PROJECT_URL.format(base=settings.PROJECT_SERVICE_URL, project_id=project_id),
            name=f"project-{project_id}",
        )
        if exc is not None:
            return route.mock(side_effect=exc)
        payload = project_body(project_id, organization_id, role) if body is None else body
        return route.mock(return_value=httpx.Response(status_code, json=payload))

    return _set
