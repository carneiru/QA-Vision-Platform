"""
Main API Router for Test Management Service
"""
from fastapi import APIRouter
from src.test_management.api.v1.endpoints import test_cases, test_suites, test_specifications

api_router = APIRouter()

api_router.include_router(test_cases.router, prefix="/test-cases", tags=["test-cases"])
api_router.include_router(test_suites.router, prefix="/test-suites", tags=["test-suites"])
api_router.include_router(test_specifications.router, prefix="/test-specifications", tags=["test-specifications"])