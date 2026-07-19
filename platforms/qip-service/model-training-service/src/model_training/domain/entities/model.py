"""Model entity representing a machine learning model."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from enum import Enum


class ModelStatus(str, Enum):
    """Model status enum."""
    DRAFT = "draft"
    TRAINING = "training"
    TRAINED = "trained"
    EVALUATING = "evaluating"
    EVALUATED = "evaluated"
    DEPLOYED = "deployed"
    ARCHIVED = "archived"
    FAILED = "failed"


class ModelType(str, Enum):
    """Model type enum."""
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    CLUSTERING = "clustering"
    RECOMMENDATION = "recommendation"
    OTHER = "other"


@dataclass
class Model:
    """Model entity representing a machine learning model."""

    id: str
    name: str
    description: Optional[str] = None
    model_type: ModelType = ModelType.OTHER
    status: ModelStatus = ModelStatus.DRAFT
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    training_config: Optional[Dict[str, Any]] = None
    evaluation_metrics: Optional[Dict[str, float]] = None
    deployed_at: Optional[datetime] = None
    deployed_by: Optional[str] = None

    def update_status(self, status: ModelStatus, user: Optional[str] = None) -> None:
        """Update the model status."""
        self.status = status
        self.updated_at = datetime.now(timezone.utc)
        if user:
            self.updated_by = user

    def update_training_config(self, config: Dict[str, Any], user: Optional[str] = None) -> None:
        """Update the training configuration."""
        self.training_config = config
        self.updated_at = datetime.now(timezone.utc)
        if user:
            self.updated_by = user

    def update_evaluation_metrics(self, metrics: Dict[str, float], user: Optional[str] = None) -> None:
        """Update the evaluation metrics."""
        self.evaluation_metrics = metrics
        self.updated_at = datetime.now(timezone.utc)
        if user:
            self.updated_by = user

    def train(self, user: Optional[str] = None) -> None:
        """Transition model to training state."""
        if not self.can_transition_to_status(ModelStatus.TRAINING):
            raise ValueError(f"Cannot transition from {self.status} to {ModelStatus.TRAINING}")
        self.status = ModelStatus.TRAINING
        self.updated_at = datetime.now(timezone.utc)
        if user:
            self.updated_by = user

    def evaluate(self, user: Optional[str] = None) -> None:
        """Transition model to evaluating state."""
        if not self.can_transition_to_status(ModelStatus.EVALUATING):
            raise ValueError(f"Cannot transition from {self.status} to {ModelStatus.EVALUATING}")
        self.status = ModelStatus.EVALUATING
        self.updated_at = datetime.now(timezone.utc)
        if user:
            self.updated_by = user

    def complete_training(self, user: Optional[str] = None) -> None:
        """Mark model training as completed."""
        if not self.can_transition_to_status(ModelStatus.TRAINED):
            raise ValueError(f"Cannot transition from {self.status} to {ModelStatus.TRAINED}")
        self.status = ModelStatus.TRAINED
        self.updated_at = datetime.now(timezone.utc)
        if user:
            self.updated_by = user

    def complete_evaluation(self, user: Optional[str] = None) -> None:
        """Mark model evaluation as completed."""
        if not self.can_transition_to_status(ModelStatus.EVALUATED):
            raise ValueError(f"Cannot transition from {self.status} to {ModelStatus.EVALUATED}")
        self.status = ModelStatus.EVALUATED
        self.updated_at = datetime.now(timezone.utc)
        if user:
            self.updated_by = user

    def deploy(self, user: Optional[str] = None) -> None:
        """Deploy the model."""
        if not self.is_ready_for_deployment():
            raise ValueError(f"Model is not ready for deployment. Current status: {self.status}")
        self.status = ModelStatus.DEPLOYED
        self.deployed_at = datetime.now(timezone.utc)
        self.deployed_by = user
        self.updated_at = datetime.now(timezone.utc)
        if user:
            self.updated_by = user
        self.is_active = True

    def retire(self, user: Optional[str] = None) -> None:
        """Retire the model."""
        if not self.can_transition_to_status(ModelStatus.ARCHIVED):
            raise ValueError(f"Cannot transition from {self.status} to {ModelStatus.ARCHIVED}")
        self.status = ModelStatus.ARCHIVED
        self.updated_at = datetime.now(timezone.utc)
        if user:
            self.updated_by = user
        self.is_active = False

    def fail(self, error_message: Optional[str] = None, user: Optional[str] = None) -> None:
        """Mark model as failed."""
        if not self.can_transition_to_status(ModelStatus.FAILED):
            raise ValueError(f"Cannot transition from {self.status} to {ModelStatus.FAILED}")
        self.status = ModelStatus.FAILED
        self.updated_at = datetime.now(timezone.utc)
        if user:
            self.updated_by = user
        # Store error info in training config or evaluation metrics if needed
        if error_message:
            if self.training_config is None:
                self.training_config = {}
            self.training_config["last_error"] = error_message

    def can_transition_to_status(self, new_status: ModelStatus) -> bool:
        """Check if transition to new status is allowed based on current state."""
        # Define valid state transitions
        valid_transitions = {
            ModelStatus.DRAFT: [ModelStatus.TRAINING, ModelStatus.ARCHIVED],
            ModelStatus.TRAINING: [ModelStatus.TRAINED, ModelStatus.FAILED],
            ModelStatus.TRAINED: [ModelStatus.EVALUATING, ModelStatus.DEPLOYED, ModelStatus.ARCHIVED],
            ModelStatus.EVALUATING: [ModelStatus.EVALUATED, ModelStatus.FAILED],
            ModelStatus.EVALUATED: [ModelStatus.DEPLOYED, ModelStatus.ARCHIVED],
            ModelStatus.DEPLOYED: [ModelStatus.ARCHIVED],
            ModelStatus.ARCHIVED: [],  # Terminal state
            ModelStatus.FAILED: [ModelStatus.TRAINING]  # Can retry from failed
        }

        return new_status in valid_transitions.get(self.status, [])

    def is_ready_for_deployment(self) -> bool:
        """Check if model is ready for deployment."""
        return self.status in [ModelStatus.TRAINED, ModelStatus.EVALUATED]

    def validate_training_config(self, config: Dict[str, Any]) -> bool:
        """Validate training configuration.

        Args:
            config: Training configuration to validate

        Returns:
            bool: True if configuration is valid, False otherwise
        """
        # Basic validation - in a real implementation this would be more comprehensive
        if not isinstance(config, dict):
            return False

        # Check for required fields
        required_fields = ['learning_rate', 'batch_size', 'epochs']
        for field in required_fields:
            if field not in config:
                return False

        # Validate specific fields
        if 'learning_rate' in config:
            lr = config['learning_rate']
            if not isinstance(lr, (int, float)) or lr <= 0:
                return False

        if 'batch_size' in config:
            bs = config['batch_size']
            if not isinstance(bs, int) or bs <= 0:
                return False

        if 'epochs' in config:
            epochs = config['epochs']
            if not isinstance(epochs, int) or epochs <= 0:
                return False

        return True

    def activate_version(self) -> None:
        """Activate this model version."""
        self.is_active = True
        self.updated_at = datetime.now(timezone.utc)

    def deactivate_version(self) -> None:
        """Deactivate this model version."""
        self.is_active = False
        self.updated_at = datetime.now(timezone.utc)

    def is_active(self) -> bool:
        """Check if model is active."""
        return getattr(self, 'is_active', False)