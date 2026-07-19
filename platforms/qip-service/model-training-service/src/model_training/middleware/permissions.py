"""Role-Based Access Control (RBAC) permissions."""

from functools import wraps
from typing import List, Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

from model_training.middleware.auth import JWTBearer
from model_training.exceptions import AuthorizationError


# Define roles
class Roles:
    """User roles."""
    ADMIN = "admin"
    TRAINER = "trainer"
    EVALUATOR = "evaluator"
    VIEWER = "viewer"


# Permission mapping
PERMISSIONS = {
    Roles.ADMIN: [
        "model:create",
        "model:read",
        "model:update",
        "model:delete",
        "model:train",
        "model:evaluate",
        "model:deploy",
        "model:retire",
        "user:manage",
        "system:configure",
    ],
    Roles.TRAINER: [
        "model:create",
        "model:read",
        "model:update",
        "model:train",
        "model:evaluate",
    ],
    Roles.EVALUATOR: [
        "model:read",
        "model:evaluate",
    ],
    Roles.VIEWER: [
        "model:read",
    ],
}


def has_permission(user_roles: List[str], permission: str) -> bool:
    """Check if user roles have the specified permission."""
    for role in user_roles:
        if role in PERMISSIONS and permission in PERMISSIONS[role]:
            return True
    return False


def require_permission(permission: str):
    """Decorator to require specific permission."""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get credentials from dependencies
            credentials: HTTPAuthorizationCredentials = kwargs.get(
                "credentials"
            )
            if not credentials:
                # Try to find it in args
                for arg in args:
                    if isinstance(
                        arg, HTTPAuthorizationCredentials
                    ):
                        credentials = arg
                        break

            if not credentials:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                )

            # Decode token to get user roles
            try:
                from jose import jwt
                from model_training.config import settings

                payload = jwt.decode(
                    credentials.credentials,
                    settings.SECRET_KEY,
                    algorithms=[settings.ALGORITHM],
                )
                user_roles = payload.get("roles", [])

                if not has_permission(user_roles, permission):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied. Required: {permission}",
                    )
            except JWTError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication token",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_roles(allowed_roles: List[str]):
    """Decorator to require specific roles."""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get credentials from dependencies
            credentials: HTTPAuthorizationCredentials = kwargs.get(
                "credentials"
            )
            if not credentials:
                # Try to find it in args
                for arg in args:
                    if isinstance(
                        arg, HTTPAuthorizationCredentials
                    ):
                        credentials = arg
                        break

            if not credentials:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                )

            # Decode token to get user roles
            try:
                from jose import jwt
                from model_training.config import settings

                payload = jwt.decode(
                    credentials.credentials,
                    settings.SECRET_KEY,
                    algorithms=[settings.ALGORITHM],
                )
                user_roles = payload.get("roles", [])

                if not any(role in user_roles for role in allowed_roles):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Insufficient permissions. Required roles: {allowed_roles}",
                    )
            except JWTError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication token",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator