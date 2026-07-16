"""
Test Execution API Main Module
"""
from fastapi import FastAPI
from src.test_execution.api.v1.router import api_router

app = FastAPI(
    title="Test Execution Service",
    description="Orchestrates test execution, manages test runs, and collects results",
    version="1.0.0"
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "test-execution"}