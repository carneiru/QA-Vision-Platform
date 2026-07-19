"""Repository interface for TrainingJob entity."""
from abc import ABC, abstractmethod
from typing import List, Optional
from domain.model import TrainingJob


class TrainingJobRepository(ABC):
    """Abstract repository for TrainingJob entities."""

    @abstractmethod
    async def create(self, job: TrainingJob) -> TrainingJob:
        """Create a new training job."""
        ...

    @abstractmethod
    async def get_by_id(self, job_id: str) -> Optional[TrainingJob]:
        """Get a job by its ID."""
        ...

    @abstractmethod
    async def get_by_model_id(self, model_id: str) -> List[TrainingJob]:
        """Get all training jobs for a specific model."""
        ...

    @abstractmethod
    async def get_by_status(self, status: str) -> List[TrainingJob]:
        """Get all jobs by their status."""
        ...

    @abstractmethod
    async def get_active_jobs(self) -> List[TrainingJob]:
        """Get all active training jobs."""
        ...

    @abstractmethod
    async def update(self, job: TrainingJob) -> TrainingJob:
        """Update an existing training job."""
        ...

    @abstractmethod
    async def delete(self, job_id: str) -> bool:
        """Delete a training job by its ID."""
        ...