"""Repository interface for ModelEvaluation entity."""
from abc import ABC, abstractmethod
from typing import List, Optional
from domain.model import ModelEvaluation


class ModelEvaluationRepository(ABC):
    """Abstract repository for ModelEvaluation entities."""

    @abstractmethod
    async def create(self, evaluation: ModelEvaluation) -> ModelEvaluation:
        """Create a new model evaluation."""
        ...

    @abstractmethod
    async def get_by_id(self, evaluation_id: str) -> Optional[ModelEvaluation]:
        """Get an evaluation by its ID."""
        ...

    @abstractmethod
    async def get_by_model_id(self, model_id: str) -> List[ModelEvaluation]:
        """Get all evaluations for a specific model."""
        ...

    @abstractmethod
    async def update(self, evaluation: ModelEvaluation) -> ModelEvaluation:
        """Update an existing evaluation."""
        ...

    @abstractmethod
    async def delete(self, evaluation_id: str) -> bool:
        """Delete an evaluation by its ID."""
        ...