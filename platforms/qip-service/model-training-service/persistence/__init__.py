"""Persistence layer for the Model Training Service."""

from .base_repository import BaseRepository
from .model_evaluation_repository_impl import ModelEvaluationRepositoryImpl
from .model_repository_impl import ModelRepositoryImpl
from .model_version_repository_impl import ModelVersionRepositoryImpl
from .training_job_repository_impl import TrainingJobRepositoryImpl

# Import messaging components
from ..infrastructure.messaging import KafkaProducer

__all__ = [
    "BaseRepository",
    "ModelEvaluationRepositoryImpl",
    "ModelRepositoryImpl",
    "ModelVersionRepositoryImpl",
    "TrainingJobRepositoryImpl",
    "KafkaProducer"
]
