"""Example service client demonstrating usage of resilient HTTP client."""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel

from model_training.infrastructure.http.client import ResilientHTTPClient, create_resilient_http_client
from model_training.config import settings


class UserModel(BaseModel):
    """Example user model."""
    id: str
    username: str
    email: str
    is_active: bool = True


class UserServiceClient:
    """Example client for a user service."""

    def __init__(self):
        """Initialize the user service client."""
        self.client = create_resilient_http_client(
            service_name="user-service",
            base_url=getattr(settings, "USER_SERVICE_URL", "http://localhost:8001"),
        )

    async def get_user(self, user_id: str) -> UserModel:
        """Get a user by ID.

        Args:
            user_id: The user ID

        Returns:
            User model

        Raises:
            HTTPException: If user not found or service unavailable
        """
        try:
            response = await self.client.get(f"/users/{user_id}")
            return UserModel(**response.json())
        except Exception as e:
            # Log and re-raise - in a real app you might want to wrap this
            # in a domain-specific exception
            raise

    async def list_users(self, skip: int = 0, limit: int = 100) -> List[UserModel]:
        """List users with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of user models
        """
        try:
            response = await self.client.get(
                "/users/",
                params={"skip": skip, "limit": limit}
            )
            users_data = response.json()
            return [UserModel(**user) for user in users_data]
        except Exception as e:
            raise

    async def close(self):
        """Close the HTTP client."""
        await self.client.close()

    def get_circuit_state(self):
        """Get the circuit breaker state for monitoring."""
        return self.client.get_circuit_state()


# Example of how to use the client context manager for short-lived usage
async def get_user_example(user_id: str) -> Optional[UserModel]:
    """Example function showing context manager usage.

    Args:
        user_id: The user ID to fetch

    Returns:
        User model if found, None otherwise
    """
    async with ResilientHTTPClientContext(
        service_name="user-service",
        base_url=getattr(settings, "USER_SERVICE_URL", "http://localhost:8001")
    ) as client:
        try:
            response = await client.get(f"/users/{user_id}")
            return UserModel(**response.json())
        except Exception:
            return None