"""
Step Repository
"""
from typing import List, Optional, Dict, Any
from src.workflow_designer.models.step import Step
from src.workflow_designer.db.mongodb import MongoDB

class StepRepository:
    def __init__(self, database: MongoDB):
        self.collection = database.get_collection("steps")

    async def create(self, data: Dict[str, Any]) -> Step:
        """Create a new step"""
        result = await self.collection.insert_one(data)
        data["_id"] = result.inserted_id
        return Step(**data)

    async def get_by_id(self, step_id: str) -> Optional[Step]:
        """Get a step by ID"""
        data = await self.collection.find_one({"_id": step_id})
        if data:
            return Step(**data)
        return None

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Step]:
        """Get steps with pagination"""
        cursor = self.collection.find().skip(skip).limit(limit)
        steps = []
        async for document in cursor:
            steps.append(Step(**document))
        return steps

    async def update(self, step_id: str, data: Dict[str, Any]) -> Optional[Step]:
        """Update a step"""
        await self.collection.update_one({"_id": step_id}, {"$set": data})
        return await self.get_by_id(step_id)

    async def delete(self, step_id: str) -> bool:
        """Delete a step"""
        result = await self.collection.delete_one({"_id": step_id})
        return result.deleted_count > 0

    async def get_by_workflow_id(self, workflow_id: str) -> List[Step]:
        """Get steps by workflow ID"""
        cursor = self.collection.find({"workflow_id": workflow_id})
        steps = []
        async for document in cursor:
            steps.append(Step(**document))
        return steps

    async def get_by_step_type(self, step_type: str) -> List[Step]:
        """Get steps by type"""
        cursor = self.collection.find({"step_type": step_type})
        steps = []
        async for document in cursor:
            steps.append(Step(**document))
        return steps