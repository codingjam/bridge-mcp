"""
Authentication module for MCP Gateway.

This module provides OIDC authentication with Keycloak integration,
including token validation, On-Behalf-Of (OBO) flow, and security middleware.
"""

from .middleware import AuthenticationMiddleware
from .token_validator import TokenValidator
from .obo_service import OBOTokenService
from .models import AuthConfig, UserContext, TokenClaims
from .exceptions import (
    AuthenticationError,
    TokenValidationError,
    TokenExchangeError,
    InsufficientPermissionsError
)

__all__ = [
    "AuthenticationMiddleware",
    "TokenValidator", 
    "OBOTokenService",
    "AuthConfig",
    "UserContext",
    "TokenClaims",
    "AuthenticationError",
    "TokenValidationError", 
    "TokenExchangeError",
    "InsufficientPermissionsError"
]
