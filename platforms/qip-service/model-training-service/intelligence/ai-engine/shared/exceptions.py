"""
Custom exceptions for AI Engine services
"""


class AIEngineException(Exception):
    """Base exception for AI Engine."""

    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class DatabaseError(AIEngineException):
    """Database related errors."""
    pass


class ValidationError(AIEngineException):
    """Data validation errors."""
    pass


class NotFoundError(AIEngineException):
    """Resource not found errors."""
    pass


class ConfigurationError(AIEngineException):
    """Configuration related errors."""
    pass


class ExternalServiceError(AIEngineException):
    """External service communication errors."""
    pass