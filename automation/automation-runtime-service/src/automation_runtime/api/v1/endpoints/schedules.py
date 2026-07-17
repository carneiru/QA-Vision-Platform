"""
Schedule Management API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from src.automation_runtime.schemas.schedule import ScheduleCreate, ScheduleUpdate, ScheduleResponse
from src.automation_runtime.service.schedule_service import ScheduleService

router = APIRouter()


@router.post("/", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    schedule: ScheduleCreate,
    service: ScheduleService = Depends()
):
    """Create a new schedule"""
    return await service.create_schedule(schedule)


@router.get("/", response_model=List[ScheduleResponse])
async def list_schedules(
    skip: int = 0,
    limit: int = 100,
    workflow_id: Optional[str] = None,
    active: Optional[bool] = None,
    service: ScheduleService = Depends()
):
    """List schedules with pagination and filtering"""
    return await service.get_schedules(skip=skip, limit=limit, workflow_id=workflow_id, active=active)


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: str,
    service: ScheduleService = Depends()
):
    """Get a specific schedule by ID"""
    schedule = await service.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: str,
    schedule: ScheduleUpdate,
    service: ScheduleService = Depends()
):
    """Update a schedule"""
    updated_schedule = await service.update_schedule(schedule_id, schedule)
    if not updated_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return updated_schedule


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: str,
    service: ScheduleService = Depends()
):
    """Delete a schedule"""
    deleted = await service.delete_schedule(schedule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return None


@router.post("/{schedule_id}/activate", response_model=ScheduleResponse)
async def activate_schedule(
    schedule_id: str,
    service: ScheduleService = Depends()
):
    """Activate a schedule"""
    activated_schedule = await service.activate_schedule(schedule_id)
    if not activated_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return activated_schedule


@router.post("/{schedule_id}/deactivate", response_model=ScheduleResponse)
async def deactivate_schedule(
    schedule_id: str,
    service: ScheduleService = Depends()
):
    """Deactivate a schedule"""
    deactivated_schedule = await service.deactivate_schedule(schedule_id)
    if not deactivated_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return deactivated_schedule
