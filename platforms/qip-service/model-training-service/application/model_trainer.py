"""Core model training functionality using repository pattern."""

import logging
from typing import Dict, Any
from datetime import datetime

from domain.model import Model, TrainingJob
from persistence import ModelRepository, TrainingJobRepository, ModelEvaluationRepository
from infrastructure.messaging import KafkaProducer

logger = logging.getLogger(__name__)


def train_model(
    model_id: str,
    training_job_id: str,
    training_config: Dict[str, Any],
    model_repository: ModelRepository = None,
    training_job_repository: TrainingJobRepository = None,
    kafka_producer: KafkaProducer = None
):
    """
    Train a machine learning model using repository pattern.

    This function runs in the background and updates the model status
    as training progresses.
    """
    # Initialize repositories if not provided (for backward compatibility)
    db_session = None
    try:
        if model_repository is None or training_job_repository is None:
            # Fallback to direct database access for backward compatibility
            from model_training.db import get_db
            from model_training.models import model as model_models

            db_session = next(get_db())

            # Get the model from database
            model = db_session.query(model_models.Model).filter(
                model_models.Model.id == model_id
            ).first()

            if not model:
                logger.error(f"Model {model_id} not found")
                return

            # Update status to training
            model.status = "training"
            model.updated_at = datetime.utcnow()
            db_session.commit()

            # TODO: Implement actual model training logic
            # This would involve:
            # 1. Loading training data based on model type
            # 2. Preprocessing data
            # 3. Selecting algorithm based on model_type
            # 4. Training with hyperparameters from training_config
            # 5. Validating the model
            # 6. Saving the trained model artifacts

            # For now, simulate training completion
            import time
            time.sleep(5)  # Simulate training time

            # Update model with training results
            model.status = "completed"
            model.accuracy = 0.85  # Placeholder - in reality would come from actual training
            model.trained_at = datetime.utcnow()
            model.updated_at = datetime.utcnow()
            model.model_path = f"/models/{model_id}/model.pkl"  # Placeholder path

            db_session.commit()
            logger.info(f"Model {model_id} training completed successfully")

            # Publish training completed event
            if kafka_producer:
                kafka_producer.publish_training_completed(
                    model_id=model_id,
                    training_job_id=training_job_id,
                    success=True,
                    metrics={"accuracy": model.accuracy}
                )

        else:
            # Use repository pattern
            # Get the model
            model = model_repository.get_by_id(model_id)

            if not model:
                logger.error(f"Model {model_id} not found")
                return

            # Update status to training
            model.status = "training"
            model.updated_at = datetime.utcnow()
            model_repository.update(model)

            # TODO: Implement actual model training logic
            # This would involve:
            # 1. Loading training data based on model type
            # 2. Preprocessing data
            # 3. Selecting algorithm based on model_type
            # 4. Training with hyperparameters from training_config
            # 5. Validating the model
            # 6. Saving the trained model artifacts

            # For now, simulate training completion
            import time
            time.sleep(5)  # Simulate training time

            # Update model with training results
            model.status = "completed"
            model.accuracy = 0.85  # Placeholder - in reality would come from actual training
            model.trained_at = datetime.utcnow()
            model.updated_at = datetime.utcnow()
            model.model_path = f"/models/{model_id}/model.pkl"  # Placeholder path

            model_repository.update(model)
            logger.info(f"Model {model_id} training completed successfully")

            # Update training job status
            training_job = training_job_repository.get_by_id(training_job_id)
            if training_job:
                training_job.status = "completed"
                training_job.completed_at = datetime.utcnow()
                training_job.updated_at = datetime.utcnow()
                training_job_repository.update(training_job)

            # Publish training completed event
            if kafka_producer:
                kafka_producer.publish_training_completed(
                    model_id=model_id,
                    training_job_id=training_job_id,
                    success=True,
                    metrics={"accuracy": model.accuracy}
                )

    except Exception as e:
        error_msg = f"Error training model {model_id}: {str(e)}"
        logger.error(error_msg)
        
        # Update model status to failed
        try:
            if model_repository is None or training_job_repository is None:
                # Fallback to direct database access
                if 'model' in locals() and model:
                    model.status = "failed"
                    model.error_message = str(e)
                    model.updated_at = datetime.utcnow()
                    if db_session:
                        db_session.commit()
            else:
                # Use repository pattern
                if 'model' in locals() and model:
                    model.status = "failed"
                    model.error_message = str(e)
                    model.updated_at = datetime.utcnow()
                    model_repository.update(model)
                    
                    # Update training job status
                    if 'training_job_id' in locals():
                        training_job = training_job_repository.get_by_id(training_job_id)
                        if training_job:
                            training_job.status = "failed"
                            training_job.error_message = str(e)
                            training_job.updated_at = datetime.utcnow()
                            training_job_repository.update(training_job)
        except Exception as update_error:
            logger.error(f"Error updating failed status: {update_error}")
        
        # Publish training failed event
        if kafka_producer:
            kafka_producer.publish_training_completed(
                model_id=model_id,
                training_job_id=training_job_id,
                success=False,
                error_message=str(e)
            )
    finally:
        # Close the database session if we created one
        if 'db_session' in locals() and db_session:
            db_session.close()
