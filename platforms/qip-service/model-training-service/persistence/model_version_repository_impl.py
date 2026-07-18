"""SQLAlchemy implementation of ModelVersionRepository."""
from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from domain.model import ModelVersion
from persistence.base_repository import BaseRepository


class ModelVersionRepositoryImpl(BaseRepository[ModelVersion]):
    """SQLAlchemy implementation of ModelVersionRepository."""

    async def get_by_model_id(self, model_id: str) -> List[ModelVersion]:
        """Get all versions for a specific model."""
        stmt = select(self._model).where(self._model.model_id == model_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_latest_version(self, model_id: str) -> Optional[ModelVersion]:
        """Get the latest version of a model."""
        stmt = (
            select(self._model)
            .where(self._model.model_id == model_id)
            .order_by(self._model.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, version: ModelVersion) -> ModelVersion:
        """Update an existing version."""
        # Update the object with new values
        stmt = (
            update(self._model)
            .where(self._model.id == version.id)
            .values(**{k: v for k, v in version.__dict__.items()
                      if not k.startswith('_') and k != 'id'})
        )
        await self._session.execute(stmt)
        await self._session.flush()

        # Return the updated object
        return await self.get_by_id(version.id)