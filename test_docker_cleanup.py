#!/usr/bin/env python3
"""
Test script to manually test Docker image removal.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp_manager.core.simple_manager import SimpleMCPManager
from mcp_manager.utils.logging import setup_logging

async def test_docker_cleanup():
    """Test Docker image cleanup functionality."""
    # Enable debug logging to see what's happening
    setup_logging(level="DEBUG")
    
    manager = SimpleMCPManager()
    
    print("🧪 Testing Docker image removal...")
    print()
    
    # Test image extraction for each Docker server
    servers = await manager.list_servers()
    docker_servers = [s for s in servers if s.server_type.value in ["docker", "docker-desktop"]]
    
    if not docker_servers:
        print("❌ No Docker servers found")
        return
    
    for server in docker_servers:
        print(f"🔍 Testing server: {server.name}")
        print(f"   Type: {server.server_type.value}")
        print(f"   Command: {server.command}")
        print(f"   Args: {server.args}")
        
        # Test image extraction
        extracted_image = manager._extract_docker_image(server.command, server.args)
        print(f"   Extracted image: {extracted_image}")
        
        # Try Docker Desktop pattern if extraction failed
        if not extracted_image and server.server_type.value == "docker-desktop":
            fallback_image = f"mcp/{server.name.lower()}"
            print(f"   Fallback image: {fallback_image}")
        
        print()
    
    # Test manual image removal
    test_images = [
        "mcp/sqlite",
        "mcp/aws-diagram", 
        "mcp/kubernetes"
    ]
    
    print("🗑️  Testing manual image removal...")
    for image in test_images:
        print(f"   Testing removal of: {image}")
        try:
            success = await manager._remove_docker_image(image)
            print(f"   Result: {'✅ Success' if success else '❌ Failed'}")
        except Exception as e:
            print(f"   Error: {e}")
        print()

if __name__ == "__main__":
    asyncio.run(test_docker_cleanup())