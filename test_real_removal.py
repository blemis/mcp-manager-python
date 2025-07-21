#!/usr/bin/env python3
"""
Test real Docker image removal by actually removing a server.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp_manager.core.simple_manager import SimpleMCPManager
from mcp_manager.utils.logging import setup_logging

async def test_real_removal():
    """Test actual server removal with Docker image cleanup."""
    # Enable debug logging to see everything
    setup_logging(level="DEBUG")
    
    manager = SimpleMCPManager()
    
    print("🧪 Testing real Docker server removal...")
    print()
    
    # List current servers
    servers = await manager.list_servers()
    docker_servers = [s for s in servers if s.server_type.value in ["docker", "docker-desktop"]]
    
    if not docker_servers:
        print("❌ No Docker servers to test with")
        return
    
    print("Available Docker servers:")
    for i, server in enumerate(docker_servers, 1):
        print(f"  {i}. {server.name} ({server.server_type.value})")
    
    print("\n⚠️  Warning: This will actually remove a server!")
    print("Make sure you can re-add it later if needed.")
    print()
    
    choice = input("Enter server number to remove (or press Enter to cancel): ").strip()
    
    if not choice or not choice.isdigit():
        print("❌ Cancelled")
        return
    
    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(docker_servers):
            print("❌ Invalid choice")
            return
        
        selected_server = docker_servers[idx]
        print(f"\n🗑️  Removing server: {selected_server.name}")
        print(f"   Type: {selected_server.server_type.value}")
        
        # Show what image would be targeted
        expected_image = f"mcp/{selected_server.name.lower()}"
        print(f"   Expected Docker image: {expected_image}")
        
        # Perform the removal
        success = await manager.remove_server(selected_server.name)
        
        if success:
            print("✅ Server removal completed!")
            print("   Check the debug logs above to see if Docker images were cleaned up")
        else:
            print("❌ Server removal failed")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_real_removal())