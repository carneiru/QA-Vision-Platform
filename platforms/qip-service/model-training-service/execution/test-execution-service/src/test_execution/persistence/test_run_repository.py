"""
Test Run Repository
"""
from typing import List, Optional, Dict, Any
from src.test_execution.models.test_run import TestRun
from src.test_execution.db.mongodb import MongoDB

class TestRunRepository:
    def __init__(self, database: MongoDB):
        self.collection = database.get_collection("test_runs")

    async def create(self, data: Dict[str, Any]) -> TestRun:
        """Create a new test run"""
        result = await self.collection.insert_one(data)
        data["_id"] = result.inserted_id
        return TestRun(**data)

    async def get_by_id(self, test_run_id: str) -> Optional[TestRun]:
        """Get a test run by ID"""
        data = await self.collection.find_one({"_id": test_run_id})
        if data:
            return TestRun(**data)
        return None

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[TestRun]:
        """Get test runs with pagination"""
        cursor = self.collection.find().skip(skip).limit(limit)
        test_runs = []
        async for document in cursor:
            test_runs.append(TestRun(**document))
        return test_runs

    async def update(self, test_run_id: str, data: Dict[str, Any]) -> Optional[TestRun]:
        """Update a test run"""
        await self.collection.update_one({"_id": test_run_id}, {"$set": data})
        return await self.get_by_id(test_run_id)

    async def delete(self, test_run_id: str) -> bool:
        """Delete a test run"""
        result = await self.collection.delete_one({"_id": test_run_id})
        return result.deleted_count > 0

    async def get_by_test_case(self, test_case_id: str) -> List[TestRun]:
        """Get test runs by test case ID"""
        cursor = self.collection.find({"test_case_id": test_case_id})
        test_runs = []
        async for document in cursor:
            test_runs.append(TestRun(**document))
        return test_runs

    async def get_by_test_suite(self, test_suite_id: str) -> List[TestRun]:
        """Get test runs by test suite ID"""
        cursor = self.collection.find({"test_suite_id": test_suite_id})
        test_runs = []
        async for document in cursor:
            test_runs.append(TestRun(**document))
        return test_runs