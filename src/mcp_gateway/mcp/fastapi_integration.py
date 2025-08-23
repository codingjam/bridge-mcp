"""
FastAPI Integration for MCP Client

Provides FastAPI routes and middleware for MCP client operations,
integrating with the existing MCP Gateway architecture.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .client_wrapper import MCPClientWrapper
from .session_manager import MCPSessionManager
from .service_adapter import ServiceRegistryMCPAdapter
from .exceptions import MCPClientError, MCPConnectionError, MCPSessionError

# Import existing auth dependencies - REUSE EXISTING PATTERNS
from ..core.service_registry import ServiceRegistry
from ..core.authenticated_proxy import AuthenticatedMCPProxyService
from ..auth.authentication_middleware import get_current_user, get_access_token
from ..auth.models import UserContext
from ..auth.obo_service import OBOTokenService
from ..core.config import get_settings


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
    obo_service: Optional[OBOTokenService] = Depends(get_obo_service)
) -> AuthenticatedMCPProxyService:
    """
    Dependency injection for authenticated proxy service
    Returns a new proxy service instance for each request
    """
    return AuthenticatedMCPProxyService(obo_service=obo_service)


# Request/Response Models
class ConnectServerRequest(BaseModel):
    """Request to connect to an MCP server."""
    server_name: str
    transport_config: Dict[str, Any]
    session_id: Optional[str] = None


class ConnectServerResponse(BaseModel):
    """Response from server connection."""
    session_id: str
    server_name: str
    status: str


class ListToolsResponse(BaseModel):
    """Response for listing tools."""
    session_id: str
    tools: List[Dict[str, Any]]


class CallToolRequest(BaseModel):
    """Request to call a tool."""
    tool_name: str
    arguments: Optional[Dict[str, Any]] = None


class CallToolResponse(BaseModel):
    """Response from tool call."""
    session_id: str
    tool_name: str
    result: Dict[str, Any]
    success: bool
    error: Optional[str] = None


class ListResourcesResponse(BaseModel):
    """Response for listing resources."""
    session_id: str
    resources: List[Dict[str, Any]]


class ReadResourceRequest(BaseModel):
    """Request to read a resource."""
    uri: str


class ReadResourceResponse(BaseModel):
    """Response from resource read."""
    session_id: str
    uri: str
    content: Dict[str, Any]


class ServerInfoResponse(BaseModel):
    """Response for server information."""
    session_id: str
    server_info: Dict[str, Any]


class SessionListResponse(BaseModel):
    """Response for session list."""
    sessions: Dict[str, Dict[str, Any]]


# Global MCP client instance
_mcp_client: Optional[MCPClientWrapper] = None
_mcp_adapter: Optional[ServiceRegistryMCPAdapter] = None


async def get_mcp_client() -> MCPClientWrapper:
    """Dependency to get MCP client instance."""
    global _mcp_client
    if _mcp_client is None:
        raise HTTPException(
            status_code=500,
            detail="MCP client not initialized"
        )
    return _mcp_client


async def get_mcp_adapter() -> ServiceRegistryMCPAdapter:
    """Dependency to get MCP adapter instance."""
    global _mcp_adapter
    if _mcp_adapter is None:
        raise HTTPException(
            status_code=500,
            detail="MCP adapter not initialized"
        )
    return _mcp_adapter


# FastAPI router for MCP endpoints
mcp_router = APIRouter(prefix="/mcp", tags=["MCP Client"])


# Simplified MCP Proxy Endpoint (Agent Integration Guide Compatible)
@mcp_router.post("/{service_id}")
async def mcp_simple_proxy(
    service_id: str,
    mcp_request: Dict[str, Any],
    http_request: Request,
    registry: ServiceRegistry = Depends(get_service_registry),
    proxy: AuthenticatedMCPProxyService = Depends(get_proxy_service),
    user: Optional[UserContext] = Depends(get_current_user),
    adapter: ServiceRegistryMCPAdapter = Depends(get_mcp_adapter),
    client: MCPClientWrapper = Depends(get_mcp_client)
):
    """
    Simplified MCP proxy endpoint - Compatible with Agent Integration Guide.
    
    Automatically manages sessions behind the scenes and handles OBO authentication.
    Supports JSON-RPC 2.0 requests like:
    {
        "method": "tools/list",
        "params": {},
        "id": 1
    }
    """
    try:
        # Validate service exists and is enabled
        service = await registry.get_service(service_id)
        if not service:
            return {
                "jsonrpc": "2.0",
                "id": mcp_request.get("id", 1),
                "error": {
                    "code": -32602,
                    "message": f"Service '{service_id}' not found"
                }
            }
        
        if not service.enabled:
            return {
                "jsonrpc": "2.0", 
                "id": mcp_request.get("id", 1),
                "error": {
                    "code": -32602,
                    "message": f"Service '{service_id}' is disabled"
                }
            }
        
        # Extract and handle authentication (same pattern as routes.py)
        user_token = get_access_token(http_request)
        transport_config = {"type": "http", "url": service.url}
        
        if service.auth.strategy in ["obo_required", "passthrough"]:
            if not user_token:
                return {
                    "jsonrpc": "2.0",
                    "id": mcp_request.get("id", 1),
                    "error": {
                        "code": -32003,
                        "message": "Authentication required for this service"
                    }
                }
            
            if service.auth.strategy == "obo_required":
                # Use OBO token exchange
                if not proxy.obo_service:
                    return {
                        "jsonrpc": "2.0",
                        "id": mcp_request.get("id", 1), 
                        "error": {
                            "code": -32603,
                            "message": "OBO service not configured"
                        }
                    }
                
                obo_token = await proxy._get_obo_token(
                    downstream_token=user_token,
                    target_audience=service.auth.target_audience
                )
                transport_config.setdefault("headers", {})
                transport_config["headers"]["Authorization"] = f"Bearer {obo_token}"
                
            elif service.auth.strategy == "passthrough":
                # Pass through the original token
                transport_config.setdefault("headers", {})
                transport_config["headers"]["Authorization"] = f"Bearer {user_token}"
        
        # Get or create session automatically (simplified for agents)
        client_id = user.user_id if user else "anonymous"
        session_key = f"auto_{client_id}_{service_id}"
        
        # For now, create a new session each time (can be optimized later)
        session_id = await client.connect_server(
            server_name=service_id,
            transport_config=transport_config
        )
        
        # Route JSON-RPC method to appropriate MCP operation
        method = mcp_request.get("method")
        params = mcp_request.get("params", {})
        request_id = mcp_request.get("id", 1)
        
        if method == "tools/list":
            tools = await client.list_tools(session_id)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema
                        } for tool in tools
                    ]
                }
            }
            
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            if not tool_name:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": "Missing required parameter: name"
                    }
                }
            
            result = await client.call_tool(session_id, tool_name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": content.type,
                            "text": getattr(content, 'text', None),
                            "data": getattr(content, 'data', None)
                        }
                        for content in result.content
                    ],
                    "isError": result.isError
                }
            }
            
        elif method == "resources/list":
            resources = await client.list_resources(session_id)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "resources": [
                        {
                            "uri": resource.uri,
                            "name": resource.name,
                            "description": resource.description,
                            "mimeType": resource.mimeType
                        } for resource in resources
                    ]
                }
            }
            
        elif method == "resources/read":
            uri = params.get("uri")
            if not uri:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": "Missing required parameter: uri"
                    }
                }
            
            result = await client.read_resource(session_id, uri)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "contents": [
                        {
                            "type": content.type,
                            "uri": getattr(content, 'uri', None),
                            "text": getattr(content, 'text', None),
                            "blob": getattr(content, 'blob', None)
                        }
                        for content in result.contents
                    ]
                }
            }
            
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
            
    except Exception as e:
        logger.error(f"Error in simplified MCP proxy for service {service_id}: {e}")
        return {
            "jsonrpc": "2.0",
            "id": mcp_request.get("id", 1),
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
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


@mcp_router.delete("/sessions/{session_id}")
async def disconnect_server(
    session_id: str,
    client: MCPClientWrapper = Depends(get_mcp_client)
):
    """Disconnect from an MCP server."""
    try:
        success = await client.disconnect_server(session_id)
        if success:
            return {"message": f"Session {session_id} disconnected successfully"}
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
    except Exception as e:
        logger.error(f"Error disconnecting session {session_id}: {e}")
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
            detail=f"Client error: {e.message}"
        )


@mcp_router.post("/sessions/{session_id}/tools/call", response_model=CallToolResponse)
async def call_tool(
    session_id: str,
    request: CallToolRequest,
    http_request: Request,
    user: Optional[UserContext] = Depends(get_current_user),
    client: MCPClientWrapper = Depends(get_mcp_client)
):
    """Call a tool on an MCP server with authentication."""
    try:
        # Validate user has access to this session
        # In a real implementation, we'd check session ownership
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )
        
        result = await client.call_tool(
            session_id=session_id,
            tool_name=request.tool_name,
            arguments=request.arguments
        )
        
        logger.info(f"User {user.user_id} called tool '{request.tool_name}' on session {session_id}")
        
        return CallToolResponse(
            session_id=session_id,
            tool_name=request.tool_name,
            result={
                "content": [
                    {
                        "type": content.type,
                        "text": getattr(content, 'text', None),
                        "data": getattr(content, 'data', None)
                    }
                    for content in result.content
                ],
                "isError": result.isError
            },
            success=not result.isError
        )
        
    except MCPSessionError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {e.message}"
        )
    except MCPClientError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Tool call failed: {e.message}"
        )


@mcp_router.get("/sessions/{session_id}/resources", response_model=ListResourcesResponse)
async def list_resources(
    session_id: str,
    client: MCPClientWrapper = Depends(get_mcp_client)
):
    """List available resources from an MCP server."""
    try:
        resources = await client.list_resources(session_id)
        return ListResourcesResponse(
            session_id=session_id,
            resources=[
                {
                    "uri": resource.uri,
                    "name": resource.name,
                    "description": resource.description,
                    "mimeType": resource.mimeType
                }
                for resource in resources
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
            detail=f"Client error: {e.message}"
        )


@mcp_router.post("/sessions/{session_id}/resources/read", response_model=ReadResourceResponse)
async def read_resource(
    session_id: str,
    request: ReadResourceRequest,
    client: MCPClientWrapper = Depends(get_mcp_client)
):
    """Read a resource from an MCP server."""
    try:
        result = await client.read_resource(session_id, request.uri)
        
        return ReadResourceResponse(
            session_id=session_id,
            uri=request.uri,
            content={
                "contents": [
                    {
                        "type": content.type,
                        "uri": getattr(content, 'uri', None),
                        "text": getattr(content, 'text', None),
                        "blob": getattr(content, 'blob', None)
                    }
                    for content in result.contents
                ]
            }
        )
        
    except MCPSessionError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {e.message}"
        )
    except MCPClientError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Resource read failed: {e.message}"
        )


@mcp_router.get("/sessions/{session_id}/info", response_model=ServerInfoResponse)
async def get_server_info(
    session_id: str,
    client: MCPClientWrapper = Depends(get_mcp_client)
):
    """Get information about an MCP server."""
    try:
        info = await client.get_server_info(session_id)
        return ServerInfoResponse(
            session_id=session_id,
            server_info=info
        )
    except MCPSessionError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {e.message}"
        )


@mcp_router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    client: MCPClientWrapper = Depends(get_mcp_client)
):
    """List all active MCP sessions."""
    try:
        sessions = await client.list_active_sessions()
        return SessionListResponse(sessions=sessions)
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@mcp_router.get("/sessions/{session_id}/health")
async def health_check(
    session_id: str,
    client: MCPClientWrapper = Depends(get_mcp_client)
):
    """Perform health check on an MCP session."""
    try:
        healthy = await client.health_check(session_id)
        return {
            "session_id": session_id,
            "healthy": healthy,
            "status": "ok" if healthy else "error"
        }
    except Exception as e:
        logger.error(f"Health check error for session {session_id}: {e}")
        return {
            "session_id": session_id,
            "healthy": False,
            "status": "error",
            "error": str(e)
        }


# Configuration endpoints
@mcp_router.get("/config")
async def get_config(
    adapter: ServiceRegistryMCPAdapter = Depends(get_mcp_adapter)
):
    """Get current MCP configuration from ServiceRegistry."""
    return {
        "global": adapter.get_global_config(),
        "services": {
            service_id: adapter.get_service_info(service_id)
            for service_id in adapter.list_enabled_services()
        }
    }


# MCP Protocol Notification Handlers  
@mcp_router.post("/notifications/initialized")
async def handle_initialized_notification():
    """
    Handle 'initialized' notification from MCP server.
    
    CRITICAL FOR MCP COMPLIANCE:
    According to MCP specification, when a server sends the 'initialized'
    notification after the handshake, the client MUST respond with 
    202 Accepted to indicate it's ready to receive requests.
    
    This is a one-way notification that confirms the initialization
    process is complete and normal MCP operations can begin.
    
    Returns:
        202 Accepted status as required by MCP protocol
    """
    logger.info("Received 'initialized' notification from MCP server")
    
    # Return 202 Accepted as required by MCP specification
    return JSONResponse(
        content={
            "status": "acknowledged",
            "message": "Client ready for MCP operations"
        },
        status_code=202
    )


@mcp_router.post("/notifications/roots/list_changed")  
async def handle_roots_list_changed():
    """
    Handle 'roots/list_changed' notification from MCP server.
    
    This notification indicates that the server's root list has changed
    and clients should refresh their understanding of available roots.
    """
    logger.info("Received 'roots/list_changed' notification from MCP server")
    
    # Notification acknowledgment - no specific response required
    return JSONResponse(
        content={"status": "acknowledged"},
        status_code=202
    )


@mcp_router.post("/notifications/progress")
async def handle_progress_notification():
    """
    Handle progress notifications from MCP server.
    
    These notifications provide updates on long-running operations.
    """
    logger.info("Received progress notification from MCP server")
    
    return JSONResponse(
        content={"status": "acknowledged"},
        status_code=202
    )


# Configuration endpoints
@mcp_router.get("/config")
async def get_config(
    adapter: ServiceRegistryMCPAdapter = Depends(get_mcp_adapter)
):
    """Get current MCP configuration from ServiceRegistry."""
    return {
        "global": adapter.get_global_config(),
        "services": {
            service_id: adapter.get_service_info(service_id)
            for service_id in adapter.list_enabled_services()
        }
    }


@mcp_router.get("/config/servers")
async def list_configured_servers(
    adapter: ServiceRegistryMCPAdapter = Depends(get_mcp_adapter)
):
    """List configured MCP servers from ServiceRegistry."""
    servers = {}
    for service_id in adapter.list_enabled_services():
        try:
            info = adapter.get_service_info(service_id)
            servers[service_id] = {
                "name": info["name"],
                "description": info["description"],
                "transport_type": info["transport"],
                "enabled": info["enabled"],
                "has_auth": info["has_auth"],
                "auth_strategy": info["auth_strategy"]
            }
        except Exception as e:
            logger.warning(f"Failed to get info for service {service_id}: {e}")
    
    return {"servers": servers}


@mcp_router.post("/config/servers/{server_name}/connect")
async def connect_configured_server(
    server_name: str,
    background_tasks: BackgroundTasks,
    adapter: ServiceRegistryMCPAdapter = Depends(get_mcp_adapter),
    client: MCPClientWrapper = Depends(get_mcp_client)
):
    """Connect to a pre-configured MCP server from ServiceRegistry."""
    
    # Find service by name (server_name could be service_id or service name)
    service_id = None
    for sid in adapter.list_enabled_services():
        try:
            info = adapter.get_service_info(sid)
            if sid == server_name or info["name"] == server_name:
                service_id = sid
                break
        except Exception:
            continue
    
    if not service_id:
        raise HTTPException(
            status_code=404,
            detail=f"Server '{server_name}' not found in configuration"
        )
    
    if not adapter.validate_service_for_mcp(service_id):
        raise HTTPException(
            status_code=400,
            detail=f"Server '{server_name}' is not properly configured for MCP"
        )
    
    try:
        session_config = adapter.get_session_config(service_id, f"config_{service_id}")
        
        session_id = await client.connect_server(
            server_name=session_config.server_name,
            transport_config=session_config.transport_config,
            session_id=session_config.session_id
        )
        
        return ConnectServerResponse(
            session_id=session_id,
            server_name=session_config.server_name,
            status="connected"
        )
        
    except Exception as e:
        logger.error(f"Failed to connect to configured server {server_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Connection failed: {str(e)}"
        )


# Initialization functions
async def initialize_mcp_client(service_registry_adapter: ServiceRegistryMCPAdapter) -> MCPClientWrapper:
    """Initialize the global MCP client with ServiceRegistry."""
    global _mcp_client, _mcp_adapter
    
    # Get global config from ServiceRegistry
    global_config = service_registry_adapter.get_global_config()
    
    session_manager = MCPSessionManager(max_sessions=100)  # Could be made configurable
    
    _mcp_client = MCPClientWrapper(
        session_manager=session_manager,
        default_timeout=global_config["default_timeout"],
        max_retries=3,  # Could be made configurable
        retry_delay=1.0
    )
    
    _mcp_adapter = service_registry_adapter
    
    # Start the client
    await _mcp_client.__aenter__()
    
    logger.info("MCP Client initialized successfully with ServiceRegistry")
    return _mcp_client


async def shutdown_mcp_client():
    """Shutdown the global MCP client."""
    global _mcp_client, _mcp_adapter
    
    if _mcp_client:
        await _mcp_client.__aexit__(None, None, None)
        _mcp_client = None
        _mcp_adapter = None
        logger.info("MCP Client shutdown complete")


# Context manager for application lifecycle
@asynccontextmanager
async def mcp_lifespan(service_registry_adapter: ServiceRegistryMCPAdapter):
    """Manage MCP client lifecycle with ServiceRegistry."""
    client = await initialize_mcp_client(service_registry_adapter)
    try:
        yield client
    finally:
        await shutdown_mcp_client()
