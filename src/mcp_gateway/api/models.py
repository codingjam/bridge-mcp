"""
API Models for Dashboard Endpoints (Compatibility Shim)

This file maintains backwards compatibility while models have been moved to:
- models/api/dashboard.py - Dashboard API models
- models/api/common.py - Common API models
- models/api/mcp.py - MCP client API models
- models/api/proxy.py - Proxy API models

Import from the new location for future code.
"""

# Import all models from new location for backwards compatibility
from ..models.api.dashboard import (
    ServiceCreateRequest,
    ServiceCreateResponse,
    ServiceDeleteResponse,
    ServiceTestRequest,
    ServiceTestResponse,
)

# Re-export for backwards compatibility
__all__ = [
    "ServiceCreateRequest",
    "ServiceCreateResponse", 
    "ServiceDeleteResponse",
    "ServiceTestRequest",
    "ServiceTestResponse",
]
