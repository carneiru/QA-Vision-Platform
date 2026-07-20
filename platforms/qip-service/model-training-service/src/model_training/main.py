"""Model Training Service Main Entry Point."""

import uvicorn
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors.cors.CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from model_training.api import api_router
from model_training.config import settings
from model_training.config_dir.logging_config import setup_json_logging
from model_training.config_dir.tracing import setup_tracing
from model_training.middleware.validation import ValidationMiddleware
from model_training.middleware.correlation_id import CorrelationIDMiddleware
from model_training.middleware.idempotency import IdempotencyMiddleware


def create_app():
    """Create and configure the FastAPI application."""
    # Setup JSON logging as per Section 11.1 of Architecture Blueprint
    setup_json_logging(settings.LOG_LEVEL)

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

    # Add validation middleware for input sanitization
    app.add_middleware(ValidationMiddleware)

    # Add correlation ID middleware for request tracing
    app.add_middleware(CorrelationIDMiddleware)

    # Add idempotency middleware for preventing duplicate requests
    app.add_middleware(IdempotencyMiddleware)

    # Set up OpenTelemetry tracing
    setup_tracing(app)

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
        log_config=None,  # Disable Uvicorn's default logging to use our custom JSON logging
        access_log=False,  # Disable Uvicorn's access log to use our custom JSON logging
    )