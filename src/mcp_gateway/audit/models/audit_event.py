"""
Audit event model for tracking MCP Gateway operations.

This module contains the AuditEvent model which captures comprehensive audit
information for all significant operations within the MCP Gateway, including
tool invocations, authentication events, policy decisions, and system operations.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    """
    Comprehensive audit event model for MCP Gateway operations.
    
    This model captures detailed audit information for compliance, security monitoring,
    and operational observability. It tracks all significant interactions including
    tool invocations, authentication events, authorization decisions, and system events.
    
    The audit event is designed to provide complete traceability of user actions,
    system decisions, and service interactions while supporting compliance requirements
    for enterprise environments.
    
    Example:
        # Create a tool invocation audit event
        event = AuditEvent.create_event(
            event_type="tool_invocation",
            actor_user_id="user-123",
            actor_client_id="agent-app",
            server_id="filesystem",
            tool_name="read_file",
            params_hash="sha256:abc123...",
            status="success",
            duration_ms=150
        )
        
        # Create an authentication event
        auth_event = AuditEvent.create_event(
            event_type="auth",
            actor_user_id="user-456",
            actor_client_id="web-client",
            server_id="gateway",
            status="success"
        )
    """
    
    # Core event identification and timing
    event_id: str = Field(
        ...,
        description="Unique event identifier (UUID4 string) for correlation and tracking"
    )
    
    timestamp: str = Field(
        ...,
        description="Event timestamp in UTC ISO 8601 format (e.g., '2024-01-15T10:30:00.123Z')"
    )
    
    # Event classification
    event_type: str = Field(
        ...,
        description="Type of event: 'tool_invocation', 'auth', 'policy', 'service_discovery', 'health_check', 'error'"
    )
    
    # Actor identification (who performed the action)
    actor_user_id: str = Field(
        ...,
        description="User identifier from token subject (sub claim) who initiated the action"
    )
    
    actor_client_id: str = Field(
        ...,
        description="Client application identifier (aud claim) that made the request"
    )
    
    # Target/resource identification (what was acted upon)
    server_id: str = Field(
        ...,
        description="Target MCP server identifier or 'gateway' for gateway-level operations"
    )
    
    tool_name: Optional[str] = Field(
        None,
        description="Name of the MCP tool that was invoked (for tool_invocation events)"
    )
    
    # Request/response tracking
    params_hash: Optional[str] = Field(
        None,
        description="SHA-256 hash of request parameters (for privacy and integrity verification)"
    )
    
    output_hash: Optional[str] = Field(
        None,
        description="SHA-256 hash of response output (for integrity verification)"
    )
    
    # Operation outcome
    status: str = Field(
        ...,
        description="Operation status: 'success', 'error', 'denied', 'timeout', 'partial'"
    )
    
    duration_ms: Optional[int] = Field(
        None,
        ge=0,
        description="Operation duration in milliseconds (for performance monitoring)"
    )
    
    # Authorization and policy tracking
    policy_allowed: Optional[bool] = Field(
        None,
        description="Whether the operation was allowed by policy engine (True/False/None for N/A)"
    )
    
    # Additional context fields based on codebase analysis
    request_id: Optional[str] = Field(
        None,
        description="Request correlation ID for tracing across services"
    )
    
    session_id: Optional[str] = Field(
        None,
        description="User session identifier from token claims"
    )
    
    user_agent: Optional[str] = Field(
        None,
        description="Client user agent string for client identification"
    )
    
    source_ip: Optional[str] = Field(
        None,
        description="Source IP address of the request (for security monitoring)"
    )
    
    scopes: Optional[list[str]] = Field(
        None,
        description="User scopes that were active during the operation"
    )
    
    error_code: Optional[str] = Field(
        None,
        description="Error code for failed operations (e.g., 'AUTH_FAILED', 'POLICY_DENIED')"
    )
    
    error_message: Optional[str] = Field(
        None,
        description="Human-readable error message for failed operations"
    )
    
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional event-specific metadata (JSON object)"
    )
    
    @classmethod
    def create_event(
        cls,
        event_type: str,
        actor_user_id: str,
        actor_client_id: str,
        server_id: str,
        status: str,
        tool_name: Optional[str] = None,
        params_hash: Optional[str] = None,
        output_hash: Optional[str] = None,
        duration_ms: Optional[int] = None,
        policy_allowed: Optional[bool] = None,
        request_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        source_ip: Optional[str] = None,
        scopes: Optional[list[str]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "AuditEvent":
        """
        Create a new audit event with auto-generated ID and timestamp.
        
        This factory method creates a complete audit event with automatic
        generation of the event ID and timestamp, ensuring consistency
        and reducing boilerplate code when creating audit events.
        
        Args:
            event_type: Type of event being audited
            actor_user_id: User who performed the action
            actor_client_id: Client application that made the request
            server_id: Target server or 'gateway' for gateway operations
            status: Operation outcome status
            tool_name: Tool name for tool invocation events
            params_hash: Hash of request parameters
            output_hash: Hash of response output
            duration_ms: Operation duration in milliseconds
            policy_allowed: Policy decision result
            request_id: Request correlation ID
            session_id: User session identifier
            user_agent: Client user agent
            source_ip: Source IP address
            scopes: User scopes during operation
            error_code: Error code for failures
            error_message: Error message for failures
            metadata: Additional event metadata
            
        Returns:
            AuditEvent: Complete audit event ready for logging
            
        Example:
            # Tool invocation audit
            event = AuditEvent.create_event(
                event_type="tool_invocation",
                actor_user_id="user-123",
                actor_client_id="agent-app",
                server_id="filesystem",
                tool_name="read_file",
                status="success",
                duration_ms=150,
                params_hash="sha256:abc123...",
                request_id="req-456"
            )
            
            # Authentication failure audit
            auth_event = AuditEvent.create_event(
                event_type="auth",
                actor_user_id="unknown",
                actor_client_id="web-client",
                server_id="gateway",
                status="error",
                error_code="INVALID_TOKEN",
                error_message="JWT token validation failed",
                source_ip="192.168.1.100"
            )
        """
        return cls(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            event_type=event_type,
            actor_user_id=actor_user_id,
            actor_client_id=actor_client_id,
            server_id=server_id,
            tool_name=tool_name,
            params_hash=params_hash,
            output_hash=output_hash,
            status=status,
            duration_ms=duration_ms,
            policy_allowed=policy_allowed,
            request_id=request_id,
            session_id=session_id,
            user_agent=user_agent,
            source_ip=source_ip,
            scopes=scopes,
            error_code=error_code,
            error_message=error_message,
            metadata=metadata or {}
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert audit event to dictionary for serialization and logging.
        
        This method provides a clean dictionary representation of the audit event
        suitable for JSON serialization, database storage, or structured logging.
        It excludes None values to keep the output clean and compact.
        
        Returns:
            Dict[str, Any]: Dictionary representation with non-None values
            
        Example:
            event = AuditEvent.create_event(...)
            event_dict = event.to_dict()
            
            # Use for structured logging
            logger.info("Audit event", extra=event_dict)
            
            # Use for JSON API response
            return {"audit_event": event_dict}
            
            # Use for database storage
            db.audit_events.insert_one(event_dict)
        """
        # Get the model dictionary and exclude None values
        data = self.model_dump(exclude_none=True)
        
        # Ensure metadata is always present as an empty dict if not set
        if 'metadata' not in data:
            data['metadata'] = {}
            
        return data
    
    def to_log_dict(self) -> Dict[str, Any]:
        """
        Convert audit event to dictionary optimized for structured logging.
        
        This method creates a logging-optimized representation that includes
        common fields for log aggregation and analysis while maintaining
        the complete audit information.
        
        Returns:
            Dict[str, Any]: Logging-optimized dictionary representation
        """
        base_dict = self.to_dict()
        
        # Add logging-specific fields for better log aggregation
        log_dict = {
            "audit_event_id": self.event_id,
            "audit_timestamp": self.timestamp,
            "audit_type": self.event_type,
            "user_id": self.actor_user_id,
            "client_id": self.actor_client_id,
            "target_server": self.server_id,
            "operation_status": self.status,
            **base_dict
        }
        
        return log_dict
    
    @property
    def is_success(self) -> bool:
        """
        Check if the audited operation was successful.
        
        Returns:
            bool: True if status indicates success
        """
        return self.status == "success"
    
    @property
    def is_failure(self) -> bool:
        """
        Check if the audited operation failed.
        
        Returns:
            bool: True if status indicates failure
        """
        return self.status in ["error", "denied", "timeout"]
    
    @property
    def is_tool_invocation(self) -> bool:
        """
        Check if this is a tool invocation event.
        
        Returns:
            bool: True if this is a tool invocation audit event
        """
        return self.event_type == "tool_invocation"
    
    @property
    def is_auth_event(self) -> bool:
        """
        Check if this is an authentication event.
        
        Returns:
            bool: True if this is an authentication audit event
        """
        return self.event_type == "auth"
    
    @property
    def is_policy_event(self) -> bool:
        """
        Check if this is a policy evaluation event.
        
        Returns:
            bool: True if this is a policy audit event
        """
        return self.event_type == "policy"
    
    def add_metadata(self, key: str, value: Any) -> None:
        """
        Add metadata to the audit event.
        
        Args:
            key: Metadata key
            value: Metadata value
        """
        if self.metadata is None:
            self.metadata = {}
        self.metadata[key] = value
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Get metadata value by key.
        
        Args:
            key: Metadata key to retrieve
            default: Default value if key not found
            
        Returns:
            Any: Metadata value or default
        """
        if self.metadata is None:
            return default
        return self.metadata.get(key, default)
