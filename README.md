# MCP Gateway

An open-source Model Context Protocol (MCP) Gateway for secure, scalable AI model interactions.

## Overview

The MCP Gateway acts as a centralized proxy and security layer for MCP servers, enabling secure access control, authentication, monitoring, and protocol bridging for AI model interactions.

## Features

### Current (Phase 1 - MVP)
- ✅ FastAPI-based async HTTP server
- ✅ Configurable service registry (YAML configuration)
- ✅ Structured logging with JSON output
- ✅ Health check endpoints
- ✅ Environment-based configuration with Pydantic
- ✅ Docker-ready containerization
- ✅ Comprehensive test suite with pytest

### Planned Features
- **Phase 2**: OAuth 2.0/OIDC authentication, RBAC, rate limiting
- **Phase 3**: Dynamic service discovery, policy engine (OPA), Prometheus metrics
- **Phase 4**: Multi-tenancy, audit logging, data masking

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
  example-mcp-server:
    name: "Example MCP Server"
    endpoint: "http://localhost:3000"
    transport: "http"
    timeout: 30
    enabled: true
```

## API Endpoints

- `GET /health` - Health check endpoint
- `GET /docs` - Interactive API documentation (debug mode only)

## Development

### Project Structure

```
src/mcp_gateway/           # Main application package
├── __init__.py
├── main.py               # Application entry point
└── core/                 # Core functionality
    ├── config.py         # Configuration management
    └── logging.py        # Logging setup
config/                   # Configuration files
├── services.yaml         # Service registry
tests/                    # Test suite
docs/                     # Documentation
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

- **Framework**: FastAPI with async/await support
- **Configuration**: Pydantic for settings validation
- **Logging**: Structlog for structured JSON logging
- **Testing**: pytest with coverage
- **Code Quality**: black, isort, flake8, mypy
- **Package Management**: uv for fast dependency resolution

### Design Principles

- **Security First**: Secure defaults and zero-trust architecture
- **Cloud Native**: Container-ready with health checks and metrics
- **Developer Experience**: Comprehensive tooling and documentation
- **Performance**: Async/await for high concurrency
- **Observability**: Structured logging and metrics built-in

## Roadmap

See our [Product Requirements Document](docs/MCP_Gateway_PRD.md) for detailed feature roadmap and technical specifications.

## License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

## Support

- 📖 [Documentation](docs/)
- 🐛 [Issue Tracker](https://github.com/your-org/mcp-gateway/issues)
- 💬 [Discussions](https://github.com/your-org/mcp-gateway/discussions)
