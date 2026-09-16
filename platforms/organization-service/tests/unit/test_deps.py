import jwt
import pytest
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from src.organization.core.config import settings
from src.organization.api.deps import get_current_user_id

app = FastAPI()


@app.get("/whoami")
def whoami(user_id: int = Depends(get_current_user_id)):
    return {"user_id": user_id}


client = TestClient(app)


def _token(sub="7", expired=False):
    delta = timedelta(minutes=-5) if expired else timedelta(minutes=5)
    return jwt.encode({"sub": sub, "exp": datetime.utcnow() + delta}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def test_valid_token_resolves_user_id():
    response = client.get("/whoami", headers={"Authorization": f"Bearer {_token()}"})
    assert response.status_code == 200
    assert response.json() == {"user_id": 7}


def test_missing_token_returns_401():
    response = client.get("/whoami")
    assert response.status_code == 401


def test_expired_token_returns_401():
    response = client.get("/whoami", headers={"Authorization": f"Bearer {_token(expired=True)}"})
    assert response.status_code == 401


def test_non_integer_sub_returns_401():
    bad = jwt.encode({"sub": "not-a-number", "exp": datetime.utcnow() + timedelta(minutes=5)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    response = client.get("/whoami", headers={"Authorization": f"Bearer {bad}"})
    assert response.status_code == 401
