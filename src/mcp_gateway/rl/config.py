"""Rate limiting configuration and dependency injection."""

from typing import Optional
from pydantic import BaseModel, Field

from mcp_gateway.core.config import get_settings
from .backend import LimiterBackend, MemoryBackend
from .limiter import RatePolicy, RateLimiter


class RateLimitConfig(BaseModel):
    """Rate limiting configuration model."""
    
    enabled: bool = Field(default=True, description="Enable rate limiting")
    default_limit: int = Field(default=5, ge=1, le=1000, description="Default requests per window")
    default_window: int = Field(default=60, ge=1, le=3600, description="Default window in seconds")
    backend: str = Field(default="memory", description="Backend type")
    redis_url: Optional[str] = Field(default=None, description="Redis URL if using Redis backend")


def get_rate_limit_config() -> RateLimitConfig:
    """Get rate limiting configuration from settings."""
    settings = get_settings()
    
    return RateLimitConfig(
        enabled=settings.ENABLE_RATE_LIMITING,
        default_limit=settings.RATE_LIMIT_DEFAULT_LIMIT,
        default_window=settings.RATE_LIMIT_DEFAULT_WINDOW,
        backend=settings.RATE_LIMIT_BACKEND,
        redis_url=settings.RATE_LIMIT_REDIS_URL
    )


def create_rate_limiter(config: Optional[RateLimitConfig] = None) -> Optional[RateLimiter]:
    """
    Create rate limiter instance based on configuration.
    
    Args:
        config: Rate limiting configuration (defaults to settings)
        
    Returns:
        RateLimiter instance or None if disabled
    """
    if config is None:
        config = get_rate_limit_config()
    
    if not config.enabled:
        return None
    
    # Create backend based on configuration
    backend: LimiterBackend
    if config.backend == "memory":
        backend = MemoryBackend()
    elif config.backend == "redis":
        # TODO: Implement Redis backend
        raise NotImplementedError("Redis backend not yet implemented")
    else:
        raise ValueError(f"Unknown rate limiting backend: {config.backend}")
    
    # Create policy
    policy = RatePolicy(
        limit=config.default_limit,
        window_seconds=config.default_window
    )
    
    return RateLimiter(backend, policy)


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> Optional[RateLimiter]:
    """Get rate limiter instance (for dependency injection)."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = create_rate_limiter()
    return _rate_limiter
