"""
Collection Service Layer
"""
from typing import List, Optional
from src.artifact_management.models.collection import Collection
from src.artifact_management.schemas.collection import CollectionCreate, CollectionUpdate
from src.artifact_management.persistence.collection_repository import CollectionRepository

class CollectionService:
    def __init__(self, repository: CollectionRepository):
        self.repository = repository

    async def create_collection(self, collection: CollectionCreate) -> Collection:
        """Create a new collection"""
        return await self.repository.create(collection.dict())

    async def get_collection(self, collection_id: str) -> Optional[Collection]:
        """Get a collection by ID"""
        return await self.repository.get_by_id(collection_id)

    async def get_collections(self, skip: int = 0, limit: int = 100) -> List[Collection]:
        """Get collections with pagination"""
        return await self.repository.get_all(skip=skip, limit=limit)

    async def update_collection(self, collection_id: str, collection: CollectionUpdate) -> Optional[Collection]:
        """Update a collection"""
        update_data = collection.dict(exclude_unset=True)
        return await self.repository.update(collection_id, update_data)

    async def delete_collection(self, collection_id: str) -> bool:
        """Delete a collection"""
        return await self.repository.delete(collection_id)

    async def get_collection_types(self) -> List[str]:
        """Get all distinct collection types"""
        # This would typically be implemented with a database distinct query
        # For now, returning a hardcoded list based on our schema
        return ["test-run", "build", "release", "release-candidate", "hotfix", "other"]

    async def get_collections_by_type(self, collection_type: str) -> List[Collection]:
        """Get all collections of a specific type"""
        return await self.repository.get_by_collection_type(collection_type)

    async def get_collections_by_owner(self, owner: str) -> List[Collection]:
        """Get all collections owned by a specific user/system"""
        return await self.repository.get_by_owner(owner)