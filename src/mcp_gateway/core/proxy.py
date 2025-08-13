"""
MCP Gateway HTTP Proxy Service
Handles request forwarding to backend MCP servers with production-grade error handling
"""
import asyncio
import logging
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import httpx
from fastapi import HTTPException

from mcp_gateway.core.config import get_settings

logger = logging.getLogger(__name__)


class MCPProxyService:
    """Service for proxying requests to MCP servers with connection pooling and resilience"""
    
    def __init__(self):
        self.settings = get_settings()
        self.http_client: Optional[httpx.AsyncClient] = None
        
    async def __aenter__(self):
        """Async context manager entry - initialize HTTP client with connection pooling"""
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=self.settings.connect_timeout,
                read=self.settings.read_timeout,
                write=self.settings.write_timeout,
                pool=self.settings.pool_timeout
            ),
            limits=httpx.Limits(
                max_connections=self.settings.max_connections,
                max_keepalive_connections=self.settings.max_keepalive_connections
            ),
            # Enable HTTP/2 for better performance
            http2=True,
            # Follow redirects with reasonable limit
            follow_redirects=True,
            max_redirects=3
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup HTTP client"""
        if self.http_client:
            await self.http_client.aclose()
    
    async def forward_request(
        self,
        target_url: str,
        method: str,
        path: str,
        headers: Dict[str, str],
        body: Optional[bytes] = None,
        query_params: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Forward HTTP request to target MCP server
        
        Args:
            target_url: Base URL of the target service
            method: HTTP method (GET, POST, etc.)
            path: Request path
            headers: Request headers
            body: Request body (for POST/PUT)
            query_params: Query parameters
            timeout: Request timeout override
            
        Returns:
            Dict containing response data, status code, and headers
            
        Raises:
            HTTPException: If request fails or times out
        """
        if not self.http_client:
            raise RuntimeError("Proxy service not initialized. Use async context manager.")
        
        # Build complete target URL
        full_url = urljoin(target_url.rstrip('/') + '/', path.lstrip('/'))
        
        # Prepare request headers (filter out hop-by-hop headers)
        proxy_headers = self._prepare_headers(headers)
        
        # Add gateway identification header
        proxy_headers["X-MCP-Gateway"] = "mcp-gateway/0.1.0"
        proxy_headers["X-Forwarded-For"] = headers.get("X-Real-IP", "unknown")
        
        # Use provided timeout or default
        request_timeout = timeout or self.settings.default_timeout
        
        try:
            logger.info(
                "Proxying request",
                extra={
                    "method": method,
                    "url": full_url,
                    "headers_count": len(proxy_headers),
                    "body_size": len(body) if body else 0,
                    "timeout": request_timeout
                }
            )
            
            # Forward request to backend MCP server
            response = await self.http_client.request(
                method=method,
                url=full_url,
                headers=proxy_headers,
                content=body,
                params=query_params,
                timeout=request_timeout
            )
            
            # Process response
            response_data = await self._process_response(response)
            
            logger.info(
                "Request forwarded successfully",
                extra={
                    "status_code": response.status_code,
                    "response_size": len(response.content),
                    "content_type": response.headers.get("content-type", "unknown")
                }
            )
            
            return response_data
            
        except httpx.TimeoutException as e:
            logger.error(f"Request timeout: {e}")
            raise HTTPException(
                status_code=504,
                detail=f"Gateway timeout: Request took longer than {request_timeout}s"
            )
        except httpx.ConnectError as e:
            logger.error(f"Connection error: {e}")
            raise HTTPException(
                status_code=502,
                detail="Bad Gateway: Unable to connect to upstream service"
            )
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP error from upstream: {e.response.status_code}")
            # Return the actual error response from upstream
            response_data = await self._process_response(e.response)
            return response_data
        except Exception as e:
            logger.error(f"Unexpected proxy error: {e}", exc_info=True)
            raise HTTPException(
                status_code=502,
                detail="Bad Gateway: Unexpected error occurred"
            )
    
    async def health_check(self, target_url: str, health_path: str = "/health") -> bool:
        """
        Perform health check on a target service
        
        Args:
            target_url: Base URL of the service
            health_path: Health check endpoint path
            
        Returns:
            True if service is healthy, False otherwise
        """
        if not self.http_client:
            return False
        
        try:
            full_url = urljoin(target_url.rstrip('/') + '/', health_path.lstrip('/'))
            
            response = await self.http_client.get(
                full_url,
                timeout=self.settings.health_check_timeout
            )
            
            is_healthy = 200 <= response.status_code < 300
            
            logger.debug(
                f"Health check result: {is_healthy}",
                extra={
                    "url": full_url,
                    "status_code": response.status_code
                }
            )
            
            return is_healthy
            
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False
    
    def _prepare_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        Prepare headers for proxying by filtering out hop-by-hop headers
        
        According to RFC 7230, these headers are connection-specific
        and should not be forwarded by proxies.
        """
        hop_by_hop_headers = {
            'connection', 'keep-alive', 'proxy-authenticate',
            'proxy-authorization', 'te', 'trailers', 'transfer-encoding',
            'upgrade', 'host', 'content-length'
        }
        
        filtered_headers = {
            key: value for key, value in headers.items()
            if key.lower() not in hop_by_hop_headers
        }
        
        # Ensure we have proper content type for JSON requests
        if not any(k.lower() == 'content-type' for k in filtered_headers.keys()):
            if any(k.lower() == 'content-type' for k in headers.keys() 
                   if headers[k].startswith('application/json')):
                filtered_headers['Content-Type'] = 'application/json'
        
        return filtered_headers
    
    async def _process_response(self, response: httpx.Response) -> Dict[str, Any]:
        """
        Process HTTP response and extract relevant data
        
        Args:
            response: HTTP response object
            
        Returns:
            Dictionary containing processed response data
        """
        response_data = {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "content": response.content
        }
        
        # Try to parse JSON response for better handling
        content_type = response.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            try:
                response_data["json"] = response.json()
            except Exception as e:
                logger.warning(f"Failed to parse JSON response: {e}")
                # Keep raw content if JSON parsing fails
        
        return response_data
