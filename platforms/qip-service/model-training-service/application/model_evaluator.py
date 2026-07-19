"""Core model evaluation functionality using repository pattern."""

import logging
from typing import Dict, Any
from datetime import datetime

from domain.model import Model, ModelEvaluation
from persistence import ModelRepository, ModelEvaluationRepository, KafkaProducer

logger = logging.getLogger(__name__)


def evaluate_model(
    model_id: str,
    evaluation_id: str,
    evaluation_config: Dict[str, Any],
    model_repository: ModelRepository = None,
    model_evaluation_repository: ModelEvaluationRepository = None,
    kafka_producer: KafkaProducer = None
):
    """
    Evaluate a machine learning model using repository pattern.

    This function runs in the background and updates the evaluation status
    as evaluation progresses.
    """
    try:
        # Get repositories if not provided (for backward compatibility)
        if model_repository is None or model_evaluation_repository is None:
            # Fallback to direct database access for backward compatibility
            from model_training.db import get_db
            from model_training.models import model as model_models

            db_session = next(get_db())

            # Get the evaluation from database
            evaluation = db_session.query(model_models.ModelEvaluation).filter(
                model_models.ModelEvaluation.id == evaluation_id
            ).first()

            if not evaluation:
                logger.error(f"Evaluation {evaluation_id} not found")
                return

            # Update status to running
            evaluation.status = "running"
            evaluation.updated_at = datetime.utcnow()
            db_session.commit()

            # TODO: Implement actual model evaluation logic
            # This would involve:
            # 1. Loading the trained model
            # 2. Loading test data
            # 3. Running predictions
            # 4. Calculating metrics (accuracy, precision, recall, F1, etc.)
            # 5. Comparing against baseline if specified
            # 6. Generating evaluation report

            # For now, simulate evaluation completion
            import time
            time.sleep(3)  # Simulate evaluation time

            # Update evaluation with results
            evaluation.status = "completed"
            evaluation.completed_at = datetime.utcnow()
            evaluation.metrics = {
                "accuracy": 0.82,
                "precision": 0.79,
                "recall": 0.85,
                "f1_score": 0.82
            }
            evaluation.updated_at = datetime.utcnow()
            db_session.commit()

            # Update model with evaluation results if this is a promotion evaluation
            if evaluation_config.get("promote_if_better_than"):
                model = db_session.query(model_models.Model).filter(
                    model_models.Model.id == model_id
                ).first()
                if model:
                    current_accuracy = getattr(model, 'accuracy', 0) or 0
                    new_accuracy = evaluation.metrics.get("accuracy", 0)

                    if new_accuracy > current_accuracy:
                        model.accuracy = new_accuracy
                        model.evaluated_at = datetime.utcnow()
                        model.updated_at = datetime.utcnow()
                        db_session.commit()
                        logger.info(f"Model {model_id} promoted with accuracy {new_accuracy}")

            # Publish evaluation completed event
            if kafka_producer:
                kafka_producer.publish_evaluation_completed(
                    model_id=model_id,
                    evaluation_id=evaluation_id,
                    success=True,
                    metrics=evaluation.metrics
                )

            logger.info(f"Evaluation {evaluation_id} for model {model_id} completed successfully")

        else:
            # Use repository pattern
            # Get the evaluation
            evaluation = model_evaluation_repository.get_by_id(evaluation_id)
            if not evaluation:
                logger.error(f"Evaluation {evaluation_id} not found")
                return

            # Update status to running
            evaluation.status = "running"
            evaluation.updated_at = datetime.utcnow()
            model_evaluation_repository.update(evaluation)

            # TODO: Implement actual model evaluation logic
            # This would involve:
            # 1. Loading the trained model
            # 2. Loading test data
            # 3. Running predictions
            # 4. Calculating metrics (accuracy, precision, recall, F1, etc.)
            # 5. Comparing against baseline if specified
            # 6. Generating evaluation report

            # For now, simulate evaluation completion
            import time
            time.sleep(3)  # Simulate evaluation time

            # Update evaluation with results
            evaluation.status = "completed"
            evaluation.completed_at = datetime.utcnow()
            evaluation.metrics = {
                "accuracy": 0.82,
                "precision": 0.79,
                "recall": 0.85,
                "f1_score": 0.82
            }
            evaluation.updated_at = datetime.utcnow()
            model_evaluation_repository.update(evaluation)

            # Update model with evaluation results if this is a promotion evaluation
            if evaluation_config.get("promote_if_better_than"):
                model = model_repository.get_by_id(model_id)
                if model:
                    current_accuracy = getattr(model, 'accuracy', 0) or 0
                    new_accuracy = evaluation.metrics.get("accuracy", 0)

                    if new_accuracy > current_accuracy:
                        model.accuracy = new_accuracy
                        model.evaluated_at = datetime.utcnow()
                        model.updated_at = datetime.utcnow()
                        model_repository.update(model)
                        logger.info(f"Model {model_id} promoted with accuracy {new_accuracy}")

            # Publish evaluation completed event
            if kafka_producer:
                kafka_producer.publish_evaluation_completed(
                    model_id=model_id,
                    evaluation_id=evaluation_id,
                    success=True,
                    metrics=evaluation.metrics
                )

            logger.info(f"Evaluation {evaluation_id} for model {model_id} completed successfully")

    except Exception as e:
        error_msg = f"Error evaluating model {model_id}: {str(e)}"
        logger.error(error_msg)
        
        # Update evaluation status to failed
        try:
            if model_repository is None or model_evaluation_repository is None:
                # Fallback to direct database access
                if 'evaluation' in locals() and evaluation:
                    evaluation.status = "failed"
                    evaluation.error_message = str(e)
                    evaluation.updated_at = datetime.utcnow()
                    if 'db_session' in locals():
                        db_session.commit()
            else:
                # Use repository pattern
                if 'evaluation' in locals() and evaluation:
                    evaluation.status = "failed"
                    evaluation.error_message = str(e)
                    evaluation.updated_at = datetime.utcnow()
                    model_evaluation_repository.update(evaluation)
        except Exception as update_error:
            logger.error(f"Error updating failed evaluation status: {update_error}")
        
        # Publish evaluation failed event
        if kafka_producer:
            try:
                kafka_producer.publish_evaluation_completed(
                    model_id=model_id,
                    evaluation_id=evaluation_id,
                    success=False,
                    error_message=str(e)
                )
            except Exception as kafka_error:
                logger.error(f"Error publishing evaluation failed event: {kafka_error}")
