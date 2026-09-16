from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from src.organization.db.session import get_db
from src.organization.utils.tokens import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_exception
    try:
        payload = decode_token(token)
        return int(payload["sub"])
    except (ValueError, KeyError, TypeError):
        raise credentials_exception


__all__ = ["get_db", "get_current_user_id"]
