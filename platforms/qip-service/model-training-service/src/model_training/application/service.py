"""Application service for model operations."""

from typing import List, Optional
from datetime import datetime
import time
from prometheus_client import Counter, Histogram
from ..domain.aggregates.model_aggregate import ModelAggregate
from ..domain.repositories.model_repository import ModelRepository
from ..domain.events.model_events import ModelEvents
from .commands.train_model_command import TrainModelCommand
from .queries.get_model_query import GetModelQuery, ListModelsQuery

# Prometheus metrics for application service
TRAINING_JOBS_TOTAL = Counter(
    'model_training_training_jobs_total',
    'Total number of training jobs',
    ['status']  # completed, failed, etc.
)

TRAINING_JOB_DURATION = Histogram(
    'model_training_training_job_duration_seconds',
    'Duration of training jobs in seconds'
)

MODEL_EVALUATIONS_TOTAL = Counter(
    'model_training_model_evaluations_total',
    'Total number of model evaluations',
    ['status']  # completed, failed, etc.
)

DEPLOYMENTS_TOTAL = Counter(
    'model_training_deployments_total',
    'Total number of model deployments',
    ['status']  # success, failure
)

DEPLOYMENTS_TOTAL = Counter(
    'model_training_deployments_total',
    'Total number of model deployments',
    ['status']  # success, failure
)


class ModelApplicationService:
    """Application service for model operations."""

    def __init__(self, repository: ModelRepository):
        """Initialize the model application service."""
        self.repository = repository

    def train_model(self, command: TrainModelCommand) -> ModelAggregate:
        """Train a model using the provided command."""
        start_time = time.time()
        # Get the model aggregate
        model_aggregate = self.repository.get_by_id(command.model_id)
        if not model_aggregate:
            raise ValueError(f"Model {command.model_id} not found")

        # Execute the command
        updated_aggregate = command.execute(model_aggregate)

        # Save the updated aggregate
        self.repository.update(updated_aggregate)

        # Record training job completion metrics
        TRAINING_JOBS_TOTAL.labels(status="completed").inc()
        TRAINING_JOB_DURATION.observe(time.time() - start_time)

        return updated_aggregate

    def get_model(self, query: GetModelQuery) -> Optional[ModelAggregate]:
        """Get a model using the provided query."""
        return query.execute(self.repository)

    def list_models(self, query: ListModelsQuery) -> List[ModelAggregate]:
        """List models using the provided query."""
        return query.execute(self.repository)

    def evaluate_model(self, model_id: str, evaluation_data: dict) -> ModelAggregate:
        """Evaluate a model."""
        start_time = time.time()
        try:
            # Get the model
            model_aggregate = self.repository.get_by_id(model_id)
            if not model_aggregate:
                raise ValueError(f"Model {model_id} not found")

            # Update model status to evaluating
            model_aggregate.update_status("evaluating")

            # In a real implementation, this would run the evaluation
            # For now, we'll simulate by updating with mock metrics
            model_aggregate.evaluation_metrics = {
                "accuracy": 0.95,
                "precision": 0.93,
                "recall": 0.97,
                "f1_score": 0.95
            }
            model_aggregate.updated_at = datetime.utcnow()

            # Add domain event for evaluation completed
            model_aggregate.add_domain_event({
                "event_type": "model.evaluation.completed",
                "model_id": model_id,
                "metrics": model_aggregate.evaluation_metrics,
                "evaluated_at": datetime.utcnow().isoformat()
            })

            # Save the updated aggregate
            self.repository.update(model_aggregate)

            # Record evaluation completion metrics
            MODEL_EVALUATIONS_TOTAL.labels(status="completed").inc()

            return model_aggregate
        except Exception as e:
            # Record evaluation failure metric
            MODEL_EVALUATIONS_TOTAL.labels(status="failed").inc()
            raise e

    def deploy_model(self, model_id: str, deployed_by: str = None) -> ModelAggregate:
        """Deploy a model."""
        # Get the model
        model_aggregate = self.repository.get_by_id(model_id)
        if not model_aggregate:
            # Record deployment failure metric
            DEPLOYMENTS_TOTAL.labels(status="failure").inc()
            raise ValueError(f"Model {model_id} not found")

        try:
            # Check if model is ready for deployment
            if model_aggregate.model.status not in ["trained", "evaluated"]:
                raise ValueError(f"Model {model_id} is not ready for deployment. Current status: {model_aggregate.model.status}")

            # Deploy the model
            model_aggregate.deploy(deployed_by)

            # Save the updated aggregate
            self.repository.update(model_aggregate)

            # Record deployment success metric
            DEPLOYMENTS_TOTAL.labels(status="success").inc()

            return model_aggregate
        except Exception as e:
            # Record deployment failure metric
            DEPLOYMENTS_TOTAL.labels(status="failure").inc()
            raise e