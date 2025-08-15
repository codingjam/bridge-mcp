#!/usr/bin/env python3
"""
Demo script showing the complete audit system in action.

This script demonstrates the audit logging functionality and shows
how it integrates with the rest of the MCP Gateway system.
"""

import json
import time
from typing import Dict, Any

from mcp_gateway.audit.logger import (
    log_audit_event,
    log_tool_invocation,
    log_auth_event,
    log_policy_event,
    get_audit_summary
)
from mcp_gateway.audit.store import get_audit_store


def demo_authentication_flow():
    """Demonstrate authentication audit logging."""
    print("🔐 Authentication Flow Demo")
    print("=" * 40)
    
    # Successful authentication
    log_auth_event(
        actor_user_id="alice@example.com",
        actor_client_id="vscode-copilot",
        status="success",
        source_ip="192.168.1.100",
        scopes=["mcp:read", "mcp:write", "filesystem:access"],
        session_id="session-abc123",
        user_agent="VSCode-Copilot/1.0"
    )
    
    # Failed authentication attempt
    log_auth_event(
        actor_user_id="unknown@suspicious.com",
        actor_client_id="unknown-client",
        status="error",
        source_ip="198.51.100.42",
        error_code="INVALID_TOKEN",
        error_message="JWT signature verification failed",
        user_agent="SuspiciousBot/1.0"
    )
    
    print("✅ Authentication events logged")


def demo_tool_invocations():
    """Demonstrate tool invocation audit logging."""
    print("\n🔧 Tool Invocation Demo")
    print("=" * 40)
    
    # File system operations
    log_tool_invocation(
        actor_user_id="alice@example.com",
        actor_client_id="vscode-copilot",
        server_id="filesystem",
        tool_name="read_file",
        duration_ms=125,
        params_hash="sha256:read_params_abc123",
        output_hash="sha256:file_content_def456",
        status="success",
        scopes=["filesystem:read"],
        metadata={"file_path": "/home/user/project/src/main.py", "file_size": 2048}
    )
    
    log_tool_invocation(
        actor_user_id="alice@example.com",
        actor_client_id="vscode-copilot",
        server_id="filesystem",
        tool_name="write_file",
        duration_ms=250,
        params_hash="sha256:write_params_ghi789",
        status="success",
        scopes=["filesystem:write"],
        metadata={"file_path": "/home/user/project/src/new_file.py", "bytes_written": 1024}
    )
    
    # Database operation that fails
    log_tool_invocation(
        actor_user_id="alice@example.com",
        actor_client_id="vscode-copilot",
        server_id="database",
        tool_name="execute_query",
        duration_ms=50,
        params_hash="sha256:query_params_jkl012",
        status="error",
        error_code="CONNECTION_TIMEOUT",
        error_message="Database connection timed out after 30 seconds",
        scopes=["database:read"],
        metadata={"query_type": "SELECT", "table": "users"}
    )
    
    print("✅ Tool invocation events logged")


def demo_policy_evaluation():
    """Demonstrate policy evaluation audit logging."""
    print("\n🛡️ Policy Evaluation Demo")
    print("=" * 40)
    
    # Policy allows operation
    log_policy_event(
        actor_user_id="alice@example.com",
        actor_client_id="vscode-copilot",
        server_id="filesystem",
        policy_allowed=True,
        tool_name="read_file",
        scopes=["filesystem:read"],
        metadata={"policy_rule": "allow_read_in_user_directory", "resource": "/home/alice/project/"}
    )
    
    # Policy denies operation
    log_policy_event(
        actor_user_id="bob@example.com",
        actor_client_id="web-client",
        server_id="admin-panel",
        policy_allowed=False,
        tool_name="delete_user",
        error_code="INSUFFICIENT_PERMISSIONS",
        error_message="User lacks admin role required for user deletion",
        scopes=["admin:users"],
        metadata={"required_role": "admin", "user_role": "user", "target_user": "charlie@example.com"}
    )
    
    print("✅ Policy evaluation events logged")


