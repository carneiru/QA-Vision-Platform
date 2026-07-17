"""
Trigger Management API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from src.automation_runtime.schemas.trigger import TriggerCreate, TriggerUpdate, TriggerResponse
from src.automation_runtime.service.trigger_service import TriggerService

router = APIRouter()


@router.post("/", response_model=TriggerResponse, status_code=status.HTTP_201_CREATED)
async def create_trigger(
    trigger: TriggerCreate,
    service: TriggerService = Depends()
):
    """Create a new trigger"""
    return await service.create_trigger(trigger)


@router.get("/", response_model=List[TriggerResponse])
async def list_triggers(
    skip: int = 0,
    limit: int = 100,
    workflow_id: Optional[str] = None,
    trigger_type: Optional[str] = None,
    active: Optional[bool] = None,
    service: TriggerService = Depends()
):
    """List triggers with pagination and filtering"""
    return await service.get_triggers(skip=skip, limit=limit, workflow_id=workflow_id, trigger_type=trigger_type, active=active)


@router.get("/{trigger_id}", response_model=TriggerResponse)
async def get_trigger(
    trigger_id: str,
    service: TriggerService = Depends()
):
    """Get a specific trigger by ID"""
    trigger = await service.get_trigger(trigger_id)
    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return trigger


@router.put("/{trigger_id}", response_model=TriggerResponse)
async def update_trigger(
    trigger_id: str,
    trigger: TriggerUpdate,
    service: TriggerService = Depends()
):
    """Update a trigger"""
    updated_trigger = await service.update_trigger(trigger_id, trigger)
    if not updated_trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return updated_trigger


@router.delete("/{trigger_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trigger(
    trigger_id: str,
    service: TriggerService = Depends()
):
    """Delete a trigger"""
    deleted = await service.delete_trigger(trigger_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return None


@router.post("/{trigger_id}/activate", response_model=TriggerResponse)
async def activate_trigger(
    trigger_id: str,
    service: TriggerService = Depends()
):
    """Activate a trigger"""
    activated_trigger = await service.activate_trigger(trigger_id)
    if not activated_trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return activated_trigger


@router.post("/{trigger_id}/deactivate", response_model=TriggerResponse)
async def deactivate_trigger(
    trigger_id: str,
    service: TriggerService = Depends()
):
    """Deactivate a trigger"""
    deactivated_trigger = await service.deactivate_trigger(trigger_id)
    if not deactivated_trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return deactivated_trigger
