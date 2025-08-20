"""
Dashboard API Routes
Provides endpoints specifically for the dashboard frontend with clear separation from core MCP functionality.

This module is intentionally decoupled from core MCP gateway logic to:
1. Maintain separation of concerns
2. Allow independent dashboard development
3. Provide aggregated data views for UI consumption
4. Enable easier testing and maintenance

Note: These endpoints are for dashboard consumption only and should not be used for core MCP operations.
"""

import asyncio
import logging
import shutil
import httpx
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, status

from mcp_gateway.core.config import get_settings
from mcp_gateway.core.service_registry import ServiceRegistry
from mcp_gateway.rl import get_rate_limiter
from mcp_gateway.api.models import (
    ServiceCreateRequest, 
    ServiceCreateResponse, 
    ServiceDeleteResponse,
    ServiceTestRequest,
    ServiceTestResponse
)

logger = logging.getLogger(__name__)

# Create dashboard-specific router with clear prefix
dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])


async def get_service_registry() -> ServiceRegistry:
    """
    Dependency injection for service registry with proper error handling
    """
    try:
        from mcp_gateway.main import get_service_registry as get_registry
        registry = await get_registry()
        return registry
    except RuntimeError as e:
        logger.error(f"Service registry not initialized: {e}")
        # Service registry not initialized - return a mock registry for testing
        # In production, this would be handled by proper initialization order
        from mcp_gateway.core.service_registry import ServiceRegistry
        from pathlib import Path
        
        # Create a temporary registry and load services
        mock_registry = ServiceRegistry(config_path=Path("config/services.yaml"))
        try:
            await mock_registry.load_services()
            logger.info(f"Loaded {len(await mock_registry.get_all_services())} services from config")
        except Exception as load_error:
            logger.error(f"Failed to load services in mock registry: {load_error}")
        
        return mock_registry


@dashboard_router.get("/overview",
                     tags=["dashboard"],
                     summary="Dashboard Overview Data",
                     description="Aggregated data for the main dashboard overview page",
                     response_model=Dict[str, Any])
async def get_dashboard_overview(
    registry: ServiceRegistry = Depends(get_service_registry)
):
    """
    Get aggregated overview data for the dashboard homepage.
    
    This endpoint provides a summary view of system status, service health,
    and key metrics for display in the dashboard overview section.
    
    Returns:
        - Service counts and health status
        - Rate limiting usage statistics  
        - System performance metrics
        - Overall system status
    
    Note: This is a dashboard-specific endpoint and should not be used for core operations.
    """
    try:
        # Get service information from registry
        services = await registry.get_all_services()
        
        # Perform real health checks for overview metrics
        healthy_count = 0
        unhealthy_count = 0
        disabled_count = 0
        
        # Quick health check for overview (with shorter timeout)
        for service_id, service in services.items():
            if not getattr(service, 'enabled', True):
                disabled_count += 1
                continue
                
            # Quick health check with shorter timeout for overview
            try:
                if service.transport == "http":
                    endpoint = str(service.endpoint)
                    health_path = getattr(service, 'health_check_path', '/health')
                    health_url = f"{endpoint.rstrip('/')}{health_path}"
                    
                    async with httpx.AsyncClient(timeout=2.0) as client:  # Shorter timeout for overview
                        response = await client.get(health_url)
                        if response.status_code == 200:
                            healthy_count += 1
                        else:
                            unhealthy_count += 1
                elif service.transport == "stdio":
                    command = getattr(service, 'command', None)
                    if command and isinstance(command, list) and len(command) > 0:
                        if shutil.which(command[0]) is not None:
                            healthy_count += 1
                        else:
                            unhealthy_count += 1
                    else:
                        unhealthy_count += 1
                else:
                    unhealthy_count += 1
            except Exception:
                unhealthy_count += 1
        
        # Calculate service metrics
        total_services = len(services)
        enabled_services = healthy_count + unhealthy_count
        
        # Get rate limiting information
        rate_limiter = get_rate_limiter()
        rate_limit_stats = await _get_rate_limit_overview(rate_limiter)
        
        # Calculate system metrics (placeholder - would be replaced with real metrics)
        system_metrics = await _get_system_metrics()
        
        # Determine overall system status
        system_status = _calculate_system_status(
            total_services, healthy_count, enabled_services, rate_limit_stats
        )
        
        overview_data = {
            # Service Information
            "services": {
                "total": total_services,
                "enabled": enabled_services,
                "healthy": healthy_count,
                "unhealthy": unhealthy_count,
                "disabled": disabled_count
            },
            
            # Rate Limiting Overview
            "rateLimiting": rate_limit_stats,
            
            # System Performance Metrics
            "performance": system_metrics,
            
            # Overall Status
            "systemStatus": system_status,
            
            # Metadata
            "lastUpdated": datetime.utcnow().isoformat(),
            "refreshInterval": 30  # Suggested refresh interval in seconds
        }
        
        logger.info(
            "Dashboard overview data generated",
            extra={
                "total_services": total_services,
                "healthy_services": healthy_count,
                "unhealthy_services": unhealthy_count,
                "disabled_services": disabled_count,
                "system_status": system_status["status"]
            }
        )
        
        return overview_data
        
    except Exception as e:
        logger.error(f"Failed to generate dashboard overview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard overview data"
        )


