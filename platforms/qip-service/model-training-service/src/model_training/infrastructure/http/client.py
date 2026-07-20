"""Resilient HTTP client with circuit breaker, retry, and timeout capabilities."""

import asyncio
import logging
from typing import Optional, Dict, Any, Callable, TypeVar, Generic
import httpx
from pybreaker import CircuitBreaker, CircuitBreakerError, CircuitState

from model_training.config import settings
from model_training.config_dir.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class ResilientHTTPClient:
    """HTTP client with resilience patterns: circuit breaker, retry, timeout."""

    def __init__(
        self,
        service_name: str,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        expected_exception: tuple = (Exception,),
    ):
        """Initialize the resilient HTTP client.

        Args:
            service_name: Name of the service for logging and metrics
            base_url: Base URL for the service
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exceptions that count as failures
        """
        self.service_name = service_name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

        # Initialize circuit breaker
        self.circuit_breaker = CircuitBreaker(
            fail_max=failure_threshold,
            reset_timeout=recovery_timeout,
            expected_exception=expected_exception,
            name=f"{service_name}_circuit_breaker",
        )

        # HTTP client with timeout limits
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )

        logger.info(
            f"Initialized resilient HTTP client for {service_name}",
            extra={
                "service": service_name,
                "base_url": base_url,
                "timeout": timeout,
                "max_retries": max_retries,
            },
        )

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> httpx.Response:
        """Make an HTTP request with resilience patterns.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL (relative to base_url)
            params: Query parameters
            json: JSON body
            data: Form data
            headers: Request headers
            **kwargs: Additional arguments passed to httpx

        Returns:
            HTTP response

        Raises:
            httpx.HTTPStatusError: For HTTP error status codes
            CircuitBreakerError: When circuit breaker is open
            httpx.RequestError: For network-related errors
        """
        full_url = url if url.startswith("http") else f"{self.base_url}/{url.lstrip('/')}"

        async def _make_request() -> httpx.Response:
            """Make the actual HTTP request with retry logic."""
            last_exception = None

            for attempt in range(self.max_retries + 1):
                try:
                    response = await self.client.request(
                        method=method,
                        url=url,
                        params=params,
                        json=json,
                        data=data,
                        headers=headers,
                        **kwargs,
                    )

                    # Raise for status to catch HTTP errors
                    response.raise_for_status()

                    # Success - return response
                    if attempt > 0:
                        logger.info(
                            f"Request succeeded after {attempt} retries",
                            extra={
                                "service": self.service_name,
                                "method": method,
                                "url": url,
                                "attempt": attempt + 1,
                            },
                        )

                    return response

                except (httpx.RequestError, httpx.HTTPStatusError) as e:
                    last_exception = e

                    # If this was the last attempt, don't retry
                    if attempt == self.max_retries:
                        break

                    # Calculate delay with exponential backoff and jitter
                    delay = (2 ** attempt) + (0.1 * attempt)  # Exponential backoff
                    jitter = 0.1 * delay  # 10% jitter
                    total_delay = delay + (jitter * (2 * hash(str(id(e))) % 1 - 0.5))  # Random jitter

                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{self.max_retries + 1}), retrying in {total_delay:.2f}s: {str(e)}",
                        extra={
                            "service": self.service_name,
                            "method": method,
                            "url": url,
                            "attempt": attempt + 1,
                            "error": str(e),
                        },
                    )

                    await asyncio.sleep(total_delay)

            # If we get here, all retries failed
            raise last_exception

        try:
            # Execute request through circuit breaker
            response = await self.circuit_breaker.call_async(_make_request)
            return response
        except CircuitBreakerError:
            logger.error(
                f"Circuit breaker OPEN for {self.service_name}",
                extra={
                    "service": self.service_name,
                    "method": method,
                    "url": url,
                },
            )
            raise
        except Exception as e:
            logger.error(
                f"Request failed after all retries: {str(e)}",
                extra={
                    "service": self.service_name,
                    "method": method,
                    "url": url,
                    "error": str(e),
                },
            )
            raise

    # Convenience methods for common HTTP verbs
    async def get(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> httpx.Response:
        """GET request."""
        return await self.request("GET", url, params=params, headers=headers, **kwargs)

    async def post(
        self,
        url: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> httpx.Response:
        """POST request."""
        return await self.request("POST", url, json=json, data=data, headers=headers, **kwargs)

    async def put(
        self,
        url: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> httpx.Response:
        """PUT request."""
        return await self.request("PUT", url, json=json, data=data, headers=headers, **kwargs)

    async def patch(
        self,
        url: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> httpx.Response:
        """PATCH request."""
        return await self.request("PATCH", url, json=json, data=data, headers=headers, **kwargs)

    async def delete(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> httpx.Response:
        """DELETE request."""
        return await self.request("DELETE", url, headers=headers, **kwargs)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
        logger.info(f"Closed HTTP client for {self.service_name}")

    def get_circuit_state(self) -> str:
        """Get current circuit breaker state.

        Returns:
            String representing the circuit breaker state: 'closed', 'open', or 'half_open'
        """
        return self.circuit_breaker.current_state


# Factory function for creating resilient HTTP clients
def create_resilient_http_client(
    service_name: str,
    base_url: str,
    timeout: float = None,
    max_retries: int = None,
) -> ResilientHTTPClient:
    """Create a resilient HTTP client with configuration from settings.

    Args:
        service_name: Name of the service
        base_url: Base URL of the service
        timeout: Request timeout (uses settings if not provided)
        max_retries: Maximum retries (uses settings if not provided)

    Returns:
        Configured ResilientHTTPClient instance
    """
    timeout = timeout or getattr(settings, "HTTP_CLIENT_TIMEOUT", 30.0)
    max_retries = max_retries or getattr(settings, "HTTP_CLIENT_MAX_RETRIES", 3)

    return ResilientHTTPClient(
        service_name=service_name,
        base_url=base_url,
        timeout=timeout,
        max_retries=max_retries,
        failure_threshold=getattr(settings, "HTTP_CIRCUIT_BREAKER_FAILURE_THRESHOLD", 5),
        recovery_timeout=getattr(settings, "HTTP_CIRCUIT_BREAKER_RECOVERY_TIMEOUT", 30),
    )


# Context manager for automatic cleanup
class ResilientHTTPClientContext:
    """Context manager for automatic cleanup of ResilientHTTPClient."""

    def __init__(self, service_name: str, base_url: str, **kwargs):
        self.client = None
        self.service_name = service_name
        self.base_url = base_url
        self.kwargs = kwargs

    async def __aenter__(self) -> ResilientHTTPClient:
        self.client = create_resilient_http_client(
            self.service_name, self.base_url, **self.kwargs
        )
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.close()