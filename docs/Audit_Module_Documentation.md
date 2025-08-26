# Audit Module Documentation

> **Comprehensive audit logging system for tracking all MCP Gateway operations**

## Status

**✅ Production Ready**: The audit module is fully implemented and operational as of Phase 1 completion (August 2025). All audit events, storage, and monitoring capabilities described here are working in production.

**📊 Monitoring**: Provides real-time audit logging with structured events, thread-safe storage, and comprehensive security monitoring.

The MCP Gateway audit module provides comprehensive audit logging capabilities for tracking all significant operations within the gateway. This documentation covers the audit event model, in-memory storage, and usage patterns.

All components described here are production-ready and currently operational in the MCP Gateway (Phase 1 complete).

## Overview

The audit module captures detailed information about:
- Tool invocations and their outcomes
- Authentication events (success/failure)
- Authorization/policy decisions
- Service discovery operations
- System events and errors

## Components

### AuditEvent Model

The `AuditEvent` class is the core model for audit logging. It captures comprehensive information about operations performed through the MCP Gateway.

## AuditStore Class

The `AuditStore` provides thread-safe, in-memory storage for audit events using a singleton pattern.

### Key Features

- **Thread-Safe Operations**: Uses `threading.Lock` for concurrent access
- **Singleton Pattern**: Global access through `get_audit_store()` function
- **Chronological Storage**: Events stored in order with efficient reverse retrieval
- **Rich Querying**: Filter by type, user, status, and more
- **Statistics**: Built-in analytics for monitoring and alerting
- **Memory Efficient**: Reverse chronological queries without full sorting

### Core Methods

#### Storage Operations
- `add_event(event: AuditEvent)`: Add audit event to store
- `get_events(limit: int = 100)`: Get recent events (newest first)
- `clear()`: Remove all events from store
- `count()`: Get total number of stored events

#### Filtering Operations
- `get_events_by_type(event_type: str, limit: int = 100)`: Filter by event type
- `get_events_by_user(user_id: str, limit: int = 100)`: Filter by user
- `get_events_by_server(server_id: str, limit: int = 100)`: Filter by server
- `get_failed_events(limit: int = 100)`: Get only failed operations
- `get_stats()`: Get comprehensive statistics (also available as `get_statistics()`)

### Usage Examples

#### Basic Store Operations
```python
from mcp_gateway.audit import AuditEvent, get_audit_store

# Get singleton store instance
store = get_audit_store()

# Add events
event = AuditEvent.create_event(
    event_type="tool_invocation",
    actor_user_id="user-123",
    actor_client_id="client-456",
    server_id="filesystem",
    status="success"
)
store.add_event(event)

# Retrieve recent events (newest first)
recent_events = store.get_events(limit=10)
for event in recent_events:
    print(f"{event.timestamp}: {event.event_type} - {event.status}")

# Get store statistics
stats = store.get_stats()
print(f"Total events: {stats['total_events']}")
print(f"Success rate: {stats['success_rate']:.1%}")
```

#### Monitoring and Alerting
```python
store = get_audit_store()

# Check for authentication failures
auth_failures = store.get_events_by_type("auth")
failed_auths = [e for e in auth_failures if e.status == "error"]

if len(failed_auths) > 5:
    print("⚠️ High number of authentication failures detected")

# Monitor user activity
user_events = store.get_events_by_user("suspicious-user")
failed_events = [e for e in user_events if e.status != "success"]

if len(failed_events) > 10:
    print(f"⚠️ User has {len(failed_events)} failed operations")

# Monitor server activity
server_events = store.get_events_by_server("filesystem")
failed_server_events = [e for e in server_events if e.status != "success"]

if len(failed_server_events) > 5:
    print(f"⚠️ Server has {len(failed_server_events)} failed operations")

# Performance monitoring
tool_events = store.get_events_by_type("tool_invocation")
slow_operations = [
    e for e in tool_events 
    if e.duration_ms and e.duration_ms > 1000
]

if slow_operations:
    print(f"⚠️ {len(slow_operations)} slow operations detected")
```

