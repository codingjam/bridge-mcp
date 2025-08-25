"""
JWT token validation service for OIDC authentication.

This         logger.info(
            "TokenValidator initialized",
            extra={
                "realm": self.config.realm,
                "jwks_uri": self.config.jwks_uri
            }
        )rovides comprehensive JWT token validation including
signature verification using JWKS, claim validation, and optional
token introspection for revocation checking.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
import asyncio
from functools import lru_cache

import httpx
from authlib.jose import JsonWebKey, JsonWebToken, JoseError
from authlib.jose.errors import InvalidClaimError, InvalidTokenError

from .models import AuthConfig, TokenClaims
from .exceptions import (
    TokenValidationError,
    KeycloakConnectionError
)

logger = logging.getLogger(__name__)


class TokenValidator:
    """
    JWT token validator with JWKS support and optional introspection.
    
    This class handles:
    - JWT signature validation using Keycloak's JWKS endpoint
    - Token claim validation (exp, iss, aud, etc.)
    - Optional token introspection for revocation checking
    - Caching of JWKS keys and introspection results for performance
    """
    
    def __init__(self, auth_config: AuthConfig):
        """
        Initialize the token validator.
        
        Args:
            auth_config: Authentication configuration containing Keycloak settings
        """
        self.config = auth_config
        self.jwt = JsonWebToken(['RS256', 'RS384', 'RS512', 'ES256', 'ES384', 'ES512'])
        
        # HTTP client for Keycloak communication
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            headers={
                'User-Agent': 'MCP-Gateway/1.0',
                'Accept': 'application/json'
            }
        )
        
        # Cache for JWKS keys
        self._jwks_cache: Optional[Dict[str, Any]] = None
        self._jwks_cache_time: Optional[datetime] = None
        self._jwks_lock = asyncio.Lock()
        
        # Cache for token introspection results
        self._introspection_cache: Dict[str, Dict[str, Any]] = {}
        self._introspection_cache_times: Dict[str, datetime] = {}
        
        logger.info(
            "TokenValidator initialized",
            extra={
                "realm": self.config.realm,
                "jwks_uri": self.config.jwks_uri
            }
        )
    
    async def validate_token(self, token: str) -> TokenClaims:
        """
        Validate a JWT access token.
        
        This method performs comprehensive token validation including:
        1. JWT signature verification using JWKS
        2. Standard claim validation (exp, iss, aud, etc.)
        3. Optional token introspection for revocation checking
        
        Args:
            token: The JWT access token to validate
            
        Returns:
            TokenClaims: Parsed and validated token claims
            
        Raises:
            TokenValidationError: If token validation fails for any reason
        """
        if not token or not token.strip():
            raise TokenValidationError("Token is empty or missing")
        
        try:
            # Step 1: Get JWKS keys for signature verification
            jwks = await self._get_jwks()
            
            # Step 2: Verify JWT signature and extract claims
            try:
                claims = self.jwt.decode(token, jwks)
            except InvalidTokenError as e:
                raise TokenValidationError(f"Invalid JWT token: {str(e)}", str(e))
            except JoseError as e:
                raise TokenValidationError(f"JWT verification failed: {str(e)}", str(e))
            
            # Step 3: Validate standard claims
            await self._validate_claims(claims)
            
            # Step 4: Parse claims into structured model
            token_claims = TokenClaims(**claims)
            
            # Step 6: Validate required scopes
            if self.config.required_scopes:
                if not token_claims.has_any_scope(self.config.required_scopes):
                    raise TokenValidationError(
                        f"Token missing required scopes: {self.config.required_scopes}"
                    )
            
            logger.info(
                "Token validation successful",
                extra={
                    "sub": token_claims.sub,
                    "scopes": token_claims.scopes,
                    "exp": token_claims.exp
                }
            )
            
            return token_claims
            
        except TokenValidationError:
            # Re-raise our own exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error during token validation: {e}", exc_info=True)
            raise TokenValidationError(f"Token validation failed: {str(e)}")
    
    async def _get_jwks(self) -> Dict[str, Any]:
        """
        Get JWKS keys from Keycloak with caching.
        
        This method retrieves the JSON Web Key Set (JWKS) from Keycloak's
        well-known endpoint and caches it according to the configured TTL.
        
        Returns:
            Dict containing JWKS keys
            
        Raises:
            KeycloakConnectionError: If unable to retrieve JWKS
        """
        async with self._jwks_lock:
            # Check if we have valid cached JWKS
            now = datetime.utcnow()
            if (self._jwks_cache and self._jwks_cache_time and
                (now - self._jwks_cache_time).total_seconds() < self.config.jwks_cache_ttl):
                return self._jwks_cache
            
            # Fetch fresh JWKS from Keycloak
            try:
                logger.info(f"Fetching JWKS from {self.config.jwks_uri}")
                
                response = await self.http_client.get(self.config.jwks_uri)
                response.raise_for_status()
                
                jwks_data = response.json()
                
                # Convert to authlib JsonWebKey format
                jwks = JsonWebKey.import_key_set(jwks_data)
                
                # Cache the results
                self._jwks_cache = jwks
                self._jwks_cache_time = now
                
                logger.info(
                    "JWKS refreshed successfully",
                    extra={
                        "keys_count": len(jwks_data.get('keys', [])),
                        "cache_ttl": self.config.jwks_cache_ttl
                    }
                )
                
                return jwks
                
            except httpx.HTTPError as e:
                logger.error(
                    f"Failed to fetch JWKS from URL: {self.config.jwks_uri} - Error: {e}",
                    extra={
                        "jwks_uri": self.config.jwks_uri,
                        "error_type": type(e).__name__,
                        "error_details": str(e)
                    }
                )
                raise KeycloakConnectionError(
                    f"Unable to fetch JWKS from Keycloak: {str(e)}",
                    str(e)
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error fetching JWKS from URL: {self.config.jwks_uri} - Error: {e}",
                    extra={
                        "jwks_uri": self.config.jwks_uri,
                        "error_type": type(e).__name__,
                        "error_details": str(e)
                    },
                    exc_info=True
                )
                raise KeycloakConnectionError(
                    f"Unexpected error fetching JWKS: {str(e)}",
                    str(e)
                )
    
    async def _validate_claims(self, claims: Dict[str, Any]) -> None:
        """
        Validate JWT standard claims.
        
        This method validates standard JWT claims including:
        - exp (expiration time)
        - iss (issuer)
        - aud (audience)
        - nbf (not before)
        
        Args:
            claims: Dictionary of JWT claims
            
        Raises:
            TokenValidationError: If any claim validation fails
        """
        now = datetime.utcnow().timestamp()
        
        # Validate expiration time (required)
        exp = claims.get('exp')
        if not exp:
            raise TokenValidationError("Token missing expiration claim (exp)")
        
        if now > (exp + self.config.clock_skew_tolerance):
            raise TokenValidationError("Token has expired")
        
        # Validate not before time (optional)
        nbf = claims.get('nbf')
        if nbf and now < (nbf - self.config.clock_skew_tolerance):
            raise TokenValidationError("Token not yet valid (nbf)")
        
        # Validate issuer (if configured)
        if self.config.issuer:
            iss = claims.get('iss')
            if iss != self.config.issuer:
                raise TokenValidationError(
                    f"Invalid issuer: expected {self.config.issuer}, got {iss}"
                )
        
        # Validate audience (if configured)
        if self.config.audience:
            aud = claims.get('aud')
            if isinstance(aud, list):
                if self.config.audience not in aud:
                    raise TokenValidationError(
                        f"Invalid audience: {self.config.audience} not in {aud}"
                    )
            elif aud != self.config.audience:
                raise TokenValidationError(
                    f"Invalid audience: expected {self.config.audience}, got {aud}"
                )
    
    async def _validate_introspection(self, token: str) -> None:
        """
        Validate token using Keycloak's introspection endpoint.
        
        This method checks if the token is still active (not revoked)
        using Keycloak's token introspection endpoint.
        
        Args:
            token: The JWT token to introspect
            
        Raises:
            TokenValidationError: If token is revoked or introspection fails
        """
        # Check cache first
        cache_key = f"introspect_{hash(token)}"
        now = datetime.utcnow()
        
        if cache_key in self._introspection_cache:
            cache_time = self._introspection_cache_times[cache_key]
            if (now - cache_time).total_seconds() < self.config.introspection_cache_ttl:
                result = self._introspection_cache[cache_key]
                if not result.get('active', False):
                    raise TokenValidationError("Token is not active (revoked)")
                return
        
        # Perform introspection
        try:
            auth = (self.config.client_id, self.config.client_secret)
            data = {'token': token}
            
            response = await self.http_client.post(
                self.config.introspection_endpoint,
                auth=auth,
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            response.raise_for_status()
            
            result = response.json()
            
            # Cache the result
            self._introspection_cache[cache_key] = result
            self._introspection_cache_times[cache_key] = now
            
            # Clean up old cache entries periodically
            await self._cleanup_introspection_cache()
            
            # Check if token is active
            if not result.get('active', False):
                raise TokenValidationError("Token is not active (revoked)")
            
            logger.info("Token introspection successful", extra={"active": True})
            
        except httpx.HTTPError as e:
            logger.error(f"Token introspection failed: {e}")
            raise TokenValidationError(f"Token introspection failed: {str(e)}")
    
    async def _cleanup_introspection_cache(self) -> None:
        """Clean up expired entries from introspection cache."""
        if len(self._introspection_cache) < 1000:  # Only cleanup when cache is large
            return
        
        now = datetime.utcnow()
        expired_keys = [
            key for key, cache_time in self._introspection_cache_times.items()
            if (now - cache_time).total_seconds() > self.config.introspection_cache_ttl
        ]
        
        for key in expired_keys:
            self._introspection_cache.pop(key, None)
            self._introspection_cache_times.pop(key, None)
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired introspection cache entries")
    
    async def close(self) -> None:
        """Clean up resources."""
        await self.http_client.aclose()
        logger.info("Token validator closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
