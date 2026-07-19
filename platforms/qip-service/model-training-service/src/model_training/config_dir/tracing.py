"""OpenTelemetry tracing configuration."""

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes

from model_training.config import settings


def setup_tracing(app=None):
    """Set up OpenTelemetry tracing.

    Args:
        app: FastAPI application instance (optional)
    """
    # If Jaeger is not enabled, return early
    if not getattr(settings, 'JAEGER_ENABLED', False):
        return trace.get_tracer(__name__)

    # Create resource attributes for the service
    resource = Resource(attributes={
        ResourceAttributes.SERVICE_NAME: settings.APP_NAME,
        ResourceAttributes.SERVICE_VERSION: settings.VERSION,
        "deployment.environment": "development" if settings.DEBUG else "production"
    })

    # Set up tracer provider
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)

    # Configure Jaeger exporter
    jaeger_exporter = JaegerExporter(
        agent_host_name=getattr(settings, 'JAEGER_HOST', 'localhost'),
        agent_port=getattr(settings, 'JAEGER_PORT', 6831),
    )
    span_processor = BatchSpanProcessor(jaeger_exporter)
    tracer_provider.add_span_processor(span_processor)

    # Instrument FastAPI if app is provided
    if app is not None:
        FastAPIInstrumentor.instrument_app(app)

    # Instrument SQLAlchemy
    SQLAlchemyInstrumentor().instrument()

    return trace.get_tracer(__name__)