@dashboard_router.get("/services/health",
                     tags=["dashboard"],
                     summary="Service Health Summary",
                     description="Summary of all service health statuses for dashboard display",
                     response_model=Dict[str, Any])
async def get_services_health_summary(
    registry: ServiceRegistry = Depends(get_service_registry)
):
    """
    Get a summary of service health statuses for dashboard visualization.
    
    This endpoint provides service health information in a format optimized
    for dashboard display, including health trends and status summaries.
    
    Note: For detailed service information, use the core /services endpoints.
    """
    try:
        services = await registry.get_all_services()
        
        service_health_summary = []
        health_counts = {"healthy": 0, "unhealthy": 0, "disabled": 0}
        
        # Perform actual health checks for each service
        health_check_tasks = []
        service_items = list(services.items())
        
        for service_id, service in service_items:
            health_check_tasks.append(_perform_health_check(service))
        
        # Execute all health checks concurrently for better performance
        health_results = await asyncio.gather(*health_check_tasks, return_exceptions=True)
        
        for (service_id, service), health_result in zip(service_items, health_results):
            # Handle any exceptions from health checks
            if isinstance(health_result, Exception):
                status = "unhealthy"
                error_message = f"Health check failed: {str(health_result)}"
                logger.error(f"Health check exception for {service_id}: {health_result}")
            else:
                status, error_message = health_result
            
            health_counts[status] += 1
            
            service_summary = {
                "id": service_id,
                "name": service.name,
                "enabled": service.enabled,
                "healthy": status == "healthy",
                "status": status,
                "transport": service.transport,
                "endpoint": str(service.endpoint) if service.transport == "http" else None,
                "tags": service.tags or [],
                "lastChecked": datetime.utcnow().isoformat(),
                "error": error_message if error_message else None
            }
            
            service_health_summary.append(service_summary)
        
        # Sort by status priority (unhealthy first, then disabled, then healthy)
        service_health_summary.sort(key=lambda s: (
            0 if s["status"] == "unhealthy" else (1 if s["status"] == "disabled" else 2),
            s["name"]
        ))
        
        summary = {
            "services": service_health_summary,
            "summary": {
                "total": len(services),
                "healthy": health_counts["healthy"],
                "unhealthy": health_counts["unhealthy"],
                "disabled": health_counts["disabled"]
            },
            "lastUpdated": datetime.utcnow().isoformat()
        }
        
        logger.info(
            f"Service health check completed",
            extra={
                "total_services": len(services),
                "healthy": health_counts["healthy"],
                "unhealthy": health_counts["unhealthy"],
                "disabled": health_counts["disabled"]
            }
        )
        
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get service health summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve service health summary"
        )


