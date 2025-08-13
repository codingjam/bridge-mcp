"""
Enhanced MCP proxy service with authentication support.

This module extends the base proxy service to support authentication
with MCP services using OBO tokens and service-specific configuration.
"""

import logging
from typing import Any, Dict, Optional

from .proxy import MCPProxyService as BaseMCPProxyService
from ..auth.obo_service import OBOTokenService
from mcp_gateway.auth.models import TokenClaims, MCPServiceAuth, AuthStrategy

logger = logging.getLogger(__name__)


class AuthenticatedMCPProxyService(BaseMCPProxyService):
    """
    MCP proxy service with authentication support.
    
    This class extends the base proxy service to handle authentication
    with downstream MCP services using OBO tokens.
    """
    
    def __init__(self, obo_service: Optional[OBOTokenService] = None):
        """
        Initialize the authenticated proxy service.
        
        Args:
            obo_service: Optional OBO service for token exchange
        """
        super().__init__()
        self.obo_service = obo_service
    
    async def forward_authenticated_request(
        self,
        target_url: str,
        method: str,
        path: str,
        headers: Dict[str, str],
        body: Optional[bytes] = None,
        query_params: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        user_token: Optional[str] = None,
        user_claims: Optional[TokenClaims] = None,
        service_auth: Optional[MCPServiceAuth] = None
    ) -> Dict[str, Any]:
        """
        Forward a request to an MCP service with authentication.
        
        This method handles authentication with the target MCP service
        by either using OBO token exchange or passing through the user token.
        
        Args:
            target_url: Target service URL
            method: HTTP method
            path: Request path
            headers: Request headers
            body: Request body
            query_params: Query parameters
            timeout: Request timeout
            user_token: Original user access token
            user_claims: Validated user token claims
            service_auth: Service-specific authentication configuration
            
        Returns:
            Dict: Response data including status, headers, and content
        """
        # Prepare headers for the downstream request
        forwarded_headers = dict(headers)
        
        # Handle authentication if enabled and OBO service is available
        if (service_auth and service_auth.requires_authentication and 
            service_auth.uses_obo and self.obo_service and user_token and user_claims):
            
            try:
                # Get service-specific access token
                service_token = await self.obo_service.get_service_token(
                    user_token=user_token,
                    user_claims=user_claims,
                    service_config=service_auth
                )
                
                # Add authentication header
                forwarded_headers['Authorization'] = f'Bearer {service_token}'
                
                # Add custom headers if configured
                forwarded_headers.update(service_auth.custom_headers)
                
                logger.debug(
                    "Added OBO authentication to MCP service request",
                    extra={
                        "service_id": service_auth.service_id,
                        "user_id": user_claims.sub,
                        "method": method,
                        "path": path,
                        "auth_strategy": service_auth.auth_strategy.value
                    }
                )
                
            except Exception as e:
                logger.error(
                    f"Failed to authenticate request to {service_auth.service_id}: {e}",
                    exc_info=True
                )
                # For OBO_REQUIRED, fail the request. For OBO_PREFERRED, try fallback
                if service_auth.requires_obo_success:
                    raise
                elif service_auth.allows_passthrough and user_token:
                    logger.info(f"OBO failed for {service_auth.service_id}, falling back to passthrough")
                    forwarded_headers['Authorization'] = f'Bearer {user_token}'
                    forwarded_headers.update(service_auth.custom_headers)
                else:
                    raise
        
        elif (user_token and service_auth and service_auth.allows_passthrough):
            # Pass through the original user token
            forwarded_headers['Authorization'] = f'Bearer {user_token}'
            forwarded_headers.update(service_auth.custom_headers)
            
            logger.debug(
                "Using user token passthrough for MCP service",
                extra={
                    "service_id": service_auth.service_id if service_auth else "unknown",
                    "method": method,
                    "path": path,
                    "auth_strategy": service_auth.auth_strategy.value if service_auth else "unknown"
                }
            )
        
        # Remove any problematic headers that shouldn't be forwarded
        headers_to_remove = ['host', 'content-length', 'connection']
        for header in headers_to_remove:
            forwarded_headers.pop(header.lower(), None)
            forwarded_headers.pop(header.title(), None)
        
        # Add gateway identification
        forwarded_headers['X-Forwarded-By'] = 'MCP-Gateway'
        forwarded_headers['X-Gateway-Version'] = '1.0'
        
        # Forward the request using the base proxy service
        return await super().forward_request(
            target_url=target_url,
            method=method,
            path=path,
            headers=forwarded_headers,
            body=body,
            query_params=query_params,
            timeout=timeout
        )
