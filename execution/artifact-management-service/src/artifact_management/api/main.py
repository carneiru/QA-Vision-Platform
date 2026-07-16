"""
Artifact Management API Main Module
"""
from fastapi import FastAPI
from src.artifact_management.api.v1.router import api_router

app = FastAPI(
    title="Artifact Management Service",
    description="Handles storage, retrieval, and management of test artifacts",
    version="1.0.0"
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "artifact-management"}