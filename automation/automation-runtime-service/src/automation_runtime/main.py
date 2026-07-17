"""
Automation Runtime Service Main Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.automation_runtime.api.v1.router import api_router
from src.automation_runtime.db.database import create_tables
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Automation Runtime Service",
    description="Service for managing workflow executions, triggers, and schedules",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    create_tables()
    logger.info("Database tables created")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "automation-runtime"}

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Automation Runtime Service",
        "version": "1.0.0",
        "docs": "/docs"
    }
EOF