#### Thread-Safe Concurrent Access
```python
import threading
from concurrent.futures import ThreadPoolExecutor

store = get_audit_store()

def worker_thread(worker_id: int):
    """Worker thread adding events concurrently."""
    for i in range(100):
        event = AuditEvent.create_event(
            event_type="test",
            actor_user_id=f"worker-{worker_id}",
            actor_client_id="concurrent-client",
            server_id="test-server",
            status="success"
        )
        store.add_event(event)

# Run multiple threads concurrently
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(worker_thread, i) for i in range(5)]
    for future in futures:
        future.result()

print(f"Total events after concurrent access: {store.count()}")
```

## High-Level Logging Functions

The audit module provides convenient high-level functions for common logging scenarios with thread-safe, non-blocking operations.

### log_audit_event Function

The primary logging function that creates events, stores them, and outputs JSON to stdout for container logging:

```python
from mcp_gateway.audit.audit_logger import log_audit_event

# Basic tool invocation logging
event = log_audit_event(
    event_type="tool_invocation",
    actor_user_id="user-123",
    actor_client_id="agent-app", 
    server_id="filesystem",
    tool_name="read_file",
    status="success",
    duration_ms=150,
    policy_allowed=True,
    params_hash="sha256:abc123",
    output_hash="sha256:def456"
)

# Authentication failure logging  
event = log_audit_event(
    event_type="auth",
    actor_user_id="unknown",
    actor_client_id="web-client",
    server_id="gateway", 
    status="error",
    error_code="INVALID_TOKEN",
    error_message="JWT signature verification failed",
    source_ip="192.168.1.100"
)
```

**Key Features:**
- **Thread-safe**: Safe for concurrent calls across multiple threads
- **Non-blocking**: Synchronous implementation optimized for performance
- **Container-friendly**: JSON output to stdout for log aggregation
- **Auto-storage**: Automatically adds to AuditStore singleton
- **Complete logging**: Structured logs with full event context

### Convenience Functions

Specialized functions for common event types:

```python
from mcp_gateway.audit.audit_logger import (
    log_tool_invocation,
    log_auth_event,
    log_policy_event
)# Tool invocation with full context
event = log_tool_invocation(
    actor_user_id="user-456",
    actor_client_id="vscode-copilot",
    server_id="filesystem",
    tool_name="write_file", 
    status="success",
    duration_ms=200,
    params_hash="sha256:params123",
    scopes=["mcp:write", "filesystem:access"]
)

# Authentication event
event = log_auth_event(
    actor_user_id="user-456",
    actor_client_id="mobile-app",
    status="success",
    source_ip="192.168.1.50",
    scopes=["mcp:read", "mcp:write"]
)

# Policy evaluation  
event = log_policy_event(
    actor_user_id="user-789",
    actor_client_id="web-app",
    server_id="database",
    tool_name="delete_table",
    policy_allowed=False,
    error_code="INSUFFICIENT_PERMISSIONS",
    error_message="User lacks admin role"
)
```

### Audit Summary Function

Get comprehensive system statistics:

```python
from mcp_gateway.audit.audit_logger import get_audit_summary

summary = get_audit_summary()
print(f"Total events: {summary['total_events']}")
print(f"Success rate: {summary['success_rate']:.1%}")
print(f"Recent failures: {len(summary['recent_failures'])}")

# Event type breakdown
for event_type, count in summary['event_types'].items():
    print(f"{event_type}: {count}")
```

## AuditEvent Model

The `AuditEvent` class is the core model for audit logging. It captures comprehensive information about operations performed through the MCP Gateway.

- **Auto-generated identifiers**: Automatic UUID and timestamp generation
- **Comprehensive context**: Full request/response tracking with hashes
- **Structured metadata**: Flexible additional context storage
- **Serialization ready**: Built-in dictionary conversion for logging/storage
- **Type safety**: Full Pydantic validation and type hints

### Core Fields

