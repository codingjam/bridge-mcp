"""
OAuth2 On-Behalf-Of (OBO) token service for MCP service authentication.

This module handles the OAuth2 token exchange flow to obtain access tokens
for calling downstream MCP services on behalf of authenticated users.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
import asyncio

import httpx

from .models import AuthConfig, TokenClaims, MCPServiceAuth
from .exceptions import TokenExchangeError, KeycloakConnectionError

logger = logging.getLogger(__name__)


class OBOTokenService:
    """
    On-Behalf-Of token service for secure MCP service access.
    
    This service implements OAuth2 token exchange (RFC 8693) to obtain
    access tokens for calling downstream MCP services. It exchanges
    the user's access token for service-specific tokens with appropriate
    scopes and audience claims.
    """
    
    def __init__(self, auth_config: AuthConfig):
        """
        Initialize the OBO token service.
        
        Args:
            auth_config: Authentication configuration
        """
        self.config = auth_config
        
        # HTTP client for Keycloak communication
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            headers={
                'User-Agent': 'MCP-Gateway-OBO/1.0',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )
        
        # Token cache: (user_token_hash, service_id) -> (token, expiry)
        self._token_cache: Dict[str, Dict[str, tuple]] = {}
        self._cache_lock = asyncio.Lock()
        
        logger.info(
            "OBO token service initialized",
            extra={
                "token_endpoint": self.config.token_endpoint,
                "cache_ttl": self.config.obo_cache_ttl
            }
        )
    
    async def get_service_token(
        self,
        user_token: str,
        user_claims: TokenClaims,
        service_config: MCPServiceAuth
    ) -> str:
        """
        Get an access token for calling a specific MCP service.
        
        This method performs OAuth2 token exchange to obtain a service-specific
        access token that can be used to authenticate with the target MCP service.
        
        Args:
            user_token: The original user access token
            user_claims: Validated claims from the user token
            service_config: Service-specific authentication configuration
            
        Returns:
            str: Access token for the target service
            
        Raises:
            TokenExchangeError: If token exchange fails
        """
        if not self.config.enable_obo:
            logger.debug("OBO disabled, returning original user token")
            return user_token
        
        if service_config.allows_passthrough:
            logger.debug(
                f"Service {service_config.service_id} configured for token passthrough"
            )
            return user_token
        
        # Check cache first
        cache_key = self._get_cache_key(user_token, service_config.service_id)
        cached_token = await self._get_cached_token(cache_key)
        if cached_token:
            logger.debug(f"Using cached OBO token for service {service_config.service_id}")
            return cached_token
        
        # Perform token exchange
        try:
            exchange_token = await self._exchange_token(
                user_token,
                user_claims,
                service_config
            )
            
            # Cache the new token
            await self._cache_token(cache_key, exchange_token)
            
            logger.info(
                "OBO token exchange successful",
                extra={
                    "service_id": service_config.service_id,
                    "user_id": user_claims.sub,
                    "target_audience": service_config.target_audience
                }
            )
            
            return exchange_token
            
        except Exception as e:
            logger.error(
                f"OBO token exchange failed for service {service_config.service_id}: {e}",
                exc_info=True
            )
            raise
    
    async def _exchange_token(
        self,
        user_token: str,
        user_claims: TokenClaims,
        service_config: MCPServiceAuth
    ) -> str:
        """
        Perform the actual OAuth2 token exchange.
        
        This method implements RFC 8693 token exchange to obtain a new
        access token for the target service.
        
        Args:
            user_token: Original user token
            user_claims: User token claims
            service_config: Service configuration
            
        Returns:
            str: New access token for the service
            
        Raises:
            TokenExchangeError: If exchange fails
        """
        try:
            # Prepare token exchange request
            exchange_data = {
                'grant_type': 'urn:ietf:params:oauth:grant-type:token-exchange',
                'subject_token': user_token,
                'subject_token_type': 'urn:ietf:params:oauth:token-type:access_token',
                'requested_token_type': 'urn:ietf:params:oauth:token-type:access_token',
                'client_id': self.config.client_id,
                'client_secret': self.config.client_secret
            }
            
            # Add audience if specified
            if service_config.target_audience:
                exchange_data['audience'] = service_config.target_audience
            
            # Add requested scopes
            if service_config.required_scopes:
                exchange_data['scope'] = ' '.join(service_config.required_scopes)
            
            logger.debug(
                "Performing token exchange",
                extra={
                    "service_id": service_config.service_id,
                    "audience": service_config.target_audience,
                    "scopes": service_config.required_scopes
                }
            )
            
            # Make token exchange request
            response = await self.http_client.post(
                self.config.token_endpoint,
                data=exchange_data
            )
            
            if response.status_code != 200:
                error_detail = await self._parse_error_response(response)
                raise TokenExchangeError(
                    f"Token exchange failed: {error_detail}",
                    error_detail
                )
            
            token_response = response.json()
            
            # Extract access token
            access_token = token_response.get('access_token')
            if not access_token:
                raise TokenExchangeError(
                    "Token exchange response missing access_token",
                    "missing_access_token"
                )
            
            return access_token
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during token exchange: {e}")
            raise KeycloakConnectionError(
                f"Unable to connect to Keycloak for token exchange: {str(e)}",
                str(e)
            )
        except TokenExchangeError:
            # Re-raise our own exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error during token exchange: {e}", exc_info=True)
            raise TokenExchangeError(
                f"Unexpected error during token exchange: {str(e)}",
                str(e)
            )
    
    async def _parse_error_response(self, response: httpx.Response) -> str:
        """
        Parse error response from Keycloak.
        
        Args:
            response: HTTP response from Keycloak
            
        Returns:
            str: Error description
        """
        try:
            error_data = response.json()
            error = error_data.get('error', 'unknown_error')
            error_description = error_data.get('error_description', 'No description provided')
            return f"{error}: {error_description}"
        except Exception:
            return f"HTTP {response.status_code}: {response.text}"
    
    def _get_cache_key(self, user_token: str, service_id: str) -> str:
        """
        Generate cache key for token storage.
        
        Args:
            user_token: User access token
            service_id: Target service ID
            
        Returns:
            str: Cache key
        """
        # Use hash of token to avoid storing sensitive data in cache keys
        token_hash = str(hash(user_token))
        return f"{token_hash}:{service_id}"
    
    async def _get_cached_token(self, cache_key: str) -> Optional[str]:
        """
        Get cached token if still valid.
        
        Args:
            cache_key: Cache key
            
        Returns:
            Optional[str]: Cached token if valid, None otherwise
        """
        async with self._cache_lock:
            if cache_key not in self._token_cache:
                return None
            
            token, expiry = self._token_cache[cache_key]
            
            # Check if token is still valid (with 30 second buffer)
            if datetime.utcnow() + timedelta(seconds=30) > expiry:
                # Token expired or expiring soon, remove from cache
                del self._token_cache[cache_key]
                return None
            
            return token
    
    async def _cache_token(self, cache_key: str, token: str) -> None:
        """
        Cache a token with TTL.
        
        Args:
            cache_key: Cache key
            token: Token to cache
        """
        async with self._cache_lock:
            expiry = datetime.utcnow() + timedelta(seconds=self.config.obo_cache_ttl)
            self._token_cache[cache_key] = (token, expiry)
            
            # Periodic cleanup of expired tokens
            await self._cleanup_expired_tokens()
    
    async def _cleanup_expired_tokens(self) -> None:
        """Clean up expired tokens from cache."""
        if len(self._token_cache) < 100:  # Only cleanup when cache is reasonably large
            return
        
        now = datetime.utcnow()
        expired_keys = [
            key for key, (_, expiry) in self._token_cache.items()
            if now > expiry
        ]
        
        for key in expired_keys:
            del self._token_cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired OBO tokens from cache")
    
    async def invalidate_user_tokens(self, user_token: str) -> None:
        """
        Invalidate all cached tokens for a specific user.
        
        This method should be called when a user logs out or their
        token is revoked to ensure no stale tokens remain in cache.
        
        Args:
            user_token: User token to invalidate
        """
        async with self._cache_lock:
            token_hash = str(hash(user_token))
            keys_to_remove = [
                key for key in self._token_cache.keys()
                if key.startswith(f"{token_hash}:")
            ]
            
            for key in keys_to_remove:
                del self._token_cache[key]
            
            if keys_to_remove:
                logger.info(
                    f"Invalidated {len(keys_to_remove)} cached OBO tokens for user"
                )
    
    async def close(self) -> None:
        """Clean up resources."""
        await self.http_client.aclose()
        async with self._cache_lock:
            self._token_cache.clear()
        logger.debug("OBO token service closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
