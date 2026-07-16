"""
Artifact Management API Router
"""
from fastapi import APIRouter
from src.artifact_management.api.v1.endpoints import artifacts, collections

api_router = APIRouter()
api_router.include_router(artifacts.router, prefix="/artifacts", tags=["artifacts"])
api_router.include_router(collections.router, prefix="/collections", tags=["collections"])