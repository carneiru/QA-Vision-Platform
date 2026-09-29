from datetime import datetime, timedelta, timezone

import jwt
import pytest

from src.ingestion.core.config import settings
from src.ingestion.utils.tokens import decode_token


def _encode(**claims) -> str:
    payload = {"sub": "1", "exp": datetime.now(timezone.utc) + timedelta(minutes=5), **claims}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def test_valid_access_token_decodes():
    assert decode_token(_encode())["sub"] == "1"


def test_refresh_token_is_rejected():
    with pytest.raises(ValueError):
        decode_token(_encode(token_type="refresh"))


def test_token_signed_with_another_key_is_rejected():
    with pytest.raises(ValueError):
        decode_token(jwt.encode({"sub": "1"}, "not-the-secret", algorithm=settings.ALGORITHM))
