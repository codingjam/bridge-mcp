"""
MCP Client Exception Classes

Custom exceptions for MCP client operations and error handling.
"""

from typing import Optional, Dict, Any


class MCPClientError(Exception):
    """Base exception for all MCP client errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class MCPConnectionError(MCPClientError):
    """Raised when connection to MCP server fails."""
    
    def __init__(
        self,
        message: str,
        server_url: Optional[str] = None,
        transport_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)
        self.server_url = server_url
        self.transport_type = transport_type


class MCPTransportError(MCPClientError):
    """Raised when transport-level operations fail."""
    
    def __init__(
        self,
        message: str,
        transport_type: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)
        self.transport_type = transport_type
        self.error_code = error_code


class MCPAuthenticationError(MCPClientError):
    """Raised when authentication with MCP server fails."""
    
    def __init__(
        self,
        message: str,
        auth_method: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)
        self.auth_method = auth_method


class MCPSessionError(MCPClientError):
    """Raised when session management operations fail."""
    
    def __init__(
        self,
        message: str,
        session_id: Optional[str] = None,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)
        self.session_id = session_id
        self.operation = operation


class MCPProtocolError(MCPClientError):
    """Raised when MCP protocol violations occur."""
    
    def __init__(
        self,
        message: str,
        method: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message, details)
        self.method = method
        self.params = params
