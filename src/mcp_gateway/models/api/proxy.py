"""
Legacy Proxy API Models

Pydantic models for the legacy HTTP proxy API.
These models handle proxying requests to MCP servers over HTTP.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel


class ProxyRequest(BaseModel):
    """Request to proxy to an MCP server via HTTP."""
    method: str
    path: str
    headers: Optional[Dict[str, str]] = None
    body: Optional[Dict[str, Any]] = None
    query_params: Optional[Dict[str, str]] = None


class ProxyResponse(BaseModel):
    """Response from HTTP proxy operation."""
    status_code: int
    headers: Dict[str, str]
    body: Dict[str, Any]
    execution_time: Optional[float] = None


class ProxyHealthResponse(BaseModel):
    """Health check response for proxy services."""
    service_name: str
    status: str
    response_time: Optional[float] = None
    error: Optional[str] = None


# Export all models
__all__ = [
    "ProxyRequest",
    "ProxyResponse", 
    "ProxyHealthResponse",
]
