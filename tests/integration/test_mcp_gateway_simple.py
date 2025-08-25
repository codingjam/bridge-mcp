#!/usr/bin/env python3
"""
Simple MCP Gateway Integration Test

Tests the MCP Gateway by simulating a real client:
1. Get user token from Keycloak
2. Call MCP Gateway endpoints
3. Let the gateway handle OBO and MCP protocol

Run: python tests/integration/test_mcp_gateway_simple.py
"""

import json
import logging
import requests
import sys

# Setup logging
logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s][%(name)s] %(message)s")
log = logging.getLogger("mcp_gateway_test")

# Configuration
KEYCLOAK_BASE = "http://localhost:8080"
REALM = "BridgeMCP"
TOKEN_URL = f"{KEYCLOAK_BASE}/realms/{REALM}/protocol/openid-connect/token"

# User credentials
USER_CLIENT = "mcp-web-client"
USERNAME = "jason@jason.com"
PASSWORD = "test123"

# Gateway
GATEWAY_BASE = "http://localhost:8000"

def get_user_token():
    """Get user access token from Keycloak."""
    log.info("Getting user token from Keycloak...")
    
    data = {
        "grant_type": "password",
        "client_id": USER_CLIENT,
        "username": USERNAME,
        "password": PASSWORD,
        "scope": "openid profile email"
    }
    
    response = requests.post(TOKEN_URL, data=data)
    response.raise_for_status()
    
    token_data = response.json()
    token = token_data["access_token"]
    log.info(f"✓ Got user token (length: {len(token)})")
    log.info(f"Token: {token}")
    
    # Also log token payload for debugging
    import base64
    try:
        parts = token.split(".")
        payload = parts[1]
        # Add padding if needed
        padding = len(payload) % 4
        if padding:
            payload += "=" * (4 - padding)
        decoded = base64.b64decode(payload)
        import json
        claims = json.loads(decoded)
        log.info(f"Token claims: {json.dumps(claims, indent=2)}")
    except Exception as e:
        log.warning(f"Could not decode token: {e}")
    
    return token

def test_gateway_health():
    """Test gateway health endpoint (unauthenticated)."""
    log.info("Testing gateway health...")
    
    response = requests.get(f"{GATEWAY_BASE}/health")
    if response.status_code == 200:
        log.info("✓ Gateway health OK")
        return True
    else:
        log.error(f"✗ Gateway health failed: {response.status_code}")
        return False

def test_mcp_connect(token):
    """Test MCP server connection via gateway."""
    log.info("Testing MCP server connect...")
    
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "server_name": "fin-assistant-mcp"
        # No transport_config - the gateway should get this from services.yaml
    }
    
    response = requests.post(
        f"{GATEWAY_BASE}/api/v1/mcp/servers/connect",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        data = response.json()
        session_id = data.get("session_id")
        log.info(f"✓ MCP connect successful, session: {session_id}")
        return session_id
    else:
        log.error(f"✗ MCP connect failed: {response.status_code} - {response.text}")
        return None

def test_mcp_tools_list(token, session_id):
    """Test listing MCP tools via gateway."""
    log.info("Testing MCP tools list...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(
        f"{GATEWAY_BASE}/api/v1/mcp/sessions/{session_id}/tools",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        tools = data.get("tools", [])
        log.info(f"✓ Got {len(tools)} tools")
        for tool in tools[:3]:  # Show first 3 tools
            log.info(f"  - {tool.get('name', 'Unknown')}")
        return tools
    else:
        log.error(f"✗ Tools list failed: {response.status_code} - {response.text}")
        return []

def test_mcp_tool_call(token, session_id, tool_name):
    """Test calling an MCP tool via gateway."""
    log.info(f"Testing MCP tool call: {tool_name}")
    
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "tool_name": tool_name,
        "arguments": {}
    }
    
    response = requests.post(
        f"{GATEWAY_BASE}/api/v1/mcp/sessions/{session_id}/tools/call",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        data = response.json()
        log.info(f"✓ Tool call successful")
        log.info(f"  Result preview: {str(data)[:200]}...")
        return True
    else:
        log.error(f"✗ Tool call failed: {response.status_code} - {response.text}")
        return False

def test_dashboard_services(token):
    """Test dashboard services endpoint."""
    log.info("Testing dashboard services...")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(
        f"{GATEWAY_BASE}/api/v1/dashboard/services",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        services = data.get("services", [])
        log.info(f"✓ Got {len(services)} services")
        return True
    else:
        log.error(f"✗ Dashboard services failed: {response.status_code} - {response.text}")
        return False

def main():
    """Run the integration test."""
    log.info("=== MCP Gateway Integration Test ===")
    
    try:
        # Get user token
        token = get_user_token()
        
        # Test gateway health
        if not test_gateway_health():
            sys.exit(1)
        
        # Test dashboard
        test_dashboard_services(token)
        
        # Test MCP flow
        session_id = test_mcp_connect(token)
        if session_id:
            tools = test_mcp_tools_list(token, session_id)
            if tools and len(tools) > 0:
                # Try to call the first tool
                first_tool = tools[0]["name"]
                test_mcp_tool_call(token, session_id, first_tool)
        
        log.info("✓ Integration test completed successfully!")
        
    except requests.exceptions.RequestException as e:
        log.error(f"✗ Network error: {e}")
        sys.exit(1)
    except Exception as e:
        log.error(f"✗ Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
