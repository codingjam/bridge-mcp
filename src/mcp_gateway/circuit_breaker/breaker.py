"""
Core Circuit Breaker implementation for MCP Gateway.

This module contains the main CircuitBreaker class and supporting components
that implement the circuit breaker pattern for protecting downstream services
from cascading failures.

The circuit breaker operates as a state machine with three states:
- CLOSED: Normal operation, requests flow through
- OPEN: Too many failures, requests are blocked
- HALF_OPEN: Testing recovery, limited requests allowed

This implementation uses asyncio for thread safety and provides comprehensive
monitoring and configuration options.
"""

import asyncio
import time
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from collections import deque
import logging

from .exceptions import CircuitBreakerConfigurationError

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """
    Circuit breaker state enumeration.
    
    States:
        CLOSED: Normal operation - requests pass through to downstream service
        OPEN: Failing fast - requests are blocked and fail immediately
        HALF_OPEN: Recovery testing - limited requests allowed to test service recovery
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """
    Configuration class for circuit breaker behavior.
    
    This class defines all the tunable parameters that control how the circuit
    breaker responds to failures and recovers from them.
    """
    
    # Failure thresholds - when to trip the breaker
    failure_threshold: int = 5
    """Number of consecutive failures required to open the circuit"""
    
    failure_rate_threshold: float = 0.5
    """Failure rate (0.0-1.0) in rolling window to open circuit"""
    
    rolling_window_size: int = 20
    """Number of recent calls to track for failure rate calculation"""
    
    # Timing configuration - how long to wait
    base_cooldown_seconds: float = 5.0
    """Initial duration to keep circuit open"""
    
    max_cooldown_seconds: float = 60.0
    """Maximum cooldown duration with exponential backoff"""
    
    cooldown_multiplier: float = 2.0
    """Factor to multiply cooldown on repeated failures"""
    
    # Half-open state configuration - recovery testing
    half_open_max_attempts: int = 3
    """Maximum probe requests allowed in half-open state"""
    
    half_open_success_threshold: int = 2
    """Successful probes needed to close circuit"""
    
    # Error categorization - what trips the breaker
    trip_on_errors: Tuple[str, ...] = (
        "ConnectionError",
        "TimeoutError", 
        "MCPConnectionError",
        "MCPTransportError",
        "ServerUnavailable",
        "ConnectTimeout",
        "ReadTimeout",
        "HTTPError"
    )
    """Error types that should trip the circuit breaker"""
    
    ignore_errors: Tuple[str, ...] = (
        "AuthenticationError",
        "AuthorizationError", 
        "ValidationError",
        "RateLimitError",
        "BadRequest",
        "NotFound",
        "Forbidden"
    )
    """Error types that should not trip the circuit breaker (client errors)"""
    
    def __post_init__(self):
        """Validate configuration values after initialization."""
        self._validate_config()
    
    def _validate_config(self):
        """
        Validate configuration parameters for consistency and sanity.
        
        Raises:
            CircuitBreakerConfigurationError: If configuration is invalid
        """
        if self.failure_threshold < 1:
            raise CircuitBreakerConfigurationError(
                "failure_threshold must be >= 1",
                config_field="failure_threshold",
                provided_value=self.failure_threshold
            )
        
        if not 0.0 <= self.failure_rate_threshold <= 1.0:
            raise CircuitBreakerConfigurationError(
                "failure_rate_threshold must be between 0.0 and 1.0",
                config_field="failure_rate_threshold", 
                provided_value=self.failure_rate_threshold
            )
        
        if self.rolling_window_size < 1:
            raise CircuitBreakerConfigurationError(
                "rolling_window_size must be >= 1",
                config_field="rolling_window_size",
                provided_value=self.rolling_window_size
            )
        
        if self.base_cooldown_seconds <= 0:
            raise CircuitBreakerConfigurationError(
                "base_cooldown_seconds must be > 0",
                config_field="base_cooldown_seconds",
                provided_value=self.base_cooldown_seconds
            )
        
        if self.max_cooldown_seconds < self.base_cooldown_seconds:
            raise CircuitBreakerConfigurationError(
                "max_cooldown_seconds must be >= base_cooldown_seconds",
                config_field="max_cooldown_seconds",
                provided_value=self.max_cooldown_seconds
            )
        
        if self.cooldown_multiplier <= 1.0:
            raise CircuitBreakerConfigurationError(
                "cooldown_multiplier must be > 1.0",
                config_field="cooldown_multiplier",
                provided_value=self.cooldown_multiplier
            )
        
        if self.half_open_max_attempts < 1:
            raise CircuitBreakerConfigurationError(
                "half_open_max_attempts must be >= 1",
                config_field="half_open_max_attempts",
                provided_value=self.half_open_max_attempts
            )
        
        if self.half_open_success_threshold < 1:
            raise CircuitBreakerConfigurationError(
                "half_open_success_threshold must be >= 1",
                config_field="half_open_success_threshold",
                provided_value=self.half_open_success_threshold
            )
        
        if self.half_open_success_threshold > self.half_open_max_attempts:
            raise CircuitBreakerConfigurationError(
                "half_open_success_threshold cannot exceed half_open_max_attempts",
                config_field="half_open_success_threshold",
                provided_value=self.half_open_success_threshold
            )


class CircuitBreaker:
    """
    Thread-safe circuit breaker implementation for protecting downstream services.
    
    The circuit breaker monitors calls to downstream services and automatically
    opens when failure thresholds are exceeded, then attempts recovery through
    controlled probing.
    
    Key Features:
    - Async/await support with asyncio locks for thread safety
    - Rolling window failure rate tracking
    - Exponential backoff for recovery attempts
    - Configurable error categorization
    - Comprehensive metrics collection
    - State transition logging
    
    Usage:
        config = CircuitBreakerConfig(failure_threshold=3, base_cooldown_seconds=10)
        breaker = CircuitBreaker("my-service", config)
        
        # Check if call should be allowed
        if await breaker.should_allow_call():
            try:
                result = await my_service_call()
                await breaker.record_success()
                return result
            except Exception as e:
                await breaker.record_failure(e)
                raise
        else:
            raise CircuitBreakerOpenError("Circuit breaker is open")
    """
    
    def __init__(self, 
                 breaker_id: str,
                 config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize circuit breaker.
        
        Args:
            breaker_id: Unique identifier for this circuit breaker instance
            config: Configuration object, uses defaults if not provided
        """
        self.breaker_id = breaker_id
        self.config = config or CircuitBreakerConfig()
        
        # State management with asyncio lock for thread safety
        self.state = CircuitBreakerState.CLOSED
        self._lock = asyncio.Lock()
        
        # Failure tracking with rolling window for rate calculation
        self.call_history: deque = deque(maxlen=self.config.rolling_window_size)
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        
        # Cooldown management with exponential backoff
        self.cooldown_until = 0.0
        self.current_cooldown = self.config.base_cooldown_seconds
        
        # Half-open state tracking for recovery testing
        self.half_open_attempts = 0
        self.half_open_successes = 0
        
        # Comprehensive metrics for monitoring and debugging
        self.total_calls = 0
        self.total_failures = 0
        self.total_successes = 0
        self.total_trips = 0
        self.last_failure_time = 0.0
        self.last_success_time = 0.0
        self.last_state_change_time = time.time()
        
        logger.info(
            "Circuit breaker initialized",
            extra={
                "breaker_id": self.breaker_id,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "failure_rate_threshold": self.config.failure_rate_threshold,
                    "base_cooldown_seconds": self.config.base_cooldown_seconds
                }
            }
        )
    
    async def is_open(self) -> bool:
        """
        Check if circuit is currently open (blocking calls).
        
        Returns:
            True if circuit is open and blocking calls
        """
        async with self._lock:
            return self._is_open_internal()
    
    def _is_open_internal(self) -> bool:
        """
        Internal check for open state without acquiring lock.
        Must be called while holding the asyncio lock.
        
        Returns:
            True if circuit should block calls
        """
        now = time.time()
        
        if self.state == CircuitBreakerState.OPEN:
            if now >= self.cooldown_until:
                # Cooldown period has expired, transition to half-open for probing
                self._transition_to_half_open()
                return False
            return True
        
        return False
    
    async def should_allow_call(self) -> bool:
        """
        Determine if a call should be allowed through the circuit breaker.
        
        This is the main entry point for checking if an operation should proceed.
        It handles state transitions and manages half-open probe attempts.
        
        Returns:
            True if call should be allowed, False if circuit is blocking
        """
        async with self._lock:
            # Check if circuit is open and should block calls
            if self._is_open_internal():
                logger.warning(
                    "Circuit breaker blocking call - circuit is open",
                    extra={
                        "breaker_id": self.breaker_id,
                        "state": self.state.value,
                        "cooldown_remaining": max(0, self.cooldown_until - time.time()),
                        "total_failures": self.total_failures,
                        "failure_rate": self._calculate_failure_rate()
                    }
                )
                return False
            
            # Handle half-open state - limit probe attempts
            if self.state == CircuitBreakerState.HALF_OPEN:
                if self.half_open_attempts >= self.config.half_open_max_attempts:
                    logger.debug(
                        "Circuit breaker blocking call - too many half-open attempts",
                        extra={
                            "breaker_id": self.breaker_id,
                            "half_open_attempts": self.half_open_attempts,
                            "max_attempts": self.config.half_open_max_attempts
                        }
                    )
                    return False
                
                # Allow probe attempt
                self.half_open_attempts += 1
                logger.debug(
                    "Circuit breaker allowing probe attempt",
                    extra={
                        "breaker_id": self.breaker_id,
                        "attempt": self.half_open_attempts,
                        "max_attempts": self.config.half_open_max_attempts
                    }
                )
            
            return True
    
    async def record_success(self, latency_ms: Optional[float] = None):
        """
        Record a successful operation.
        
        This updates the circuit breaker state and may trigger transitions
        from half-open to closed if enough successes are recorded.
        
        Args:
            latency_ms: Optional latency measurement for performance tracking
        """
        async with self._lock:
            # Update metrics
            self.total_calls += 1
            self.total_successes += 1
            self.last_success_time = time.time()
            self.call_history.append(True)
            
            # Reset consecutive failure counter
            self.consecutive_failures = 0
            self.consecutive_successes += 1
            
            # Handle state transitions based on success
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.half_open_successes += 1
                
                if self.half_open_successes >= self.config.half_open_success_threshold:
                    self._close_circuit()
                    logger.info(
                        "Circuit breaker closed after successful probes",
                        extra={
                            "breaker_id": self.breaker_id,
                            "successful_probes": self.half_open_successes,
                            "required_successes": self.config.half_open_success_threshold
                        }
                    )
            
            elif self.state == CircuitBreakerState.OPEN:
                # This shouldn't happen during normal operation
                logger.warning(
                    "Received success while circuit is open - transitioning to half-open",
                    extra={"breaker_id": self.breaker_id}
                )
                self._transition_to_half_open()
            
            # Log success with performance data
            logger.debug(
                "Circuit breaker recorded success",
                extra={
                    "breaker_id": self.breaker_id,
                    "latency_ms": latency_ms,
                    "state": self.state.value,
                    "consecutive_successes": self.consecutive_successes
                }
            )
    
    async def record_failure(self, 
                            error: Exception,
                            error_category: Optional[str] = None):
        """
        Record a failed operation and potentially trip the breaker.
        
        This analyzes the error type to determine if it should count toward
        circuit breaker trips, then updates state accordingly.
        
        Args:
            error: The exception that occurred during the operation
            error_category: Optional explicit categorization of the error
        """
        async with self._lock:
            # Update basic metrics
            self.total_calls += 1
            self.total_failures += 1
            self.last_failure_time = time.time()
            
            # Categorize error to determine if it should trip the breaker
            error_type = error_category or type(error).__name__
            
            # Check if this error should be ignored (client errors)
            if error_type in self.config.ignore_errors:
                logger.debug(
                    "Circuit breaker ignoring client error",
                    extra={
                        "breaker_id": self.breaker_id,
                        "error_type": error_type,
                        "error_message": str(error)
                    }
                )
                # Still record the call but don't count as failure for tripping
                self.call_history.append(True)
                return
            
            # Record as failure and update counters
            self.call_history.append(False)
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            
            # Check if we should trip the breaker
            should_trip = self._should_trip()
            
            if should_trip and self.state == CircuitBreakerState.CLOSED:
                self._open_circuit()
                
            elif self.state == CircuitBreakerState.HALF_OPEN:
                # Failed during probe - return to open with extended cooldown
                self._open_circuit(extend_cooldown=True)
                logger.warning(
                    "Circuit breaker probe failed - extending cooldown",
                    extra={
                        "breaker_id": self.breaker_id,
                        "error_type": error_type,
                        "error_message": str(error),
                        "new_cooldown_seconds": self.current_cooldown
                    }
                )
            
            # Log failure details
            logger.warning(
                "Circuit breaker recorded failure",
                extra={
                    "breaker_id": self.breaker_id,
                    "error_type": error_type,
                    "error_message": str(error),
                    "consecutive_failures": self.consecutive_failures,
                    "state": self.state.value,
                    "should_trip": should_trip
                }
            )
    
    def _should_trip(self) -> bool:
        """
        Determine if the circuit breaker should trip based on failure patterns.
        
        This implements the core logic for when to open the circuit based on
        both consecutive failures and failure rate in the rolling window.
        
        Returns:
            True if circuit should be opened due to failures
        """
        # Check consecutive failures threshold
        if self.consecutive_failures >= self.config.failure_threshold:
            logger.debug(
                "Circuit breaker should trip - consecutive failures exceeded",
                extra={
                    "breaker_id": self.breaker_id,
                    "consecutive_failures": self.consecutive_failures,
                    "threshold": self.config.failure_threshold
                }
            )
            return True
        
        # Check failure rate in rolling window (need minimum sample size)
        if len(self.call_history) >= min(10, self.config.rolling_window_size // 2):
            failure_rate = self._calculate_failure_rate()
            if failure_rate >= self.config.failure_rate_threshold:
                logger.debug(
                    "Circuit breaker should trip - failure rate exceeded",
                    extra={
                        "breaker_id": self.breaker_id,
                        "failure_rate": failure_rate,
                        "threshold": self.config.failure_rate_threshold,
                        "sample_size": len(self.call_history)
                    }
                )
                return True
        
        return False
    
    def _open_circuit(self, extend_cooldown: bool = False):
        """
        Open the circuit breaker due to failures.
        
        This transitions the breaker to the OPEN state and sets up the cooldown
        period with optional exponential backoff.
        
        Args:
            extend_cooldown: If True, apply exponential backoff to cooldown period
        """
        old_state = self.state
        self.state = CircuitBreakerState.OPEN
        self.total_trips += 1
        self.last_state_change_time = time.time()
        
        # Apply exponential backoff if this is a repeated failure
        if extend_cooldown:
            self.current_cooldown = min(
                self.current_cooldown * self.config.cooldown_multiplier,
                self.config.max_cooldown_seconds
            )
        
        # Set cooldown expiration time
        self.cooldown_until = time.time() + self.current_cooldown
        
        logger.warning(
            "Circuit breaker opened",
            extra={
                "breaker_id": self.breaker_id,
                "previous_state": old_state.value if old_state else "unknown",
                "consecutive_failures": self.consecutive_failures,
                "failure_rate": self._calculate_failure_rate(),
                "cooldown_seconds": self.current_cooldown,
                "total_trips": self.total_trips,
                "extended_cooldown": extend_cooldown
            }
        )
    
    def _transition_to_half_open(self):
        """
        Transition from OPEN to HALF_OPEN state for recovery testing.
        
        This resets the probe counters and allows limited requests through
        to test if the downstream service has recovered.
        """
        old_state = self.state
        self.state = CircuitBreakerState.HALF_OPEN
        self.half_open_attempts = 0
        self.half_open_successes = 0
        self.last_state_change_time = time.time()
        
        logger.info(
            "Circuit breaker entering half-open state for recovery testing",
            extra={
                "breaker_id": self.breaker_id,
                "previous_state": old_state.value,
                "max_probe_attempts": self.config.half_open_max_attempts,
                "required_successes": self.config.half_open_success_threshold
            }
        )
    
    def _close_circuit(self):
        """
        Close the circuit breaker after successful recovery.
        
        This returns the breaker to normal operation and resets failure counters.
        Also implements cooldown reduction for faster recovery on subsequent issues.
        """
        old_state = self.state
        self.state = CircuitBreakerState.CLOSED
        self.consecutive_failures = 0
        self.half_open_attempts = 0
        self.half_open_successes = 0
        self.last_state_change_time = time.time()
        
        # Reduce cooldown on successful recovery (but maintain minimum)
        self.current_cooldown = max(
            self.config.base_cooldown_seconds,
            self.current_cooldown / self.config.cooldown_multiplier
        )
        
        logger.info(
            "Circuit breaker closed - service recovered",
            extra={
                "breaker_id": self.breaker_id,
                "previous_state": old_state.value,
                "reduced_cooldown_seconds": self.current_cooldown
            }
        )
    
    def _calculate_failure_rate(self) -> float:
        """
        Calculate current failure rate from rolling window.
        
        Returns:
            Failure rate as float between 0.0 and 1.0
        """
        if not self.call_history:
            return 0.0
        
        failures = sum(1 for success in self.call_history if not success)
        return failures / len(self.call_history)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about circuit breaker performance.
        
        Returns:
            Dictionary containing current state and performance metrics
        """
        now = time.time()
        
        return {
            "breaker_id": self.breaker_id,
            "state": self.state.value,
            "state_duration_seconds": now - self.last_state_change_time,
            
            # Call statistics
            "total_calls": self.total_calls,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            
            # Failure analysis
            "failure_rate": self._calculate_failure_rate(),
            "rolling_window_size": len(self.call_history),
            "max_window_size": self.config.rolling_window_size,
            
            # Circuit breaker events
            "total_trips": self.total_trips,
            "current_cooldown_seconds": self.current_cooldown,
            "cooldown_remaining_seconds": max(0, self.cooldown_until - now) if self.state == CircuitBreakerState.OPEN else 0,
            
            # Half-open state info
            "half_open_attempts": self.half_open_attempts,
            "half_open_successes": self.half_open_successes,
            "half_open_max_attempts": self.config.half_open_max_attempts,
            "half_open_success_threshold": self.config.half_open_success_threshold,
            
            # Timestamps
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "last_state_change_time": self.last_state_change_time,
            
            # Configuration
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "failure_rate_threshold": self.config.failure_rate_threshold,
                "base_cooldown_seconds": self.config.base_cooldown_seconds,
                "max_cooldown_seconds": self.config.max_cooldown_seconds
            }
        }
    
    def reset(self):
        """
        Manually reset circuit breaker to closed state.
        
        This is useful for administrative purposes or when you know
        the downstream service has been fixed.
        """
        self.state = CircuitBreakerState.CLOSED
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.half_open_attempts = 0
        self.half_open_successes = 0
        self.current_cooldown = self.config.base_cooldown_seconds
        self.cooldown_until = 0.0
        self.call_history.clear()
        self.last_state_change_time = time.time()
        
        logger.info(
            "Circuit breaker manually reset to closed state",
            extra={"breaker_id": self.breaker_id}
        )
