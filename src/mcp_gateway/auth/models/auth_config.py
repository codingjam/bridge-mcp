"""
Authentication configuration model.

This module contains the AuthConfig model which defines all the necessary
configuration parameters for OIDC authentication with Keycloak.
"""

from typing import Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator


class AuthConfig(BaseModel):
    """
    Configuration for OIDC authentication with Keycloak.
    
    This model contains all the necessary configuration parameters
    for integrating with Keycloak for authentication and token validation.
    It supports both basic JWT validation and advanced features like
    token introspection and OAuth2 On-Behalf-Of (OBO) flow.
    
    Example:
        auth_config = AuthConfig(
            keycloak_server_url="https://keycloak.example.com",
            realm="mcp-gateway",
            client_id="gateway-client",
            client_secret="secret-value",
            audience="mcp-services",
            enable_obo=True
        )
    """
    
    # Keycloak server configuration
    keycloak_server_url: HttpUrl = Field(
        ...,
        description="Base URL of the Keycloak server (e.g., https://keycloak.example.com)"
    )
    
    realm: str = Field(
        ...,
        min_length=1,
        description="Keycloak realm name where clients and users are defined"
    )
    
    # Client configuration for the MCP Gateway
    client_id: str = Field(
        ...,
        min_length=1,
        description="Client ID for the MCP Gateway registered in Keycloak"
    )
    
    client_secret: str = Field(
        ...,
        min_length=1,
        description="Client secret for the MCP Gateway (confidential client)"
    )
    
    # Token validation settings
    audience: Optional[str] = Field(
        None,
        description="Expected audience claim in JWT tokens (optional)"
    )
    
    issuer: Optional[str] = Field(
        None,
        description="Expected issuer claim in JWT tokens (auto-generated if not provided)"
    )
    
    # JWKS (JSON Web Key Set) settings
    jwks_cache_ttl: int = Field(
        default=3600,
        ge=300,
        le=86400,
        description="Time to live for JWKS cache in seconds (5 min to 24 hours)"
    )
    
    # Token introspection settings (for revocation checking)
    enable_token_introspection: bool = Field(
        default=False,
        description="Enable token introspection for real-time revocation checking"
    )
    
    introspection_cache_ttl: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Time to live for introspection cache in seconds (1 min to 1 hour)"
    )
    
    # OBO (On-Behalf-Of) settings for service-to-service authentication
    enable_obo: bool = Field(
        default=True,
        description="Enable OAuth2 token exchange for On-Behalf-Of flow"
    )
    
    obo_cache_ttl: int = Field(
        default=1800,
        ge=300,
        le=3600,
        description="Time to live for OBO token cache in seconds (5 min to 1 hour)"
    )
    
    # Security settings
    clock_skew_tolerance: int = Field(
        default=300,
        ge=0,
        le=900,
        description="Clock skew tolerance in seconds for token validation (up to 15 min)"
    )
    
    required_scopes: list[str] = Field(
        default_factory=list,
        description="Required scopes for accessing the MCP Gateway (e.g., ['mcp:read'])"
    )
    
    @field_validator('keycloak_server_url')
    @classmethod
    def validate_keycloak_url(cls, v: HttpUrl) -> str:
        """
        Ensure the Keycloak URL doesn't end with a slash.
        
        This prevents double slashes in generated URLs and ensures
        consistent URL formatting throughout the application.
        
        Args:
            v: The Keycloak server URL
            
        Returns:
            str: Normalized URL without trailing slash
        """
        return str(v).rstrip('/')
    
    @property
    def jwks_uri(self) -> str:
        """
        Get the JWKS (JSON Web Key Set) URI for the realm.
        
        This endpoint provides the public keys used to verify
        JWT token signatures issued by this Keycloak realm.
        
        Returns:
            str: Complete JWKS endpoint URL
        """
        return f"{self.keycloak_server_url}/realms/{self.realm}/protocol/openid-connect/certs"
    
    @property
    def token_endpoint(self) -> str:
        """
        Get the OAuth2 token endpoint for the realm.
        
        This endpoint is used for token exchange operations
        during the On-Behalf-Of (OBO) flow.
        
        Returns:
            str: Complete token endpoint URL
        """
        return f"{self.keycloak_server_url}/realms/{self.realm}/protocol/openid-connect/token"
    
    @property
    def introspection_endpoint(self) -> str:
        """
        Get the token introspection endpoint for the realm.
        
        This endpoint is used to check if tokens are still active
        and have not been revoked. Only used when token introspection
        is enabled.
        
        Returns:
            str: Complete introspection endpoint URL
        """
        return f"{self.keycloak_server_url}/realms/{self.realm}/protocol/openid-connect/token/introspect"
    
    @property
    def issuer_url(self) -> str:
        """
        Get the expected issuer URL for the realm.
        
        This URL should match the 'iss' claim in JWT tokens
        issued by this Keycloak realm. Used for token validation.
        
        Returns:
            str: Expected issuer URL
        """
        return f"{self.keycloak_server_url}/realms/{self.realm}"
