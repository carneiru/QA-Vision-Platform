"""
API endpoints for the Data Preparation service
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
import logging

from ..service import DataPreparationService
from ..repository import DataPreparationRepository

logger = logging.getLogger(__name__)

router = APIRouter()


# Simple factory for dependency injection
def get_data_preparation_repository() -> DataPreparationRepository:
    """Get data preparation repository instance."""
    return DataPreparationRepository()


def get_data_preparation_service(
    repository: DataPreparationRepository = Depends(get_data_preparation_repository)
) -> DataPreparationService:
    """Dependency to get data preparation service instance."""
    return DataPreparationService(repository=repository)


@router.post("/prepare", response_model=List[Dict[str, Any]])
async def prepare_data(
    source: str = Query(..., description="Data source identifier"),
    config: Optional[Dict[str, Any]] = None,
    service: DataPreparationService = Depends(get_data_preparation_service)
):
    """Prepare data from a source."""
    try:
        result = await service.prepare_data(source=source, config=config)
        return result
    except Exception as e:
        logger.error(f"Error preparing data from {source}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
async def validate_data_quality(
    data: List[Dict[str, Any]],
    service: DataPreparationService = Depends(get_data_preparation_service)
):
    """Validate the quality of prepared data."""
    try:
        result = await service.validate_data_quality(data=data)
        return result
    except Exception as e:
        logger.error(f"Error validating data quality: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "data-preparation"}