# Helper functions for dashboard data aggregation
async def _perform_health_check(service) -> Tuple[str, Optional[str]]:
    """
    Perform actual health check on a service.
    
    Returns:
        Tuple of (status, error_message)
        status: "healthy", "unhealthy", "disabled"
    """
    try:
        if not getattr(service, 'enabled', True):
            return "disabled", "Service is disabled"
            
        transport = getattr(service, 'transport', None)
        if not transport:
            return "unhealthy", "No transport configuration"
            
        if transport == "http":
            # Test HTTP connectivity
            endpoint = str(getattr(service, 'endpoint', ''))
            if not endpoint:
                return "unhealthy", "No endpoint configured"
                
            health_path = getattr(service, 'health_check_path', '/health')
            health_url = f"{endpoint.rstrip('/')}{health_path}"
            
            try:
                timeout = getattr(service, 'timeout', 5.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(health_url)
                    if response.status_code == 200:
                        return "healthy", None
                    else:
                        return "unhealthy", f"HTTP {response.status_code}"
            except httpx.ConnectError:
                return "unhealthy", "Connection refused"
            except httpx.TimeoutException:
                return "unhealthy", "Connection timeout"
            except Exception as e:
                return "unhealthy", f"Connection failed: {str(e)}"
                    
        elif transport == "stdio":
            # For STDIO, check if command exists and is executable
            command = getattr(service, 'command', None)
            if not command or not isinstance(command, list) or len(command) == 0:
                return "unhealthy", "No command specified"
                
            try:
                # Test if command exists
                if shutil.which(command[0]) is None:
                    return "unhealthy", f"Command not found: {command[0]}"
                return "healthy", None
            except Exception as e:
                return "unhealthy", f"Command check failed: {str(e)}"
                
        else:
            return "unhealthy", f"Unknown transport type: {transport}"
            
    except Exception as e:
        logger.error(f"Health check error for service: {e}", exc_info=True)
        return "unhealthy", f"Health check error: {str(e)}"


async def _get_rate_limit_overview(rate_limiter) -> Dict[str, Any]:
    """
    Get rate limiting overview data for dashboard display.
    
    This function aggregates rate limiting information in a dashboard-friendly format.
    """
    try:
        # Placeholder implementation - would integrate with actual rate limiter
        # In a real implementation, this would query the rate limiter for current usage
        
        return {
            "enabled": rate_limiter is not None,
            "totalRequests": 1250,  # Placeholder - would be real metrics
            "limitedRequests": 23,  # Placeholder - would be real metrics
            "currentRps": 45.2,     # Placeholder - would be real metrics
            "averageRps": 38.7,     # Placeholder - would be real metrics
            "peakRps": 120.5,       # Placeholder - would be real metrics
            "utilizationPercent": 68.5,  # Placeholder - would be calculated from limits
            "activeRules": 5,       # Placeholder - would count active rules
            "status": "operational"
        }
        
    except Exception as e:
        logger.warning(f"Could not retrieve rate limiting overview: {e}")
        return {
            "enabled": False,
            "status": "unavailable",
            "error": "Rate limiting data unavailable"
        }


async def _get_system_metrics() -> Dict[str, Any]:
    """
    Get system performance metrics for dashboard display.
    
    This function would integrate with monitoring systems to provide
    performance data in a dashboard-friendly format.
    """
    # Placeholder implementation - in a real system this would:
    # - Query metrics from monitoring systems
    # - Calculate performance statistics
    # - Provide real-time system health data
    
    return {
        "averageResponseTime": 234.5,  # milliseconds
        "p95ResponseTime": 450.2,      # milliseconds
        "p99ResponseTime": 1250.8,     # milliseconds
        "requestsPerSecond": 45.2,
        "successRate": 99.7,           # percentage
        "errorRate": 0.3,              # percentage
        "uptime": "7d 12h 34m",        # would be calculated from start time
        "memoryUsage": 68.5,           # percentage
        "cpuUsage": 23.8               # percentage
    }


def _calculate_system_status(
    total_services: int,
    healthy_services: int,
    enabled_services: int,
    rate_limit_stats: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate overall system status based on various health indicators.
    
    This function provides a simple health assessment for dashboard display.
    """
    if enabled_services == 0:
        status = "no_services"
        message = "No services are currently enabled"
        severity = "warning"
    elif healthy_services == enabled_services:
        status = "operational"
        message = "All services are healthy"
        severity = "success"
    elif healthy_services == 0:
        status = "critical"
        message = "No services are responding"
        severity = "error"
    elif healthy_services / enabled_services >= 0.8:
        status = "degraded"
        message = f"{enabled_services - healthy_services} services are unhealthy"
        severity = "warning"
    else:
        status = "critical"
        message = f"Multiple services are unhealthy ({healthy_services}/{enabled_services} healthy)"
        severity = "error"
    
    return {
        "status": status,
        "message": message,
        "severity": severity,
        "healthyServices": healthy_services,
        "totalEnabledServices": enabled_services,
        "lastChecked": datetime.utcnow().isoformat()
    }


def _get_service_status_text(enabled: bool, healthy: bool) -> str:
    """Get human-readable status text for a service."""
    if not enabled:
        return "disabled"
    elif healthy:
        return "healthy"
    else:
        return "unhealthy"


@dashboard_router.post("/services",
                      tags=["dashboard"],
                      summary="Create New Service",
                      description="Add a new MCP service to the configuration",
                      response_model=ServiceCreateResponse)
async def create_service(
    service_data: ServiceCreateRequest,
    registry: ServiceRegistry = Depends(get_service_registry)
):
    """
    Create a new MCP service and add it to the configuration.
    
    This endpoint allows the dashboard to dynamically add new services
    to the MCP Gateway configuration. The service will be persisted
    to the services.yaml file and immediately available for use.
    
    Args:
        service_data: Service configuration data
        
    Returns:
        ServiceCreateResponse with the generated service ID and status
        
    Raises:
        HTTPException: If service creation fails
    """
    logger.info(f"Creating new service: name={service_data.name}, transport={service_data.transport}")
    
    try:
        # Generate unique service ID from name
        service_id = registry.generate_service_id(service_data.name)
        
        # Prepare service configuration for YAML
        service_config = {
            "name": service_data.name,
            "description": service_data.description or "",
            "transport": service_data.transport,
            "enabled": service_data.enabled,
            "tags": service_data.tags or []
        }
        
        # Add transport-specific configuration
        if service_data.transport == "http":
            if not service_data.endpoint:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="endpoint is required for HTTP transport"
                )
            service_config.update({
                "endpoint": service_data.endpoint,
                "timeout": service_data.timeout or 30.0,
                "health_check_path": service_data.health_check_path or "/health"
            })
        elif service_data.transport == "stdio":
            if not service_data.command:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="command is required for STDIO transport"
                )
            service_config.update({
                "endpoint": service_id,  # Use service_id as endpoint for stdio
                "command": service_data.command,
            })
            if service_data.working_directory:
                service_config["working_directory"] = service_data.working_directory
        
        # Add authentication configuration
        if service_data.auth:
            service_config["auth"] = service_data.auth
        else:
            # Default to no authentication
            service_config["auth"] = {"strategy": "no_auth"}
        
        # Add service to configuration file
        await registry.add_service_to_config(service_id, service_config)
        
        logger.info(
            f"Created new service via dashboard API",
            extra={
                "service_id": service_id,
                "service_name": service_data.name,
                "transport": service_data.transport,
                "enabled": service_data.enabled
            }
        )
        
        return ServiceCreateResponse(
            id=service_id,
            status="created",
            message=f"Service '{service_data.name}' created successfully with ID '{service_id}'"
        )
        
    except ValueError as e:
        logger.warning(f"Service creation validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create service: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create service: {str(e)}"
        )


@dashboard_router.delete("/services/{service_id}",
                        tags=["dashboard"],
                        summary="Delete Service",
                        description="Remove an MCP service from the configuration",
                        response_model=ServiceDeleteResponse)
async def delete_service(
    service_id: str,
    registry: ServiceRegistry = Depends(get_service_registry)
):
    """
    Delete an MCP service from the configuration.
    
    This endpoint allows the dashboard to remove services from the
    MCP Gateway configuration. The service will be removed from
    the services.yaml file and no longer available for routing.
    
    Args:
        service_id: The ID of the service to delete
        
    Returns:
        ServiceDeleteResponse with the deletion status
        
    Raises:
        HTTPException: If service deletion fails or service not found
    """
    try:
        # Get service info before deletion for logging
        services = await registry.get_all_services()
        if service_id not in services:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Service '{service_id}' not found"
            )
        
        service = services[service_id]
        service_name = service.name
        
        # Remove service from configuration file
        await registry.remove_service_from_config(service_id)
        
        logger.info(
            f"Deleted service via dashboard API",
            extra={
                "service_id": service_id,
                "service_name": service_name
            }
        )
        
        return ServiceDeleteResponse(
            id=service_id,
            status="deleted",
            message=f"Service '{service_name}' (ID: '{service_id}') deleted successfully"
        )
        
    except ValueError as e:
        logger.warning(f"Service deletion validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete service {service_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete service: {str(e)}"
        )


@dashboard_router.post("/services/test",
                      tags=["dashboard"],
                      summary="Test Service Connection",
                      description="Test connectivity to a service without adding it",
                      response_model=ServiceTestResponse)
async def test_service_connection(
    test_data: ServiceTestRequest
):
    """
    Test connectivity to a service without adding it to the configuration.
    
    This endpoint allows the dashboard to validate service connectivity
    before actually creating the service. Useful for form validation
    and troubleshooting.
    
    Args:
        test_data: Service connection test parameters
        
    Returns:
        ServiceTestResponse with test results
    """
    start_time = time.time()
    
    try:
        if test_data.transport == "http":
            if not test_data.endpoint:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="endpoint is required for HTTP transport test"
                )
            
            # Test HTTP connectivity
            try:
                timeout = test_data.timeout or 5.0
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(f"{test_data.endpoint.rstrip('/')}/health")
                    response_time = time.time() - start_time
                    
                    if response.status_code == 200:
                        return ServiceTestResponse(
                            success=True,
                            message="HTTP service is reachable",
                            response_time=response_time,
                            details={
                                "status_code": response.status_code,
                                "endpoint": test_data.endpoint
                            }
                        )
                    else:
                        return ServiceTestResponse(
                            success=False,
                            message=f"HTTP service responded with status {response.status_code}",
                            response_time=response_time,
                            details={
                                "status_code": response.status_code,
                                "endpoint": test_data.endpoint
                            }
                        )
            except httpx.ConnectError:
                return ServiceTestResponse(
                    success=False,
                    message="Connection refused - service may not be running",
                    response_time=time.time() - start_time,
                    details={"error": "connection_refused"}
                )
            except httpx.TimeoutException:
                return ServiceTestResponse(
                    success=False,
                    message="Connection timeout - service is not responding",
                    response_time=time.time() - start_time,
                    details={"error": "timeout"}
                )
            except Exception as e:
                return ServiceTestResponse(
                    success=False,
                    message=f"Connection failed: {str(e)}",
                    response_time=time.time() - start_time,
                    details={"error": str(e)}
                )
                
        elif test_data.transport == "stdio":
            if not test_data.command:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="command is required for STDIO transport test"
                )
            
            # Test STDIO command availability
            try:
                command_name = test_data.command[0]
                if shutil.which(command_name) is None:
                    return ServiceTestResponse(
                        success=False,
                        message=f"Command '{command_name}' not found in PATH",
                        response_time=time.time() - start_time,
                        details={
                            "error": "command_not_found",
                            "command": command_name
                        }
                    )
                
                return ServiceTestResponse(
                    success=True,
                    message=f"Command '{command_name}' is available",
                    response_time=time.time() - start_time,
                    details={
                        "command": command_name,
                        "full_command": test_data.command
                    }
                )
                
            except Exception as e:
                return ServiceTestResponse(
                    success=False,
                    message=f"Command test failed: {str(e)}",
                    response_time=time.time() - start_time,
                    details={"error": str(e)}
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported transport type: {test_data.transport}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Service connection test failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Connection test failed: {str(e)}"
        )
