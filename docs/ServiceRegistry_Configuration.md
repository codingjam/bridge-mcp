# ServiceRegistry Configuration Guide

> **Configuration-driven service discovery and authentication management for MCP Gateway**

## Status

**✅ Production Ready**: The ServiceRegistry system is fully implemented and operational as of Phase 1 completion (August 2025). All authentication strategies and configuration options described here are working in production.

**🔄 MCP Integration**: Currently being enhanced in Phase 2 to support MCP protocol compliance with Streamable HTTP transport and Python MCP SDK integration.

## Overview

The ServiceRegistry is the central component of the MCP Gateway that manages service discovery, configuration, and authentication strategies. It provides a configuration-driven approach to defining how the gateway interacts with MCP services, including authentication requirements and service-specific settings.

## Architecture

The ServiceRegistry bridges YAML configuration files with the gateway's runtime authentication and proxy systems:

```
services.yaml → ServiceRegistry → Authentication Models → API Routes
```

### Key Components

1. **MCPService Model**: Defines service endpoints, transport, and basic configuration
2. **MCPServiceAuth Model**: Defines authentication strategies and requirements per service
3. **ServiceRegistry Class**: Loads and manages service and authentication configurations
4. **AuthStrategy Enum**: Defines available authentication strategies

## Configuration File Structure

### Basic Service Configuration

```yaml
# config/services.yaml
services:
  example-service:
    name: "Example MCP Server"
    description: "A sample MCP server for demonstration"
    endpoint: "http://localhost:3000"
    transport: "http"
    health_check_path: "/health"
    timeout: 30
    enabled: true
    version: "1.0.0"
    tags: ["example", "demo"]
    
    # Authentication configuration
    auth:
      strategy: "obo_required"
      target_audience: "example-service"
      required_scopes: ["mcp:call", "example:read"]
      custom_headers:
        "X-Service-Name": "mcp-gateway"
        "X-Version": "1.0.0"
      cache_tokens: true
      custom_cache_ttl: 1800

# Global configuration
global:
  default_timeout: 30
  health_check_interval: 60
  enable_service_discovery: false
  enable_health_checks: true
```

## Authentication Strategies

The ServiceRegistry supports four authentication strategies defined in the `AuthStrategy` enum:

### 1. NO_AUTH
```yaml
auth:
  strategy: "no_auth"
```
- **Use Case**: Public services that don't require authentication
- **Behavior**: No authentication headers are sent
- **Example**: Public documentation APIs, health check endpoints

### 2. PASSTHROUGH
```yaml
auth:
  strategy: "passthrough"
  required_scopes: ["legacy:access"]
  custom_headers:
    "X-Gateway": "mcp-gateway"
```
- **Use Case**: Legacy services that accept user tokens directly
- **Behavior**: User's JWT token is forwarded as-is to the service
- **Example**: Legacy systems that validate JWT tokens themselves

### 3. OBO_PREFERRED
```yaml
auth:
  strategy: "obo_preferred"
  target_audience: "flexible-service"
  required_scopes: ["service:read"]
```
- **Use Case**: Services that prefer service-specific tokens but can fallback
- **Behavior**: Attempts OBO token exchange, falls back to passthrough if OBO fails
- **Example**: Services being migrated to use service-specific tokens

### 4. OBO_REQUIRED
```yaml
auth:
  strategy: "obo_required"
  target_audience: "secure-service"
  required_scopes: ["service:read", "service:write"]
  custom_headers:
    "X-Service-Name": "mcp-gateway"
```
- **Use Case**: Secure services requiring service-specific tokens
- **Behavior**: Always performs OBO token exchange, fails if unavailable
- **Example**: Financial services, healthcare systems, production databases

## Advanced Configuration Options

### Custom Headers
Add service-specific headers to all requests:

```yaml
auth:
  custom_headers:
    "X-Service-Name": "mcp-gateway"
    "X-Version": "1.0.0"
    "X-Client-ID": "gateway-client"
    "Content-Type": "application/json"
```

### Token Caching
Control token caching behavior:

```yaml
auth:
  cache_tokens: true              # Enable/disable token caching
  custom_cache_ttl: 1800         # Custom TTL in seconds (30 minutes)
```

