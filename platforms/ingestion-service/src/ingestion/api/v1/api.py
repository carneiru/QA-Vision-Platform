from fastapi import APIRouter

from src.ingestion.api.v1.endpoints import api_keys, collect

api_router = APIRouter()
api_router.include_router(api_keys.router, prefix="/projects/{project_id}/api-keys", tags=["api-keys"])
api_router.include_router(collect.router, prefix="/collect", tags=["collect"])

__all__ = ["api_router"]
