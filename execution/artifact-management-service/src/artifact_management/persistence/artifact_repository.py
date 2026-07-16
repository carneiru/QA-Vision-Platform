"""
Artifact Repository
"""
from typing import List, Optional, Dict, Any
from src.artifact_management.models.artifact import Artifact
from src.artifact_management.db.mongodb import MongoDB

class ArtifactRepository:
    def __init__(self, database: MongoDB):
        self.collection = database.get_collection("artifacts")

    async def create(self, data: Dict[str, Any]) -> Artifact:
        """Create a new artifact"""
        result = await self.collection.insert_one(data)
        data["_id"] = result.inserted_id
        return Artifact(**data)

    async def get_by_id(self, artifact_id: str) -> Optional[Artifact]:
        """Get an artifact by ID"""
        data = await self.collection.find_one({"_id": artifact_id})
        if data:
            return Artifact(**data)
        return None

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Artifact]:
        """Get artifacts with pagination"""
        cursor = self.collection.find().skip(skip).limit(limit)
        artifacts = []
        async for document in cursor:
            artifacts.append(Artifact(**document))
        return artifacts

    async def update(self, artifact_id: str, data: Dict[str, Any]) -> Optional[Artifact]:
        """Update an artifact"""
        await self.collection.update_one({"_id": artifact_id}, {"$set": data})
        return await self.get_by_id(artifact_id)

    async def delete(self, artifact_id: str) -> bool:
        """Delete an artifact"""
        result = await self.collection.delete_one({"_id": artifact_id})
        return result.deleted_count > 0

    async def get_by_collection_id(self, collection_id: str) -> List[Artifact]:
        """Get artifacts by collection ID"""
        cursor = self.collection.find({"collection_id": collection_id})
        artifacts = []
        async for document in cursor:
            artifacts.append(Artifact(**document))
        return artifacts

    async def get_by_artifact_type(self, artifact_type: str) -> List[Artifact]:
        """Get artifacts by type"""
        cursor = self.collection.find({"artifact_type": artifact_type})
        artifacts = []
        async for document in cursor:
            artifacts.append(Artifact(**document))
        return artifacts

    async def get_by_tags(self, tags: List[str]) -> List[Artifact]:
        """Get artifacts by tags"""
        # Using $in operator to match any of the provided tags
        cursor = self.collection.find({"tags": {"$in": tags}})
        artifacts = []
        async for document in cursor:
            artifacts.append(Artifact(**document))
        return artifacts