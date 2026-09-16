import jwt
import pytest
from datetime import datetime, timedelta
from src.organization.core.config import settings
from src.organization.utils.tokens import decode_token


def test_decode_token_returns_payload():
    token = jwt.encode(
        {"sub": "42", "exp": datetime.utcnow() + timedelta(minutes=5)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    payload = decode_token(token)
    assert payload["sub"] == "42"


def test_decode_token_rejects_bad_signature():
    token = jwt.encode(
        {"sub": "42", "exp": datetime.utcnow() + timedelta(minutes=5)},
        "wrong-secret",
        algorithm=settings.ALGORITHM,
    )
    with pytest.raises(ValueError):
        decode_token(token)


def test_decode_token_rejects_expired():
    token = jwt.encode(
        {"sub": "42", "exp": datetime.utcnow() - timedelta(minutes=5)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    with pytest.raises(ValueError):
        decode_token(token)
