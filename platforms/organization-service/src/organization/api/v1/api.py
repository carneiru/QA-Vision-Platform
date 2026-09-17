from fastapi import APIRouter
from src.organization.api.v1.endpoints import organizations

api_router = APIRouter()
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])

__all__ = ["api_router"]
