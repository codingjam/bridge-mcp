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

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from mcp_gateway.core.config import get_settings
from mcp_gateway.core.service_registry import ServiceRegistry
from mcp_gateway.rl import get_rate_limiter

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
        health_status = await registry.get_all_health_status()
        
        # Calculate service metrics
        total_services = len(services)
        enabled_services = sum(1 for service in services.values() if service.enabled)
        healthy_services = sum(1 for service_id in services.keys() if health_status.get(service_id, False))
        
        # Get rate limiting information
        rate_limiter = get_rate_limiter()
        rate_limit_stats = await _get_rate_limit_overview(rate_limiter)
        
        # Calculate system metrics (placeholder - would be replaced with real metrics)
        system_metrics = await _get_system_metrics()
        
        # Determine overall system status
        system_status = _calculate_system_status(
            total_services, healthy_services, enabled_services, rate_limit_stats
        )
        
        overview_data = {
            # Service Information
            "services": {
                "total": total_services,
                "enabled": enabled_services,
                "healthy": healthy_services,
                "unhealthy": enabled_services - healthy_services,
                "disabled": total_services - enabled_services
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
                "healthy_services": healthy_services,
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
        health_status = await registry.get_all_health_status()
        
        service_health_summary = []
        
        for service_id, service in services.items():
            is_healthy = health_status.get(service_id, False)
            
            service_summary = {
                "id": service_id,
                "name": service.name,
                "enabled": service.enabled,
                "healthy": is_healthy,
                "status": _get_service_status_text(service.enabled, is_healthy),
                "transport": service.transport,
                "endpoint": str(service.endpoint) if service.transport == "http" else None,
                "tags": service.tags or [],
                "lastChecked": datetime.utcnow().isoformat()  # Placeholder - would be real timestamp
            }
            
            service_health_summary.append(service_summary)
        
        # Sort by status priority (unhealthy first, then disabled, then healthy)
        service_health_summary.sort(key=lambda s: (
            0 if not s["enabled"] else (1 if not s["healthy"] else 2),
            s["name"]
        ))
        
        summary = {
            "services": service_health_summary,
            "summary": {
                "total": len(services),
                "healthy": sum(1 for s in service_health_summary if s["healthy"] and s["enabled"]),
                "unhealthy": sum(1 for s in service_health_summary if not s["healthy"] and s["enabled"]),
                "disabled": sum(1 for s in service_health_summary if not s["enabled"])
            },
            "lastUpdated": datetime.utcnow().isoformat()
        }
        
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get service health summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve service health summary"
        )


# Helper functions for dashboard data aggregation
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
