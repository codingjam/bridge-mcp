"""
Service authentication configuration model.

This module contains the MCPServiceAuth model which defines how the gateway
should authenticate with individual MCP services, including OBO token exchange
configuration and custom authentication headers.
"""

from enum import Enum
from typing import Dict, List
from pydantic import BaseModel, Field


class AuthStrategy(str, Enum):
    """
    Authentication strategy for MCP services.
    
    Defines the different ways the gateway can authenticate with
    downstream MCP services, providing clear options for various
    integration scenarios.
    """
    
    OBO_REQUIRED = "obo_required"
    """
    Always use OAuth2 On-Behalf-Of token exchange.
    Fails if OBO is not available or token exchange fails.
    Best for services that require service-specific tokens.
    """
    
    OBO_PREFERRED = "obo_preferred"
    """
    Try OBO first, fallback to user token passthrough.
    Provides resilience while preferring the more secure OBO approach.
    Good for services transitioning to OBO support.
    """
    
    PASSTHROUGH = "passthrough"
    """
    Always forward the original user token.
    Used for services that accept user tokens directly.
    Simpler but less secure than OBO.
    """
    
    NO_AUTH = "no_auth"
    """
    No authentication with the service.
    Used for public services or services with alternative auth mechanisms.
    """


class MCPServiceAuth(BaseModel):
    """
    Authentication configuration for individual MCP services.
    
    This model defines how the gateway should authenticate with
    specific MCP services. It supports various authentication strategies
    including OAuth2 On-Behalf-Of (OBO) token exchange, user token
    passthrough, and custom authentication headers.
    
    The configuration allows for fine-grained control over how each
    service is accessed, accommodating different security requirements
    and integration patterns.
    
    Example:
        # Service requiring OBO with specific audience
        service_auth = MCPServiceAuth(
            service_id="analytics-api",
            auth_strategy=AuthStrategy.OBO_REQUIRED,
            target_audience="analytics-backend",
            required_scopes=["analytics:read", "analytics:query"],
            custom_headers={"X-Service-Version": "v2"}
        )
        
        # Service accepting user tokens directly
        legacy_auth = MCPServiceAuth(
            service_id="legacy-service",
            auth_strategy=AuthStrategy.PASSTHROUGH,
            custom_headers={"X-Legacy-Mode": "true"}
        )
    """
    
    # Service identification
    service_id: str = Field(
        ..., 
        description="Unique identifier for the MCP service"
    )
    
    # Authentication strategy
    auth_strategy: AuthStrategy = Field(
        default=AuthStrategy.NO_AUTH,
        description="Authentication strategy to use for this service"
    )
    
    # OBO (On-Behalf-Of) configuration
    target_audience: str | None = Field(
        None,
        description="Target audience for OBO token exchange (required for OBO strategies)"
    )
    
    required_scopes: List[str] = Field(
        default_factory=list,
        description="Required scopes for OBO token exchange or validation"
    )
    
    # Backward compatibility fields (deprecated in favor of auth_strategy)
    enable_auth: bool = Field(
        default=True,
        description="[DEPRECATED] Use auth_strategy instead. Whether authentication is required"
    )
    
    passthrough_user_token: bool = Field(
        default=False,
        description="[DEPRECATED] Use auth_strategy=PASSTHROUGH instead"
    )
    
    # Service-specific customization
    custom_headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Custom headers to add when calling this service"
    )
    
    # Token caching behavior
    cache_tokens: bool = Field(
        default=True,
        description="Whether to cache OBO tokens for this service"
    )
    
    custom_cache_ttl: int | None = Field(
        None,
        ge=60,
        le=7200,
        description="Custom cache TTL for this service's tokens (seconds, 1min-2hrs)"
    )
    
    # Retry and timeout configuration
    auth_timeout: float | None = Field(
        None,
        ge=1.0,
        le=30.0,
        description="Custom timeout for authentication operations (seconds)"
    )
    
    max_auth_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Maximum retries for failed authentication attempts"
    )
    
    def model_post_init(self, __context) -> None:
        """
        Post-initialization validation and backward compatibility handling.
        
        This method ensures backward compatibility with the old enable_auth
        and passthrough_user_token fields while migrating to the new
        auth_strategy field.
        """
        # Handle backward compatibility for auth strategy
        if self.auth_strategy == AuthStrategy.NO_AUTH:
            # Infer strategy from legacy fields
            if self.enable_auth and self.passthrough_user_token:
                self.auth_strategy = AuthStrategy.PASSTHROUGH
            elif self.enable_auth and not self.passthrough_user_token:
                self.auth_strategy = AuthStrategy.OBO_REQUIRED
            elif not self.enable_auth:
                self.auth_strategy = AuthStrategy.NO_AUTH
    
    @property
    def requires_authentication(self) -> bool:
        """
        Check if this service requires any form of authentication.
        
        Returns:
            bool: True if authentication is required, False for no-auth services
        """
        return self.auth_strategy != AuthStrategy.NO_AUTH
    
    @property
    def uses_obo(self) -> bool:
        """
        Check if this service uses OAuth2 On-Behalf-Of token exchange.
        
        Returns:
            bool: True if OBO is used (required or preferred)
        """
        return self.auth_strategy in [AuthStrategy.OBO_REQUIRED, AuthStrategy.OBO_PREFERRED]
    
    @property
    def allows_passthrough(self) -> bool:
        """
        Check if this service allows user token passthrough.
        
        Returns:
            bool: True if passthrough is allowed (as primary or fallback strategy)
        """
        return self.auth_strategy in [AuthStrategy.PASSTHROUGH, AuthStrategy.OBO_PREFERRED]
    
    @property
    def requires_obo_success(self) -> bool:
        """
        Check if OBO token exchange must succeed (no fallback allowed).
        
        Returns:
            bool: True if OBO failure should cause request failure
        """
        return self.auth_strategy == AuthStrategy.OBO_REQUIRED
    
    def get_effective_cache_ttl(self, default_ttl: int) -> int:
        """
        Get the effective cache TTL for this service.
        
        Args:
            default_ttl: System default cache TTL
            
        Returns:
            int: Effective cache TTL to use (custom or default)
        """
        if not self.cache_tokens:
            return 0  # No caching
        return self.custom_cache_ttl or default_ttl
    
    def get_auth_headers(self, token: str) -> Dict[str, str]:
        """
        Get complete headers for authenticating with this service.
        
        Combines the authentication header with any custom headers
        defined for this service.
        
        Args:
            token: The access token to use for authentication
            
        Returns:
            Dict[str, str]: Complete headers dictionary
            
        Example:
            headers = service_auth.get_auth_headers("abc123token")
            # Returns: {
            #     "Authorization": "Bearer abc123token",
            #     "X-Service-Version": "v2",
            #     "X-Custom-Header": "value"
            # }
        """
        headers = {"Authorization": f"Bearer {token}"}
        headers.update(self.custom_headers)
        return headers
    
    def validate_config(self) -> List[str]:
        """
        Validate the service authentication configuration.
        
        Checks for common configuration errors and returns a list
        of validation warnings or errors.
        
        Returns:
            List[str]: List of validation issues (empty if valid)
            
        Example:
            issues = service_auth.validate_config()
            if issues:
                logger.warning(f"Service {service_id} config issues: {issues}")
        """
        issues = []
        
        # Check OBO configuration
        if self.uses_obo and not self.target_audience:
            issues.append("OBO strategy requires target_audience to be specified")
        
        # Check scope configuration
        if self.uses_obo and not self.required_scopes:
            issues.append("OBO strategy should specify required_scopes")
        
        # Check cache configuration
        if self.custom_cache_ttl and not self.cache_tokens:
            issues.append("custom_cache_ttl specified but cache_tokens is False")
        
        # Check timeout configuration
        if self.auth_timeout and self.auth_timeout < 1.0:
            issues.append("auth_timeout should be at least 1.0 seconds")
        
        return issues
    
    def to_dict(self) -> dict:
        """
        Convert service auth config to dictionary for logging or storage.
        
        Returns:
            dict: Service authentication configuration (excluding secrets)
        """
        return {
            "service_id": self.service_id,
            "auth_strategy": self.auth_strategy.value,
            "target_audience": self.target_audience,
            "required_scopes": self.required_scopes,
            "cache_tokens": self.cache_tokens,
            "custom_cache_ttl": self.custom_cache_ttl,
            "auth_timeout": self.auth_timeout,
            "max_auth_retries": self.max_auth_retries,
            "custom_headers_count": len(self.custom_headers)
        }
