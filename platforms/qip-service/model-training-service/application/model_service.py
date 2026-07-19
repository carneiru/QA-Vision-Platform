"""Service layer for model training operations using repository pattern."""

from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from domain.model import Model, ModelEvaluation, ModelVersion, TrainingJob
from persistence import (
    ModelRepository,
    ModelEvaluationRepository,
    ModelVersionRepository,
    TrainingJobRepository,
    KafkaProducer
)


class ModelService:
    """Service for model operations using repository pattern."""

    def __init__(
        self,
        model_repository: ModelRepository,
        model_evaluation_repository: ModelEvaluationRepository,
        model_version_repository: ModelVersionRepository,
        training_job_repository: TrainingJobRepository,
        kafka_producer: KafkaProducer = None
    ):
        """Initialize service with repository dependencies."""
        self.model_repo = model_repository
        self.model_evaluation_repo = model_evaluation_repo
        self.model_version_repo = model_version_repo
        self.training_job_repo = training_job_repo
        self.kafka_producer = kafka_producer

    async def create_model(self, model_data: dict, created_by: Optional[str] = None) -> Model:
        """Create a new model."""
        model_dict = model_data.copy()
        if created_by:
            model_dict["created_by"] = created_by

        model = Model(**model_dict)
        created_model = await self.model_repo.create(model)
        
        # Publish model created event
        if self.kafka_producer:
            self.kafka_producer.publish_model_created(
                model_id=created_model.id,
                model_data=created_model.dict(),
                created_by=created_by
            )
        
        return created_model

    async def get_model(self, model_id: str) -> Optional[Model]:
        """Get a model by ID."""
        return await self.model_repo.get_by_id(model_id)

    async def get_models(self, skip: int = 0, limit: int = 100) -> List[Model]:
        """Get a list of models."""
        return await self.model_repo.get_all(skip=skip, limit=limit)

    async def update_model(self, model_id: str, model_data: dict) -> Optional[Model]:
        """Update a model."""
        model = await self.model_repo.get_by_id(model_id)
        if not model:
            return None

        # Store original values for event
        original_data = model.dict()
        
        # Update model attributes
        for key, value in model_data.items():
            if hasattr(model, key) and not key.startswith('_') and key != 'id':
                setattr(model, key, value)

        updated_model = await self.model_repo.update(model)
        
        # Publish model updated event
        if self.kafka_producer:
            self.kafka_producer.publish_model_updated(
                model_id=updated_model.id,
                changes={k: v for k, v in model_data.items() if k in updated_model.dict() and 
                         updated_model.dict()[k] != original_data.get(k)},
                updated_by=None  # TODO: Get from context
            )
        
        return updated_model

    async def delete_model(self, model_id: str) -> bool:
        """Delete a model."""
        model = await self.model_repo.get_by_id(model_id)
        if not model:
            return False
        
        result = await self.model_repo.delete(model_id)
        
        # Publish model deleted event
        if self.kafka_producer and result:
            self.kafka_producer.publish_model_deleted(
                model_id=model_id
            )
        
        return result

    async def train_model(self, model_id: str) -> str:
        """Start training a model."""
        # Get the model
        model = await self.model_repo.get_by_id(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")

        # Update status to training
        model.status = "training"
        model.updated_at = datetime.utcnow()
        await self.model_repo.update(model)

        # Generate training job ID
        training_job_id = str(uuid.uuid4())

        # Create training job record
        training_job = TrainingJob(
            id=training_job_id,
            model_id=model_id,
            status="queued"
        )
        await self.training_job_repo.create(training_job)

        # Publish training started event
        if self.kafka_producer:
            self.kafka_producer.publish_training_requested(
                model_id=model_id,
                training_job_id=training_job_id,
                training_config=model.training_config or {}
            )

        # Start training in background (this would be handled by a task queue in production)
        # For now, we'll simulate by calling the trainer function directly
        # In a real implementation, this would be offloaded to a worker process
        try:
            # Import here to avoid circular imports
            from model_training.core.model_trainer import train_model as train_model_func
            train_model_func(
                model_id=model_id,
                training_job_id=training_job_id,
                training_config=model.training_config or {},
                model_repository=self.model_repo,
                training_job_repository=self.training_job_repo,
                kafka_producer=self.kafka_producer
            )
        except Exception as e:
            # Update training job status on failure
            training_job.status = "failed"
            training_job.error_message = str(e)
            training_job.updated_at = datetime.utcnow()
            await self.training_job_repo.update(training_job)
            
            # Publish training failed event
            if self.kafka_producer:
                self.kafka_producer.publish_training_completed(
                    model_id=model_id,
                    training_job_id=training_job_id,
                    success=False,
                    error_message=str(e)
                )
            raise e

        return training_job_id

    async def evaluate_model(self, model_id: str, evaluation_request: dict) -> str:
        """Start evaluating a model."""
        # Get the model
        model = await self.model_repo.get_by_id(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")

        # Generate evaluation ID
        evaluation_id = str(uuid.uuid4())

        # Create evaluation record
        evaluation = ModelEvaluation(
            id=evaluation_id,
            model_id=model_id,
            evaluation_type=evaluation_request.get("evaluation_type"),
            status="pending"
        )
        await self.model_evaluation_repo.create(evaluation)

        # Publish evaluation started event
        if self.kafka_producer:
            self.kafka_producer.publish_evaluation_requested(
                model_id=model_id,
                evaluation_id=evaluation_id,
                evaluation_config=evaluation_request.get("evaluation_config", {})
            )

        # Start evaluation in background
        try:
            # Import here to avoid circular imports
            from model_training.core.model_evaluator import evaluate_model as evaluate_model_func
            evaluate_model_func(
                model_id=model_id,
                evaluation_id=evaluation_id,
                evaluation_config=evaluation_request.get("evaluation_config", {}),
                model_evaluation_repository=self.model_evaluation_repo,
                model_repository=self.model_repo,
                kafka_producer=self.kafka_producer
            )
        except Exception as e:
            # Update evaluation status on failure
            evaluation.status = "failed"
            evaluation.error_message = str(e)
            evaluation.updated_at = datetime.utcnow()
            await self.model_evaluation_repo.update(evaluation)
            
            # Publish evaluation failed event
            if self.kafka_producer:
                self.kafka_producer.publish_evaluation_completed(
                    model_id=model_id,
                    evaluation_id=evaluation_id,
                    success=False,
                    error_message=str(e)
                )
            raise e

        return evaluation_id

    async def deploy_model(self, model_id: str) -> Model:
        """Deploy a model."""
        model = await self.model_repo.get_by_id(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")

        if model.status != "completed":
            raise ValueError(f"Model {model_id} must be completed before deployment")

        model.status = "deployed"
        model.is_active = True
        model.deployed_at = datetime.utcnow()
        model.updated_at = datetime.utcnow()
        updated_model = await self.model_repo.update(model)
        
        # Publish model deployed event
        if self.kafka_producer:
            self.kafka_producer.publish_model_deployed(
                model_id=updated_model.id,
                deployed_by=None  # TODO: Get from context
            )
        
        return updated_model

    async def retire_model(self, model_id: str) -> Model:
        """Retire a model."""
        model = await self.model_repo.get_by_id(model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")

        model.status = "retired"
        model.is_active = False
        model.updated_at = datetime.utcnow()
        updated_model = await self.model_repo.update(model)
        
        # Publish model retired event
        if self.kafka_producer:
            self.kafka_producer.publish_model_retired(
                model_id=updated_model.id,
                retired_by=None  # TODO: Get from context
            )
        
        return updated_model

    async def get_model_versions(self, model_id: str) -> List[ModelVersion]:
        """Get all versions of a model."""
        return await self.model_version_repo.get_by_model_id(model_id)

    async def get_model_evaluations(self, model_id: str) -> List[ModelEvaluation]:
        """Get all evaluations of a model."""
        return await self.model_evaluation_repo.get_by_model_id(model_id)
