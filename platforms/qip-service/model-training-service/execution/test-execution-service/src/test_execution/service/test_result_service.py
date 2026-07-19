"""
Test Result Service Layer
"""
from typing import List, Optional
from src.test_execution.models.test_result import TestResult
from src.test_execution.schemas.test_result import TestResultCreate, TestResultUpdate
from src.test_execution.persistence.test_result_repository import TestResultRepository

class TestResultService:
    def __init__(self, repository: TestResultRepository):
        self.repository = repository

    async def create_test_result(self, test_result: TestResultCreate) -> TestResult:
        """Create a new test result"""
        return await self.repository.create(test_result.dict())

    async def get_test_result(self, test_result_id: str) -> Optional[TestResult]:
        """Get a test result by ID"""
        return await self.repository.get_by_id(test_result_id)

    async def get_test_results(self, skip: int = 0, limit: int = 100) -> List[TestResult]:
        """Get test results with pagination"""
        return await self.repository.get_all(skip=skip, limit=limit)

    async def update_test_result(self, test_result_id: str, test_result: TestResultUpdate) -> Optional[TestResult]:
        """Update a test result"""
        update_data = test_result.dict(exclude_unset=True)
        return await self.repository.update(test_result_id, update_data)

    async def delete_test_result(self, test_result_id: str) -> bool:
        """Delete a test result"""
        return await self.repository.delete(test_result_id)

    async def get_test_results_by_run(self, test_run_id: str) -> List[TestResult]:
        """Get all test results for a specific test run"""
        return await self.repository.get_by_run_id(test_run_id)

    async def get_test_results_by_test_case(self, test_case_id: str) -> List[TestResult]:
        """Get test results by test case ID"""
        return await self.repository.get_by_test_case(test_case_id)