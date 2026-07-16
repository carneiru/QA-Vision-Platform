"""
Test Case Repository
"""
from typing import List, Optional, Dict, Any
from src.test_management.models.test_case import TestCase
from src.test_management.db.mongodb import MongoDB

class TestCaseRepository:
    def __init__(self, database: MongoDB):
        self.collection = database.get_collection("test_cases")

    async def create(self, data: Dict[str, Any]) -> TestCase:
        """Create a new test case"""
        result = await self.collection.insert_one(data)
        data["_id"] = result.inserted_id
        return TestCase(**data)

    async def get_by_id(self, test_case_id: str) -> Optional[TestCase]:
        """Get a test case by ID"""
        data = await self.collection.find_one({"_id": test_case_id})
        if data:
            return TestCase(**data)
        return None

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[TestCase]:
        """Get test cases with pagination"""
        cursor = self.collection.find().skip(skip).limit(limit)
        test_cases = []
        async for document in cursor:
            test_cases.append(TestCase(**document))
        return test_cases

    async def update(self, test_case_id: str, data: Dict[str, Any]) -> Optional[TestCase]:
        """Update a test case"""
        await self.collection.update_one({"_id": test_case_id}, {"$set": data})
        return await self.get_by_id(test_case_id)

    async def delete(self, test_case_id: str) -> bool:
        """Delete a test case"""
        result = await self.collection.delete_one({"_id": test_case_id})
        return result.deleted_count > 0

    async def get_by_suite(self, test_suite_id: str) -> List[TestCase]:
        """Get test cases by test suite ID"""
        cursor = self.collection.find({"test_suite_id": test_suite_id})
        test_cases = []
        async for document in cursor:
            test_cases.append(TestCase(**document))
        return test_cases

    async def get_by_specification(self, test_spec_id: str) -> List[TestCase]:
        """Get test cases by test specification ID"""
        cursor = self.collection.find({"test_specification_id": test_spec_id})
        test_cases = []
        async for document in cursor:
            test_cases.append(TestCase(**document))
        return test_cases