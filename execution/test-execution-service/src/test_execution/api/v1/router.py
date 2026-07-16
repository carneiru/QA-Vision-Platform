"""
Test Execution API Router
"""
from fastapi import APIRouter
from src.test_execution.api.v1.endpoints import test_runs, test_results

api_router = APIRouter()
api_router.include_router(test_runs.router, prefix="/test-runs", tags=["test-runs"])
api_router.include_router(test_results.router, prefix="/test-results", tags=["test-results"])