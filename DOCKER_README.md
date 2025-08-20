# MCP Gateway Docker Setup

This directory contains Docker configuration for running the MCP Gateway with Keycloak authentication using a shared external network for communication with other services.

## Architecture

The setup uses an external Docker network (`mcp-shared`) that allows multiple docker-compose projects to communicate with each other. This is ideal when you have:

- MCP Gateway and Keycloak (this compose file)
- Separate MCP servers (other compose files)
- Additional services that need to communicate

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- For Keycloak setup: Git Bash (Windows) or bash shell (Linux/Mac)
- `curl` and `jq` for testing scripts

### 1. Start Services

```bash
# Windows
start.bat start

# Linux/Mac/Git Bash
./start.sh start
```

### 2. Set Up Keycloak

Access the Keycloak admin console at http://localhost:8080 and configure manually:
- Login with `admin/admin123`
- Create realm, clients, scopes, and users as needed
- See the Manual Configuration section below for details

### 3. Test Your Setup

Test the services directly:
```bash
# Test Keycloak
curl http://localhost:8080/health/ready

# Test MCP Gateway  
curl http://localhost:8000/api/v1/health
```

## Service URLs

- **MCP Gateway**: http://localhost:8000
- **Keycloak Admin Console**: http://localhost:8080 (admin/admin123)
- **Gateway API Docs**: http://localhost:8000/docs

## Files Overview

### Docker Configuration

- **`Dockerfile`**: Multi-stage build for MCP Gateway
- **`docker-compose.yml`**: Complete stack with Keycloak and Gateway
- **`.dockerignore`**: Optimized for smaller images

### Scripts

- **`start.sh`** / **`start.bat`**: Main orchestration script

### Configuration

- **`requirements.txt`**: Python dependencies
- **`config/services.yaml`**: MCP service definitions

## Detailed Commands

### Service Management

```bash
# Start all services
./start.sh start

# Stop all services  
./start.sh stop

# Restart services
./start.sh restart

# View service status
./start.sh status

# Clean everything (removes data!)
./start.sh clean
```

### Logging

```bash
# All service logs
./start.sh logs

# Specific service logs
./start.sh logs mcp-gateway
./start.sh logs keycloak
```

### Development

```bash
# Open shell in gateway container
./start.sh shell

# Open shell in specific container
./start.sh shell keycloak
```

## Network Management

### Shared Network

The setup automatically creates and uses an external network called `mcp-shared`. This allows multiple docker-compose projects to communicate.

```bash
# View network details
docker network inspect mcp-shared

# List containers on the network
docker network inspect mcp-shared | jq '.[0].Containers'

# Manually create network (done automatically by start scripts)
docker network create mcp-shared

# Remove network (only when no containers are connected)
docker network rm mcp-shared
```

### Troubleshooting Network Issues

```bash
# Check if network exists
docker network ls | grep mcp-shared

# See which containers are connected
docker network inspect mcp-shared

# Test connectivity between containers
docker exec mcp-gateway ping keycloak
docker exec mcp-gateway ping your-mcp-server

# Check DNS resolution
docker exec mcp-gateway nslookup keycloak
```

## Configuration Details

### Environment Variables

The docker-compose.yml sets these key environment variables:

```yaml
# Authentication
ENABLE_AUTH=true
KEYCLOAK_SERVER_URL=http://keycloak:8080
KEYCLOAK_REALM=mcp-gateway
KEYCLOAK_CLIENT_ID=mcp-gateway
KEYCLOAK_CLIENT_SECRET=your-client-secret

# Token validation  
TOKEN_AUDIENCE=mcp-gateway
TOKEN_ISSUER=http://keycloak:8080/realms/mcp-gateway

# OBO (On-Behalf-Of) flow
ENABLE_OBO=true
OBO_CACHE_TTL=1800

# Security
REQUIRED_SCOPES=["mcp:read","mcp:call"]
CORS_ORIGINS=["http://localhost:3000","http://localhost:8000","http://localhost:8080"]
```

### Keycloak Setup

Manual configuration via web UI at http://localhost:8080:

1. **Create Realm**: `mcp-gateway`
2. **Create Confidential Client** (`mcp-gateway`):
   - Client Type: Confidential
   - Service Account: Enabled
   - OAuth 2.0 Token Exchange: Enabled
   - Note the client secret from Credentials tab
3. **Create Public Client** (`mcp-web-client`):
   - Client Type: Public
   - Direct Access Grants: Enabled
4. **Create Scopes**: `mcp:read`, `mcp:call`, `analytics:read`
5. **Create Test User**: username `testuser`, password `testpass123`

Update your docker-compose.yml with the actual client secret.

### Service Configuration

Edit `config/services.yaml` to define your MCP services:

