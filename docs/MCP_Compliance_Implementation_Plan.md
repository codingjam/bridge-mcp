# MCP Gateway Complia### Critical MCP Spec Compliance Issues ❌

1. **No MCP Client Integration**: Current HTTP proxy doesn't use MCP protocol - need to integrate Python MCP client SDK
2. **No Session Management**: Gateway treats each request independently - missing MCP session tracking and reuse
3. **Missing Initialize Handshake**: No implementation of required MCP initialize/initialized flow
4. **No Streamable HTTP Support**: Not using MCP's streamable HTTP transport (single /mcp endpoint with optional SSE responses)
5. **Missing MCP Headers**: Not handling `Mcp-Session-Id` or `MCP-Protocol-Version`
6. **No Session-Based Retries**: Missing retry logic for session expiry scenarios
7. **No Concurrency Safety**: Potential race conditions in session creation

**Note**: The legacy HTTP+SSE transport (two-endpoint model) is deprecated as of 2024-11-05. The replacement is Streamable HTTP (2025-03-26), which uses a single `/mcp` endpoint that can return JSON or SSE responses as needed.mentation Plan

**Date**: August 19, 2025  
**Repository**: bridge-mcp  
**Branch**: feature/rate-limiter  
**Status**: Planning Phase

## Executive Summary

This document outlines the implementation plan to bring the MCP Gateway into full compliance with the Model Context Protocol (MCP) specification. Instead of implementing MCP protocol details from scratch, we will leverage an existing Python MCP client SDK to handle protocol compliance while building gateway-specific features like OBO authentication, session reuse, and multi-client request proxying on top of it.

## Current State Analysis

### What's Working Well ✅
- **Basic HTTP Proxy**: `MCPProxyService` provides solid foundation with connection pooling
- **Authentication Layer**: `AuthenticatedMCPProxyService` handles OBO tokens properly
- **Header Filtering**: Basic hop-by-hop header filtering is implemented
- **Error Handling**: Good timeout and connection error handling
- **Structured Logging**: JSON logging with proper context
- **Rate Limiting**: Comprehensive rate limiting system in place

### Critical MCP Spec Compliance Issues ❌

1. **No MCP Client Integration**: Current HTTP proxy doesn't use MCP protocol - need to integrate Python MCP client SDK
2. **No Session Management**: Gateway treats each request independently - missing MCP session tracking and reuse
3. **Missing Initialize Handshake**: No implementation of required MCP initialize/initialized flow
4. **No Streamable HTTP Support**: Not using MCP's streamable HTTP transport (deprecated legacy HTTP+SSE transport as of 2025-03-26)
5. **Missing MCP Headers**: Not handling `Mcp-Session-Id` or `MCP-Protocol-Version`
6. **No Session-Based Retries**: Missing retry logic for session expiry scenarios
7. **No Concurrency Safety**: Potential race conditions in session creation

## Implementation Plan

### Phase 0: MCP Client SDK Integration 🔧
**Priority**: CRITICAL - Foundation for all MCP compliance  
**Estimated Effort**: 1-2 days

#### MCP Client Library Options:
- **`mcp` package**: Official Python MCP client (if available)
- **`model-context-protocol`**: Alternative Python implementation
- **Custom wrapper**: Around existing MCP libraries

#### Integration Strategy:
```python
# Use async context managers for SDK transport + session
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from pydantic import AnyUrl

class MCPClientWrapper:
    def __init__(self, server_url: str, auth_token: str = None):
        self.server_url = server_url
        self.auth_token = auth_token
        self.session: ClientSession = None
        self.transport_context = None
        self.session_context = None
    
    async def initialize_session(self) -> MCPSession:
        """Use async context managers for SDK transport + session"""
        headers = {"Authorization": f"Bearer {self.auth_token}"} if self.auth_token else {}
        
        # Open transport as async context manager (yields 3 values)
        self.transport_context = streamablehttp_client(
            AnyUrl(self.server_url), 
            extra_headers=headers
        )
        read, write, _meta = await self.transport_context.__aenter__()
        
        # Open ClientSession as async context manager
        self.session_context = ClientSession(read, write)
        session = await self.session_context.__aenter__()
        
        # Perform initialize → initialized handshake
        init_result = await session.initialize()
        await session.initialized()  # 202 empty response
        
        return MCPSession.from_sdk_result(init_result, session, self)
    
    async def close(self):
        """Cleanup SDK session and transport via context managers"""
        if self.session_context:
            await self.session_context.__aexit__(None, None, None)
        if self.transport_context:
            await self.transport_context.__aexit__(None, None, None)
```

#### Dependencies to Add:
```toml
# pyproject.toml
[dependencies]
mcp = "^1.0.0"  # Official Python MCP SDK
```

### Phase 1: MCP Session Management 🏗️
**Priority**: HIGH - Critical for MCP compliance  
**Estimated Effort**: 3-4 days

#### New Components Needed:
```
src/mcp_gateway/session/
├── __init__.py
├── manager.py          # MCPSessionManager class
├── models.py           # MCPSession dataclass
├── storage.py          # Session storage with TTL
└── client_wrapper.py   # MCP client integration wrapper
```

#### Key Features:
- **MCP Client Integration**: Wrap Python MCP client with gateway-specific logic
- **Per-Client Session Storage**: Store MCP client instances and session data per downstream client
- **Session TTL Management**: Automatic cleanup of expired sessions and MCP client connections
- **Thread-Safe Operations**: Concurrent request handling for same client
- **Session Invalidation**: Clear sessions on auth failures or protocol errors

