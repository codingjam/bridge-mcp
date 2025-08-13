"""
MCP Gateway API Routes
Defines HTTP endpoints for the gateway with comprehensive error handling and validation
"""
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from mcp_gateway.core.config import get_settings
from mcp_gateway.core.proxy import MCPProxyService
from mcp_gateway.core.authenticated_proxy import AuthenticatedMCPProxyService
from mcp_gateway.core.service_registry import ServiceRegistry
from mcp_gateway.auth.middleware import get_current_user, get_access_token
from mcp_gateway.auth.models import UserContext, MCPServiceAuth, AuthStrategy
from mcp_gateway.auth.obo_service import OBOTokenService

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter()

# Global registry and OBO service instances (will be properly injected in production)
_registry: Optional[ServiceRegistry] = None
_obo_service: Optional[OBOTokenService] = None


async def get_service_registry() -> ServiceRegistry:
    """
    Dependency injection for service registry
    This ensures a singleton pattern and proper lifecycle management
    """
    global _registry
    if _registry is None:
        settings = get_settings()
        _registry = ServiceRegistry(Path(settings.SERVICE_REGISTRY_FILE))
        await _registry.load_services()
    return _registry


async def get_obo_service() -> Optional[OBOTokenService]:
    """
    Dependency injection for OBO service
    Returns OBO service if authentication is enabled
    """
    global _obo_service
    if _obo_service is None:
        settings = get_settings()
        auth_config = settings.get_auth_config()
        if auth_config and auth_config.enable_obo:
            _obo_service = OBOTokenService(auth_config)
    return _obo_service


async def get_proxy_service(
    obo_service: Optional[OBOTokenService] = Depends(get_obo_service)
) -> AuthenticatedMCPProxyService:
    """
    Dependency injection for authenticated proxy service
    Returns a new proxy service instance for each request
    """
    return AuthenticatedMCPProxyService(obo_service=obo_service)


@router.get("/health", 
           summary="Health Check",
           description="Check if the gateway is running and healthy")
async def health_check():
    """Health check endpoint with basic system information"""
    settings = get_settings()
    return {
        "status": "healthy",
        "service": "mcp-gateway",
        "version": "0.1.0",
        "environment": "development" if settings.DEBUG else "production"
    }


@router.get("/services",
           summary="List Services",
           description="Get all available MCP services with their status",
           response_model=Dict[str, Any])
async def list_services(registry: ServiceRegistry = Depends(get_service_registry)):
    """List all available MCP services with health status"""
    try:
        services = await registry.get_all_services()
        health_status = await registry.get_all_health_status()
        
        result = {
            "count": len(services),
            "services": {}
        }
        
        for service_id, service in services.items():
            result["services"][service_id] = {
                "id": service_id,
                "name": service.name,
                "description": service.description,
                "transport": service.transport,
                "enabled": service.enabled,
                "healthy": health_status.get(service_id, False),
                "endpoint": str(service.endpoint) if service.transport == "http" else None,
                "tags": service.tags,
                "version": service.version
            }
        
        logger.info(f"Listed {len(services)} services")
        return result
        
    except Exception as e:
        logger.error(f"Failed to list services: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve services"
        )


@router.get("/services/{service_id}",
           summary="Get Service Info",
           description="Get detailed information about a specific service",
           response_model=Dict[str, Any])
async def get_service_info(
    service_id: str,
    registry: ServiceRegistry = Depends(get_service_registry)
):
    """Get information about a specific service"""
    if not service_id or not service_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service ID cannot be empty"
        )
    
    service = await registry.get_service(service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' not found"
        )
    
    health_status = await registry.get_health_status(service_id)
    
    return {
        "id": service_id,
        "name": service.name,
        "description": service.description,
        "transport": service.transport,
        "enabled": service.enabled,
        "healthy": health_status,
        "endpoint": str(service.endpoint) if service.transport == "http" else None,
        "health_check_path": service.health_check_path,
        "timeout": service.timeout,
        "tags": service.tags,
        "version": service.version,
        "base_path": service.base_path
    }


