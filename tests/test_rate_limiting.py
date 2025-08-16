"""Tests for rate limiting functionality."""

import pytest
import time
from unittest.mock import Mock, AsyncMock, patch

from mcp_gateway.rl import (
    RateLimiter, RatePolicy, MemoryBackend, 
    build_rl_key, RateLimitMiddleware,
    RateLimitConfig, create_rate_limiter
)
from mcp_gateway.rl.exceptions import RateLimitBackendError


class TestRateLimitKey:
    """Test rate limiting key generation."""
    
    def test_build_rl_key_basic(self):
        """Test basic key generation."""
        key = build_rl_key(
            user_id="user123",
            service_id="service456", 
            tool_name="get_weather"
        )
        assert key == "rl:user:user123|service:service456|tool:get_weather"
    
    def test_build_rl_key_normalization(self):
        """Test key normalization."""
        key = build_rl_key(
            user_id=" User123 ",
            service_id=" SERVICE456 ",
            tool_name=" GET_Weather "
        )
        assert key == "rl:user:User123|service:service456|tool:get_weather"
    
    def test_build_rl_key_delimiter_collision(self):
        """Test delimiter collision handling."""
        key = build_rl_key(
            user_id="user|with|pipes",
            service_id="service|456",
            tool_name="tool|name"
        )
        assert key == "rl:user:user_with_pipes|service:service_456|tool:tool_name"


class TestMemoryBackend:
    """Test memory backend functionality."""
    
    def test_memory_backend_single_increment(self):
        """Test single increment operation."""
        backend = MemoryBackend()
        count, ttl = backend.incr_and_get("test_key", 60)
        
        assert count == 1
        assert 0 < ttl <= 60
    
    def test_memory_backend_multiple_increments(self):
        """Test multiple increments in same window."""
        backend = MemoryBackend()
        
        # First increment
        count1, ttl1 = backend.incr_and_get("test_key", 60)
        assert count1 == 1
        
        # Second increment
        count2, ttl2 = backend.incr_and_get("test_key", 60)
        assert count2 == 2
        
        # TTL should be similar (within a few seconds)
        assert abs(ttl1 - ttl2) <= 2
    
    def test_memory_backend_different_keys(self):
        """Test that different keys have separate counters."""
        backend = MemoryBackend()
        
        count1, _ = backend.incr_and_get("key1", 60)
        count2, _ = backend.incr_and_get("key2", 60)
        
        assert count1 == 1
        assert count2 == 1
    
    def test_memory_backend_window_separation(self):
        """Test that different windows have separate counters."""
        backend = MemoryBackend()
        
        # Mock time to control windows
        with patch('time.time') as mock_time:
            # First window (time 0-59)
            mock_time.return_value = 30
            count1, _ = backend.incr_and_get("test_key", 60)
            assert count1 == 1
            
            # Second window (time 60-119)
            mock_time.return_value = 90
            count2, _ = backend.incr_and_get("test_key", 60)
            assert count2 == 1  # Reset in new window


