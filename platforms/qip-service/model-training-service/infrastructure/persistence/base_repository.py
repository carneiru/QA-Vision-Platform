"""SQLAlchemy base repository implementation."""
from abc import ABC
from typing import Generic, TypeVar, List, Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from persistence.base_repository import BaseRepository as BaseRepositoryInterface

T = TypeVar("T")


class BaseRepository(BaseRepositoryInterface[T], ABC, Generic[T]):
    """Base repository implementation for SQLAlchemy models."""

    def __init__(self, session: AsyncSession, model: type[T]):
        self._session = session
        self._model = model

    async def create(self, obj: T) -> T:
        """Create a new entity."""
        self._session.add(obj)
        await self._session.flush()
        await self._session.refresh(obj)
        return obj

    async def get_by_id(self, id: str) -> Optional[T]:
        """Get an entity by its ID."""
        stmt = select(self._model).where(self._model.id == id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """Get all entities with pagination."""
        stmt = select(self._model).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def update(self, id: str, obj: T) -> Optional[T]:
        """Update an existing entity."""
        # Update the object with new values
        stmt = (
            update(self._model)
            .where(self._model.id == id)
            .values(**{k: v for k, v in obj.__dict__.items()
                      if not k.startswith('_') and k != 'id'})
        )
        await self._session.execute(stmt)
        await self._session.flush()

        # Return the updated object
        return await self.get_by_id(id)

    async def delete(self, id: str) -> bool:
        """Delete an entity by its ID."""
        stmt = delete(self._model).where(self._model.id == id)
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0