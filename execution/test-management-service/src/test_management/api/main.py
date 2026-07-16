"""
Test Management API Main Module
"""
from fastapi import FastAPI
from src.test_management.api.v1.router import api_router

app = FastAPI(
    title="Test Management Service",
    description="Manages test cases, test suites, and test specifications",
    version="1.0.0"
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "test-management"}