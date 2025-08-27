"""
Circuit Breaker exceptions for MCP Gateway.

This module defines custom exceptions used by the circuit breaker system
to handle various failure scenarios and provide meaningful error information.
"""

from typing import Optional, Dict, Any


class CircuitBreakerError(Exception):
    """
    Base exception class for circuit breaker related errors.
    
    This is the parent class for all circuit breaker exceptions and provides
    common functionality for error handling and debugging.
    """
    
    def __init__(self, message: str, server_key: Optional[str] = None, 
                 context: Optional[Dict[str, Any]] = None):
        """
        Initialize circuit breaker error.
        
        Args:
            message: Human-readable error description
            server_key: Identifier of the server/service that failed
            context: Additional context information for debugging
        """
        super().__init__(message)
        self.server_key = server_key
        self.context = context or {}
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert exception to dictionary for API responses and logging.
        
        Returns:
            Dictionary representation of the error
        """
        return {
            "error_type": self.__class__.__name__,
            "message": str(self),
            "server_key": self.server_key,
            "context": self.context
        }


class CircuitBreakerOpenError(CircuitBreakerError):
    """
    Raised when circuit breaker is open and blocking calls.
    
    This exception indicates that the circuit breaker is currently in the OPEN
    state due to too many recent failures. Clients should implement retry logic
    with appropriate backoff based on the cooldown information provided.
    
    Attributes:
        cooldown_remaining: Seconds until circuit breaker may transition to HALF_OPEN
        failure_rate: Current failure rate that triggered the open state
        total_failures: Total number of failures recorded
        last_failure_time: Timestamp of the most recent failure
    """
    
    def __init__(self, 
                 message: str, 
                 server_key: Optional[str] = None,
                 cooldown_remaining: float = 0,
                 failure_rate: float = 0,
                 total_failures: int = 0,
                 last_failure_time: Optional[float] = None):
        """
        Initialize circuit breaker open error.
        
        Args:
            message: Human-readable error description
            server_key: Identifier of the failing server/service
            cooldown_remaining: Seconds remaining until potential recovery
            failure_rate: Current failure percentage (0.0 to 1.0)
            total_failures: Total number of recorded failures
            last_failure_time: Unix timestamp of last failure
        """
        super().__init__(message, server_key)
        self.cooldown_remaining = cooldown_remaining
        self.failure_rate = failure_rate
        self.total_failures = total_failures
        self.last_failure_time = last_failure_time
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary with circuit breaker specific information.
        
        Returns:
            Extended dictionary with circuit breaker state details
        """
        base_dict = super().to_dict()
        base_dict.update({
            "error": "circuit_breaker_open",
            "cooldown_remaining_seconds": self.cooldown_remaining,
            "failure_rate": self.failure_rate,
            "total_failures": self.total_failures,
            "last_failure_time": self.last_failure_time,
            "retry_after_ms": int(self.cooldown_remaining * 1000),
            "can_retry": True,
            "recommended_action": "wait_and_retry"
        })
        return base_dict
    
    def get_http_status_code(self) -> int:
        """
        Get appropriate HTTP status code for this error.
        
        Returns:
            503 Service Unavailable - standard for circuit breaker open
        """
        return 503
    
    def get_retry_after_header(self) -> str:
        """
        Get value for HTTP Retry-After header.
        
        Returns:
            String representation of seconds to wait before retry
        """
        return str(int(self.cooldown_remaining))


class CircuitBreakerConfigurationError(CircuitBreakerError):
    """
    Raised when circuit breaker configuration is invalid.
    
    This exception indicates that the circuit breaker configuration contains
    invalid values or incompatible settings that prevent proper operation.
    """
    
    def __init__(self, message: str, config_field: Optional[str] = None,
                 provided_value: Optional[Any] = None):
        """
        Initialize configuration error.
        
        Args:
            message: Description of the configuration issue
            config_field: Name of the problematic configuration field
            provided_value: The invalid value that was provided
        """
        super().__init__(message)
        self.config_field = config_field
        self.provided_value = provided_value
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with configuration details."""
        base_dict = super().to_dict()
        base_dict.update({
            "error": "circuit_breaker_configuration_error",
            "config_field": self.config_field,
            "provided_value": self.provided_value
        })
        return base_dict


class CircuitBreakerTimeoutError(CircuitBreakerError):
    """
    Raised when an operation times out within the circuit breaker.
    
    This is different from CircuitBreakerOpenError - this indicates that
    the operation itself timed out, which may contribute to opening the circuit.
    """
    
    def __init__(self, message: str, server_key: Optional[str] = None,
                 timeout_seconds: Optional[float] = None):
        """
        Initialize timeout error.
        
        Args:
            message: Description of the timeout
            server_key: Identifier of the server that timed out
            timeout_seconds: Duration of the timeout that occurred
        """
        super().__init__(message, server_key)
        self.timeout_seconds = timeout_seconds
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with timeout details."""
        base_dict = super().to_dict()
        base_dict.update({
            "error": "circuit_breaker_timeout",
            "timeout_seconds": self.timeout_seconds
        })
        return base_dict


class CircuitBreakerOperationError(CircuitBreakerError):
    """
    Raised when a circuit breaker operation fails due to internal errors.
    
    This exception wraps other exceptions that occur during circuit breaker
    operations, providing additional context about the failure.
    """
    
    def __init__(self, message: str, server_key: Optional[str] = None,
                 original_exception: Optional[Exception] = None,
                 operation: Optional[str] = None):
        """
        Initialize operation error.
        
        Args:
            message: Description of the operation failure
            server_key: Identifier of the affected server
            original_exception: The original exception that was wrapped
            operation: Name of the operation that failed
        """
        super().__init__(message, server_key)
        self.original_exception = original_exception
        self.operation = operation
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with operation details."""
        base_dict = super().to_dict()
        base_dict.update({
            "error": "circuit_breaker_operation_error",
            "operation": self.operation,
            "original_error": str(self.original_exception) if self.original_exception else None,
            "original_error_type": type(self.original_exception).__name__ if self.original_exception else None
        })
        return base_dict
