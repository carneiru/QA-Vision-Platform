"""
Workflow Service Layer
"""
from typing import List, Optional
from src.workflow_designer.models.workflow import Workflow
from src.workflow_designer.schemas.workflow import WorkflowCreate, WorkflowUpdate
from src.workflow_designer.persistence.workflow_repository import WorkflowRepository

class WorkflowService:
    def __init__(self, repository: WorkflowRepository):
        self.repository = repository

    async def create_workflow(self, workflow: WorkflowCreate) -> Workflow:
        """Create a new workflow"""
        return await self.repository.create(workflow.dict())

    async def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get a workflow by ID"""
        return await self.repository.get_by_id(workflow_id)

    async def get_workflows(self, skip: int = 0, limit: int = 100) -> List[Workflow]:
        """Get workflows with pagination"""
        return await self.repository.get_all(skip=skip, limit=limit)

    async def update_workflow(self, workflow_id: str, workflow: WorkflowUpdate) -> Optional[Workflow]:
        """Update a workflow"""
        update_data = workflow.dict(exclude_unset=True)
        return await self.repository.update(workflow_id, update_data)

    async def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow"""
        return await self.repository.delete(workflow_id)

    async def get_workflows_by_category(self, category: str) -> List[Workflow]:
        """Get all workflows in a specific category"""
        return await self.repository.get_by_category(category)

    async def get_workflows_by_tag(self, tag: str) -> List[Workflow]:
        """Get all workflows with a specific tag"""
        return await self.repository.get_by_tag(tag)

    async def get_templates(self) -> List[Workflow]:
        """Get all workflow templates"""
        return await self.repository.get_templates()