"""Main entry point for the MCP Gateway application."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from mcp_gateway.api.routes import router
from mcp_gateway.core.config import settings, get_settings
from mcp_gateway.core.logging import setup_logging
from mcp_gateway.core.service_registry import ServiceRegistry
from mcp_gateway.auth.authentication_middleware import AuthenticationMiddleware
from mcp_gateway.rl import RateLimitMiddleware, get_rate_limiter

logger = logging.getLogger(__name__)

# Global service registry instance
_service_registry: Optional[ServiceRegistry] = None


async def get_service_registry() -> ServiceRegistry:
    """Get the global service registry instance (for dependency injection)"""
    global _service_registry
    if _service_registry is None:
        raise RuntimeError("Service registry not initialized")
    return _service_registry


async def create_service_registry() -> ServiceRegistry:
    """Create and initialize the service registry"""
    from pathlib import Path
    
    auth_config = settings.get_auth_config()
    registry = ServiceRegistry(
        config_path=Path(settings.SERVICE_REGISTRY_FILE),
        auth_config=auth_config
    )
    
    # Load services and authentication configurations
    await registry.load_services()
    
    return registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan management
    Handles startup and shutdown procedures
    """
    # Startup
    logger.info("Starting MCP Gateway...")
    
    # Initialize service registry
    global _service_registry
    try:
        _service_registry = await create_service_registry()
        logger.info("Service registry initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize service registry: {e}")
        raise
    
    logger.info(
        "Gateway configuration",
        extra={
            "host": settings.HOST,
            "port": settings.PORT,
            "debug": settings.DEBUG,
            "log_level": settings.LOG_LEVEL,
            "service_registry_file": settings.SERVICE_REGISTRY_FILE,
            "auth_enabled": settings.ENABLE_AUTH,
            "rate_limiting_enabled": settings.ENABLE_RATE_LIMITING
        }
    )
    
    yield
    
    # Shutdown
    logger.info("Shutting down MCP Gateway...")
    _service_registry = None


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Custom validation error handler"""
    logger.warning(
        "Request validation failed",
        extra={
            "url": str(request.url),
            "method": request.method,
            "errors": exc.errors()
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Request validation failed",
            "errors": exc.errors()
        }
    )


async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler for unhandled errors"""
    logger.error(
        "Unhandled exception",
        extra={
            "url": str(request.url),
            "method": request.method,
            "error": str(exc)
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error occurred"
        }
    )


def create_app() -> FastAPI:
    """Create and configure the FastAPI application with production settings."""
    app = FastAPI(
        title="MCP Gateway",
        description="Model Context Protocol Gateway for secure AI model interactions",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
        openapi_tags=[
            {
                "name": "health",
                "description": "Health check and system status"
            },
            {
                "name": "services", 
                "description": "MCP service management and discovery"
            },
            {
                "name": "proxy",
                "description": "Request proxying to MCP servers"
            },
            {
                "name": "mcp",
                "description": "Model Context Protocol specific endpoints"
            },
            {
                "name": "dashboard",
                "description": "Dashboard-specific endpoints for UI consumption"
            }
        ]
    )
    
    # Create rate limiter using dependency injection
    limiter = get_rate_limiter()
    
    # Add rate limiting middleware (before authentication middleware)
    app.add_middleware(
        RateLimitMiddleware,
        limiter=limiter,
        apply_to_paths=("/api/v1/mcp",)  # Apply only to MCP protocol endpoints
    )
    
    # Add authentication middleware if enabled
    auth_config = settings.get_auth_config()
    if auth_config:
        logger.info(
            "Adding authentication middleware",
            extra={
                "keycloak_realm": auth_config.realm,
                "enable_obo": auth_config.enable_obo,
                "required_scopes": auth_config.required_scopes
            }
        )
        app.add_middleware(AuthenticationMiddleware, auth_config=auth_config)
    else:
        logger.warning("Authentication is disabled - running in insecure mode")
    
    # Add security middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"]
    )
    
    # Add custom exception handlers
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    # Include API routes
    app.include_router(router, prefix="/api/v1")
    
    # Root endpoint
    @app.get("/", tags=["health"])
    async def root():
        """Root endpoint with gateway information and available endpoints"""
        return {
            "service": "MCP Gateway",
            "version": "0.1.0", 
            "status": "running",
            "description": "Model Context Protocol Gateway for secure AI model interactions",
            "authentication": {
                "enabled": settings.ENABLE_AUTH,
                "realm": settings.KEYCLOAK_REALM if settings.ENABLE_AUTH else None,
                "oidc_endpoint": f"{settings.KEYCLOAK_SERVER_URL}/realms/{settings.KEYCLOAK_REALM}" if settings.ENABLE_AUTH and settings.KEYCLOAK_SERVER_URL else None
            },
            "api": {
                "version": "v1",
                "base_url": "/api/v1"
            },
            "endpoints": {
                "health": "/api/v1/health",
                "services": "/api/v1/services",
                "service_detail": "/api/v1/services/{service_id}",
                "service_health": "/api/v1/services/{service_id}/health",
                "proxy": "/api/v1/proxy/{service_id}/{path}",
                "mcp_call": "/api/v1/mcp/{service_id}/call"
            },
            "documentation": {
                "swagger": "/docs" if settings.DEBUG else "disabled",
                "redoc": "/redoc" if settings.DEBUG else "disabled"
            }
        }
    
    return app


# Create app instance for uvicorn to find
app = create_app()


def main() -> None:
    """Main entry point for the application."""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting MCP Gateway...")
    
    # Create FastAPI app
    app = create_app()
    
    # Run the server
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        access_log=True,
        server_header=False,  # Don't reveal server info
        date_header=True,
    )


if __name__ == "__main__":
    main()
