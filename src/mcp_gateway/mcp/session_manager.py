"""
MCP Session Manager

Manages MCP client sessions, including lifecycle, connection pooling,
and error recovery.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Optional, Any, AsyncGenerator, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from mcp import ClientSession
from mcp.types import CreateMessageRequestParams, CreateMessageResult

from .transport_factory import MCPTransportFactory
from .exceptions import MCPSessionError, MCPConnectionError
from ..core.logging import get_logger
from ..circuit_breaker import CircuitBreakerManager, CircuitBreakerOpenError


logger = get_logger(__name__)


@dataclass
class MCPSessionConfig:
    """Configuration for MCP session."""
    session_id: str
    server_name: str
    transport_config: Dict[str, Any]
    max_retries: int = 3
    retry_delay: float = 1.0
    session_timeout: float = 300.0  # 5 minutes
    heartbeat_interval: float = 30.0  # 30 seconds
    auto_reconnect: bool = True


@dataclass 
class MCPSessionInfo:
    """Information about an active MCP session."""
    session_id: str
    server_name: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    connection_count: int = 0
    error_count: int = 0
    status: str = "initializing"  # initializing, active, error, closed


class MCPSessionManager:
    """Manages MCP client sessions with connection pooling and error recovery."""
    
    def __init__(self, max_sessions: int = 100, circuit_breaker_manager: Optional[CircuitBreakerManager] = None):
        self._sessions: Dict[str, ClientSession] = {}
        self._session_info: Dict[str, MCPSessionInfo] = {}
        self._session_configs: Dict[str, MCPSessionConfig] = {}
        self._transports: Dict[str, Any] = {}  # Store transport context managers
        self._max_sessions = max_sessions
        self._cleanup_task: Optional[asyncio.Task] = None
        self._heartbeat_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
        
        # Circuit breaker integration for resilient session management
        self.circuit_breaker_manager = circuit_breaker_manager or CircuitBreakerManager()
        
    async def start(self):
        """Start the session manager."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("MCP Session Manager started")

    async def stop(self):
        """Stop the session manager and cleanup all sessions."""
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        
        # Cancel all heartbeat tasks
        for task in self._heartbeat_tasks.values():
            task.cancel()
        
        if self._heartbeat_tasks:
            await asyncio.gather(*self._heartbeat_tasks.values(), return_exceptions=True)
        self._heartbeat_tasks.clear()
        
        # Close all sessions
        async with self._lock:
            for session_id in list(self._sessions.keys()):
                await self._close_session_internal(session_id)
                
        logger.info("MCP Session Manager stopped")

    async def create_session(
        self,
        config: MCPSessionConfig,
        sampling_callback: Optional[callable] = None
    ) -> str:
        """
        Create a new MCP session with circuit breaker protection.
        
        Args:
            config: Session configuration
            sampling_callback: Optional callback for sampling requests
            
        Returns:
            Session ID
            
        Raises:
            MCPSessionError: If session creation fails
            CircuitBreakerOpenError: If circuit breaker is open for this server
        """
        # Check circuit breaker before attempting session creation
        server_key = self._get_server_key(config)
        breaker = await self.circuit_breaker_manager.get_breaker(server_key)
        
        if await breaker.is_open():
            stats = breaker.get_stats()
            raise CircuitBreakerOpenError(
                f"Cannot create session - circuit breaker is open for server: {config.server_name}",
                server_key=server_key,
                cooldown_remaining=stats["cooldown_remaining_seconds"],
                failure_rate=stats["failure_rate"]
            )
        
        async with self._lock:
            if len(self._sessions) >= self._max_sessions:
                raise MCPSessionError(
                    f"Maximum sessions limit ({self._max_sessions}) reached",
                    operation="create_session"
                )
            
            if config.session_id in self._sessions:
                raise MCPSessionError(
                    f"Session {config.session_id} already exists",
                    session_id=config.session_id,
                    operation="create_session"
                )
        
        try:
            logger.info(f"Creating MCP session {config.session_id} for server {config.server_name}")
            logger.debug(f"Transport config: {config.transport_config}")
            
            # Create session info
            session_info = MCPSessionInfo(
                session_id=config.session_id,
                server_name=config.server_name,
                status="initializing"
            )
            
            # Store configuration and info
            self._session_configs[config.session_id] = config
            self._session_info[config.session_id] = session_info
            
            logger.debug(f"Creating transport for session {config.session_id}")
            
            # Use circuit breaker for transport creation
            transport_cm = await self.circuit_breaker_manager.check_and_call(
                server_key,
                self._create_transport_with_breaker,
                config.transport_config
            )
            
            try:
                # Manually enter the transport context to keep it alive
                reader, writer, _ = await transport_cm.__aenter__()
                logger.debug(f"Transport created successfully for session {config.session_id}")
                
                session = ClientSession(
                    read_stream=reader,
                    write_stream=writer,
                    sampling_callback=sampling_callback
                )
                
                logger.debug(f"Entering ClientSession context for session {config.session_id}")
                # Enter the ClientSession context first
                await session.__aenter__()
                
                logger.debug(f"Initializing MCP session {config.session_id}")
                # Initialize the session with timeout and circuit breaker protection
                try:
                    await self.circuit_breaker_manager.check_and_call(
                        server_key,
                        self._initialize_session_with_timeout,
                        session,
                        config.session_id
                    )
                    logger.info(f"MCP session {config.session_id} initialized successfully")
                except asyncio.TimeoutError:
                    logger.error(f"MCP session {config.session_id} initialization timed out after 30 seconds")
                    # Cleanup both session and transport on failure
                    try:
                        await session.__aexit__(None, None, None)
                    finally:
                        await transport_cm.__aexit__(None, None, None)
                    raise MCPSessionError(
                        f"Session initialization timed out for {config.session_id}",
                        session_id=config.session_id,
                        operation="initialize_session"
                    )
                except Exception as init_error:
                    logger.error(f"MCP session {config.session_id} initialization failed: {init_error}")
                    # Cleanup both session and transport on failure
                    try:
                        await session.__aexit__(None, None, None)
                    finally:
                        await transport_cm.__aexit__(None, None, None)
                    raise MCPSessionError(
                        f"Session initialization failed for {config.session_id}: {str(init_error)}",
                        session_id=config.session_id,
                        operation="initialize_session"
                    ) from init_error
                
                async with self._lock:
                    self._sessions[config.session_id] = session
                    session_info.status = "active"
                    session_info.connection_count += 1
                    session_info.last_activity = datetime.utcnow()  # Update activity on successful creation
                    # Store the transport context manager so we can close it later
                    self._transports[config.session_id] = transport_cm
                    
                # Start heartbeat task
                if config.heartbeat_interval > 0:
                    self._heartbeat_tasks[config.session_id] = asyncio.create_task(
                        self._heartbeat_loop(config.session_id)
                    )
                
                logger.info(f"Created MCP session {config.session_id} for server {config.server_name}")
                return config.session_id
                
            except Exception as e:
                # Ensure transport is cleaned up on any failure
                try:
                    await transport_cm.__aexit__(None, None, None)
                except:
                    pass
                raise
                
        except CircuitBreakerOpenError:
            # Don't wrap circuit breaker errors
            await self._cleanup_failed_session(config.session_id)
            raise
        except Exception as e:
            # Cleanup on failure
            await self._cleanup_failed_session(config.session_id)
            raise MCPSessionError(
                f"Failed to create session {config.session_id}: {str(e)}",
                session_id=config.session_id,
                operation="create_session"
            ) from e

    async def get_session(self, session_id: str) -> Optional[ClientSession]:
        """Get an existing session by ID."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if session and session_id in self._session_info:
                self._session_info[session_id].last_activity = datetime.utcnow()
            return session

    async def close_session(self, session_id: str) -> bool:
        """Close a specific session."""
        async with self._lock:
            return await self._close_session_internal(session_id)

    async def list_sessions(self) -> Dict[str, MCPSessionInfo]:
        """List all active sessions."""
        async with self._lock:
            return self._session_info.copy()

    async def get_session_info(self, session_id: str) -> Optional[MCPSessionInfo]:
        """Get information about a specific session."""
        async with self._lock:
            return self._session_info.get(session_id)

    async def _close_session_internal(self, session_id: str) -> bool:
        """Internal method to close a session (must be called with lock held)."""
        if session_id not in self._sessions:
            return False
            
        try:
            # Cancel heartbeat task
            if session_id in self._heartbeat_tasks:
                self._heartbeat_tasks[session_id].cancel()
                del self._heartbeat_tasks[session_id]
            
            # Close session using context manager exit
            session = self._sessions[session_id]
            try:
                await session.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error exiting session context for {session_id}: {e}")
                # Fallback to close() if context exit fails
                if hasattr(session, 'close'):
                    try:
                        await session.close()
                    except Exception:
                        pass
            
            # Close transport context manager
            transport_cm = self._transports.pop(session_id, None)
            if transport_cm:
                try:
                    await transport_cm.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error closing transport for session {session_id}: {e}")
            
            # Remove from tracking
            del self._sessions[session_id]
            if session_id in self._session_info:
                self._session_info[session_id].status = "closed"
                del self._session_info[session_id]
            if session_id in self._session_configs:
                del self._session_configs[session_id]
                
            logger.info(f"Closed MCP session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error closing session {session_id}: {e}")
            return False

    async def _cleanup_failed_session(self, session_id: str):
        """Cleanup a failed session creation."""
        async with self._lock:
            self._session_configs.pop(session_id, None)
            self._session_info.pop(session_id, None)
            # Also clean up any transport that might have been stored
            transport_cm = self._transports.pop(session_id, None)
            if transport_cm:
                try:
                    await transport_cm.__aexit__(None, None, None)
                except Exception:
                    pass
            if session_id in self._heartbeat_tasks:
                self._heartbeat_tasks[session_id].cancel()
                del self._heartbeat_tasks[session_id]

    async def _cleanup_loop(self):
        """Background task to cleanup expired sessions."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_expired_sessions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in session cleanup loop: {e}")

    async def _cleanup_expired_sessions(self):
        """Remove expired sessions."""
        now = datetime.utcnow()
        expired_sessions = []
        
        async with self._lock:
            for session_id, info in self._session_info.items():
                config = self._session_configs.get(session_id)
                if config and now - info.last_activity > timedelta(seconds=config.session_timeout):
                    expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            logger.info(f"Removing expired session {session_id}")
            await self.close_session(session_id)

    async def _heartbeat_loop(self, session_id: str):
        """Heartbeat loop for a specific session with circuit breaker integration."""
        config = self._session_configs.get(session_id)
        if not config:
            return
        
        server_key = self._get_server_key(config)
        
        try:
            while True:
                await asyncio.sleep(config.heartbeat_interval)
                
                # Check if session is still active
                async with self._lock:
                    if session_id not in self._sessions:
                        break
                    
                    session = self._sessions[session_id]
                    info = self._session_info[session_id]
                
                try:
                    # Use circuit breaker for heartbeat operations
                    await self.circuit_breaker_manager.check_and_call(
                        server_key,
                        self._perform_heartbeat,
                        session
                    )
                    
                    async with self._lock:
                        info.last_activity = datetime.utcnow()
                        if info.status == "error":
                            info.status = "active"
                            
                except CircuitBreakerOpenError:
                    logger.error(f"Circuit breaker open for {server_key}, closing session {session_id}")
                    await self.close_session(session_id)
                    break
                except Exception as e:
                    logger.warning(f"Heartbeat failed for session {session_id}: {e}")
                    async with self._lock:
                        info.error_count += 1
                        info.status = "error"
                        
                    # Consider closing session if too many errors
                    if info.error_count >= 3:
                        logger.error(f"Too many heartbeat errors for session {session_id}, closing")
                        await self.close_session(session_id)
                        break
                        
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in heartbeat loop for session {session_id}: {e}")

    async def _create_transport_with_breaker(self, transport_config: Dict[str, Any]):
        """Create transport with circuit breaker protection."""
        return MCPTransportFactory.create_transport(transport_config)
    
    async def _initialize_session_with_timeout(self, session: ClientSession, session_id: str):
        """Initialize session with timeout protection."""
        await asyncio.wait_for(session.initialize(), timeout=30.0)
    
    async def _perform_heartbeat(self, session: ClientSession):
        """Perform heartbeat operation (list tools as lightweight check)."""
        await session.list_tools()
    
    def _get_server_key(self, config: MCPSessionConfig) -> str:
        """Generate a unique key for server identification in circuit breaker."""
        # Use server name as the key for circuit breaker grouping
        return config.server_name

    async def call_tool_with_breaker(
        self,
        session_id: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """
        Call a tool with circuit breaker protection.
        
        Args:
            session_id: Session identifier
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution result
            
        Raises:
            MCPSessionError: If session not found
            CircuitBreakerOpenError: If circuit breaker is open
        """
        session_info = self._session_info.get(session_id)
        if not session_info:
            raise MCPSessionError(
                f"Session {session_id} not found",
                session_id=session_id,
                operation="call_tool"
            )
        
        config = self._session_configs.get(session_id)
        if not config:
            raise MCPSessionError(
                f"Session configuration not found for {session_id}",
                session_id=session_id,
                operation="call_tool"
            )
        
        server_key = self._get_server_key(config)
        session = self._sessions[session_id]
        
        # Use circuit breaker manager's check_and_call for tool execution
        return await self.circuit_breaker_manager.check_and_call(
            server_key,
            self._call_tool_internal,
            session,
            tool_name,
            arguments
        )
    
    async def _call_tool_internal(
        self,
        session: ClientSession,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """Internal method for calling tools on MCP session."""
        result = await session.call_tool(tool_name, arguments)
        return result

    async def list_tools_with_breaker(self, session_id: str):
        """List tools with circuit breaker protection."""
        session_info = self._session_info.get(session_id)
        if not session_info:
            raise MCPSessionError(
                f"Session {session_id} not found",
                session_id=session_id,
                operation="list_tools"
            )
        
        config = self._session_configs.get(session_id)
        if not config:
            raise MCPSessionError(
                f"Session configuration not found for {session_id}",
                session_id=session_id,
                operation="list_tools"
            )
        
        server_key = self._get_server_key(config)
        session = self._sessions[session_id]
        
        return await self.circuit_breaker_manager.check_and_call(
            server_key,
            session.list_tools
        )

    async def list_resources_with_breaker(self, session_id: str):
        """List resources with circuit breaker protection."""
        session_info = self._session_info.get(session_id)
        if not session_info:
            raise MCPSessionError(
                f"Session {session_id} not found",
                session_id=session_id,
                operation="list_resources"
            )
        
        config = self._session_configs.get(session_id)
        if not config:
            raise MCPSessionError(
                f"Session configuration not found for {session_id}",
                session_id=session_id,
                operation="list_resources"
            )
        
        server_key = self._get_server_key(config)
        session = self._sessions[session_id]
        
        return await self.circuit_breaker_manager.check_and_call(
            server_key,
            session.list_resources
        )

    async def read_resource_with_breaker(self, session_id: str, uri):
        """Read resource with circuit breaker protection."""
        session_info = self._session_info.get(session_id)
        if not session_info:
            raise MCPSessionError(
                f"Session {session_id} not found",
                session_id=session_id,
                operation="read_resource"
            )
        
        config = self._session_configs.get(session_id)
        if not config:
            raise MCPSessionError(
                f"Session configuration not found for {session_id}",
                session_id=session_id,
                operation="read_resource"
            )
        
        server_key = self._get_server_key(config)
        session = self._sessions[session_id]
        
        return await self.circuit_breaker_manager.check_and_call(
            server_key,
            session.read_resource,
            uri
        )

    async def list_prompts_with_breaker(self, session_id: str):
        """List prompts with circuit breaker protection."""
        session_info = self._session_info.get(session_id)
        if not session_info:
            raise MCPSessionError(
                f"Session {session_id} not found",
                session_id=session_id,
                operation="list_prompts"
            )
        
        config = self._session_configs.get(session_id)
        if not config:
            raise MCPSessionError(
                f"Session configuration not found for {session_id}",
                session_id=session_id,
                operation="list_prompts"
            )
        
        server_key = self._get_server_key(config)
        session = self._sessions[session_id]
        
        return await self.circuit_breaker_manager.check_and_call(
            server_key,
            session.list_prompts
        )

    async def get_prompt_with_breaker(self, session_id: str, prompt_name: str, arguments: Optional[Dict[str, str]] = None):
        """Get prompt with circuit breaker protection."""
        session_info = self._session_info.get(session_id)
        if not session_info:
            raise MCPSessionError(
                f"Session {session_id} not found",
                session_id=session_id,
                operation="get_prompt"
            )
        
        config = self._session_configs.get(session_id)
        if not config:
            raise MCPSessionError(
                f"Session configuration not found for {session_id}",
                session_id=session_id,
                operation="get_prompt"
            )
        
        server_key = self._get_server_key(config)
        session = self._sessions[session_id]
        
        return await self.circuit_breaker_manager.check_and_call(
            server_key,
            session.get_prompt,
            name=prompt_name,
            arguments=arguments
        )

    async def get_circuit_breaker_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics for monitoring."""
        return await self.circuit_breaker_manager.get_manager_stats()


# Sampling callback helper function
async def default_sampling_callback(
    context: Any,
    params: CreateMessageRequestParams
) -> CreateMessageResult:
    """Default sampling callback that returns a simple response."""
    from mcp.types import TextContent
    
    return CreateMessageResult(
        role="assistant",
        content=TextContent(
            type="text",
            text="This is a default response from the MCP Gateway. "
                 "Configure a proper sampling callback for your use case."
        ),
        model="mcp-gateway",
        stopReason="endTurn"
    )
