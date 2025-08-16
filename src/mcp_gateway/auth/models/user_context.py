"""
User context model.

This module contains the UserContext model which provides a simplified
representation of an authenticated user for use throughout the application.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from .token_claims import TokenClaims


class UserContext(BaseModel):
    """
    User context information extracted from validated token.
    
    This model provides a simplified and normalized view of the authenticated user
    for use throughout the application. It extracts the most commonly needed
    user information from the token claims and provides convenient methods
    for authorization checks.
    
    The UserContext is created from validated TokenClaims and serves as a
    clean interface between the authentication system and the rest of the
    application, hiding the complexity of JWT token structures.
    
    Example:
        # Created from token claims
        user = UserContext.from_token_claims(validated_claims)
        
        # Used in application logic
        if user.has_scope("mcp:admin"):
            return admin_dashboard()
        
        # Access user information
        logger.info(f"User {user.username} ({user.user_id}) accessed service")
    """
    
    # Core user identification
    user_id: str = Field(
        ..., 
        description="Unique user identifier (from 'sub' claim)"
    )
    
    username: Optional[str] = Field(
        None, 
        description="User's preferred username (human-readable identifier)"
    )
    
    email: Optional[str] = Field(
        None, 
        description="User's email address (if available and verified)"
    )
    
    name: Optional[str] = Field(
        None, 
        description="User's full display name"
    )
    
    # Authorization information
    scopes: List[str] = Field(
        default_factory=list, 
        description="List of granted scopes for authorization checks"
    )
    
    roles: List[str] = Field(
        default_factory=list, 
        description="List of user roles (typically realm roles)"
    )
    
    # Token metadata for tracking and debugging
    token_jti: Optional[str] = Field(
        None, 
        description="Token ID (jti claim) for tracking and revocation"
    )
    
    session_id: Optional[str] = Field(
        None, 
        description="Session identifier for SSO coordination"
    )
    
    # Timestamp information for session management
    authenticated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when authentication was processed by the gateway"
    )
    
    token_expires_at: datetime = Field(
        ..., 
        description="When the underlying access token expires"
    )
    
    # User verification status
    email_verified: Optional[bool] = Field(
        None,
        description="Whether the user's email has been verified in the identity provider"
    )
    
    @classmethod
    def from_token_claims(cls, claims: TokenClaims) -> "UserContext":
        """
        Create UserContext from validated token claims.
        
        This factory method extracts the relevant user information from
        JWT token claims and creates a normalized UserContext object.
        It handles missing or optional claims gracefully.
        
        Args:
            claims: Validated token claims from JWT
            
        Returns:
            UserContext: Normalized user context object
            
        Example:
            # After token validation
            validated_claims = await token_validator.validate_token(token)
            user_context = UserContext.from_token_claims(validated_claims)
            
            # Now use the clean user context
            request.state.user = user_context
        """
        return cls(
            user_id=claims.sub,
            username=claims.preferred_username,
            email=claims.email,
            name=claims.name,
            scopes=claims.scopes,
            roles=claims.get_realm_roles(),
            token_jti=claims.jti,
            session_id=claims.session_state,
            token_expires_at=datetime.fromtimestamp(claims.exp),
            email_verified=claims.email_verified
        )
    
    def has_scope(self, required_scope: str) -> bool:
        """
        Check if the user has a specific scope.
        
        This is the primary method for scope-based authorization in the application.
        It provides a clean interface for checking permissions without dealing
        with token claims directly.
        
        Args:
            required_scope: The scope to check for (e.g., "mcp:read")
            
        Returns:
            bool: True if the user has the required scope
            
        Example:
            @app.get("/admin")
            async def admin_endpoint(user: UserContext = Depends(require_auth)):
                if not user.has_scope("mcp:admin"):
                    raise HTTPException(403, "Admin access required")
                return {"admin": "data"}
        """
        return required_scope in self.scopes
    
    def has_any_scope(self, required_scopes: List[str]) -> bool:
        """
        Check if the user has any of the required scopes.
        
        Useful for endpoints that can be accessed with different permission levels.
        
        Args:
            required_scopes: List of acceptable scopes
            
        Returns:
            bool: True if the user has at least one of the required scopes
            
        Example:
            if user.has_any_scope(["mcp:read", "mcp:admin"]):
                # User can read data
                return get_data()
        """
        return any(scope in self.scopes for scope in required_scopes)
    
    def has_all_scopes(self, required_scopes: List[str]) -> bool:
        """
        Check if the user has all of the required scopes.
        
        Used when multiple permissions are required for an operation.
        
        Args:
            required_scopes: List of required scopes (all must be present)
            
        Returns:
            bool: True if the user has all required scopes
        """
        return all(scope in self.scopes for scope in required_scopes)
    
    def has_role(self, required_role: str) -> bool:
        """
        Check if the user has a specific role.
        
        Role-based authorization using realm roles from Keycloak.
        Roles are typically higher-level permissions than scopes.
        
        Args:
            required_role: The role to check for (e.g., "admin")
            
        Returns:
            bool: True if the user has the required role
            
        Example:
            if user.has_role("super-admin"):
                # Grant access to system administration
                return system_admin_panel()
        """
        return required_role in self.roles
    
    def has_any_role(self, required_roles: List[str]) -> bool:
        """
        Check if the user has any of the required roles.
        
        Args:
            required_roles: List of acceptable roles
            
        Returns:
            bool: True if the user has at least one of the required roles
        """
        return any(role in self.roles for role in required_roles)
    
    @property
    def is_token_expired(self) -> bool:
        """
        Check if the user's token is expired.
        
        This check uses the gateway's local time and doesn't account for
        clock skew. It's primarily useful for session management and
        determining when to prompt for re-authentication.
        
        Returns:
            bool: True if the token has expired
            
        Note:
            For authoritative token validation, use the TokenValidator
            which includes proper clock skew handling.
        """
        return datetime.utcnow() > self.token_expires_at
    
    @property
    def is_email_verified(self) -> bool:
        """
        Check if the user's email is verified.
        
        Returns:
            bool: True if email is verified, False if not verified or unknown
        """
        return self.email_verified is True
    
    @property
    def display_name(self) -> str:
        """
        Get the best available display name for the user.
        
        Returns the full name if available, otherwise falls back to
        username, email, or user ID in that order.
        
        Returns:
            str: User's display name for UI purposes
        """
        return (
            self.name or 
            self.username or 
            self.email or 
            f"User {self.user_id}"
        )
    
    @property
    def time_until_token_expiry(self) -> int:
        """
        Get seconds until token expires.
        
        Useful for implementing token refresh logic or warning users
        about upcoming session expiration.
        
        Returns:
            int: Seconds until token expires (negative if already expired)
        """
        delta = self.token_expires_at - datetime.utcnow()
        return int(delta.total_seconds())
    
    def to_dict(self) -> dict:
        """
        Convert user context to dictionary for logging or serialization.
        
        Excludes sensitive information and provides a clean representation
        suitable for logging or API responses.
        
        Returns:
            dict: User context as dictionary (without sensitive data)
        """
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "name": self.name,
            "scopes": self.scopes,
            "roles": self.roles,
            "email_verified": self.email_verified,
            "authenticated_at": self.authenticated_at.isoformat(),
            "token_expires_at": self.token_expires_at.isoformat()
        }
