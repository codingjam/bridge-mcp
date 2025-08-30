#!/usr/bin/env python3
"""
SSE Streaming Integration Test

Tests the SSE streaming functionality added to the MCP Gateway:
1. Get user token from Keycloak
2. Call the new simulate_long_task tool with streaming enabled
3. Verify we receive incremental chunks via Server-Sent Events
4. Test both streaming and non-streaming modes

Run: python tests/integration/test_sse_streaming.py
"""

import json
import logging
import requests
import sys
import time
from typing import Iterator, Optional

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s][%(name)s] %(message)s")
log = logging.getLogger("sse_streaming_test")

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

def get_user_token() -> str:
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

def test_sse_streaming_tool_call(token: str) -> bool:
    """Test SSE streaming with the simulate_long_task tool."""
    log.info("=== Testing SSE Streaming Tool Call ===")
    
    # Test payload with streaming enabled
    payload = {
        "jsonrpc": "2.0",
        "id": "sse_test_001",
        "method": "tools/call",
        "params": {
            "server_name": "fin-assistant-mcp",
            "name": "simulate_long_task",
            "arguments": {
                "task": "sse_streaming_test",
                "steps": 5,
                "delay_seconds": 0.5
            },
            "stream": True  # Enable streaming via JSON-RPC params
        }
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream"  # Request SSE format
    }
    
    log.info(f"Sending streaming request to: {GATEWAY_BASE}/api/v1/mcp/proxy")
    log.info(f"Payload: {json.dumps(payload, indent=2)}")
    
    start_time = time.time()
    timeout = 15.0  # 15 second timeout
    
    try:
        response = requests.post(
            f"{GATEWAY_BASE}/api/v1/mcp/proxy",
            json=payload,
            headers=headers,
            stream=True,  # Enable streaming response
            timeout=timeout  # Add timeout to prevent hanging
        )
        
        log.info(f"Response status: {response.status_code}")
        log.info(f"Response headers: {dict(response.headers)}")
        
        if response.status_code != 200:
            log.error(f"✗ Request failed with status {response.status_code}")
            log.error(f"Response body: {response.text}")
            return False
        
        # Verify SSE headers
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" not in content_type:
            log.error(f"✗ Expected text/event-stream, got: {content_type}")
            return False
        
        log.info("✓ SSE headers correct")
        
        # Process SSE stream
        chunk_count = 0
        progress_chunks = 0
        result_chunks = 0
        
        for line in response.iter_lines(decode_unicode=True):
            # Check for timeout
            elapsed = time.time() - start_time
            if elapsed > timeout:
                log.error(f"✗ Stream timeout after {elapsed:.2f}s")
                return False
                
            if not line.strip():
                continue
                
            if line.startswith("data: "):
                chunk_count += 1
                data = line[6:]  # Remove "data: " prefix
                try:
                    chunk_data = json.loads(data)
                    elapsed = time.time() - start_time
                    
                    log.info(f"Chunk {chunk_count} (t+{elapsed:.2f}s): {chunk_data}")
                    
                    # Verify JSON-RPC envelope
                    if "jsonrpc" not in chunk_data or chunk_data["jsonrpc"] != "2.0":
                        log.error("✗ Missing or invalid JSON-RPC envelope")
                        return False
                    
                    if "id" not in chunk_data or chunk_data["id"] != "sse_test_001":
                        log.error("✗ Missing or invalid correlation ID")
                        return False
                    
                    # Check chunk content - support both old nested and new flattened structure
                    chunk_content = None
                    if "stream" in chunk_data:
                        # New flattened structure
                        chunk_content = chunk_data["stream"]
                    elif "chunk" in chunk_data:
                        # Old nested structure - extract from wrapper
                        chunk_wrapper = chunk_data["chunk"]
                        if "chunk" in chunk_wrapper:
                            chunk_content = chunk_wrapper["chunk"]
                        else:
                            chunk_content = chunk_wrapper
                    
                    if chunk_content:
                        if chunk_content.get("type") == "progress":
                            progress_chunks += 1
                            # Verify progress structure
                            required_fields = ["task", "step", "total_steps", "percent", "message"]
                            for field in required_fields:
                                if field not in chunk_content:
                                    log.error(f"✗ Missing progress field: {field}")
                                    return False
                            
                            log.info(f"  Progress: {chunk_content['step']}/{chunk_content['total_steps']} ({chunk_content['percent']}%)")
                            
                        elif chunk_content.get("type") == "result":
                            result_chunks += 1
                            # Verify result structure
                            required_fields = ["task", "duration_seconds", "summary"]
                            for field in required_fields:
                                if field not in chunk_content:
                                    log.error(f"✗ Missing result field: {field}")
                                    return False
                            
                            log.info(f"  Result: {chunk_content['summary']}")
                    
                except json.JSONDecodeError as e:
                    log.error(f"✗ Invalid JSON chunk: {data} - {e}")
                    return False
            
            elif line.startswith("event: "):
                event_type = line[7:]  # Remove "event: " prefix
                log.info(f"Event: {event_type}")
                
                if event_type == "end":
                    log.info("✓ Stream completed normally")
                    break
                elif event_type == "error":
                    log.error("✗ Stream error event received")
                    return False
        
        total_time = time.time() - start_time
        
        # Verify we got the expected chunks
        log.info(f"✓ Total chunks received: {chunk_count}")
        log.info(f"✓ Progress chunks: {progress_chunks}")
        log.info(f"✓ Result chunks: {result_chunks}")
        log.info(f"✓ Total time: {total_time:.2f}s")
        
        if progress_chunks != 5:  # We requested 5 steps
            log.error(f"✗ Expected 5 progress chunks, got {progress_chunks}")
            return False
        
        if result_chunks != 1:
            log.error(f"✗ Expected 1 result chunk, got {result_chunks}")
            return False
        
        log.info("✓ SSE streaming test passed!")
        return True
        
    except requests.exceptions.RequestException as e:
        log.error(f"✗ Request error: {e}")
        return False
    except Exception as e:
        log.error(f"✗ Unexpected error: {e}")
        return False

