"""
Dashboard Router

FastAPI router for dashboard management operations.
Provides endpoints for configuring and managing MCP services through the web UI.
"""

import asyncio
import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from ..core.service_registry import ServiceRegistry
from ..core.config import settings
from ..auth.authentication_middleware import get_current_user
from ..auth.models import UserContext

# Import API models
from .models.dashboard import (
    ServiceCreateRequest,
    ServiceCreateResponse,
    ServiceDeleteResponse,
    ServiceListResponse,
    ServiceInfo,
    ServiceTestRequest,
    ServiceTestResponse,
)
from .models.common import ErrorResponse, SuccessResponse, HealthResponse

logger = logging.getLogger(__name__)

# Create dashboard router
dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


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
        print("DEBUG: service_registry is None in app.state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service registry not initialized"
        )
    return registry


@dashboard_router.get("/services", response_model=ServiceListResponse)
async def list_services(
    registry: ServiceRegistry = Depends(get_service_registry),
    user: Optional[UserContext] = Depends(get_current_user)
):
    """List all registered MCP services."""
    try:
        # Validate authentication if required
        if settings.ENABLE_AUTH and user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # Get all services from registry
        services = []
        for service_id, service_config in registry.services.items():
            service_info = ServiceInfo(
                service_id=service_id,
                name=service_config.name,
                description=service_config.description,
                connection_type=service_config.transport,  # Use 'transport' not 'connection_type'
                status="active"  # TODO: Add real status checking
            )
            services.append(service_info)
        
        return ServiceListResponse(services=services)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list services: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list services"
        )


@dashboard_router.post("/services", response_model=ServiceCreateResponse)
async def create_service(
    request: ServiceCreateRequest,
    registry: ServiceRegistry = Depends(get_service_registry),
    user: Optional[UserContext] = Depends(get_current_user)
):
    """Create a new MCP service configuration."""
    try:
        # Validate authentication if required
        if settings.ENABLE_AUTH and user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # Create service configuration
        service_id = await registry.register_service(
            name=request.name,
            description=request.description,
            transport=request.transport,
            enabled=request.enabled,
            endpoint=request.endpoint,
            timeout=request.timeout,
            health_check_path=request.health_check_path,
            command=request.command,
            working_directory=request.working_directory,
            auth=request.auth,
            tags=request.tags
        )
        
        return ServiceCreateResponse(
            id=service_id,
            status="created",
            message=f"Service '{request.name}' created successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create service '{request.name}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create service: {str(e)}"
        )


@dashboard_router.delete("/services/{service_id}", response_model=ServiceDeleteResponse)
async def delete_service(
    service_id: str,
    registry: ServiceRegistry = Depends(get_service_registry),
    user: Optional[UserContext] = Depends(get_current_user)
):
    """Delete an MCP service configuration."""
    try:
        # Validate authentication if required
        if settings.ENABLE_AUTH and user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # Check if service exists
        service = await registry.get_service(service_id)
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_id}' not found"
            )
        
        # Delete service
        await registry.unregister_service(service_id)
        
        return ServiceDeleteResponse(
            id=service_id,
            status="deleted",
            message=f"Service '{service_id}' deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete service '{service_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete service: {str(e)}"
        )


@dashboard_router.post("/services/test", response_model=ServiceTestResponse)
async def test_service(
    request: ServiceTestRequest,
    user: Optional[UserContext] = Depends(get_current_user)
):
    """Test connectivity to an MCP service."""
    try:
        # Validate authentication if required
        if settings.ENABLE_AUTH and user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # Basic validation
        if request.transport == "http" and not request.endpoint:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="HTTP transport requires an endpoint"
            )
        
        if request.transport == "stdio" and not request.command:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="STDIO transport requires a command"
            )
        
        # Perform test based on transport type
        if request.transport == "http":
            # Test HTTP endpoint connectivity
            import aiohttp
            import time
            
            start_time = time.time()
            timeout = aiohttp.ClientTimeout(total=request.timeout)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(request.endpoint) as response:
                    response_time = time.time() - start_time
                    
                    return ServiceTestResponse(
                        success=response.status < 400,
                        message=f"HTTP {response.status}: {response.reason}",
                        response_time=response_time,
                        details={
                            "status_code": response.status,
                            "headers": dict(response.headers),
                            "endpoint": request.endpoint
                        }
                    )
        
        elif request.transport == "stdio":
            # Test STDIO command execution
            import subprocess
            import time
            
            start_time = time.time()
            
            try:
                result = subprocess.run(
                    request.command,
                    capture_output=True,
                    text=True,
                    timeout=request.timeout
                )
                response_time = time.time() - start_time
                
                return ServiceTestResponse(
                    success=result.returncode == 0,
                    message=f"Command exited with code {result.returncode}",
                    response_time=response_time,
                    details={
                        "return_code": result.returncode,
                        "stdout": result.stdout[:1000],  # Limit output
                        "stderr": result.stderr[:1000],
                        "command": request.command
                    }
                )
                
            except subprocess.TimeoutExpired:
                response_time = time.time() - start_time
                return ServiceTestResponse(
                    success=False,
                    message=f"Command timed out after {request.timeout} seconds",
                    response_time=response_time,
                    details={"timeout": request.timeout, "command": request.command}
                )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Service test failed: {e}")
        return ServiceTestResponse(
            success=False,
            message=f"Test failed: {str(e)}",
            response_time=None,
            details={"error": str(e)}
        )
