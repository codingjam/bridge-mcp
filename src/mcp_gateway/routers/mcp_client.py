"""
MCP Client Router

FastAPI router for native MCP client operations.
Provides endpoints for connecting to MCP servers and executing operations
using the native MCP protocol with authentication integration.
"""

import asyncio
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Request, status
from fastapi.responses import JSONResponse

from ..mcp.client_wrapper import MCPClientWrapper
from ..mcp.session_manager import MCPSessionManager
from ..mcp.service_adapter import ServiceRegistryMCPAdapter
from ..mcp.exceptions import MCPClientError, MCPConnectionError, MCPSessionError

# Import existing auth dependencies - REUSE EXISTING PATTERNS
from ..core.service_registry import ServiceRegistry
from ..core.authenticated_proxy import AuthenticatedMCPProxyService
from ..core.logging import get_logger
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

logger = get_logger(__name__)


# Dependency injection functions - REUSE PATTERNS FROM routes.py
async def get_service_registry(request: Request) -> ServiceRegistry:
    """
    Dependency injection for service registry from app state
    """
    if not hasattr(request.app.state, 'service_registry'):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service registry not initialized"
        )
    registry = request.app.state.service_registry
    if registry is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service registry not initialized"
        )
    return registry


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
        obo_service=obo_service
    )


# Global MCP client instance - Remove global variables
# _mcp_client: Optional[MCPClientWrapper] = None
# _mcp_adapter: Optional[ServiceRegistryMCPAdapter] = None


# Create MCP router
mcp_router = APIRouter(prefix="/mcp", tags=["MCP Client"])


async def get_mcp_client(request: Request) -> MCPClientWrapper:
    """Get or create MCP client instance from app state."""
    if not hasattr(request.app.state, 'mcp_client'):
        # Get service registry for circuit breaker manager
        service_registry = request.app.state.service_registry
        if not service_registry:
            raise HTTPException(
                status_code=503,
                detail="Service registry not initialized"
            )
        
        # Create MCP client with just the circuit breaker manager
        # Let it create its own session manager
        mcp_client = MCPClientWrapper(
            circuit_breaker_manager=service_registry.circuit_breaker_manager
        )
        
        # Store service registry reference for adapter access
        mcp_client._service_registry = service_registry
        
        await mcp_client.__aenter__()
        request.app.state.mcp_client = mcp_client
    return request.app.state.mcp_client


