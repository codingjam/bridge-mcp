# Bridge MCP Gateway

An open-source Model Context Protocol (MCP) Gateway for secure, scalable, and protocol-compliant AI-tool integration with native MCP client support.

In modern enterprises, teams often deploy a diverse set of services, tools, and agents that need to interact securely and efficiently. The MCP Gateway provides a unified entry point for all MCP-compliant services, standardizing authentication, authorization, auditing, and protocol handling. By centralizing these concerns, the gateway reduces integration complexity, enforces consistent security policies, enables observability, and accelerates onboarding of new services—making it easier for organizations to scale, govern, and monitor their service ecosystem.

Unlike traditional HTTP proxies, the MCP Gateway provides native MCP protocol support with proper session management, connection pooling, and full compliance with the Model Context Protocol specification. This ensures optimal performance, reliability, and compatibility with all MCP-compliant services.

## Overview

The MCP Gateway acts as a centralized MCP-native proxy and security layer for MCP servers, enabling secure access control, authentication, monitoring, and native protocol support for any MCP-compliant service. Built with the official Python MCP SDK, it provides seamless protocol handling with advanced features like session management, connection pooling, and streamable HTTP transport.

## Features

### Current (Phase 2 - MCP Protocol Compliance) ✅
- ✅ **Native MCP Client SDK Integration** - Official Python MCP SDK with protocol compliance
- ✅ **Advanced Session Management** - Per-client session isolation with connection pooling and lifecycle management
- ✅ **MCP Initialize Handshake** - Proper MCP initialize/initialized flow implementation
- ✅ **Streamable HTTP Support** - Native MCP transport with proper endpoint handling (/mcp/, /mcp/stream, /mcp/send)
- ✅ **Transport Lifecycle Management** - Proper async context management for long-lived connections
- ✅ **Complete OIDC Authentication System** with Keycloak integration and JWT validation
- ✅ **OAuth2 On-Behalf-Of (OBO) Flow** with automatic token exchange and caching
- ✅ **Enhanced Error Handling** - TaskGroup exception capture with detailed sub-exception logging
- ✅ **Health check endpoints** with real-time service monitoring
- ✅ **Circuit Breaker Protection** - Per-server failure isolation with state machine (CLOSED/OPEN/HALF_OPEN)

### In Progress (Phase 3 - Advanced Features) 🚧
- 🟡 **Rate limiting system** (Redis-based distributed rate limiting)
- 🟡 **Comprehensive audit system** with structured logging and event tracking
- 🟡 **Advanced Monitoring Dashboard** - React/TypeScript UI for service management


### MCP Compliance Implementation
- 📄 [MCP Compliance Implementation Plan](docs/MCP_Compliance_Implementation_Plan.md)

### Planned Features (Phase 3+)
- **RBAC & Policy Engine**: Role-based access control with Open Policy Agent (OPA)
- **Advanced Monitoring**: Prometheus metrics and Grafana dashboards
- **Transport Bridging**: HTTP ↔ stdio protocol interoperability
- **Multi-tenancy**: Tenant isolation and resource quotas
- **Plugin Architecture**: Third-party integrations and community extensions

## Dashboard (Under Development)

The MCP Gateway includes a modern web-based dashboard for monitoring and managing your MCP services. The dashboard provides real-time insights into service health, performance metrics, and system status.

![Dashboard Overview](docs/screenshots/dashboard-overview.png)

### Dashboard Features
- **Service Management**: View and monitor all configured MCP services
- **Real-time Health Monitoring**: Live service health checks and status updates
- **Performance Metrics**: Response times, success rates, and system performance
- **System Overview**: Total requests, active services, and operational status
- **Responsive Design**: Modern UI built with React and Ant Design

### Accessing the Dashboard
1. Start the MCP Gateway server
2. Start the dashboard development server:
   ```bash
   cd dashboard
   npm install
   npm run dev
   ```
3. Open your browser to `http://localhost:5173`

*Note: The dashboard is currently under active development and new features are being added regularly.*

## Quick Start

### Prerequisites
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/mcp-gateway.git
   cd mcp-gateway
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Set up environment configuration:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Run the gateway:**
   ```bash
   uv run python -m mcp_gateway.main
   ```

The gateway will start on `http://127.0.0.1:8000` by default.

## Using the MCP Gateway

### Native MCP Client API

The gateway provides a RESTful API that wraps the native MCP protocol:

#### 1. Connect to an MCP Server
```bash
curl -X POST "http://localhost:8000/api/v1/mcp/servers/connect" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "server_name": "fin-assistant-mcp"
  }'
```

Response:
```json
{
  "session_id": "fin-assistant-mcp_123456",
  "server_name": "fin-assistant-mcp",
  "status": "connected"
}
```

#### 2. List Available Tools
```bash
curl -X GET "http://localhost:8000/api/v1/mcp/sessions/{session_id}/tools" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

#### 3. Call a Tool
```bash
curl -X POST "http://localhost:8000/api/v1/mcp/sessions/{session_id}/tools/call" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "get_statement",
    "arguments": {
      "account": "checking",
      "month": "2024-01"
    }
  }'
