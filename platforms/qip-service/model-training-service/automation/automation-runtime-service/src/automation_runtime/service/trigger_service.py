"""
Trigger Service Layer
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from ..models.trigger import Trigger
from ..persistence.trigger_repository import TriggerRepository
from ..schemas.trigger import TriggerCreate, TriggerUpdate, TriggerType, TriggerStatus

class TriggerService:
    def __init__(self, repository: TriggerRepository):
        self.repository = repository

    async def create_trigger(self, trigger: TriggerCreate) -> Trigger:
        """Create a new trigger"""
        trigger_dict = trigger.dict()
        # Set initial values
        trigger_dict["status"] = TriggerStatus.ACTIVE
        trigger_dict["created_at"] = datetime.utcnow()
        trigger_dict["updated_at"] = datetime.utcnow()

        return await self.repository.create(trigger_dict)

    async def get_trigger(self, trigger_id: str) -> Optional[Trigger]:
        """Get a specific trigger by ID"""
        return await self.repository.get_by_id(trigger_id)

    async def get_triggers(self, skip: int = 0, limit: int = 100,
                         trigger_type: Optional[TriggerType] = None,
                         status: Optional[TriggerStatus] = None,
                         workflow_id: Optional[str] = None) -> List[Trigger]:
        """List triggers with pagination and filtering"""
        if trigger_type:
            return await self.repository.get_by_type(trigger_type, skip=skip, limit=limit)
        elif status:
            return await self.repository.get_by_status(status, skip=skip, limit=limit)
        elif workflow_id:
            return await self.repository.get_by_workflow_id(workflow_id, skip=skip, limit=limit)
        else:
            return await self.repository.get_all(skip=skip, limit=limit)

    async def update_trigger(self, trigger_id: str, trigger: TriggerUpdate) -> Optional[Trigger]:
        """Update a trigger"""
        update_data = trigger.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()

        updated_trigger = await self.repository.update(trigger_id, update_data)
        return updated_trigger

    async def delete_trigger(self, trigger_id: str) -> bool:
        """Delete a trigger"""
        return await self.repository.delete(trigger_id)

    async def activate_trigger(self, trigger_id: str) -> Optional[Trigger]:
        """Activate a trigger"""
        update_data = {
            "status": TriggerStatus.ACTIVE,
            "updated_at": datetime.utcnow()
        }
        return await self.repository.update(trigger_id, update_data)

    async def deactivate_trigger(self, trigger_id: str) -> Optional[Trigger]:
        """Deactivate a trigger"""
        update_data = {
            "status": TriggerStatus.INACTIVE,
            "updated_at": datetime.utcnow()
        }
        return await self.repository.update(trigger_id, update_data)
EOF