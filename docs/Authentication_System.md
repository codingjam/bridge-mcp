# Authentication System Implementation

## Overview

This document provides a comprehensive overview of the OIDC authentication system implemented for the MCP Gateway. The system provides secure authentication using Keycloak as the identity provider and supports OAuth2 On-Behalf-Of (OBO) flow for service-to-service communication.

## Architecture

### Core Components

1. **AuthenticationMiddleware** (`auth/middleware.py`)
   - FastAPI middleware that intercepts all requests
   - Extracts and validates Bearer tokens
   - Returns 401 for unauthenticated requests
   - Creates user context for authenticated requests

2. **TokenValidator** (`auth/token_validator.py`)
   - Validates JWT tokens using Keycloak's JWKS endpoint
   - Supports signature verification and claim validation
   - Optional token introspection for revocation checking
   - Implements caching for performance optimization

3. **OBOTokenService** (`auth/obo_service.py`)
   - Implements OAuth2 token exchange (RFC 8693)
   - Exchanges user tokens for service-specific tokens
   - Supports caching and automatic token refresh
   - Handles service-specific audience and scope requirements

4. **AuthenticatedMCPProxyService** (`core/authenticated_proxy.py`)
   - Extends the base proxy service with authentication
   - Integrates with OBO service for downstream authentication
   - Supports both OBO tokens and user token passthrough

### Data Models

5. **AuthConfig** (`auth/models.py`)
   - Configuration model for Keycloak integration
   - Includes all necessary OIDC and OBO settings

6. **TokenClaims** (`auth/models.py`)
   - Structured representation of JWT token claims
   - Supports standard and Keycloak-specific claims

7. **UserContext** (`auth/models.py`)
   - Simplified user information for application use
   - Created from validated token claims

8. **MCPServiceAuth** (`auth/models.py`)
   - Service-specific authentication configuration
   - Defines how to authenticate with individual MCP services

## Authentication Flow

### 1. Request Authentication

```
Client Request → Authentication Middleware → Token Validation → User Context Creation
```

1. Client sends request with `Authorization: Bearer <token>` header
2. Middleware extracts the Bearer token
3. TokenValidator validates the token:
   - Fetches JWKS keys from Keycloak
   - Verifies JWT signature
   - Validates standard claims (exp, iss, aud, etc.)
   - Optional introspection for revocation checking
4. Creates UserContext from validated claims
5. Continues to route handler or returns 401 on failure

### 2. Service Authentication (OBO Flow)

```
User Token → Token Exchange → Service Token → MCP Service Call
```

1. Gateway has user's validated token
2. OBOTokenService exchanges user token for service-specific token:
   - Uses gateway's client credentials
   - Requests appropriate audience and scopes
   - Caches the exchanged token
3. AuthenticatedMCPProxyService uses service token for downstream calls
4. MCP service receives authenticated request

## Configuration

### Environment Variables

```bash
# Authentication Configuration
ENABLE_AUTH=true
KEYCLOAK_SERVER_URL=https://your-keycloak-server.com
KEYCLOAK_REALM=your-realm
KEYCLOAK_CLIENT_ID=mcp-gateway
KEYCLOAK_CLIENT_SECRET=your-client-secret

# Token Validation
TOKEN_AUDIENCE=mcp-gateway
TOKEN_ISSUER=https://your-keycloak-server.com/realms/your-realm
JWKS_CACHE_TTL=3600

# OBO Configuration
ENABLE_OBO=true
OBO_CACHE_TTL=1800

# Security Settings
CLOCK_SKEW_TOLERANCE=300
REQUIRED_SCOPES=["mcp:read"]
```

### Service Configuration

```yaml
# config/services.yaml
services:
  my-service:
    name: "My MCP Service"
    transport: "http"
    endpoint: "https://my-service.com"
    enabled: true
    auth:
      strategy: "obo_required"  # Options: no_auth, passthrough, obo_preferred, obo_required
      target_audience: "my-service"
      required_scopes: ["mcp:call"]
      custom_headers:
        "X-Service-Name": "mcp-gateway"
```

## Security Features

### Token Security
- JWT signature validation using RS256/ES256 algorithms
- Standard claim validation (exp, iss, aud, nbf)
- Clock skew tolerance for distributed systems
- Optional token introspection for real-time revocation

### Caching Strategy
- JWKS keys cached with configurable TTL
- Introspection results cached to reduce load
- OBO tokens cached with expiration handling
- Automatic cleanup of expired cache entries

### Error Handling
- Comprehensive exception hierarchy
- Proper HTTP status code mapping
- Detailed logging for debugging
- Graceful degradation on service failures

## Service Registry Integration

### Configuration-Driven Authentication

The ServiceRegistry now serves as the central bridge between YAML configuration and the authentication system, providing configuration-driven authentication strategies per service:

```python
# Service Registry loads authentication configurations from YAML
from mcp_gateway.core.service_registry import ServiceRegistry
from mcp_gateway.auth.models import AuthStrategy

# Initialize registry with authentication support
registry = ServiceRegistry(config_path=Path("config/services.yaml"), auth_config=auth_config)
await registry.load_services()

# Get service authentication configuration
auth_config = await registry.get_service_auth("my-service")
if auth_config.auth_strategy == AuthStrategy.OBO_REQUIRED:
    # Use OBO token exchange
    pass
elif auth_config.auth_strategy == AuthStrategy.PASSTHROUGH:
    # Pass user token directly
    pass
```

### Authentication Strategies

The system supports four authentication strategies defined in the `AuthStrategy` enum:

- **`NO_AUTH`**: No authentication required (public services)
- **`PASSTHROUGH`**: Pass user token directly to service
- **`OBO_PREFERRED`**: Use OBO if available, fallback to passthrough
- **`OBO_REQUIRED`**: Always use OBO token exchange (fails if unavailable)

### Service-Specific Configuration

Each service can have its own authentication configuration:

```yaml
services:
  secure-analytics:
    auth:
      strategy: "obo_required"
      target_audience: "analytics-api"
      required_scopes: ["analytics:read", "mcp:call"]
      custom_headers:
        "X-Service-Name": "mcp-gateway"
        "X-Version": "1.0.0"
        
  legacy-service:
    auth:
      strategy: "passthrough"
      required_scopes: ["legacy:access"]
      custom_headers:
        "X-Gateway": "mcp-gateway"
```

## API Integration

### Dependency Injection

```python
from mcp_gateway.auth.authentication_middleware import get_current_user, require_authentication
from mcp_gateway.core.service_registry import ServiceRegistry

@router.get("/protected-endpoint")
async def protected_endpoint(
    user: UserContext = Depends(require_authentication),
    registry: ServiceRegistry = Depends(get_service_registry)
):
    return {"user_id": user.user_id, "scopes": user.scopes}

@router.get("/services/{service_id}")
async def get_service_detail(
    service_id: str,
    registry: ServiceRegistry = Depends(get_service_registry)
):
    service = await registry.get_service(service_id)
    auth_config = await registry.get_service_auth(service_id)
    
    return {
        "service": service,
        "auth": {
            "strategy": auth_config.auth_strategy,
            "requires_obo": auth_config.auth_strategy in [AuthStrategy.OBO_REQUIRED, AuthStrategy.OBO_PREFERRED]
        }
    }
```

### Request Context

```python
# Access user information in route handlers
user = request.state.user  # UserContext object
token = request.state.access_token  # Original JWT token
claims = request.state.token_claims  # Parsed token claims
```

## Testing

### Unit Tests
- Comprehensive test suite for all components
- Mock-based testing for external dependencies
- Test coverage for error scenarios
- Performance testing for caching mechanisms

### Integration Tests
- End-to-end authentication flow testing
- Keycloak integration testing
- Service authentication testing
- Error handling validation

## Monitoring and Observability

### Logging
- Structured logging with correlation IDs
- Authentication success/failure events
- Token validation metrics
- OBO operation tracking

### Metrics
- Authentication latency
- Token validation success rate
- Cache hit ratios
- Error rate monitoring

### Security Monitoring
- Failed authentication attempts
- Unusual access patterns
- Token validation errors
- Service authentication failures

## Production Considerations

### Performance
- Implement Redis for distributed caching
- Monitor and tune cache TTL values
- Use connection pooling for HTTP clients
- Optimize JWKS refresh frequency

### Security
- Use HTTPS for all communications
- Rotate client secrets regularly
- Monitor for security vulnerabilities
- Implement rate limiting
- Regular security audits

### High Availability
- Multiple Keycloak instances
- Load balancing for gateway instances
- Health checks for all components
- Circuit breaker patterns for external calls

### Disaster Recovery
- Backup Keycloak configuration
- Document recovery procedures
- Test failover scenarios
- Monitor system dependencies

## Troubleshooting

### Common Issues

1. **Token Validation Failures**
   - Check Keycloak connectivity
   - Verify JWKS URL accessibility
   - Check clock synchronization
   - Validate issuer and audience configuration

2. **OBO Token Exchange Failures**
   - Verify client credentials
   - Check token exchange policy configuration
   - Validate target audience settings
   - Review scope requirements

3. **Service Authentication Issues**
   - Check service endpoint configuration
   - Verify OBO token scopes
   - Review service-specific auth requirements
   - Monitor token expiration

### Debug Mode
Enable detailed logging:
```bash
LOG_LEVEL=DEBUG
```

This provides comprehensive logs of the authentication process for troubleshooting.

## Future Enhancements

### Planned Features
- Support for multiple identity providers
- Advanced RBAC with fine-grained permissions
- Token refresh automation
- Enhanced monitoring and alerting
- Performance optimizations

### Extensibility
The authentication system is designed to be extensible:
- Custom token validators
- Additional identity providers
- Custom claim processors
- Service-specific authentication strategies

## Conclusion

This authentication system provides enterprise-grade security for the MCP Gateway while maintaining performance and usability. The modular design allows for easy customization and extension while following security best practices and industry standards.