```

#### 4. List and Read Resources
```bash
# List resources
curl -X GET "http://localhost:8000/api/v1/mcp/sessions/{session_id}/resources" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Read a specific resource
curl -X POST "http://localhost:8000/api/v1/mcp/sessions/{session_id}/resources/read" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"uri": "file://statements/2024-01.pdf"}'
```

### Authentication Flow

The gateway handles OAuth2 On-Behalf-Of (OBO) token exchange automatically:

1. **Client authenticates** with Keycloak using their credentials
2. **Client calls gateway** with their JWT token
3. **Gateway exchanges** user token for service-specific token (OBO flow)
4. **Gateway connects** to MCP server using the service token
5. **All subsequent calls** use the established MCP session

### Integration Testing

Run the integration test to verify end-to-end functionality:

```bash
# Ensure both Keycloak and your MCP server are running
python tests/integration/test_mcp_gateway_simple.py
```

This test demonstrates:
- User authentication with Keycloak
- MCP server connection via gateway
- Tool listing and execution
- Proper session management

### Using with uv

This project uses [uv](https://github.com/astral-sh/uv) for fast, reliable Python package management:

```bash
# Install development dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Run with coverage
uv run pytest --cov=mcp_gateway --cov-report=html

# Format code
uv run black src tests
uv run isort src tests

# Type checking
uv run mypy src
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `127.0.0.1` | Server host address |
| `PORT` | `8000` | Server port |
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FORMAT` | `json` | Log format (json/text) |
| `SERVICE_REGISTRY_FILE` | `config/services.yaml` | Path to service registry |

### Service Registry

Configure MCP servers in `config/services.yaml`:

```yaml
services:
  fin-assistant-mcp:
    name: "Financial Assistant MCP"
    endpoint: "http://localhost:3000/mcp/"  # Note: trailing slash required for MCP
    transport: "http"  # Supports: http, stdio
    timeout: 30
    enabled: true
    auth:
      strategy: "obo_required"  # Options: none, passthrough, obo_required
      target_audience: "account"
      keycloak_server_url: "http://localhost:8080"
      realm: "BridgeMCP"
      client_id: "fin-mcp-server"
      token_issuer: "http://localhost:8080/realms/BridgeMCP"
      required_scopes: []
      custom_headers:
        X-Service-Name: "mcp-gateway"
        X-Version: "1.0.0"
  
  local-stdio-server:
    name: "Local STDIO MCP Server"
    transport: "stdio"
    command: ["python", "-m", "my_mcp_server"]
    working_directory: "/path/to/server"
    environment:
      MCP_SERVER_ENV: "production"
    enabled: true
    auth:
      strategy: "none"
```

## API Endpoints

### MCP Native Endpoints
- `POST /api/v1/mcp/servers/connect` - Connect to MCP server with session management
- `GET /api/v1/mcp/sessions/{session_id}/tools` - List tools from connected MCP server
- `POST /api/v1/mcp/sessions/{session_id}/tools/call` - Call MCP tool with native protocol
- `GET /api/v1/mcp/sessions/{session_id}/resources` - List MCP server resources
- `POST /api/v1/mcp/sessions/{session_id}/resources/read` - Read MCP server resource
- `GET /api/v1/mcp/sessions/{session_id}/prompts` - List MCP server prompts
- `GET /api/v1/mcp/sessions/{session_id}/info` - Get MCP server information
- `DELETE /api/v1/mcp/sessions/{session_id}` - Close MCP session

### Core Endpoints
- `GET /health` - Health check endpoint
- `GET /docs` - Interactive API documentation (debug mode only)
- `GET /api/v1/services` - List all configured MCP services
- `GET /api/v1/services/{service_id}` - Get detailed service information
- `GET /api/v1/services/{service_id}/health` - Check specific service health

### Dashboard API Endpoints
- `GET /api/v1/dashboard/overview` - Dashboard overview metrics
- `GET /api/v1/dashboard/services/health` - Service health summary for dashboard

*See `/docs` for complete API documentation when running in debug mode.*

## Development

### Project Structure

```
src/mcp_gateway/           # Main application package
├── __init__.py
├── main.py               # Application entry point
├── routers/              # FastAPI routers and endpoints
│   ├── mcp_client.py     # Native MCP client endpoints
│   ├── routes.py         # Legacy/proxy routes
│   ├── dashboard_routes.py # Dashboard-specific API routes
│   └── models/           # Pydantic models for API
├── mcp/                  # Native MCP implementation
│   ├── client_wrapper.py # High-level MCP client wrapper
│   ├── session_manager.py # MCP session lifecycle management
│   ├── transport_factory.py # MCP transport creation (HTTP, stdio)
│   ├── service_adapter.py # Service registry integration
│   └── exceptions.py     # MCP-specific exceptions
├── core/                 # Core functionality
│   ├── config.py         # Configuration management
│   ├── logging.py        # Structured logging setup
│   ├── service_registry.py # Service registry management
│   ├── authenticated_proxy.py # Legacy proxy with auth
│   └── errors.py         # Application-wide error handling
├── auth/                 # Authentication modules
│   ├── authentication_middleware.py # OIDC/JWT middleware
│   ├── obo_service.py    # OAuth2 On-Behalf-Of implementation
│   └── models.py         # Authentication data models
└── utils/               # Utility functions
dashboard/                # React-based web dashboard
├── src/                  # Dashboard source code
├── public/               # Static assets
└── package.json          # Dashboard dependencies
config/                   # Configuration files
├── services.yaml         # Service registry with MCP endpoints
tests/                    # Test suite
├── integration/          # End-to-end integration tests
└── unit/                 # Unit tests
docs/                     # Documentation
└── screenshots/          # Dashboard screenshots
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=mcp_gateway --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_config.py -v
```

### Code Quality

This project uses several tools for code quality:

```bash
# Format code
uv run black src tests
uv run isort src tests

