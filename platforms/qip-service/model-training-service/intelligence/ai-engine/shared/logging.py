"""
Logging configuration for AI Engine services
"""
import logging
import sys
from typing import Any, Dict

import structlog
from pythonjsonlogger import jsonlogger


def setup_logging(log_level: str = "INFO") -> None:
    """Configure structured logging for the application."""

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.JSONRenderer() if log_level != "DEBUG" else
            dev_console_renderer,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )


def dev_console_renderer(logger: Any, name: str, event_dict: Dict[str, Any]) -> str:
    """Format output for console during development."""
    return f"[{event_dict.get('level', '').upper()}] {event_dict.get('event', '')}"


def get_logger(name: str):
    """Get a structured logger instance."""
    return structlog.get_logger(name)