#### Required Fields
- `event_id`: Unique UUID4 identifier for the event
- `timestamp`: UTC ISO 8601 timestamp (e.g., "2024-01-15T10:30:00.123Z")
- `event_type`: Type of event ("tool_invocation", "auth", "policy", etc.)
- `actor_user_id`: User identifier who initiated the action
- `actor_client_id`: Client application identifier
- `server_id`: Target MCP server or "gateway" for gateway operations
- `status`: Operation outcome ("success", "error", "denied", "timeout", "partial")

#### Optional Fields
- `tool_name`: Name of the invoked MCP tool (for tool invocations)
- `params_hash`: SHA-256 hash of request parameters
- `output_hash`: SHA-256 hash of response output
- `duration_ms`: Operation duration in milliseconds
- `policy_allowed`: Policy engine decision (boolean)
- `request_id`: Request correlation ID
- `session_id`: User session identifier
- `user_agent`: Client user agent string
- `source_ip`: Source IP address
- `scopes`: User scopes active during operation
- `error_code`: Error code for failed operations
- `error_message`: Human-readable error description
- `metadata`: Additional event-specific data (JSON object)

## Usage Examples

### Creating Audit Events

#### Tool Invocation Event
```python
from mcp_gateway.audit import AuditEvent

# Successful tool invocation
tool_event = AuditEvent.create_event(
    event_type="tool_invocation",
    actor_user_id="user-12345",
    actor_client_id="ai-agent",
    server_id="filesystem",
    tool_name="read_file",
    status="success",
    duration_ms=150,
    params_hash="sha256:abc123...",
    output_hash="sha256:def456...",
    request_id="req-789",
    session_id="session-456",
    scopes=["mcp:read", "filesystem:access"],
    policy_allowed=True,
    metadata={
        "file_path": "/workspace/data.txt",
        "file_size": 1024
    }
)
```

#### Authentication Event
```python
# Authentication failure
auth_event = AuditEvent.create_event(
    event_type="auth",
    actor_user_id="unknown",
    actor_client_id="web-client",
    server_id="gateway",
    status="error",
    error_code="INVALID_TOKEN",
    error_message="JWT token validation failed",
    source_ip="192.168.1.100",
    user_agent="Mozilla/5.0...",
    metadata={
        "token_type": "Bearer",
        "failure_reason": "token_expired"
    }
)
```

#### Policy Decision Event
```python
# Access denied by policy
policy_event = AuditEvent.create_event(
    event_type="policy",
    actor_user_id="user-67890",
    actor_client_id="app",
    server_id="database",
    tool_name="delete_table",
    status="denied",
    policy_allowed=False,
    scopes=["mcp:read"],
    error_code="INSUFFICIENT_PERMISSIONS",
    error_message="Operation requires admin scope",
    metadata={
        "required_scopes": ["database:admin"],
        "risk_level": "high"
    }
)
```

### Working with Audit Events

#### Serialization for Logging
```python
# Convert to dictionary for structured logging
event_dict = audit_event.to_dict()
logger.info("Audit event", extra=event_dict)

# Optimized format for log aggregation
log_dict = audit_event.to_log_dict()
logger.info("Operation completed", **log_dict)
```

#### JSON Serialization
```python
import json

# Serialize for API responses or storage
json_data = json.dumps(audit_event.to_dict())

# Parse back from JSON
parsed_dict = json.loads(json_data)
```

#### Metadata Operations
```python
# Add metadata dynamically
audit_event.add_metadata("request_size", 1024)
audit_event.add_metadata("compression", "gzip")

# Retrieve metadata
size = audit_event.get_metadata("request_size")
unknown = audit_event.get_metadata("unknown_key", "default_value")
```

#### Status and Type Checking
```python
# Check operation outcome
if audit_event.is_success:
    print("Operation succeeded")
elif audit_event.is_failure:
    print("Operation failed")

# Check event type
if audit_event.is_tool_invocation:
    print(f"Tool {audit_event.tool_name} was called")
elif audit_event.is_auth_event:
    print("Authentication event")
elif audit_event.is_policy_event:
    print("Policy evaluation event")
```

