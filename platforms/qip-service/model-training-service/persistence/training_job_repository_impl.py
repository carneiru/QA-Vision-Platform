"""SQLAlchemy implementation of TrainingJobRepository."""
from typing import List, Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from domain.model import TrainingJob
from persistence.base_repository import BaseRepository


class TrainingJobRepositoryImpl(BaseRepository[TrainingJob]):
    """SQLAlchemy implementation of TrainingJobRepository."""

    async def get_by_model_id(self, model_id: str) -> List[TrainingJob]:
        """Get all training jobs for a specific model."""
        stmt = select(self._model).where(self._model.model_id == model_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_by_status(self, status: str) -> List[TrainingJob]:
        """Get all jobs by their status."""
        stmt = select(self._model).where(self._model.status == status)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_active_jobs(self) -> List[TrainingJob]:
        """Get all active training jobs."""
        # Assuming active jobs are those with status 'training' or 'pending'
        stmt = select(self._model).where(
            self._model.status.in_(['training', 'pending'])
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update(self, job: TrainingJob) -> TrainingJob:
        """Update an existing training job."""
        # Update the object with new values
        stmt = (
            update(self._model)
            .where(self._model.id == job.id)
            .values(**{k: v for k, v in job.__dict__.items()
                      if not k.startswith('_') and k != 'id'})
        )
        await self._session.execute(stmt)
        await self._session.flush()

        # Return the updated object
        return await self.get_by_id(job.id)