class TestRateLimiter:
    """Test rate limiter functionality."""
    
    def test_rate_limiter_allows_under_limit(self):
        """Test that requests under limit are allowed."""
        backend = MemoryBackend()
        policy = RatePolicy(limit=5, window_seconds=60)
        limiter = RateLimiter(backend, policy)
        
        # First 5 requests should be allowed
        for i in range(5):
            allowed, retry_after = limiter.check_and_consume("test_key")
            assert allowed is True
            assert retry_after == 0
    
    def test_rate_limiter_blocks_over_limit(self):
        """Test that requests over limit are blocked."""
        backend = MemoryBackend()
        policy = RatePolicy(limit=5, window_seconds=60)
        limiter = RateLimiter(backend, policy)
        
        # First 5 requests should be allowed
        for i in range(5):
            allowed, retry_after = limiter.check_and_consume("test_key")
            assert allowed is True
            assert retry_after == 0
        
        # 6th request should be blocked
        allowed, retry_after = limiter.check_and_consume("test_key")
        assert allowed is False
        assert retry_after > 0
        assert retry_after <= 60
    
    def test_rate_limiter_user_service_tool_isolation(self):
        """Test that rate limits are isolated by user, service, and tool."""
        backend = MemoryBackend()
        policy = RatePolicy(limit=2, window_seconds=60)
        limiter = RateLimiter(backend, policy)
        
        # User1 + Service1 + Tool1 - should allow 2 requests
        key1 = build_rl_key(user_id="user1", service_id="service1", tool_name="tool1")
        allowed1, _ = limiter.check_and_consume(key1)
        allowed2, _ = limiter.check_and_consume(key1)
        blocked, _ = limiter.check_and_consume(key1)
        
        assert allowed1 is True
        assert allowed2 is True
        assert blocked is False
        
        # User1 + Service1 + Tool2 - should allow 2 more requests (different tool)
        key2 = build_rl_key(user_id="user1", service_id="service1", tool_name="tool2")
        allowed3, _ = limiter.check_and_consume(key2)
        allowed4, _ = limiter.check_and_consume(key2)
        
        assert allowed3 is True
        assert allowed4 is True
        
        # User2 + Service1 + Tool1 - should allow 2 more requests (different user)
        key3 = build_rl_key(user_id="user2", service_id="service1", tool_name="tool1")
        allowed5, _ = limiter.check_and_consume(key3)
        allowed6, _ = limiter.check_and_consume(key3)
        
        assert allowed5 is True
        assert allowed6 is True


class TestRateLimitConfig:
    """Test rate limit configuration."""
    
    def test_rate_limit_config_defaults(self):
        """Test default configuration values."""
        config = RateLimitConfig()
        
        assert config.enabled is True
        assert config.default_limit == 5
        assert config.default_window == 60
        assert config.backend == "memory"
        assert config.redis_url is None
    
    def test_create_rate_limiter_memory_backend(self):
        """Test creating rate limiter with memory backend."""
        config = RateLimitConfig(
            enabled=True,
            default_limit=3,
            default_window=30,
            backend="memory"
        )
        
        limiter = create_rate_limiter(config)
        
        assert limiter is not None
        assert isinstance(limiter._backend, MemoryBackend)
        assert limiter._policy.limit == 3
        assert limiter._policy.window_seconds == 30
    
    def test_create_rate_limiter_disabled(self):
        """Test that disabled config returns None."""
        config = RateLimitConfig(enabled=False)
        limiter = create_rate_limiter(config)
        
        assert limiter is None
    
    def test_create_rate_limiter_redis_not_implemented(self):
        """Test that Redis backend raises NotImplementedError."""
        config = RateLimitConfig(backend="redis")
        
        with pytest.raises(NotImplementedError, match="Redis backend not yet implemented"):
            create_rate_limiter(config)


