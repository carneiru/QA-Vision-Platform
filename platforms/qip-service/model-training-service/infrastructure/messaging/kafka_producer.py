"""Kafka producer implementation for model lifecycle events."""

import json
import logging
from typing import Dict, Any
from datetime import datetime

try:
    from confluent_kafka import Producer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    Producer = None

from ..config.settings import Settings

logger = logging.getLogger(__name__)


class KafkaProducer:
    """Kafka producer for publishing model lifecycle events."""
    
    def __init__(self, settings: Settings = None):
        """Initialize Kafka producer.
        
        Args:
            settings: Application settings (optional, will create default if not provided)
        """
        self.settings = settings or Settings()
        self.producer = None
        self._initialized = False
        
        if KAFKA_AVAILABLE:
            self._initialize_producer()
        else:
            logger.warning("Confluent Kafka not available. Events will not be published.")
    
    def _initialize_producer(self):
        """Initialize the Kafka producer."""
        try:
            kafka_config = {
                'bootstrap.servers': self.settings.KAFKA_BOOTSTRAP_SERVERS or 'localhost:9092',
                'client.id': 'model-training-service'
            }
            
            # Add security configuration if provided
            if self.settings.KAFKA_SECURITY_PROTOCOL:
                kafka_config.update({
                    'security.protocol': self.settings.KAFKA_SECURITY_PROTOCOL,
                    'sasl.mechanisms': self.settings.KAFKA_SASL_MECHANISM or 'PLAIN',
                    'sasl.username': self.settings.KAFKA_SASL_USERNAME,
                    'sasl.password': self.settings.KAFKA_SASL_PASSWORD
                })
            
            self.producer = Producer(kafka_config)
            self._initialized = True
            logger.info("Kafka producer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
            self.producer = None
            self._initialized = False
    
    def _delivery_callback(self, err, msg):
        """Callback for message delivery reports."""
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")
    
    def _publish_event(self, topic: str, event_data: Dict[str, Any]):
        """Publish an event to Kafka.
        
        Args:
            topic: Kafka topic to publish to
            event_data: Event data to publish
        """
        if not self._initialized or not self.producer:
            logger.warning(f"Kafka producer not available. Event not published to {topic}: {event_data}")
            return
        
        try:
            # Add timestamp if not present
            if 'timestamp' not in event_data:
                event_data['timestamp'] = datetime.utcnow().isoformat()
            
            # Serialize event data
            value = json.dumps(event_data).encode('utf-8')
            
            # Produce message
            self.producer.produce(
                topic=topic,
                value=value,
                callback=self._delivery_callback
            )
            
            # Trigger delivery reports
            self.producer.poll(0)
            
            logger.debug(f"Event published to {topic}: {event_data.get('event_type', 'unknown')}")
        except Exception as e:
            logger.error(f"Failed to publish event to {topic}: {e}")
    
    def publish_training_requested(self, model_id: str, training_job_id: str, 
                                 training_config: Dict[str, Any], requested_by: str = None):
        """Publish model training requested event.
        
        Args:
            model_id: ID of the model to train
            training_job_id: ID of the training job
            training_config: Training configuration
            requested_by: User who requested the training (optional)
        """
        event_data = {
            'event_type': 'model.training.requested.v1',
            'model_id': model_id,
            'training_job_id': training_job_id,
            'training_config': training_config,
            'requested_by': requested_by,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        topic = self.settings.KAFKA_TOPIC_MODEL_EVENTS or 'model-events'
        self._publish_event(topic, event_data)
        logger.info(f"Published model training requested event for model {model_id}")
    
    def publish_training_completed(self, model_id: str, training_job_id: str,
                                 success: bool, metrics: Dict[str, Any] = None,
                                 error_message: str = None):
        """Publish model training completed event.
        
        Args:
            model_id: ID of the model that was trained
            training_job_id: ID of the training job
            success: Whether training was successful
            metrics: Training metrics (if successful)
            error_message: Error message (if failed)
        """
        event_data = {
            'event_type': 'model.training.completed.v1',
            'model_id': model_id,
            'training_job_id': training_job_id,
            'success': success,
            'metrics': metrics or {},
            'error_message': error_message,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        topic = self.settings.KAFKA_TOPIC_MODEL_EVENTS or 'model-events'
        self._publish_event(topic, event_data)
        logger.info(f"Published model training completed event for model {model_id} (success: {success})")
    
    def publish_evaluation_requested(self, model_id: str, evaluation_id: str,
                                   evaluation_config: Dict[str, Any], requested_by: str = None):
        """Publish model evaluation requested event.
        
        Args:
            model_id: ID of the model to evaluate
            evaluation_id: ID of the evaluation job
            evaluation_config: Evaluation configuration
            requested_by: User who requested the evaluation (optional)
        """
        event_data = {
            'event_type': 'model.evaluation.requested.v1',
            'model_id': model_id,
            'evaluation_id': evaluation_id,
            'evaluation_config': evaluation_config,
            'requested_by': requested_by,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        topic = self.settings.KAFKA_TOPIC_MODEL_EVENTS or 'model-events'
        self._publish_event(topic, event_data)
        logger.info(f"Published model evaluation requested event for model {model_id}")
    
    def publish_evaluation_completed(self, model_id: str, evaluation_id: str,
                                   success: bool, metrics: Dict[str, Any] = None,
                                   error_message: str = None):
        """Publish model evaluation completed event.
        
        Args:
            model_id: ID of the model that was evaluated
            evaluation_id: ID of the evaluation job
            success: Whether evaluation was successful
            metrics: Evaluation metrics (if successful)
            error_message: Error message (if failed)
        """
        event_data = {
            'event_type': 'model.evaluation.completed.v1',
            'model_id': model_id,
            'evaluation_id': evaluation_id,
            'success': success,
            'metrics': metrics or {},
            'error_message': error_message,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        topic = self.settings.KAFKA_TOPIC_MODEL_EVENTS or 'model-events'
        self._publish_event(topic, event_data)
        logger.info(f"Published model evaluation completed event for model {model_id} (success: {success})")
    
    def flush(self, timeout: float = 10.0):
        """Flush any pending messages.
        
        Args:
            timeout: Maximum time to wait for flushing (seconds)
        """
        if self.producer:
            self.producer.flush(timeout)
    
    def close(self):
        """Close the producer and cleanup resources."""
        if self.producer:
            self.flush()
            self.producer = None
            self._initialized = False
            logger.info("Kafka producer closed")

    def publish_model_created(self, model_id: str, model_data: dict, created_by: str = None):
        """Publish model created event."""
        event_data = {
            'event_type': 'model.created.v1',
            'model_id': model_id,
            'model_data': model_data,
            'created_by': created_by,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        topic = self.settings.KAFKA_TOPIC_MODEL_EVENTS or 'model-events'
        self._publish_event(topic, event_data)
        logger.info(f"Published model created event for model {model_id}")

    def publish_model_updated(self, model_id: str, changes: dict, updated_by: str = None):
        """Publish model updated event."""
        event_data = {
            'event_type': 'model.updated.v1',
            'model_id': model_id,
            'changes': changes,
            'updated_by': updated_by,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        topic = self.settings.KAFKA_TOPIC_MODEL_EVENTS or 'model-events'
        self._publish_event(topic, event_data)
        logger.info(f"Published model updated event for model {model_id}")

    def publish_model_deleted(self, model_id: str):
        """Publish model deleted event."""
        event_data = {
            'event_type': 'model.deleted.v1',
            'model_id': model_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        topic = self.settings.KAFKA_TOPIC_MODEL_EVENTS or 'model-events'
        self._publish_event(topic, event_data)
        logger.info(f"Published model deleted event for model {model_id}")

    def publish_model_deployed(self, model_id: str, deployed_by: str = None):
        """Publish model deployed event."""
        event_data = {
            'event_type': 'model.deployed.v1',
            'model_id': model_id,
            'deployed_by': deployed_by,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        topic = self.settings.KAFKA_TOPIC_MODEL_EVENTS or 'model-events'
        self._publish_event(topic, event_data)
        logger.info(f"Published model deployed event for model {model_id}")

    def publish_model_retired(self, model_id: str, retired_by: str = None):
        """Publish model retired event."""
        event_data = {
            'event_type': 'model.retired.v1',
            'model_id': model_id,
            'retired_by': retired_by,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        topic = self.settings.KAFKA_TOPIC_MODEL_EVENTS or 'model-events'
        self._publish_event(topic, event_data)
        logger.info(f"Published model retired event for model {model_id}")