#### Implementation Details:
```python
# Simplified session model - let SDK manage MCP headers
@dataclass
class MCPSession:
    client_id: str
    server_url: str
    session: ClientSession  # Actual MCP ClientSession instance
    wrapper: MCPClientWrapper  # Holds context managers
    created_at: datetime
    expires_at: datetime
    last_used: datetime
    
    async def list_tools(self):
        """Use typed SDK methods"""
        self.last_used = datetime.utcnow()
        return await self.session.list_tools()
    
    async def call_tool(self, name: str, args: dict):
        """Use typed SDK methods"""
        self.last_used = datetime.utcnow() 
        return await self.session.call_tool(name, args)
    
    async def call_tool_stream(self, name: str, args: dict):
        """Streaming tool calls"""
        self.last_used = datetime.utcnow()
        return self.session.call_tool_stream(name, args)
    
    async def close(self):
        """Central eviction path with proper context cleanup"""
        if self.wrapper:
            await self.wrapper.close()
    
# Session manager with SDK integration and per-audience locks
class MCPSessionManager:
    def __init__(self):
        self._sessions: Dict[str, MCPSession] = {}
        self._init_locks: Dict[str, asyncio.Lock] = {}
        self._refresh_locks: Dict[str, asyncio.Lock] = {}  # Per-audience refresh locks
    
    def _get_session_key(self, client_id: str, server_url: str) -> str:
        """Key sessions by (user_id, server_url)"""
        return f"{client_id}:{server_url}"
    
    def _get_audience_key(self, server_url: str) -> str:
        """Extract audience for token management"""
        return server_url  # Could extract domain if needed
    
    async def get_or_create_session(
        self, client_id: str, server_url: str, auth_token: str = None
    ) -> MCPSession:
        """Get existing session or create new one with proper locking"""
        session_key = self._get_session_key(client_id, server_url)
        
        # Short-circuit if session exists and valid
        if session_key in self._sessions:
            session = self._sessions[session_key]
            if session.expires_at > datetime.utcnow():
                return session
        
        # Acquire per-client init lock
        async with self._get_init_lock(session_key):
            # Double-check after acquiring lock
            if session_key in self._sessions:
                session = self._sessions[session_key]
                if session.expires_at > datetime.utcnow():
                    return session
            
            # Create new session
            wrapper = MCPClientWrapper(server_url, auth_token)
            session = await wrapper.initialize_session()
            self._sessions[session_key] = session
            return session
    
    async def invalidate_session(self, client_id: str, server_url: str) -> None:
        """Invalidate and cleanup session"""
        session_key = self._get_session_key(client_id, server_url)
        if session_key in self._sessions:
            session = self._sessions.pop(session_key)
            await session.close()
    
    async def refresh_token_and_reinit(self, client_id: str, server_url: str):
        """Per-audience refresh lock to prevent thundering herd"""
        audience_key = self._get_audience_key(server_url)
        
        async with self._get_refresh_lock(audience_key):
            # Check if another thread already refreshed
            if self._token_cache.is_fresh(audience_key):
                return await self.get_or_create_session(client_id, server_url)
            
            # Refresh token and only invalidate sessions for this (user, server)
            new_token = await self._obo_service.refresh_token(audience_key)
            await self.invalidate_session(client_id, server_url)
            return await self.get_or_create_session(client_id, server_url, new_token)
```

### Phase 2: Initialize Handshake Implementation 🤝
**Priority**: HIGH - Required MCP protocol flow  
**Estimated Effort**: 2-3 days

#### Required MCP Initialize Flow:
1. **Detect New Client**: First request from unknown client triggers initialization
2. **Create Transport**: Use `streamablehttp_client()` with server URL and auth headers
3. **Initialize Session**: Create `ClientSession` and call `session.initialize()` → `session.initialized()`
4. **Store Session**: Cache the ClientSession instance and session metadata per downstream client
5. **Forward Original Request**: Continue with original client request using established MCP session

#### Handshake Response Semantics:
- `initialize()` → **200 + JSON** (returns server capabilities and info)
- `notifications/initialized` → **202 + empty** (notification acknowledgment)
- All other methods (`list_tools`, `call_tool`) → **200 + JSON** or **200 + SSE**

#### Components to Modify:
- `src/mcp_gateway/core/authenticated_proxy.py` - Add session-aware request handling
- `src/mcp_gateway/api/routes.py` - Integrate session management
- `src/mcp_gateway/core/proxy.py` - Support initialize handshake

#### Error Scenarios:
- Initialize timeout → Return error to client
- Server rejects initialize → Log and return appropriate error
- MCP client connection failure → Session creation failure
- Auth token issues → Retry with fresh token via OBO service

### Phase 3: Streamable HTTP Response Support 🌊
**Priority**: HIGH - Required for MCP protocol version 2025-03-26+  
**Estimated Effort**: 2-3 days

#### MCP Streamable HTTP Transport Overview:
- **Single Endpoint**: All requests go to `/mcp` endpoint (POST for requests, optional GET for server-push)
- **Response Modes**: Server can return `application/json` or `text/event-stream` based on request type
- **GET Behavior**: Optional server-initiated notifications/events via SSE; return 405 if not supported
- **Accept Header**: Clients must include `Accept: application/json, text/event-stream` on all requests

#### Current Problem:
```python
# Current: Buffers entire response
response_content = await response.read()
return web.Response(body=response_content, ...)
```

