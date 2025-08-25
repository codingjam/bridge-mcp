"""
API Models package

Contains Pydantic models for FastAPI request/response handling:
- mcp: MCP client API models
- dashboard: Dashboard management API models
- common: Shared API models and utilities
"""

# Import all models for easy access
from .common import (
    ErrorResponse,
    SuccessResponse,
    HealthResponse,
    StatusResponse,
    PaginatedResponse,
)
from .mcp import (
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
from .dashboard import (
    ServiceCreateRequest,
    ServiceCreateResponse,
    ServiceDeleteResponse,
    ServiceTestRequest,
    ServiceTestResponse,
)

# Export all models
__all__ = [
    # Common models
    "ErrorResponse",
    "SuccessResponse", 
    "HealthResponse",
    "StatusResponse",
    "PaginatedResponse",
    # MCP models
    "ConnectServerRequest",
    "ConnectServerResponse",
    "ListToolsResponse", 
    "CallToolRequest",
    "CallToolResponse",
    "ListResourcesResponse",
    "ReadResourceRequest",
    "ReadResourceResponse",
    "ServerInfoResponse",
    "SessionListResponse",
    # Dashboard models
    "ServiceCreateRequest",
    "ServiceCreateResponse",
    "ServiceDeleteResponse",
    "ServiceTestRequest", 
    "ServiceTestResponse",
]
