"""
Test Suite Repository
"""
from typing import List, Optional, Dict, Any
from src.test_management.models.test_suite import TestSuite
from src.test_management.db.mongodb import MongoDB

class TestSuiteRepository:
    def __init__(self, database: MongoDB):
        self.collection = database.get_collection("test_suites")

    async def create(self, data: Dict[str, Any]) -> TestSuite:
        """Create a new test suite"""
        result = await self.collection.insert_one(data)
        data["_id"] = result.inserted_id
        return TestSuite(**data)

    async def get_by_id(self, test_suite_id: str) -> Optional[TestSuite]:
        """Get a test suite by ID"""
        data = await self.collection.find_one({"_id": test_suite_id})
        if data:
            return TestSuite(**data)
        return None

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[TestSuite]:
        """Get test suites with pagination"""
        cursor = self.collection.find().skip(skip).limit(limit)
        test_suites = []
        async for document in cursor:
            test_suites.append(TestSuite(**document))
        return test_suites

    async def update(self, test_suite_id: str, data: Dict[str, Any]) -> Optional[TestSuite]:
        """Update a test suite"""
        await self.collection.update_one({"_id": test_suite_id}, {"$set": data})
        return await self.get_by_id(test_suite_id)

    async def delete(self, test_suite_id: str) -> bool:
        """Delete a test suite"""
        result = await self.collection.delete_one({"_id": test_suite_id})
        return result.deleted_count > 0

    async def get_test_cases_in_suite(self, test_suite_id: str) -> List[dict]:
        """Get all test cases in a test suite"""
        # This would typically join with test cases collection
        # For now, we'll return an empty list as a placeholder
        return []