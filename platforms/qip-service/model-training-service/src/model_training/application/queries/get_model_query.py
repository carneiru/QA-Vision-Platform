"""Query for getting model information."""

from dataclasses import dataclass
from typing import Optional
from ....domain.aggregates.model_aggregate import ModelAggregate
from ....domain.repositories.model_repository import ModelRepository


@dataclass
class GetModelQuery:
    """Query to get model information."""

    model_id: str

    def execute(self, repository: ModelRepository) -> Optional[ModelAggregate]:
        """Execute the get model query."""
        return repository.get_by_id(self.model_id)


@dataclass
class ListModelsQuery:
    """Query to list models with optional filtering."""

    skip: int = 0
    limit: int = 100
    status: Optional[str] = None

    def execute(self, repository: ModelRepository) -> list:
        """Execute the list models query."""
        return repository.list_models(skip=self.skip, limit=self.limit, status=self.status)