#### Target Implementation:
```python
# Streamable HTTP via SDK with proper response streaming
from fastapi import Response
from starlette.responses import StreamingResponse
import json
import asyncio
import time

async def streamable_call_tool(session: MCPSession, tool_name: str, args: dict, correlation_id: str):
    """Handle streamable tool calls with client disconnect handling"""
    
    async def stream_generator():
        last_activity = time.time()  # Track idle time for timeout
        chunk_count = 0
        first_byte_sent = False
        start_time = time.time()
        
        try:
            # SDK yields responses as async iterator (streamable HTTP with SSE format per spec)
            async for response_chunk in session.call_tool_streamable(tool_name, args):
                current_time = time.time()
                last_activity = current_time  # Reset idle timer
                
                # Track first byte latency
                if not first_byte_sent:
                    first_byte_latency = (current_time - start_time) * 1000
                    logger.info("mcp_streaming_first_byte", latency_ms=first_byte_latency, correlation_id=correlation_id)
                    first_byte_sent = True
                
                # Size guard - cap response chunk size to prevent memory spikes
                chunk_data = json.dumps(response_chunk)
                if len(chunk_data) > session.config.max_event_size:
                    logger.warning("mcp_chunk_size_capped", original_size=len(chunk_data), 
                                 capped_size=session.config.max_event_size, correlation_id=correlation_id)
                    # Truncate and mark as capped
                    chunk_data = chunk_data[:session.config.max_event_size] + '...'
                    yield f"data: {chunk_data}\n\n"
                    yield f"data: {json.dumps({'error': 'Response chunk truncated due to size limit'})}\n\n"
                else:
                    # Handle large chunks - split if needed (secondary chunking)
                    if len(chunk_data) > session.config.stream_buffer_size:
                        for i in range(0, len(chunk_data), session.config.stream_buffer_size):
                            chunk = chunk_data[i:i + session.config.stream_buffer_size]
                            yield f"data: {chunk}\n\n"
                            chunk_count += 1
                    else:
                        yield f"data: {chunk_data}\n\n"
                        chunk_count += 1
                
                # Check for idle timeout - proactively close abandoned streams
                if (current_time - last_activity) * 1000 > session.config.stream_idle_timeout_ms:
                    idle_duration = (current_time - last_activity) * 1000
                    logger.warning("mcp_stream_idle_timeout", client_hash=hashlib.sha256(f"{session.client_id}:{session.server_url}".encode()).hexdigest()[:8], 
                                 idle_duration_ms=idle_duration)
                    break
        
        except asyncio.CancelledError:
            # Client disconnected
            client_hash = hashlib.sha256(f"{session.client_id}:{session.server_url}".encode()).hexdigest()[:8]
            logger.warning("mcp_client_disconnect", tool_name=tool_name, client_hash=client_hash, 
                         reason="cancelled_error", chunks_sent=chunk_count)
            raise
        except Exception as e:
            # Other streaming errors
            logger.error("mcp_streaming_error", error=str(e), correlation_id=correlation_id)
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
            raise
    
    return StreamingResponse(
        stream_generator(), 
        media_type="text/event-stream",  # SSE format per MCP spec for streaming responses
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable proxy buffering
        }
    )

async def handle_mcp_get_request(session: MCPSession):
    """Handle optional GET requests for server-initiated notifications/events per MCP spec"""
    # GET in Streamable HTTP is optional - used for long-lived notifications or server-initiated events
    if not session.config.enable_server_push:
        # Return 405 Method Not Allowed if server-push not supported
        raise HTTPException(status_code=405, detail="GET method not supported - no server-initiated events")
    
    # TODO: Implement server-initiated SSE stream for notifications
    async def server_push_generator():
        # Server can send notifications/requests to client via SSE
        while True:
            # Wait for server-initiated events (placeholder implementation)
            await asyncio.sleep(30)  # Replace with actual event waiting
            yield f"data: {json.dumps({'type': 'ping', 'timestamp': time.time()})}\n\n"
    
    return StreamingResponse(
        server_push_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

async def proxy_mcp_request(session: MCPSession, tool_name: str, args: dict, correlation_id: str):
    """Route to streamable or non-streamable with partial stream protection and size guards"""
    
    # Size guard for request JSON
    request_size = len(json.dumps(args))
    if request_size > session.config.max_request_json_size:
        logger.warning("mcp_request_size_rejected", size=request_size, limit=session.config.max_request_json_size)
        raise HTTPException(status_code=413, detail=f"Request JSON too large: {request_size} bytes")
    
    # Check if we already sent partial output (prevent retries)
    if hasattr(session, '_partial_stream_sent') and session._partial_stream_sent:
        logger.warning("mcp_retry_blocked", reason="partial_stream_sent", correlation_id=correlation_id)
        raise HTTPException(status_code=409, detail="Cannot retry after partial stream output")
    
    # Check if tool supports streamable responses
    tools = await session.list_tools()
    tool_def = next((t for t in tools if t.name == tool_name), None)
    
    if tool_def and getattr(tool_def, 'supports_streamable', False):
        session._partial_stream_sent = True  # Mark to prevent retries
        return await streamable_call_tool(session, tool_name, args, correlation_id)
    else:
        # Non-streamable call
        result = await session.call_tool(tool_name, args)
        return JSONResponse(result)
```

#### Alternative for Callback-Based SDKs:
```python
# If SDK uses callbacks instead of async iterator for streamable responses
import asyncio
from typing import AsyncGenerator

async def callback_to_async_generator(session: MCPSession, tool_name: str, args: dict) -> AsyncGenerator[dict, None]:
    """Convert callback-based streamable responses to async generator"""
    queue = asyncio.Queue()
    
    def on_response_chunk(chunk):
        queue.put_nowait(chunk)
    
    def on_complete():
        queue.put_nowait(None)  # Sentinel for completion
    
    # Start streamable call with callbacks
    await session.call_tool_streamable_callback(tool_name, args, on_response_chunk, on_complete)
    
    # Yield from queue until completion
    while True:
        chunk = await queue.get()
        if chunk is None:  # Completion sentinel
            break
        yield chunk
```

#### Changes Needed:
- **SDK Streamable Integration**: Use async generators that iterate over SDK-emitted response chunks
- **Prompt Flushing**: Ensure real-time streaming with immediate chunk forwarding
- **FastAPI Integration**: Return `StreamingResponse` with proper SSE headers for streaming, JSON for non-streaming
- **Connection Management**: Handle client disconnections and dead stream detection
- **Accept Header**: Include `Accept: application/json, text/event-stream` on POST requests per spec
- **GET Support**: Optional SSE stream via GET to same /mcp endpoint (or return 405 if not supported)

