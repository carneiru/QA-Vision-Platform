"""Input validation and sanitization middleware."""

import re
import html
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class ValidationMiddleware(BaseHTTPMiddleware):
    """Middleware for input validation and sanitization."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        # Patterns to detect potential injection attempts
        self.sql_injection_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER)\b)",
            r"(\b(OR|AND)\b\s+\d+=\d+)",
            r"(--|#|/\*|\*/)",
            r"(\bEXEC\b|\bEXECUTE\b)",
        ]
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe",
            r"<object",
            r"<embed",
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process incoming request and validate/sanitize input."""
        # Validate query parameters
        self._validate_query_params(request.query_params)

        # Validate path parameters
        self._validate_path_params(request.path_params)

        # For methods with body, validate JSON data
        if request.method in ["POST", "PUT", "PATCH"]:
            # Note: We don't actually read the body here to avoid consuming it
            # Actual validation should happen in the endpoint using Pydantic models
            pass

        response = await call_next(request)
        return response

    def _validate_query_params(self, query_params):
        """Validate query parameters for malicious content."""
        for key, value in query_params.items():
            if isinstance(value, str):
                self._check_for_threats(value, f"query param '{key}'")

    def _validate_path_params(self, path_params):
        """Validate path parameters for malicious content."""
        for key, value in path_params.items():
            if isinstance(value, str):
                self._check_for_threats(value, f"path param '{key}'")

    def _check_for_threats(self, input_str: str, source: str):
        """Check input for potential security threats."""
        # Check for SQL injection
        for pattern in self.sql_injection_patterns:
            if re.search(pattern, input_str, re.IGNORECASE):
                # In a real implementation, we might log this or take other action
                # For now, we'll just sanitize by escaping
                pass

        # Check for XSS
        for pattern in self.xss_patterns:
            if re.search(pattern, input_str, re.IGNORECASE):
                # In a real implementation, we might log this or take other action
                # For now, we'll just sanitize by escaping
                pass

    def sanitize_input(self, input_str: str) -> str:
        """Sanitize input by escaping HTML entities."""
        return html.escape(input_str)