async def get_mcp_adapter(request: Request) -> ServiceRegistryMCPAdapter:
    """Get or create MCP adapter instance from app state."""
    if not hasattr(request.app.state, 'mcp_adapter'):
        service_registry = request.app.state.service_registry
        if not service_registry:
            raise HTTPException(
                status_code=503,
                detail="Service registry not initialized"
            )
        request.app.state.mcp_adapter = ServiceRegistryMCPAdapter(service_registry)
    return request.app.state.mcp_adapter


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
        
        # Get the proper MCPServiceAuth object from registry
        service_auth = await registry.get_service_auth(server_name)
        
        if service_auth and service_auth.auth_strategy.value in ["obo_required", "passthrough"]:
            if not user_token:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required for this service"
                )
            
            if service_auth.auth_strategy.value == "obo_required":
                # Use OBO token exchange (same pattern as routes.py)
                if not proxy.obo_service:
                    raise HTTPException(
                        status_code=500,
                        detail="OBO service not configured"
                    )
                
                # Get token claims from request state (already validated by auth middleware)
                user_claims = getattr(http_request.state, 'token_claims', None)
                if not user_claims:
                    raise HTTPException(
                        status_code=401,
                        detail="No token claims available"
                    )
                
                # Get OBO token for the target service
                obo_token = await proxy.obo_service.get_service_token(
                    user_token=user_token,
                    user_claims=user_claims,
                    service_config=service_auth
                )
                headers["Authorization"] = f"Bearer {obo_token}"
                
            elif service_auth.auth_strategy.value == "passthrough":
                # Pass through the original token
                headers["Authorization"] = f"Bearer {user_token}"
        
        # Route request based on method
        if method == "tools/list":
            # Handle tool listing using direct method
            client = await get_mcp_client(http_request)
            tools = await client.list_tools_direct(server_name, headers)
            return {
                "jsonrpc": "2.0",
                "id": request_data.get("id"),
                "result": {"tools": tools}
            }
            
        elif method == "tools/call":
            # Handle tool execution with optional SSE streaming
            client = await get_mcp_client(http_request)
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if not tool_name:
                raise HTTPException(status_code=400, detail="Tool name required")

            # Check for streaming intent through multiple channels
            # 1. Query parameter: ?stream=true
            qp_stream = http_request.query_params.get("stream", "").lower() in ("1", "true", "yes")
            
            # 2. JSON-RPC params: "stream": true
            param_stream = params.get("stream") is True
            
            # 3. Accept header: Accept: text/event-stream
            accept_stream = "text/event-stream" in http_request.headers.get("accept", "")
            
            # Enable streaming if any trigger is active
            want_stream = qp_stream or param_stream or accept_stream

            if not want_stream:
                # Standard non-streaming path (existing behavior)
                result = await client.call_tool_direct(
                    server_name, tool_name, arguments, headers
                )
                return {
                    "jsonrpc": "2.0",
                    "id": request_data.get("id"),
                    "result": result
                }

            # SSE Streaming path - return incremental results as Server-Sent Events
            from fastapi.responses import StreamingResponse
            import json
            import time
            import asyncio

            correlation_id = request_data.get("id")
            start_time = time.perf_counter()

            async def event_stream():
                """
                Generate SSE frames for streaming tool call results.
                Each chunk is wrapped in a JSON-RPC style envelope.
                """
                first_chunk = True
                try:
                    logger.info(f"Starting SSE stream for tool '{tool_name}' on server '{server_name}'")
                    
                    # Stream chunks from the MCP server
                    async for item in client.stream_tool_call_direct(
                        server_name, tool_name, arguments, headers
                    ):
                        # Normalized frame from wrapper: {final, payload, elapsed_ms, session_id}
                        frame = {
                            "jsonrpc": "2.0",
                            "id": correlation_id,
                            "stream": item.get("payload"),
                            "final": bool(item.get("final")),
                            "first": first_chunk,
                            "elapsed_ms": item.get("elapsed_ms", int((time.perf_counter() - start_time) * 1000)),
                        }
                        first_chunk = False
                        yield f"data: {json.dumps(frame, ensure_ascii=False)}\n\n"
                    
                    # Emit completion event
                    yield f"event: end\ndata: {{\"id\":\"{correlation_id}\"}}\n\n"
                    logger.info(f"SSE stream completed for tool '{tool_name}' on server '{server_name}'")
                    
                except asyncio.CancelledError:
                    # Client disconnected - log and cleanup
                    logger.debug(
                        f"SSE client disconnected during tool call", 
                        extra={
                            "tool": tool_name, 
                            "server": server_name,
                            "correlation_id": correlation_id,
                            "elapsed_ms": int((time.perf_counter() - start_time) * 1000)
                        }
                    )
                    # Note: Session cleanup will be handled by the client wrapper's session manager
                    raise
                except Exception as e:
                    # Error during streaming - emit error event then stop
                    logger.error(
                        f"SSE stream error for tool '{tool_name}' on server '{server_name}': {e}",
                        extra={
                            "tool": tool_name,
                            "server": server_name, 
                            "correlation_id": correlation_id,
                            "elapsed_ms": int((time.perf_counter() - start_time) * 1000)
                        }
                    )
                    error_frame = {
                        "jsonrpc": "2.0",
                        "id": correlation_id,
                        "error": {
                            "code": -32603,
                            "message": "Stream error",
                            "data": str(e)
                        }
                    }
                    yield f"event: error\ndata: {json.dumps(error_frame, ensure_ascii=False)}\n\n"

            # Return streaming response with appropriate headers
            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",           # Prevent caching
                    "Connection": "keep-alive",            # Keep connection open
                    "X-Accel-Buffering": "no",           # Disable nginx buffering
                }
            )
            
        else:
            # Generic JSON-RPC forwarding
            adapter = await get_mcp_adapter(http_request)
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
        
        # Always build transport config from service configuration
        transport_config = {
            "type": service.transport,
            "url": str(service.endpoint)
        }
        
        # Add service-specific config based on transport type
        if service.transport == "stdio" and service.command:
            transport_config["command"] = service.command
            if service.working_directory:
                transport_config["working_directory"] = service.working_directory
            if service.environment:
                transport_config["environment"] = service.environment
        
        # Get the proper MCPServiceAuth object from registry
        service_auth = await registry.get_service_auth(request.server_name)
        
        logger.info(f"Attempting to connect to MCP server '{request.server_name}' with transport: {service.transport}")
        logger.debug(f"Service endpoint: {service.endpoint}")
        logger.debug(f"Auth strategy: {service_auth.auth_strategy.value if service_auth else 'none'}")
        
        if service_auth and service_auth.auth_strategy.value in ["obo_required", "passthrough"]:
            if not user_token:
                logger.error(f"No user token provided for authenticated service '{request.server_name}'")
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required for this service"
                )
            
            logger.debug(f"Using auth strategy: {service_auth.auth_strategy.value}")
            
            if service_auth.auth_strategy.value == "obo_required":
                # Use OBO token exchange (same pattern as routes.py)
                if not proxy.obo_service:
                    logger.error("OBO service not configured")
                    raise HTTPException(
                        status_code=500,
                        detail="OBO service not configured"
                    )
                
                # Get token claims from request state (already validated by auth middleware)
                user_claims = getattr(http_request.state, 'token_claims', None)
                if not user_claims:
                    logger.error("No token claims available for OBO exchange")
                    raise HTTPException(
                        status_code=401,
                        detail="No token claims available"
                    )
                
                logger.debug("Performing OBO token exchange")
                # Get OBO token for the target service
                obo_token = await proxy.obo_service.get_service_token(
                    user_token=user_token,
                    user_claims=user_claims,
                    service_config=service_auth
                )
                
                logger.debug("OBO token exchange successful")
                # Add OBO token to transport config - only add Authorization, let SDK handle other headers
                if "headers" not in transport_config:
                    transport_config["headers"] = {}
                transport_config["headers"]["Authorization"] = f"Bearer {obo_token}"
                
            elif service_auth.auth_strategy.value == "passthrough":
                logger.debug("Using passthrough authentication")
                # Pass through the original token - only add Authorization, let SDK handle other headers
                if "headers" not in transport_config:
                    transport_config["headers"] = {}
                transport_config["headers"]["Authorization"] = f"Bearer {user_token}"
        else:
            logger.debug("No authentication required for this service")
        
        logger.info(f"Initiating MCP connection to '{request.server_name}' with session ID: {request.session_id or 'auto-generated'}")
        
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
    http_request: Request,
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
    http_request: Request,
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
        
        # Convert CallToolResult to dictionary for the response
        result_dict = {
            "meta": result.meta.model_dump() if result.meta else None,
            "content": [content.model_dump() for content in result.content] if result.content else [],
            "isError": result.isError
        }
        
        return CallToolResponse(
            session_id=session_id,
            tool_name=request.tool_name,
            result=result_dict,
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
