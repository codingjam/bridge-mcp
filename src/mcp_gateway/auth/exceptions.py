"""
Custom exceptions for authentication and authorization.

This module defines specific exception types for different authentication 
and authorization failure scenarios, providing clear error categorization
and appropriate HTTP status code mapping.
"""

from typing import Optional


class AuthenticationError(Exception):
    """
    Base exception for authentication failures.
    
    This exception is raised when authentication fails for any reason,
    such as missing or invalid tokens.
    """
    
    def __init__(self, message: str, error_code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "authentication_failed"


class TokenValidationError(AuthenticationError):
    """
    Exception raised when token validation fails.
    
    This includes scenarios like:
    - Invalid JWT signature
    - Expired tokens
    - Invalid token format
    - Missing required claims
    """
    
    def __init__(self, message: str, token_error: Optional[str] = None):
        super().__init__(message, "token_validation_failed")
        self.token_error = token_error


class TokenExchangeError(AuthenticationError):
    """
    Exception raised when OAuth2 token exchange (OBO) fails.
    
    This occurs when the gateway cannot exchange the user's token
    for an access token to call downstream MCP services.
    """
    
    def __init__(self, message: str, keycloak_error: Optional[str] = None):
        super().__init__(message, "token_exchange_failed")
        self.keycloak_error = keycloak_error


class InsufficientPermissionsError(AuthenticationError):
    """
    Exception raised when user has valid authentication but insufficient permissions.
    
    This occurs when:
    - User token is valid but lacks required scopes
    - User doesn't have access to specific MCP services
    - Service-specific authorization failures
    """
    
    def __init__(self, message: str, required_permission: Optional[str] = None):
        super().__init__(message, "insufficient_permissions")
        self.required_permission = required_permission


class KeycloakConnectionError(AuthenticationError):
    """
    Exception raised when unable to connect to Keycloak.
    
    This includes network failures, Keycloak service unavailability,
    or configuration errors.
    """
    
    def __init__(self, message: str, connection_error: Optional[str] = None):
        super().__init__(message, "keycloak_connection_failed")
        self.connection_error = connection_error
