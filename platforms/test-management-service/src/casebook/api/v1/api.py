from fastapi import APIRouter

from src.casebook.api.v1.endpoints import cases, suites

api_router = APIRouter()
api_router.include_router(cases.router, prefix="/projects/{project_id}/cases", tags=["cases"])
api_router.include_router(cases.labels_router, prefix="/projects/{project_id}/case-labels", tags=["cases"])
api_router.include_router(suites.router, prefix="/projects/{project_id}/suites", tags=["suites"])

__all__ = ["api_router"]
