"""Model Training API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from datetime import datetime

from model_training.db import get_db
from model_training.models import model as model_models
from model_training.schemas import model as model_schemas
from model_training.service import model_service

# Create database tables
from model_training.db import engine
model_models.Base.metadata.create_all(bind=engine)

router = APIRouter()


@router.post("/", response_model=model_schemas.ModelResponse, status_code=status.HTTP_201_CREATED)
async def register_model(
    model_data: model_schemas.ModelCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Register a new ML model for training.

    This endpoint creates a new model record and initiates the training process
    in the background.
    """
    # Create model record
    db_model = model_service.ModelService.create_model(db, model_data, model_data.created_by)

    # Update status to training
    db_model.status = "training"
    db_model.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_model)

    # Start training in background
    background_tasks.add_task(
        model_service.ModelService.train_model,
        db_model.id,
        db
    )

    return db_model


@router.get("/{model_id}", response_model=model_schemas.ModelResponse)
async def get_model(model_id: str, db: Session = Depends(get_db)):
    """
    Get model details and metadata by ID.
    """
    model = model_service.ModelService.get_model(db, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID {model_id} not found"
        )
    return model


@router.put("/{model_id}/version/{version}", response_model=model_schemas.ModelResponse)
async def deploy_model_version(
    model_id: str,
    version: str,
    db: Session = Depends(get_db)
):
    """
    Deploy a specific model version.

    This endpoint marks a specific model version as active/production.
    """
    # Get the specific model version
    model = db.query(model_models.Model).filter(
        model_models.Model.id == model_id,
        model_models.Model.version == version
    ).first()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} version {version} not found"
        )

    # Deactivate all other versions of this model
    db.query(model_models.Model).filter(
        model_models.Model.id == model_id
    ).update({model_models.Model.is_active: False})

    # Activate this version
    model.is_active = True
    model.status = "deployed"
    model.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(model)

    return model


@router.post("/{model_id}/evaluate", response_model=model_schemas.ModelEvaluationResponse)
async def evaluate_model(
    model_id: str,
    evaluation_request: model_schemas.ModelEvaluationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Run model evaluation against a test dataset.

    This endpoint triggers model evaluation and returns the results.
    """
    model = model_service.ModelService.get_model(db, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID {model_id} not found"
        )

    # Create evaluation record
    evaluation = model_models.ModelEvaluation(
        id=str(uuid.uuid4()),
        model_id=model_id,
        evaluation_type=evaluation_request.evaluation_type,
        status="running",
        started_at=datetime.utcnow(),
        parameters=evaluation_request.parameters or {}
    )

    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)

    # Start evaluation in background
    background_tasks.add_task(
        model_service.ModelService.evaluate_model,
        model_id,
        evaluation.id,
        evaluation_request.evaluation_config or {},
        db
    )

    return model_schemas.ModelEvaluationResponse(
        evaluation_id=evaluation.id,
        model_id=model_id,
        status="running",
        started_at=evaluation.started_at
    )


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def retire_model(model_id: str, db: Session = Depends(get_db)):
    """
    Retire a model version.

    This endpoint marks a model as retired/deprecated.
    """
    model = model_service.ModelService.get_model(db, model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model with ID {model_id} not found"
        )

    model.status = "retired"
    model.updated_at = datetime.utcnow()

    db.commit()

    return None


@router.get("/", response_model=List[model_schemas.ModelResponse])
async def list_models(
    skip: int = 0,
    limit: int = 100,
    model_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List models with optional filtering.
    """
    query = db.query(model_models.Model)

    if model_type:
        query = query.filter(model_models.Model.model_type == model_type)

    if status:
        query = query.filter(model_models.Model.status == status)

    models = query.offset(skip).limit(limit).all()
    return models


@router.get("/{model_id}/versions", response_model=List[model_schemas.ModelResponse])
async def get_model_versions(model_id: str, db: Session = Depends(get_db)):
    """
    Get all versions of a specific model.
    """
    models = model_service.ModelService.get_model_versions(db, model_id)

    if not models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No versions found for model {model_id}"
        )

    return models


@router.get("/{model_id}/evaluations", response_model=List[model_schemas.ModelEvaluationResponse])
def get_model_evaluations(
    model_id: str,
    db: Session = Depends(get_db)
):
    """Get all evaluations of an ML model."""
    # Check if model exists
    db_model = model_service.ModelService.get_model(db, model_id)
    if db_model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    evaluations = model_service.ModelService.get_model_evaluations(db, model_id)
    return evaluations