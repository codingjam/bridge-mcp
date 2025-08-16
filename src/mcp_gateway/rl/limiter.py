"""Rate limiter implementation."""

from dataclasses import dataclass
from typing import Tuple, Optional

from .backend import LimiterBackend, MemoryBackend


@dataclass
class RatePolicy:
    """Rate limiting policy configuration."""
    limit: int = 5
    window_seconds: int = 60


class RateLimiter:
    """Rate limiter that uses a backend to track and enforce rate limits."""
    
    def __init__(self, backend: LimiterBackend, policy: Optional[RatePolicy] = None):
        """Initialize rate limiter with backend and policy."""
        self._backend = backend
        self._policy = policy or RatePolicy()
    
    def check_and_consume(self, key: str) -> Tuple[bool, int]:
        """
        Use backend.incr_and_get(key, policy.window_seconds).
        If count > policy.limit -> return (False, ttl_remaining)
        Else -> return (True, 0)
        """
        count, ttl_remaining = self._backend.incr_and_get(key, self._policy.window_seconds)
        
        if count > self._policy.limit:
            return False, ttl_remaining
        else:
            return True, 0


def make_default_limiter() -> RateLimiter:
    """Factory function to create a RateLimiter with MemoryBackend and default policy."""
    backend = MemoryBackend()
    policy = RatePolicy()
    return RateLimiter(backend, policy)
