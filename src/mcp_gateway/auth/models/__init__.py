"""
Authentication models package.

This package provides comprehensive data models for OIDC authentication,
user context management, and service authentication configuration.

The models are organized into focused modules:
- auth_config: Keycloak/OIDC configuration
- token_claims: JWT token structure and validation
- user_context: Simplified user representation
- service_auth: Service-specific authentication settings

Example Usage:
    from mcp_gateway.auth.models import (
        AuthConfig,
        TokenClaims,
        UserContext,
        MCPServiceAuth,
        AuthStrategy
    )
    
    # Configure OIDC authentication
    config = AuthConfig(
        keycloak_server_url="https://keycloak.example.com",
        realm="mcp-gateway",
        client_id="gateway-client",
        client_secret="secret"
    )
    
    # Create service authentication config
    service_auth = MCPServiceAuth(
        service_id="analytics-api",
        auth_strategy=AuthStrategy.OBO_REQUIRED,
        target_audience="analytics-backend"
    )
"""

from .auth_config import AuthConfig
from .token_claims import TokenClaims
from .user_context import UserContext
from .service_auth import MCPServiceAuth, AuthStrategy

__all__ = [
    # Core authentication configuration
    "AuthConfig",
    
    # Token and user models
    "TokenClaims",
    "UserContext",
    
    # Service authentication
    "MCPServiceAuth",
    "AuthStrategy",
]

# Version information for the models package
__version__ = "1.0.0"
