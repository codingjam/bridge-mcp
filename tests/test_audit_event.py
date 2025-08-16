"""
Unit tests for AuditEvent model.

This module contains comprehensive tests for the AuditEvent class to ensure
correct functionality for audit logging in the MCP Gateway.
"""

import uuid
import json
from datetime import datetime, timezone
from typing import Dict, Any

import pytest
from pydantic import ValidationError

from mcp_gateway.audit.models.audit_event import AuditEvent


class TestAuditEvent:
    """Test cases for AuditEvent model."""
    
    def test_create_event_minimal(self):
        """Test creating an audit event with minimal required fields."""
        event = AuditEvent.create_event(
            event_type="test",
            actor_user_id="user-123",
            actor_client_id="client-456",
            server_id="test-server",
            status="success"
        )
        
        assert event.event_type == "test"
        assert event.actor_user_id == "user-123"
        assert event.actor_client_id == "client-456"
        assert event.server_id == "test-server"
        assert event.status == "success"
        assert event.event_id is not None
        assert event.timestamp is not None
        assert event.metadata == {}
        
        # Verify UUID format
        uuid.UUID(event.event_id)  # Should not raise exception
        
        # Verify timestamp format
        datetime.fromisoformat(event.timestamp.replace('Z', '+00:00'))
    
    def test_create_event_full(self):
        """Test creating an audit event with all fields."""
        metadata = {"test_key": "test_value", "number": 123}
        scopes = ["scope1", "scope2"]
        
        event = AuditEvent.create_event(
            event_type="tool_invocation",
            actor_user_id="user-123",
            actor_client_id="client-456",
            server_id="filesystem",
            status="success",
            tool_name="read_file",
            params_hash="sha256:abc123",
            output_hash="sha256:def456",
            duration_ms=150,
            policy_allowed=True,
            request_id="req-789",
            session_id="session-123",
            user_agent="Test-Agent/1.0",
            source_ip="192.168.1.1",
            scopes=scopes,
            error_code=None,
            error_message=None,
            metadata=metadata
        )
        
        assert event.event_type == "tool_invocation"
        assert event.tool_name == "read_file"
        assert event.params_hash == "sha256:abc123"
        assert event.output_hash == "sha256:def456"
        assert event.duration_ms == 150
        assert event.policy_allowed is True
        assert event.request_id == "req-789"
        assert event.session_id == "session-123"
        assert event.user_agent == "Test-Agent/1.0"
        assert event.source_ip == "192.168.1.1"
        assert event.scopes == scopes
        assert event.metadata == metadata
    
    def test_manual_construction(self):
        """Test manually constructing an AuditEvent."""
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        event = AuditEvent(
            event_id=event_id,
            timestamp=timestamp,
            event_type="auth",
            actor_user_id="user-456",
            actor_client_id="client-789",
            server_id="gateway",
            status="error"
        )
        
        assert event.event_id == event_id
        assert event.timestamp == timestamp
        assert event.event_type == "auth"
        assert event.status == "error"
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        event = AuditEvent.create_event(
            event_type="test",
            actor_user_id="user-123",
            actor_client_id="client-456",
            server_id="test-server",
            status="success",
            duration_ms=100,
            metadata={"key": "value"}
        )
        
        event_dict = event.to_dict()
        
        assert isinstance(event_dict, dict)
        assert event_dict["event_type"] == "test"
        assert event_dict["actor_user_id"] == "user-123"
        assert event_dict["duration_ms"] == 100
        assert event_dict["metadata"] == {"key": "value"}
        
        # Should exclude None values
        assert "tool_name" not in event_dict
        assert "params_hash" not in event_dict
        
        # Should be JSON serializable
        json.dumps(event_dict)
    
    def test_to_log_dict(self):
        """Test conversion to logging-optimized dictionary."""
        event = AuditEvent.create_event(
            event_type="tool_invocation",
            actor_user_id="user-123",
            actor_client_id="client-456",
            server_id="filesystem",
            status="success"
        )
        
        log_dict = event.to_log_dict()
        
        assert isinstance(log_dict, dict)
        assert log_dict["audit_event_id"] == event.event_id
        assert log_dict["audit_timestamp"] == event.timestamp
        assert log_dict["audit_type"] == "tool_invocation"
        assert log_dict["user_id"] == "user-123"
        assert log_dict["client_id"] == "client-456"
        assert log_dict["target_server"] == "filesystem"
        assert log_dict["operation_status"] == "success"
        
        # Should also include original fields
        assert log_dict["event_id"] == event.event_id
        assert log_dict["event_type"] == "tool_invocation"
    
    def test_status_properties(self):
        """Test status check properties."""
        success_event = AuditEvent.create_event(
            event_type="test",
            actor_user_id="user-123",
            actor_client_id="client-456",
            server_id="test-server",
            status="success"
        )
        
        error_event = AuditEvent.create_event(
            event_type="test",
            actor_user_id="user-123",
            actor_client_id="client-456",
            server_id="test-server",
            status="error"
        )
        
        denied_event = AuditEvent.create_event(
            event_type="test",
            actor_user_id="user-123",
            actor_client_id="client-456",
            server_id="test-server",
            status="denied"
        )
        
        timeout_event = AuditEvent.create_event(
            event_type="test",
            actor_user_id="user-123",
            actor_client_id="client-456",
            server_id="test-server",
            status="timeout"
        )
        
        # Test is_success
        assert success_event.is_success is True
        assert error_event.is_success is False
        assert denied_event.is_success is False
        
        # Test is_failure
        assert success_event.is_failure is False
        assert error_event.is_failure is True
        assert denied_event.is_failure is True
        assert timeout_event.is_failure is True
    
    def test_event_type_properties(self):
        """Test event type check properties."""
        tool_event = AuditEvent.create_event(
            event_type="tool_invocation",
            actor_user_id="user-123",
            actor_client_id="client-456",
            server_id="test-server",
            status="success"
        )
        
        auth_event = AuditEvent.create_event(
            event_type="auth",
            actor_user_id="user-123",
            actor_client_id="client-456",
            server_id="test-server",
            status="success"
        )
        
        policy_event = AuditEvent.create_event(
            event_type="policy",
            actor_user_id="user-123",
            actor_client_id="client-456",
            server_id="test-server",
            status="success"
        )
        
        # Test tool invocation detection
        assert tool_event.is_tool_invocation is True
        assert auth_event.is_tool_invocation is False
        assert policy_event.is_tool_invocation is False
        
        # Test auth event detection
        assert tool_event.is_auth_event is False
        assert auth_event.is_auth_event is True
        assert policy_event.is_auth_event is False
        
        # Test policy event detection
        assert tool_event.is_policy_event is False
        assert auth_event.is_policy_event is False
        assert policy_event.is_policy_event is True
    
    def test_metadata_operations(self):
        """Test metadata manipulation methods."""
        event = AuditEvent.create_event(
            event_type="test",
            actor_user_id="user-123",
            actor_client_id="client-456",
            server_id="test-server",
            status="success"
        )
        
        # Test adding metadata
        event.add_metadata("key1", "value1")
        event.add_metadata("key2", 123)
        event.add_metadata("key3", {"nested": "object"})
        
        assert event.metadata["key1"] == "value1"
        assert event.metadata["key2"] == 123
        assert event.metadata["key3"] == {"nested": "object"}
        
        # Test getting metadata
        assert event.get_metadata("key1") == "value1"
        assert event.get_metadata("key2") == 123
        assert event.get_metadata("nonexistent") is None
        assert event.get_metadata("nonexistent", "default") == "default"
    
    def test_metadata_none_handling(self):
        """Test metadata handling when initially None."""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            event_type="test",
            actor_user_id="user-123",
            actor_client_id="client-456",
            server_id="test-server",
            status="success",
            metadata=None
        )
        
        # add_metadata should initialize metadata dict
        event.add_metadata("test_key", "test_value")
        assert event.metadata == {"test_key": "test_value"}
        
        # Test get_metadata with None metadata
        event.metadata = None
        assert event.get_metadata("any_key") is None
        assert event.get_metadata("any_key", "default") == "default"
    
    def test_validation_errors(self):
        """Test validation errors for invalid data."""
        # Test missing required fields
        with pytest.raises(ValidationError):
            AuditEvent(
                event_id=str(uuid.uuid4()),
                timestamp=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                # Missing required fields
            )
        
        # Test invalid duration_ms (negative)
        with pytest.raises(ValidationError):
            AuditEvent.create_event(
                event_type="test",
                actor_user_id="user-123",
                actor_client_id="client-456",
                server_id="test-server",
                status="success",
                duration_ms=-1  # Invalid negative duration
            )
    
    def test_json_serialization(self):
        """Test that audit events can be properly JSON serialized."""
        event = AuditEvent.create_event(
            event_type="tool_invocation",
            actor_user_id="user-123",
            actor_client_id="client-456",
            server_id="filesystem",
            status="success",
            tool_name="read_file",
            duration_ms=150,
            scopes=["scope1", "scope2"],
            metadata={"nested": {"key": "value"}, "list": [1, 2, 3]}
        )
        
        # Test to_dict serialization
        event_dict = event.to_dict()
        json_str = json.dumps(event_dict)
        
        # Verify we can deserialize back
        parsed_dict = json.loads(json_str)
        assert parsed_dict["event_type"] == "tool_invocation"
        assert parsed_dict["tool_name"] == "read_file"
        assert parsed_dict["scopes"] == ["scope1", "scope2"]
        assert parsed_dict["metadata"]["nested"]["key"] == "value"
    
    def test_real_world_scenarios(self):
        """Test real-world audit event scenarios."""
        
        # Scenario 1: Successful tool invocation with full context
        successful_tool_call = AuditEvent.create_event(
            event_type="tool_invocation",
            actor_user_id="alice@example.com",
            actor_client_id="copilot-vscode",
            server_id="filesystem",
            tool_name="write_file",
            status="success",
            duration_ms=234,
            params_hash="sha256:e3b0c44298fc1c149afbf4c8996fb924",
            output_hash="sha256:b5d4045c3f466fa91fe2cc6abe79232a",
            policy_allowed=True,
            request_id="req-550e8400-e29b-41d4-a716-446655440000",
            session_id="sess-123456789",
            user_agent="VSCode/1.85.0",
            source_ip="10.0.0.42",
            scopes=["mcp:write", "filesystem:access"],
            metadata={
                "file_path": "/workspace/src/main.py",
                "file_size_bytes": 1024,
                "encoding": "utf-8"
            }
        )
        
        assert successful_tool_call.is_success
        assert successful_tool_call.is_tool_invocation
        assert successful_tool_call.policy_allowed is True
        
        # Scenario 2: Authentication failure
        auth_failure = AuditEvent.create_event(
            event_type="auth",
            actor_user_id="unknown",
            actor_client_id="suspicious-client",
            server_id="gateway",
            status="error",
            error_code="INVALID_TOKEN",
            error_message="JWT signature verification failed",
            source_ip="198.51.100.42",
            user_agent="curl/7.68.0",
            metadata={
                "attempted_endpoint": "/api/v1/services",
                "token_issuer": "https://unknown.example.com",
                "auth_header_present": True
            }
        )
        
        assert auth_failure.is_failure
        assert auth_failure.is_auth_event
        assert auth_failure.get_metadata("attempted_endpoint") == "/api/v1/services"
        
        # Scenario 3: Policy-based access denial
        policy_denial = AuditEvent.create_event(
            event_type="policy",
            actor_user_id="bob@example.com",
            actor_client_id="web-dashboard",
            server_id="database",
            tool_name="execute_sql",
            status="denied",
            policy_allowed=False,
            request_id="req-policy-check-789",
            scopes=["mcp:read"],
            error_code="INSUFFICIENT_SCOPE",
            error_message="Operation requires 'database:admin' scope",
            metadata={
                "required_scopes": ["database:admin"],
                "attempted_operation": "DROP TABLE users",
                "policy_engine_version": "2.1.0",
                "risk_assessment": "HIGH"
            }
        )
        
        assert policy_denial.is_failure
        assert policy_denial.is_policy_event
        assert policy_denial.policy_allowed is False
        
        # Verify all events can be serialized
        for event in [successful_tool_call, auth_failure, policy_denial]:
            event_dict = event.to_dict()
            json.dumps(event_dict)  # Should not raise
            
            log_dict = event.to_log_dict()
            json.dumps(log_dict)  # Should not raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
