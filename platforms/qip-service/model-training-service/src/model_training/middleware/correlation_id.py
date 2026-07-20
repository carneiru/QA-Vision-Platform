"""Correlation ID middleware for request tracing."""

import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation ID to requests and responses."""

    def __init__(self, app, header_name: str = "X-Request-ID"):
        """Initialize the middleware.

        Args:
            app: The FastAPI application
            header_name: The header name to use for correlation ID
        """
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and add correlation ID.

        Args:
            request: The incoming request
            call_next: The next middleware/endpoint in the chain

        Returns:
            The response with correlation ID header
        """
        # Extract correlation ID from request headers or generate a new one
        correlation_id = request.headers.get(self.header_name)
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Add correlation ID to request state for access throughout the application
        request.state.correlation_id = correlation_id

        # Process the request
        response = await call_next(request)

        # Add correlation ID to response headers
        response.headers[self.header_name] = correlation_id

        return response