"""Messaging infrastructure for the Model Training Service."""

from .kafka_producer import KafkaProducer
from .kafka_consumer import KafkaConsumer

__all__ = ["KafkaProducer", "KafkaConsumer"]
