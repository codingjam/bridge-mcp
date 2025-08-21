# Rate Limiting Quick Reference

> **TL;DR for the production-ready rate limiting system**

## Status
**✅ Production Ready**: Implemented and operational as of Phase 1 completion (August 2025).

## TL;DR

**Requirement**: Users cannot invoke a tool for a specific server more than 5 times per minute.

**Solution**: Composite key rate limiting with format `rl:user:{user_id}|service:{service_id}|tool:{tool_name}`.

## Quick Setup

### 1. Environment Configuration
```bash
# .env file
ENABLE_RATE_LIMITING=true
RATE_LIMIT_DEFAULT_LIMIT=5
RATE_LIMIT_DEFAULT_WINDOW=60
RATE_LIMIT_BACKEND=memory
```

### 2. Middleware Integration
```python
# Already integrated in main.py
from mcp_gateway.rl import get_rate_limiter, RateLimitMiddleware

limiter = get_rate_limiter()
app.add_middleware(RateLimitMiddleware, limiter=limiter)
```

### 3. Test Configuration
```bash
# Run tests
uv run python -m pytest tests/test_rate_limiting.py -v
```

## Key Concepts

| Concept | Description | Example |
|---------|-------------|---------|
| **Composite Key** | `user + service + tool` | `rl:user:alice\|service:weather\|tool:get_weather` |
| **Fixed Window** | 60-second reset intervals | Window 1: 0-59s, Window 2: 60-119s |
| **Isolation** | Separate limits per combination | User1+Weather+GetTemp ≠ User1+News+GetHeadlines |
| **429 Response** | Rate limit exceeded | Returns `Retry-After` header |

## API Behavior

### Allowed Requests (1-5)
```http
POST /api/v1/mcp/weather_service/call
Authorization: Bearer <token>
Content-Type: application/json

{
  "method": "tools/call",
  "params": {
    "name": "get_weather",
    "arguments": {"city": "Paris"}
  }
}

Response: 200 OK
```

### Blocked Request (6+)
```http
POST /api/v1/mcp/weather_service/call
# Same request as above

Response: 429 Too Many Requests
Retry-After: 45
{
  "detail": "Rate limit exceeded"
}
```

## Isolation Examples

```python
# These are ALL separate rate limits:

# Different users
alice_weather = "rl:user:alice|service:weather|tool:get_weather"     # 5/min
bob_weather   = "rl:user:bob|service:weather|tool:get_weather"       # 5/min

# Different services  
alice_weather = "rl:user:alice|service:weather|tool:get_weather"     # 5/min
alice_news    = "rl:user:alice|service:news|tool:get_weather"        # 5/min

# Different tools
alice_weather   = "rl:user:alice|service:weather|tool:get_weather"   # 5/min
alice_forecast  = "rl:user:alice|service:weather|tool:get_forecast"  # 5/min
```

## Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Rate limiting not working | `ENABLE_RATE_LIMITING=false` | Set to `true` in `.env` |
| All requests blocked | Authentication middleware order | Rate limit middleware must be BEFORE auth |
| Memory growing | No cleanup | Memory backend auto-cleans every 10 windows |
| Users bypassing limits | Missing user_id | Check auth middleware extracts `request.state.user_id` |

## Testing Commands

```bash
# Run all rate limiting tests
uv run python -m pytest tests/test_rate_limiting.py -v

# Run specific requirement test
uv run python -m pytest tests/test_rate_limiting.py::TestIntegrationScenario::test_user_cannot_invoke_tool_more_than_5_times_per_minute -v

# Check configuration
python -c "from mcp_gateway.rl.config import get_rate_limit_config; print(get_rate_limit_config())"
```

## Monitoring

### Log Messages
```bash
# Rate limit exceeded
grep "Rate limit exceeded" logs/ | jq '.user_id, .service_id, .tool_name, .retry_after'

# Middleware initialization  
grep "Rate limiting middleware initialized" logs/

# Backend errors
grep "Memory backend error" logs/
```

### Key Metrics
- **Violations per user**: `rate_limit_exceeded` events by `user_id`
- **Popular tools**: Most frequently rate-limited `tool_name` values
- **Service load**: Rate limit events by `service_id`
- **Retry times**: Average `retry_after` values

## Customization

### Custom Limits
```python
# In main.py
from mcp_gateway.rl import RateLimitConfig, create_rate_limiter

config = RateLimitConfig(
    default_limit=10,      # 10 requests instead of 5
    default_window=300     # per 5 minutes instead of 1
)
limiter = create_rate_limiter(config)
```

### Different Paths
```python
# Apply to different endpoints
app.add_middleware(
    RateLimitMiddleware,
    limiter=limiter,
    apply_to_paths=("/api/v1/mcp", "/api/v1/custom")
)
```

### Disable Rate Limiting
```bash
# .env
ENABLE_RATE_LIMITING=false
```

## Architecture Summary

```
Request → CORS → TrustedHost → RateLimit → Auth → Routes
                                   ↓
                             Extract Context
                                   ↓  
                           Build Composite Key
                                   ↓
                           Check/Increment Counter
                                   ↓
                           Allow/Block (429)
```

**Components**:
- **Middleware**: Request interception and context extraction
- **Limiter**: Policy enforcement and allow/deny decisions  
- **Backend**: Counter storage and window management
- **Config**: Environment variable integration
- **Keys**: Composite key generation and normalization

For detailed information, see the full [Rate Limiting Documentation](Rate_Limiting_Documentation.md).
