"""Kafka consumer for consuming events from other services."""

import json
import logging
from typing import Callable, Dict, Any
from confluent_kafka import Consumer, KafkaError

from config.settings import Settings

logger = logging.getLogger(__name__)


class KafkaConsumer:
    """Kafka consumer for processing events from other services."""
    
    def __init__(self, settings: Settings = None, group_id: str = "model-training-service"):
        """Initialize Kafka consumer.
        
        Args:
            settings: Application settings (optional, will create default if not provided)
            group_id: Consumer group ID
        """
        self.settings = settings or Settings()
        self.consumer = None
        self.running = False
        self.handlers = {}  # event_type -> handler function
        
        self._initialize_consumer(group_id)
    
    def _initialize_consumer(self, group_id: str):
        """Initialize the Kafka consumer."""
        try:
            consumer_config = {
                'bootstrap.servers': self.settings.KAFKA_BOOTSTRAP_SERVERS or 'localhost:9092',
                'group.id': group_id,
                'auto.offset.reset': 'earliest',
                'enable.auto.commit': True
            }
            
            # Add security configuration if provided
            if self.settings.KAFKA_SECURITY_PROTOCOL:
                consumer_config.update({
                    'security.protocol': self.settings.KAFKA_SECURITY_PROTOCOL,
                    'sasl.mechanisms': self.settings.KAFKA_SASL_MECHANISM or 'PLAIN',
                    'sasl.username': self.settings.KAFKA_SASL_USERNAME,
                    'sasl.password': self.settings.KAFKA_SASL_PASSWORD
                })
            
            self.consumer = Consumer(consumer_config)
            logger.info("Kafka consumer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka consumer: {e}")
            self.consumer = None
    
    def subscribe(self, topics: list):
        """Subscribe to Kafka topics.
        
        Args:
            topics: List of topics to subscribe to
        """
        if not self.consumer:
            logger.error("Cannot subscribe: Kafka consumer not initialized")
            return
        
        try:
            self.consumer.subscribe(topics)
            logger.info(f"Subscribed to topics: {topics}")
        except Exception as e:
            logger.error(f"Failed to subscribe to topics {topics}: {e}")
    
    def register_handler(self, event_type: str, handler: Callable[[Dict[str, Any]], None]):
        """Register a handler for a specific event type.
        
        Args:
            event_type: The event type to handle
            handler: Function to call when event is received
        """
        self.handlers[event_type] = handler
        logger.debug(f"Registered handler for event type: {event_type}")
    
    def process_message(self, msg):
        """Process a single message.
        
        Args:
            msg: Kafka message object
        """
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                # End of partition event
                return
            else:
                logger.error(f"Consumer error: {msg.error()}")
                return
        
        try:
            # Parse message
            message_value = msg.value().decode('utf-8')
            event_data = json.loads(message_value)
            
            event_type = event_data.get('event_type')
            if not event_type:
                logger.warning("Received message without event_type")
                return
            
            # Call handler if registered
            if event_type in self.handlers:
                try:
                    self.handlers[event_type](event_data)
                except Exception as e:
                    logger.error(f"Error in handler for event {event_type}: {e}")
            else:
                logger.debug(f"No handler registered for event type: {event_type}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def start_consuming(self, timeout: float = 1.0):
        """Start consuming messages.
        
        Args:
            timeout: Poll timeout in seconds
        """
        if not self.consumer:
            logger.error("Cannot start consuming: Kafka consumer not initialized")
            return
        
        self.running = True
        logger.info("Starting to consume messages...")
        
        try:
            while self.running:
                msg = self.consumer.poll(timeout=timeout)
                if msg is None:
                    continue
                self.process_message(msg)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        except Exception as e:
            logger.error(f"Error in consumer loop: {e}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop consuming messages."""
        self.running = False
        if self.consumer:
            self.consumer.close()
            logger.info("Kafka consumer stopped")
