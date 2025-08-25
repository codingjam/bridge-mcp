"""
MCP Client API Models

Pydantic models for MCP client API requests and responses.
These models handle the JSON-RPC communication with MCP servers.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel


class ConnectServerRequest(BaseModel):
    """Request to connect to an MCP server."""
    server_name: str
    session_id: Optional[str] = None


class ConnectServerResponse(BaseModel):
    """Response from server connection."""
    session_id: str
    server_name: str
    status: str


class ListToolsResponse(BaseModel):
    """Response for listing tools."""
    session_id: str
    tools: List[Dict[str, Any]]


class CallToolRequest(BaseModel):
    """Request to call a tool."""
    tool_name: str
    arguments: Optional[Dict[str, Any]] = None


class CallToolResponse(BaseModel):
    """Response from tool call."""
    session_id: str
    tool_name: str
    result: Dict[str, Any]
    success: bool
    error: Optional[str] = None


class ListResourcesResponse(BaseModel):
    """Response for listing resources."""
    session_id: str
    resources: List[Dict[str, Any]]


class ReadResourceRequest(BaseModel):
    """Request to read a resource."""
    uri: str


class ReadResourceResponse(BaseModel):
    """Response from resource read."""
    session_id: str
    uri: str
    content: Dict[str, Any]


class ServerInfoResponse(BaseModel):
    """Response for server information."""
    session_id: str
    server_info: Dict[str, Any]


class SessionListResponse(BaseModel):
    """Response for session list."""
    sessions: Dict[str, Dict[str, Any]]


# Export all models
__all__ = [
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
]