class TestRateLimitMiddleware:
    """Test rate limiting middleware."""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock FastAPI request."""
        request = Mock()
        request.method = "POST"
        request.url.path = "/api/v1/mcp/test_service/call"
        request.state.user_id = "test_user"
        
        # Mock request body for MCP tool call
        body_data = {
            "method": "tools/call",
            "params": {
                "name": "test_tool",
                "arguments": {"param1": "value1"}
            }
        }
        import json
        request.body = AsyncMock(return_value=json.dumps(body_data).encode())
        
        return request
    
    @pytest.fixture
    def rate_limiter(self):
        """Create a rate limiter for testing."""
        backend = MemoryBackend()
        policy = RatePolicy(limit=2, window_seconds=60)  # Low limit for testing
        return RateLimiter(backend, policy)
    
    @pytest.fixture
    def middleware(self, rate_limiter):
        """Create middleware with test rate limiter."""
        app = Mock()
        return RateLimitMiddleware(app, limiter=rate_limiter)
    
    @pytest.mark.asyncio
    async def test_middleware_allows_under_limit(self, middleware, mock_request):
        """Test middleware allows requests under rate limit."""
        call_next = AsyncMock(return_value="success")
        
        # First request should be allowed
        result = await middleware.dispatch(mock_request, call_next)
        assert result == "success"
        call_next.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_middleware_blocks_over_limit(self, middleware, mock_request):
        """Test middleware blocks requests over rate limit."""
        call_next = AsyncMock(return_value="success")
        
        # First 2 requests should be allowed
        await middleware.dispatch(mock_request, call_next)
        await middleware.dispatch(mock_request, call_next)
        
        # Third request should be blocked
        response = await middleware.dispatch(mock_request, call_next)
        
        # Should return 429 response, not call next
        assert hasattr(response, 'status_code')
        assert response.status_code == 429
        assert call_next.call_count == 2  # Only called for first 2 requests
    
    @pytest.mark.asyncio
    async def test_middleware_skips_non_post(self, middleware):
        """Test middleware skips non-POST requests."""
        request = Mock()
        request.method = "GET"
        call_next = AsyncMock(return_value="success")
        
        result = await middleware.dispatch(request, call_next)
        assert result == "success"
        call_next.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_middleware_skips_wrong_path(self, middleware):
        """Test middleware skips requests to non-MCP paths."""
        request = Mock()
        request.method = "POST"
        request.url.path = "/api/v1/health"
        call_next = AsyncMock(return_value="success")
        
        result = await middleware.dispatch(request, call_next)
        assert result == "success"
        call_next.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_middleware_disabled_when_no_limiter(self):
        """Test middleware is disabled when no limiter provided."""
        app = Mock()
        middleware = RateLimitMiddleware(app, limiter=None)
        
        request = Mock()
        request.method = "POST"
        request.url.path = "/api/v1/mcp/test/call"
        call_next = AsyncMock(return_value="success")
        
        result = await middleware.dispatch(request, call_next)
        assert result == "success"
        call_next.assert_called_once()


class TestIntegrationScenario:
    """Integration test for the specific user requirement."""
    
    @pytest.mark.asyncio
    async def test_user_cannot_invoke_tool_more_than_5_times_per_minute(self):
        """
        Test the specific requirement: 
        A user cannot invoke a tool for a specific server more than 5 times in a minute.
        """
        # Create rate limiter with 5 requests per 60 seconds
        backend = MemoryBackend()
        policy = RatePolicy(limit=5, window_seconds=60)
        limiter = RateLimiter(backend, policy)
        
        # Test data
        user_id = "user123"
        service_id = "weather_service"
        tool_name = "get_current_weather"
        
        key = build_rl_key(
            user_id=user_id,
            service_id=service_id,
            tool_name=tool_name
        )
        
        # User should be able to make 5 requests
        for i in range(5):
            allowed, retry_after = limiter.check_and_consume(key)
            assert allowed is True, f"Request {i+1} should be allowed"
            assert retry_after == 0, f"Request {i+1} should have no retry delay"
        
        # 6th request should be blocked
        allowed, retry_after = limiter.check_and_consume(key)
        assert allowed is False, "6th request should be blocked"
        assert retry_after > 0, "Should provide retry-after time"
        assert retry_after <= 60, "Retry-after should be within window"
        
        # 7th request should also be blocked
        allowed, retry_after = limiter.check_and_consume(key)
        assert allowed is False, "7th request should also be blocked"
        
        # Different tool for same service should have separate limit
        different_tool_key = build_rl_key(
            user_id=user_id,
            service_id=service_id,
            tool_name="get_weather_forecast"  # Different tool
        )
        
        allowed, retry_after = limiter.check_and_consume(different_tool_key)
        assert allowed is True, "Different tool should have separate rate limit"
        
        # Different service should have separate limit
        different_service_key = build_rl_key(
            user_id=user_id,
            service_id="news_service",  # Different service
            tool_name=tool_name
        )
        
        allowed, retry_after = limiter.check_and_consume(different_service_key)
        assert allowed is True, "Different service should have separate rate limit"
        
        # Different user should have separate limit
        different_user_key = build_rl_key(
            user_id="user456",  # Different user
            service_id=service_id,
            tool_name=tool_name
        )
        
        allowed, retry_after = limiter.check_and_consume(different_user_key)
        assert allowed is True, "Different user should have separate rate limit"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
