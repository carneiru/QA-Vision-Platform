"""Service layer for model training operations."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid
import logging

from model_training.domain.aggregates.model_aggregate import ModelAggregate
from model_training.domain.repositories.model_repository import ModelRepository
from model_training.domain.entities.model import Model, ModelType, ModelStatus
from model_training.core.model_trainer import train_model
from model_training.core.model_evaluator import evaluate_model
from model_training.infrastructure.messaging.kafka_producer import KafkaProducerWrapper
from model_training.config import settings

# OpenTelemetry imports
from opentelemetry import trace

logger = logging.getLogger(__name__)


class ModelService:
    """Service for model operations."""

    def __init__(self, repository: ModelRepository):
        """Initialize the model service with a repository."""
        self.repository = repository
        self.tracer = trace.get_tracer(__name__)

    def create_model(self, model_data: dict, created_by: Optional[str] = None) -> ModelAggregate:
        """Create a new model."""
        with self.tracer.start_as_current_span("create_model") as span:
            # Convert dict to appropriate format if needed
            if hasattr(model_data, 'dict'):
                model_dict = model_data.dict()
            else:
                model_dict = model_data.copy()

            if created_by:
                model_dict["created_by"] = created_by

            # Create domain model
            domain_model = Model(
                id=str(model_dict.get("id", str(uuid.uuid4()))),
                name=model_dict["name"],
                description=model_dict.get("description"),
                model_type=ModelType(model_dict.get("model_type", "other")),
                status=ModelStatus(model_dict.get("status", "draft")),
                version=model_dict.get("version", "1.0.0"),
                created_by=model_dict.get("created_by"),
                training_config=model_dict.get("training_config"),
                evaluation_metrics=model_dict.get("evaluation_metrics")
            )

            # Create aggregate
            model_aggregate = ModelAggregate(model=domain_model)

            # Add to repository
            self.repository.add(model_aggregate)

            # Add attributes to the span
            span.set_attribute("model.id", str(model_aggregate.model.id))
            span.set_attribute("model.name", model_aggregate.model.name)
            span.set_attribute("model.type", model_aggregate.model.model_type.value)

            return model_aggregate

    def get_model(self, model_id: str) -> Optional[ModelAggregate]:
        """Get a model by ID."""
        with self.tracer.start_as_current_span("get_model") as span:
            model_aggregate = self.repository.get_by_id(model_id)

            # Add attributes to the span
            span.set_attribute("model.id", model_id)
            if model_aggregate is not None:
                span.set_attribute("model.found", True)
                span.set_attribute("model.name", model_aggregate.model.name)
            else:
                span.set_attribute("model.found", False)

            return model_aggregate

    def get_models(self, skip: int = 0, limit: int = 100, model_type: Optional[str] = None, status: Optional[str] = None) -> List[ModelAggregate]:
        """Get a list of models with optional filtering."""
        with self.tracer.start_as_current_span("get_models") as span:
            # Get models from repository with pagination
            models = self.repository.list_models(skip=skip, limit=limit)

            # Apply filters
            if model_type:
                try:
                    model_type_enum = ModelType(model_type)
                    models = [m for m in models if m.model.model_type == model_type_enum]
                except ValueError:
                    pass  # Invalid model type, return filtered list will be empty

            if status:
                try:
                    status_enum = ModelStatus(status)
                    models = [m for m in models if m.model.status == status_enum]
                except ValueError:
                    pass  # Invalid status, return filtered list will be empty

            # Add pagination info to span
            span.set_attribute("query.skip", skip)
            span.set_attribute("query.limit", limit)
            if model_type:
                span.set_attribute("query.model_type", model_type)
            if status:
                span.set_attribute("query.status", status)

            # Add result count to span
            span.set_attribute("result.count", len(models))

            return models

    def update_model(self, model_id: str, model_data: dict) -> Optional[ModelAggregate]:
        """Update a model."""
        with self.tracer.start_as_current_span("update_model") as span:
            model_aggregate = self.repository.get_by_id(model_id)
            if not model_aggregate:
                span.set_attribute("model.found", False)
                return None

            # Add attributes to the span
            span.set_attribute("model.id", model_id)
            span.set_attribute("model.found", True)

            # Update model attributes
            if hasattr(model_data, 'dict'):
                update_data = model_data.dict(exclude_unset=True)
            else:
                update_data = {k: v for k, v in model_data.items() if v is not None}

            # Update the domain model through its methods where possible
            model = model_aggregate.model

            if "name" in update_data:
                model.name = update_data["name"]
            if "description" in update_data:
                model.description = update_data["description"]
            if "model_type" in update_data:
                model.model_type = ModelType(update_data["model_type"])
            if "version" in update_data:
                model.version = update_data["version"]
            if "training_config" in update_data:
                model.training_config = update_data["training_config"]
            if "evaluation_metrics" in update_data:
                model.evaluation_metrics = update_data["evaluation_metrics"]

            model.updated_at = datetime.now(timezone.utc)

            # Update in repository
            self.repository.update(model_aggregate)

            return model_aggregate

    def delete_model(self, model_id: str) -> bool:
        """Delete a model."""
        with self.tracer.start_as_current_span("delete_model") as span:
            model_aggregate = self.repository.get_by_id(model_id)
            if not model_aggregate:
                span.set_attribute("model.found", False)
                return False

            # Add attributes to the span
            span.set_attribute("model.id", model_id)
            span.set_attribute("model.found", True)

            # Delete from repository
            result = self.repository.delete(model_id)
            return result

    def train_model(self, model_id: str, initiated_by: Optional[str] = None) -> str:
        """Start training a model."""
        with self.tracer.start_as_current_span("train_model") as span:
            # Get the model aggregate
            model_aggregate = self.repository.get_by_id(model_id)
            if not model_aggregate:
                span.set_attribute("model.found", False)
                raise ValueError(f"Model {model_id} not found")

            # Add attributes to the span
            span.set_attribute("model.id", model_id)
            span.set_attribute("model.found", True)
            span.set_attribute("model.name", model_aggregate.model.name)

            # Transition model to training state using domain method
            model_aggregate.model.train(initiated_by)

            # Save the updated aggregate
            self.repository.update(model_aggregate)

            # Generate training job ID
            training_job_id = str(uuid.uuid4())

            # Add training job ID to span
            span.set_attribute("training.job.id", training_job_id)

            # Send training request to Kafka
            try:
                producer = KafkaProducerWrapper()

                # Prepare training request data
                training_request = {
                    "model_id": model_id,
                    "training_job_id": training_job_id,
                    "training_config": model_aggregate.model.training_config or {},
                    "initiated_by": initiated_by
                }

                # Send to Kafka
                producer.send_model_training_request(training_request)
                producer.close()

                # Start actual training (would be done by worker in production)
                # For now we'll call directly but in production this would be async
                train_model(model_id, training_job_id, model_aggregate.model.training_config or {}, None)
            except Exception as e:
                # Update model status on failure using domain method
                model_aggregate.model.fail(str(e), initiated_by)
                self.repository.update(model_aggregate)
                span.record_exception(e)
                span.set_status(trace.StatusCode.ERROR, str(e))
                raise e

            return training_job_id

    def evaluate_model(self, model_id: str, evaluation_config: Dict[str, Any], initiated_by: Optional[str] = None) -> str:
        """Start evaluating a model."""
        with self.tracer.start_as_current_span("evaluate_model") as span:
            # Get the model
            model_aggregate = self.repository.get_by_id(model_id)
            if not model_aggregate:
                span.set_attribute("model.found", False)
                raise ValueError(f"Model {model_id} not found")

            # Add attributes to the span
            span.set_attribute("model.id", model_id)
            span.set_attribute("model.found", True)
            span.set_attribute("model.name", model_aggregate.model.name)

            # Generate evaluation ID
            evaluation_id = str(uuid.uuid4())

            # Add evaluation ID to span
            span.set_attribute("evaluation.id", evaluation_id)

            # Start evaluation in background
            try:
                # Send evaluation request to Kafka
                producer = KafkaProducerWrapper()

                # Prepare evaluation request data
                evaluation_request = {
                    "model_id": model_id,
                    "evaluation_id": evaluation_id,
                    "evaluation_config": evaluation_config,
                    "initiated_by": initiated_by
                }

                # Send to Kafka
                producer.send_model_evaluation_request(evaluation_request)
                producer.close()

                # Start actual evaluation (would be done by worker in production)
                evaluate_model(model_id, evaluation_id, evaluation_config, None)
            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.StatusCode.ERROR, str(e))
                raise e

            return evaluation_id

    def deploy_model(self, model_id: str, deployed_by: Optional[str] = None) -> ModelAggregate:
        """Deploy a model."""
        with self.tracer.start_as_current_span("deploy_model") as span:
            model_aggregate = self.repository.get_by_id(model_id)
            if not model_aggregate:
                span.set_attribute("model.found", False)
                raise ValueError(f"Model {model_id} not found")

            # Add attributes to the span
            span.set_attribute("model.id", model_id)
            span.set_attribute("model.found", True)
            span.set_attribute("model.name", model_aggregate.model.name)

            # Deploy the model using domain method
            model_aggregate.model.deploy(deployed_by)

            # Save the updated aggregate
            self.repository.update(model_aggregate)

            # Add deployment attributes to span
            span.set_attribute("model.status.after", "deployed")
            span.set_attribute("model.is_active", True)

            return model_aggregate

    def deploy_model_version(self, model_id: str, version: str, deployed_by: Optional[str] = None) -> ModelAggregate:
        """Deploy a specific model version."""
        with self.tracer.start_as_current_span("deploy_model_version") as span:
            # Get the specific model version
            # For now, we'll get the model and check if version matches
            # In a full implementation, we'd have a repository method to get by model_id and version
            model_aggregate = self.repository.get_by_id(model_id)
            if not model_aggregate:
                span.set_attribute("model.found", False)
                raise ValueError(f"Model {model_id} version {version} not found")

            # Check if it's the right version
            if model_aggregate.model.version != version:
                span.set_attribute("model.found", False)
                raise ValueError(f"Model {model_id} version {version} not found")

            # Add attributes to the span
            span.set_attribute("model.id", model_id)
            span.set_attribute("model.version", version)
            span.set_attribute("model.found", True)
            span.set_attribute("model.name", model_aggregate.model.name)

            # Check if model is completed before deployment using domain method
            if not model_aggregate.model.is_ready_for_deployment():
                span.set_attribute("model.status", model_aggregate.model.status.value)
                raise ValueError(f"Model {model_id} version {version} must be completed before deployment")

            # Deactivate all other versions of this model
            # Get all versions of this model
            all_models = self.repository.list_models(limit=1000)  # Get a large number to capture all versions
            other_versions = [m for m in all_models if m.model.id == model_id and m.model.id != model_aggregate.model.id]

            # Deactivate other versions using domain method
            for other_model_aggregate in other_versions:
                other_model_aggregate.model.deactivate_version()
                other_model_aggregate.model.updated_at = datetime.now(timezone.utc)
                self.repository.update(other_model_aggregate)

            # Activate this version using domain method
            model_aggregate.model.activate_version()
            model_aggregate.model.status = ModelStatus.DEPLOYED
            model_aggregate.model.deployed_at = datetime.now(timezone.utc)
            model_aggregate.model.deployed_by = deployed_by
            model_aggregate.model.updated_at = datetime.now(timezone.utc)

            # Save the updated aggregate
            self.repository.update(model_aggregate)

            # Add deployment attributes to span
            span.set_attribute("model.status.after", "deployed")
            span.set_attribute("model.is_active", True)

            # Send model trained event to Kafka
            try:
                producer = KafkaProducerWrapper()

                # Prepare model trained event data
                model_trained_event = {
                    "id": str(model_aggregate.model.id),
                    "name": model_aggregate.model.name,
                    "version": model_aggregate.model.version,
                    "model_type": model_aggregate.model.model_type.value,
                    "status": model_aggregate.model.status.value,
                    "deployed_at": model_aggregate.model.deployed_at.isoformat() if model_aggregate.model.deployed_at else None,
                    "deployed_by": deployed_by
                }

                # Send to Kafka
                producer.send_model_trained_event(model_trained_event)
                producer.close()
            except Exception as e:
                # Log error but don't fail the deployment
                logger.warning(f"Failed to send model trained event to Kafka: {e}")

            return model_aggregate

    def retire_model(self, model_id: str, retired_by: Optional[str] = None) -> ModelAggregate:
        """Retire a model."""
        with self.tracer.start_as_current_span("retire_model") as span:
            model_aggregate = self.repository.get_by_id(model_id)
            if not model_aggregate:
                span.set_attribute("model.found", False)
                raise ValueError(f"Model {model_id} not found")

            # Add attributes to the span
            span.set_attribute("model.id", model_id)
            span.set_attribute("model.found", True)
            span.set_attribute("model.name", model_aggregate.model.name)

            # Retire the model using domain method
            model_aggregate.model.retire(retired_by)

            # Save the updated aggregate
            self.repository.update(model_aggregate)

            # Add retirement attributes to span
            span.set_attribute("model.status.after", "retired")
            span.set_attribute("model.is_active", False)

            return model_aggregate

    def get_model_versions(self, model_id: str) -> List[ModelAggregate]:
        """Get all versions of a model."""
        with self.tracer.start_as_current_span("get_model_versions") as span:
            # Add attributes to the span
            span.set_attribute("model.id", model_id)

            # Get all models and filter by model_id
            all_models = self.repository.list_models(limit=1000)  # Get a large number to capture all versions
            versions = [m for m in all_models if m.model.id == model_id]

            # Add result count to span
            span.set_attribute("result.count", len(versions))

            return versions

    def get_model_evaluations(self, model_id: str) -> List[ModelAggregate]:
        """Get all evaluations of a model."""
        with self.tracer.start_as_current_span("get_model_evaluations") as span:
            # Add attributes to the span
            span.set_attribute("model.id", model_id)

            # Evaluations would be handled by a different repository/service
            # For now, returning empty list as this would require evaluation-specific repository
            evaluations = []

            # Add result count to span
            span.set_attribute("result.count", len(evaluations))

            return evaluations

    def get_model_evaluation(self, model_id: str, evaluation_id: str) -> Optional[ModelAggregate]:
        """Get a specific evaluation by ID."""
        with self.tracer.start_as_current_span("get_model_evaluation") as span:
            # Add attributes to the span
            span.set_attribute("evaluation.id", evaluation_id)
            span.set_attribute("evaluation.model_id", model_id)

            # Evaluations would be handled by a different repository/service
            # For now, returning None as this would require evaluation-specific repository
            evaluation = None

            # Add attributes to the span
            if evaluation is not None:
                span.set_attribute("evaluation.found", True)
                span.set_attribute("evaluation.model_id", str(evaluation.model_id))
            else:
                span.set_attribute("evaluation.found", False)

            return evaluation