@router.get("/services/{service_id}/health",
           summary="Check Service Health",
           description="Perform a health check on a specific service",
           response_model=Dict[str, Any])
async def check_service_health(
    service_id: str,
    registry: ServiceRegistry = Depends(get_service_registry)
):
    """Check health of a specific service"""
    service = await registry.get_service(service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' not found"
        )
    
    if not service.enabled:
        return {
            "service_id": service_id,
            "healthy": False,
            "status": "disabled",
            "message": "Service is disabled"
        }
    
    if service.transport != "http":
        return {
            "service_id": service_id,
            "healthy": None,
            "status": "unsupported",
            "message": f"Health checks not supported for {service.transport} transport"
        }
    
    try:
        async with MCPProxyService() as proxy:
            is_healthy = await proxy.health_check(
                str(service.endpoint),
                service.health_check_path
            )
            
            # Update health status in registry
            await registry.update_health_status(service_id, is_healthy)
            
            return {
                "service_id": service_id,
                "healthy": is_healthy,
                "status": "healthy" if is_healthy else "unhealthy",
                "endpoint": str(service.endpoint),
                "health_check_path": service.health_check_path
            }
            
    except Exception as e:
        logger.error(f"Health check failed for {service_id}: {e}")
        await registry.update_health_status(service_id, False)
        
        return {
            "service_id": service_id,
            "healthy": False,
            "status": "error",
            "message": f"Health check failed: {str(e)}"
        }


