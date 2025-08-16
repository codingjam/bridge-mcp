"""Rate limiting exceptions."""

from typing import Optional


class RateLimitError(Exception):
    """Base exception for rate limiting errors."""
    
    def __init__(self, message: str, error_code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "rate_limit_error"


class RateLimitExceededError(RateLimitError):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, message: str, retry_after: int, key: Optional[str] = None):
        super().__init__(message, "rate_limit_exceeded")
        self.retry_after = retry_after
        self.key = key


class RateLimitConfigurationError(RateLimitError):
    """Exception raised when rate limiting configuration is invalid."""
    
    def __init__(self, message: str, config_error: Optional[str] = None):
        super().__init__(message, "rate_limit_configuration_error")
        self.config_error = config_error


class RateLimitBackendError(RateLimitError):
    """Exception raised when rate limiting backend fails."""
    
    def __init__(self, message: str, backend_error: Optional[str] = None):
        super().__init__(message, "rate_limit_backend_error")
        self.backend_error = backend_error
