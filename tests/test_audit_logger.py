"""
Unit tests for audit logging functions.

This module contains comprehensive tests for the audit logging functions
to ensure correct functionality for thread-safe audit logging in the MCP Gateway.
"""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from unittest.mock import patch
from typing import List

import pytest

from mcp_gateway.audit.models.audit_event import AuditEvent
from mcp_gateway.audit.store import get_audit_store
from mcp_gateway.audit.audit_logger import (
    log_audit_event,
    log_tool_invocation,
    log_auth_event,
    log_policy_event,
    get_audit_summary
)


class TestAuditLogger:
    """Test cases for audit logging functions."""
    
    def setup_method(self):
        """Setup method to clear the store before each test."""
        store = get_audit_store()
        store.clear()
    
    def test_log_audit_event_basic(self):
        """Test basic audit event logging."""
        store = get_audit_store()
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            event = log_audit_event(
                event_type="test",
                actor_user_id="user-123",
                actor_client_id="client-456",
                server_id="test-server",
                status="success"
            )
        
        # Verify event was created and returned
        assert isinstance(event, AuditEvent)
        assert event.event_type == "test"
        assert event.actor_user_id == "user-123"
        assert event.status == "success"
        
        # Verify event was stored
        assert store.count() == 1
        stored_events = store.get_events()
        assert stored_events[0] is event
        
        # Verify JSON was printed to stdout
        output = mock_stdout.getvalue().strip()
        assert output  # Should have output
        
        # Verify output is valid JSON
        parsed_output = json.loads(output)
        assert parsed_output["audit_type"] == "test"
        assert parsed_output["user_id"] == "user-123"
        assert parsed_output["operation_status"] == "success"
    
    def test_log_audit_event_with_all_fields(self):
        """Test audit event logging with all optional fields."""
        store = get_audit_store()
        
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            event = log_audit_event(
                event_type="tool_invocation",
                actor_user_id="user-123",
                actor_client_id="client-456",
                server_id="filesystem",
                tool_name="read_file",
                params_hash="sha256:abc123",
                output_hash="sha256:def456",
                status="success",
                duration_ms=150,
                policy_allowed=True,
                request_id="req-789",
                session_id="session-123",
                user_agent="Test-Agent/1.0",
                source_ip="192.168.1.1",
                scopes=["mcp:read", "filesystem:access"],
                metadata={"file_path": "/test/file.txt"}
            )
        
        # Verify all fields are set
        assert event.tool_name == "read_file"
        assert event.params_hash == "sha256:abc123"
        assert event.output_hash == "sha256:def456"
        assert event.duration_ms == 150
        assert event.policy_allowed is True
        assert event.request_id == "req-789"
        assert event.scopes == ["mcp:read", "filesystem:access"]
        assert event.metadata["file_path"] == "/test/file.txt"
        
        # Verify event was stored
        assert store.count() == 1
        
        # Verify JSON output contains all fields
        output = mock_stdout.getvalue().strip()
        parsed_output = json.loads(output)
        assert parsed_output["tool_name"] == "read_file"
        assert parsed_output["duration_ms"] == 150
        assert parsed_output["policy_allowed"] is True
    
    def test_log_tool_invocation_convenience(self):
        """Test log_tool_invocation convenience function."""
        store = get_audit_store()
        
        with patch('sys.stdout', new_callable=StringIO):
            event = log_tool_invocation(
                actor_user_id="user-123",
                actor_client_id="copilot",
                server_id="filesystem",
                tool_name="write_file",
                duration_ms=200,
                params_hash="sha256:params123",
                scopes=["mcp:write"]
            )
        
        assert event.event_type == "tool_invocation"
        assert event.tool_name == "write_file"
        assert event.duration_ms == 200
        assert event.scopes == ["mcp:write"]
        assert store.count() == 1
    
    def test_log_auth_event_convenience(self):
        """Test log_auth_event convenience function."""
        store = get_audit_store()
        
        with patch('sys.stdout', new_callable=StringIO):
            event = log_auth_event(
                actor_user_id="user-123",
                actor_client_id="web-client",
                status="success",
                source_ip="192.168.1.100",
                scopes=["mcp:read", "mcp:write"]
            )
        
        assert event.event_type == "auth"
        assert event.server_id == "gateway"
        assert event.source_ip == "192.168.1.100"
        assert event.scopes == ["mcp:read", "mcp:write"]
        assert store.count() == 1
    
    def test_log_policy_event_convenience(self):
        """Test log_policy_event convenience function."""
        store = get_audit_store()
        
        with patch('sys.stdout', new_callable=StringIO):
            # Test allowed policy
            event1 = log_policy_event(
                actor_user_id="user-123",
                actor_client_id="app",
                server_id="database",
                policy_allowed=True,
                tool_name="select_data"
            )
            
            # Test denied policy (should auto-set status to denied)
            event2 = log_policy_event(
                actor_user_id="user-456",
                actor_client_id="app",
                server_id="database",
                policy_allowed=False,
                tool_name="delete_table",
                error_code="INSUFFICIENT_PERMISSIONS"
            )
        
        assert event1.event_type == "policy"
        assert event1.policy_allowed is True
        assert event1.status == "success"
        
        assert event2.event_type == "policy"
        assert event2.policy_allowed is False
        assert event2.status == "denied"
        assert event2.error_code == "INSUFFICIENT_PERMISSIONS"
        
        assert store.count() == 2
    
    def test_thread_safety_concurrent_logging(self):
        """Test thread safety of audit logging functions."""
        store = get_audit_store()
        num_threads = 10
        events_per_thread = 20
        
        def log_events(thread_id: int):
            """Log events from a specific thread."""
            for i in range(events_per_thread):
                with patch('sys.stdout', new_callable=StringIO):
                    log_audit_event(
                        event_type="test",
                        actor_user_id=f"user-{thread_id}-{i}",
                        actor_client_id=f"client-{thread_id}",
                        server_id="test-server",
                        status="success",
                        duration_ms=i * 10
                    )
        
        # Run concurrent threads
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(log_events, i) for i in range(num_threads)]
            
            # Wait for all threads to complete
            for future in futures:
                future.result()
        
        # Verify all events were logged and stored
        expected_total = num_threads * events_per_thread
        assert store.count() == expected_total
        
        # Verify we can retrieve all events
        all_events = store.get_events(limit=expected_total)
        assert len(all_events) == expected_total
    
    def test_concurrent_stdout_output(self):
        """Test that concurrent stdout output doesn't interfere."""
        outputs = []
        num_threads = 5
        
        def capture_output(thread_id: int):
            """Capture output from a specific thread."""
            with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
                log_audit_event(
                    event_type="concurrent_test",
                    actor_user_id=f"user-{thread_id}",
                    actor_client_id=f"client-{thread_id}",
                    server_id="test-server",
                    status="success"
                )
                outputs.append(mock_stdout.getvalue().strip())
        
        # Run concurrent threads
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(capture_output, i) for i in range(num_threads)]
            
            # Wait for all threads to complete
            for future in futures:
                future.result()
        
        # Verify all threads produced valid JSON output
        assert len(outputs) == num_threads
        for output in outputs:
            assert output  # Should have output
            parsed = json.loads(output)  # Should be valid JSON
            assert parsed["audit_type"] == "concurrent_test"
    
    def test_error_handling_audit_failure(self):
        """Test error handling when audit logging fails."""
        # Test with invalid duration (negative value should cause validation error)
        with patch('sys.stderr', new_callable=StringIO) as mock_stderr:
            with patch('sys.stdout', new_callable=StringIO):
                event = log_audit_event(
                    event_type="test",
                    actor_user_id="user-123",
                    actor_client_id="client-456",
                    server_id="test-server",
                    status="success",
                    duration_ms=-1  # Invalid negative duration
                )
        
        # Should have logged error to stderr
        error_output = mock_stderr.getvalue()
        assert "audit_error" in error_output or event is None
    
    def test_get_audit_summary(self):
        """Test getting audit summary."""
        store = get_audit_store()
        
        # Add some test events
        with patch('sys.stdout', new_callable=StringIO):
            log_audit_event("auth", "user1", "client1", "gateway", status="success")
            log_audit_event("auth", "user2", "client2", "gateway", status="error")
            log_audit_event("tool_invocation", "user1", "client1", "fs", status="success")
            log_audit_event("policy", "user2", "client2", "db", status="denied")
        
        summary = get_audit_summary()
        
        assert summary["total_events"] == 4
        assert summary["success_rate"] == 0.5  # 2 successes out of 4
        assert summary["failure_rate"] == 0.5  # 2 failures out of 4
        assert summary["event_types"]["auth"] == 2
        assert summary["event_types"]["tool_invocation"] == 1
        assert summary["event_types"]["policy"] == 1
        assert summary["status_counts"]["success"] == 2
        assert summary["status_counts"]["error"] == 1
        assert summary["status_counts"]["denied"] == 1
        
        # Verify recent events structure
        assert len(summary["recent_events"]) == 4
        assert "timestamp" in summary["recent_events"][0]
        assert "type" in summary["recent_events"][0]
        assert "user" in summary["recent_events"][0]
        
        # Verify recent failures structure
        assert len(summary["recent_failures"]) == 2
        assert "timestamp" in summary["recent_failures"][0]
        assert "error" in summary["recent_failures"][0]
    
    def test_json_output_format(self):
        """Test that JSON output has correct format for container logs."""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            event = log_audit_event(
                event_type="tool_invocation",
                actor_user_id="user-123",
                actor_client_id="client-456",
                server_id="filesystem",
                tool_name="read_file",
                status="success",
                duration_ms=100,
                metadata={"test": "value"}
            )
        
        output = mock_stdout.getvalue().strip()
        parsed = json.loads(output)
        
        # Verify log_dict format is used (has audit-specific fields)
        assert "audit_event_id" in parsed
        assert "audit_timestamp" in parsed
        assert "audit_type" in parsed
        assert "user_id" in parsed
        assert "client_id" in parsed
        assert "target_server" in parsed
        assert "operation_status" in parsed
        
        # Verify original fields are also present
        assert parsed["audit_type"] == "tool_invocation"
        assert parsed["user_id"] == "user-123"
        assert parsed["operation_status"] == "success"
        assert parsed["tool_name"] == "read_file"
        assert parsed["duration_ms"] == 100
        assert parsed["metadata"]["test"] == "value"
    
    def test_real_world_usage_patterns(self):
        """Test real-world usage patterns."""
        store = get_audit_store()
        
        with patch('sys.stdout', new_callable=StringIO):
            # Simulate a complete user session
            
            # 1. User authentication
            log_auth_event(
                actor_user_id="alice@example.com",
                actor_client_id="vscode-copilot",
                status="success",
                source_ip="10.0.0.42",
                scopes=["mcp:read", "mcp:write"]
            )
            
            # 2. Tool invocations
            log_tool_invocation(
                actor_user_id="alice@example.com",
                actor_client_id="vscode-copilot",
                server_id="filesystem",
                tool_name="read_file",
                duration_ms=120,
                params_hash="sha256:file_params",
                output_hash="sha256:file_content"
            )
            
            log_tool_invocation(
                actor_user_id="alice@example.com",
                actor_client_id="vscode-copilot",
                server_id="filesystem",
                tool_name="write_file",
                duration_ms=250,
                params_hash="sha256:write_params"
            )
            
            # 3. Policy evaluation
            log_policy_event(
                actor_user_id="alice@example.com",
                actor_client_id="vscode-copilot",
                server_id="database",
                policy_allowed=False,
                tool_name="drop_table",
                error_code="INSUFFICIENT_PERMISSIONS",
                metadata={"required_role": "admin"}
            )
            
            # 4. Authentication failure from different user
            log_auth_event(
                actor_user_id="unknown",
                actor_client_id="suspicious-app",
                status="error",
                source_ip="198.51.100.42",
                error_code="INVALID_TOKEN",
                error_message="JWT signature verification failed"
            )
        
        # Verify all events were logged
        assert store.count() == 5
        
        # Verify summary reflects the session
        summary = get_audit_summary()
        assert summary["total_events"] == 5
        assert summary["event_types"]["auth"] == 2
        assert summary["event_types"]["tool_invocation"] == 2
        assert summary["event_types"]["policy"] == 1
        
        # Verify user-specific activity
        alice_events = store.get_events_by_user("alice@example.com")
        assert len(alice_events) == 4  # All except the auth failure
        
        # Verify failed events
        failed_events = store.get_failed_events()
        assert len(failed_events) == 2  # Auth failure and policy denial


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
