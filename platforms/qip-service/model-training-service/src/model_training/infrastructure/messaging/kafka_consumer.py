"""Kafka consumer with OpenTelemetry tracing."""

import json
import logging
from typing import Callable, Dict, Any
from kafka import KafkaConsumer
from opentelemetry import trace
from opentelemetry.trace import SpanKind
from opentelemetry.propagators import get_global_textmap
from opentelemetry.context import attach, set_value, set_parent

from model_training.config import settings
from model_training.config_dir.tracing import setup_tracing

logger = logging.getLogger(__name__)


class KafkaConsumerWrapper:
    """Kafka consumer wrapper with OpenTelemetry tracing."""

    def __init__(self, topics: list, group_id: str = "model-training-service"):
        """Initialize Kafka consumer.

        Args:
            topics: List of topics to subscribe to
            group_id: Consumer group ID
        """
        self.consumer = KafkaConsumer(
            *topics,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            group_id=group_id,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
        )
        self.tracer = trace.get_tracer(__name__)
        logger.info(f"Kafka consumer initialized for topics: {topics}")

    def consume_messages(self, message_handler: Callable[[Dict[str, Any]], None]) -> None:
        """Consume messages from Kafka topics with tracing.

        Args:
            message_handler: Function to handle incoming messages
        """
        try:
            for message in self.consumer:
                # Extract trace context from message headers
                ctx = None
                if message.headers:
                    try:
                        headers_dict = {k: v.decode('utf-8') if isinstance(v, bytes) else v
                                      for k, v in message.headers}
                        propagator = get_global_textmap()
                        ctx = propagator.extract(carrier=headers_dict)
                    except Exception as e:
                        logger.warning(f"Failed to extract trace context from headers: {e}")
                        ctx = None

                # Create a span for each message with extracted context as parent
                with self.tracer.start_as_current_span(
                    f"consume_message_{message.topic}",
                    kind=SpanKind.CONSUMER,
                    context=ctx
                ) as span:
                    # Add message attributes
                    span.set_attribute("messaging.system", "kafka")
                    span.set_attribute("messaging.destination", message.topic)
                    span.set_attribute("messaging.destination_kind", "topic")
                    span.set_attribute("messaging.kafka.partition", message.partition)
                    span.set_attribute("messaging.kafka.offset", message.offset)
                    span.set_attribute("messaging.kafka.key", str(message.key) if message.key else "")

                    # Add message payload attributes (if not too large)
                    if message.value:
                        if isinstance(message.value, dict):
                            if "id" in message.value:
                                span.set_attribute("messaging.message_id", str(message.value["id"]))
                            if "name" in message.value:
                                span.set_attribute("messaging.message_payload", str(message.value["name"])[:100])
                            if "model_id" in message.value:
                                span.set_attribute("messaging.message.model_id", str(message.value["model_id"]))

                    # Process the message
                    try:
                        message_handler(message.value)
                        # Mark message as processed successfully
                        span.set_attribute("messaging.message.processed", True)
                    except Exception as e:
                        # Record error in span
                        span.set_attribute("messaging.message.processed", False)
                        span.set_attribute("messaging.message.error", str(e))
                        logger.error(f"Error processing message from topic {message.topic}: {e}")
                        # Re-raise to allow the consumer to handle the error appropriately
                        raise

        except Exception as e:
            logger.error(f"Error in Kafka consumer: {e}")
            raise
        finally:
            self.close()

    def close(self):
        """Close the Kafka consumer."""
        self.consumer.close()