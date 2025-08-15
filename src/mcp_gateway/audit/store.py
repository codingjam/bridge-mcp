"""
In-memory audit event store for MCP Gateway.

This module provides a thread-safe, singleton audit store that holds audit events
in memory for quick access and retrieval. The store maintains events in chronological
order and provides methods for adding, querying, and managing audit events.
"""

import threading
from typing import List, Optional, Dict, Any
from .models.audit_event import AuditEvent


class AuditStore:
    """
    Thread-safe in-memory store for audit events.
    
    This class provides a centralized, thread-safe storage mechanism for audit events
    within the MCP Gateway. It maintains events in chronological order and supports
    efficient retrieval of recent events for monitoring and debugging purposes.
    
    The store uses a singleton pattern to ensure consistent access across the application
    and includes thread synchronization to handle concurrent access safely.
    
    Features:
    - Thread-safe operations using threading.Lock
    - Chronological event storage with efficient retrieval
    - Singleton pattern for global access
    - Memory-efficient reverse chronological queries
    - Safe concurrent access from multiple threads
    
    Example:
        # Get the singleton instance
        store = AuditStore.get_instance()
        
        # Add audit events
        event = AuditEvent.create_event(...)
        store.add_event(event)
        
        # Retrieve recent events
        recent_events = store.get_events(limit=50)
        
        # Clear all events
        store.clear()
    """
    
    _instance: Optional['AuditStore'] = None
    _lock = threading.Lock()
    
    def __init__(self):
        """
        Initialize the audit store.
        
        Note: Use get_instance() instead of direct instantiation to ensure
        singleton behavior and consistent access across the application.
        """
        self._events: List[AuditEvent] = []
        self._store_lock = threading.Lock()
    
    @classmethod
    def get_instance(cls) -> 'AuditStore':
        """
        Get the singleton instance of the audit store.
        
        This method implements the singleton pattern with thread-safe initialization.
        Multiple calls will always return the same instance, ensuring consistent
        audit event storage across the entire application.
        
        Returns:
            AuditStore: The singleton audit store instance
            
        Example:
            store = AuditStore.get_instance()
            store.add_event(audit_event)
        """
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def add_event(self, event: AuditEvent) -> None:
        """
        Add an audit event to the store.
        
        Events are stored in chronological order (oldest first) to enable
        efficient retrieval of recent events. This method is thread-safe
        and can be called concurrently from multiple threads.
        
        Args:
            event: The AuditEvent instance to store
            
        Example:
            store = AuditStore.get_instance()
            
            audit_event = AuditEvent.create_event(
                event_type="tool_invocation",
                actor_user_id="user-123",
                actor_client_id="client-456",
                server_id="filesystem",
                status="success"
            )
            
            store.add_event(audit_event)
        """
        with self._store_lock:
            self._events.append(event)
    
    def get_events(self, limit: int = 100) -> List[AuditEvent]:
        """
        Retrieve the latest audit events in reverse chronological order.
        
        Returns the most recent events first (newest to oldest), up to the
        specified limit. This method is thread-safe and provides a consistent
        view of events even during concurrent modifications.
        
        Args:
            limit: Maximum number of events to return (default: 100)
            
        Returns:
            List[AuditEvent]: List of audit events in reverse chronological order
            
        Example:
            store = AuditStore.get_instance()
            
            # Get the 10 most recent events
            recent_events = store.get_events(limit=10)
            
            # Get all events (up to default limit)
            all_recent = store.get_events()
            
            # Process events (newest first)
            for event in recent_events:
                print(f"{event.timestamp}: {event.event_type}")
        """
        with self._store_lock:
            # Return a copy of the events in reverse order (newest first)
            # Using slicing to get the last 'limit' items, then reverse
            if len(self._events) <= limit:
                return self._events[::-1]  # Reverse entire list
            else:
                return self._events[-limit:][::-1]  # Last 'limit' items, reversed
    
    def get_events_by_type(self, event_type: str, limit: int = 100) -> List[AuditEvent]:
        """
        Retrieve audit events of a specific type in reverse chronological order.
        
        Filters events by event_type and returns the most recent matches.
        This method is useful for monitoring specific types of operations
        like authentication failures or policy denials.
        
        Args:
            event_type: The type of events to retrieve (e.g., "auth", "tool_invocation")
            limit: Maximum number of events to return (default: 100)
            
        Returns:
            List[AuditEvent]: Filtered list of audit events in reverse chronological order
            
        Example:
            store = AuditStore.get_instance()
            
            # Get recent authentication events
            auth_events = store.get_events_by_type("auth", limit=20)
            
            # Get recent tool invocations
            tool_events = store.get_events_by_type("tool_invocation", limit=50)
        """
        with self._store_lock:
            # Filter events by type and get the most recent ones
            filtered_events = [event for event in self._events if event.event_type == event_type]
            
            # Return in reverse chronological order (newest first)
            if len(filtered_events) <= limit:
                return filtered_events[::-1]
            else:
                return filtered_events[-limit:][::-1]
    
    def get_events_by_user(self, user_id: str, limit: int = 100) -> List[AuditEvent]:
        """
        Retrieve audit events for a specific user in reverse chronological order.
        
        Filters events by actor_user_id and returns the most recent matches.
        This method is useful for user activity monitoring and debugging
        user-specific issues.
        
        Args:
            user_id: The user ID to filter events for
            limit: Maximum number of events to return (default: 100)
            
        Returns:
            List[AuditEvent]: Filtered list of audit events in reverse chronological order
            
        Example:
            store = AuditStore.get_instance()
            
            # Get recent events for a specific user
            user_events = store.get_events_by_user("user-123", limit=25)
            
            # Analyze user activity
            for event in user_events:
                print(f"User {user_id}: {event.event_type} - {event.status}")
        """
        with self._store_lock:
            # Filter events by user and get the most recent ones
            filtered_events = [event for event in self._events if event.actor_user_id == user_id]
            
            # Return in reverse chronological order (newest first)
            if len(filtered_events) <= limit:
                return filtered_events[::-1]
            else:
                return filtered_events[-limit:][::-1]
    
    def get_events_by_server(self, server_id: str, limit: int = 100) -> List[AuditEvent]:
        """
        Retrieve audit events for a specific server in reverse chronological order.
        
        Filters events by server_id and returns the most recent matches.
        This method is useful for server-specific monitoring and debugging
        server-related issues.
        
        Args:
            server_id: The server ID to filter events for
            limit: Maximum number of events to return (default: 100)
            
        Returns:
            List[AuditEvent]: Filtered list of audit events in reverse chronological order
            
        Example:
            store = AuditStore.get_instance()
            
            # Get recent events for a specific server
            server_events = store.get_events_by_server("filesystem", limit=25)
            
            # Analyze server activity
            for event in server_events:
                print(f"Server {server_id}: {event.event_type} - {event.status}")
        """
        with self._store_lock:
            # Filter events by server and get the most recent ones
            filtered_events = [event for event in self._events if event.server_id == server_id]
            
            # Return in reverse chronological order (newest first)
            if len(filtered_events) <= limit:
                return filtered_events[::-1]
            else:
                return filtered_events[-limit:][::-1]
    
    def get_failed_events(self, limit: int = 100) -> List[AuditEvent]:
        """
        Retrieve failed audit events in reverse chronological order.
        
        Returns events with status indicating failure (error, denied, timeout).
        This method is useful for monitoring system health and identifying
        issues that require attention.
        
        Args:
            limit: Maximum number of events to return (default: 100)
            
        Returns:
            List[AuditEvent]: Filtered list of failed events in reverse chronological order
            
        Example:
            store = AuditStore.get_instance()
            
            # Get recent failures for monitoring
            failures = store.get_failed_events(limit=10)
            
            # Alert on authentication failures
            auth_failures = [e for e in failures if e.event_type == "auth"]
            if len(auth_failures) > 5:
                send_alert("High authentication failure rate detected")
        """
        with self._store_lock:
            # Filter events by failure status
            failed_statuses = {"error", "denied", "timeout"}
            failed_events = [event for event in self._events if event.status in failed_statuses]
            
            # Return in reverse chronological order (newest first)
            if len(failed_events) <= limit:
                return failed_events[::-1]
            else:
                return failed_events[-limit:][::-1]
    
    def count(self) -> int:
        """
        Get the total number of audit events in the store.
        
        Returns:
            int: Total number of stored audit events
            
        Example:
            store = AuditStore.get_instance()
            total_events = store.count()
            print(f"Total audit events: {total_events}")
        """
        with self._store_lock:
            return len(self._events)
    
    def clear(self) -> None:
        """
        Remove all audit events from the store.
        
        This method clears all stored events and is useful for testing,
        maintenance, or when implementing log rotation policies. The operation
        is thread-safe and atomic.
        
        Example:
            store = AuditStore.get_instance()
            
            # Clear all events (e.g., for testing)
            store.clear()
            
            # Verify store is empty
            assert store.count() == 0
        """
        with self._store_lock:
            self._events.clear()
    
    def get_stats(self) -> dict:
        """
        Get statistics about the audit events in the store.
        
        Returns a dictionary with various statistics about stored events,
        including counts by type, status, and other useful metrics.
        
        Returns:
            dict: Statistics about stored audit events
            
        Example:
            store = AuditStore.get_instance()
            stats = store.get_stats()
            
            print(f"Total events: {stats['total_events']}")
            print(f"Success rate: {stats['success_rate']:.2%}")
            print(f"Event types: {stats['event_types']}")
        """
        with self._store_lock:
            if not self._events:
                return {
                    "total_events": 0,
                    "event_types": {},
                    "status_counts": {},
                    "success_rate": 0.0,
                    "failure_rate": 0.0
                }
            
            # Count events by type
            event_types = {}
            status_counts = {}
            success_count = 0
            
            for event in self._events:
                # Count by event type
                event_types[event.event_type] = event_types.get(event.event_type, 0) + 1
                
                # Count by status
                status_counts[event.status] = status_counts.get(event.status, 0) + 1
                
                # Count successes
                if event.status == "success":
                    success_count += 1
            
            total_events = len(self._events)
            success_rate = success_count / total_events if total_events > 0 else 0.0
            failure_rate = 1.0 - success_rate
            
            return {
                "total_events": total_events,
                "event_types": event_types,
                "status_counts": status_counts,
                "success_rate": success_rate,
                "failure_rate": failure_rate
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Alias for get_stats() for convenience."""
        return self.get_stats()


# Convenience function to get the singleton instance
def get_audit_store() -> AuditStore:
    """
    Convenience function to get the singleton audit store instance.
    
    This function provides a simple way to access the audit store without
    needing to call the class method directly. It's the recommended way
    to access the audit store throughout the application.
    
    Returns:
        AuditStore: The singleton audit store instance
        
    Example:
        from mcp_gateway.audit.store import get_audit_store
        
        store = get_audit_store()
        store.add_event(audit_event)
    """
    return AuditStore.get_instance()
