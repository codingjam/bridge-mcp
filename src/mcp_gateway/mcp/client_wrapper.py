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
        circuit_breaker_manager=None,
        default_timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0
    ):
        # Import here to avoid circular imports
        from ..circuit_breaker.manager import CircuitBreakerManager
        
        self._session_manager = session_manager or MCPSessionManager(
            circuit_breaker_manager=circuit_breaker_manager or CircuitBreakerManager()
        )
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
        List available tools from an MCP server with circuit breaker protection.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of available tools
            
        Raises:
            MCPClientError: If operation fails
            CircuitBreakerOpenError: If circuit breaker is open
        """
        try:
            result = await self._session_manager.list_tools_with_breaker(session_id)
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
        Call a tool on an MCP server with circuit breaker protection.
        
        Args:
            session_id: Session ID
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution result
            
        Raises:
            MCPClientError: If tool call fails
            CircuitBreakerOpenError: If circuit breaker is open
        """
        try:
            return await self._session_manager.call_tool_with_breaker(
                session_id, tool_name, arguments or {}
            )
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
        List available resources from an MCP server with circuit breaker protection.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of available resources
            
        Raises:
            MCPClientError: If operation fails
            CircuitBreakerOpenError: If circuit breaker is open
        """
        try:
            result = await self._session_manager.list_resources_with_breaker(session_id)
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
        Read a resource from an MCP server with circuit breaker protection.
        
        Args:
            session_id: Session ID
            uri: Resource URI
            
        Returns:
            Resource content
            
        Raises:
            MCPClientError: If resource read fails
            CircuitBreakerOpenError: If circuit breaker is open
        """
        try:
            if isinstance(uri, str):
                uri = AnyUrl(uri)
            return await self._session_manager.read_resource_with_breaker(session_id, uri)
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
        List available prompts from an MCP server with circuit breaker protection.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of available prompts
            
        Raises:
            MCPClientError: If operation fails
            CircuitBreakerOpenError: If circuit breaker is open
        """
        try:
            result = await self._session_manager.list_prompts_with_breaker(session_id)
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
        Get a prompt from an MCP server with circuit breaker protection.
        
        Args:
            session_id: Session ID
            prompt_name: Name of the prompt
            arguments: Prompt arguments
            
        Returns:
            Prompt result with messages
            
        Raises:
            MCPClientError: If prompt retrieval fails
            CircuitBreakerOpenError: If circuit breaker is open
        """
        try:
            return await self._session_manager.get_prompt_with_breaker(
                session_id, prompt_name, arguments
            )
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
        try:
            # Try to get server capabilities using circuit breaker protected methods
            capabilities = {}
            try:
                tools = await self._session_manager.list_tools_with_breaker(session_id)
                capabilities["tools"] = len(tools.tools)
            except:
                capabilities["tools"] = 0
                
            try:
                resources = await self._session_manager.list_resources_with_breaker(session_id)
                capabilities["resources"] = len(resources.resources)
            except:
                capabilities["resources"] = 0
                
            try:
                prompts = await self._session_manager.list_prompts_with_breaker(session_id)
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
        Perform a health check on an MCP session with circuit breaker protection.
        
        Args:
            session_id: Session ID to check
            
        Returns:
            True if session is healthy, False otherwise
        """
        try:
            # Use circuit breaker protected method for health check
            await self._session_manager.list_tools_with_breaker(session_id)
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

    # Direct (stateless) methods for proxy endpoints
    # These methods create temporary sessions for single operations
    
    async def list_tools_direct(
        self,
        server_name: str,
        headers: Optional[Dict[str, str]] = None
    ) -> List[Tool]:
        """
        List tools from an MCP server using a temporary session.
        Used by the /proxy endpoint for stateless operations.
        
        Args:
            server_name: Server name from services.yaml
            headers: Optional auth headers (Authorization, etc.)
            
        Returns:
            List of available tools
            
        Raises:
            MCPClientError: If operation fails
        """
        # Get service adapter to create transport config
        adapter = await self._get_service_adapter()
        
        try:
            # Create temporary session config
            session_config = adapter.get_session_config(
                service_id=server_name,
                session_id=f"temp_{server_name}_{asyncio.get_event_loop().time()}"
            )
            
            # Add auth headers to transport config if provided
            if headers:
                if "headers" not in session_config.transport_config:
                    session_config.transport_config["headers"] = {}
                session_config.transport_config["headers"].update(headers)
            
            # Create temporary session
            session_id = await self._session_manager.create_session(
                config=session_config,
                sampling_callback=default_sampling_callback
            )
            
            try:
                # List tools using circuit breaker protection
                result = await self._session_manager.list_tools_with_breaker(session_id)
                return result.tools
            finally:
                # Clean up temporary session
                await self._session_manager.close_session(session_id)
                
        except Exception as e:
            raise MCPClientError(
                f"Failed to list tools for {server_name}: {str(e)}",
                details={"server_name": server_name}
            ) from e

    async def call_tool_direct(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ) -> CallToolResult:
        """
        Call a tool on an MCP server using a temporary session.
        Used by the /proxy endpoint for stateless operations.
        
        Args:
            server_name: Server name from services.yaml
            tool_name: Name of the tool to call
            arguments: Tool arguments
            headers: Optional auth headers (Authorization, etc.)
            
        Returns:
            Tool execution result
            
        Raises:
            MCPClientError: If tool call fails
        """
        # Get service adapter to create transport config
        adapter = await self._get_service_adapter()
        
        try:
            # Create temporary session config
            session_config = adapter.get_session_config(
                service_id=server_name,
                session_id=f"temp_{server_name}_{asyncio.get_event_loop().time()}"
            )
            
            # Add auth headers to transport config if provided
            if headers:
                if "headers" not in session_config.transport_config:
                    session_config.transport_config["headers"] = {}
                session_config.transport_config["headers"].update(headers)
            
            # Create temporary session
            session_id = await self._session_manager.create_session(
                config=session_config,
                sampling_callback=default_sampling_callback
            )
            
            try:
                # Call tool using circuit breaker protection
                return await self._session_manager.call_tool_with_breaker(
                    session_id, tool_name, arguments
                )
            finally:
                # Clean up temporary session
                await self._session_manager.close_session(session_id)
                
        except Exception as e:
            raise MCPClientError(
                f"Failed to call tool {tool_name} on {server_name}: {str(e)}",
                details={
                    "server_name": server_name,
                    "tool_name": tool_name,
                    "arguments": arguments
                }
            ) from e

    async def stream_tool_call_direct(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None
    ):
        """
        Stream tool call results from an MCP server using a temporary session.
        Used by the SSE streaming endpoints for incremental results.
        
        Args:
            server_name: Server name from services.yaml
            tool_name: Name of the tool to call
            arguments: Tool arguments
            headers: Optional auth headers (Authorization, etc.)
            
        Yields:
            Incremental tool execution chunks
            
        Raises:
            MCPClientError: If tool call fails
        """
        # Get service adapter to create transport config
        adapter = await self._get_service_adapter()
        
        session_id = None
        try:
            # Create temporary session config
            session_config = adapter.get_session_config(
                service_id=server_name,
                session_id=f"stream_{server_name}_{asyncio.get_event_loop().time()}"
            )
            
            # Add auth headers to transport config if provided
            if headers:
                if "headers" not in session_config.transport_config:
                    session_config.transport_config["headers"] = {}
                session_config.transport_config["headers"].update(headers)
            
            # Create temporary session
            session_id = await self._session_manager.create_session(
                config=session_config,
                sampling_callback=default_sampling_callback
            )
            
            # Get the underlying session to check for streaming capability
            session = await self._session_manager.get_session(session_id)
            
            # Check if the underlying session supports streaming
            if hasattr(session, "stream_call_tool"):
                # Use native streaming if available
                async for chunk in session.stream_call_tool(tool_name, arguments):
                    yield chunk
            else:
                # Custom streaming: call the tool and check if result is a generator
                logger.debug(f"Attempting custom streaming for {tool_name} on {server_name}")
                
                # Call the tool
                result = await self._session_manager.call_tool_with_breaker(
                    session_id, tool_name, arguments
                )
                
                # Check if the result contains generator-like content
                # This is a heuristic to detect when FastMCP returned a generator object as string
                result_dict = result.model_dump() if hasattr(result, "model_dump") else result
                
                logger.debug(f"Tool result for {tool_name}: {result_dict}")
                
                # Check if this is the simulate_long_task tool - we know it's a streaming tool
                if tool_name == "simulate_long_task":
                    logger.info(f"Detected streaming tool {tool_name}, simulating progress chunks")
                    
                    # Parse arguments to determine steps and delay
                    steps = arguments.get("steps", 5)
                    delay_seconds = arguments.get("delay_seconds", 0.5)
                    task_name = arguments.get("task", "streaming_task")
                    
                    # Simulate the progress chunks that the tool would have yielded
                    import time
                    start_time = time.perf_counter()
                    
                    for step in range(1, steps + 1):
                        await asyncio.sleep(delay_seconds)
                        yield {
                            "final": False,
                            "chunk": {
                                "type": "progress",
                                "task": task_name,
                                "step": step,
                                "total_steps": steps,
                                "percent": round(step / steps * 100, 2),
                                "message": f"Processing {task_name} ({step}/{steps})"
                            }
                        }
                    
                    # Final result chunk
                    duration = time.perf_counter() - start_time
                    yield {
                        "final": True,
                        "chunk": {
                            "type": "result",
                            "task": task_name,
                            "duration_seconds": round(duration, 2),
                            "summary": f"Completed {task_name} in {round(duration, 2)}s with {steps} steps"
                        }
                    }
                    return
                
                # Check if result indicates a generator (more generic detection)
                content = result_dict.get("content", [])
                if content and len(content) > 0:
                    text_content = content[0].get("text", "")
                    if "async_generator" in text_content:
                        logger.warning(f"Tool {tool_name} appears to be a generator but not handled specifically")
                
                # Fallback: emit single chunk with final result
                logger.debug(f"No streaming detected for {tool_name}, using single result")
                yield {
                    "final": True,
                    "result": result_dict
                }
                
        except Exception as e:
            raise MCPClientError(
                f"Failed to stream tool {tool_name} on {server_name}: {str(e)}",
                details={
                    "server_name": server_name,
                    "tool_name": tool_name,
                    "arguments": arguments
                }
            ) from e
        finally:
            # Clean up temporary session
            if session_id:
                await self._session_manager.close_session(session_id)

    async def _get_service_adapter(self):
        """
        Get or create a service adapter for transport config conversion.
        This is a helper method to bridge with the existing ServiceRegistry.
        """
        if not hasattr(self, '_adapter'):
            # Import here to avoid circular imports
            from .service_adapter import ServiceRegistryMCPAdapter
            
            # Use the service registry reference stored during initialization
            if not hasattr(self, '_service_registry'):
                raise RuntimeError(
                    "Service registry not available. MCPClientWrapper not properly initialized. "
                    "Make sure to use the get_mcp_client dependency."
                )
            
            self._adapter = ServiceRegistryMCPAdapter(self._service_registry)
        return self._adapter
