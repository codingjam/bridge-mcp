"""
Unit tests for AuditStore class.

This module contains comprehensive tests for the AuditStore class to ensure
correct functionality for thread-safe audit event storage in the MCP Gateway.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List

import pytest

from mcp_gateway.audit.models.audit_event import AuditEvent
from mcp_gateway.audit.store import AuditStore, get_audit_store


class TestAuditStore:
    """Test cases for AuditStore class."""
    
    def setup_method(self):
        """Setup method to clear the store before each test."""
        # Clear the singleton instance for clean tests
        AuditStore._instance = None
        
    def test_singleton_pattern(self):
        """Test that AuditStore follows singleton pattern."""
        store1 = AuditStore.get_instance()
        store2 = AuditStore.get_instance()
        
        # Both references should point to the same instance
        assert store1 is store2
        
        # Test convenience function returns same instance
        store3 = get_audit_store()
        assert store1 is store3
    
    def test_add_event(self):
        """Test adding audit events to the store."""
        store = AuditStore.get_instance()
        
        # Create test events
        event1 = AuditEvent.create_event(
            event_type="auth",
            actor_user_id="user-1",
            actor_client_id="client-1",
            server_id="gateway",
            status="success"
        )
        
        event2 = AuditEvent.create_event(
            event_type="tool_invocation",
            actor_user_id="user-2",
            actor_client_id="client-2",
            server_id="filesystem",
            status="error"
        )
        
        # Add events
        store.add_event(event1)
        store.add_event(event2)
        
        # Verify events are stored
        assert store.count() == 2
        
        # Get events and verify order (newest first)
        events = store.get_events()
        assert len(events) == 2
        assert events[0] is event2  # Most recent first
        assert events[1] is event1  # Older second
    
    def test_get_events_limit(self):
        """Test get_events with different limits."""
        store = AuditStore.get_instance()
        
        # Add multiple events
        events = []
        for i in range(10):
            event = AuditEvent.create_event(
                event_type="test",
                actor_user_id=f"user-{i}",
                actor_client_id=f"client-{i}",
                server_id="test-server",
                status="success"
            )
            events.append(event)
            store.add_event(event)
        
        # Test default limit
        retrieved = store.get_events()
        assert len(retrieved) == 10
        
        # Test custom limits
        assert len(store.get_events(limit=5)) == 5
        assert len(store.get_events(limit=3)) == 3
        assert len(store.get_events(limit=15)) == 10  # More than available
        
        # Verify reverse chronological order
        recent_5 = store.get_events(limit=5)
        assert recent_5[0] is events[9]  # Most recent
        assert recent_5[4] is events[5]  # 5th most recent
    
    def test_get_events_by_type(self):
        """Test filtering events by type."""
        store = AuditStore.get_instance()
        
        # Add events of different types
        auth_events = []
        tool_events = []
        
        for i in range(3):
            auth_event = AuditEvent.create_event(
                event_type="auth",
                actor_user_id=f"user-{i}",
                actor_client_id=f"client-{i}",
                server_id="gateway",
                status="success"
            )
            auth_events.append(auth_event)
            store.add_event(auth_event)
            
            tool_event = AuditEvent.create_event(
                event_type="tool_invocation",
                actor_user_id=f"user-{i}",
                actor_client_id=f"client-{i}",
                server_id="filesystem",
                status="success"
            )
            tool_events.append(tool_event)
            store.add_event(tool_event)
        
        # Test filtering by type
        retrieved_auth = store.get_events_by_type("auth")
        retrieved_tools = store.get_events_by_type("tool_invocation")
        retrieved_none = store.get_events_by_type("nonexistent")
        
        assert len(retrieved_auth) == 3
        assert len(retrieved_tools) == 3
        assert len(retrieved_none) == 0
        
        # Verify correct events are returned
        for event in retrieved_auth:
            assert event.event_type == "auth"
        
        for event in retrieved_tools:
            assert event.event_type == "tool_invocation"
        
        # Verify reverse chronological order
        assert retrieved_auth[0] is auth_events[2]  # Most recent auth event
        assert retrieved_tools[0] is tool_events[2]  # Most recent tool event
    
    def test_get_events_by_user(self):
        """Test filtering events by user ID."""
        store = AuditStore.get_instance()
        
        # Add events for different users
        user1_events = []
        user2_events = []
        
        for i in range(3):
            # Events for user-1
            event1 = AuditEvent.create_event(
                event_type="test",
                actor_user_id="user-1",
                actor_client_id=f"client-{i}",
                server_id="test-server",
                status="success"
            )
            user1_events.append(event1)
            store.add_event(event1)
            
            # Events for user-2
            event2 = AuditEvent.create_event(
                event_type="test",
                actor_user_id="user-2",
                actor_client_id=f"client-{i}",
                server_id="test-server",
                status="success"
            )
            user2_events.append(event2)
            store.add_event(event2)
        
        # Test filtering by user
        user1_retrieved = store.get_events_by_user("user-1")
        user2_retrieved = store.get_events_by_user("user-2")
        user3_retrieved = store.get_events_by_user("user-3")
        
        assert len(user1_retrieved) == 3
        assert len(user2_retrieved) == 3
        assert len(user3_retrieved) == 0
        
        # Verify correct events are returned
        for event in user1_retrieved:
            assert event.actor_user_id == "user-1"
        
        for event in user2_retrieved:
            assert event.actor_user_id == "user-2"
        
        # Verify reverse chronological order
        assert user1_retrieved[0] is user1_events[2]  # Most recent for user-1
        assert user2_retrieved[0] is user2_events[2]  # Most recent for user-2
    
    def test_get_failed_events(self):
        """Test filtering failed events."""
        store = AuditStore.get_instance()
        
        success_events = []
        failed_events = []
        
        # Add successful events
        for i in range(3):
            event = AuditEvent.create_event(
                event_type="test",
                actor_user_id=f"user-{i}",
                actor_client_id="client",
                server_id="server",
                status="success"
            )
            success_events.append(event)
            store.add_event(event)
        
        # Add failed events with different failure types
        failure_statuses = ["error", "denied", "timeout"]
        for i, status in enumerate(failure_statuses):
            event = AuditEvent.create_event(
                event_type="test",
                actor_user_id=f"user-fail-{i}",
                actor_client_id="client",
                server_id="server",
                status=status
            )
            failed_events.append(event)
            store.add_event(event)
        
        # Test filtering failed events
        retrieved_failed = store.get_failed_events()
        
        assert len(retrieved_failed) == 3
        
        # Verify only failed events are returned
        for event in retrieved_failed:
            assert event.status in ["error", "denied", "timeout"]
        
        # Verify reverse chronological order
        assert retrieved_failed[0] is failed_events[2]  # Most recent failure
    
    def test_count(self):
        """Test counting events in the store."""
        store = AuditStore.get_instance()
        
        assert store.count() == 0
        
        # Add events and verify count
        for i in range(5):
            event = AuditEvent.create_event(
                event_type="test",
                actor_user_id=f"user-{i}",
                actor_client_id="client",
                server_id="server",
                status="success"
            )
            store.add_event(event)
            assert store.count() == i + 1
    
    def test_clear(self):
        """Test clearing all events from the store."""
        store = AuditStore.get_instance()
        
        # Add some events
        for i in range(5):
            event = AuditEvent.create_event(
                event_type="test",
                actor_user_id=f"user-{i}",
                actor_client_id="client",
                server_id="server",
                status="success"
            )
            store.add_event(event)
        
        assert store.count() == 5
        
        # Clear and verify
        store.clear()
        assert store.count() == 0
        assert len(store.get_events()) == 0
    
    def test_get_stats(self):
        """Test getting statistics about stored events."""
        store = AuditStore.get_instance()
        
        # Test stats with empty store
        stats = store.get_stats()
        assert stats["total_events"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["failure_rate"] == 0.0
        
        # Add events with different types and statuses
        events_data = [
            ("auth", "success"),
            ("auth", "error"),
            ("tool_invocation", "success"),
            ("tool_invocation", "success"),
            ("policy", "denied"),
        ]
        
        for event_type, status in events_data:
            event = AuditEvent.create_event(
                event_type=event_type,
                actor_user_id="user",
                actor_client_id="client",
                server_id="server",
                status=status
            )
            store.add_event(event)
        
        # Test stats with data
        stats = store.get_stats()
        
        assert stats["total_events"] == 5
        assert stats["event_types"]["auth"] == 2
        assert stats["event_types"]["tool_invocation"] == 2
        assert stats["event_types"]["policy"] == 1
        assert stats["status_counts"]["success"] == 3
        assert stats["status_counts"]["error"] == 1
        assert stats["status_counts"]["denied"] == 1
        assert stats["success_rate"] == 0.6  # 3/5
        assert stats["failure_rate"] == 0.4  # 2/5
    
    def test_thread_safety_add_events(self):
        """Test thread safety when adding events concurrently."""
        store = AuditStore.get_instance()
        num_threads = 10
        events_per_thread = 20
        
        def add_events(thread_id: int):
            """Add events from a specific thread."""
            for i in range(events_per_thread):
                event = AuditEvent.create_event(
                    event_type="test",
                    actor_user_id=f"user-{thread_id}-{i}",
                    actor_client_id=f"client-{thread_id}",
                    server_id="test-server",
                    status="success"
                )
                store.add_event(event)
        
        # Run concurrent threads
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(add_events, i) for i in range(num_threads)]
            
            # Wait for all threads to complete
            for future in futures:
                future.result()
        
        # Verify all events were added
        expected_total = num_threads * events_per_thread
        assert store.count() == expected_total
        
        # Verify we can retrieve all events
        all_events = store.get_events(limit=expected_total)
        assert len(all_events) == expected_total
    
    def test_thread_safety_mixed_operations(self):
        """Test thread safety with mixed read/write operations."""
        store = AuditStore.get_instance()
        num_threads = 5
        operations_per_thread = 50
        results = {}
        
        def mixed_operations(thread_id: int):
            """Perform mixed read/write operations."""
            results[thread_id] = {
                "events_added": 0,
                "events_read": 0,
                "counts_checked": 0
            }
            
            for i in range(operations_per_thread):
                if i % 3 == 0:
                    # Add event
                    event = AuditEvent.create_event(
                        event_type="test",
                        actor_user_id=f"user-{thread_id}-{i}",
                        actor_client_id=f"client-{thread_id}",
                        server_id="test-server",
                        status="success"
                    )
                    store.add_event(event)
                    results[thread_id]["events_added"] += 1
                elif i % 3 == 1:
                    # Read events
                    events = store.get_events(limit=10)
                    results[thread_id]["events_read"] += len(events)
                else:
                    # Check count
                    count = store.count()
                    results[thread_id]["counts_checked"] += 1
        
        # Run concurrent threads
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(mixed_operations, i) for i in range(num_threads)]
            
            # Wait for all threads to complete
            for future in futures:
                future.result()
        
        # Verify operations completed without errors
        total_events_added = sum(r["events_added"] for r in results.values())
        assert store.count() == total_events_added
        
        # Verify all threads performed operations
        for thread_id, result in results.items():
            assert result["events_added"] > 0
            assert result["counts_checked"] > 0
    
    def test_singleton_thread_safety(self):
        """Test that singleton pattern is thread-safe."""
        instances = []
        num_threads = 10
        
        def get_instance():
            """Get singleton instance from thread."""
            instance = AuditStore.get_instance()
            instances.append(instance)
        
        # Run concurrent threads to get singleton
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(get_instance) for _ in range(num_threads)]
            
            # Wait for all threads to complete
            for future in futures:
                future.result()
        
        # Verify all threads got the same instance
        assert len(instances) == num_threads
        first_instance = instances[0]
        for instance in instances:
            assert instance is first_instance


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
