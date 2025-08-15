"""
Audit logging functions for MCP Gateway.

This module provides high-level functions for audit logging that integrate
the AuditEvent model with the AuditStore and provide convenient logging
to stdout for container-based deployments.
"""

import json
import sys
import threading
from typing import Optional, List, Dict, Any

from .models.audit_event import AuditEvent
from .store import get_audit_store


# Thread-safe print lock for concurrent stdout access
_print_lock = threading.Lock()


def log_audit_event(
    event_type: str,
    actor_user_id: str,
    actor_client_id: str,
    server_id: str,
    tool_name: Optional[str] = None,
    params_hash: Optional[str] = None,
    output_hash: Optional[str] = None,
    status: str = "success",
    duration_ms: Optional[int] = None,
    policy_allowed: Optional[bool] = None,
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
    user_agent: Optional[str] = None,
    source_ip: Optional[str] = None,
    scopes: Optional[List[str]] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AuditEvent:
    """
    Create, store, and log an audit event for MCP Gateway operations.
    
    This function provides a complete audit logging solution that:
    1. Creates an AuditEvent using the static factory method
    2. Stores the event in the thread-safe AuditStore
    3. Outputs the event as JSON to stdout for container logs
    4. Returns the created event for further use
    
    The function is thread-safe and non-blocking, making it suitable for
    high-concurrency environments and real-time audit logging.
    
    Args:
        event_type: Type of event (e.g., 'tool_invocation', 'auth', 'policy')
        actor_user_id: User identifier who initiated the action
        actor_client_id: Client application identifier
        server_id: Target MCP server or 'gateway' for gateway operations
        tool_name: Name of the invoked tool (optional)
        params_hash: SHA-256 hash of request parameters (optional)
        output_hash: SHA-256 hash of response output (optional)
        status: Operation status (default: 'success')
        duration_ms: Operation duration in milliseconds (optional)
        policy_allowed: Policy engine decision (optional)
        request_id: Request correlation ID (optional)
        session_id: User session identifier (optional)
        user_agent: Client user agent string (optional)
        source_ip: Source IP address (optional)
        scopes: User scopes during operation (optional)
        error_code: Error code for failed operations (optional)
        error_message: Error message for failed operations (optional)
        metadata: Additional event-specific data (optional)
        
    Returns:
        AuditEvent: The created and stored audit event
        
    Example:
        # Log a successful tool invocation
        event = log_audit_event(
            event_type="tool_invocation",
            actor_user_id="user-123",
            actor_client_id="vscode-copilot",
            server_id="filesystem",
            tool_name="read_file",
            status="success",
            duration_ms=150,
            params_hash="sha256:abc123...",
            scopes=["mcp:read", "filesystem:access"]
        )
        
        # Log an authentication failure
        log_audit_event(
            event_type="auth",
            actor_user_id="unknown",
            actor_client_id="suspicious-app",
            server_id="gateway",
            status="error",
            error_code="INVALID_TOKEN",
            error_message="JWT signature verification failed",
            source_ip="192.168.1.100"
        )
        
        # Log a policy denial
        log_audit_event(
            event_type="policy",
            actor_user_id="user-456",
            actor_client_id="restricted-client",
            server_id="database",
            tool_name="delete_table",
            status="denied",
            policy_allowed=False,
            error_code="INSUFFICIENT_PERMISSIONS",
            scopes=["mcp:read"]
        )
    """
    try:
        # 1. Create audit event using static factory method
        audit_event = AuditEvent.create_event(
            event_type=event_type,
            actor_user_id=actor_user_id,
            actor_client_id=actor_client_id,
            server_id=server_id,
            status=status,
            tool_name=tool_name,
            params_hash=params_hash,
            output_hash=output_hash,
            duration_ms=duration_ms,
            policy_allowed=policy_allowed,
            request_id=request_id,
            session_id=session_id,
            user_agent=user_agent,
            source_ip=source_ip,
            scopes=scopes,
            error_code=error_code,
            error_message=error_message,
            metadata=metadata
        )
        
        # 2. Add event to the audit store (thread-safe)
        store = get_audit_store()
        store.add_event(audit_event)
        
        # 3. Print event in JSON format to stdout for container logs (thread-safe)
        json_output = json.dumps(audit_event.to_log_dict(), separators=(',', ':'))
        
        with _print_lock:
            # Use print() which is thread-safe for line-buffered output
            print(json_output, file=sys.stdout, flush=True)
        
        return audit_event
        
    except Exception as e:
        # Fallback: ensure we don't break the application due to audit logging issues
        # Log the error to stderr and create a minimal event if possible
        error_msg = f"Audit logging error: {str(e)}"
        
        with _print_lock:
            print(json.dumps({
                "audit_error": error_msg,
                "event_type": event_type,
                "actor_user_id": actor_user_id,
                "status": "audit_failed"
            }), file=sys.stderr, flush=True)
        
        # Try to create a minimal event if the error wasn't in event creation
        try:
            minimal_event = AuditEvent.create_event(
                event_type="error",
                actor_user_id=actor_user_id,
                actor_client_id=actor_client_id,
                server_id="audit_system",
                status="error",
                error_code="AUDIT_LOGGING_FAILED",
                error_message=error_msg
            )
            
            # Try to store the error event
            store = get_audit_store()
            store.add_event(minimal_event)
            
            return minimal_event
            
        except Exception:
            # If even minimal event creation fails, return None
            # This ensures the function doesn't crash the application
            return None


def log_tool_invocation(
    actor_user_id: str,
    actor_client_id: str,
    server_id: str,
    tool_name: str,
    status: str = "success",
    duration_ms: Optional[int] = None,
    params_hash: Optional[str] = None,
    output_hash: Optional[str] = None,
    policy_allowed: Optional[bool] = None,
    request_id: Optional[str] = None,
    session_id: Optional[str] = None,
    scopes: Optional[List[str]] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> AuditEvent:
    """
    Convenience function for logging tool invocation events.
    
    Args:
        actor_user_id: User who invoked the tool
        actor_client_id: Client application
        server_id: Target MCP server
        tool_name: Name of the invoked tool
        status: Operation status (default: 'success')
        duration_ms: Execution time in milliseconds
        params_hash: Hash of input parameters
        output_hash: Hash of output data
        policy_allowed: Policy decision
        request_id: Request correlation ID
        session_id: User session ID
        scopes: User scopes
        error_code: Error code if failed
        error_message: Error message if failed
        metadata: Additional metadata
        
    Returns:
        AuditEvent: The created audit event
        
    Example:
        log_tool_invocation(
            actor_user_id="user-123",
            actor_client_id="copilot",
            server_id="filesystem",
            tool_name="read_file",
            duration_ms=120,
            params_hash="sha256:abc123...",
            scopes=["mcp:read"]
        )
    """
    return log_audit_event(
        event_type="tool_invocation",
        actor_user_id=actor_user_id,
        actor_client_id=actor_client_id,
        server_id=server_id,
        tool_name=tool_name,
        status=status,
        duration_ms=duration_ms,
        params_hash=params_hash,
        output_hash=output_hash,
        policy_allowed=policy_allowed,
        request_id=request_id,
        session_id=session_id,
        scopes=scopes,
        error_code=error_code,
        error_message=error_message,
        metadata=metadata
    )


def log_auth_event(
    actor_user_id: str,
    actor_client_id: str,
    status: str = "success",
    source_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_id: Optional[str] = None,
    scopes: Optional[List[str]] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> AuditEvent:
    """
    Convenience function for logging authentication events.
    
    Args:
        actor_user_id: User being authenticated (or 'unknown' for failures)
        actor_client_id: Client application
        status: Authentication result (default: 'success')
        source_ip: Source IP address
        user_agent: Client user agent
        session_id: Session identifier
        scopes: Granted scopes
        error_code: Error code if failed
        error_message: Error message if failed
        metadata: Additional metadata
        
    Returns:
        AuditEvent: The created audit event
        
    Example:
        log_auth_event(
            actor_user_id="user-123",
            actor_client_id="web-client",
            status="success",
            source_ip="192.168.1.100",
            scopes=["mcp:read", "mcp:write"]
        )
    """
    return log_audit_event(
        event_type="auth",
        actor_user_id=actor_user_id,
        actor_client_id=actor_client_id,
        server_id="gateway",
        status=status,
        source_ip=source_ip,
        user_agent=user_agent,
        session_id=session_id,
        scopes=scopes,
        error_code=error_code,
        error_message=error_message,
        metadata=metadata
    )


def log_policy_event(
    actor_user_id: str,
    actor_client_id: str,
    server_id: str,
    policy_allowed: bool,
    tool_name: Optional[str] = None,
    status: str = "success",
    request_id: Optional[str] = None,
    scopes: Optional[List[str]] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> AuditEvent:
    """
    Convenience function for logging policy evaluation events.
    
    Args:
        actor_user_id: User subject to policy evaluation
        actor_client_id: Client application
        server_id: Target server/resource
        policy_allowed: Policy decision result
        tool_name: Tool being accessed (optional)
        status: Policy evaluation status (default: 'success')
        request_id: Request correlation ID
        scopes: User scopes evaluated
        error_code: Error code if evaluation failed
        error_message: Error message if evaluation failed
        metadata: Additional policy context
        
    Returns:
        AuditEvent: The created audit event
        
    Example:
        log_policy_event(
            actor_user_id="user-123",
            actor_client_id="app",
            server_id="database",
            policy_allowed=False,
            tool_name="delete_table",
            status="denied",
            scopes=["mcp:read"],
            error_code="INSUFFICIENT_PERMISSIONS"
        )
    """
    # Map policy decision to status if not explicitly provided
    if status == "success" and not policy_allowed:
        status = "denied"
    
    return log_audit_event(
        event_type="policy",
        actor_user_id=actor_user_id,
        actor_client_id=actor_client_id,
        server_id=server_id,
        tool_name=tool_name,
        status=status,
        policy_allowed=policy_allowed,
        request_id=request_id,
        scopes=scopes,
        error_code=error_code,
        error_message=error_message,
        metadata=metadata
    )


def get_audit_summary() -> Dict[str, Any]:
    """
    Get a summary of audit events from the store.
    
    Returns:
        dict: Summary statistics and recent events
        
    Example:
        summary = get_audit_summary()
        print(f"Total events: {summary['total_events']}")
        print(f"Success rate: {summary['success_rate']:.1%}")
    """
    store = get_audit_store()
    stats = store.get_stats()
    recent_events = store.get_events(limit=10)
    recent_failures = store.get_failed_events(limit=5)
    
    return {
        "total_events": stats["total_events"],
        "success_rate": stats["success_rate"],
        "failure_rate": stats["failure_rate"],
        "event_types": stats["event_types"],
        "status_counts": stats["status_counts"],
        "recent_events": [
            {
                "timestamp": event.timestamp,
                "type": event.event_type,
                "user": event.actor_user_id,
                "status": event.status,
                "server": event.server_id
            }
            for event in recent_events
        ],
        "recent_failures": [
            {
                "timestamp": event.timestamp,
                "type": event.event_type,
                "user": event.actor_user_id,
                "status": event.status,
                "error": event.error_message
            }
            for event in recent_failures
        ]
    }
