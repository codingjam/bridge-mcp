"""Rate limiting middleware for FastAPI."""

import logging
from typing import Tuple, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .limiter import RateLimiter
from .keys import build_rl_key

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limits on specified endpoints."""
    
    def __init__(
        self, 
        app, 
        limiter: Optional[RateLimiter] = None, 
        apply_to_paths: Tuple[str, ...] = ("/api/v1/mcp",)
    ):
        """Initialize rate limiting middleware."""
        super().__init__(app)
        self.limiter = limiter
        self.apply_to_paths = apply_to_paths
        
        # If no limiter provided, rate limiting is effectively disabled
        if self.limiter is None:
            logger.info("Rate limiting middleware initialized but disabled (no limiter provided)")
        else:
            logger.info(
                "Rate limiting middleware initialized",
                extra={
                    "apply_to_paths": self.apply_to_paths,
                    "policy_limit": self.limiter._policy.limit,
                    "policy_window": self.limiter._policy.window_seconds
                }
            )
    
    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting to matching requests."""
        # Skip if rate limiting is disabled
        if self.limiter is None:
            return await call_next(request)
            
        # Only apply to POST requests on specified paths
        if request.method != "POST":
            return await call_next(request)
        
        # Check if the request path matches any of our target paths
        request_path = request.url.path
        should_apply = any(request_path.startswith(path) for path in self.apply_to_paths)
        
        if not should_apply:
            return await call_next(request)
        
        try:
            # Extract service_id from URL path and tool from request body
            user_id, service_id, tool_name = await self._extract_context_from_mcp_request(request)
            
            # Build rate limiting key
            key = build_rl_key(
                user_id=user_id,
                service_id=service_id,
                tool_name=tool_name
            )
            
            # Check rate limit
            allowed, retry_after = self.limiter.check_and_consume(key)
            
            if not allowed:
                logger.warning(
                    "Rate limit exceeded",
                    extra={
                        "user_id": user_id,
                        "service_id": service_id,
                        "tool_name": tool_name,
                        "retry_after": retry_after,
                        "path": request_path,
                        "rate_limit_key": key
                    }
                )
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                    headers={"Retry-After": str(retry_after)}
                )
            
            # Rate limit check passed, continue with request
            return await call_next(request)
            
        except Exception as e:
            # If context extraction fails, check if it's an HTTPException and let it bubble up
            if hasattr(e, 'status_code'):
                # It's already an HTTPException, let it pass through
                raise
            else:
                # Unexpected error, log and let it bubble up
                logger.error(
                    "Unexpected error in rate limiting middleware",
                    extra={
                        "error": str(e),
                        "path": request.url.path,
                        "method": request.method
                    },
                    exc_info=True
                )
                raise
    
    async def _extract_context_from_mcp_request(self, request: Request) -> Tuple[str, str, str]:
        """Extract user_id, service_id, and tool_name from MCP request."""
        # Extract user_id from state or fallback to header
        user_id = getattr(request.state, 'user_id', None)
        if not user_id:
            user_id = request.headers.get('X-User-Id')
        
        if not user_id:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail="user_id missing - not found in request.state.user_id or X-User-Id header"
            )
        
        # Extract service_id from URL path: /api/v1/mcp/{service_id}/call
        path_parts = request.url.path.split('/')
        service_id = None
        
        # For /api/v1/mcp/{service_id}/call - service_id is at index 4
        if len(path_parts) >= 5 and 'mcp' in path_parts:
            mcp_index = path_parts.index('mcp')
            if mcp_index + 1 < len(path_parts):
                service_id = path_parts[mcp_index + 1]
        
        if not service_id:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail="service_id missing from URL path"
            )
        
        # Extract tool_name from MCP request body
        try:
            body = await request.body()
            if not body:
                tool_name = "unknown_tool"
            else:
                import json
                try:
                    data = json.loads(body)
                    # MCP protocol structure: look for method or params.name
                    if data.get('method') == 'tools/call':
                        # Standard MCP tool call: {"method": "tools/call", "params": {"name": "tool_name", ...}}
                        tool_name = data.get('params', {}).get('name', 'unknown_tool')
                    else:
                        # Other MCP methods or custom structure
                        tool_name = data.get('method', 'unknown_method')
                except json.JSONDecodeError:
                    tool_name = "unknown_tool"
        except Exception:
            tool_name = "unknown_tool"
        
        return user_id, service_id, tool_name
