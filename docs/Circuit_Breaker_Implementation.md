# Circuit Breaker Implementation

This document describes the circuit breaker pattern implementation in the MCP Gateway, providing resilience against cascading failures when communicating with downstream MCP servers.

## Overview

The circuit breaker pattern prevents cascading failures by monitoring the health of downstream services and temporarily stopping requests to failing services. Our implementation provides:

- **Automatic failure detection** with configurable thresholds
- **Three states**: CLOSED (normal), OPEN (failing), HALF_OPEN (testing recovery)
- **Exponential backoff** for recovery attempts
- **Per-server isolation** to prevent one failing server from affecting others
- **Comprehensive metrics** for monitoring and alerting

## Architecture

### Core Components

1. **CircuitBreaker** (`src/mcp_gateway/circuit_breaker/breaker.py`)
   - Individual circuit breaker instance
   - State machine implementation (CLOSED → OPEN → HALF_OPEN → CLOSED)
   - Failure tracking and timeout management

2. **CircuitBreakerManager** (`src/mcp_gateway/circuit_breaker/manager.py`)
   - Manages multiple circuit breakers per server
   - Provides unified interface for protected operations
   - Error categorization and retry logic

3. **Exceptions** (`src/mcp_gateway/circuit_breaker/exceptions.py`)
   - `CircuitBreakerError`: Base exception class
   - `CircuitBreakerOpenError`: Thrown when circuit is open

### Integration Points

1. **Service Registry** (`src/mcp_gateway/core/service_registry.py`)
   - Initializes circuit breaker manager
   - Provides dependency injection for other components

2. **Session Manager** (`src/mcp_gateway/mcp/session_manager.py`)
   - Protects session creation and tool calls
   - Integrates circuit breaker into heartbeat monitoring
   - Provides circuit breaker-aware API methods

3. **Client Wrapper** (`src/mcp_gateway/mcp/client_wrapper.py`)
   - Passes circuit breaker manager to session manager
   - Ensures proper initialization

## Configuration

### Circuit Breaker Settings

```python
@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5          # Failures before opening
    recovery_timeout: float = 60.0      # Seconds before attempting recovery
    success_threshold: int = 3          # Successes needed to close
    timeout: float = 30.0               # Operation timeout
    exponential_backoff: bool = True    # Enable backoff
    max_recovery_timeout: float = 300.0 # Maximum backoff time
```

### Per-Server Isolation

Each MCP server gets its own circuit breaker instance, identified by server name. This ensures:
- Failures in one server don't affect others
- Independent recovery timing
- Granular monitoring and alerting

## State Transitions

### CLOSED State (Normal Operation)
- All requests pass through normally
- Failure counter tracks consecutive failures
- Transitions to OPEN when failure threshold exceeded

### OPEN State (Circuit Tripped)
- All requests immediately fail with `CircuitBreakerOpenError`
- No requests reach the downstream server
- Transitions to HALF_OPEN after recovery timeout

### HALF_OPEN State (Testing Recovery)
- Limited requests allowed to test server health
- Success transitions back to CLOSED
- Failure transitions back to OPEN with exponential backoff

## Usage Examples

### Basic Tool Call with Circuit Breaker

```python
try:
    result = await session_manager.call_tool_with_breaker(
        session_id="session-123",
        tool_name="analyze_data",
        arguments={"dataset": "sales_2024"}
    )
    print(f"Tool result: {result}")
except CircuitBreakerOpenError as e:
    print(f"Circuit breaker open: {e.message}")
    print(f"Retry after: {e.retry_after} seconds")
except MCPSessionError as e:
    print(f"Session error: {e}")
```

### Creating Session with Circuit Breaker Protection

```python
config = MCPSessionConfig(
    server_name="analytics-server",
    transport_config={
        "type": "http",
        "endpoint": "https://analytics.company.com"
    }
)

try:
    session_id = await session_manager.create_session(config)
    print(f"Created session: {session_id}")
except CircuitBreakerOpenError:
    print("Server temporarily unavailable")
except Exception as e:
    print(f"Failed to create session: {e}")
```

### Monitoring Circuit Breaker Health

```python
# Get statistics for all circuit breakers
stats = await session_manager.get_circuit_breaker_stats()
print(f"Total breakers: {stats['total_breakers']}")

for server_name, breaker_stats in stats['breakers'].items():
    print(f"Server: {server_name}")
    print(f"  State: {breaker_stats['state']}")
    print(f"  Failures: {breaker_stats['failure_count']}")
    print(f"  Last failure: {breaker_stats['last_failure_time']}")
```

## Error Handling

### CircuitBreakerOpenError

