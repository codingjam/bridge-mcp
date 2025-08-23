"""
MCP Transport Factory

Factory for creating different types of MCP transport connections
(stdio, streamable HTTP, etc.) based on server configuration.
"""

import asyncio
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Tuple, Optional, Dict, Any, Union
from urllib.parse import urlparse

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.auth import OAuthClientProvider
from mcp.shared.auth import OAuthClientMetadata
from pydantic import AnyUrl

from .exceptions import MCPTransportError, MCPConnectionError, MCPAuthenticationError


class MCPTransportFactory:
    """Factory for creating MCP transport connections."""
    
    @staticmethod
    async def create_stdio_transport(
        command: str,
        args: Optional[list[str]] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None
    ) -> AsyncGenerator[Tuple[asyncio.StreamReader, asyncio.StreamWriter], None]:
        """
        Create a stdio transport connection for local MCP servers.
        
        Args:
            command: Command to execute the MCP server
            args: Command line arguments
            env: Environment variables
            cwd: Working directory
            
        Yields:
            Tuple of (reader, writer) streams
            
        Raises:
            MCPTransportError: If stdio connection fails
        """
        try:
            # Merge environment with current environment
            full_env = dict(os.environ)
            if env:
                full_env.update(env)
            
            server_params = StdioServerParameters(
                command=command,
                args=args or [],
                env=full_env,
                cwd=cwd
            )
            
            async with stdio_client(server_params) as (read_stream, write_stream):
                yield read_stream, write_stream
                
        except Exception as e:
            raise MCPTransportError(
                f"Failed to create stdio transport: {str(e)}",
                transport_type="stdio",
                details={
                    "command": command,
                    "args": args,
                    "cwd": cwd
                }
            ) from e

    @staticmethod
    async def create_http_transport(
        url: str,
        auth_provider: Optional[OAuthClientProvider] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None
    ) -> AsyncGenerator[Tuple[asyncio.StreamReader, asyncio.StreamWriter, Any], None]:
        """
        Create a streamable HTTP transport connection.
        
        Args:
            url: MCP server URL
            auth_provider: OAuth authentication provider
            headers: Additional HTTP headers
            timeout: Request timeout in seconds
            
        Yields:
            Tuple of (reader, writer, session_info)
            
        Raises:
            MCPTransportError: If HTTP connection fails
        """
        try:
            # Validate URL
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise MCPTransportError(
                    f"Invalid URL format: {url}",
                    transport_type="streamable_http"
                )
            
            async with streamablehttp_client(
                url=url,
                auth=auth_provider,
                headers=headers,
                timeout=timeout
            ) as (read_stream, write_stream, session_info):
                yield read_stream, write_stream, session_info
                
        except Exception as e:
            if isinstance(e, MCPTransportError):
                raise
            raise MCPTransportError(
                f"Failed to create HTTP transport: {str(e)}",
                transport_type="streamable_http",
                details={
                    "url": url,
                    "headers": headers,
                    "timeout": timeout
                }
            ) from e

    @classmethod
    async def create_authenticated_http_transport(
        cls,
        url: str,
        client_metadata: OAuthClientMetadata,
        auth_server_url: str,
        redirect_handler: Optional[callable] = None,
        callback_handler: Optional[callable] = None,
        token_storage: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None
    ) -> AsyncGenerator[Tuple[asyncio.StreamReader, asyncio.StreamWriter, Any], None]:
        """
        Create an authenticated HTTP transport with OAuth.
        
        Args:
            url: MCP server URL
            client_metadata: OAuth client configuration
            auth_server_url: Authorization server URL
            redirect_handler: Function to handle auth redirects
            callback_handler: Function to handle auth callbacks
            token_storage: Token storage implementation
            headers: Additional HTTP headers
            timeout: Request timeout
            
        Yields:
            Tuple of (reader, writer, session_info)
            
        Raises:
            MCPAuthenticationError: If authentication fails
            MCPTransportError: If transport creation fails
        """
        try:
            auth_provider = OAuthClientProvider(
                server_url=auth_server_url,
                client_metadata=client_metadata,
                storage=token_storage,
                redirect_handler=redirect_handler,
                callback_handler=callback_handler
            )
            
            async with cls.create_http_transport(
                url=url,
                auth_provider=auth_provider,
                headers=headers,
                timeout=timeout
            ) as (read_stream, write_stream, session_info):
                yield read_stream, write_stream, session_info
                
        except Exception as e:
            if isinstance(e, (MCPTransportError, MCPAuthenticationError)):
                raise
            raise MCPAuthenticationError(
                f"Failed to create authenticated transport: {str(e)}",
                auth_method="oauth2",
                details={
                    "url": url,
                    "auth_server_url": auth_server_url
                }
            ) from e

    @classmethod
    @asynccontextmanager
    async def create_transport(
        cls,
        config: Dict[str, Any]
    ) -> AsyncGenerator[Tuple[asyncio.StreamReader, asyncio.StreamWriter, Optional[Any]], None]:
        """
        Create a transport connection based on configuration.
        
        Args:
            config: Transport configuration dictionary
            
        Configuration format:
            {
                "type": "stdio" | "http" | "authenticated_http",
                "command": str (for stdio),
                "args": list[str] (for stdio),
                "env": dict (for stdio),
                "cwd": str (for stdio),
                "url": str (for http/authenticated_http),
                "headers": dict (for http),
                "timeout": float (for http),
                "auth": dict (for authenticated_http)
            }
            
        Yields:
            Tuple of (reader, writer, session_info)
        """
        transport_type = config.get("type", "stdio")
        
        if transport_type == "stdio":
            async with cls.create_stdio_transport(
                command=config["command"],
                args=config.get("args"),
                env=config.get("env"),
                cwd=config.get("cwd")
            ) as (reader, writer):
                yield reader, writer, None
                
        elif transport_type == "http":
            async with cls.create_http_transport(
                url=config["url"],
                headers=config.get("headers"),
                timeout=config.get("timeout")
            ) as (reader, writer, session_info):
                yield reader, writer, session_info
                
        elif transport_type == "authenticated_http":
            auth_config = config.get("auth", {})
            async with cls.create_authenticated_http_transport(
                url=config["url"],
                client_metadata=auth_config["client_metadata"],
                auth_server_url=auth_config["auth_server_url"],
                redirect_handler=auth_config.get("redirect_handler"),
                callback_handler=auth_config.get("callback_handler"),
                token_storage=auth_config.get("token_storage"),
                headers=config.get("headers"),
                timeout=config.get("timeout")
            ) as (reader, writer, session_info):
                yield reader, writer, session_info
                
        else:
            raise MCPTransportError(
                f"Unsupported transport type: {transport_type}",
                transport_type=transport_type
            )
