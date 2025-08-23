"""
MCP Client Integration Module

This module provides MCP (Model Context Protocol) client functionality
for the MCP Gateway, implementing Phase 0 of MCP compliance.

This module integrates with the existing ServiceRegistry and services.yaml
configuration system rather than creating separate configuration.
"""

from .client_wrapper import MCPClientWrapper
from .session_manager import MCPSessionManager
from .transport_factory import MCPTransportFactory
from .service_adapter import ServiceRegistryMCPAdapter, create_mcp_adapter
from .fastapi_integration import mcp_router, initialize_mcp_client, shutdown_mcp_client, mcp_lifespan
from .exceptions import (
    MCPClientError, MCPConnectionError, MCPTransportError,
    MCPAuthenticationError, MCPSessionError, MCPProtocolError
)

__all__ = [
    "MCPClientWrapper",
    "MCPSessionManager", 
    "MCPTransportFactory",
    "ServiceRegistryMCPAdapter",
    "create_mcp_adapter",
    "mcp_router",
    "initialize_mcp_client",
    "shutdown_mcp_client",
    "mcp_lifespan",
    "MCPClientError",
    "MCPConnectionError", 
    "MCPTransportError",
    "MCPAuthenticationError",
    "MCPSessionError", 
    "MCPProtocolError",
]
