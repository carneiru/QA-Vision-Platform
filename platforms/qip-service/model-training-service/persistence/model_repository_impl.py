"""SQLAlchemy implementation of ModelRepository."""
from typing import List, Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from domain.model import Model
from persistence.base_repository import BaseRepository


class ModelRepositoryImpl(BaseRepository[Model]):
    """SQLAlchemy implementation of ModelRepository."""

    async def get_by_name(self, name: str) -> Optional[Model]:
        """Get a model by its name."""
        stmt = select(self._model).where(self._model.name == name)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_status(self, status: str) -> List[Model]:
        """Get models by their status."""
        stmt = select(self._model).where(self._model.status == status)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def get_active_models(self) -> List[Model]:
        """Get all active models."""
        stmt = select(self._model).where(self._model.status == "active")
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update(self, model: Model) -> Model:
        """Update an existing model."""
        # Update the object with new values
        stmt = (
            update(self._model)
            .where(self._model.id == model.id)
            .values(**{k: v for k, v in model.__dict__.items()
                      if not k.startswith('_') and k != 'id'})
        )
        await self._session.execute(stmt)
        await self._session.flush()

        # Return the updated object
        return await self.get_by_id(model.id)