#### Modified Files:
- `src/mcp_gateway/core/proxy.py` - Replace `_process_response` with streamable logic
- `src/mcp_gateway/api/routes.py` - Return `StreamingResponse` for streamable content, JSONResponse for non-streaming
- `src/mcp_gateway/api/routes.py` - Add GET /mcp endpoint for optional SSE push (or return 405)

### Phase 4: MCP-Compliant Header Management 📋
**Priority**: MEDIUM - Protocol compliance  
**Estimated Effort**: 1-2 days

#### SDK Header Management:
- **SDK Handles MCP Headers**: After init, SDK automatically manages `Mcp-Session-Id`, `MCP-Protocol-Version`
- **Transport-Level Auth**: Set `Authorization` header when creating transport via `streamablehttp_client()`
- **Accept Header**: Include `Accept: application/json, text/event-stream` on POST requests per spec
- **Gateway Headers Only**: Focus on headers for fallback raw HTTP calls, not SDK-managed requests

#### Required Headers for Transport Creation:
```python
# Set headers once when opening transport - DO NOT set MCP headers manually
headers = {
    "Authorization": f"Bearer {auth_token}",  # OBO token
    "User-Agent": "MCP Gateway/1.0.0",       # Optional
    "Accept": "application/json, text/event-stream"  # Required per spec
}
# DO NOT manually set Mcp-Session-Id or MCP-Protocol-Version - SDK handles these
read, write, _meta = await streamablehttp_client(AnyUrl(server_url), extra_headers=headers).__aenter__()
```

#### Fallback HTTP Requirements:
- **MCP-Protocol-Version**: Include on all subsequent requests when not using SDK
- **Authorization**: Always include Bearer token per auth section
- **Accept**: Must include both JSON and SSE support per spec

#### Scope of Phase 4:
- **Fallback HTTP Requests**: Headers for non-SDK calls (health checks, etc.)
- **Client Request Headers**: Preserve and forward appropriate headers from downstream clients  
- **Response Header Cleanup**: Strip hop-by-hop headers from responses

#### Modified Components:
- `src/mcp_gateway/core/proxy.py` - Enhance header handling for fallback HTTP calls
- `src/mcp_gateway/session/client_wrapper.py` - Set transport headers during session creation

### Phase 5: Retry Logic & Error Recovery 🔄
**Priority**: MEDIUM - Robustness improvement  
**Estimated Effort**: 2 days

#### Retry Scenarios by Category:
```
401/403 Response → Re-exchange OBO token → Re-init session → Retry once
"Invalid/Missing Session" → Re-init only (keep token) → Retry once  
Network/Timeout Errors → Exponential backoff with jitter → Retry 2-3 times
Server Unavailable → Exponential backoff → Retry 2-3 times
```

#### Granular Retry Policy:
- **Auth Failures (401/403)**: Evict only the (user_id, audience) token and re-exchange - max 1 retry
- **Session Errors**: Keep existing token, just re-initialize MCP session - max 1 retry
- **Network Issues**: Implement backoff with jitter, limit attempts - max 2-3 retries
- **Avoid Blind Retries**: Record specific failure category in logs/metrics
- **Token Scope**: Don't tear down all sessions for server unless IdP forces it

#### Session Recovery Flow:
1. **Detect Retry Condition**: Categorize error (auth vs session vs network)
2. **Conditional Token Refresh**: Only refresh OBO token on 401/403 errors
3. **Invalidate Current Session**: Clear from session storage and close transport
4. **Re-initialize**: Create new transport and ClientSession with (possibly) fresh token
5. **Retry Original Request**: With new MCP session, log retry reason
6. **Fail if Retry Fails**: Return error to client with retry context

#### Implementation:
- Add retry logic to `AuthenticatedMCPProxyService.forward_authenticated_request`
- Implement exponential backoff with jitter for network failures
- Session invalidation integration with retry mechanism  
- OBO token cache eviction on auth failures only
- Comprehensive retry reason logging and metrics

### Phase 6: Concurrency & Race Condition Prevention 🔒
**Priority**: MEDIUM - Stability improvement  
**Estimated Effort**: 1-2 days

#### Race Condition Scenarios:
- **Multiple Initialize**: Concurrent requests from same client triggering multiple session creations
- **Session Creation**: Multiple threads creating MCP sessions simultaneously  
- **Session Cleanup**: Cleanup running while MCP session being accessed
- **Token Refresh**: Multiple requests triggering concurrent OBO token refresh
- **Transport Lifecycle**: Concurrent access to transport during re-initialization

#### Synchronization Strategy:
```python
# Per-audience refresh locks to avoid blocking unrelated tenants
class MCPSessionManager:
    def __init__(self):
        self._sessions: Dict[str, MCPSession] = {}
        self._init_locks: Dict[str, asyncio.Lock] = {}
        self._refresh_locks: Dict[str, asyncio.Lock] = {}  # Per-audience locks
    
    async def get_or_create_session(self, client_id: str, server_url: str):
        session_key = f"{client_id}:{server_url}"
        
        # Per-client init lock prevents multiple session creation
        async with self._get_init_lock(session_key):
            # Double-check pattern
            if self._has_valid_session(session_key):
                return self._sessions[session_key]
            return await self._create_new_session(session_key, server_url)
    
    async def refresh_token_and_reinit(self, client_id: str, server_url: str):
        audience_key = self._get_audience_key(server_url)
        
        # Per-audience refresh lock prevents thundering herd per server
        async with self._get_refresh_lock(audience_key):
            # Check if another thread already refreshed for this audience
            if self._token_cache.is_fresh(audience_key):
                return await self.get_or_create_session(client_id, server_url)
            
            # Refresh token and invalidate only this (user, server) session
            new_token = await self._obo_service.refresh_token(audience_key)
            await self.invalidate_session(client_id, server_url)  # Not all sessions
            return await self.get_or_create_session(client_id, server_url, new_token)
```

