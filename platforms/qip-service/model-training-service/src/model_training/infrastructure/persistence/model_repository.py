"""SQLAlchemy implementation of the model repository."""

from typing import List, Optional
from sqlalchemy.orm import Session
from .....src.model_training.infrastructure.db import models as db_models
from ..domain.aggregates.model_aggregate import ModelAggregate
from ..domain.repositories.model_repository import ModelRepository
from ..domain.entities.model import ModelStatus, ModelType
from ..value_objects.model_metrics import ModelMetrics


class ModelRepositoryImpl(ModelRepository):
    """SQLAlchemy implementation of the model repository."""

    def __init__(self, db_session: Session):
        """Initialize repository with database session."""
        self.db_session = db_session

    def get_by_id(self, model_id: str) -> Optional[ModelAggregate]:
        """Get model by ID."""
        db_model = self.db_session.query(db_models.Model).filter(
            db_models.Model.id == model_id
        ).first()

        if not db_model:
            return None

        return self._db_model_to_aggregate(db_model)

    def add(self, model: ModelAggregate) -> None:
        """Add a new model."""
        db_model = self._aggregate_to_db_model(model)
        self.db_session.add(db_model)
        self.db_session.commit()
        self.db_session.refresh(db_model)
        # Update the aggregate with the database-generated ID if needed
        model.model.id = db_model.id

    def update(self, model: ModelAggregate) -> None:
        """Update an existing model."""
        db_model = self.db_session.query(db_models.Model).filter(
            db_models.Model.id == model.model.id
        ).first()

        if not db_model:
            raise ValueError(f"Model with id {model.model.id} not found")

        # Update the database model
        db_model.name = model.model.name
        db_model.description = model.model.description
        db_model.model_type = model.model.model_type.value
        db_model.status = model.model.status.value
        db_model.version = model.model.version
        db_model.created_by = model.model.created_by
        db_model.updated_by = model.model.updated_by
        db_model.training_config = model.model.training_config
        db_model.evaluation_metrics = model.model.evaluation_metrics
        db_model.deployed_at = model.model.deployed_at
        db_model.deployed_by = model.model.deployed_by
        db_model.updated_at = model.model.updated_at

        self.db_session.commit()
        self.db_session.refresh(db_model)

    def delete(self, model_id: str) -> bool:
        """Delete a model by ID."""
        db_model = self.db_session.query(db_models.Model).filter(
            db_models.Model.id == model_id
        ).first()

        if not db_model:
            return False

        self.db_session.delete(db_model)
        self.db_session.commit()
        return True

    def list_models(self, skip: int = 0, limit: int = 100, status: Optional[str] = None) -> List[ModelAggregate]:
        """List models with optional filtering."""
        query = self.db_session.query(db_models.Model)

        if status:
            query = query.filter(db_models.Model.status == status)

        db_models_list = query.offset(skip).limit(limit).all()

        return [self._db_model_to_aggregate(db_model) for db_model in db_models_list]

    def exists(self, model_id: str) -> bool:
        """Check if a model exists."""
        return self.db_session.query(db_models.Model).filter(
            db_models.Model.id == model_id
        ).first() is not None

    def _db_model_to_aggregate(self, db_model: db_models.Model) -> ModelAggregate:
        """Convert database model to domain aggregate."""
        # Create domain entity
        domain_model = Model(
            id=db_model.id,
            name=db_model.name,
            description=db_model.description,
            model_type=ModelType(db_model.model_type),
            status=ModelStatus(db_model.status),
            version=db_model.version,
            created_at=db_model.created_at,
            updated_at=db_model.updated_at,
            created_by=db_model.created_by,
            updated_by=db_model.updated_by,
            training_config=db_model.training_config,
            evaluation_metrics=db_model.evaluation_metrics,
            deployed_at=db_model.deployed_at,
            deployed_by=db_model.deployed_by
        )

        # Create aggregate
        aggregate = ModelAggregate(model=domain_model)
        return aggregate

    def _aggregate_to_db_model(self, aggregate: ModelAggregate) -> db_models.Model:
        """Convert domain aggregate to database model."""
        model = aggregate.model

        db_model = db_models.Model(
            id=model.id,
            name=model.name,
            description=model.description,
            model_type=model.model_type.value,
            status=model.model_status.value,
            version=model.version,
            created_at=model.created_at,
            updated_at=model.updated_at,
            created_by=model.created_by,
            updated_by=model.updated_by,
            training_config=model.training_config,
            evaluation_metrics=model.evaluation_metrics,
            deployed_at=model.deployed_at,
            deployed_by=model.deployed_by
        )

        return db_model