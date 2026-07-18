"""Repository interface for ModelVersion entity."""
from abc import ABC, abstractmethod
from typing import List, Optional
from domain.model import ModelVersion


class ModelVersionRepository(ABC):
    """Abstract repository for ModelVersion entities."""

    @abstractmethod
    async def create(self, version: ModelVersion) -> ModelVersion:
        """Create a new model version."""
        ...

    @abstractmethod
    async def get_by_id(self, version_id: str) -> Optional[ModelVersion]:
        """Get a version by its ID."""
        ...

    @abstractmethod
    async def get_by_model_id(self, model_id: str) -> List[ModelVersion]:
        """Get all versions for a specific model."""
        ...

    @abstractmethod
    async def get_latest_version(self, model_id: str) -> Optional[ModelVersion]:
        """Get the latest version of a model."""
        ...

    @abstractmethod
    async def update(self, version: ModelVersion) -> ModelVersion:
        """Update an existing version."""
        ...

    @abstractmethod
    async def delete(self, version_id: str) -> bool:
        """Delete a version by its ID."""
        ...