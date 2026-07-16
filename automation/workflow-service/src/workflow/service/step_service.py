"""
Step Service Layer
"""
from typing import List, Optional
from src.workflow_designer.models.step import Step
from src.workflow_designer.schemas.step import StepCreate, StepUpdate
from src.workflow_designer.persistence.step_repository import StepRepository

class StepService:
    def __init__(self, repository: StepRepository):
        self.repository = repository

    async def create_step(self, step: StepCreate) -> Step:
        """Create a new step"""
        return await self.repository.create(step.dict())

    async def get_step(self, step_id: str) -> Optional[Step]:
        """Get a step by ID"""
        return await self.repository.get_by_id(step_id)

    async def get_steps(self, skip: int = 0, limit: int = 100) -> List[Step]:
        """Get steps with pagination"""
        return await self.repository.get_all(skip=skip, limit=limit)

    async def update_step(self, step_id: str, step: StepUpdate) -> Optional[Step]:
        """Update a step"""
        update_data = step.dict(exclude_unset=True)
        return await self.repository.update(step_id, update_data)

    async def delete_step(self, step_id: str) -> bool:
        """Delete a step"""
        return await self.repository.delete(step_id)

    async def get_steps_by_workflow(self, workflow_id: str) -> List[Step]:
        """Get all steps for a specific workflow"""
        return await self.repository.get_by_workflow_id(workflow_id)

    async def get_steps_by_type(self, step_type: str) -> List[Step]:
        """Get all steps of a specific type"""
        return await self.repository.get_by_step_type(step_type)