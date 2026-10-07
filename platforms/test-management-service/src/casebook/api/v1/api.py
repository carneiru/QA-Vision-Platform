from fastapi import APIRouter

from src.casebook.api.v1.endpoints import case_import, cases, ci_target, suites

api_router = APIRouter()
api_router.include_router(case_import.router, prefix="/projects/{project_id}/cases", tags=["cases"])
api_router.include_router(cases.router, prefix="/projects/{project_id}/cases", tags=["cases"])
api_router.include_router(cases.labels_router, prefix="/projects/{project_id}/case-labels", tags=["cases"])
api_router.include_router(cases.folders_router, prefix="/projects/{project_id}/case-folders", tags=["cases"])
api_router.include_router(cases.features_router, prefix="/projects/{project_id}/case-features", tags=["cases"])
api_router.include_router(suites.router, prefix="/projects/{project_id}/suites", tags=["suites"])
api_router.include_router(ci_target.router, prefix="/projects/{project_id}/ci-target", tags=["runs"])

__all__ = ["api_router"]
