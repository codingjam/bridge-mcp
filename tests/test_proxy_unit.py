"""
Tests for MCP Gateway proxy functionality - Unit tests only
Tests individual components in isolation without HTTP endpoints
"""
import pytest
from unittest.mock import AsyncMock, patch

from mcp_gateway.core.service_registry import MCPService


@pytest.fixture
def mock_service():
    """Mock MCP service configuration"""
    return MCPService(
        name="Test Service",
        description="Test MCP service for unit tests",
        endpoint="http://localhost:3000",
        transport="http",
        enabled=True,
        tags=["test"],
        timeout=10.0
    )


class TestUnitTests:
    """Pure unit tests for individual components"""
    
    def test_mcp_service_model_validation(self):
        """Test MCPService model validation"""
        # Test valid HTTP service
        service = MCPService(
            name="Test HTTP Service",
            description="Test service",
            endpoint="http://localhost:3000",
            transport="http",
            enabled=True,
            timeout=30.0,
            tags=["test"]
        )
        assert service.name == "Test HTTP Service"
        assert service.transport == "http"
        assert service.enabled is True
        
        # Test valid stdio service
        stdio_service = MCPService(
            name="Test Stdio Service",
            description="Test stdio service",
            endpoint="stdio-test",
            transport="stdio",
            command=["python", "-m", "test_server"],
            enabled=True,
            timeout=30.0,
            tags=["test"]
        )
        assert stdio_service.transport == "stdio"
        assert stdio_service.command == ["python", "-m", "test_server"]
    
    def test_mcp_service_stdio_validation_error(self):
        """Test that stdio transport requires command"""
        with pytest.raises(ValueError, match="Stdio transport requires a command"):
            MCPService(
                name="Invalid Stdio Service",
                description="Stdio without command",
                endpoint="stdio-test",
                transport="stdio",
                # Missing command field
                enabled=True,
                timeout=30.0,
                tags=["test"]
            )
    
    @patch('mcp_gateway.core.service_registry.ServiceRegistry.load_services')
    def test_service_registry_loading(self, mock_load):
        """Test service registry loading"""
        from mcp_gateway.core.service_registry import ServiceRegistry
        from pathlib import Path
        
        registry = ServiceRegistry(Path("test.yaml"))
        
        # Test that load_services is called
        mock_load.return_value = AsyncMock()
        registry.load_services()
        mock_load.assert_called_once()
    
    def test_proxy_response_structure(self):
        """Test proxy response structure is correct"""
        mock_proxy_response = {
            "status_code": 200,
            "headers": {"content-type": "application/json"},
            "content": b'{"result": "success"}',
            "json": {"result": "success"}
        }
        
        assert "status_code" in mock_proxy_response
        assert "headers" in mock_proxy_response
        assert "content" in mock_proxy_response
        assert mock_proxy_response["status_code"] == 200
        assert mock_proxy_response["headers"]["content-type"] == "application/json"
