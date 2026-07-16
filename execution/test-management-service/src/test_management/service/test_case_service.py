"""
Test Case Service Layer
"""
from typing import List, Optional
from src.test_management.models.test_case import TestCase
from src.test_management.schemas.test_case import TestCaseCreate, TestCaseUpdate
from src.test_management.persistence.test_case_repository import TestCaseRepository

class TestCaseService:
    def __init__(self, repository: TestCaseRepository):
        self.repository = repository

    async def create_test_case(self, test_case: TestCaseCreate) -> TestCase:
        """Create a new test case"""
        return await self.repository.create(test_case.dict())

    async def get_test_case(self, test_case_id: str) -> Optional[TestCase]:
        """Get a test case by ID"""
        return await self.repository.get_by_id(test_case_id)

    async def get_test_cases(self, skip: int = 0, limit: int = 100) -> List[TestCase]:
        """Get test cases with pagination"""
        return await self.repository.get_all(skip=skip, limit=limit)

    async def update_test_case(self, test_case_id: str, test_case: TestCaseUpdate) -> Optional[TestCase]:
        """Update a test case"""
        update_data = test_case.dict(exclude_unset=True)
        return await self.repository.update(test_case_id, update_data)

    async def delete_test_case(self, test_case_id: str) -> bool:
        """Delete a test case"""
        return await self.repository.delete(test_case_id)

    async def get_test_cases_by_suite(self, test_suite_id: str) -> List[TestCase]:
        """Get all test cases for a specific test suite"""
        return await self.repository.get_by_suite_id(test_suite_id)

    async def get_test_cases_by_specification(self, test_spec_id: str) -> List[TestCase]:
        """Get all test cases for a specific test specification"""
        return await self.repository.get_by_specification_id(test_spec_id)