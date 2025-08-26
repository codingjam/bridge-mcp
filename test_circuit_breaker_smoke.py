#!/usr/bin/env python3
"""
Simple smoke test for circuit breaker functionality
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp_gateway.circuit_breaker import CircuitBreaker, CircuitBreakerManager, CircuitBreakerConfig


async def test_circuit_breaker():
    """Simple test of circuit breaker functionality."""
    print("Testing circuit breaker manager...")
    
    # Test circuit breaker manager
    manager = CircuitBreakerManager()
    
    # Test successful call
    async def successful_operation():
        return "success"
    
    result = await manager.check_and_call("test-server", successful_operation)
    print(f"Manager successful call: {result}")
    
    # Test failing call
    async def failing_operation():
        raise Exception("Test failure")
    
    # Should fail a few times
    for i in range(3):
        try:
            await manager.check_and_call("failing-server", failing_operation)
        except Exception as e:
            print(f"Call {i+1} failed: {e}")
    
    print("Circuit breaker smoke test completed successfully!")


if __name__ == "__main__":
    asyncio.run(test_circuit_breaker())
