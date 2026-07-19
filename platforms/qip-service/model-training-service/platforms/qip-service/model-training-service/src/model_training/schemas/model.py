"""Pydantic models for API request and response validation."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ModelBase(BaseModel):
    """Base model for Model."""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    model_type: str = Field(..., description="Type of ML model (classification, regression, clustering, etc.)")
    training_config: Optional[Dict[str, Any]] = Field(None, description="Configuration for model training")
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    created_by: Optional[str] = Field(None, description="User who created the model")


class ModelCreate(ModelBase):
    """Model for creating a new model."""
    pass


class ModelUpdate(BaseModel):
    """Model for updating an existing model."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    model_type: Optional[str] = Field(None, description="Type of ML model")
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ModelResponse(ModelBase):
    """Model for model response."""
    id: str
    version: str
    status: str  # training, completed, failed, deployed, retired
    is_active: bool
    created_at: datetime
    updated_at: datetime
    trained_at: Optional[datetime] = None
    deployed_at: Optional[datetime] = None
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None

    class Config:
        orm_mode = True


class ModelEvaluationRequest(BaseModel):
    """Model for model evaluation request."""
    evaluation_type: str = Field(..., description="Type of evaluation (accuracy, precision, recall, f1, etc.)")
    evaluation_config: Optional[Dict[str, Any]] = Field(None, description="Configuration for evaluation")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Additional parameters")


class ModelEvaluationResponse(BaseModel):
    """Model for model evaluation response."""
    evaluation_id: str
    model_id: str
    status: str  # running, completed, failed
    started_at: datetime
    completed_at: Optional[datetime] = None
    metrics: Optional[Dict[str, float]] = None


class ModelVersionResponse(BaseModel):
    """Model for model version response."""
    id: str
    version: str
    status: str
    is_active: bool
    created_at: datetime
    accuracy: Optional[float] = None

    class Config:
        orm_mode = True