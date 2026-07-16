"""
Test Result Repository
"""
from typing import List, Optional, Dict, Any
from src.test_execution.models.test_result import TestResult
from src.test_execution.db.mongodb import MongoDB

class TestResultRepository:
    def __init__(self, database: MongoDB):
        self.collection = database.get_collection("test_results")

    async def create(self, data: Dict[str, Any]) -> TestResult:
        """Create a new test result"""
        result = await self.collection.insert_one(data)
        data["_id"] = result.inserted_id
        return TestResult(**data)

    async def get_by_id(self, test_result_id: str) -> Optional[TestResult]:
        """Get a test result by ID"""
        data = await self.collection.find_one({"_id": test_result_id})
        if data:
            return TestResult(**data)
        return None

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[TestResult]:
        """Get test results with pagination"""
        cursor = self.collection.find().skip(skip).limit(limit)
        test_results = []
        async for document in cursor:
            test_results.append(TestResult(**document))
        return test_results

    async def update(self, test_result_id: str, data: Dict[str, Any]) -> Optional[TestResult]:
        """Update a test result"""
        await self.collection.update_one({"_id": test_result_id}, {"$set": data})
        return await self.get_by_id(test_result_id)

    async def delete(self, test_result_id: str) -> bool:
        """Delete a test result"""
        result = await self.collection.delete_one({"_id": test_result_id})
        return result.deleted_count > 0

    async def get_by_run_id(self, test_run_id: str) -> List[TestResult]:
        """Get test results by test run ID"""
        cursor = self.collection.find({"test_run_id": test_run_id})
        test_results = []
        async for document in cursor:
            test_results.append(TestResult(**document))
        return test_results

    async def get_by_test_case(self, test_case_id: str) -> List[TestResult]:
        """Get test results by test case ID"""
        cursor = self.collection.find({"test_case_id": test_case_id})
        test_results = []
        async for document in cursor:
            test_results.append(TestResult(**document))
        return test_results