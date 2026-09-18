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