```yaml
services:
  your-external-service:
    name: "Your External MCP Service"
    transport: "http"
    endpoint: "http://host.docker.internal:3000"  # External service
    enabled: true
    auth:
      strategy: "obo_required"  # or "passthrough", "no_auth"
      target_audience: "your-service"
      required_scopes: ["mcp:call"]
```

## Testing

### Manual Testing

```bash
# Get access token
TOKEN=$(curl -s -X POST "http://localhost:8080/realms/mcp-gateway/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=mcp-web-client" \
  -d "username=testuser" \
  -d "password=testpass123" \
  -d "scope=openid profile mcp:read mcp:call" | jq -r '.access_token')

# Test authenticated endpoint
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/services

# Test service proxy (replace 'your-service' with actual service ID)
curl -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"method": "list_tools", "params": {}}' \
  http://localhost:8000/api/v1/mcp/your-service/call
```

### Automated Testing

Test the services manually:

```bash
# Get access token
TOKEN=$(curl -s -X POST "http://localhost:8080/realms/mcp-gateway/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=mcp-web-client" \
  -d "username=testuser" \
  -d "password=testpass123" \
  -d "scope=openid profile mcp:read mcp:call" | jq -r '.access_token')

# Test authenticated endpoint
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/services

# Test service proxy (replace 'your-service' with actual service ID)
curl -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"method": "list_tools", "params": {}}' \
  http://localhost:8000/api/v1/mcp/your-service/call
```

## Troubleshooting

### Common Issues

1. **Services not starting**
   ```bash
   # Check Docker
   docker info
   
   # Check logs
   ./start.sh logs
   ```

2. **Keycloak not ready**
   ```bash
   # Wait longer, then check
   curl http://localhost:8080/health/ready
   ```

3. **Authentication failures**
   ```bash
   # Verify Keycloak setup
   curl http://localhost:8080/realms/mcp-gateway/.well-known/openid_configuration
   
   # Check gateway logs
   ./start.sh logs mcp-gateway
   ```

4. **Port conflicts**
   ```bash
   # Check what's using ports
   netstat -tulpn | grep :8080
   netstat -tulpn | grep :8000
   ```

### Debug Mode

Enable debug logging by editing docker-compose.yml:

```yaml
environment:
  - LOG_LEVEL=DEBUG  # Change from INFO
```

### Health Checks

```bash
# Service health
./start.sh status

# Manual health checks
curl http://localhost:8000/api/v1/health
curl http://localhost:8080/health/ready
```

## Production Considerations

### Security

1. **Change default passwords**:
   - Keycloak admin: `admin/admin123`
   - Test user: `testuser/testpass123`
   - Client secret: `your-client-secret`

2. **Use external database** for Keycloak (replace dev-file)

3. **Enable HTTPS** with proper certificates

4. **Restrict CORS origins** to your actual domains

### Scaling

1. **External Keycloak**: Use managed Keycloak service
2. **Load balancing**: Add multiple gateway instances
3. **External Redis**: For distributed caching
4. **Monitoring**: Add Prometheus/Grafana

### Environment Variables

Create `.env` file for sensitive values:

```bash
KEYCLOAK_ADMIN_PASSWORD=secure-password
KEYCLOAK_CLIENT_SECRET=secure-client-secret
DATABASE_PASSWORD=secure-db-password
```

## Integration with External MCP Services

The shared network (`mcp-shared`) allows seamless communication between services across different docker-compose files.

### Same Network Communication

For services on the `mcp-shared` network, use container names directly:

```yaml
# config/services.yaml
services:
  your-mcp-service:
    endpoint: "http://your-mcp-server:3000"  # Direct container name
    auth:
      strategy: "obo_required"
      target_audience: "your-service"
```

### External Docker Compose

Your separate MCP service docker-compose.yml should join the same network:

```yaml
# your-mcp-service/docker-compose.yml
version: '3.8'

services:
  your-mcp-server:
    build: .
    container_name: your-mcp-server
    ports:
      - "3000:3000"
    networks:
      - mcp-shared
    # ... other configuration

networks:
  mcp-shared:
    external: true
```

### Manual Container Connection

For containers started manually:

```bash
# Connect existing container to shared network
docker network connect mcp-shared your-existing-container

# Run new container with shared network
docker run --network mcp-shared --name your-mcp-server your-image
```

### Host Services (Non-Docker)

For services running directly on the host:

```yaml
# config/services.yaml  
services:
  host-service:
    endpoint: "http://host.docker.internal:3000"  # Windows/Mac
    # endpoint: "http://172.17.0.1:3000"         # Linux (bridge gateway)
```

## Support

For issues and questions:

1. Check logs: `./start.sh logs`
2. Verify configuration: `./start.sh status`
3. Test authentication: `./test-auth.sh`
4. Review the main documentation in `docs/`
