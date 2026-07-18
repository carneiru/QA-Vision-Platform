"""Model Training Service Main Entry Point."""

import uvicorn

from model_training.api import api_router
from model_training.config import settings

def create_app():
    """Create and configure the FastAPI application."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(
        title="Model Training Service",
        description="Service for training and managing machine learning models",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API router
    app.include_router(api_router, prefix="/api/v1")

    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "model_training.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )