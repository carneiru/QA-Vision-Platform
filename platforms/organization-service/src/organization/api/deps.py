from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
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


def require_org_role(*roles: str):
    from src.organization.service.member_service import get_role  # local import avoids a service->deps->service cycle

    def dependency(
        org_id: int,
        db: Session = Depends(get_db),
        user_id: int = Depends(get_current_user_id),
    ) -> str:
        role = get_role(db, org_id, user_id)
        if role is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not a member of this organization")
        if role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return role

    return dependency


__all__ = ["get_db", "get_current_user_id", "require_org_role"]
