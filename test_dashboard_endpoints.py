#!/usr/bin/env python3
"""
Test script for dashboard API endpoints
Tests the new dashboard endpoints to ensure they return proper data structures
"""

import json
import requests
import sys
from typing import Any, Dict

# Server configuration
BASE_URL = "http://127.0.0.1:8001"
DASHBOARD_BASE = f"{BASE_URL}/api/v1/dashboard"

def test_endpoint(endpoint: str, name: str) -> bool:
    """Test a single endpoint and validate response structure"""
    try:
        print(f"\n🧪 Testing {name}...")
        print(f"   URL: {endpoint}")
        
        response = requests.get(endpoint, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Status: {response.status_code}")
            print(f"   📊 Response structure:")
            
            # Pretty print the response structure (but limit output)
            formatted_json = json.dumps(data, indent=2)
            lines = formatted_json.split('\n')
            if len(lines) > 20:
                print('\n'.join(lines[:15]))
                print(f"   ... (truncated, showing first 15 lines of {len(lines)} total)")
            else:
                print(formatted_json)
            
            return True
        else:
            print(f"   ❌ Status: {response.status_code}")
            print(f"   📝 Error: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Connection error: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"   ❌ JSON decode error: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 Dashboard API Endpoint Testing")
    print("=" * 50)
    
    # Test endpoints
    endpoints = [
        (f"{DASHBOARD_BASE}/overview", "Dashboard Overview"),
        (f"{DASHBOARD_BASE}/services/health", "Service Health Summary"),
        (f"{BASE_URL}/api/v1/health", "Core Health Check"),
        (f"{BASE_URL}/api/v1/services", "Service Registry"),
    ]
    
    results = []
    
    for endpoint, name in endpoints:
        success = test_endpoint(endpoint, name)
        results.append((name, success))
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 Test Summary:")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status} - {name}")
    
    print(f"\n🎯 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All dashboard endpoints are working correctly!")
        return 0
    else:
        print("⚠️  Some endpoints failed. Check server logs for details.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
