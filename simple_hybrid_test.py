#!/usr/bin/env python3
"""Simple test for hybrid state system."""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, "src")

from mcp_manager.core.state import MCPServerStateManager


async def simple_test():
    """Simple async test."""
    print("🧪 Simple Hybrid State Test")
    
    # Initialize
    db_path = Path("/tmp/simple_test.db")
    if db_path.exists():
        db_path.unlink()
    
    state_manager = MCPServerStateManager(db_path)
    print("✅ State manager initialized")
    
    # Test fast method
    start = time.time()
    servers = state_manager.list_servers_fast()
    fast_time = (time.time() - start) * 1000
    print(f"⚡ Fast: {len(servers)} servers in {fast_time:.1f}ms")
    
    # Test cached method
    start = time.time()
    cached = await state_manager.list_servers_cached()
    cached_time = (time.time() - start) * 1000
    print(f"📊 Cached: {len(cached)} servers in {cached_time:.1f}ms")
    
    # Test record event
    if servers:
        await state_manager.record_usage_event(
            servers[0].name, "test", {"data": "test"}
        )
        print(f"📝 Recorded event for {servers[0].name}")
    
    print("✅ Test completed successfully!")


if __name__ == "__main__":
    asyncio.run(simple_test())