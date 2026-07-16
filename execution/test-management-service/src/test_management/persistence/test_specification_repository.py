"""
Test Specification Repository
"""
from typing import List, Optional, Dict, Any
from src.test_management.models.test_specification import TestSpecification
from src.test_management.db.mongodb import MongoDB

class TestSpecificationRepository:
    def __init__(self, database: MongoDB):
        self.collection = database.get_collection("test_specifications")

    async def create(self, data: Dict[str, Any]) -> TestSpecification:
        """Create a new test specification"""
        result = await self.collection.insert_one(data)
        data["_id"] = result.inserted_id
        return TestSpecification(**data)

    async def get_by_id(self, test_spec_id: str) -> Optional[TestSpecification]:
        """Get a test specification by ID"""
        data = await self.collection.find_one({"_id": test_spec_id})
        if data:
            return TestSpecification(**data)
        return None

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[TestSpecification]:
        """Get test specifications with pagination"""
        cursor = self.collection.find().skip(skip).limit(limit)
        test_specs = []
        async for document in cursor:
            test_specs.append(TestSpecification(**document))
        return test_specs

    async def update(self, test_spec_id: str, data: Dict[str, Any]) -> Optional[TestSpecification]:
        """Update a test specification"""
        await self.collection.update_one({"_id": test_spec_id}, {"$set": data})
        return await self.get_by_id(test_spec_id)

    async def delete(self, test_spec_id: str) -> bool:
        """Delete a test specification"""
        result = await self.collection.delete_one({"_id": test_spec_id})
        return result.deleted_count > 0

    async def get_test_cases_by_specification(self, test_spec_id: str) -> List[dict]:
        """Get all test cases for a specific test specification"""
        # This would typically join with test cases collection
        # For now, we'll return an empty list as a placeholder
        return []