## Integration Patterns

### Complete Import Reference

For comprehensive audit logging functionality, import all components:

```python
from mcp_gateway.audit import (
    # Core models and store
    AuditEvent, 
    AuditStore, 
    get_audit_store,
    
    # High-level logging functions
    log_audit_event,
    log_tool_invocation,
    log_auth_event, 
    log_policy_event,
    get_audit_summary
)
```

### Production Integration Example

```python
from mcp_gateway.audit import log_audit_event, get_audit_store
import time

class ToolInvocationService:
    async def invoke_tool(self, user_context, server_id, tool_name, params):
        start_time = time.time()
        
        try:
            # Perform tool invocation
            result = await self._call_mcp_tool(server_id, tool_name, params)
            
            # Log successful invocation
            log_audit_event(
                event_type="tool_invocation",
                actor_user_id=user_context.user_id,
                actor_client_id=user_context.client_id,
                server_id=server_id,
                tool_name=tool_name,
                status="success",
                duration_ms=int((time.time() - start_time) * 1000),
                policy_allowed=True
            )
            
            return result
            
        except Exception as e:
            # Log failed invocation  
            log_audit_event(
                event_type="tool_invocation",
                actor_user_id=user_context.user_id,
                actor_client_id=user_context.client_id,
                server_id=server_id,
                tool_name=tool_name,
                status="error",
                duration_ms=int((time.time() - start_time) * 1000),
                error_code=type(e).__name__,
                error_message=str(e)
            )
            raise
```

### Middleware Integration with AuditStore
```python
from mcp_gateway.audit import AuditEvent, get_audit_store
from mcp_gateway.core.logging import get_logger

logger = get_logger(__name__)
audit_store = get_audit_store()

async def audit_middleware(request, call_next):
    start_time = time.time()
    
    try:
        response = await call_next(request)
        
        # Create and store success audit event
        audit_event = AuditEvent.create_event(
            event_type="tool_invocation",
            actor_user_id=request.user.user_id,
            actor_client_id=request.user.client_id,
            server_id=request.path_params.get("server_id"),
            tool_name=request.json().get("method"),
            status="success",
            duration_ms=int((time.time() - start_time) * 1000),
            request_id=request.headers.get("X-Request-ID"),
            session_id=request.user.session_id,
            source_ip=request.client.host,
            scopes=request.user.scopes
        )
        
        # Store in memory and log
        audit_store.add_event(audit_event)
        logger.info("Tool invocation completed", **audit_event.to_log_dict())
        return response
        
    except Exception as e:
        # Create and store failure audit event
        audit_event = AuditEvent.create_event(
            event_type="tool_invocation",
            actor_user_id=getattr(request.user, 'user_id', 'unknown'),
            actor_client_id=getattr(request.user, 'client_id', 'unknown'),
            server_id=request.path_params.get("server_id", "unknown"),
            status="error",
            duration_ms=int((time.time() - start_time) * 1000),
            error_code=type(e).__name__,
            error_message=str(e),
            source_ip=request.client.host
        )
        
        audit_store.add_event(audit_event)
        logger.error("Tool invocation failed", **audit_event.to_log_dict())
        raise
```

