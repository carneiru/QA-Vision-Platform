"""Authentication dependencies."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from model_training.config import settings
from model_training.security.jwt import verify_token
from model_training.exceptions import AuthenticationError, AuthorizationError

# Security scheme
security = HTTPBearer()


async get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = verify_token(credentials.credentials)
        return payload
    except JWTError:
        raise credentials_exception
    except Exception:
        raise credentials_exception


def require_role(required_role: str):
    """Dependency to require a specific role."""
    def role_dependency(current_user: dict = Depends(get_current_user)):
        user_roles = current_user.get("roles", [])
        if required_role not in user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}",
            )
        return current_user
    return Depends(role_dependency)


def require_any_role(required_roles: list):
    """Dependency to require any of the specified roles."""
    def role_dependency(current_user: dict = Depends(get_current_user)):
        user_roles = set(current_user.get("roles", []))
        required_roles_set = set(required_roles)
        if not user_roles.intersection(required_roles_set):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required one of: {required_roles}",
            )
        return current_user
    return Depends(role_dependency)