### Timeout Configuration
Set service-specific timeouts:

```yaml
auth:
  auth_timeout: 10.0             # Authentication timeout (seconds)
  max_auth_retries: 3            # Max retry attempts for auth failures
```

### Transport-Specific Configuration

#### HTTP Services
```yaml
services:
  http-service:
    transport: "http"
    endpoint: "https://api.example.com"
    base_path: "/api/v1"          # Prepended to all requests
    health_check_path: "/health"
```

#### Stdio Services
```yaml
services:
  local-service:
    transport: "stdio"
    endpoint: "local-mcp-server"
    command: ["python", "-m", "my_mcp_server"]
    working_directory: "/path/to/server"
    environment:
      PYTHONPATH: "/custom/path"
      DEBUG: "true"
```

## ServiceRegistry Usage

### Initialization
```python
from mcp_gateway.core.service_registry import ServiceRegistry
from mcp_gateway.core.config import Settings
from pathlib import Path

# Initialize with configuration
settings = Settings()
auth_config = settings.get_auth_config()
registry = ServiceRegistry(
    config_path=Path("config/services.yaml"),
    auth_config=auth_config
)

# Load services and authentication configurations
await registry.load_services()
```

### Service Discovery
```python
# Get all services
all_services = registry.services

# Get specific service
service = await registry.get_service("example-service")
if service:
    print(f"Service: {service.name}")
    print(f"Endpoint: {service.endpoint}")
    print(f"Enabled: {service.enabled}")
```

### Authentication Configuration Access
```python
# Get authentication configuration for a service
auth_config = await registry.get_service_auth("example-service")
if auth_config:
    print(f"Strategy: {auth_config.auth_strategy}")
    print(f"Target audience: {auth_config.target_audience}")
    print(f"Required scopes: {auth_config.required_scopes}")
```

### Service Filtering
```python
from mcp_gateway.auth.models import AuthStrategy

# Get services by authentication strategy
obo_services = await registry.get_services_with_auth_strategy(
    AuthStrategy.OBO_REQUIRED
)

# Get services by transport
http_services = await registry.get_services_by_transport("http")

# Get services by tag
database_services = await registry.get_services_by_tag("database")
```

## Integration with FastAPI

### Dependency Injection
```python
from fastapi import Depends
from mcp_gateway.core.service_registry import ServiceRegistry

async def get_service_registry() -> ServiceRegistry:
    return app.state.service_registry

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
            "target_audience": auth_config.target_audience,
            "requires_obo": auth_config.auth_strategy in [
                AuthStrategy.OBO_REQUIRED, 
                AuthStrategy.OBO_PREFERRED
            ]
        }
    }
```

### Application Startup
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    registry = await create_service_registry()
    app.state.service_registry = registry
    
    yield
    
    # Shutdown
    # Cleanup if needed

app = FastAPI(lifespan=lifespan)
```

## Validation and Error Handling

The ServiceRegistry provides comprehensive validation:

### Service Validation
- **Required fields**: name, endpoint, transport
- **Transport validation**: Must be "http" or "stdio"
- **URL validation**: HTTP endpoints must be valid URLs
- **Command validation**: Stdio services must have valid commands

### Authentication Validation
- **Strategy validation**: Must be valid AuthStrategy enum value
- **Audience validation**: Required for OBO strategies
- **Scope validation**: Must be list of strings
- **Header validation**: Must be string key-value pairs

### Error Handling
```python
try:
    await registry.load_services()
except FileNotFoundError:
    logger.error("Services configuration file not found")
except yaml.YAMLError as e:
    logger.error(f"Invalid YAML configuration: {e}")
except ValidationError as e:
    logger.error(f"Configuration validation failed: {e}")
```

## Health Monitoring

### Service Health Checks
```python
# Check individual service health
is_healthy = await registry.check_service_health("example-service")

# Get health status for all services
health_status = registry.get_health_status()
for service_id, is_healthy in health_status.items():
    print(f"{service_id}: {'healthy' if is_healthy else 'unhealthy'}")
```

### Health Check Configuration
```yaml
services:
  example-service:
    health_check_path: "/api/health"  # Custom health endpoint
    timeout: 5.0                      # Health check timeout
