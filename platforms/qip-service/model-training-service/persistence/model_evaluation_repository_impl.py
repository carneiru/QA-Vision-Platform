"""SQLAlchemy implementation of ModelEvaluationRepository."""
from typing import List, Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from domain.model import ModelEvaluation
from persistence.base_repository import BaseRepository


class ModelEvaluationRepositoryImpl(BaseRepository[ModelEvaluation]):
    """SQLAlchemy implementation of ModelEvaluationRepository."""

    async def get_by_model_id(self, model_id: str) -> List[ModelEvaluation]:
        """Get all evaluations for a specific model."""
        stmt = select(self._model).where(self._model.model_id == model_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update(self, evaluation: ModelEvaluation) -> ModelEvaluation:
        """Update an existing evaluation."""
        # Update the object with new values
        stmt = (
            update(self._model)
            .where(self._model.id == evaluation.id)
            .values(**{k: v for k, v in evaluation.__dict__.items()
                      if not k.startswith('_') and k != 'id'})
        )
        await self._session.execute(stmt)
        await self._session.flush()

        # Return the updated object
        return await self.get_by_id(evaluation.id)