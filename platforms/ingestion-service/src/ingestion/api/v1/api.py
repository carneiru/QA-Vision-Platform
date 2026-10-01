from fastapi import APIRouter

from src.ingestion.api.v1.endpoints import analytics, api_keys, collect, runs

api_router = APIRouter()
api_router.include_router(api_keys.router, prefix="/projects/{project_id}/api-keys", tags=["api-keys"])
api_router.include_router(runs.project_router, prefix="/projects/{project_id}/runs", tags=["runs"])
api_router.include_router(analytics.router, prefix="/projects/{project_id}/analytics", tags=["analytics"])
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
api_router.include_router(collect.router, prefix="/collect", tags=["collect"])

__all__ = ["api_router"]
