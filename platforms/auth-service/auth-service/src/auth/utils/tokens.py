# src/services/auth-service/src/auth/utils/tokens.py
from datetime import datetime, timedelta
from typing import Optional, Union
import jwt
from jwt.exceptions import InvalidTokenError
from pydantic import EmailStr
from src.auth.config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# create_refresh_token (JWT-based) was removed: refresh tokens are opaque, revocable rows
# issued by AuthService.create_user_session. Reintroducing a JWT variant would silently
# bring back unstored, unrevocable refresh tokens.

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except InvalidTokenError:
        raise ValueError("Could not validate credentials")
