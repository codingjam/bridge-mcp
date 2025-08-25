"""
MCP Client Router

FastAPI router for native MCP client operations.
Provides endpoints for connecting to MCP servers and executing operations
using the native MCP protocol with authentication integration.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import JSONResponse

from ..mcp.client_wrapper import MCPClientWrapper
from ..mcp.session_manager import MCPSessionManager
from ..mcp.service_adapter import ServiceRegistryMCPAdapter
from ..mcp.exceptions import MCPClientError, MCPConnectionError, MCPSessionError

# Import existing auth dependencies - REUSE EXISTING PATTERNS
from ..core.service_registry import ServiceRegistry
from ..core.authenticated_proxy import AuthenticatedMCPProxyService
from ..auth.authentication_middleware import get_current_user, get_access_token
from ..auth.models import UserContext
from ..auth.obo_service import OBOTokenService
from ..core.config import get_settings

# Import API models
from .models.mcp import (
    ConnectServerRequest,
    ConnectServerResponse,
    ListToolsResponse,
    CallToolRequest,
    CallToolResponse,
    ListResourcesResponse,
    ReadResourceRequest,
    ReadResourceResponse,
    ServerInfoResponse,
    SessionListResponse,
)
from .models.common import ErrorResponse, SuccessResponse, HealthResponse

logger = logging.getLogger(__name__)


# Dependency injection functions - REUSE PATTERNS FROM routes.py
async def get_service_registry() -> ServiceRegistry:
    """
    Dependency injection for service registry
    Import here to avoid circular dependency
    """
    from mcp_gateway.main import get_service_registry as get_registry
    return await get_registry()


async def get_obo_service() -> Optional[OBOTokenService]:
    """
    Dependency injection for OBO service
    Returns OBO service if authentication is enabled
    """
    settings = get_settings()
    auth_config = settings.get_auth_config()
    if auth_config and auth_config.enable_obo:
        return OBOTokenService(auth_config)
    return None


async def get_proxy_service(
    service_registry: ServiceRegistry = Depends(get_service_registry),
    obo_service: Optional[OBOTokenService] = Depends(get_obo_service),
) -> AuthenticatedMCPProxyService:
    """
    Dependency injection for authenticated proxy service
    REUSES the exact same pattern as api/routes.py
    """
    return AuthenticatedMCPProxyService(
        service_registry=service_registry,
        obo_service=obo_service
    )


# Global MCP client instance
_mcp_client: Optional[MCPClientWrapper] = None
_mcp_adapter: Optional[ServiceRegistryMCPAdapter] = None


# Create MCP router
mcp_router = APIRouter(prefix="/mcp", tags=["MCP Client"])


async def get_mcp_client() -> MCPClientWrapper:
    """Get or create MCP client instance."""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = MCPClientWrapper()
    return _mcp_client


async def get_mcp_adapter() -> ServiceRegistryMCPAdapter:
    """Get or create MCP adapter instance."""
    global _mcp_adapter
    if _mcp_adapter is None:
        service_registry = await get_service_registry()
        _mcp_adapter = ServiceRegistryMCPAdapter(service_registry)
    return _mcp_adapter


# Simplified proxy endpoint for Agent Integration Guide compatibility
@mcp_router.post("/proxy")
async def mcp_simple_proxy(
    http_request: Request,
    registry: ServiceRegistry = Depends(get_service_registry),
    proxy: AuthenticatedMCPProxyService = Depends(get_proxy_service),
    user: Optional[UserContext] = Depends(get_current_user),
):
    """
    Simplified MCP proxy endpoint that accepts JSON-RPC requests and routes them
    to the appropriate MCP server. Compatible with Agent Integration Guide patterns.
    """
    try:
        # Parse JSON-RPC request
        request_data = await http_request.json()
        
        # Extract method and server name
        method = request_data.get("method")
        params = request_data.get("params", {})
        
        # Determine target server from params or routing rules
        server_name = params.get("server_name") or request_data.get("server_name")
        if not server_name:
            raise HTTPException(
                status_code=400,
                detail="Server name required in request"
            )
        
        # Get service configuration for auth requirements
        service = await registry.get_service(server_name)
        if not service:
            raise HTTPException(
                status_code=404,
                detail=f"Service '{server_name}' not found"
            )

        if not service.enabled:
            raise HTTPException(
                status_code=503,
                detail=f"Service '{server_name}' is disabled"
            )

        # Extract access token from request (same pattern as routes.py)
        user_token = get_access_token(http_request)
        
        # Handle authentication based on service auth strategy
        headers = {}
        
        if service.auth.strategy in ["obo_required", "passthrough"]:
            if not user_token:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required for this service"
                )
            
            if service.auth.strategy == "obo_required":
                # Use OBO token exchange (same pattern as routes.py)
                if not proxy.obo_service:
                    raise HTTPException(
                        status_code=500,
                        detail="OBO service not configured"
                    )
                
                # Get OBO token for the target service
                obo_token = await proxy._get_obo_token(
                    downstream_token=user_token,
                    target_audience=service.auth.target_audience
                )
                headers["Authorization"] = f"Bearer {obo_token}"
                
            elif service.auth.strategy == "passthrough":
                # Pass through the original token
                headers["Authorization"] = f"Bearer {user_token}"
        
        # Route request based on method
        if method == "tools/list":
            # Handle tool listing
            client = await get_mcp_client()
            # Use existing session or create temporary one
            tools = await client.list_tools_direct(server_name, headers)
            return {
                "jsonrpc": "2.0",
                "id": request_data.get("id"),
                "result": {"tools": tools}
            }
            
        elif method == "tools/call":
            # Handle tool execution
            client = await get_mcp_client()
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            
            result = await client.call_tool_direct(
                server_name, tool_name, arguments, headers
            )
            return {
                "jsonrpc": "2.0",
                "id": request_data.get("id"),
                "result": result
            }
            
        else:
            # Generic JSON-RPC forwarding
            adapter = await get_mcp_adapter()
            response = await adapter.forward_request(
                server_name=server_name,
                request_data=request_data,
                headers=headers
            )
            return response
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in MCP proxy: {e}")
        return {
            "jsonrpc": "2.0",
            "id": request_data.get("id") if "request_data" in locals() else None,
            "error": {
                "code": -32603,
                "message": "Internal error",
                "data": str(e)
            }
        }


# Session-based MCP Endpoints (Advanced Usage)
@mcp_router.post("/servers/connect", response_model=ConnectServerResponse)
async def connect_server(
    request: ConnectServerRequest,
    http_request: Request,
    registry: ServiceRegistry = Depends(get_service_registry),
    proxy: AuthenticatedMCPProxyService = Depends(get_proxy_service),
    user: Optional[UserContext] = Depends(get_current_user),
    client: MCPClientWrapper = Depends(get_mcp_client)
):
    """Connect to an MCP server with authentication and OBO token support."""
    try:
        # Get service configuration for auth requirements
        service = await registry.get_service(request.server_name)
        if not service:
            raise HTTPException(
                status_code=404,
                detail=f"Service '{request.server_name}' not found"
            )

        if not service.enabled:
            raise HTTPException(
                status_code=503,
                detail=f"Service '{request.server_name}' is disabled"
            )

        # Extract access token from request (same pattern as routes.py)
        user_token = get_access_token(http_request)
        
        # Handle authentication based on service auth strategy
        transport_config = request.transport_config.copy()
        
        if service.auth.strategy in ["obo_required", "passthrough"]:
            if not user_token:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required for this service"
                )
            
            if service.auth.strategy == "obo_required":
                # Use OBO token exchange (same pattern as routes.py)
                if not proxy.obo_service:
                    raise HTTPException(
                        status_code=500,
                        detail="OBO service not configured"
                    )
                
                # Get OBO token for the target service
                obo_token = await proxy._get_obo_token(
                    downstream_token=user_token,
                    target_audience=service.auth.target_audience
                )
                
                # Add OBO token to transport config
                transport_config.setdefault("headers", {})
                transport_config["headers"]["Authorization"] = f"Bearer {obo_token}"
                
            elif service.auth.strategy == "passthrough":
                # Pass through the original token
                transport_config.setdefault("headers", {})
                transport_config["headers"]["Authorization"] = f"Bearer {user_token}"
        
        # Connect to MCP server with authenticated transport
        session_id = await client.connect_server(
            server_name=request.server_name,
            transport_config=transport_config,
            session_id=request.session_id
        )
        
        logger.info(f"Successfully connected to MCP server '{request.server_name}' with session {session_id}")
        
        return ConnectServerResponse(
            session_id=session_id,
            server_name=request.server_name,
            status="connected"
        )
        
    except HTTPException:
        raise
    except MCPConnectionError as e:
        logger.error(f"MCP connection failed for service '{request.server_name}': {e.message}")
        raise HTTPException(
            status_code=400,
            detail=f"Connection failed: {e.message}"
        )
    except Exception as e:
        logger.error(f"Unexpected error connecting to server '{request.server_name}': {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@mcp_router.get("/sessions/{session_id}/tools", response_model=ListToolsResponse)
async def list_tools(
    session_id: str,
    user: Optional[UserContext] = Depends(get_current_user),
    client: MCPClientWrapper = Depends(get_mcp_client)
):
    """List available tools from an MCP server with authentication."""
    try:
        # Validate user has access to this session
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )
        
        tools = await client.list_tools(session_id)
        return ListToolsResponse(
            session_id=session_id,
            tools=[
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema
                }
                for tool in tools
            ]
        )
    except MCPSessionError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {e.message}"
        )
    except MCPClientError as e:
        raise HTTPException(
            status_code=400,
            detail=f"MCP client error: {e.message}"
        )
    except Exception as e:
        logger.error(f"Error listing tools for session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@mcp_router.post("/sessions/{session_id}/tools/call", response_model=CallToolResponse)
async def call_tool(
    session_id: str,
    request: CallToolRequest,
    user: Optional[UserContext] = Depends(get_current_user),
    client: MCPClientWrapper = Depends(get_mcp_client)
):
    """Call a tool on an MCP server with authentication."""
    try:
        # Validate user has access to this session
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )
        
        result = await client.call_tool(
            session_id=session_id,
            tool_name=request.tool_name,
            arguments=request.arguments or {}
        )
        
        return CallToolResponse(
            session_id=session_id,
            tool_name=request.tool_name,
            result=result,
            success=True
        )
        
    except MCPSessionError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {e.message}"
        )
    except MCPClientError as e:
        logger.error(f"Tool call failed for {request.tool_name}: {e.message}")
        return CallToolResponse(
            session_id=session_id,
            tool_name=request.tool_name,
            result={},
            success=False,
            error=e.message
        )
    except Exception as e:
        logger.error(f"Unexpected error calling tool {request.tool_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