#### Thread Safety Measures:
- **Per-Client Init Locks**: Prevent concurrent session creation for same (client, server)
- **Per-Audience Refresh Locks**: Prevent thundering herd per server without blocking unrelated tenants
- **Session Access Safety**: Thread-safe session storage and cleanup
- **Context Manager Cleanup**: Proper __aexit__ calls for transport and session contexts
- **Horizontal Scaling**: Consider Redis for locks + session map if scaling across instances

### Phase 7: Enhanced Observability 📊
**Priority**: LOW - Monitoring and debugging  
**Estimated Effort**: 1 day

#### New Logging Events:
```python
# Startup logging with SDK version and protocol negotiation
logger.info("mcp_gateway_startup", mcp_sdk_version=mcp.__version__, pinned_version=config.mcp_sdk_version_pin)
logger.info("mcp_protocol_negotiated", protocol_version=negotiated_version, server_url=server_url)

# Session lifecycle - no need to log session_id/protocol_version (SDK manages)
logger.info("mcp_session_created", client_id=client_id, server_url=server_url, correlation_id=correlation_id)
logger.info("mcp_session_expired", client_id=client_id, server_url=server_url, ttl=ttl)

# Transport and ClientSession lifecycle
logger.info("mcp_transport_created", client_id=client_id, server_url=server_url)
logger.info("mcp_transport_closed", client_id=client_id, reason="session_expired")

# Initialize handshake (via SDK) with latency tracking
logger.info("mcp_initialize_start", client_id=client_id, server_url=server_url, correlation_id=correlation_id)
logger.info("mcp_initialize_success", client_id=client_id, server_url=server_url, latency_ms=latency, correlation_id=correlation_id)
logger.info("mcp_initialized_sent", client_id=client_id, status_code=202)

# Streamable responses with hashed identifiers for safety and size guards
client_hash = hashlib.sha256(f"{client_id}:{server_url}".encode()).hexdigest()[:8]
logger.info("mcp_streamable_start", tool_name=tool_name, client_hash=client_hash, correlation_id=correlation_id)
logger.warning("mcp_chunk_size_capped", original_size=len(chunk_data), capped_size=config.max_event_size, client_hash=client_hash)
logger.info("mcp_streamable_chunk", bytes_sent=len(chunk), total_chunks=chunk_count, client_hash=client_hash)
logger.info("mcp_streamable_first_byte", latency_ms=first_byte_latency, correlation_id=correlation_id)
logger.warning("mcp_stream_idle_timeout", client_hash=client_hash, idle_duration_ms=idle_duration)

# Client disconnects and connection management (no SSE heartbeats needed)
logger.warning("mcp_client_disconnect", tool_name=tool_name, client_hash=client_hash, reason="cancelled_error")
logger.debug("mcp_connection_keepalive", client_hash=client_hash, elapsed_ms=elapsed_since_last_activity)

# Retry attempts with reasons and limits - stable retry_id for correlation
retry_id = str(uuid.uuid4())[:8]  # Short stable ID for retry correlation
logger.warning("mcp_retry_attempt", reason="auth_failure", category="401", attempt=1, max_retries=1, 
              correlation_id=correlation_id, retry_id=retry_id)
logger.info("mcp_retry_success", correlation_id=correlation_id, retry_id=retry_id)
logger.warning("mcp_retry_blocked", reason="partial_stream_sent", correlation_id=correlation_id)

# OBO token management - log audience and expires_at, never tokens
logger.info("obo_token_cache_miss", audience=audience_key, user_id=client_id, correlation_id=correlation_id)
logger.info("obo_token_refresh", audience=audience_key, expires_at=expires_at)
logger.warning("obo_token_evicted", audience=audience_key, reason="auth_failure")

# Circuit breaker events
logger.warning("circuit_breaker_open", client_id=client_id, server_url=server_url, failure_rate=failure_rate)
logger.info("circuit_breaker_closed", client_id=client_id, server_url=server_url)
```

#### Metrics to Track:
- Session creation/expiry rates by (client, server)
- Transport lifecycle events and connection pool health
- **Initialize latency histogram**: Track handshake performance
- **First-byte latency histogram**: Critical for streaming responsiveness
- Streaming response volume and chunk throughput
- Retry attempt frequency by category (auth/session/network)
- OBO token refresh frequency and cache hit rates
- Dead stream detection and cleanup events
- Circuit breaker state changes per client

## Implementation Priority

### Phase Execution Order:
1. **Phase 0**: MCP Client SDK Integration (Foundation)
2. **Phase 1**: Session Management (MCP Client Wrapping)
3. **Phase 2**: Initialize Handshake (MCP Client Integration)
4. **Phase 3**: Streaming Support (Feature Completion)
5. **Phase 4**: Header Management (Protocol Compliance)
6. **Phase 5**: Retry Logic (Robustness)
7. **Phase 6**: Concurrency (Stability)
8. **Phase 7**: Observability (Monitoring)

### Critical Path:
Phases 0-3 are **blocking** - must be completed for basic MCP compliance.  
Phases 4-7 are **enhancements** - improve robustness and observability.

## Key Files to Modify

### Core Components:
- `src/mcp_gateway/core/proxy.py` - Add streaming and session support
- `src/mcp_gateway/core/authenticated_proxy.py` - Session-aware request handling
- `src/mcp_gateway/api/routes.py` - Integrate session management

### New Components:
- `src/mcp_gateway/session/` - Complete session management module with MCP client integration
- `tests/test_session_management.py` - Session testing
- `tests/test_mcp_client_integration.py` - MCP client wrapper tests
- `tests/test_streaming.py` - Streaming response tests

### Configuration:
- `src/mcp_gateway/core/config.py` - Add session TTL, retry settings, and streaming config

