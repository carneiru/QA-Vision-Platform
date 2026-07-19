"""JWT Authentication middleware for Model Training Service."""
import os
from typing import Optional
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from model_training.config.settings import settings

# Security scheme
security = HTTPBearer()


def verify_token(token: str) -> dict:
    """
    Verify JWT token and return payload.

    Args:
        token: JWT token string

    Returns:
        dict: Token payload

    Raises:
        HTTPException: If token is invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return payload
    except JWTError:
        raise credentials_exception


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = security
) -> dict:
    """
    Get current authenticated user from JWT token.

    Args:
        request: FastAPI request object
        credentials: HTTP authorization credentials

    Returns:
        dict: User information from token

    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = verify_token(token)
        return payload
    except HTTPException:
        raise credentials_exception
    except Exception:
        raise credentials_exception


def require_role(required_role: str):
    """
    Dependency to require a specific role.

    Args:
        required_role: Required role string

    Returns:
        Callable: Dependency function
    """
    def role_checker(current_user: dict = get_current_user) -> dict:
        user_roles = current_user.get("roles", [])
        if required_role not in user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}"
            )
        return current_user
    return role_checker


def require_any_role(required_roles: list):
    """
    Dependency to require any of the specified roles.

    Args:
        required_roles: List of acceptable role strings

    Returns:
        Callable: Dependency function
    """
    def role_checker(current_user: dict = get_current_user) -> dict:
        user_roles = set(current_user.get("roles", []))
        required_roles_set = set(required_roles)
        if not user_roles.intersection(required_roles_set):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required one of: {required_roles}"
            )
        return current_user
    return role_checker