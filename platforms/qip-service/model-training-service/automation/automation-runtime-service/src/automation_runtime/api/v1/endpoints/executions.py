"""
Workflow Executions API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List, Optional
from src.automation_runtime.schemas.execution import ExecutionCreate, ExecutionUpdate, ExecutionResponse
from src.automation_runtime.service.execution_service import ExecutionService

router = APIRouter()


@router.post("/", response_model=ExecutionResponse, status_code=status.HTTP_201_CREATED)
async def create_execution(
    execution: ExecutionCreate,
    background_tasks: BackgroundTasks,
    service: ExecutionService = Depends()
):
    """Create a new workflow execution"""
    return await service.create_execution(execution, background_tasks)


@router.get("/", response_model=List[ExecutionResponse])
async def list_executions(
    skip: int = 0,
    limit: int = 100,
    workflow_id: Optional[str] = None,
    status: Optional[str] = None,
    service: ExecutionService = Depends()
):
    """List executions with pagination and filtering"""
    return await service.get_executions(skip=skip, limit=limit, workflow_id=workflow_id, status=status)


@router.get("/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: str,
    service: ExecutionService = Depends()
):
    """Get a specific execution by ID"""
    execution = await service.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution


@router.put("/{execution_id}", response_model=ExecutionResponse)
async def update_execution(
    execution_id: str,
    execution: ExecutionUpdate,
    service: ExecutionService = Depends()
):
    """Update an execution"""
    updated_execution = await service.update_execution(execution_id, execution)
    if not updated_execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return updated_execution


@router.delete("/{execution_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_execution(
    execution_id: str,
    service: ExecutionService = Depends()
):
    """Delete an execution"""
    deleted = await service.delete_execution(execution_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Execution not found")
    return None


@router.post("/{execution_id}/cancel", response_model=ExecutionResponse)
async def cancel_execution(
    execution_id: str,
    service: ExecutionService = Depends()
):
    """Cancel a running execution"""
    cancelled_execution = await service.cancel_execution(execution_id)
    if not cancelled_execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return cancelled_execution


@router.get("/{execution_id}/status", response_model=dict)
async def get_execution_status(
    execution_id: str,
    service: ExecutionService = Depends()
):
    """Get execution status"""
    status_info = await service.get_execution_status(execution_id)
    if not status_info:
        raise HTTPException(status_code=404, detail="Execution not found")
    return status_info
