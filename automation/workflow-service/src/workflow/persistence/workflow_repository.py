"""
Workflow Repository
"""
from typing import List, Optional, Dict, Any
from src.workflow_designer.models.workflow import Workflow
from src.workflow_designer.db.mongodb import MongoDB

class WorkflowRepository:
    def __init__(self, database: MongoDB):
        self.collection = database.get_collection("workflows")

    async def create(self, data: Dict[str, Any]) -> Workflow:
        """Create a new workflow"""
        result = await self.collection.insert_one(data)
        data["_id"] = result.inserted_id
        return Workflow(**data)

    async def get_by_id(self, workflow_id: str) -> Optional[Workflow]:
        """Get a workflow by ID"""
        data = await self.collection.find_one({"_id": workflow_id})
        if data:
            return Workflow(**data)
        return None

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Workflow]:
        """Get workflows with pagination"""
        cursor = self.collection.find().skip(skip).limit(limit)
        workflows = []
        async for document in cursor:
            workflows.append(Workflow(**document))
        return workflows

    async def update(self, workflow_id: str, data: Dict[str, Any]) -> Optional[Workflow]:
        """Update a workflow"""
        await self.collection.update_one({"_id": workflow_id}, {"$set": data})
        return await self.get_by_id(workflow_id)

    async def delete(self, workflow_id: str) -> bool:
        """Delete a workflow"""
        result = await self.collection.delete_one({"_id": workflow_id})
        return result.deleted_count > 0

    async def get_by_category(self, category: str) -> List[Workflow]:
        """Get workflows by category"""
        cursor = self.collection.find({"category": category})
        workflows = []
        async for document in cursor:
            workflows.append(Workflow(**document))
        return workflows

    async def get_by_tag(self, tag: str) -> List[Workflow]:
        """Get workflows by tag"""
        cursor = self.collection.find({"tags": tag})
        workflows = []
        async for document in cursor:
            workflows.append(Workflow(**document))
        return workflows

    async def get_templates(self) -> List[Workflow]:
        """Get all workflow templates"""
        cursor = self.collection.find({"is_template": True})
        workflows = []
        async for document in cursor:
            workflows.append(Workflow(**document))
        return workflows