#### Configuration Options:
```python
# Add to config.py
@dataclass
class MCPConfig:
    # Protocol and session settings
    protocol_version_pin: Optional[str] = None  # Optional - let SDK negotiate by default
    mcp_sdk_version_pin: Optional[str] = None   # Pin SDK version for controlled rollouts
    session_ttl_seconds: int = 3600
    token_ttl_skew_seconds: int = 300  # Expire tokens early
    
    # Size guards to prevent memory spikes
    max_request_json_size: int = 2 * 1024 * 1024   # 2MB cap on request JSON
    max_event_size: int = 256 * 1024                # 256KB cap per SSE event before chunking
    
    # Retry and backoff settings with hard limits
    max_auth_retries: int = 1        # Auth failures: exactly 1 retry
    max_session_retries: int = 1     # Session errors: exactly 1 retry  
    max_network_retries: int = 3     # Network issues: up to 3 retries
    retry_base_delay_ms: int = 100
    retry_max_delay_ms: int = 5000
    
    # Streaming settings with backpressure controls
    stream_ping_timeout_ms: int = 30000  # Detect dead streams
    stream_idle_timeout_ms: int = 300000  # 5min idle timeout - proactively close abandoned streams
    stream_buffer_size: int = 8192       # Max chunk size before splitting
    stream_keepalive_interval_ms: int = 10000  # Connection keepalive (no SSE heartbeats needed)
    
    # Concurrency and circuit breaker settings
    max_concurrent_sessions_per_server: int = 100
    max_concurrent_streams_per_client: int = 5   # Protect against chatty agents
    session_cleanup_interval_seconds: int = 300
    
    # Circuit breaker settings per client
    circuit_breaker_failure_threshold: int = 5   # Failures before opening
    circuit_breaker_timeout_seconds: int = 60    # How long to stay open
    circuit_breaker_success_threshold: int = 3   # Successes to close
    
    # Rate limiting integration
    rate_limit_before_session: bool = True       # Cheap rejection
    rate_limit_after_obo: bool = True           # Protect downstream
    json_call_rate_limit: int = 100             # Per minute
    streamable_call_rate_limit: int = 10       # Per minute (more expensive)
    
    # Horizontal scaling
    use_redis_for_sessions: bool = False        # Config flip for scaling
    redis_session_prefix: str = "mcp_gateway_sessions"
    redis_lock_prefix: str = "mcp_gateway_locks"
    
    # Future extensibility - server-push notifications via GET /mcp SSE
    enable_server_push: bool = False            # TODO: GET /mcp SSE endpoint for optional server-initiated notifications
    server_push_return_405: bool = True         # Return 405 Method Not Allowed if GET /mcp not supported
```

**Note**: SSE as a standalone (two-endpoint) transport is deprecated as of 2024-11-05. Streamable HTTP (2025-03-26) — a single `/mcp` endpoint with optional SSE responses — is now the standard.

## Testing Strategy

### Unit Tests:
- **Session Lifecycle**: Creation, expiry, cleanup with ClientSession instances
- **Transport Management**: Connection creation, cleanup, and error handling
- **Initialize Handshake**: Success/failure scenarios via MCP SDK
- **Header Processing**: Transport header setup and fallback HTTP headers
- **Retry Logic**: Category-specific retry scenarios with OBO token refresh
- **Concurrency**: Lock behavior and race condition prevention

### Integration Tests:
- **End-to-End Session Flow**: Client → Gateway → ClientSession → MCP Server
- **Streamable Responses**: SSE forwarding via async generators from SDK (per spec)
- **Concurrent Client Handling**: Multiple clients, same server with proper locking
- **Error Recovery**: Session invalidation and retry with categorized failures
- **Transport Lifecycle**: Proper cleanup and re-creation scenarios
- **OBO Integration**: Token refresh, cache eviction, and audience mapping

### Contract Tests:
- **Protocol Compliance**: Assert correct response codes for each operation:
  - `initialize()` → **200 + JSON** (never 202)
  - `notifications/initialized` → **202 + empty** (critical: ONLY this returns 202) - **FIRST TEST IN CI**
  - `list_tools()` → **200 + JSON**
  - Streamable tool calls → **text/event-stream** with multiple chunks and flushing (SSE format per spec)
- **Notification Contract**: Explicitly verify no other method returns 202 (prevents VS Code auth loop bugs)
- **Body Replay Test**: Ensure request body can be read twice (prevents empty initialize payload)
- **Size Guard Tests**: Test request JSON size limits and response chunk size capping
- **Streamable Hardening**: Test client disconnect handling and connection management
- **Stream Idle Timeout**: Test proactive stream closure on idle timeout
- **Partial Stream Protection**: Verify retries are blocked after streamable response starts
- **OBO Failure Modes**: Test expired tokens, invalid audience, missing scope
- **Correct 401 vs 403 mapping**: Map upstream errors appropriately
- **Circuit Breaker**: Test failure threshold, timeout, and recovery scenarios
- **Retry Correlation**: Test retry_id correlation between original and retry attempts

### Performance Tests:
- **Session Storage Performance**: High session volume with ClientSession instances
- **Size Guard Performance**: Impact of JSON size validation and response chunk size capping
- **Streamable Throughput**: Large SSE responses via async generators with backpressure and idle timeout
- **Concurrent Request Handling**: Load testing with transport connection pooling
- **Memory Usage**: ClientSession and transport lifecycle efficiency with size limits
- **Lock Contention**: Performance under high concurrency with dual-lock strategy
- **Circuit Breaker Performance**: Impact of circuit breaker checks under load
- **Rate Limiter Integration**: Performance impact of dual rate limiting (before/after OBO)
- **Horizontal Scaling**: Redis-based session and lock performance vs local-only

## Implementation Details & Best Practices