# Lint code
uv run flake8 src tests

# Type checking
uv run mypy src

# Run all quality checks
uv run pre-commit run --all-files
```

## Docker Deployment

(Docker configuration coming in Phase 1 completion)

## Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup

1. Fork and clone the repository
2. Install dependencies: `uv sync --extra dev`
3. Make your changes
4. Run tests: `uv run pytest`
5. Submit a pull request

## Architecture

### Technology Stack

- **Framework**: FastAPI with async/await support and native MCP protocol compliance
- **MCP Integration**: Official Python MCP SDK (v1.11.0+) with session management and streaming
- **Session Management**: Advanced connection pooling with proper lifecycle management and cleanup
- **Transport Support**: HTTP (streamable) and stdio transports with automatic failover
- **Authentication**: Authlib for OAuth/OIDC, OBO token exchange with Keycloak integration
- **Rate Limiting**: Redis-based distributed rate limiting with configurable policies
- **Configuration**: Pydantic for settings validation and environment variables
- **Logging**: Structlog for structured JSON logging with audit trails and debug capabilities
- **Testing**: pytest with comprehensive coverage, integration tests, and contract testing
- **Code Quality**: black, isort, flake8, mypy with pre-commit hooks
- **Package Management**: uv for fast dependency resolution and virtual environments
- **Frontend**: React/TypeScript dashboard with Ant Design components (planned)

### Design Principles

- **MCP Native First**: Full native implementation using official MCP SDK for optimal performance
- **Protocol Compliance**: 100% adherence to Model Context Protocol specification with proper session handling
- **Security First**: Secure defaults, zero-trust architecture, and comprehensive audit trails
- **Connection Lifecycle**: Proper async context management with resource cleanup and connection pooling
- **Cloud Native**: Container-ready with health checks, metrics, and horizontal scaling support
- **Developer Experience**: Comprehensive tooling, documentation, and clear contribution guidelines
- **Performance**: Async/await for high concurrency with efficient session pooling and transport reuse
- **Observability**: Structured logging, metrics, tracing, and real-time monitoring built-in
- **Fault Tolerance**: Circuit breakers, retries, and graceful degradation for production reliability

## Roadmap

### Current Status: Phase 2 Complete ✅
**MCP Protocol Compliance** - Successfully implemented full Model Context Protocol support with native client integration, advanced session management, and streamable HTTP transport.

**Branch**: `mcp-spec-compliance` → merging to `main`  
**Status**: Phase 2 implementation complete with native MCP SDK integration  
**Next**: Phase 3 advanced features (circuit breakers, enhanced monitoring, multi-transport bridging)

### Key Achievements
- ✅ **Native MCP Client**: Full implementation using official Python MCP SDK
- ✅ **Session Management**: Advanced connection pooling with proper lifecycle management
- ✅ **Transport Support**: HTTP (streamable) and stdio transports with proper cleanup
- ✅ **Authentication Integration**: Seamless OBO token flow with MCP connections
- ✅ **Protocol Compliance**: 100% adherence to MCP specification with proper handshakes
- ✅ **Circuit Breaker Pattern**: Comprehensive failure isolation with state machine and per-server protection
- ✅ **Production Ready**: Comprehensive error handling, logging, and monitoring

### Detailed Roadmap
See our [Product Requirements Document](docs/MCP_Gateway_PRD.md) for detailed feature roadmap, technical specifications, and implementation phases.

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

## Support & Community

- 📖 **Documentation**: [Technical Docs](docs/) | [Implementation Plan](docs/MCP_Compliance_Implementation_Plan.md)
- 🐛 **Issue Tracker**: [GitHub Issues](https://github.com/codingjam/bridge-mcp/issues) for bug reports and feature requests
- 💬 **Discussions**: [GitHub Discussions](https://github.com/codingjam/bridge-mcp/discussions) for questions and community chat
- 🤝 **Contributing**: See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines
- 📧 **Contact**: Reach out via GitHub Issues or Discussions for project-related inquiries

### Getting Help
1. **Check existing issues** - Your question might already be answered
2. **Browse the documentation** - Comprehensive guides and API references
3. **Start a discussion** - For questions, ideas, or general community interaction
4. **Open an issue** - For bug reports or specific feature requests
