"""Command for training a machine learning model."""

from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime
from ....domain.entities.model import Model, ModelStatus, ModelType
from ....domain.value_objects.model_metrics import ModelMetrics
from ....domain.aggregates.model_aggregate import ModelAggregate
from ....domain.repositories.model_repository import ModelRepository


@dataclass
class TrainModelCommand:
    """Command to train a machine learning model."""

    model_id: str
    training_data_path: str
    training_config: Dict[str, Any]
    initiated_by: Optional[str] = None
    initiated_at: datetime = field(default_factory=datetime.utcnow)

    def execute(self, model_aggregate: ModelAggregate) -> ModelAggregate:
        """Execute the train model command."""
        # Validate that model exists and is in correct state
        if model_aggregate.model.status not in [ModelStatus.DRAFT, ModelStatus.FAILED]:
            raise ValueError(f"Model {self.model_id} cannot be trained in status {model_aggregate.model.status}")

        # Update model status to training
        model_aggregate.update_status(ModelStatus.TRAINING)

        # In a real implementation, this would trigger the training process
        # For now, we'll simulate by updating the model with training config
        model_aggregate.model.training_config = self.training_config
        model_aggregate.model.updated_at = datetime.utcnow()
        if self.initiated_by:
            model_aggregate.model.updated_by = self.initiated_by

        # Add domain event for training started
        model_aggregate.add_domain_event({
            "event_type": "model.training.started",
            "model_id": self.model_id,
            "training_data_path": self.training_data_path,
            "training_config": self.training_config,
            "initiated_by": self.initiated_by,
            "timestamp": datetime.utcnow().isoformat()
        })

        return model_aggregate