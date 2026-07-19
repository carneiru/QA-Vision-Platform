"""Repository interface for Model entities."""
from .base_repository import BaseRepository
from ..domain.model import Model


class ModelRepository(BaseRepository[Model]):
    """Repository interface for Model entities."""

    async def get_by_name(self, name: str) -> Optional[Model]:
        """Get a model by its name."""
        raise NotImplementedError

    async def get_by_status(self, status: str) -> List[Model]:
        """Get models by their status."""
        raise NotImplementedError

    async def get_active_models(self) -> List[Model]:
        """Get all active models."""
        raise NotImplementedError