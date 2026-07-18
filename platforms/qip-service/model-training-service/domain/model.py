"""SQLAlchemy models for the Model Training Service."""

import uuid
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

Base = declarative_base()


class Model(Base):
    """Model entity representing a machine learning model."""

    __tablename__ = "models"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    model_type = Column(String(50), nullable=False)  # classification, regression, clustering, etc.
    algorithm = Column(String(50), nullable=False)  # random_forest, xgboost, neural_network, etc.
    version = Column(String(20), nullable=False, default="1.0.0")
    status = Column(String(20), nullable=False, default="created")  # created, training, completed, failed, deployed, archived
    accuracy = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)
    training_config = Column(JSON, nullable=True)  # Hyperparameters and training configuration
    feature_schema = Column(JSON, nullable=True)  # Expected input features
    model_path = Column(String(500), nullable=True)  # Path to stored model artifact
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    trained_at = Column(DateTime(timezone=True), nullable=True)
    deployed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    evaluations = relationship("ModelEvaluation", back_populates="model", cascade="all, delete-orphan")
    versions = relationship("ModelVersion", back_populates="model", cascade="all, delete-orphan")


class ModelEvaluation(Base):
    """Model evaluation entity."""

    __tablename__ = "model_evaluations"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    model_id = Column(String(36), ForeignKey("models.id"), nullable=False)
    evaluation_type = Column(String(50), nullable=False)  # validation, production, A/B test
    status = Column(String(20), nullable=False, default="pending")  # pending, running, completed, failed
    metrics = Column(JSON, nullable=True)  # Evaluation metrics
    dataset_info = Column(JSON, nullable=True)  # Information about evaluation dataset
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    model = relationship("Model", back_populates="evaluations")


class ModelVersion(Base):
    """Model version entity for tracking different versions of the same model."""

    __tablename__ = "model_versions"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    model_id = Column(String(36), ForeignKey("models.id"), nullable=False)
    version_number = Column(String(20), nullable=False)
    model_path = Column(String(500), nullable=True)
    performance_metrics = Column(JSON, nullable=True)
    release_notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    model = relationship("Model", back_populates="versions")


class TrainingJob(Base):
    """Training job entity for tracking asynchronous training processes."""

    __tablename__ = "training_jobs"

    id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    model_id = Column(String(36), ForeignKey("models.id"), nullable=False)
    status = Column(String(20), nullable=False, default="queued")  # queued, running, completed, failed, cancelled
    progress = Column(Integer, default=0)  # Progress percentage
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    model = relationship("Model")