### Context Manager for Session Acquisition:
```python
@asynccontextmanager
async def acquire_mcp_session(client_id: str, server_url: str, obo_token: str, correlation_id: str):
    """Context manager that guarantees: create if missing → initialize → reuse"""
    session = None
    try:
        # Apply rate limiting before session acquisition (cheap rejection)
        if config.rate_limit_before_session:
            await rate_limiter.check_limit(client_id, "session_acquisition")
        
        session = await session_manager.get_or_create_session(
            client_id, server_url, obo_token
        )
        
        # Apply rate limiting after OBO (protect downstream)
        if config.rate_limit_after_obo:
            await rate_limiter.check_limit(f"{client_id}:{server_url}", "downstream_calls")
        
        yield session
    except Exception as e:
        if should_retry(e):
            # Check circuit breaker state
            if circuit_breaker.is_open(client_id, server_url):
                logger.warning("circuit_breaker_reject", client_id=client_id, server_url=server_url)
                raise HTTPException(status_code=503, detail="Circuit breaker open")
            
            # Single retry path with category-specific logic and stable retry correlation
            retry_id = str(uuid.uuid4())[:8]  # Short stable ID for retry correlation
            
            if is_auth_error(e):
                logger.warning("mcp_retry_attempt", reason="auth_failure", category="401", 
                             attempt=1, max_retries=1, correlation_id=correlation_id, retry_id=retry_id)
                # Evict only (user_id, audience) token
                audience_key = session_manager._get_audience_key(server_url)
                await obo_service.evict_token(audience_key, client_id)
                fresh_token = await obo_service.get_token(audience_key, client_id)
                await session_manager.invalidate_session(client_id, server_url)
                session = await session_manager.get_or_create_session(
                    client_id, server_url, fresh_token
                )
            elif is_session_error(e):
                logger.warning("mcp_retry_attempt", reason="session_error", category="session", 
                             attempt=1, max_retries=1, correlation_id=correlation_id, retry_id=retry_id)
                # Keep token, just re-init session
                await session_manager.invalidate_session(client_id, server_url)
                session = await session_manager.get_or_create_session(
                    client_id, server_url, obo_token
                )
            else:
                # Network errors handled with backoff in session manager
                circuit_breaker.record_failure(client_id, server_url)
                raise
            
            # Record success if retry worked
            logger.info("mcp_retry_success", correlation_id=correlation_id, retry_id=retry_id)
            circuit_breaker.record_success(client_id, server_url)
            yield session
        else:
            circuit_breaker.record_failure(client_id, server_url)
            raise
    finally:
        if session:
            # Use BackgroundTask for cleanup - don't block response
            asyncio.create_task(session_manager.schedule_cleanup_check(session))
```

### Request Body Preservation (Starlette Pattern Only):
```python
# Use ONLY this pattern - avoid mutating ASGI scope
class MCPProxyMiddleware:
    async def __call__(self, request: Request, call_next):
        # Read body but preserve for downstream handlers
        body = await request.body()
        setattr(request, "_body", body)  # Let downstream read again
        
        # Add correlation ID for tracing
        correlation_id = str(uuid.uuid4())
        setattr(request, "_correlation_id", correlation_id)
        
        return await call_next(request)

# Test to ensure body can be read twice (prevents initialize empty payload bug)
async def test_body_replay():
    # Simulate middleware reading body
    body1 = await request.body()
    # Downstream handler should still get body
    body2 = await request.body()
    assert body1 == body2, "Body replay failed - initialize will get empty payload"
```

### App-Level Shutdown Hook:
```python
# Add to FastAPI app startup/shutdown
@app.on_event("startup")
async def startup_mcp_gateway():
    """Log MCP Gateway startup with SDK version info"""
    try:
        import mcp
        actual_version = mcp.__version__
        pinned_version = config.mcp_sdk_version_pin
        
        if pinned_version and actual_version != pinned_version:
            logger.warning("mcp_version_mismatch", actual=actual_version, pinned=pinned_version)
        
        logger.info("mcp_gateway_startup", mcp_sdk_version=actual_version, pinned_version=pinned_version)
    except ImportError:
        logger.error("mcp_sdk_missing", message="MCP SDK not installed")
        raise

@app.on_event("shutdown")
async def shutdown_mcp_sessions():
    """Graceful shutdown of all active MCP sessions"""
    logger.info("mcp_shutdown_start", active_sessions=len(session_manager._sessions))
    
    # Iterate all active sessions and properly close context managers
    for session_key, session in session_manager._sessions.items():
        try:
            logger.info("mcp_session_shutdown", session_key=session_key)
            await session.close()  # Calls wrapper.close() which handles __aexit__
        except Exception as e:
            logger.error("mcp_session_shutdown_error", session_key=session_key, error=str(e))
    
    logger.info("mcp_shutdown_complete")

# Circuit breaker implementation
class CircuitBreaker:
    def __init__(self, config: MCPConfig):
        self.config = config
        self.failure_counts: Dict[str, int] = {}
        self.success_counts: Dict[str, int] = {}
        self.last_failure_time: Dict[str, float] = {}
        self.state: Dict[str, str] = {}  # "closed", "open", "half-open"
    
    def _get_key(self, client_id: str, server_url: str) -> str:
        return f"{client_id}:{server_url}"
    
    def is_open(self, client_id: str, server_url: str) -> bool:
        key = self._get_key(client_id, server_url)
        state = self.state.get(key, "closed")
        
        if state == "open":
            # Check if timeout has elapsed
            if time.time() - self.last_failure_time.get(key, 0) > self.config.circuit_breaker_timeout_seconds:
                self.state[key] = "half-open"
                return False
            return True
        
        return False
    
    def record_failure(self, client_id: str, server_url: str):
        key = self._get_key(client_id, server_url)
        self.failure_counts[key] = self.failure_counts.get(key, 0) + 1
        self.last_failure_time[key] = time.time()
        
        if self.failure_counts[key] >= self.config.circuit_breaker_failure_threshold:
            self.state[key] = "open"
            logger.warning("circuit_breaker_open", client_id=client_id, server_url=server_url, 
                         failure_count=self.failure_counts[key])
    
    def record_success(self, client_id: str, server_url: str):
        key = self._get_key(client_id, server_url)
        current_state = self.state.get(key, "closed")
        
        if current_state == "half-open":
            self.success_counts[key] = self.success_counts.get(key, 0) + 1
            if self.success_counts[key] >= self.config.circuit_breaker_success_threshold:
                self.state[key] = "closed"
                self.failure_counts[key] = 0
                self.success_counts[key] = 0
                logger.info("circuit_breaker_closed", client_id=client_id, server_url=server_url)
        elif current_state == "closed":
            # Reset failure count on success
            self.failure_counts[key] = 0
```

