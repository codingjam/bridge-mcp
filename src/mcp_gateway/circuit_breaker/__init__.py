"""
Circuit Breaker module for MCP Gateway.

This module provides circuit breaker pattern implementation to protect against
cascading failures and provide resilient downstream service communication.

The circuit breaker pattern is a design pattern used to prevent a network or service 
failure from cascading to other services. It acts as a safety switch that:
- Monitors failure rates
- Blocks requests when thresholds are exceeded (OPEN state)
- Automatically recovers by testing with probe requests (HALF_OPEN state)
- Returns to normal operation when service recovers (CLOSED state)

Key Features:
- Per-server circuit breakers for isolated failure handling
- Configurable failure thresholds and timeouts
- Exponential backoff for recovery attempts
- Thread-safe async implementation
- Comprehensive metrics and observability
- Smart error categorization (trip vs ignore)

Example Usage:
    from mcp_gateway.circuit_breaker import CircuitBreakerManager
    
    # Initialize manager with default config
    manager = CircuitBreakerManager()
    
    # Execute protected operation
    try:
        result = await manager.check_and_call(
            "filesystem-server",
            mcp_operation,
            *args, **kwargs
        )
    except CircuitBreakerOpenError as e:
        # Handle circuit breaker open state
        logger.warning(f"Circuit breaker open: {e}")
        return {"error": "service_unavailable", "retry_after": e.cooldown_remaining}
"""

from .breaker import CircuitBreaker, CircuitBreakerState, CircuitBreakerConfig
from .manager import CircuitBreakerManager
from .exceptions import CircuitBreakerOpenError, CircuitBreakerError

__all__ = [
    "CircuitBreaker",
    "CircuitBreakerState", 
    "CircuitBreakerConfig",
    "CircuitBreakerManager",
    "CircuitBreakerOpenError",
    "CircuitBreakerError"
]

__version__ = "1.0.0"
