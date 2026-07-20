"""Kafka producer with OpenTelemetry tracing."""

import json
from typing import Dict, Any
from kafka import KafkaProducer
from opentelemetry import trace
from opentelemetry.trace import SpanKind
from opentelemetry.propagators import get_global_textmap

from model_training.config import settings
from model_training.config_dir.tracing import setup_tracing


class KafkaProducerWrapper:
    """Kafka producer wrapper with OpenTelemetry tracing."""

    def __init__(self):
        """Initialize Kafka producer."""
        self.producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
        )
        self.tracer = trace.get_tracer(__name__)

    def send_model_training_request(self, model_data: dict) -> None:
        """Send model training request to Kafka topic with tracing.

        Args:
            model_data: Model data to send
        """
        with self.tracer.start_as_current_span(
            "send_model_training_request",
            kind=SpanKind.PRODUCER
        ) as span:
            # Add message attributes
            span.set_attribute("messaging.system", "kafka")
            span.set_attribute("messaging.destination", settings.MODEL_TRAINING_TOPIC)
            span.set_attribute("messaging.destination_kind", "topic")

            # Add message payload attributes (if not too large)
            if "id" in model_data:
                span.set_attribute("messaging.message_id", str(model_data["id"]))
            if "name" in model_data:
                span.set_attribute("messaging.message_payload", str(model_data["name"])[:100])  # Truncate if too long

            # Prepare headers with trace context
            headers = []
            propagator = get_global_textmap()
            carrier = {}
            propagator.inject(carrier)
            for key, value in carrier.items():
                headers.append((key.encode('utf-8'), str(value).encode('utf-8')))

            # Send message
            future = self.producer.send(
                settings.MODEL_TRAINING_TOPIC,
                value=model_data,
                key=str(model_data.get("id", "")),
                headers=headers if headers else None
            )

            # Wait for confirmation
            record_metadata = future.get(timeout=10)

            # Add record metadata to span
            span.set_attribute("messaging.kafka.partition", record_metadata.partition)
            span.set_attribute("messaging.kafka.offset", record_metadata.offset)
            span.set_attribute("messaging.destination", f"{settings.MODEL_TRAINING_TOPIC}:{record_metadata.partition}")

    def send_model_trained_event(self, model_data: dict) -> None:
        """Send model trained event to Kafka topic with tracing.

        Args:
            model_data: Model data to send
        """
        with self.tracer.start_as_current_span(
            "send_model_trained_event",
            kind=SpanKind.PRODUCER
        ) as span:
            # Add message attributes
            span.set_attribute("messaging.system", "kafka")
            span.set_attribute("messaging.destination", settings.MODEL_TRAINED_TOPIC)
            span.set_attribute("messaging.destination_kind", "topic")

            # Add message payload attributes
            if "id" in model_data:
                span.set_attribute("messaging.message_id", str(model_data["id"]))
            if "name" in model_data:
                span.set_attribute("messaging.message_payload", str(model_data["name"])[:100])

            # Prepare headers with trace context
            headers = []
            propagator = get_global_textmap()
            carrier = {}
            propagator.inject(carrier)
            for key, value in carrier.items():
                headers.append((key.encode('utf-8'), str(value).encode('utf-8')))

            # Send message
            future = self.producer.send(
                settings.MODEL_TRAINED_TOPIC,
                value=model_data,
                key=str(model_data.get("id", "")),
                headers=headers if headers else None
            )

            # Wait for confirmation
            record_metadata = future.get(timeout=10)

            # Add record metadata to span
            span.set_attribute("messaging.kafka.partition", record_metadata.partition)
            span.set_attribute("messaging.kafka.offset", record_metadata.offset)
            span.set_attribute("messaging.destination", f"{settings.MODEL_TRAINED_TOPIC}:{record_metadata.partition}")

    def send_model_evaluation_request(self, evaluation_data: dict) -> None:
        """Send model evaluation request to Kafka topic with tracing.

        Args:
            evaluation_data: Evaluation data to send
        """
        with self.tracer.start_as_current_span(
            "send_model_evaluation_request",
            kind=SpanKind.PRODUCER
        ) as span:
            # Add message attributes
            span.set_attribute("messaging.system", "kafka")
            span.set_attribute("messaging.destination", settings.MODEL_EVALUATION_TOPIC)
            span.set_attribute("messaging.destination_kind", "topic")

            # Add message payload attributes
            if "id" in evaluation_data:
                span.set_attribute("messaging.message_id", str(evaluation_data["id"]))
            if "model_id" in evaluation_data:
                span.set_attribute("messaging.message.model_id", str(evaluation_data["model_id"]))

            # Prepare headers with trace context
            headers = []
            propagator = get_global_textmap()
            carrier = {}
            propagator.inject(carrier)
            for key, value in carrier.items():
                headers.append((key.encode('utf-8'), str(value).encode('utf-8')))

            # Send message
            future = self.producer.send(
                settings.MODEL_EVALUATION_TOPIC,
                value=evaluation_data,
                key=str(evaluation_data.get("id", "")),
                headers=headers if headers else None
            )

            # Wait for confirmation
            record_metadata = future.get(timeout=10)

            # Add record metadata to span
            span.set_attribute("messaging.kafka.partition", record_metadata.partition)
            span.set_attribute("messaging.kafka.offset", record_metadata.offset)
            span.set_attribute("messaging.destination", f"{settings.MODEL_EVALUATION_TOPIC}:{record_metadata.partition}")

    def close(self):
        """Close the Kafka producer."""
        self.producer.close()