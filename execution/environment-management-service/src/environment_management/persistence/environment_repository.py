"""
Environment Repository
"""
from typing import List, Optional, Dict, Any
from src.environment_management.models.environment import Environment
from src.environment_management.db.mongodb import MongoDB

class EnvironmentRepository:
    def __init__(self, database: MongoDB):
        self.collection = database.get_collection("environments")

    async def create(self, data: Dict[str, Any]) -> Environment:
        """Create a new environment"""
        result = await self.collection.insert_one(data)
        data["_id"] = result.inserted_id
        return Environment(**data)

    async def get_by_id(self, environment_id: str) -> Optional[Environment]:
        """Get an environment by ID"""
        data = await self.collection.find_one({"_id": environment_id})
        if data:
            return Environment(**data)
        return None

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Environment]:
        """Get environments with pagination"""
        cursor = self.collection.find().skip(skip).limit(limit)
        environments = []
        async for document in cursor:
            environments.append(Environment(**document))
        return environments

    async def update(self, environment_id: str, data: Dict[str, Any]) -> Optional[Environment]:
        """Update an environment"""
        await self.collection.update_one({"_id": environment_id}, {"$set": data})
        return await self.get_by_id(environment_id)

    async def delete(self, environment_id: str) -> bool:
        """Delete an environment"""
        result = await self.collection.delete_one({"_id": environment_id})
        return result.deleted_count > 0

    async def get_by_status(self, status: str) -> List[Environment]:
        """Get environments by status"""
        cursor = self.collection.find({"status": status})
        environments = []
        async for document in cursor:
            environments.append(Environment(**document))
        return environments

    async def get_by_type(self, environment_type: str) -> List[Environment]:
        """Get environments by type"""
        cursor = self.collection.find({"environment_type": environment_type})
        environments = []
        async for document in cursor:
            environments.append(Environment(**document))
        return environments