"""
Execution Repository
"""
from typing import List, Optional, Dict, Any
from ..models.execution import Execution
from ..db.mongodb import db

class ExecutionRepository:
    def __init__(self):
        self.collection = None

    async def _get_collection(self):
        if self.collection is None:
            self.collection = db.get_collection("executions")
        return self.collection

    async def create(self, execution_data: dict) -> Execution:
        """Create a new execution"""
        collection = await self._get_collection()
        # Ensure we have an id (the Execution model should generate one)
        # We'll store the execution data as is, but remove any _id to avoid conflict
        if "_id" in execution_data:
            del execution_data["_id"]
        result = await collection.insert_one(execution_data)
        # Inserted document will have an _id field added by MongoDB
        # We want to return an Execution object that has the id from the input (which is the same as the one we set)
        # So we can simply return Execution(**execution_data)
        return Execution(**execution_data)

    async def get_by_id(self, execution_id: str) -> Optional[Execution]:
        """Get an execution by ID"""
        collection = await self._get_collection()
        # We stored the execution with an "id" field (string) that is our application id.
        document = await collection.find_one({"id": execution_id})
        if document:
            # Remove the MongoDB _id field before creating the Execution object
            # because the Execution model does not have an _id field.
            document.pop("_id", None)
            return Execution(**document)
        return None

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Execution]:
        """Get all executions with pagination"""
        collection = await self._get_collection()
        cursor = collection.find().skip(skip).limit(limit)
        executions = []
        async for document in cursor:
            document.pop("_id", None)
            executions.append(Execution(**document))
        return executions

    async def get_by_workflow_id(self, workflow_id: str, skip: int = 0, limit: int = 100) -> List[Execution]:
        """Get executions by workflow ID"""
        collection = await self._get_collection()
        cursor = collection.find({"workflow_id": workflow_id}).skip(skip).limit(limit)
        executions = []
        async for document in cursor:
            document.pop("_id", None)
            executions.append(Execution(**document))
        return executions

    async def get_by_status(self, status: str, skip: int = 0, limit: int = 100) -> List[Execution]:
        """Get executions by status"""
        collection = await self._get_collection()
        cursor = collection.find({"status": status}).skip(skip).limit(limit)
        executions = []
        async for document in cursor:
            document.pop("_id", None)
            executions.append(Execution(**document))
        return executions

    async def update(self, execution_id: str, update_data: dict) -> Optional[Execution]:
        """Update an execution"""
        collection = await self._get_collection()
        # Remove _id from update_data if present
        if "_id" in update_data:
            del update_data["_id"]
        # We are updating by our application id
        result = await collection.update_one({"id": execution_id}, {"$set": update_data})
        if result.modified_count == 1:
            return await self.get_by_id(execution_id)
        return None

    async def delete(self, execution_id: str) -> bool:
        """Delete an execution"""
        collection = await self._get_collection()
        result = await collection.delete_one({"id": execution_id})
        return result.deleted_count > 0