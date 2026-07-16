"""
Test Suite Service Layer
"""
from typing import List, Optional
from src.test_management.models.test_suite import TestSuite
from src.test_management.schemas.test_suite import TestSuiteCreate, TestSuiteUpdate
from src.test_management.persistence.test_suite_repository import TestSuiteRepository

class TestSuiteService:
    def __init__(self, repository: TestSuiteRepository):
        self.repository = repository

    async def create_test_suite(self, test_suite: TestSuiteCreate) -> TestSuite:
        """Create a new test suite"""
        return await self.repository.create(test_suite.dict())

    async def get_test_suite(self, test_suite_id: str) -> Optional[TestSuite]:
        """Get a test suite by ID"""
        return await self.repository.get_by_id(test_suite_id)

    async def get_test_suites(self, skip: int = 0, limit: int = 100) -> List[TestSuite]:
        """Get test suites with pagination"""
        return await self.repository.get_all(skip=skip, limit=limit)

    async def update_test_suite(self, test_suite_id: str, test_suite: TestSuiteUpdate) -> Optional[TestSuite]:
        """Update a test suite"""
        update_data = test_suite.dict(exclude_unset=True)
        return await self.repository.update(test_suite_id, update_data)

    async def delete_test_suite(self, test_suite_id: str) -> bool:
        """Delete a test suite"""
        return await self.repository.delete(test_suite_id)

    async def get_test_cases_in_suite(self, test_suite_id: str) -> List[dict]:
        """Get all test cases in a test suite"""
        return await self.repository.get_test_cases_in_suite(test_suite_id)