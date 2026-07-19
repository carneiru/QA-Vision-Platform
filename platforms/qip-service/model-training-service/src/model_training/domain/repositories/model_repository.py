"""Repository interface for model aggregate."""

from abc import ABC, abstractmethod
from typing import List, Optional
from ..domain.aggregates.model_aggregate import ModelAggregate


class ModelRepository(ABC):
    """Abstract repository for model aggregate."""

    @abstractmethod
    def get_by_id(self, model_id: str) -> Optional[ModelAggregate]:
        """Get model by ID."""
        pass

    @abstractmethod
    def add(self, model: ModelAggregate) -> None:
        """Add a new model."""
        pass

    @abstractmethod
    def update(self, model: ModelAggregate) -> None:
        """Update an existing model."""
        pass

    @abstractmethod
    def delete(self, model_id: str) -> bool:
        """Delete a model by ID."""
        pass

    @abstractmethod
    def list_models(self, skip: int = 0, limit: int = 100, status: Optional[str] = None) -> List[ModelAggregate]:
        """List models with optional filtering."""
        pass

    @abstractmethod
    def exists(self, model_id: str) -> bool:
        """Check if a model exists."""
        pass