@router.api_route(
    "/proxy/{service_id}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    summary="Proxy Request",
    description="Proxy any HTTP request to the specified MCP service"
)
async def proxy_request(
    service_id: str,
    path: str,
    request: Request,
    registry: ServiceRegistry = Depends(get_service_registry),
    proxy: AuthenticatedMCPProxyService = Depends(get_proxy_service),
    user: Optional[UserContext] = Depends(get_current_user)
):
    """
    Proxy requests to MCP servers with comprehensive error handling and authentication
    
    This endpoint forwards any HTTP request to the specified MCP service,
    handling headers, body, and query parameters transparently. If authentication
    is enabled, it will use OBO tokens for secure service-to-service communication.
    """
    # Validate service ID
    if not service_id or not service_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service ID cannot be empty"
        )
    
    # Get service configuration
    service = await registry.get_service(service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' not found"
        )
    
    if not service.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service '{service_id}' is disabled"
        )
    
    if service.transport != "http":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Service '{service_id}' does not support HTTP transport (uses {service.transport})"
        )
    
    # Prepare request data
    method = request.method
    headers = dict(request.headers)
    query_params = dict(request.query_params) if request.query_params else None
    
    # Handle request body for methods that support it
    body = None
    if method in ["POST", "PUT", "PATCH"]:
        try:
            body = await request.body()
        except Exception as e:
            logger.error(f"Failed to read request body: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to read request body"
            )
    
    # Build full path with service base path if configured
    full_path = path
    if service.base_path:
        full_path = f"{service.base_path.rstrip('/')}/{path.lstrip('/')}"
    
    # Get authentication data if available
    user_token = get_access_token(request)
    user_claims = getattr(request.state, 'token_claims', None)
    
    # Create service auth configuration (this could be loaded from service registry)
    service_auth = MCPServiceAuth(
        service_id=service_id,
        auth_strategy=AuthStrategy.OBO_REQUIRED if user else AuthStrategy.NO_AUTH,
        required_scopes=[],
        custom_headers={}
    )
    
    # Forward request through authenticated proxy
    try:
        logger.info(
            f"Proxying {method} request",
            extra={
                "service_id": service_id,
                "method": method,
                "path": full_path,
                "authenticated": user is not None,
                "user_id": user.user_id if user else None,
                "query_params": bool(query_params),
                "body_size": len(body) if body else 0
            }
        )
        
        response_data = await proxy.forward_authenticated_request(
            target_url=str(service.endpoint),
            method=method,
            path=full_path,
            headers=headers,
            body=body,
            query_params=query_params,
            timeout=service.timeout,
            user_token=user_token,
            user_claims=user_claims,
            service_auth=service_auth
        )
        
        # Prepare response headers (filter out problematic ones)
        response_headers = response_data.get("headers", {})
        filtered_headers = {
            k: v for k, v in response_headers.items()
            if k.lower() not in ['content-length', 'transfer-encoding', 'connection', 'server']
        }
        
        # Return appropriate response type
        if "json" in response_data:
            return JSONResponse(
                content=response_data["json"],
                status_code=response_data["status_code"],
                headers=filtered_headers
            )
        else:
            return Response(
                content=response_data["content"],
                status_code=response_data["status_code"],
                headers=filtered_headers
            )
            
    except HTTPException:
        # Re-raise HTTP exceptions from proxy service
        raise
    except Exception as e:
        logger.error(
            f"Proxy request failed for {service_id}",
            extra={
                "service_id": service_id,
                "method": method,
                "path": full_path,
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Proxy error: {str(e)}"
        )


@router.post("/mcp/{service_id}/call",
            summary="MCP Protocol Call",
            description="Make a Model Context Protocol call to a specific service")
async def mcp_call(
    service_id: str,
    request: Request,
    registry: ServiceRegistry = Depends(get_service_registry),
    proxy: AuthenticatedMCPProxyService = Depends(get_proxy_service),
    user: Optional[UserContext] = Depends(get_current_user)
):
    """
    MCP protocol call endpoint
    
    This is a specialized endpoint for MCP protocol calls with
    proper header handling, protocol compliance, and authentication.
    """
    service = await registry.get_service(service_id)
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Service '{service_id}' not found"
        )
    
    if not service.enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service '{service_id}' is disabled"
        )
    
    if service.transport != "http":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"MCP calls only supported for HTTP transport, service uses {service.transport}"
        )
    
    # Prepare MCP-specific headers
    headers = dict(request.headers)
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "application/json"
    headers["X-MCP-Gateway"] = "mcp-gateway/0.1.0"
    
    # Get authentication data if available
    user_token = get_access_token(request)
    user_claims = getattr(request.state, 'token_claims', None)
    
    # Create service auth configuration for MCP calls
    service_auth = MCPServiceAuth(
        service_id=service_id,
        auth_strategy=AuthStrategy.OBO_REQUIRED if user else AuthStrategy.NO_AUTH,
        required_scopes=["mcp:call"],  # MCP-specific scope
        custom_headers={}
    )
    
    try:
        body = await request.body()
        
        logger.info(
            f"Making MCP call to {service_id}",
            extra={
                "service_id": service_id,
                "endpoint": str(service.endpoint),
                "authenticated": user is not None,
                "user_id": user.user_id if user else None
            }
        )
        
        response_data = await proxy.forward_authenticated_request(
            target_url=str(service.endpoint),
            method="POST",
            path="/call",  # Standard MCP call endpoint
            headers=headers,
            body=body,
            timeout=service.timeout,
            user_token=user_token,
            user_claims=user_claims,
            service_auth=service_auth
        )
        
        # MCP calls should always return JSON
        if "json" in response_data:
            return JSONResponse(
                content=response_data["json"],
                status_code=response_data["status_code"]
            )
        else:
            # If not JSON, try to parse the content as JSON
            try:
                import json
                content = json.loads(response_data["content"].decode())
                return JSONResponse(content=content, status_code=response_data["status_code"])
            except:
                # Fall back to raw content
                return Response(
                    content=response_data["content"],
                    status_code=response_data["status_code"],
                    media_type="application/json"
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MCP call failed for {service_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"MCP call failed: {str(e)}"
        )
