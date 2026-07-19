"""
Configuration Service Layer
"""
from typing import List, Optional
from src.environment_management.models.configuration import Configuration
from src.environment_management.schemas.configuration import ConfigurationCreate, ConfigurationUpdate
from src.environment_management.persistence.configuration_repository import ConfigurationRepository

class ConfigurationService:
    def __init__(self, repository: ConfigurationRepository):
        self.repository = repository

    async def create_configuration(self, configuration: ConfigurationCreate) -> Configuration:
        """Create a new configuration"""
        return await self.repository.create(configuration.dict())

    async def get_configuration(self, configuration_id: str) -> Optional[Configuration]:
        """Get a configuration by ID"""
        return await self.repository.get_by_id(configuration_id)

    async def get_configurations(self, skip: int = 0, limit: int = 100) -> List[Configuration]:
        """Get configurations with pagination"""
        return await self.repository.get_all(skip=skip, limit=limit)

    async def update_configuration(self, configuration_id: str, configuration: ConfigurationUpdate) -> Optional[Configuration]:
        """Update a configuration"""
        update_data = configuration.dict(exclude_unset=True)
        return await self.repository.update(configuration_id, update_data)

    async def delete_configuration(self, configuration_id: str) -> bool:
        """Delete a configuration"""
        return await self.repository.delete(configuration_id)

    async def get_configurations_by_environment(self, environment_id: str) -> List[Configuration]:
        """Get all configurations for a specific environment"""
        return await self.repository.get_by_environment_id(environment_id)