"""
Authentication models (legacy import).

This module provides backward compatibility imports from the new models package.
All models have been moved to individual files under auth/models/ for better
organization and maintainability.

DEPRECATED: Import from mcp_gateway.auth.models directly instead.

Example:
    # Preferred (new):
    from mcp_gateway.auth.models import AuthConfig, UserContext
    
    # Still works (legacy):
    from mcp_gateway.auth.models import AuthConfig, UserContext
"""

# Import all models from the new package structure
from .models import (
    AuthConfig,
    TokenClaims,
    UserContext,
    MCPServiceAuth,
    AuthStrategy
)

# Re-export everything for backward compatibility
__all__ = [
    "AuthConfig",
    "TokenClaims", 
    "UserContext",
    "MCPServiceAuth",
    "AuthStrategy"
]
