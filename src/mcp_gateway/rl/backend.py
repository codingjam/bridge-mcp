"""Rate limiting backend implementations."""

import time
import threading
import logging
from abc import ABC, abstractmethod
from typing import Dict, Tuple

from .exceptions import RateLimitBackendError

logger = logging.getLogger(__name__)


class LimiterBackend(ABC):
    """Abstract base class for rate limiting backends."""
    
    @abstractmethod
    def incr_and_get(self, key: str, window_seconds: int) -> Tuple[int, int]:
        """
        Atomically increment the counter for `key` in the current fixed window.
        Return (count, ttl_remaining_seconds).
        window_id = floor(epoch / window_seconds)
        ttl_remaining_seconds = ((window_id+1)*window_seconds) - now
        """
        pass


class MemoryBackend(LimiterBackend):
    """Thread-safe in-memory rate limiting backend."""
    
    def __init__(self):
        self._counters: Dict[Tuple[str, int], int] = {}
        self._lock = threading.Lock()
    
    def incr_and_get(self, key: str, window_seconds: int) -> Tuple[int, int]:
        """
        Atomically increment the counter for `key` in the current fixed window.
        Return (count, ttl_remaining_seconds).
        """
        try:
            with self._lock:
                now = time.time()
                window_id = int(now // window_seconds)
                
                # Calculate TTL remaining in current window
                window_end = (window_id + 1) * window_seconds
                ttl_remaining = int(window_end - now)
                
                # Increment counter for this key and window
                counter_key = (key, window_id)
                current_count = self._counters.get(counter_key, 0)
                new_count = current_count + 1
                self._counters[counter_key] = new_count
                
                # Clean up old windows (optional optimization)
                self._cleanup_old_windows(window_id, window_seconds)
                
                return new_count, ttl_remaining
        except Exception as e:
            logger.error(
                "Memory backend error during incr_and_get",
                extra={"key": key, "window_seconds": window_seconds, "error": str(e)},
                exc_info=True
            )
            raise RateLimitBackendError(f"Memory backend failed: {str(e)}", str(e))
    
    def _cleanup_old_windows(self, current_window_id: int, window_seconds: int) -> None:
        """Remove counters from old windows to prevent memory leaks."""
        # Only clean up occasionally to avoid performance impact
        if current_window_id % 10 == 0:  # Clean every 10 windows
            cutoff_window = current_window_id - 2  # Keep current and previous window
            keys_to_remove = [
                key for key in self._counters.keys()
                if key[1] < cutoff_window
            ]
            for key in keys_to_remove:
                del self._counters[key]
