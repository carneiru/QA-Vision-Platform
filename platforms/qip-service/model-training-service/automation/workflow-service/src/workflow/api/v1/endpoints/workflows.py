"""
Workflows API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from src.workflow_designer.schemas.workflow import WorkflowCreate, WorkflowUpdate, WorkflowResponse
from src.workflow_designer.service.workflow_service import WorkflowService

router = APIRouter()


@router.post("/", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    workflow: WorkflowCreate,
    service: WorkflowService = Depends()
):
    """Create a new workflow"""
    return await service.create_workflow(workflow)


@router.get("/", response_model=List[WorkflowResponse])
async def list_workflows(
    skip: int = 0,
    limit: int = 100,
    service: WorkflowService = Depends()
):
    """List workflows with pagination"""
    return await service.get_workflows(skip=skip, limit=limit)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    service: WorkflowService = Depends()
):
    """Get a specific workflow by ID"""
    workflow = await service.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    workflow: WorkflowUpdate,
    service: WorkflowService = Depends()
):
    """Update a workflow"""
    updated_workflow = await service.update_workflow(workflow_id, workflow)
    if not updated_workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return updated_workflow


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: str,
    service: WorkflowService = Depends()
):
    """Delete a workflow"""
    deleted = await service.delete_workflow(workflow_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return None


@router.get("/category/{category}", response_model=List[WorkflowResponse])
async def get_workflows_by_category(
    category: str,
    service: WorkflowService = Depends()
):
    """Get all workflows in a specific category"""
    return await service.get_workflows_by_category(category)


@router.get("/tag/{tag}", response_model=List[WorkflowResponse])
async def get_workflows_by_tag(
    tag: str,
    service: WorkflowService = Depends()
):
    """Get all workflows with a specific tag"""
    return await service.get_workflows_by_tag(tag)