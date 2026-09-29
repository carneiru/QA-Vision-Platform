from fastapi import APIRouter

from src.ingestion.api.v1.endpoints import api_keys

api_router = APIRouter()
api_router.include_router(api_keys.router, prefix="/projects/{project_id}/api-keys", tags=["api-keys"])

__all__ = ["api_router"]
