"""
Configuration Repository
"""
from typing import List, Optional, Dict, Any
from src.environment_management.models.configuration import Configuration
from src.environment_management.db.mongodb import MongoDB

class ConfigurationRepository:
    def __init__(self, database: MongoDB):
        self.collection = database.get_collection("configurations")

    async def create(self, data: Dict[str, Any]) -> Configuration:
        """Create a new configuration"""
        result = await self.collection.insert_one(data)
        data["_id"] = result.inserted_id
        return Configuration(**data)

    async def get_by_id(self, configuration_id: str) -> Optional[Configuration]:
        """Get a configuration by ID"""
        data = await self.collection.find_one({"_id": configuration_id})
        if data:
            return Configuration(**data)
        return None

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Configuration]:
        """Get configurations with pagination"""
        cursor = self.collection.find().skip(skip).limit(limit)
        configurations = []
        async for document in cursor:
            configurations.append(Configuration(**document))
        return configurations

    async def update(self, configuration_id: str, data: Dict[str, Any]) -> Optional[Configuration]:
        """Update a configuration"""
        await self.collection.update_one({"_id": configuration_id}, {"$set": data})
        return await self.get_by_id(configuration_id)

    async def delete(self, configuration_id: str) -> bool:
        """Delete a configuration"""
        result = await self.collection.delete_one({"_id": configuration_id})
        return result.deleted_count > 0

    async def get_by_environment_id(self, environment_id: str) -> List[Configuration]:
        """Get configurations by environment ID"""
        cursor = self.collection.find({"environment_id": environment_id})
        configurations = []
        async for document in cursor:
            configurations.append(Configuration(**document))
        return configurations

    async def get_by_configuration_type(self, configuration_type: str) -> List[Configuration]:
        """Get configurations by type"""
        cursor = self.collection.find({"configuration_type": configuration_type})
        configurations = []
        async for document in cursor:
            configurations.append(Configuration(**document))
        return configurations