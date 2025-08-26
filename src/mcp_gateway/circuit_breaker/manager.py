"""
Circuit Breaker Manager for MCP Gateway.

This module provides centralized management of multiple circuit breakers,
typically one per downstream MCP server. It handles creation, configuration,
and coordination of circuit breakers across the gateway.

The manager provides:
- Per-server circuit breaker instances
- Centralized configuration management  
- Integrated execution with automatic failure recording
- Comprehensive monitoring and statistics
- Administrative operations (reset, cleanup)

Example Usage:
    # Initialize manager with default configuration
    manager = CircuitBreakerManager()
    
    # Execute protected operation
    try:
        result = await manager.check_and_call(
            "filesystem-server",
            my_async_function,
            arg1, arg2,
            kwarg1="value"
        )
    except CircuitBreakerOpenError:
        # Handle circuit breaker open case
        return handle_service_unavailable()
"""

import asyncio
from typing import Dict, Optional, List, Any, Callable, Awaitable
from datetime import datetime, timedelta
import logging

from .breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerState
from .exceptions import CircuitBreakerOpenError, CircuitBreakerOperationError

logger = logging.getLogger(__name__)


class CircuitBreakerManager:
    """
    Centralized manager for multiple circuit breakers in the MCP Gateway.
    
    This class manages a collection of circuit breakers, typically one per
    downstream MCP server. It provides high-level operations that integrate
    circuit breaker protection with actual service calls.
    
    Key Features:
    - Automatic circuit breaker creation per server
    - Per-server custom configuration support
    - Integrated call execution with protection
    - Error categorization and handling
    - Comprehensive monitoring and statistics
    - Administrative operations for maintenance
    
    Thread Safety:
    The manager uses asyncio locks to ensure thread-safe access to the
    circuit breaker collection and provides atomic operations.
    """
    
    def __init__(self, default_config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize circuit breaker manager.
        
        Args:
            default_config: Default configuration for new circuit breakers.
                          If not provided, uses CircuitBreakerConfig defaults.
        """
        self.default_config = default_config or CircuitBreakerConfig()
        
        # Thread-safe collection of circuit breakers
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
        
        # Per-server custom configurations
        self._server_configs: Dict[str, CircuitBreakerConfig] = {}
        
        # Manager-level metrics
        self.total_protected_calls = 0
        self.total_breaker_trips = 0
        self.active_open_breakers = 0
        self._created_at = datetime.utcnow()
        
        logger.info(
            "Circuit breaker manager initialized",
            extra={
                "default_config": {
                    "failure_threshold": self.default_config.failure_threshold,
                    "base_cooldown_seconds": self.default_config.base_cooldown_seconds,
                    "failure_rate_threshold": self.default_config.failure_rate_threshold
                }
            }
        )
    
    async def get_breaker(self, server_key: str) -> CircuitBreaker:
        """
        Get or create a circuit breaker for the specified server.
        
        This method implements lazy initialization - circuit breakers are created
        on first access. Each server gets its own isolated circuit breaker instance.
        
        Args:
            server_key: Unique identifier for the downstream server/service
            
        Returns:
            CircuitBreaker instance for the specified server
        """
        async with self._lock:
            if server_key not in self._breakers:
                # Use server-specific config if available, otherwise use default
                config = self._server_configs.get(server_key, self.default_config)
                
                # Create new circuit breaker instance
                self._breakers[server_key] = CircuitBreaker(server_key, config)
                
                logger.info(
                    "Created new circuit breaker for server",
                    extra={
                        "server_key": server_key,
                        "total_breakers": len(self._breakers),
                        "config": {
                            "failure_threshold": config.failure_threshold,
                            "base_cooldown_seconds": config.base_cooldown_seconds
                        }
                    }
                )
            
            return self._breakers[server_key]
    
    async def set_server_config(self, server_key: str, config: CircuitBreakerConfig):
        """
        Set custom configuration for a specific server.
        
        This allows per-server tuning of circuit breaker behavior. If a circuit
        breaker already exists for this server, its configuration will be updated.
        
        Args:
            server_key: Server identifier to configure
            config: Custom circuit breaker configuration
        """
        async with self._lock:
            self._server_configs[server_key] = config
            
            # Update existing breaker configuration if it exists
            if server_key in self._breakers:
                self._breakers[server_key].config = config
                logger.info(
                    "Updated circuit breaker configuration for server",
                    extra={
                        "server_key": server_key,
                        "failure_threshold": config.failure_threshold,
                        "base_cooldown_seconds": config.base_cooldown_seconds
                    }
                )
    
    async def check_and_call(self, 
                            server_key: str,
                            async_func: Callable[..., Awaitable[Any]],
                            *args,
                            **kwargs) -> Any:
        """
        Execute an async function with circuit breaker protection.
        
        This is the main method for executing protected operations. It handles:
        - Circuit breaker state checking
        - Automatic success/failure recording
        - Error categorization and handling
        - Performance measurement
        
        Args:
            server_key: Identifier for the downstream server
            async_func: The async function to execute with protection
            *args: Positional arguments to pass to async_func
            **kwargs: Keyword arguments to pass to async_func
            
        Returns:
            The result of async_func if successful
            
        Raises:
            CircuitBreakerOpenError: If circuit breaker is open
            CircuitBreakerOperationError: If execution fails due to internal errors
            Exception: Any exception raised by async_func (after recording failure)
        """
        # Get circuit breaker for this server
        breaker = await self.get_breaker(server_key)
        
        # Update manager metrics
        self.total_protected_calls += 1
        
        # Check if call should be allowed through circuit breaker
        if not await breaker.should_allow_call():
            stats = breaker.get_stats()
            
            # Update manager metrics for blocked calls
            if breaker.state == CircuitBreakerState.OPEN:
                self.active_open_breakers = await self._count_open_breakers()
            
            raise CircuitBreakerOpenError(
                f"Circuit breaker is open for server: {server_key}",
                server_key=server_key,
                cooldown_remaining=stats["cooldown_remaining_seconds"],
                failure_rate=stats["failure_rate"],
                total_failures=stats["total_failures"],
                last_failure_time=stats["last_failure_time"]
            )
        
        # Execute the protected operation with timing
        start_time = asyncio.get_event_loop().time()
        
        try:
            logger.debug(
                "Executing protected call through circuit breaker",
                extra={
                    "server_key": server_key,
                    "function": async_func.__name__ if hasattr(async_func, '__name__') else str(async_func),
                    "breaker_state": breaker.state.value
                }
            )
            
            # Execute the actual function
            result = await async_func(*args, **kwargs)
            
            # Calculate latency and record success
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            await breaker.record_success(latency_ms)
            
            logger.debug(
                "Protected call completed successfully",
                extra={
                    "server_key": server_key,
                    "latency_ms": latency_ms,
                    "breaker_state": breaker.state.value
                }
            )
            
            return result
            
        except Exception as e:
            # Calculate latency for failed operation
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # Categorize the error for circuit breaker decision
            error_category = self._categorize_error(e)
            
            # Record failure with circuit breaker
            await breaker.record_failure(e, error_category)
            
            # Update manager metrics if breaker tripped
            if breaker.state == CircuitBreakerState.OPEN:
                self.total_breaker_trips += 1
                self.active_open_breakers = await self._count_open_breakers()
            
            logger.warning(
                "Protected call failed",
                extra={
                    "server_key": server_key,
                    "error_type": type(e).__name__,
                    "error_category": error_category,
                    "error_message": str(e),
                    "latency_ms": latency_ms,
                    "breaker_state": breaker.state.value
                }
            )
            
            # Re-raise the original exception
            raise
    
    def _categorize_error(self, error: Exception) -> str:
        """
        Categorize an error for circuit breaker decision making.
        
        This method analyzes exceptions to determine whether they should
        contribute to circuit breaker tripping or be ignored as client errors.
        
        Args:
            error: The exception to categorize
            
        Returns:
            String category for the error type
        """
        error_type = type(error).__name__
        
        # Handle HTTP-like status codes if available
        if hasattr(error, "status_code"):
            status = getattr(error, "status_code", 500)
            if 400 <= status < 500:
                return "ClientError"  # Don't trip breaker for client errors
            else:
                return "ServerError"  # Trip breaker for server errors
        
        # Handle timeout-related errors
        if "timeout" in error_type.lower() or "timeout" in str(error).lower():
            return "TimeoutError"
        
        # Handle connection-related errors
        if "connection" in error_type.lower() or "connection" in str(error).lower():
            return "ConnectionError"
        
        # Handle MCP-specific errors
        if "mcp" in error_type.lower():
            if "connection" in error_type.lower():
                return "MCPConnectionError"
            elif "session" in error_type.lower():
                return "MCPSessionError"
            elif "transport" in error_type.lower():
                return "MCPTransportError"
            else:
                return "MCPError"
        
        # Handle asyncio cancellation (don't trip breaker)
        if isinstance(error, asyncio.CancelledError):
            return "CancelledError"
        
        # Default categorization
        return error_type
    
    async def _count_open_breakers(self) -> int:
        """
        Count how many circuit breakers are currently open.
        
        Returns:
            Number of circuit breakers in OPEN state
        """
        count = 0
        async with self._lock:
            for breaker in self._breakers.values():
                if breaker.state == CircuitBreakerState.OPEN:
                    count += 1
        return count
    
    async def get_all_stats(self) -> List[Dict[str, Any]]:
        """
        Get comprehensive statistics for all circuit breakers.
        
        Returns:
            List of dictionaries containing stats for each circuit breaker
        """
        async with self._lock:
            stats = []
            
            for breaker in self._breakers.values():
                breaker_stats = breaker.get_stats()
                stats.append(breaker_stats)
            
            # Update manager-level metrics
            self.active_open_breakers = sum(
                1 for breaker in self._breakers.values() 
                if breaker.state == CircuitBreakerState.OPEN
            )
            
            return stats
    
    async def get_manager_stats(self) -> Dict[str, Any]:
        """
        Get manager-level statistics and summary information.
        
        Returns:
            Dictionary containing manager and aggregate statistics
        """
        async with self._lock:
            stats = await self.get_all_stats()
            
            # Calculate aggregate metrics
            total_calls = sum(s["total_calls"] for s in stats)
            total_failures = sum(s["total_failures"] for s in stats)
            total_successes = sum(s["total_successes"] for s in stats)
            
            # Count states
            state_counts = {
                "closed": sum(1 for s in stats if s["state"] == "closed"),
                "open": sum(1 for s in stats if s["state"] == "open"),
                "half_open": sum(1 for s in stats if s["state"] == "half_open")
            }
            
            # Calculate success rate
            success_rate = total_successes / total_calls if total_calls > 0 else 0.0
            
            return {
                "manager": {
                    "total_breakers": len(self._breakers),
                    "total_protected_calls": self.total_protected_calls,
                    "total_breaker_trips": self.total_breaker_trips,
                    "active_open_breakers": self.active_open_breakers,
                    "uptime_seconds": (datetime.utcnow() - self._created_at).total_seconds()
                },
                "aggregate": {
                    "total_calls": total_calls,
                    "total_failures": total_failures,
                    "total_successes": total_successes,
                    "success_rate": success_rate,
                    "failure_rate": 1.0 - success_rate if total_calls > 0 else 0.0
                },
                "states": state_counts,
                "breakers": stats
            }
    
    async def reset_breaker(self, server_key: str) -> bool:
        """
        Manually reset a specific circuit breaker to closed state.
        
        This is useful for administrative purposes when you know a service
        has been fixed and want to immediately restore traffic.
        
        Args:
            server_key: Identifier of the circuit breaker to reset
            
        Returns:
            True if breaker was reset, False if breaker doesn't exist
        """
        async with self._lock:
            if server_key in self._breakers:
                breaker = self._breakers[server_key]
                old_state = breaker.state
                
                breaker.reset()
                
                logger.info(
                    "Circuit breaker manually reset",
                    extra={
                        "server_key": server_key,
                        "previous_state": old_state.value,
                        "new_state": breaker.state.value
                    }
                )
                
                return True
            
            return False
    
    async def reset_all_breakers(self) -> int:
        """
        Reset all circuit breakers to closed state.
        
        This is a bulk administrative operation for emergency recovery.
        
        Returns:
            Number of circuit breakers that were reset
        """
        async with self._lock:
            reset_count = 0
            
            for server_key, breaker in self._breakers.items():
                if breaker.state != CircuitBreakerState.CLOSED:
                    old_state = breaker.state
                    breaker.reset()
                    reset_count += 1
                    
                    logger.info(
                        "Circuit breaker reset during bulk operation",
                        extra={
                            "server_key": server_key,
                            "previous_state": old_state.value
                        }
                    )
            
            if reset_count > 0:
                logger.warning(
                    "Bulk circuit breaker reset completed",
                    extra={"reset_count": reset_count, "total_breakers": len(self._breakers)}
                )
            
            return reset_count
    
    async def cleanup_inactive_breakers(self, inactive_threshold_minutes: int = 60) -> int:
        """
        Remove circuit breakers that haven't been used recently.
        
        This helps manage memory usage by cleaning up breakers for servers
        that are no longer being accessed.
        
        Args:
            inactive_threshold_minutes: Minutes of inactivity before cleanup
            
        Returns:
            Number of circuit breakers that were removed
        """
        inactive_threshold = timedelta(minutes=inactive_threshold_minutes)
        now = datetime.utcnow()
        
        async with self._lock:
            to_remove = []
            
            for server_key, breaker in self._breakers.items():
                # Check last activity time
                last_activity = max(
                    breaker.last_success_time,
                    breaker.last_failure_time,
                    breaker.last_state_change_time
                )
                
                # Convert to datetime for comparison
                last_activity_dt = datetime.fromtimestamp(last_activity)
                
                if now - last_activity_dt > inactive_threshold:
                    to_remove.append(server_key)
            
            # Remove inactive breakers
            for server_key in to_remove:
                del self._breakers[server_key]
                # Also remove custom config if present
                self._server_configs.pop(server_key, None)
                
                logger.info(
                    "Removed inactive circuit breaker",
                    extra={
                        "server_key": server_key,
                        "inactive_threshold_minutes": inactive_threshold_minutes
                    }
                )
            
            if to_remove:
                logger.info(
                    "Circuit breaker cleanup completed",
                    extra={
                        "removed_count": len(to_remove),
                        "remaining_breakers": len(self._breakers)
                    }
                )
            
            return len(to_remove)
    
    async def get_breaker_by_server(self, server_key: str) -> Optional[CircuitBreaker]:
        """
        Get circuit breaker for a server without creating one if it doesn't exist.
        
        Args:
            server_key: Server identifier
            
        Returns:
            CircuitBreaker instance if it exists, None otherwise
        """
        async with self._lock:
            return self._breakers.get(server_key)
    
    async def list_server_keys(self) -> List[str]:
        """
        Get list of all server keys with active circuit breakers.
        
        Returns:
            List of server identifiers
        """
        async with self._lock:
            return list(self._breakers.keys())
    
    async def shutdown(self):
        """
        Gracefully shutdown the circuit breaker manager.
        
        This method should be called during application shutdown to clean up
        resources and log final statistics.
        """
        logger.info(
            "Circuit breaker manager shutting down",
            extra={
                "total_breakers": len(self._breakers),
                "total_protected_calls": self.total_protected_calls,
                "total_breaker_trips": self.total_breaker_trips
            }
        )
        
        # Clear all breakers
        async with self._lock:
            self._breakers.clear()
            self._server_configs.clear()
