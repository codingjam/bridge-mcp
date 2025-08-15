"""Configuration management for MCP Gateway."""

from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with comprehensive proxy configuration."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )
    
    # Server configuration
    HOST: str = Field(default="127.0.0.1", description="Server host")
    PORT: int = Field(default=8000, description="Server port")
    DEBUG: bool = Field(default=False, description="Debug mode")
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(default="json", description="Logging format: json or text")
    
    # Authentication
    API_KEY_HEADER: str = Field(default="X-API-Key", description="API key header name")
    
    # OIDC Authentication with Keycloak
    ENABLE_AUTH: bool = Field(default=False, description="Enable OIDC authentication")
    KEYCLOAK_SERVER_URL: Optional[str] = Field(default=None, description="Keycloak server URL")
    KEYCLOAK_REALM: str = Field(default="master", description="Keycloak realm")
    KEYCLOAK_CLIENT_ID: str = Field(default="mcp-gateway", description="Keycloak client ID")
    KEYCLOAK_CLIENT_SECRET: str = Field(default="", description="Keycloak client secret")
    
    # OIDC Token validation settings
    TOKEN_AUDIENCE: Optional[str] = Field(default=None, description="Expected token audience")
    TOKEN_ISSUER: Optional[str] = Field(default=None, description="Expected token issuer")
    JWKS_CACHE_TTL: int = Field(default=3600, description="JWKS cache TTL in seconds")
    
    # OBO (On-Behalf-Of) settings
    ENABLE_OBO: bool = Field(default=True, description="Enable OAuth2 token exchange for OBO")
    OBO_CACHE_TTL: int = Field(default=1800, description="OBO token cache TTL in seconds")
    
    # Security settings
    CLOCK_SKEW_TOLERANCE: int = Field(default=300, description="Clock skew tolerance in seconds")
    REQUIRED_SCOPES: list[str] = Field(default_factory=list, description="Required scopes for gateway access")
    
    # Service registry
    SERVICE_REGISTRY_FILE: str = Field(
        default="config/services.yaml",
        description="Path to service registry configuration file"
    )
    
    @field_validator('LOG_LEVEL')
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()
    
    @field_validator('LOG_FORMAT')
    @classmethod
    def validate_log_format(cls, v):
        """Validate log format"""
        valid_formats = ['json', 'text']
        if v.lower() not in valid_formats:
            raise ValueError(f"Log format must be one of {valid_formats}")
        return v.lower()
    
    def get_auth_config(self):
        """Create AuthConfig from settings"""
        if not self.ENABLE_AUTH or not self.KEYCLOAK_SERVER_URL:
            return None
        
        from mcp_gateway.auth.models import AuthConfig
        
        return AuthConfig(
            keycloak_server_url=self.KEYCLOAK_SERVER_URL,
            realm=self.KEYCLOAK_REALM,
            client_id=self.KEYCLOAK_CLIENT_ID,
            client_secret=self.KEYCLOAK_CLIENT_SECRET,
            audience=self.TOKEN_AUDIENCE,
            issuer=self.TOKEN_ISSUER,
            jwks_cache_ttl=self.JWKS_CACHE_TTL,
            enable_obo=self.ENABLE_OBO,
            obo_cache_ttl=self.OBO_CACHE_TTL,
            clock_skew_tolerance=self.CLOCK_SKEW_TOLERANCE,
            required_scopes=self.REQUIRED_SCOPES
        )


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings (for dependency injection)"""
    return settings
