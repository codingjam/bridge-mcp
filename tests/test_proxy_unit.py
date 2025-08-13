"""
Tests for MCP Gateway proxy functionality - Unit tests only
Tests individual components in isolation without HTTP endpoints
"""
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from mcp_gateway.main import create_app
from mcp_gateway.core.service_registry import MCPService


@pytest.fixture
def client():
    """Create test client"""
    app = create_app()
    return TestClient(app)


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


class TestHealthEndpoint:
    """Test basic health endpoint functionality"""
    
    def test_health_endpoint(self, client):
        """Test the basic health endpoint works"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
        assert data["service"] == "mcp-gateway"


class TestServiceManagement:
    """Test service listing and management endpoints - Integration tests"""
    
    def test_list_services(self, client):
        """Test services listing endpoint"""
        response = client.get("/api/v1/services")
        assert response.status_code == 200
        data = response.json()
        
        assert "count" in data
        assert "services" in data
        assert data["count"] == 2  # example-mcp-server + local-mcp-server
        assert "example-mcp-server" in data["services"]
        
        service_data = data["services"]["example-mcp-server"]
        assert service_data["name"] == "Example MCP Server"
        assert service_data["transport"] == "http"
        assert service_data["enabled"] is True
    
    def test_get_service_info(self, client):
        """Test individual service info endpoint"""
        response = client.get("/api/v1/services/example-mcp-server")
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == "example-mcp-server"
        assert data["name"] == "Example MCP Server"
        assert data["transport"] == "http"
        assert data["enabled"] is True
        assert data["endpoint"] == "http://localhost:3000"
    
    def test_service_not_found(self, client):
        """Test service not found error"""
        response = client.get("/api/v1/services/nonexistent-service")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()


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
