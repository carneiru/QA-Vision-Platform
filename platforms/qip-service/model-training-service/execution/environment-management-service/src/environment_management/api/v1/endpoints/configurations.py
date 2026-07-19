"""
Configuration API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from src.environment_management.schemas.configuration import ConfigurationCreate, ConfigurationUpdate, ConfigurationResponse
from src.environment_management.service.configuration_service import ConfigurationService

router = APIRouter()


@router.post("/", response_model=ConfigurationResponse, status_code=status.HTTP_201_CREATED)
async def create_configuration(
    configuration: ConfigurationCreate,
    service: ConfigurationService = Depends()
):
    """Create a new configuration"""
    return await service.create_configuration(configuration)


@router.get("/", response_model=List[ConfigurationResponse])
async def list_configurations(
    skip: int = 0,
    limit: int = 100,
    service: ConfigurationService = Depends()
):
    """List configurations with pagination"""
    return await service.get_configurations(skip=skip, limit=limit)


@router.get("/{configuration_id}", response_model=ConfigurationResponse)
async def get_configuration(
    configuration_id: str,
    service: ConfigurationService = Depends()
):
    """Get a specific configuration by ID"""
    configuration = await service.get_configuration(configuration_id)
    if not configuration:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return configuration


@router.put("/{configuration_id}", response_model=ConfigurationResponse)
async def update_configuration(
    configuration_id: str,
    configuration: ConfigurationUpdate,
    service: ConfigurationService = Depends()
):
    """Update a configuration"""
    updated_configuration = await service.update_configuration(configuration_id, configuration)
    if not updated_configuration:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return updated_configuration


@router.delete("/{configuration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_configuration(
    configuration_id: str,
    service: ConfigurationService = Depends()
):
    """Delete a configuration"""
    deleted = await service.delete_configuration(configuration_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return None


@router.get("/environment/{environment_id}", response_model=List[ConfigurationResponse])
async def get_configurations_by_environment(
    environment_id: str,
    service: ConfigurationService = Depends()
):
    """Get all configurations for a specific environment"""
    return await service.get_configurations_by_environment(environment_id)