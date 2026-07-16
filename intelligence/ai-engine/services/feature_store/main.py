"""
Main application entry point for the Feature Store service
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router as feature_store_router
from . import database
from shared.logging import setup_logging
from shared.config import get_settings

# Setup logging
settings = get_settings()
setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="QA Vision AI Engine - Feature Store Service",
    description="Service for managing ML features with versioning and retrieval capabilities",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(feature_store_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info("Starting Feature Store Service")
    # Initialize database connection
    try:
        # Test database connection
        async for session in database.get_async_session():
            await session.execute("SELECT 1")
            break
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        # Don't fail startup in development, but log the error
        if not settings.DEBUG:
            raise


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("Shutting down Feature Store Service")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Feature Store Service",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "feature-store",
        "version": "0.1.0"
    }