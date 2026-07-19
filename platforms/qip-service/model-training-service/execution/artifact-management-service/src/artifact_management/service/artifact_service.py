"""
Artifact Service Layer
"""
from typing import List, Optional
from src.artifact_management.models.artifact import Artifact
from src.artifact_management.schemas.artifact import ArtifactCreate, ArtifactUpdate
from src.artifact_management.persistence.artifact_repository import ArtifactRepository

class ArtifactService:
    def __init__(self, repository: ArtifactRepository):
        self.repository = repository

    async def create_artifact(self, artifact: ArtifactCreate) -> Artifact:
        """Create a new artifact"""
        return await self.repository.create(artifact.dict())

    async def get_artifact(self, artifact_id: str) -> Optional[Artifact]:
        """Get an artifact by ID"""
        return await self.repository.get_by_id(artifact_id)

    async def get_artifacts(self, skip: int = 0, limit: int = 100) -> List[Artifact]:
        """Get artifacts with pagination"""
        return await self.repository.get_all(skip=skip, limit=limit)

    async def update_artifact(self, artifact_id: str, artifact: ArtifactUpdate) -> Optional[Artifact]:
        """Update an artifact"""
        update_data = artifact.dict(exclude_unset=True)
        return await self.repository.update(artifact_id, update_data)

    async def delete_artifact(self, artifact_id: str) -> bool:
        """Delete an artifact"""
        return await self.repository.delete(artifact_id)

    async def get_artifacts_by_collection(self, collection_id: str) -> List[Artifact]:
        """Get all artifacts for a specific collection"""
        return await self.repository.get_by_collection_id(collection_id)

    async def get_artifacts_by_type(self, artifact_type: str) -> List[Artifact]:
        """Get all artifacts of a specific type"""
        return await self.repository.get_by_artifact_type(artifact_type)