### Service Integration with Monitoring
```python
class AuditService:
    def __init__(self):
        self.logger = get_logger(__name__)
        self.store = get_audit_store()
    
    async def log_and_monitor_tool_invocation(self, user_context, server_id, 
                                            tool_name, params, result, 
                                            duration_ms, policy_allowed):
        """Log tool invocation and check for alerts."""
        
        # Create parameter and output hashes for privacy
        params_hash = hashlib.sha256(
            json.dumps(params, sort_keys=True).encode()
        ).hexdigest()
        
        output_hash = hashlib.sha256(
            json.dumps(result, sort_keys=True).encode()
        ).hexdigest()
        
        audit_event = AuditEvent.create_event(
            event_type="tool_invocation",
            actor_user_id=user_context.user_id,
            actor_client_id=user_context.client_id,
            server_id=server_id,
            tool_name=tool_name,
            status="success",
            duration_ms=duration_ms,
            params_hash=f"sha256:{params_hash}",
            output_hash=f"sha256:{output_hash}",
            session_id=user_context.session_id,
            scopes=user_context.scopes,
            policy_allowed=policy_allowed
        )
        
        # Store and log
        self.store.add_event(audit_event)
        self.logger.info("Tool invocation audit", **audit_event.to_log_dict())
        
        # Check for monitoring alerts
        await self._check_performance_alerts(duration_ms, tool_name)
        await self._check_user_activity_alerts(user_context.user_id)
    
    async def _check_performance_alerts(self, duration_ms: int, tool_name: str):
        """Check for performance-related alerts."""
        if duration_ms > 5000:  # 5 second threshold
            recent_slow = [
                e for e in self.store.get_events_by_type("tool_invocation", limit=100)
                if e.tool_name == tool_name and e.duration_ms and e.duration_ms > 5000
            ]
            
            if len(recent_slow) > 5:
                self.logger.warning(
                    f"Performance alert: {tool_name} has {len(recent_slow)} slow executions",
                    tool_name=tool_name,
                    slow_execution_count=len(recent_slow),
                    latest_duration_ms=duration_ms
                )
    
    async def _check_user_activity_alerts(self, user_id: str):
        """Check for suspicious user activity."""
        user_events = self.store.get_events_by_user(user_id, limit=50)
        recent_failures = [e for e in user_events if e.status != "success"]
        
        if len(recent_failures) > 10:
            self.logger.warning(
                f"Security alert: User {user_id} has {len(recent_failures)} recent failures",
                user_id=user_id,
                failure_count=len(recent_failures),
                total_recent_events=len(user_events)
            )
    
    async def get_security_summary(self) -> dict:
        """Get security summary from audit store."""
        stats = self.store.get_stats()
        auth_events = self.store.get_events_by_type("auth", limit=100)
        auth_failures = [e for e in auth_events if e.status == "error"]
        policy_denials = self.store.get_events_by_type("policy", limit=100)
        denied_policies = [e for e in policy_denials if e.status == "denied"]
        
        return {
            "total_events": stats["total_events"],
            "success_rate": stats["success_rate"],
            "auth_failure_count": len(auth_failures),
            "policy_denial_count": len(denied_policies),
            "recent_failures": self.store.get_failed_events(limit=10)
        }
```

