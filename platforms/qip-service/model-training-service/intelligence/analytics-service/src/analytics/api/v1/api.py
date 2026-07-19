from fastapi import APIRouter
from .endpoints import auth, users, sso

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(sso.router, prefix="/sso", tags=["sso"])

__all__ = ["api_router"]