from fastapi import APIRouter
from src.organization.api.v1.endpoints import organizations, members

api_router = APIRouter()
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(members.router, prefix="/organizations/{org_id}/members", tags=["members"])

__all__ = ["api_router"]
