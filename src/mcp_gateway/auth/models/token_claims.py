"""
JWT token claims model.

This module contains the TokenClaims model which represents the structured
claims extracted from a validated JWT access token, including both standard
JWT claims and Keycloak-specific extensions.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class TokenClaims(BaseModel):
    """
    JWT token claims model.
    
    This model represents the claims extracted from a validated JWT token,
    including both standard JWT claims (RFC 7519) and Keycloak-specific claims.
    It provides convenient methods for checking scopes, roles, and token validity.
    
    The model handles various token types including access tokens, ID tokens,
    and refresh tokens, though it's primarily designed for access tokens used
    in API authentication.
    
    Example:
        claims = TokenClaims(
            sub="user-123",
            iss="https://keycloak.example.com/realms/test",
            aud="my-client",
            exp=1735689600,
            iat=1735603200,
            scope="openid profile mcp:read"
        )
        
        if claims.has_scope("mcp:read"):
            # User has required scope
            pass
    """
    
    # Standard JWT claims (RFC 7519)
    sub: str = Field(
        ..., 
        description="Subject identifier - unique user ID within the issuer"
    )
    
    iss: str = Field(
        ..., 
        description="Issuer identifier - URL of the token issuing authority"
    )
    
    aud: Optional[Union[str, List[str]]] = Field(
        None, 
        description="Audience - intended recipient(s) of the token (can be string or list)"
    )
    
    exp: int = Field(
        ..., 
        description="Expiration time - Unix timestamp when token expires"
    )
    
    iat: int = Field(
        ..., 
        description="Issued at time - Unix timestamp when token was created"
    )
    
    nbf: Optional[int] = Field(
        None, 
        description="Not before time - Unix timestamp before which token is invalid"
    )
    
    jti: Optional[str] = Field(
        None, 
        description="JWT ID - unique identifier for this token"
    )
    
    azp: Optional[str] = Field(
        None,
        description="Authorized party - the party to which the ID Token was issued"
    )
    
    # Keycloak-specific user information claims
    preferred_username: Optional[str] = Field(
        None, 
        description="User's preferred username in Keycloak"
    )
    
    email: Optional[str] = Field(
        None, 
        description="User's email address (if available and verified)"
    )
    
    email_verified: Optional[bool] = Field(
        None, 
        description="Whether the user's email address has been verified"
    )
    
    name: Optional[str] = Field(
        None, 
        description="User's full display name"
    )
    
    given_name: Optional[str] = Field(
        None, 
        description="User's given (first) name"
    )
    
    family_name: Optional[str] = Field(
        None, 
        description="User's family (last) name"
    )
    
    # Authorization and scope claims
    scope: Optional[str] = Field(
        None, 
        description="Space-separated list of granted scopes (e.g., 'openid profile mcp:read')"
    )
    
    resource_access: Optional[Dict[str, Any]] = Field(
        None, 
        description="Client-specific role mappings and permissions"
    )
    
    realm_access: Optional[Dict[str, Any]] = Field(
        None, 
        description="Realm-level role mappings and permissions"
    )
    
    # Session and authentication context
    session_state: Optional[str] = Field(
        None, 
        description="Keycloak session identifier for SSO coordination"
    )
    
    acr: Optional[str] = Field(
        None, 
        description="Authentication Context Class Reference - strength of authentication"
    )
    
    @property
    def scopes(self) -> List[str]:
        """
        Get the list of scopes from the scope claim.
        
        Parses the space-separated scope string into a list of individual scopes.
        This is useful for checking if the token has specific permissions.
        
        Returns:
            List[str]: List of granted scopes, empty list if no scopes
            
        Example:
            token.scope = "openid profile mcp:read mcp:write"
            token.scopes  # Returns: ["openid", "profile", "mcp:read", "mcp:write"]
        """
        if not self.scope:
            return []
        return self.scope.split(' ')
    
    @property
    def is_expired(self) -> bool:
        """
        Check if the token is expired.
        
        Compares the token's expiration time with the current time.
        This check should be performed before using the token for authentication.
        
        Returns:
            bool: True if the token has expired, False otherwise
            
        Note:
            This method doesn't account for clock skew. Use the TokenValidator
            for production validation which includes clock skew tolerance.
        """
        return datetime.utcnow().timestamp() > self.exp
    
    def has_scope(self, required_scope: str) -> bool:
        """
        Check if the token has a specific scope.
        
        This method is case-sensitive and looks for exact scope matches.
        Useful for implementing scope-based authorization in API endpoints.
        
        Args:
            required_scope: The scope to check for (e.g., "mcp:read")
            
        Returns:
            bool: True if the token has the required scope, False otherwise
            
        Example:
            if token.has_scope("mcp:admin"):
                # User has admin permissions
                allow_admin_operations()
        """
        return required_scope in self.scopes
    
    def has_any_scope(self, required_scopes: List[str]) -> bool:
        """
        Check if the token has any of the required scopes.
        
        This is useful when multiple scopes could grant access to a resource,
        implementing OR-based scope authorization.
        
        Args:
            required_scopes: List of acceptable scopes
            
        Returns:
            bool: True if the token has at least one of the required scopes
            
        Example:
            if token.has_any_scope(["mcp:read", "mcp:admin"]):
                # User has either read or admin access
                allow_read_operations()
        """
        return any(scope in self.scopes for scope in required_scopes)
    
    def has_all_scopes(self, required_scopes: List[str]) -> bool:
        """
        Check if the token has all of the required scopes.
        
        This implements AND-based scope authorization where all specified
        scopes must be present for access to be granted.
        
        Args:
            required_scopes: List of required scopes (all must be present)
            
        Returns:
            bool: True if the token has all required scopes
            
        Example:
            if token.has_all_scopes(["mcp:read", "mcp:write"]):
                # User has both read and write permissions
                allow_full_access()
        """
        return all(scope in self.scopes for scope in required_scopes)
    
    def get_client_roles(self, client_id: str) -> List[str]:
        """
        Get roles for a specific client from resource_access claim.
        
        Keycloak stores client-specific roles in the resource_access claim.
        This method extracts roles for a particular client application.
        
        Args:
            client_id: The client ID to get roles for
            
        Returns:
            List[str]: List of roles for the specified client, empty if none
            
        Example:
            admin_roles = token.get_client_roles("admin-console")
            if "realm-admin" in admin_roles:
                # User is a realm administrator
                grant_admin_access()
        """
        if not self.resource_access:
            return []
        
        client_access = self.resource_access.get(client_id, {})
        return client_access.get('roles', [])
    
    def get_realm_roles(self) -> List[str]:
        """
        Get realm-level roles from the realm_access claim.
        
        Realm roles are global roles that apply across all clients
        in the Keycloak realm. These are often used for high-level
        authorization decisions.
        
        Returns:
            List[str]: List of realm roles, empty if none
            
        Example:
            realm_roles = token.get_realm_roles()
            if "admin" in realm_roles:
                # User is a realm-level admin
                grant_global_admin_access()
        """
        if not self.realm_access:
            return []
        return self.realm_access.get('roles', [])
    
    def has_client_role(self, client_id: str, role: str) -> bool:
        """
        Check if the token has a specific client role.
        
        Convenience method that combines getting client roles and checking
        for a specific role in one operation.
        
        Args:
            client_id: The client ID to check
            role: The role to look for
            
        Returns:
            bool: True if the user has the specified role for the client
        """
        return role in self.get_client_roles(client_id)
    
    def has_realm_role(self, role: str) -> bool:
        """
        Check if the token has a specific realm role.
        
        Convenience method for checking realm-level roles.
        
        Args:
            role: The realm role to check for
            
        Returns:
            bool: True if the user has the specified realm role
        """
        return role in self.get_realm_roles()
    
    def time_until_expiry(self) -> int:
        """
        Get the number of seconds until the token expires.
        
        Useful for determining if a token needs to be refreshed soon
        or for implementing token refresh strategies.
        
        Returns:
            int: Seconds until expiry (negative if already expired)
        """
        return self.exp - int(datetime.utcnow().timestamp())
