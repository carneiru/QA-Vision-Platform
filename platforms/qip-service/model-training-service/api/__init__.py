"""API router for Model Training Service."""

from fastapi import APIRouter

from model_training.api import endpoints

api_router = APIRouter()
api_router.include_router(endpoints.router, prefix="/models", tags=["models"])