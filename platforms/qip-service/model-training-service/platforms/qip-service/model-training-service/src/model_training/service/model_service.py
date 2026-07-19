"""Service layer for model training operations."""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from model_training.models import model as model_models
from model_training.schemas import model as model_schemas
from model_training.core.model_trainer import train_model
from model_training.core.model_evaluator import evaluate_model


class ModelService:
    """Service for model operations."""

    @staticmethod
    def create_model(db: Session, model_data: model_schemas.ModelCreate, created_by: Optional[str] = None) -> model_models.Model:
        """Create a new model."""
        model_dict = model_data.dict()
        if created_by:
            model_dict["created_by"] = created_by

        db_model = model_models.Model(**model_dict)
        db.add(db_model)
        db.commit()
        db.refresh(db_model)
        return db_model

    @staticmethod
    def get_model(db: Session, model_id: str) -> Optional[model_models.Model]:
        """Get a model by ID."""
        return db.query(model_models.Model).filter(model_models.Model.id == model_id).first()

    @staticmethod
    def get_models(db: Session, skip: int = 0, limit: int = 100) -> List[model_models.Model]:
        """Get a list of models."""
        return db.query(model_models.Model).offset(skip).limit(limit).all()

    @staticmethod
    def update_model(db: Session, model_id: str, model_data: model_schemas.ModelUpdate) -> Optional[model_models.Model]:
        """Update a model."""
        db_model = ModelService.get_model(db, model_id)
        if not db_model:
            return None

        update_data = model_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_model, field, value)

        db_model.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_model)
        return db_model

    @staticmethod
    def delete_model(db: Session, model_id: str) -> bool:
        """Delete a model."""
        db_model = ModelService.get_model(db, model_id)
        if not db_model:
            return False

        db.delete(db_model)
        db.commit()
        return True

    @staticmethod
    def train_model(db: Session, model_id: str) -> str:
        """Start training a model."""
        # Get the model
        model = ModelService.get_model(db, model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")

        # Update status to training
        model.status = "training"
        model.updated_at = datetime.utcnow()
        db.commit()

        # Generate training job ID
        training_job_id = str(uuid.uuid4())

        # Create training job record
        training_job = model_models.TrainingJob(
            id=training_job_id,
            model_id=model_id,
            status="queued"
        )
        db.add(training_job)
        db.commit()

        # Start training in background (this would be handled by a task queue in production)
        # For now, we'll simulate by calling the trainer function directly
        # In a real implementation, this would be offloaded to a worker process
        try:
            train_model(model_id, training_job_id, model.training_config or {}, db)
        except Exception as e:
            # Update training job status on failure
            training_job.status = "failed"
            training_job.updated_at = datetime.utcnow()
            db.commit()
            raise e

        return training_job_id

    @staticmethod
    def evaluate_model(db: Session, model_id: str, evaluation_request: model_schemas.ModelEvaluationRequest) -> str:
        """Start evaluating a model."""
        # Get the model
        model = ModelService.get_model(db, model_id)
        if not model:
            raise ValueError(f"Model {model_id} not found")

        # Generate evaluation ID
        evaluation_id = str(uuid.uuid4())

        # Create evaluation record
        evaluation = model_models.ModelEvaluation(
            id=evaluation_id,
            model_id=model_id,
            evaluation_type=evaluation_request.evaluation_type,
            status="pending",
            metrics=None,
            dataset_info=None
        )
        db.add(evaluation)
        db.commit()

        # Start evaluation in background
        try:
            evaluate_model(model_id, evaluation_id, evaluation_request.dict(), db)
        except Exception as e:
            # Update evaluation status on failure
            evaluation.status = "failed"
            evaluation.error_message = str(e)
            evaluation.updated_at = datetime.utcnow()
            db.commit()
            raise e

        return evaluation_id

    @staticmethod
    def deploy_model(db: Session, model_id: str) -> model_models.Model:
        """Deploy a model."""
        db_model = ModelService.get_model(db, model_id)
        if not db_model:
            raise ValueError(f"Model {model_id} not found")

        if db_model.status != "completed":
            raise ValueError(f"Model {model_id} must be completed before deployment")

        db_model.status = "deployed"
        db_model.is_active = True
        db_model.deployed_at = datetime.utcnow()
        db_model.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_model)
        return db_model

    @staticmethod
    def retire_model(db: Session, model_id: str) -> model_models.Model:
        """Retire a model."""
        db_model = ModelService.get_model(db, model_id)
        if not db_model:
            raise ValueError(f"Model {model_id} not found")

        db_model.status = "retired"
        db_model.is_active = False
        db_model.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_model)
        return db_model

    @staticmethod
    def get_model_versions(db: Session, model_id: str) -> List[model_models.ModelVersion]:
        """Get all versions of a model."""
        return db.query(model_models.ModelVersion).filter(
            model_models.ModelVersion.model_id == model_id
        ).all()

    @staticmethod
    def get_model_evaluations(db: Session, model_id: str) -> List[model_models.ModelEvaluation]:
        """Get all evaluations of a model."""
        return db.query(model_models.ModelEvaluation).filter(
            model_models.ModelEvaluation.model_id == model_id
        ).all()