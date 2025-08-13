"""Logging configuration for MCP Gateway."""

import logging
import logging.config
import sys
from typing import Dict, Any, Union

import structlog

from mcp_gateway.core.config import settings


def setup_logging() -> None:
    """Setup structured logging for the application."""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            _get_renderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper()),
    )


def _get_renderer() -> Union[structlog.processors.JSONRenderer, structlog.dev.ConsoleRenderer]:
    """Get the appropriate log renderer based on configuration."""
    if settings.LOG_FORMAT.lower() == "json":
        return structlog.processors.JSONRenderer()
    else:
        return structlog.dev.ConsoleRenderer(colors=True)


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
