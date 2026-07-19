"""
Collection Repository
"""
from typing import List, Optional, Dict, Any
from src.artifact_management.models.collection import Collection
from src.artifact_management.db.mongodb import MongoDB

class CollectionRepository:
    def __init__(self, database: MongoDB):
        self.collection = database.get_collection("collections")

    async def create(self, data: Dict[str, Any]) -> Collection:
        """Create a new collection"""
        result = await self.collection.insert_one(data)
        data["_id"] = result.inserted_id
        return Collection(**data)

    async def get_by_id(self, collection_id: str) -> Optional[Collection]:
        """Get a collection by ID"""
        data = await self.collection.find_one({"_id": collection_id})
        if data:
            return Collection(**data)
        return None

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Collection]:
        """Get collections with pagination"""
        cursor = self.collection.find().skip(skip).limit(limit)
        collections = []
        async for document in cursor:
            collections.append(Collection(**document))
        return collections

    async def update(self, collection_id: str, data: Dict[str, Any]) -> Optional[Collection]:
        """Update a collection"""
        await self.collection.update_one({"_id": collection_id}, {"$set": data})
        return await self.get_by_id(collection_id)

    async def delete(self, collection_id: str) -> bool:
        """Delete a collection"""
        result = await self.collection.delete_one({"_id": collection_id})
        return result.deleted_count > 0

    async def get_by_collection_type(self, collection_type: str) -> List[Collection]:
        """Get collections by type"""
        cursor = self.collection.find({"collection_type": collection_type})
        collections = []
        async for document in cursor:
            collections.append(Collection(**document))
        return collections

    async def get_by_owner(self, owner: str) -> List[Collection]:
        """Get collections by owner"""
        cursor = self.collection.find({"owner": owner})
        collections = []
        async for document in cursor:
            collections.append(Collection(**document))
        return collections