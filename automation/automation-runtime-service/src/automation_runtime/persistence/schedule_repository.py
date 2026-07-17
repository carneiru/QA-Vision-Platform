"""
Schedule Repository
"""
from typing import List, Optional, Dict, Any
from ..models.schedule import Schedule
from ..db.mongodb import db

class ScheduleRepository:
    def __init__(self):
        self.collection = None

    async def _get_collection(self):
        if self.collection is None:
            self.collection = db.get_collection("schedules")
        return self.collection

    async def create(self, schedule_data: dict) -> Schedule:
        """Create a new schedule"""
        collection = await self._get_collection()
        if "_id" in schedule_data:
            del schedule_data["_id"]
        result = await collection.insert_one(schedule_data)
        return Schedule(**schedule_data)

    async def get_by_id(self, schedule_id: str) -> Optional[Schedule]:
        """Get a schedule by ID"""
        collection = await self._get_collection()
        document = await collection.find_one({"id": schedule_id})
        if document:
            document.pop("_id", None)
            return Schedule(**document)
        return None

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Schedule]:
        """Get all schedules with pagination"""
        collection = await self._get_collection()
        cursor = collection.find().skip(skip).limit(limit)
        schedules = []
        async for document in cursor:
            document.pop("_id", None)
            schedules.append(Schedule(**document))
        return schedules

    async def get_by_type(self, schedule_type: str, skip: int = 0, limit: int = 100) -> List[Schedule]:
        """Get schedules by type"""
        collection = await self._get_collection()
        cursor = collection.find({"schedule_type": schedule_type}).skip(skip).limit(limit)
        schedules = []
        async for document in cursor:
            document.pop("_id", None)
            schedules.append(Schedule(**document))
        return schedules

    async def get_by_status(self, status: str, skip: int = 0, limit: int = 100) -> List[Schedule]:
        """Get schedules by status"""
        collection = await self._get_collection()
        cursor = collection.find({"status": status}).skip(skip).limit(limit)
        schedules = []
        async for document in cursor:
            document.pop("_id", None)
            schedules.append(Schedule(**document))
        return schedules

    async def get_by_workflow_id(self, workflow_id: str, skip: int = 0, limit: int = 100) -> List[Schedule]:
        """Get schedules by workflow ID"""
        collection = await self._get_collection()
        cursor = collection.find({"workflow_id": workflow_id}).skip(skip).limit(limit)
        schedules = []
        async for document in cursor:
            document.pop("_id", None)
            schedules.append(Schedule(**document))
        return schedules

    async def update(self, schedule_id: str, update_data: dict) -> Optional[Schedule]:
        """Update a schedule"""
        collection = await self._get_collection()
        if "_id" in update_data:
            del update_data["_id"]
        result = await collection.update_one({"id": schedule_id}, {"$set": update_data})
        if result.modified_count == 1:
            return await self.get_by_id(schedule_id)
        return None

    async def delete(self, schedule_id: str) -> bool:
        """Delete a schedule"""
        collection = await self._get_collection()
        result = await collection.delete_one({"id": schedule_id})
        return result.deleted_count > 0