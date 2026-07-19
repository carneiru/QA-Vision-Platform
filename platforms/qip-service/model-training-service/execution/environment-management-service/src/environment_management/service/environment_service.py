"""
Environment Service Layer
"""
from typing import List, Optional
from src.environment_management.models.environment import Environment
from src.environment_management.schemas.environment import EnvironmentCreate, EnvironmentUpdate
from src.environment_management.persistence.environment_repository import EnvironmentRepository
from datetime import datetime

class EnvironmentService:
    def __init__(self, repository: EnvironmentRepository):
        self.repository = repository

    async def create_environment(self, environment: EnvironmentCreate) -> Environment:
        """Create a new environment"""
        return await self.repository.create(environment.dict())

    async def get_environment(self, environment_id: str) -> Optional[Environment]:
        """Get an environment by ID"""
        return await self.repository.get_by_id(environment_id)

    async def get_environments(self, skip: int = 0, limit: int = 100) -> List[Environment]:
        """Get environments with pagination"""
        return await self.repository.get_all(skip=skip, limit=limit)

    async def update_environment(self, environment_id: str, environment: EnvironmentUpdate) -> Optional[Environment]:
        """Update an environment"""
        update_data = environment.dict(exclude_unset=True)
        return await self.repository.update(environment_id, update_data)

    async def delete_environment(self, environment_id: str) -> bool:
        """Delete an environment"""
        return await self.repository.delete(environment_id)

    async def provision_environment(self, environment_id: str) -> Optional[Environment]:
        """Provision an environment"""
        environment = await self.get_environment(environment_id)
        if not environment:
            return None

        # Update status to provisioning
        await self.repository.update(environment_id, {"status": "provisioning"})

        # In a real implementation, this would call infrastructure-as-code tools
        # For now, we'll just update the status to provisioned
        await self.repository.update(environment_id, {
            "status": "provisioned",
            "provisioned_at": datetime.utcnow()
        })

        return await self.get_environment(environment_id)

    async def deprovision_environment(self, environment_id: str) -> Optional[Environment]:
        """Deprovision an environment"""
        environment = await self.get_environment(environment_id)
        if not environment:
            return None

        # Update status to deprovisioned
        await self.repository.update(environment_id, {"status": "deprovisioned"})

        return await self.get_environment(environment_id)