```

## Best Practices

### Configuration Management
1. **Environment-specific configs**: Use different YAML files for dev/staging/prod
2. **Secret management**: Store sensitive values in environment variables
3. **Validation**: Always validate configuration before deployment
4. **Documentation**: Document service-specific requirements

### Security
1. **Least privilege**: Use minimum required scopes for each service
2. **Token caching**: Enable caching for performance, but consider security implications
3. **Audit trails**: Log authentication strategy usage
4. **Regular rotation**: Rotate OBO client credentials regularly

### Performance
1. **Health checks**: Configure appropriate health check intervals
2. **Timeouts**: Set reasonable timeouts for each service
3. **Caching**: Use token caching for frequently accessed services

### Monitoring
1. **Service metrics**: Monitor service health and response times
2. **Authentication metrics**: Track OBO token exchange success/failure rates
3. **Error tracking**: Monitor authentication and service call failures
4. **Capacity planning**: Monitor connection and resource usage

## Migration Guide

### From Hardcoded to Configuration-Driven

**Before (Hardcoded)**:
```python
# Old approach - hardcoded service auth
if service_id == "secure-service":
    auth_strategy = AuthStrategy.OBO_REQUIRED
    target_audience = "secure-service"
elif service_id == "legacy-service":
    auth_strategy = AuthStrategy.PASSTHROUGH
```

**After (Configuration-Driven)**:
```yaml
# New approach - YAML configuration
services:
  secure-service:
    auth:
      strategy: "obo_required"
      target_audience: "secure-service"
  
  legacy-service:
    auth:
      strategy: "passthrough"
```

```python
# Runtime usage
auth_config = await registry.get_service_auth(service_id)
auth_strategy = auth_config.auth_strategy
target_audience = auth_config.target_audience
```

## Example Configurations

### Microservices Architecture
```yaml
services:
  user-service:
    name: "User Management Service"
    endpoint: "http://user-service:8080"
    auth:
      strategy: "obo_required"
      target_audience: "user-service"
      required_scopes: ["user:read", "user:write"]
  
  notification-service:
    name: "Notification Service"
    endpoint: "http://notification-service:8080"
    auth:
      strategy: "obo_required"
      target_audience: "notification-service"
      required_scopes: ["notification:send"]
  
  public-docs:
    name: "Public Documentation"
    endpoint: "http://docs-service:8080"
    auth:
      strategy: "no_auth"
```

### Hybrid Environment
```yaml
services:
  modern-api:
    name: "Modern Microservice"
    endpoint: "https://api.modern-service.com"
    auth:
      strategy: "obo_required"
      target_audience: "modern-api"
      custom_headers:
        "X-API-Version": "v2"
  
  legacy-system:
    name: "Legacy System"
    endpoint: "https://legacy.company.com"
    auth:
      strategy: "passthrough"
      custom_headers:
        "X-Legacy-Client": "mcp-gateway"
  
  local-tool:
    name: "Local Development Tool"
    transport: "stdio"
    command: ["python", "local_tool.py"]
    auth:
      strategy: "no_auth"
```

## Troubleshooting

### Common Issues

1. **Service Not Found**
   ```
   Error: Service 'my-service' not found in registry
   ```
   - Check service is defined in services.yaml
   - Verify service ID matches exactly (case-sensitive)
   - Ensure services.yaml is loaded correctly

2. **Invalid Authentication Strategy**
   ```
   Error: Invalid auth strategy 'invalid_strategy'
   ```
   - Use valid strategy: no_auth, passthrough, obo_preferred, obo_required
   - Check for typos in strategy name

3. **OBO Configuration Missing**
   ```
   Error: target_audience required for OBO strategies
   ```
   - Add target_audience for obo_required/obo_preferred strategies
   - Verify Keycloak client configuration

4. **Service Health Check Failures**
   ```
   Error: Health check failed for service 'my-service'
   ```
   - Verify service endpoint is accessible
   - Check health_check_path configuration
   - Review service logs for errors

### Debug Mode
```python
import logging
logging.getLogger("mcp_gateway.core.service_registry").setLevel(logging.DEBUG)
```

This provides detailed logs of service loading and authentication configuration parsing.
