"""Base repository interface."""
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """Base repository interface defining common CRUD operations."""

    @abstractmethod
    async def create(self, obj: T) -> T:
        """Create a new entity."""
        pass

    @abstractmethod
    async def get_by_id(self, id: str) -> Optional[T]:
        """Get an entity by its ID."""
        pass

    @abstractmethod
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """Get all entities with pagination."""
        pass

    @abstractmethod
    async def update(self, id: str, obj: T) -> Optional[T]:
        """Update an existing entity."""
        pass

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Delete an entity by its ID."""
        pass