def demo_custom_audit_events():
    """Demonstrate custom audit event logging."""
    print("\n📝 Custom Audit Events Demo")
    print("=" * 40)
    
    # System maintenance event
    log_audit_event(
        event_type="system_maintenance",
        actor_user_id="system",
        actor_client_id="maintenance-service",
        server_id="gateway",
        status="success",
        duration_ms=30000,
        metadata={
            "maintenance_type": "cache_cleanup",
            "items_cleaned": 1250,
            "disk_space_freed_mb": 45
        }
    )
    
    # Rate limiting event
    log_audit_event(
        event_type="rate_limit",
        actor_user_id="bob@example.com",
        actor_client_id="aggressive-client",
        server_id="gateway",
        status="denied",
        error_code="RATE_LIMIT_EXCEEDED",
        error_message="Request rate limit exceeded: 100 requests per minute",
        source_ip="203.0.113.15",
        metadata={
            "rate_limit": "100/minute",
            "current_rate": "150/minute",
            "window_start": time.time() - 60
        }
    )
    
    print("✅ Custom audit events logged")


def demo_audit_summary():
    """Demonstrate audit summary functionality."""
    print("\n📊 Audit Summary Demo")
    print("=" * 40)
    
    summary = get_audit_summary()
    
    print(f"Total Events: {summary['total_events']}")
    print(f"Success Rate: {summary['success_rate']:.1%}")
    print(f"Failure Rate: {summary['failure_rate']:.1%}")
    
    print("\nEvent Type Breakdown:")
    for event_type, count in summary['event_types'].items():
        print(f"  {event_type}: {count}")
    
    print("\nStatus Breakdown:")
    for status, count in summary['status_counts'].items():
        print(f"  {status}: {count}")
    
    print(f"\nRecent Events: {len(summary['recent_events'])}")
    print(f"Recent Failures: {len(summary['recent_failures'])}")


def demo_store_queries():
    """Demonstrate audit store query capabilities."""
    print("\n🗄️ Audit Store Queries Demo")
    print("=" * 40)
    
    store = get_audit_store()
    
    # Query by user
    alice_events = store.get_events_by_user("alice@example.com")
    print(f"Alice's events: {len(alice_events)}")
    
    # Query by server
    fs_events = store.get_events_by_server("filesystem")
    print(f"Filesystem events: {len(fs_events)}")
    
    # Query by event type
    auth_events = store.get_events_by_type("auth")
    print(f"Authentication events: {len(auth_events)}")
    
    # Query failed events
    failed_events = store.get_failed_events()
    print(f"Failed events: {len(failed_events)}")
    
    # Get statistics
    stats = store.get_statistics()
    print(f"\nStore Statistics:")
    print(f"  Total events: {stats['total_events']}")
    print(f"  Success rate: {stats['success_rate']:.1%}")
    print(f"  Failure rate: {stats['failure_rate']:.1%}")
    print(f"  Event types: {list(stats['event_types'].keys())}")
    print(f"  Status types: {list(stats['status_counts'].keys())}")


def main():
    """Run the complete audit system demo."""
    print("🚀 MCP Gateway Audit System Demo")
    print("=" * 50)
    
    # Clear any existing events
    store = get_audit_store()
    store.clear()
    
    # Run all demo scenarios
    demo_authentication_flow()
    demo_tool_invocations()
    demo_policy_evaluation()
    demo_custom_audit_events()
    demo_audit_summary()
    demo_store_queries()
    
    print("\n🎉 Demo completed successfully!")
    print(f"Total events generated: {store.count()}")
    
    # Show a sample of the JSON output format
    print("\n📄 Sample JSON Output Format:")
    print("-" * 30)
    
    # Get the most recent event and show its JSON representation
    recent_events = store.get_events(limit=1)
    if recent_events:
        sample_event = recent_events[0]
        sample_json = json.dumps(sample_event.to_dict(), indent=2)
        print(sample_json)


if __name__ == "__main__":
    main()
