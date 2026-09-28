from fastapi import APIRouter

from src.project.api.v1.endpoints import projects, repositories

api_router = APIRouter()
api_router.include_router(projects.org_router, prefix="/organizations/{org_id}/projects", tags=["projects"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(
    repositories.router, prefix="/projects/{project_id}/repositories", tags=["repositories"]
)

__all__ = ["api_router"]
