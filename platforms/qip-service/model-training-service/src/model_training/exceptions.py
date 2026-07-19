"""Custom exceptions for Model Training Service."""


class AuthenticationError(Exception):
    """Authentication error."""


class AuthorizationError(Exception):
    """Authorization error."""


class ValidationError(Exception):
    """Validation error."""