"""
Test Run Service Layer
"""
from typing import List, Optional
from src.test_execution.models.test_run import TestRun
from src.test_execution.schemas.test_run import TestRunCreate, TestRunUpdate
from src.test_execution.persistence.test_run_repository import TestRunRepository
from src.test_execution.persistence.test_result_repository import TestResultRepository

class TestRunService:
    def __init__(self, run_repository: TestRunRepository, result_repository: TestResultRepository):
        self.run_repository = run_repository
        self.result_repository = result_repository

    async def create_test_run(self, test_run: TestRunCreate) -> TestRun:
        """Create a new test run"""
        return await self.run_repository.create(test_run.dict())

    async def get_test_run(self, test_run_id: str) -> Optional[TestRun]:
        """Get a test run by ID"""
        return await self.run_repository.get_by_id(test_run_id)

    async def get_test_runs(self, skip: int = 0, limit: int = 100) -> List[TestRun]:
        """Get test runs with pagination"""
        return await self.run_repository.get_all(skip=skip, limit=limit)

    async def update_test_run(self, test_run_id: str, test_run: TestRunUpdate) -> Optional[TestRun]:
        """Update a test run"""
        update_data = test_run.dict(exclude_unset=True)
        return await self.run_repository.update(test_run_id, update_data)

    async def delete_test_run(self, test_run_id: str) -> bool:
        """Delete a test run"""
        return await self.run_repository.delete(test_run_id)

    async def execute_test_run(self, test_run_id: str) -> Optional[TestRun]:
        """Execute a test run"""
        # This would typically trigger test execution
        # For now, we'll just update the status to 'running'
        test_run = await self.get_test_run(test_run_id)
        if not test_run:
            return None

        # Update status to indicate execution started
        from datetime import datetime
        update_data = {
            "status": "running",
            "start_time": datetime.utcnow()
        }
        updated_run = await self.run_repository.update(test_run_id, update_data)
        return updated_run

    async def get_test_run_results(self, test_run_id: str) -> List[dict]:
        """Get all results for a test run"""
        results = await self.result_repository.get_by_run_id(test_run_id)
        return [result.dict() for result in results]

    async def get_test_runs_by_test_case(self, test_case_id: str) -> List[TestRun]:
        """Get test runs by test case ID"""
        return await self.run_repository.get_by_test_case(test_case_id)

    async def get_test_runs_by_test_suite(self, test_suite_id: str) -> List[TestRun]:
        """Get test runs by test suite ID"""
        return await self.run_repository.get_by_test_suite(test_suite_id)