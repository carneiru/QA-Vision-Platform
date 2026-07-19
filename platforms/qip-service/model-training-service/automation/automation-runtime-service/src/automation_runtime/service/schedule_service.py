"""
Schedule Service Layer
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from ..models.schedule import Schedule
from ..persistence.schedule_repository import ScheduleRepository
from ..schemas.schedule import ScheduleCreate, ScheduleUpdate, ScheduleType, ScheduleStatus

class ScheduleService:
    def __init__(self, repository: ScheduleRepository):
        self.repository = repository

    async def create_schedule(self, schedule: ScheduleCreate) -> Schedule:
        """Create a new schedule"""
        schedule_dict = schedule.dict()
        # Set initial values
        schedule_dict["status"] = ScheduleStatus.ACTIVE
        schedule_dict["created_at"] = datetime.utcnow()
        schedule_dict["updated_at"] = datetime.utcnow()

        return await self.repository.create(schedule_dict)

    async def get_schedule(self, schedule_id: str) -> Optional[Schedule]:
        """Get a specific schedule by ID"""
        return await self.repository.get_by_id(schedule_id)

    async def get_schedules(self, skip: int = 0, limit: int = 100,
                          schedule_type: Optional[ScheduleType] = None,
                          status: Optional[ScheduleStatus] = None,
                          workflow_id: Optional[str] = None) -> List[Schedule]:
        """List schedules with pagination and filtering"""
        if schedule_type:
            return await self.repository.get_by_type(schedule_type, skip=skip, limit=limit)
        elif status:
            return await self.repository.get_by_status(status, skip=skip, limit=limit)
        elif workflow_id:
            return await self.repository.get_by_workflow_id(workflow_id, skip=skip, limit=limit)
        else:
            return await self.repository.get_all(skip=skip, limit=limit)

    async def update_schedule(self, schedule_id: str, schedule: ScheduleUpdate) -> Optional[Schedule]:
        """Update a schedule"""
        update_data = schedule.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()

        updated_schedule = await self.repository.update(schedule_id, update_data)
        return updated_schedule

    async def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule"""
        return await self.repository.delete(schedule_id)

    async def activate_schedule(self, schedule_id: str) -> Optional[Schedule]:
        """Activate a schedule"""
        update_data = {
            "status": ScheduleStatus.ACTIVE,
            "updated_at": datetime.utcnow()
        }
        return await self.repository.update(schedule_id, update_data)

    async def deactivate_schedule(self, schedule_id: str) -> Optional[Schedule]:
        """Deactivate a schedule"""
        update_data = {
            "status": ScheduleStatus.INACTIVE,
            "updated_at": datetime.utcnow()
        }
        return await self.repository.update(schedule_id, update_data)
EOF