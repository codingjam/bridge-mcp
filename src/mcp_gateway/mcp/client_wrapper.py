"""
MCP Client Wrapper

High-level wrapper around MCP ClientSession providing simplified interface
for MCP operations with error handling, retries, and integration with the
MCP Gateway architecture.
"""

import asyncio
from typing import Optional, Dict, Any, List, Union
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.types import (
    Tool, Resource, Prompt, PromptMessage,
    CallToolResult, GetPromptResult, ReadResourceResult,
    TextContent, ImageContent, EmbeddedResource
)
from pydantic import AnyUrl

from .session_manager import MCPSessionManager, MCPSessionConfig, default_sampling_callback
from .exceptions import MCPClientError, MCPSessionError, MCPConnectionError
from ..core.logging import get_logger


logger = get_logger(__name__)


class MCPClientWrapper:
    """
    High-level wrapper for MCP client operations.
    
    Provides simplified interface for:
    - Tool discovery and execution
    - Resource reading
    - Prompt management
    - Session lifecycle management
    - Error handling and retries
    """
    
    def __init__(
        self,
        session_manager: Optional[MCPSessionManager] = None,
        default_timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        self._session_manager = session_manager or MCPSessionManager()
        self._default_timeout = default_timeout
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._own_session_manager = session_manager is None

    async def __aenter__(self):
        """Async context manager entry."""
        if self._own_session_manager:
            await self._session_manager.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._own_session_manager:
            await self._session_manager.stop()

    async def connect_server(
        self,
        server_name: str,
        transport_config: Dict[str, Any],
        session_id: Optional[str] = None,
        sampling_callback: Optional[callable] = None,
        **kwargs
    ) -> str:
        """
        Connect to an MCP server.
        
        Args:
            server_name: Human-readable server name
            transport_config: Transport configuration dict
            session_id: Optional custom session ID
            sampling_callback: Optional sampling callback function
            **kwargs: Additional session configuration
            
        Returns:
            Session ID for the created connection
            
        Raises:
            MCPConnectionError: If connection fails
        """
        if not session_id:
            session_id = f"{server_name}_{asyncio.get_event_loop().time()}"
        
        config = MCPSessionConfig(
            session_id=session_id,
            server_name=server_name,
            transport_config=transport_config,
            max_retries=kwargs.get('max_retries', self._max_retries),
            retry_delay=kwargs.get('retry_delay', self._retry_delay),
            session_timeout=kwargs.get('session_timeout', 300.0),
            heartbeat_interval=kwargs.get('heartbeat_interval', 30.0),
            auto_reconnect=kwargs.get('auto_reconnect', True)
        )
        
        try:
            return await self._session_manager.create_session(
                config=config,
                sampling_callback=sampling_callback or default_sampling_callback
            )
        except Exception as e:
            raise MCPConnectionError(
                f"Failed to connect to server {server_name}: {str(e)}",
                server_url=transport_config.get('url'),
                transport_type=transport_config.get('type')
            ) from e

    async def disconnect_server(self, session_id: str) -> bool:
        """
        Disconnect from an MCP server.
        
        Args:
            session_id: Session ID to disconnect
            
        Returns:
            True if disconnected successfully, False otherwise
        """
        return await self._session_manager.close_session(session_id)

    async def list_tools(self, session_id: str) -> List[Tool]:
        """
        List available tools from an MCP server.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of available tools
            
        Raises:
            MCPClientError: If operation fails
        """
        session = await self._get_session(session_id)
        try:
            result = await session.list_tools()
            return result.tools
        except Exception as e:
            raise MCPClientError(
                f"Failed to list tools: {str(e)}",
                details={"session_id": session_id}
            ) from e

    async def call_tool(
        self,
        session_id: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> CallToolResult:
        """
        Call a tool on an MCP server.
        
        Args:
            session_id: Session ID
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution result
            
        Raises:
            MCPClientError: If tool call fails
        """
        session = await self._get_session(session_id)
        try:
            result = await session.call_tool(
                name=tool_name,
                arguments=arguments or {}
            )
            return result
        except Exception as e:
            raise MCPClientError(
                f"Failed to call tool {tool_name}: {str(e)}",
                details={
                    "session_id": session_id,
                    "tool_name": tool_name,
                    "arguments": arguments
                }
            ) from e

    async def list_resources(self, session_id: str) -> List[Resource]:
        """
        List available resources from an MCP server.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of available resources
            
        Raises:
            MCPClientError: If operation fails
        """
        session = await self._get_session(session_id)
        try:
            result = await session.list_resources()
            return result.resources
        except Exception as e:
            raise MCPClientError(
                f"Failed to list resources: {str(e)}",
                details={"session_id": session_id}
            ) from e

    async def read_resource(
        self,
        session_id: str,
        uri: Union[str, AnyUrl]
    ) -> ReadResourceResult:
        """
        Read a resource from an MCP server.
        
        Args:
            session_id: Session ID
            uri: Resource URI
            
        Returns:
            Resource content
            
        Raises:
            MCPClientError: If resource read fails
        """
        session = await self._get_session(session_id)
        try:
            if isinstance(uri, str):
                uri = AnyUrl(uri)
            result = await session.read_resource(uri)
            return result
        except Exception as e:
            raise MCPClientError(
                f"Failed to read resource {uri}: {str(e)}",
                details={
                    "session_id": session_id,
                    "uri": str(uri)
                }
            ) from e

    async def list_prompts(self, session_id: str) -> List[Prompt]:
        """
        List available prompts from an MCP server.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of available prompts
            
        Raises:
            MCPClientError: If operation fails
        """
        session = await self._get_session(session_id)
        try:
            result = await session.list_prompts()
            return result.prompts
        except Exception as e:
            raise MCPClientError(
                f"Failed to list prompts: {str(e)}",
                details={"session_id": session_id}
            ) from e

    async def get_prompt(
        self,
        session_id: str,
        prompt_name: str,
        arguments: Optional[Dict[str, str]] = None
    ) -> GetPromptResult:
        """
        Get a prompt from an MCP server.
        
        Args:
            session_id: Session ID
            prompt_name: Name of the prompt
            arguments: Prompt arguments
            
        Returns:
            Prompt result with messages
            
        Raises:
            MCPClientError: If prompt retrieval fails
        """
        session = await self._get_session(session_id)
        try:
            result = await session.get_prompt(
                name=prompt_name,
                arguments=arguments
            )
            return result
        except Exception as e:
            raise MCPClientError(
                f"Failed to get prompt {prompt_name}: {str(e)}",
                details={
                    "session_id": session_id,
                    "prompt_name": prompt_name,
                    "arguments": arguments
                }
            ) from e

    async def get_server_info(self, session_id: str) -> Dict[str, Any]:
        """
        Get information about the connected MCP server.
        
        Args:
            session_id: Session ID
            
        Returns:
            Server information
        """
        session_info = await self._session_manager.get_session_info(session_id)
        if not session_info:
            raise MCPClientError(
                f"Session {session_id} not found",
                details={"session_id": session_id}
            )
        
        # Get capabilities and server details
        session = await self._get_session(session_id)
        try:
            # Try to get server capabilities
            capabilities = {}
            try:
                tools = await session.list_tools()
                capabilities["tools"] = len(tools.tools)
            except:
                capabilities["tools"] = 0
                
            try:
                resources = await session.list_resources()
                capabilities["resources"] = len(resources.resources)
            except:
                capabilities["resources"] = 0
                
            try:
                prompts = await session.list_prompts()
                capabilities["prompts"] = len(prompts.prompts)
            except:
                capabilities["prompts"] = 0
            
            return {
                "session_id": session_id,
                "server_name": session_info.server_name,
                "status": session_info.status,
                "created_at": session_info.created_at.isoformat(),
                "last_activity": session_info.last_activity.isoformat(),
                "connection_count": session_info.connection_count,
                "error_count": session_info.error_count,
                "capabilities": capabilities
            }
        except Exception as e:
            raise MCPClientError(
                f"Failed to get server info: {str(e)}",
                details={"session_id": session_id}
            ) from e

    async def list_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        List all active MCP sessions.
        
        Returns:
            Dictionary of session info by session ID
        """
        sessions = await self._session_manager.list_sessions()
        return {
            session_id: {
                "server_name": info.server_name,
                "status": info.status,
                "created_at": info.created_at.isoformat(),
                "last_activity": info.last_activity.isoformat(),
                "connection_count": info.connection_count,
                "error_count": info.error_count
            }
            for session_id, info in sessions.items()
        }

    async def health_check(self, session_id: str) -> bool:
        """
        Perform a health check on an MCP session.
        
        Args:
            session_id: Session ID to check
            
        Returns:
            True if session is healthy, False otherwise
        """
        try:
            session = await self._get_session(session_id)
            # Simple health check by listing tools
            await session.list_tools()
            return True
        except Exception:
            return False

    async def _get_session(self, session_id: str) -> ClientSession:
        """
        Get a session with error handling.
        
        Args:
            session_id: Session ID
            
        Returns:
            ClientSession instance
            
        Raises:
            MCPSessionError: If session not found or invalid
        """
        session = await self._session_manager.get_session(session_id)
        if not session:
            raise MCPSessionError(
                f"Session {session_id} not found or inactive",
                session_id=session_id,
                operation="get_session"
            )
        return session

    async def _retry_operation(self, operation, *args, **kwargs):
        """
        Retry an operation with exponential backoff.
        
        Args:
            operation: Async function to retry
            *args: Operation arguments
            **kwargs: Operation keyword arguments
            
        Returns:
            Operation result
            
        Raises:
            Exception: If all retries fail
        """
        last_exception = None
        
        for attempt in range(self._max_retries + 1):
            try:
                return await operation(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self._max_retries:
                    delay = self._retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Operation failed (attempt {attempt + 1}/{self._max_retries + 1}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Operation failed after {self._max_retries + 1} attempts")
        
        raise last_exception
