"""
Test script for MCP Gateway proxy functionality
Tests the running gateway server with real HTTP requests
"""
import asyncio
import json
import httpx


async def test_gateway():
    """Test the MCP Gateway server"""
    base_url = "http://127.0.0.1:8000"
    
    async with httpx.AsyncClient() as client:
        print("🚀 Testing MCP Gateway...")
        
        # Test root endpoint
        print("\n1. Root endpoint:")
        response = await client.get(base_url)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Service: {data.get('service')}")
            print(f"   Version: {data.get('version')}")
        
        # Test health endpoint
        print("\n2. Health endpoint:")
        response = await client.get(f"{base_url}/api/v1/health")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Health: {data.get('status')}")
        
        # Test services listing
        print("\n3. Services listing:")
        response = await client.get(f"{base_url}/api/v1/services")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Service count: {data.get('count')}")
            for service_id, service in data.get('services', {}).items():
                print(f"   - {service_id}: {service.get('name')} ({service.get('transport')})")
        
        # Test specific service info
        print("\n4. Service details:")
        response = await client.get(f"{base_url}/api/v1/services/example-mcp-server")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Name: {data.get('name')}")
            print(f"   Endpoint: {data.get('endpoint')}")
            print(f"   Enabled: {data.get('enabled')}")
        
        # Test service health check
        print("\n5. Service health check:")
        response = await client.get(f"{base_url}/api/v1/services/example-mcp-server/health")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Healthy: {data.get('healthy')}")
            print(f"   Health status: {data.get('status')}")
        
        # Test proxy request (will likely fail since localhost:3000 doesn't exist)
        print("\n6. Proxy request test:")
        try:
            response = await client.get(f"{base_url}/api/v1/proxy/example-mcp-server/health", timeout=5.0)
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print(f"   Response: {response.text[:100]}...")
            else:
                print(f"   Error: {response.text[:100]}...")
        except Exception as e:
            print(f"   Expected connection error: {type(e).__name__}")
        
        # Test MCP call (will also likely fail)
        print("\n7. MCP call test:")
        try:
            mcp_request = {"method": "ping", "params": {}}
            response = await client.post(
                f"{base_url}/api/v1/mcp/example-mcp-server/call",
                json=mcp_request,
                timeout=5.0
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print(f"   Response: {response.text[:100]}...")
            else:
                print(f"   Error: {response.text[:100]}...")
        except Exception as e:
            print(f"   Expected connection error: {type(e).__name__}")
        
        print("\n✅ Gateway API test completed!")


if __name__ == "__main__":
    asyncio.run(test_gateway())