### Real-time Monitoring Dashboard
```python
class AuditDashboard:
    def __init__(self):
        self.store = get_audit_store()
    
    def get_dashboard_data(self) -> dict:
        """Get real-time dashboard data from audit store."""
        stats = self.store.get_stats()
        recent_events = self.store.get_events(limit=20)
        recent_failures = self.store.get_failed_events(limit=10)
        
        # Performance metrics
        tool_events = self.store.get_events_by_type("tool_invocation", limit=100)
        durations = [e.duration_ms for e in tool_events if e.duration_ms]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            "overview": {
                "total_events": stats["total_events"],
                "success_rate": stats["success_rate"],
                "failure_rate": stats["failure_rate"],
                "avg_response_time_ms": avg_duration
            },
            "recent_activity": [
                {
                    "timestamp": e.timestamp,
                    "type": e.event_type,
                    "user": e.actor_user_id,
                    "status": e.status,
                    "server": e.server_id
                }
                for e in recent_events
            ],
            "alerts": [
                {
                    "timestamp": e.timestamp,
                    "message": f"{e.event_type} failed: {e.error_message}",
                    "user": e.actor_user_id,
                    "severity": "high" if e.event_type == "auth" else "medium"
                }
                for e in recent_failures
            ],
            "event_types": stats["event_types"],
            "status_distribution": stats["status_counts"]
        }
    
    def get_user_activity(self, user_id: str) -> dict:
        """Get activity summary for a specific user."""
        user_events = self.store.get_events_by_user(user_id, limit=100)
        
        if not user_events:
            return {"error": "No events found for user"}
        
        failed_events = [e for e in user_events if e.status != "success"]
        tool_usage = {}
        for event in user_events:
            if event.tool_name:
                tool_usage[event.tool_name] = tool_usage.get(event.tool_name, 0) + 1
        
        return {
            "user_id": user_id,
            "total_events": len(user_events),
            "failed_events": len(failed_events),
            "success_rate": (len(user_events) - len(failed_events)) / len(user_events),
            "most_recent_activity": user_events[0].timestamp,
            "tool_usage": tool_usage,
            "recent_events": [
                {
                    "timestamp": e.timestamp,
                    "type": e.event_type,
                    "status": e.status,
                    "tool": e.tool_name,
                    "server": e.server_id
                }
                for e in user_events[:10]
            ]
        }
```
```python
from mcp_gateway.audit import AuditEvent
from mcp_gateway.core.logging import get_logger

logger = get_logger(__name__)

async def audit_middleware(request, call_next):
    start_time = time.time()
    
    try:
        response = await call_next(request)
        
        # Create success audit event
        audit_event = AuditEvent.create_event(
            event_type="tool_invocation",
            actor_user_id=request.user.user_id,
            actor_client_id=request.user.client_id,
            server_id=request.path_params.get("server_id"),
            tool_name=request.json().get("method"),
            status="success",
            duration_ms=int((time.time() - start_time) * 1000),
            request_id=request.headers.get("X-Request-ID"),
            session_id=request.user.session_id,
            source_ip=request.client.host,
            scopes=request.user.scopes
        )
        
        logger.info("Tool invocation completed", **audit_event.to_log_dict())
        return response
        
    except Exception as e:
        # Create failure audit event
        audit_event = AuditEvent.create_event(
            event_type="tool_invocation",
            actor_user_id=getattr(request.user, 'user_id', 'unknown'),
            actor_client_id=getattr(request.user, 'client_id', 'unknown'),
            server_id=request.path_params.get("server_id", "unknown"),
            status="error",
            duration_ms=int((time.time() - start_time) * 1000),
            error_code=type(e).__name__,
            error_message=str(e),
            source_ip=request.client.host
        )
        
        logger.error("Tool invocation failed", **audit_event.to_log_dict())
        raise
```

### Service Integration
```python
class AuditService:
    def __init__(self):
        self.logger = get_logger(__name__)
    
    async def log_tool_invocation(self, user_context, server_id, tool_name, 
                                 params, result, duration_ms, policy_allowed):
        """Log a tool invocation audit event."""
        
        # Create parameter and output hashes for privacy
        params_hash = hashlib.sha256(
            json.dumps(params, sort_keys=True).encode()
        ).hexdigest()
        
        output_hash = hashlib.sha256(
            json.dumps(result, sort_keys=True).encode()
        ).hexdigest()
        
        audit_event = AuditEvent.create_event(
            event_type="tool_invocation",
            actor_user_id=user_context.user_id,
            actor_client_id=user_context.client_id,
            server_id=server_id,
            tool_name=tool_name,
            status="success",
            duration_ms=duration_ms,
            params_hash=f"sha256:{params_hash}",
            output_hash=f"sha256:{output_hash}",
            session_id=user_context.session_id,
            scopes=user_context.scopes,
            policy_allowed=policy_allowed
        )
        
        self.logger.info("Tool invocation audit", **audit_event.to_log_dict())
    
    async def log_auth_failure(self, client_id, source_ip, user_agent, 
                              error_code, error_message):
        """Log an authentication failure audit event."""
        
        audit_event = AuditEvent.create_event(
            event_type="auth",
            actor_user_id="unknown",
            actor_client_id=client_id or "unknown",
            server_id="gateway",
            status="error",
            error_code=error_code,
            error_message=error_message,
            source_ip=source_ip,
            user_agent=user_agent,
            metadata={
                "auth_method": "OIDC",
                "failure_category": "token_validation"
            }
        )
        
        self.logger.warning("Authentication failure", **audit_event.to_log_dict())
```

