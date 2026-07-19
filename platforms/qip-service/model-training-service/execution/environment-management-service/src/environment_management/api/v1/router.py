"""
Environment Management API Router
"""
from fastapi import APIRouter
from src.environment_management.api.v1.endpoints import environments, configurations

api_router = APIRouter()
api_router.include_router(environments.router, prefix="/environments", tags=["environments"])
api_router.include_router(configurations.router, prefix="/configurations", tags=["configurations"])