def test_non_streaming_tool_call(token: str) -> bool:
    """Test the same tool without streaming for comparison."""
    log.info("=== Testing Non-Streaming Tool Call (Fallback) ===")
    
    # Same payload but without streaming
    payload = {
        "jsonrpc": "2.0",
        "id": "non_stream_test_001",
        "method": "tools/call",
        "params": {
            "server_name": "fin-assistant-mcp",
            "name": "simulate_long_task",
            "arguments": {
                "task": "non_streaming_test",
                "steps": 3,
                "delay_seconds": 0.3
            }
            # No "stream": True
        }
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"  # Request JSON, not SSE
    }
    
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{GATEWAY_BASE}/api/v1/mcp/proxy",
            json=payload,
            headers=headers
        )
        
        log.info(f"Response status: {response.status_code}")
        
        if response.status_code != 200:
            log.error(f"✗ Request failed with status {response.status_code}")
            log.error(f"Response body: {response.text}")
            return False
        
        # Should get JSON response (not SSE)
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            log.error(f"✗ Expected application/json, got: {content_type}")
            return False
        
        response_data = response.json()
        total_time = time.time() - start_time
        
        log.info(f"✓ Non-streaming response received in {total_time:.2f}s")
        log.info(f"Response structure: {list(response_data.keys())}")
        
        # Verify JSON-RPC response structure
        if "jsonrpc" not in response_data or response_data["jsonrpc"] != "2.0":
            log.error("✗ Missing or invalid JSON-RPC envelope")
            return False
        
        if "id" not in response_data or response_data["id"] != "non_stream_test_001":
            log.error("✗ Missing or invalid correlation ID")
            return False
        
        if "result" not in response_data:
            log.error("✗ Missing result field")
            return False
        
        log.info("✓ Non-streaming test passed!")
        return True
        
    except Exception as e:
        log.error(f"✗ Error: {e}")
        return False

def test_tools_list(token: str) -> bool:
    """Test that the new simulate_long_task tool is available."""
    log.info("=== Testing Tools List ===")
    
    payload = {
        "jsonrpc": "2.0",
        "id": "tools_list_001",
        "method": "tools/list",
        "params": {
            "server_name": "fin-assistant-mcp"
        }
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            f"{GATEWAY_BASE}/api/v1/mcp/proxy",
            json=payload,
            headers=headers
        )
        
        if response.status_code != 200:
            log.error(f"✗ Tools list failed: {response.status_code} - {response.text}")
            return False
        
        response_data = response.json()
        tools = response_data.get("result", {}).get("tools", [])
        
        log.info(f"✓ Found {len(tools)} tools:")
        tool_names = []
        for tool in tools:
            tool_name = tool.get("name", "unknown")
            tool_names.append(tool_name)
            log.info(f"  - {tool_name}: {tool.get('description', 'no description')[:80]}...")
        
        if "simulate_long_task" not in tool_names:
            log.error("✗ simulate_long_task tool not found in tools list")
            return False
        
        log.info("✓ simulate_long_task tool found!")
        return True
        
    except Exception as e:
        log.error(f"✗ Error: {e}")
        return False

def test_gateway_health() -> bool:
    """Test gateway health endpoint."""
    log.info("Testing gateway health...")
    
    try:
        response = requests.get(f"{GATEWAY_BASE}/health")
        if response.status_code == 200:
            log.info("✓ Gateway health OK")
            return True
        else:
            log.error(f"✗ Gateway health failed: {response.status_code}")
            return False
    except Exception as e:
        log.error(f"✗ Gateway health error: {e}")
        return False

def main():
    """Run the SSE streaming integration test."""
    log.info("=== SSE Streaming Integration Test ===")
    
    try:
        # Test gateway health first
        if not test_gateway_health():
            log.error("Gateway is not healthy, aborting tests")
            sys.exit(1)
        
        # Get user token
        token = get_user_token()
        
        # Test tools list to verify our new tool is available
        if not test_tools_list(token):
            log.error("Tools list test failed, aborting")
            sys.exit(1)
        
        # Test non-streaming mode first (simpler)
        if not test_non_streaming_tool_call(token):
            log.error("Non-streaming test failed, aborting")
            sys.exit(1)
        
        # Test SSE streaming mode
        if not test_sse_streaming_tool_call(token):
            log.error("SSE streaming test failed")
            sys.exit(1)
        
        log.info("🎉 All SSE streaming tests passed successfully!")
        
    except requests.exceptions.ConnectionError as e:
        log.error(f"✗ Connection error: {e}")
        log.error("Make sure both the MCP Gateway (port 8000) and Keycloak (port 8080) are running")
        sys.exit(1)
    except Exception as e:
        log.error(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