## Best Practices

### 1. Hash Sensitive Data
Always hash request parameters and responses rather than logging them directly:
```python
import hashlib
import json

params_hash = hashlib.sha256(
    json.dumps(params, sort_keys=True).encode()
).hexdigest()

audit_event = AuditEvent.create_event(
    # ... other fields ...
    params_hash=f"sha256:{params_hash}"
)
```

### 2. Use Correlation IDs
Include request IDs for tracing across services:
```python
request_id = str(uuid.uuid4())
# Pass request_id through all service calls

audit_event = AuditEvent.create_event(
    # ... other fields ...
    request_id=request_id
)
```

### 3. Structured Metadata
Use consistent metadata structures:
```python
metadata = {
    "operation_type": "read",
    "resource_type": "file",
    "resource_path": "/workspace/data.txt",
    "request_size_bytes": len(params),
    "response_size_bytes": len(result)
}

audit_event = AuditEvent.create_event(
    # ... other fields ...
    metadata=metadata
)
```

### 4. Error Context
Provide comprehensive error information:
```python
try:
    # ... operation ...
except SpecificError as e:
    audit_event = AuditEvent.create_event(
        # ... other fields ...
        status="error",
        error_code="SPECIFIC_ERROR_CODE",
        error_message=str(e),
        metadata={
            "error_type": type(e).__name__,
            "stack_trace": traceback.format_exc(),
            "retry_count": retry_count
        }
    )
```

### 5. Performance Tracking
Always include timing information:
```python
start_time = time.time()
try:
    # ... operation ...
    status = "success"
except Exception:
    status = "error"
    raise
finally:
    duration_ms = int((time.time() - start_time) * 1000)
    
    audit_event = AuditEvent.create_event(
        # ... other fields ...
        status=status,
        duration_ms=duration_ms
    )
```

## Event Types

### Standard Event Types
- `tool_invocation`: MCP tool calls
- `auth`: Authentication events
- `policy`: Authorization/policy decisions
- `service_discovery`: Service discovery operations
- `health_check`: Health check operations
- `error`: System errors and exceptions

### Status Values
- `success`: Operation completed successfully
- `error`: Operation failed due to an error
- `denied`: Operation denied by policy/authorization
- `timeout`: Operation timed out
- `partial`: Operation partially completed

## Integration with Existing Systems

### Structured Logging
The audit events integrate seamlessly with the existing structured logging system:
```python
from mcp_gateway.core.logging import get_logger

logger = get_logger(__name__)

# Direct logging
logger.info("Audit event", **audit_event.to_log_dict())

# With additional context
logger.error(
    "Operation failed", 
    **audit_event.to_log_dict(),
    additional_context="some_value"
)
```

### Metrics and Monitoring
Audit events can drive metrics collection:
```python
# Count events by type and status
metrics.counter("audit_events_total").labels(
    event_type=audit_event.event_type,
    status=audit_event.status
).inc()

# Track operation duration
if audit_event.duration_ms:
    metrics.histogram("operation_duration_ms").labels(
        event_type=audit_event.event_type,
        server_id=audit_event.server_id
    ).observe(audit_event.duration_ms)
```

## Security Considerations

1. **Data Privacy**: Never log sensitive data directly; use hashes
2. **Access Control**: Ensure audit logs are properly secured
3. **Retention**: Implement appropriate log retention policies
4. **Integrity**: Consider audit log signing for compliance
5. **Monitoring**: Alert on suspicious audit patterns

## Compliance Features

The audit module supports enterprise compliance requirements:

- **Complete traceability**: Every operation is auditable
- **Immutable events**: Once created, events should not be modified
- **Correlation**: Request IDs enable end-to-end tracing
- **Privacy-preserving**: Sensitive data is hashed, not logged
- **Structured format**: Consistent JSON format for automated processing
- **Comprehensive context**: Full user, client, and operation context
