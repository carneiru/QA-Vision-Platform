"""Model Training API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from datetime import datetime
import time
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

from model_training.db import get_db
from model_training.infrastructure.persistence.model_repository import ModelRepositoryImpl
from model_training.service import model_service
from model_training.models import model as model_models
from model_training.schemas import model as model_schemas
from model_training.auth import get_current_user, require_role, require_any_role
from model_training.db import engine

# Initialize router
router = APIRouter()

# Prometheus metrics
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

def get_model_repository(db: Session = Depends(get_db)) -> ModelRepositoryImpl:
    """Dependency to get model repository."""
    return ModelRepositoryImpl(db)

def get_model_service(repository: ModelRepositoryImpl = Depends(get_model_repository)) -> model_service.ModelService:
    """Dependency to get model service."""
    return model_service.ModelService(repository)

async def register_model(
    model_data: model_schemas.ModelCreate,
    background_tasks: BackgroundTasks,
    service: model_service.ModelService = Depends(get_model_service),
    current_user: dict = Depends(get_current_user)
):
    """Register a new ML model."""
    try:
        # Prepare model data
        model_dict = model_data.dict()
        model_dict["created_by"] = current_user.get("sub")
        
        # Create model using service
        model_aggregate = service.create_model(model_dict, current_user.get("sub"))
        
        # Convert to response format
        response_data = {
            "id": model_aggregate.model.id,
            "name": model_aggregate.model.name,
            "description": model_aggregate.model.description,
            "model_type": model_aggregate.model.model_type.value,
            "status": model_aggregate.model.status.value,
            "version": model_aggregate.model.version,
            "created_by": model_aggregate.model.created_by,
            "created_at": model_aggregate.model.created_at.isoformat() if model_aggregate.model.created_at else None,
            "updated_at": model_aggregate.model.updated_at.isoformat() if model_aggregate.model.updated_at else None
        }
        
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=response_data
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create model: {str(e)}"
        )

async def get_model(
    model_id: str,
    service: model_service.ModelService = Depends(get_model_service),
    current_user: dict = Depends(get_current_user)
):
    """Get model details and metadata."""
    try:
        model_aggregate = service.get_model(model_id)
        if not model_aggregate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model {model_id} not found"
            )
        
        # Convert to response format
        response_data = {
            "id": model_aggregate.model.id,
            "name": model_aggregate.model.name,
            "description": model_aggregate.model.description,
            "model_type": model_aggregate.model.model_type.value,
            "status": model_aggregate.model.status.value,
            "version": model_aggregate.model.version,
            "created_by": model_aggregate.model.created_by,
            "created_at": model_aggregate.model.created_at.isoformat() if model_aggregate.model.created_at else None,
            "updated_at": model_aggregate.model.updated_at.isoformat() if model_aggregate.model.updated_at else None,
            "training_config": model_aggregate.model.training_config,
            "evaluation_metrics": model_aggregate.model.evaluation_metrics,
            "deployed_at": model_aggregate.model.deployed_at.isoformat() if model_aggregate.model.deployed_at else None,
            "deployed_by": model_aggregate.model.deployed_by
        }
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=response_data
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve model: {str(e)}"
        )

async def deploy_model_version(
    model_id: str,
    version: str,
    background_tasks: BackgroundTasks,
    service: model_service.ModelService = Depends(get_model_service),
    current_user: dict = Depends(get_current_user)
):
    """Deploy specific model version."""
    try:
        # Deploy model version using service
        model_aggregate = service.deploy_model_version(model_id, version, current_user.get("sub"))
        
        # Convert to response format
        response_data = {
            "id": model_aggregate.model.id,
            "name": model_aggregate.model.name,
            "version": model_aggregate.model.version,
            "model_type": model_aggregate.model.model_type.value,
            "status": model_aggregate.model.status.value,
            "deployed_at": model_aggregate.model.deployed_at.isoformat() if model_aggregate.model.deployed_at else None,
            "deployed_by": model_aggregate.model.deployed_by
        }
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=response_data
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deploy model: {str(e)}"
        )

async def evaluate_model(
    model_id: str,
    evaluation_data: model_schemas.ModelEvaluation,
    background_tasks: BackgroundTasks,
    service: model_service.ModelService = Depends(get_model_service),
    current_user: dict = Depends(get_current_user)
):
    """Run model evaluation against test set."""
    try:
        # Start evaluation using service
        evaluation_id = service.evaluate_model(
            model_id, 
            evaluation_data.dict(), 
            current_user.get("sub")
        )
        
        # Return evaluation ID
        response_data = {
            "evaluation_id": evaluation_id,
            "status": "started",
            "message": "Model evaluation started successfully"
        }
        
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=response_data
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start model evaluation: {str(e)}"
        )

async def retire_model(
    model_id: str,
    background_tasks: BackgroundTasks,
    service: model_service.ModelService = Depends(get_model_service),
    current_user: dict = Depends(get_current_user)
):
    """Retire model version."""
    try:
        # Retire model using service
        model_aggregate = service.retire_model(model_id, current_user.get("sub"))
        
        # Convert to response format
        response_data = {
            "id": model_aggregate.model.id,
            "name": model_aggregate.model.name,
            "status": model_aggregate.model.status.value,
            "retired_at": model_aggregate.model.updated_at.isoformat() if model_aggregate.model.updated_at else None,
            "retired_by": model_aggregate.model.retired_by
        }
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=response_data
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retire model: {str(e)}"
        )

async def list_models(
    skip: int = 0,
    limit: int = 100,
    model_type: Optional[str] = None,
    status: Optional[str] = None,
    service: model_service.ModelService = Depends(get_model_service),
    current_user: dict = Depends(get_current_user)
):
    """List models with optional filtering."""
    try:
        # Get models using service
        models = service.get_models(skip=skip, limit=limit, model_type=model_type, status=status)
        
        # Convert to response format
        model_list = []
        for model_aggregate in models:
            model_data = {
                "id": model_aggregate.model.id,
                "name": model_aggregate.model.name,
                "description": model_aggregate.model.description,
                "model_type": model_aggregate.model.model_type.value,
                "status": model_aggregate.model.status.value,
                "version": model_aggregate.model.version,
                "created_by": model_aggregate.model.created_by,
                "created_at": model_aggregate.model.created_at.isoformat() if model_aggregate.model.created_at else None,
                "updated_at": model_aggregate.model.updated_at.isoformat() if model_aggregate.model.updated_at else None
            }
            model_list.append(model_data)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "models": model_list,
                "count": len(model_list),
                "skip": skip,
                "limit": limit
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list models: {str(e)}"
        )

async def get_model_versions(
    model_id: str,
    service: model_service.ModelService = Depends(get_model_service),
    current_user: dict = Depends(get_current_user)
):
    """Get all versions of a specific model."""
    try:
        # Get model versions using service
        model_versions = service.get_model_versions(model_id)
        
        # Convert to response format
        versions_list = []
        for model_aggregate in model_versions:
            version_data = {
                "id": model_aggregate.model.id,
                "version": model_aggregate.model.version,
                "model_type": model_aggregate.model.model_type.value,
                "status": model_aggregate.model.status.value,
                "is_active": model_aggregate.model.is_active,
                "created_at": model_aggregate.model.created_at.isoformat() if model_aggregate.model.created_at else None,
                "updated_at": model_aggregate.model.updated_at.isoformat() if model_aggregate.model.updated_at else None
            }
            versions_list.append(version_data)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "model_id": model_id,
                "versions": versions_list,
                "count": len(versions_list)
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get model versions: {str(e)}"
        )

async def get_model_evaluations(
    model_id: str,
    service: model_service.ModelService = Depends(get_model_service),
    current_user: dict = Depends(get_current_user)
):
    """Get all evaluations for a specific model."""
    try:
        # Get model evaluations using service
        evaluations = service.get_model_evaluations(model_id)
        
        # Convert to response format
        evaluations_list = []
        for eval_aggregate in evaluations:
            eval_data = {
                "id": eval_aggregate.model.id,
                "model_id": eval_aggregate.model.id,  # This would be different in a real implementation
                "evaluation_type": "standard",  # Placeholder
                "status": eval_aggregate.model.status.value,  # This is not ideal but works for now
                "completed_at": eval_aggregate.model.updated_at.isoformat() if eval_aggregate.model.updated_at else None,
                "metrics": eval_aggregate.model.evaluation_metrics
            }
            evaluations_list.append(eval_data)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "model_id": model_id,
                "evaluations": evaluations_list,
                "count": len(evaluations_list)
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get model evaluations: {str(e)}"
        )

async def get_model_evaluation(
    model_id: str,
    evaluation_id: str,
    service: model_service.ModelService = Depends(get_model_service),
    current_user: dict = Depends(get_current_user)
):
    """Get a specific evaluation by ID."""
    try:
        # Get model evaluation using service
        evaluation = service.get_model_evaluation(model_id, evaluation_id)
        if not evaluation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evaluation {evaluation_id} for model {model_id} not found"
            )
        
        # Convert to response format
        eval_data = {
            "id": evaluation.model.id,
            "model_id": evaluation.model.id,  # This would be different in a real implementation
            "evaluation_type": "standard",  # Placeholder
            "status": evaluation.model.status.value,  # This is not ideal but works for now
            "created_at": evaluation.model.created_at.isoformat() if evaluation.model.created_at else None,
            "updated_at": evaluation.model.updated_at.isoformat() if evaluation.model.updated_at else None,
            "metrics": evaluation.model.evaluation_metrics
        }
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=eval_data
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get model evaluation: {str(e)}"
        )

async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

async def liveness_probe():
    """Liveness probe endpoint."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "alive"}
    )

async def readiness_probe(
    repository: ModelRepositoryImpl = Depends(get_model_repository)
):
    """Readiness probe endpoint."""
    try:
        # Simple check: can we query the database?
        # We'll just check if the repository works by trying to count models
        models = repository.list_models(limit=1)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ready", "database": "connected"}
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready", "error": str(e)}
        )

async def health_check(
    repository: ModelRepositoryImpl = Depends(get_model_repository)
):
    """Health check endpoint."""
    try:
        # Check database connectivity
        models = repository.list_models(limit=1)
        
        # Get model counts by status
        all_models = repository.list_models(limit=1000)
        status_counts = {}
        for model in all_models:
            status = model.model.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "healthy",
                "database": "connected",
                "model_count": len(all_models),
                "status_breakdown": status_counts
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "error": str(e)}
        )
