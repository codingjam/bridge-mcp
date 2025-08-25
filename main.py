#!/usr/bin/env python3
"""
Main entry point for MCP Gateway when running locally in VS Code.
This file allows running the gateway directly from the project root.
"""

import sys
from pathlib import Path

# Add the src directory to Python path
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))


def main():
    """Run the MCP Gateway server."""
    import uvicorn
    from mcp_gateway.main import app
    
    print("Starting MCP Gateway locally...")
    print("Access at: http://localhost:8000")
    print("Health check: http://localhost:8000/health")
    print("API docs: http://localhost:8000/docs")
    
    # Run the server with VS Code debugging support
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="debug",
        reload=False  # Disable reload for debugging
    )


if __name__ == "__main__":
    main()