When a circuit breaker is open, requests fail immediately with `CircuitBreakerOpenError`:

```python
{
    "error": "circuit_breaker_open",
    "message": "Circuit breaker is open for server 'analytics-server'",
    "server_name": "analytics-server",
    "state": "OPEN",
    "retry_after": 60.0,
    "failure_count": 5,
    "last_failure_time": "2024-01-15T10:30:00Z"
}
```

### Exponential Backoff

Recovery timeout increases exponentially for repeated failures:
- First failure: 60 seconds
- Second failure: 120 seconds  
- Third failure: 240 seconds
- Maximum: 300 seconds (configurable)

## Best Practices

### 1. Configure Appropriate Thresholds

```python
# For critical services - more conservative
critical_config = CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=30.0,
    success_threshold=5
)

# For less critical services - more permissive
standard_config = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=60.0,
    success_threshold=3
)
```

### 2. Handle Circuit Breaker Errors Gracefully

```python
async def call_tool_with_fallback(session_id, tool_name, arguments):
    try:
        return await session_manager.call_tool_with_breaker(
            session_id, tool_name, arguments
        )
    except CircuitBreakerOpenError:
        # Provide cached result or default response
        return await get_cached_result(tool_name, arguments)
    except Exception as e:
        # Log error and provide fallback
        logger.error(f"Tool call failed: {e}")
        return {"error": "Service temporarily unavailable"}
```

### 3. Monitor Circuit Breaker Metrics

Set up monitoring for:
- Circuit breaker state changes
- Failure rates per server
- Recovery times
- Open circuit duration

```python
# Example monitoring endpoint
@app.get("/api/v1/circuit-breaker/health")
async def circuit_breaker_health():
    stats = await session_manager.get_circuit_breaker_stats()
    
    # Check for any open circuits
    open_circuits = [
        name for name, info in stats['breakers'].items()
        if info['state'] == 'OPEN'
    ]
    
    return {
        "status": "healthy" if not open_circuits else "degraded",
        "open_circuits": open_circuits,
        "total_breakers": stats['total_breakers']
    }
```

## Integration with Existing Systems

### Health Checks

Circuit breaker integrates with existing health check infrastructure:

```python
async def _heartbeat_loop(self, session_id: str):
    """Enhanced heartbeat with circuit breaker protection."""
    try:
        await self.circuit_breaker_manager.check_and_call(
            server_key,
            self._perform_heartbeat,
            session
        )
    except CircuitBreakerOpenError:
        # Close session when circuit is open
        await self.close_session(session_id)
```

### Authentication

Circuit breaker respects authentication boundaries:
- Per-server circuit breakers maintain auth context
- OBO token refresh doesn't trigger circuit breaker
- Authentication failures are separate from service failures

### Rate Limiting

Circuit breaker works alongside rate limiting:
- Rate limiting happens before circuit breaker check
- Circuit breaker prevents requests from reaching rate limiter when open
- Both systems provide complementary protection

## Troubleshooting

### Common Issues

1. **Circuit Opens Too Frequently**
   - Increase `failure_threshold`
   - Check if server has intermittent issues
   - Review timeout settings

2. **Circuit Takes Too Long to Recover**
   - Decrease `recovery_timeout`
   - Disable exponential backoff for testing
   - Check if underlying issue is resolved

3. **Circuit Never Opens Despite Failures**
   - Verify error types are being counted
   - Check failure threshold configuration
   - Review error categorization logic

### Debugging

Enable debug logging for detailed circuit breaker information:

```python
import logging
logging.getLogger("mcp_gateway.circuit_breaker").setLevel(logging.DEBUG)
```

Log output includes:
- State transitions with timestamps
- Failure counts and types  
- Recovery attempt results
- Configuration values

## Security Considerations

1. **Information Disclosure**: Circuit breaker errors don't expose internal server details
2. **Resource Protection**: Prevents resource exhaustion from failed requests
3. **Graceful Degradation**: Maintains service availability during partial failures
4. **Audit Trail**: All state changes are logged for security monitoring

## Performance Impact

- **Minimal Overhead**: Simple state checks for healthy services
- **Memory Efficient**: One circuit breaker instance per unique server
- **Non-blocking**: Async implementation with no blocking operations
- **Configurable**: Timeouts and thresholds tunable for performance requirements

## Future Enhancements

1. **Dynamic Configuration**: Runtime adjustment of circuit breaker parameters
2. **Advanced Metrics**: Histograms, percentiles, and trend analysis
3. **Custom Policies**: Server-specific failure detection logic
4. **Circuit Breaker Coordination**: Cross-instance circuit breaker state sharing
5. **Predictive Opening**: ML-based failure prediction and preemptive circuit opening
