"""
Test Specification Service Layer
"""
from typing import List, Optional
from src.test_management.models.test_specification import TestSpecification
from src.test_management.schemas.test_specification import TestSpecificationCreate, TestSpecificationUpdate
from src.test_management.persistence.test_specification_repository import TestSpecificationRepository

class TestSpecificationService:
    def __init__(self, repository: TestSpecificationRepository):
        self.repository = repository

    async def create_test_specification(self, test_spec: TestSpecificationCreate) -> TestSpecification:
        """Create a new test specification"""
        return await self.repository.create(test_spec.dict())

    async def get_test_specification(self, test_spec_id: str) -> Optional[TestSpecification]:
        """Get a test specification by ID"""
        return await self.repository.get_by_id(test_spec_id)

    async def get_test_specifications(self, skip: int = 0, limit: int = 100) -> List[TestSpecification]:
        """Get test specifications with pagination"""
        return await self.repository.get_all(skip=skip, limit=limit)

    async def update_test_specification(self, test_spec_id: str, test_spec: TestSpecificationUpdate) -> Optional[TestSpecification]:
        """Update a test specification"""
        update_data = test_spec.dict(exclude_unset=True)
        return await self.repository.update(test_spec_id, update_data)

    async def delete_test_specification(self, test_spec_id: str) -> bool:
        """Delete a test specification"""
        return await self.repository.delete(test_spec_id)

    async def get_test_cases_by_specification(self, test_spec_id: str) -> List[dict]:
        """Get all test cases for a specific test specification"""
        return await self.repository.get_test_cases_by_specification(test_spec_id)