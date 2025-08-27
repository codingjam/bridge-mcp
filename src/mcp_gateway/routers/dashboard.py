"""
Dashboard Router

FastAPI router for dashboard management operations.
Provides endpoints for configuring and managing MCP services through the web UI.
"""

import asyncio
import logging
import subprocess
import time
from typing import Dict, List, Optional

import aiohttp
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


@dashboard_router.get("/overview", response_model=Dict)
async def get_dashboard_overview(
    registry: ServiceRegistry = Depends(get_service_registry),
    user: Optional[UserContext] = Depends(get_current_user)
):
    """Get dashboard overview metrics."""
    try:
        # Validate authentication if required
        if settings.ENABLE_AUTH and user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # Get basic metrics
        total_services = len(registry.services)
        active_services = sum(1 for service in registry.services.values() if service.enabled)
        healthy_services = active_services  # TODO: Add real health checking
        unhealthy_services = total_services - healthy_services
        
        return {
            "services": {
                "total": total_services,
                "healthy": healthy_services,
                "unhealthy": unhealthy_services,
                "disabled": total_services - active_services
            },
            "performance": {
                "averageResponseTime": 0,  # TODO: Add real response time tracking
                "successRate": 100 if total_services == 0 else (healthy_services / total_services) * 100,
                "cpuUsage": 0,  # TODO: Add real CPU monitoring
                "memoryUsage": 0  # TODO: Add real memory monitoring
            },
            "rateLimiting": {
                "totalRequests": 0,  # TODO: Add real request counting
                "currentRps": 0,  # TODO: Add real RPS calculation
                "blockedRequests": 0,  # TODO: Add real blocking metrics
                "throttledRequests": 0  # TODO: Add real throttling metrics
            },
            "systemStatus": {
                "status": "operational" if healthy_services == total_services else "degraded",
                "message": "All systems operational" if healthy_services == total_services else f"{unhealthy_services} service(s) unhealthy",
                "severity": "info" if healthy_services == total_services else "warning",
                "lastChecked": "2024-01-01T00:00:00Z",  # TODO: Add real timestamps
                "uptime": "00:00:00"  # TODO: Add real uptime tracking
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get dashboard overview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get dashboard overview"
        )


@dashboard_router.get("/services/health", response_model=Dict)
async def get_services_health(
    registry: ServiceRegistry = Depends(get_service_registry),
    user: Optional[UserContext] = Depends(get_current_user)
):
    """Get health status for all services."""
    try:
        # Validate authentication if required
        if settings.ENABLE_AUTH and user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # Get health status for all services
        services = []
        healthy_count = 0
        unhealthy_count = 0
        disabled_count = 0
        
        for service_id, service_config in registry.services.items():
            is_healthy = service_config.enabled  # TODO: Add real health checking
            status = "healthy" if is_healthy else "unhealthy" if service_config.enabled else "disabled"
            
            if status == "healthy":
                healthy_count += 1
            elif status == "unhealthy":
                unhealthy_count += 1
            else:
                disabled_count += 1
            
            services.append({
                "id": service_id,
                "name": service_config.name,
                "endpoint": service_config.endpoint or "N/A",
                "transport": service_config.transport,
                "enabled": service_config.enabled,
                "healthy": is_healthy,
                "lastChecked": "2024-01-01T00:00:00Z",  # TODO: Add real timestamps
                "tags": service_config.tags or []
            })
        
        return {
            "services": services,
            "summary": {
                "total": len(services),
                "healthy": healthy_count,
                "unhealthy": unhealthy_count,
                "disabled": disabled_count
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get services health: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get services health"
        )


@dashboard_router.get("/services", response_model=ServiceListResponse)
async def list_services(request: Request):
    """List all registered MCP services."""
    try:
        # Get registry directly from app state
        registry = request.app.state.service_registry

        # Get all services from registry
        services = []
        for service_id, service_config in registry.services.items():
            service_info = ServiceInfo(
                service_id=service_id,
                name=service_config.name,
                description=service_config.description,
                connection_type=service_config.transport,
                status="active"
            )
            services.append(service_info)

        return ServiceListResponse(services=services)

    except Exception as e:
        logger.error(f"Failed to list services: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list services"
        )


@dashboard_router.post("/services", response_model=ServiceCreateResponse)
async def create_service(request: ServiceCreateRequest, request_obj: Request):
    """Create a new MCP service configuration."""
    try:
        registry = request_obj.app.state.service_registry

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
