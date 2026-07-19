"""Model aggregate representing the model domain object."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from .entities.model import Model, ModelStatus, ModelType
from .repositories.model_repository import ModelRepository


@dataclass
class ModelAggregate:
    """Model aggregate representing the model domain object."""

    model: Model
    _repository: ModelRepository = field(default=None, repr=False)
    _domain_events: List[dict] = field(default_factory=list, repr=False)

    def __post_init__(self):
        """Initialize aggregate after creation."""
        pass

    def add_domain_event(self, event: dict) -> None:
        """Add a domain event to be published after transaction."""
        self._domain_events.append(event)

    def get_domain_events(self) -> List[dict]:
        """Get and clear domain events."""
        events = self._domain_events.copy()
        self._domain_events.clear()
        return events

    def update_status(self, status: ModelStatus) -> None:
        """Update model status."""
        old_status = self.model.status
        self.model.status = status
        self.model.updated_at = datetime.utcnow()

        # Add domain event for status change
        self.add_domain_event({
            "event_type": "model.status.changed",
            "model_id": self.model.id,
            "old_status": old_status.value,
            "new_status": status.value,
            "timestamp": datetime.utcnow().isoformat()
        })

    def update_metadata(self, metadata: Dict[str, Any]) -> None:
        """Update model metadata."""
        self.model.metadata.update(metadata)
        self.model.updated_at = datetime.utcnow()

        # Add domain event for metadata update
        self.add_domain_event({
            "event_type": "model.metadata.updated",
            "model_id": self.model.id,
            "metadata": metadata,
            "timestamp": datetime.utcnow().isoformat()
        })

    def set_training_parameters(self, parameters: Dict[str, Any]) -> None:
        """Set training parameters for the model."""
        self.model.training_parameters = parameters
        self.model.updated_at = datetime.utcnow()

        # Add domain event for training parameters set
        self.add_domain_event({
            "event_type": "model.training.parameters.set",
            "model_id": self.model.id,
            "parameters": parameters,
            "timestamp": datetime.utcnow().isoformat()
        })