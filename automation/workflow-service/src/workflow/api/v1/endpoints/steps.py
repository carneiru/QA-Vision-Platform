"""
Steps API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from src.workflow_designer.schemas.step import StepCreate, StepUpdate, StepResponse
from src.workflow_designer.service.step_service import StepService

router = APIRouter()


@router.post("/", response_model=StepResponse, status_code=status.HTTP_201_CREATED)
async def create_step(
    step: StepCreate,
    service: StepService = Depends()
):
    """Create a new step"""
    return await service.create_step(step)


@router.get("/", response_model=List[StepResponse])
async def list_steps(
    skip: int = 0,
    limit: int = 100,
    service: StepService = Depends()
):
    """List steps with pagination"""
    return await service.get_steps(skip=skip, limit=limit)


@router.get("/{step_id}", response_model=StepResponse)
async def get_step(
    step_id: str,
    service: StepService = Depends()
):
    """Get a specific step by ID"""
    step = await service.get_step(step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    return step


@router.put("/{step_id}", response_model=StepResponse)
async def update_step(
    step_id: str,
    step: StepUpdate,
    service: StepService = Depends()
):
    """Update a step"""
    updated_step = await service.update_step(step_id, step)
    if not updated_step:
        raise HTTPException(status_code=404, detail="Step not found")
    return updated_step


@router.delete("/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_step(
    step_id: str,
    service: StepService = Depends()
):
    """Delete a step"""
    deleted = await service.delete_step(step_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Step not found")
    return None


@router.get("/workflow/{workflow_id}", response_model=List[StepResponse])
async def get_steps_by_workflow(
    workflow_id: str,
    service: StepService = Depends()
):
    """Get all steps for a specific workflow"""
    return await service.get_steps_by_workflow(workflow_id)


@router.get("/type/{step_type}", response_model=List[StepResponse])
async def get_steps_by_type(
    step_type: str,
    service: StepService = Depends()
):
    """Get all steps of a specific type"""
    return await service.get_steps_by_type(step_type)