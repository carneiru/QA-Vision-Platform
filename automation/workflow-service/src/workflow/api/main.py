"""
Workflow Designer API Main Module
"""
from fastapi import FastAPI
from src.workflow.api.v1.router import api_router

app = FastAPI(
    title="Workflow Service",
    description="Designs and manages workflow definitions for test automation",
    version="1.0.0"
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "workflow"}