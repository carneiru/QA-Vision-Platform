"""Idempotency middleware for preventing duplicate requests."""

import json
import uuid
from typing import Optional
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis

from model_training.config import settings
from model_training.config_dir.logging_config import get_logger

logger = get_logger(__name__)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Middleware to provide idempotency for POST, PUT, and PATCH requests."""

    def __init__(self, app, exclude_paths: list = None):
        """Initialize the idempotency middleware.

        Args:
            app: The ASGI application
            exclude_paths: List of paths to exclude from idempotency checks
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/docs", "/redoc", "/openapi.json", "/health", "/metrics"]
        self.redis_client = None
        self._initialize_redis()

    def _initialize_redis(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
        except Exception as e:
            logger.warning(f"Failed to connect to Redis for idempotency: {e}")
            self.redis_client = None

    async def dispatch(self, request: Request, call_next):
        """Process the request and apply idempotency checks.

        Args:
            request: The incoming request
            call_next: The next middleware/endpoint in the chain

        Returns:
            The response from the endpoint
        """
        # Skip idempotency for excluded paths or non-idempotent methods
        if (request.url.path in self.exclude_paths or
            request.method not in ["POST", "PUT", "PATCH"] or
            self.redis_client is None):
            return await call_next(request)

        # Get idempotency key from header
        idempotency_key = request.headers.get("Idempotency-Key")

        # If no idempotency key, proceed normally
        if not idempotency_key:
            return await call_next(request)

        # Validate idempotency key format
        try:
            # Validate that it's a valid UUID
            uuid.UUID(idempotency_key)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid Idempotency-Key format. Must be a valid UUID."
            )

        # Check if we have a cached response for this key
        cache_key = f"idempotency:{idempotency_key}:{request.method}:{request.url.path}"
        cached_response = await self.redis_client.get(cache_key)

        if cached_response:
            # Return cached response
            try:
                response_data = json.loads(cached_response)
                return Response(
                    content=response_data["body"],
                    status_code=response_data["status_code"],
                    headers=response_data["headers"]
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse cached response for key {idempotency_key}: {e}")
                # If cache is corrupted, proceed with normal processing

        # Process the request normally
        response = await call_next(request)

        # Cache the successful response (only for 2xx status codes)
        if 200 <= response.status_code < 300:
            try:
                # Collect the response body
                response_body = b""
                async for chunk in response.body_iterator:
                    response_body += chunk

                # Prepare response data for caching
                response_data = {
                    "body": response_body.decode(),
                    "status_code": response.status_code,
                    "headers": dict(response.headers)
                }

                # Cache the response with TTL (24 hours)
                await self.redis_client.setex(
                    cache_key,
                    86400,  # 24 hours in seconds
                    json.dumps(response_data)
                )

                # Return a new response with the collected body
                return Response(
                    content=response_data["body"],
                    status_code=response_data["status_code"],
                    headers=response_data["headers"]
                )
            except Exception as e:
                logger.warning(f"Failed to cache response for key {idempotency_key}: {e}")

        return response