"""
Test circuit breaker integration with session manager and service registry.
Tests the end-to-end integration of circuit breakers with MCP operations.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.mcp_gateway.circuit_breaker.exceptions import CircuitBreakerOpenError
from src.mcp_gateway.circuit_breaker.manager import CircuitBreakerManager
from src.mcp_gateway.circuit_breaker.breaker import CircuitBreakerState
from src.mcp_gateway.mcp.session_manager import MCPSessionManager, MCPSessionConfig
from src.mcp_gateway.mcp.client_wrapper import MCPClientWrapper
from src.mcp_gateway.core.service_registry import ServiceRegistry
from src.mcp_gateway.mcp.exceptions import MCPSessionError


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration across components."""
    
    @pytest.fixture
    def circuit_breaker_manager(self):
        """Create a circuit breaker manager for testing."""
        return CircuitBreakerManager()
    
    @pytest.fixture
    def session_manager(self, circuit_breaker_manager):
        """Create a session manager with circuit breaker."""
        return MCPSessionManager(
            circuit_breaker_manager=circuit_breaker_manager,
            max_sessions=10
        )
    
    @pytest.fixture
    def service_registry(self):
        """Create a service registry with circuit breaker manager."""
        registry = ServiceRegistry()
        return registry
    
    @pytest.fixture
    def client_wrapper(self, circuit_breaker_manager):
        """Create a client wrapper with circuit breaker manager."""
        return MCPClientWrapper(
            circuit_breaker_manager=circuit_breaker_manager,
            default_timeout=30.0,
            max_retries=3
        )
    
    @pytest.mark.asyncio
    async def test_session_creation_with_circuit_breaker(self, session_manager):
        """Test that session creation uses circuit breaker protection."""
        config = MCPSessionConfig(
            session_id="test-session-1",
            server_name="test-server",
            transport_config={
                "type": "stdio",
                "command": ["python", "-m", "echo"],
                "args": []
            }
        )
        
        # Mock the transport factory to simulate failure
        with patch('src.mcp_gateway.mcp.session_manager.MCPTransportFactory') as mock_factory:
            mock_factory.create_transport.side_effect = Exception("Connection failed")
            
            # Session creation should handle the error via circuit breaker
            with pytest.raises(Exception):
                await session_manager.create_session(config)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_open_prevents_calls(self, session_manager):
        """Test that open circuit breaker prevents further calls."""
        config = MCPSessionConfig(
            session_id="test-session-2",
            server_name="failing-server",
            transport_config={
                "type": "stdio",
                "command": ["python", "-m", "nonexistent"],
                "args": []
            }
        )
        
        # Force circuit breaker to open state by triggering failures
        server_key = session_manager._get_server_key(config)
        breaker = await session_manager.circuit_breaker_manager.get_breaker(server_key)
        
        # Manually trigger failures to open the circuit
        for _ in range(breaker.config.failure_threshold + 1):
            # Simulate the proper circuit breaker workflow
            if await breaker.should_allow_call():
                try:
                    await self._failing_operation()
                    await breaker.record_success()
                except Exception as e:
                    await breaker.record_failure(e)
            else:
                # Circuit is already open
                break
        
        # Circuit should now be open
        assert breaker.state == CircuitBreakerState.OPEN
        
        # Further calls should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            await session_manager.circuit_breaker_manager.check_and_call(
                server_key,
                self._failing_operation
            )
    
    async def _failing_operation(self):
        """Helper method that always fails."""
        raise Exception("Simulated failure")
    
    @pytest.mark.asyncio
    async def test_service_registry_circuit_breaker_manager(self, service_registry):
        """Test that service registry has circuit breaker manager."""
        assert hasattr(service_registry, 'circuit_breaker_manager')
        assert isinstance(service_registry.circuit_breaker_manager, CircuitBreakerManager)
    
    @pytest.mark.asyncio
    async def test_client_wrapper_circuit_breaker_integration(self, client_wrapper):
        """Test that client wrapper integrates with circuit breaker."""
        # Verify session manager has circuit breaker
        assert hasattr(client_wrapper._session_manager, 'circuit_breaker_manager')
        assert isinstance(
            client_wrapper._session_manager.circuit_breaker_manager,
            CircuitBreakerManager
        )
    
    @pytest.mark.asyncio
    async def test_call_tool_with_breaker(self, session_manager):
        """Test tool calling with circuit breaker protection."""
        # Create a mock session
        session_id = "test-session"
        mock_session = AsyncMock()
        mock_session.call_tool.return_value = {"result": "success"}
        
        # Mock session storage
        session_manager._sessions[session_id] = mock_session
        session_manager._session_info[session_id] = MagicMock()
        session_manager._session_configs[session_id] = MCPSessionConfig(
            session_id=session_id,
            server_name="test-server",
            transport_config={"type": "stdio", "command": ["echo"], "args": []}
        )
        
        # Call tool with breaker protection
        result = await session_manager.call_tool_with_breaker(
            session_id=session_id,
            tool_name="test_tool",
            arguments={"arg1": "value1"}
        )
        
        assert result == {"result": "success"}
        mock_session.call_tool.assert_called_once_with("test_tool", {"arg1": "value1"})
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_stats(self, session_manager):
        """Test getting circuit breaker statistics."""
        stats = await session_manager.get_circuit_breaker_stats()
        assert isinstance(stats, dict)
        assert "total_breakers" in stats
        assert "breakers" in stats
    
    @pytest.mark.asyncio
    async def test_heartbeat_with_circuit_breaker(self, session_manager):
        """Test heartbeat functionality with circuit breaker protection."""
        session_id = "heartbeat-test"
        
        # Mock session and config
        mock_session = AsyncMock()
        mock_session.list_tools.return_value = []
        
        config = MCPSessionConfig(
            server_name="heartbeat-server",
            transport_config={"type": "stdio", "command": ["echo"], "args": []},
            heartbeat_interval=0.1  # Short interval for testing
        )
        
        session_manager._sessions[session_id] = mock_session
        session_manager._session_configs[session_id] = config
        session_manager._session_info[session_id] = MagicMock()
        session_manager._session_info[session_id].last_activity = None
        session_manager._session_info[session_id].status = "active"
        session_manager._session_info[session_id].error_count = 0
        
        # Start heartbeat and let it run briefly
        heartbeat_task = asyncio.create_task(
            session_manager._heartbeat_loop(session_id)
        )
        
        # Wait a bit then cancel
        await asyncio.sleep(0.2)
        heartbeat_task.cancel()
        
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        
        # Verify heartbeat was called
        assert mock_session.list_tools.called


if __name__ == "__main__":
    pytest.main([__file__])
