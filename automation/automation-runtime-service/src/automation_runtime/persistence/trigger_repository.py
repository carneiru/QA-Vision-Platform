"""
Trigger Repository
"""
from typing import List, Optional, Dict, Any
from ..models.trigger import Trigger
from ..db.mongodb import db

class TriggerRepository:
    def __init__(self):
        self.collection = None

    async def _get_collection(self):
        if self.collection is None:
            self.collection = db.get_collection("triggers")
        return self.collection

    async def create(self, trigger_data: dict) -> Trigger:
        """Create a new trigger"""
        collection = await self._get_collection()
        if "_id" in trigger_data:
            del trigger_data["_id"]
        result = await collection.insert_one(trigger_data)
        return Trigger(**trigger_data)

    async def get_by_id(self, trigger_id: str) -> Optional[Trigger]:
        """Get a trigger by ID"""
        collection = await self._get_collection()
        document = await collection.find_one({"id": trigger_id})
        if document:
            document.pop("_id", None)
            return Trigger(**document)
        return None

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Trigger]:
        """Get all triggers with pagination"""
        collection = await self._get_collection()
        cursor = collection.find().skip(skip).limit(limit)
        triggers = []
        async for document in cursor:
            document.pop("_id", None)
            triggers.append(Trigger(**document))
        return triggers

    async def get_by_type(self, trigger_type: str, skip: int = 0, limit: int = 100) -> List[Trigger]:
        """Get triggers by type"""
        collection = await self._get_collection()
        cursor = collection.find({"trigger_type": trigger_type}).skip(skip).limit(limit)
        triggers = []
        async for document in cursor:
            document.pop("_id", None)
            triggers.append(Trigger(**document))
        return triggers

    async def get_by_status(self, status: str, skip: int = 0, limit: int = 100) -> List[Trigger]:
        """Get triggers by status"""
        collection = await self._get_collection()
        cursor = collection.find({"status": status}).skip(skip).limit(limit)
        triggers = []
        async for document in cursor:
            document.pop("_id", None)
            triggers.append(Trigger(**document))
        return triggers

    async def get_by_workflow_id(self, workflow_id: str, skip: int = 0, limit: int = 100) -> List[Trigger]:
        """Get triggers by workflow ID"""
        collection = await self._get_collection()
        cursor = collection.find({"workflow_id": workflow_id}).skip(skip).limit(limit)
        triggers = []
        async for document in cursor:
            document.pop("_id", None)
            triggers.append(Trigger(**document))
        return triggers

    async def update(self, trigger_id: str, update_data: dict) -> Optional[Trigger]:
        """Update a trigger"""
        collection = await self._get_collection()
        if "_id" in update_data:
            del update_data["_id"]
        result = await collection.update_one({"id": trigger_id}, {"$set": update_data})
        if result.modified_count == 1:
            return await self.get_by_id(trigger_id)
        return None

    async def delete(self, trigger_id: str) -> bool:
        """Delete a trigger"""
        collection = await self._get_collection()
        result = await collection.delete_one({"id": trigger_id})
        return result.deleted_count > 0