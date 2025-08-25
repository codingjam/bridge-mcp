"""
Routers package for MCP Gateway

Contains FastAPI routers and their associated models:
- mcp_client: Native MCP client routes
- dashboard: Dashboard management routes
- models: API request/response models for all routers
"""

from .mcp_client import mcp_router
from .dashboard import dashboard_router

# Export all routers
__all__ = [
    "mcp_router",
    "dashboard_router",
]
