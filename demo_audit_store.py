"""
Demo script showing AuditStore usage patterns.

This script demonstrates how to use the AuditStore for various audit logging
scenarios in the MCP Gateway, including thread-safe operations and querying.
"""

import time
import json
from concurrent.futures import ThreadPoolExecutor
from mcp_gateway.audit import AuditEvent, get_audit_store


def demo_basic_usage():
    """Demonstrate basic AuditStore usage."""
    print("=== Basic AuditStore Usage ===")
    
    store = get_audit_store()
    store.clear()  # Start fresh
    
    # Add various types of audit events
    events = [
        # Tool invocation success
        AuditEvent.create_event(
            event_type="tool_invocation",
            actor_user_id="alice@example.com",
            actor_client_id="vscode-copilot",
            server_id="filesystem",
            tool_name="read_file",
            status="success",
            duration_ms=120,
            params_hash="sha256:abc123...",
            scopes=["mcp:read", "filesystem:access"]
        ),
        
        # Authentication failure
        AuditEvent.create_event(
            event_type="auth",
            actor_user_id="unknown",
            actor_client_id="suspicious-app",
            server_id="gateway",
            status="error",
            error_code="INVALID_TOKEN",
            error_message="JWT signature verification failed",
            source_ip="192.168.1.100"
        ),
        
        # Policy denial
        AuditEvent.create_event(
            event_type="policy",
            actor_user_id="bob@example.com",
            actor_client_id="web-dashboard",
            server_id="database",
            tool_name="delete_table",
            status="denied",
            policy_allowed=False,
            error_code="INSUFFICIENT_PERMISSIONS",
            scopes=["mcp:read"]
        ),
        
        # Successful service discovery
        AuditEvent.create_event(
            event_type="service_discovery",
            actor_user_id="charlie@example.com",
            actor_client_id="monitoring-tool",
            server_id="gateway",
            status="success",
            duration_ms=45,
            metadata={"services_found": 5}
        )
    ]
    
    # Add events to store
    for event in events:
        store.add_event(event)
        time.sleep(0.01)  # Small delay to ensure different timestamps
    
    print(f"Added {store.count()} events to store")
    
    # Demonstrate querying
    print("\n--- Recent Events (newest first) ---")
    recent = store.get_events(limit=3)
    for i, event in enumerate(recent, 1):
        print(f"{i}. {event.event_type}: {event.status} (User: {event.actor_user_id})")
    
    print("\n--- Authentication Events ---")
    auth_events = store.get_events_by_type("auth")
    for event in auth_events:
        print(f"   {event.timestamp}: {event.status} - {event.error_message}")
    
    print("\n--- Failed Events ---")
    failed = store.get_failed_events()
    for event in failed:
        print(f"   {event.event_type}: {event.status} - {event.actor_user_id}")
    
    print("\n--- Store Statistics ---")
    stats = store.get_stats()
    print(f"   Total events: {stats['total_events']}")
    print(f"   Success rate: {stats['success_rate']:.1%}")
    print(f"   Event types: {dict(stats['event_types'])}")
    print(f"   Status distribution: {dict(stats['status_counts'])}")


def demo_thread_safety():
    """Demonstrate thread-safe operations."""
    print("\n=== Thread Safety Demo ===")
    
    store = get_audit_store()
    store.clear()
    
    def simulate_user_activity(user_id: str, num_events: int):
        """Simulate a user performing various operations."""
        for i in range(num_events):
            event_type = ["tool_invocation", "service_discovery", "auth"][i % 3]
            status = "success" if i % 4 != 0 else "error"
            
            event = AuditEvent.create_event(
                event_type=event_type,
                actor_user_id=user_id,
                actor_client_id=f"client-{user_id}",
                server_id="test-server",
                status=status,
                duration_ms=50 + (i * 10)
            )
            
            store.add_event(event)
            time.sleep(0.001)  # Tiny delay to simulate real work
    
    # Simulate concurrent users
    users = ["alice", "bob", "charlie", "diana", "eve"]
    events_per_user = 20
    
    print(f"Simulating {len(users)} concurrent users with {events_per_user} events each...")
    
    start_time = time.time()
    with ThreadPoolExecutor(max_workers=len(users)) as executor:
        futures = [
            executor.submit(simulate_user_activity, user, events_per_user) 
            for user in users
        ]
        
        # Wait for all threads to complete
        for future in futures:
            future.result()
    
    elapsed = time.time() - start_time
    total_events = len(users) * events_per_user
    
    print(f"✅ Successfully processed {total_events} events in {elapsed:.2f}s")
    print(f"   Events/second: {total_events/elapsed:.0f}")
    print(f"   Final store count: {store.count()}")
    
    # Show per-user statistics
    print("\n--- Per-User Activity ---")
    for user in users:
        user_events = store.get_events_by_user(user)
        failed_count = sum(1 for e in user_events if e.status != "success")
        print(f"   {user}: {len(user_events)} events, {failed_count} failures")


def demo_monitoring_patterns():
    """Demonstrate common monitoring and alerting patterns."""
    print("\n=== Monitoring Patterns Demo ===")
    
    store = get_audit_store()
    
    # Check for security concerns
    print("--- Security Monitoring ---")
    
    # Check for authentication failures
    auth_failures = [e for e in store.get_events_by_type("auth") if e.status == "error"]
    if len(auth_failures) > 2:
        print(f"⚠️  Alert: {len(auth_failures)} authentication failures detected")
        for failure in auth_failures[:3]:  # Show first 3
            print(f"     {failure.timestamp}: {failure.source_ip} - {failure.error_message}")
    
    # Check for policy denials
    policy_denials = [e for e in store.get_events_by_type("policy") if e.status == "denied"]
    if policy_denials:
        print(f"⚠️  Alert: {len(policy_denials)} policy denials")
        for denial in policy_denials:
            print(f"     {denial.actor_user_id} denied access to {denial.server_id}/{denial.tool_name}")
    
    # Performance monitoring
    print("\n--- Performance Monitoring ---")
    tool_events = store.get_events_by_type("tool_invocation")
    if tool_events:
        durations = [e.duration_ms for e in tool_events if e.duration_ms is not None]
        if durations:
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            print(f"   Average tool execution time: {avg_duration:.1f}ms")
            print(f"   Slowest operation: {max_duration}ms")
            
            if max_duration > 1000:
                print(f"⚠️  Alert: Slow operation detected ({max_duration}ms)")
    
    # User activity analysis
    print("\n--- User Activity Analysis ---")
    stats = store.get_stats()
    if stats["total_events"] > 0:
        print(f"   Total operations: {stats['total_events']}")
        print(f"   Overall success rate: {stats['success_rate']:.1%}")
        
        if stats['failure_rate'] > 0.2:  # More than 20% failures
            print(f"⚠️  Alert: High failure rate ({stats['failure_rate']:.1%})")


def main():
    """Run all demonstrations."""
    print("🔍 MCP Gateway AuditStore Demonstration\n")
    
    demo_basic_usage()
    demo_thread_safety()
    demo_monitoring_patterns()
    
    print("\n✅ All demonstrations completed successfully!")
    
    # Show final store state
    store = get_audit_store()
    print(f"\nFinal store contains {store.count()} total events")


if __name__ == "__main__":
    main()
