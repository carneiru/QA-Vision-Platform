"""
Artifacts API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from src.artifact_management.schemas.artifact import ArtifactCreate, ArtifactUpdate, ArtifactResponse
from src.artifact_management.service.artifact_service import ArtifactService

router = APIRouter()


@router.post("/", response_model=ArtifactResponse, status_code=status.HTTP_201_CREATED)
async def create_artifact(
    artifact: ArtifactCreate,
    service: ArtifactService = Depends()
):
    """Create a new artifact"""
    return await service.create_artifact(artifact)


@router.get("/", response_model=List[ArtifactResponse])
async def list_artifacts(
    skip: int = 0,
    limit: int = 100,
    service: ArtifactService = Depends()
):
    """List artifacts with pagination"""
    return await service.get_artifacts(skip=skip, limit=limit)


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(
    artifact_id: str,
    service: ArtifactService = Depends()
):
    """Get a specific artifact by ID"""
    artifact = await service.get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


@router.put("/{artifact_id}", response_model=ArtifactResponse)
async def update_artifact(
    artifact_id: str,
    artifact: ArtifactUpdate,
    service: ArtifactService = Depends()
):
    """Update an artifact"""
    updated_artifact = await service.update_artifact(artifact_id, artifact)
    if not updated_artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return updated_artifact


@router.delete("/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_artifact(
    artifact_id: str,
    service: ArtifactService = Depends()
):
    """Delete an artifact"""
    deleted = await service.delete_artifact(artifact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return None


@router.get("/collection/{collection_id}", response_model=List[ArtifactResponse])
async def get_artifacts_by_collection(
    collection_id: str,
    service: ArtifactService = Depends()
):
    """Get all artifacts for a specific collection"""
    return await service.get_artifacts_by_collection(collection_id)


@router.get("/type/{artifact_type}", response_model=List[ArtifactResponse])
async def get_artifacts_by_type(
    artifact_type: str,
    service: ArtifactService = Depends()
):
    """Get all artifacts of a specific type"""
    return await service.get_artifacts_by_type(artifact_type)