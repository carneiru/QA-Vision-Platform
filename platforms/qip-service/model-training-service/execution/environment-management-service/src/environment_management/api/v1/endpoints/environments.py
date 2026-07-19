"""
Environment API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from src.environment_management.schemas.environment import EnvironmentCreate, EnvironmentUpdate, EnvironmentResponse
from src.environment_management.service.environment_service import EnvironmentService

router = APIRouter()


@router.post("/", response_model=EnvironmentResponse, status_code=status.HTTP_201_CREATED)
async def create_environment(
    environment: EnvironmentCreate,
    service: EnvironmentService = Depends()
):
    """Create a new environment"""
    return await service.create_environment(environment)


@router.get("/", response_model=List[EnvironmentResponse])
async def list_environments(
    skip: int = 0,
    limit: int = 100,
    service: EnvironmentService = Depends()
):
    """List environments with pagination"""
    return await service.get_environments(skip=skip, limit=limit)


@router.get("/{environment_id}", response_model=EnvironmentResponse)
async def get_environment(
    environment_id: str,
    service: EnvironmentService = Depends()
):
    """Get a specific environment by ID"""
    environment = await service.get_environment(environment_id)
    if not environment:
        raise HTTPException(status_code=404, detail="Environment not found")
    return environment


@router.put("/{environment_id}", response_model=EnvironmentResponse)
async def update_environment(
    environment_id: str,
    environment: EnvironmentUpdate,
    service: EnvironmentService = Depends()
):
    """Update an environment"""
    updated_environment = await service.update_environment(environment_id, environment)
    if not updated_environment:
        raise HTTPException(status_code=404, detail="Environment not found")
    return updated_environment


@router.delete("/{environment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_environment(
    environment_id: str,
    service: EnvironmentService = Depends()
):
    """Delete an environment"""
    deleted = await service.delete_environment(environment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Environment not found")
    return None


@router.post("/{environment_id}/provision", response_model=EnvironmentResponse)
async def provision_environment(
    environment_id: str,
    service: EnvironmentService = Depends()
):
    """Provision an environment"""
    provisioned_environment = await service.provision_environment(environment_id)
    if not provisioned_environment:
        raise HTTPException(status_code=404, detail="Environment not found")
    return provisioned_environment


@router.post("/{environment_id}/deprovision", response_model=EnvironmentResponse)
async def deprovision_environment(
    environment_id: str,
    service: EnvironmentService = Depends()
):
    """Deprovision an environment"""
    deprovisioned_environment = await service.deprovision_environment(environment_id)
    if not deprovisioned_environment:
        raise HTTPException(status_code=404, detail="Environment not found")
    return deprovisioned_environment