### Horizontal Scaling Adapter:
```python
# Redis adapter for distributed sessions and locks
class RedisSessionManager(MCPSessionManager):
    def __init__(self, redis_client, config: MCPConfig):
        super().__init__()
        self.redis = redis_client
        self.config = config
        self.local_sessions = {}  # Local cache
    
    async def get_or_create_session(self, client_id: str, server_url: str, auth_token: str = None):
        if self.config.use_redis_for_sessions:
            # Distributed session management
            session_key = self._get_session_key(client_id, server_url)
            
            # Try local cache first
            if session_key in self.local_sessions:
                session = self.local_sessions[session_key]
                if session.expires_at > datetime.utcnow():
                    return session
            
            # Use Redis-based distributed lock
            async with RedisLock(self.redis, f"{self.config.redis_lock_prefix}:{session_key}"):
                # Check Redis for existing session metadata
                session_data = await self.redis.get(f"{self.config.redis_session_prefix}:{session_key}")
                if session_data:
                    # Session exists, create local instance
                    return await self._create_local_session_from_redis(session_data)
                
                # Create new session and store in Redis
                session = await self._create_new_session(client_id, server_url, auth_token)
                await self._store_session_in_redis(session_key, session)
                return session
        else:
            # Fall back to local-only mode
            return await super().get_or_create_session(client_id, server_url, auth_token)
```

## Risk Assessment

### High Risk:
- **Breaking Changes**: Session management will change API behavior
- **Performance Impact**: Session storage and ClientSession instance overhead
- **Backward Compatibility**: Existing clients may need updates
- **MCP SDK Dependency**: Reliance on Python MCP SDK stability and updates
- **Transport Connection Limits**: Managing connection pool sizes per server
- **Streaming Backpressure**: Large responses could impact TTFB if not properly chunked (using SSE format per spec)

### Medium Risk:
- **Memory Usage**: Session storage growth with ClientSession instances over time
- **Connection Leaks**: Transport and ClientSession connection management
- **Race Conditions**: Complex concurrent session and token refresh handling
- **OBO Token Management**: Token refresh timing, cache coherence, and failure scenarios
- **Dead Stream Detection**: Identifying and cleaning up stale streaming connections
- **Circuit Breaker State**: Managing circuit breaker state across multiple instances
- **Rate Limiter Accuracy**: Ensuring accurate rate limiting with distributed sessions

### Mitigation Strategies:
- **Gradual Rollout**: Feature flags for session management and SDK integration
- **Comprehensive Testing**: Unit, integration, contract, and performance tests including streaming hardening
- **Monitoring**: Detailed logging, metrics, dead stream detection, and circuit breaker state tracking
- **Documentation**: Clear migration guide for clients and operational runbooks
- **Connection Limits**: Configurable limits and circuit breakers for transport connections
- **Backpressure Controls**: Stream buffer size limits and event chunking for large payloads
- **Fallback Mechanisms**: Local-only mode as fallback when Redis is unavailable
- **Rate Limiting Strategy**: Dual rate limiting (before session + after OBO) with different limits for JSON vs streamable responses

## Success Criteria

### MCP Compliance:
- ✅ Proper session management per client using ClientSession instances
- ✅ Complete initialize/initialized handshake via MCP SDK (200 + 202 semantics)
- ✅ Streamable HTTP response support via async generators with prompt flushing
- ✅ SDK-managed header handling with transport-level auth setup
- ✅ Category-based retry logic with OBO token refresh and session re-init

### Performance:
- 📈 No significant latency increase for JSON responses
- 📈 Efficient streamable responses via async generators with NDJSON format
- 📈 Stable memory usage with ClientSession and transport cleanup
- 📈 Optimized connection pooling and reuse across requests

### Reliability:
- 🔧 Graceful handling of session expiry and transport lifecycle
- 🔧 Category-based error recovery with proper retry semantics
- 🔧 Thread-safe concurrent operations with dual-lock strategy
- 🔧 Dead stream detection and cleanup for long-running connections
- 🔧 Circuit breaker protection per client to shed load gracefully
- 🔧 Partial stream protection preventing dangerous retries
- 🔧 App-level shutdown hooks for clean resource cleanup

## Next Steps

1. **Review and Approve Plan** - Stakeholder sign-off ✅
2. **Research MCP Client Libraries** - Evaluate available Python MCP client options
3. **Create Feature Branch** - `feature/mcp-compliance` 
4. **Begin Phase 0** - Integrate MCP client SDK with version pinning
5. **Implement Contract Test First** - 202-only for `notifications/initialized` (prevents regressions)
6. **Begin Phase 1** - Implement session management with MCP client wrapper
7. **Iterative Development** - Phase-by-phase implementation with size guards and streaming hardening
8. **Testing at Each Phase** - Comprehensive test coverage including retry correlation
9. **Documentation Updates** - User and developer guides
9. **TODO: Future Server-Push** - Optional GET /mcp SSE endpoint for server-initiated notifications (or return 405)

---

**Document Version**: 1.0  
**Last Updated**: August 19, 2025  
**Author**: GitHub Copilot  
**Reviewers**: [To be assigned]
