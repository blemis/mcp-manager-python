#!/usr/bin/env python3
"""
Test script for hybrid server state management system.
"""

import asyncio
import time
from pathlib import Path

# Add src to path for testing
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp_manager.core.state import MCPServerStateManager
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


async def test_hybrid_state():
    """Test the hybrid state management system."""
    print("🧪 Testing Hybrid Server State Management System")
    print("=" * 60)
    
    # Initialize state manager
    db_path = Path("/tmp/test_hybrid_state.db")
    if db_path.exists():
        db_path.unlink()  # Clean slate for testing
    
    state_manager = MCPServerStateManager(db_path)
    
    # Test 1: Fast method (config files only)
    print("\n1. Testing fast server listing (config files only)...")
    start_time = time.time()
    fast_servers = state_manager.list_servers_fast()
    fast_time = (time.time() - start_time) * 1000
    print(f"   ⚡ Found {len(fast_servers)} servers in {fast_time:.1f}ms")
    for server in fast_servers[:3]:  # Show first 3
        print(f"      • {server.name} ({server.server_type.value})")
    
    # Test 2: Cached method (database + runtime cache)
    print("\n2. Testing cached server listing (database + cache)...")
    start_time = time.time()
    cached_servers = await state_manager.list_servers_cached()
    cached_time = (time.time() - start_time) * 1000
    print(f"   📊 Found {len(cached_servers)} servers in {cached_time:.1f}ms")
    for server_state in cached_servers[:3]:
        status_info = f"status: {server_state.status.status.value}" if server_state.status else "no status"
        print(f"      • {server_state.server.name} ({status_info})")
    
    # Test 3: Live method (real-time status)
    print("\n3. Testing live server listing (real-time status)...")
    start_time = time.time()
    live_servers = await state_manager.list_servers_live()
    live_time = (time.time() - start_time) * 1000
    print(f"   🔴 Found {len(live_servers)} servers in {live_time:.1f}ms")
    for server_state in live_servers[:3]:
        status_info = f"status: {server_state.status.status.value}" if server_state.status else "no status"
        health = "🟢 healthy" if server_state.is_healthy else "🔴 unhealthy"
        print(f"      • {server_state.server.name} ({status_info}, {health})")
    
    # Test 4: Record usage events
    print("\n4. Testing usage event recording...")
    if fast_servers:
        test_server = fast_servers[0].name
        await state_manager.record_usage_event(
            server_name=test_server,
            event_type="test_event",
            event_data={"test": True, "timestamp": time.time()},
            user_context="test_user"
        )
        print(f"   📝 Recorded test event for {test_server}")
    
    # Test 5: Get server analytics
    print("\n5. Testing server analytics...")
    if fast_servers:
        test_server = fast_servers[0].name
        analytics = await state_manager.get_server_analytics(test_server)
        if analytics:
            print(f"   📈 Analytics for {test_server}:")
            print(f"      • Total checks: {analytics.total_checks}")
            print(f"      • Success rate: {analytics.success_rate:.1%}")
            print(f"      • Reliability score: {analytics.reliability_score:.1f}")
        else:
            print(f"   📈 No analytics yet for {test_server} (expected for new server)")
    
    # Test 6: Config drift detection
    print("\n6. Testing config drift detection...")
    drifts = await state_manager.detect_config_drift()
    print(f"   🔍 Found {len(drifts)} configuration drifts")
    for drift in drifts[:3]:  # Show first 3
        print(f"      • {drift.server_name}: {drift.drift_type} - {drift.description}")
    
    # Test 7: Performance comparison
    print("\n7. Performance comparison:")
    print(f"   ⚡ Fast method:   {fast_time:6.1f}ms (config files only)")
    print(f"   📊 Cached method: {cached_time:6.1f}ms (database + cache)")
    print(f"   🔴 Live method:   {live_time:6.1f}ms (real-time status)")
    
    speedup_cached = live_time / cached_time if cached_time > 0 else 0
    speedup_fast = live_time / fast_time if fast_time > 0 else 0
    print(f"   📈 Cached is {speedup_cached:.1f}x faster than live")
    print(f"   📈 Fast is {speedup_fast:.1f}x faster than live")
    
    # Test 8: Cache behavior
    print("\n8. Testing cache behavior...")
    start_time = time.time()
    cached_servers_2 = await state_manager.list_servers_cached()
    cached_time_2 = (time.time() - start_time) * 1000
    print(f"   💨 Second cached call: {cached_time_2:.1f}ms (should be much faster due to runtime cache)")
    
    print("\n✅ Hybrid state management system test completed!")
    print(f"Database stored at: {db_path}")


if __name__ == "__main__":
    asyncio.run(test_hybrid_state())