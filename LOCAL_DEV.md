# Local Development Setup

This guide explains how to run the MCP Gateway locally for quick debugging and development.

## Prerequisites

- Python 3.12+
- Docker (for Keycloak)
- Git

## Quick Start

### 1. Start Keycloak (Required for Authentication)

```bash
# Start only Keycloak from Docker Compose
docker-compose up -d keycloak
```

Wait for Keycloak to be healthy (check with `docker-compose ps`).

### 2. Run Gateway Locally

**Option A: Using PowerShell script (Windows)**
```powershell
.\run_local.ps1
```

**Option B: Manual setup**
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
.\venv\Scripts\activate
# Or on Linux/Mac:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set Python path
$env:PYTHONPATH = "$PWD\src;$env:PYTHONPATH"  # Windows PowerShell
# export PYTHONPATH="$PWD/src:$PYTHONPATH"    # Linux/Mac

# Run the gateway
python run_local.py
```

### 3. Test the Gateway

The gateway will be available at:
- **Health endpoint**: http://localhost:8000/health
- **API docs**: http://localhost:8000/docs
- **Dashboard**: http://localhost:8000/api/v1/dashboard/services

## Configuration

The `.env` file contains all configuration for local development. Key settings:

- `DEBUG=true` - Enables debug logging and auto-reload
- `KEYCLOAK_SERVER_URL=http://localhost:8080` - Points to local Keycloak
- `REQUIRED_SCOPES=[]` - No required scopes for easier testing

## Testing Authentication

Use the integration test to verify authentication:

```bash
python tests\integration\test_mcp_gateway_simple.py
```

## Debugging

When running locally:
- All logs are printed to console
- Auto-reload is enabled (code changes restart the server)
- Debug level logging shows detailed authentication flow
- No Docker rebuild needed for code changes

## Stopping

- **Gateway**: Press `Ctrl+C` in the terminal
- **Keycloak**: `docker-compose stop keycloak`

## Troubleshooting

1. **Import errors**: Make sure `PYTHONPATH` includes the `src` directory
2. **Keycloak connection failed**: Ensure Keycloak is running and healthy
3. **Port conflicts**: Change `PORT` in `.env` if 8000 is in use
