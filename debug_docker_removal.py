#!/usr/bin/env python3
"""
Debug script to test Docker image removal functionality.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp_manager.core.simple_manager import SimpleMCPManager
from mcp_manager.utils.logging import setup_logging

async def debug_docker_removal():
    """Debug Docker image removal."""
    # Enable debug logging
    setup_logging(level="DEBUG")
    
    manager = SimpleMCPManager()
    
    print("🔍 Debugging Docker image removal...")
    print()
    
    # List current servers
    print("📋 Current servers:")
    try:
        servers = await manager.list_servers()
        for i, server in enumerate(servers, 1):
            print(f"  {i}. {server.name} ({server.server_type.value})")
            if server.server_type.value in ["docker", "docker_desktop"]:
                print(f"     Command: {server.command}")
                print(f"     Args: {server.args}")
                
                # Test image extraction
                image = manager._extract_docker_image(server.command, server.args)
                print(f"     Extracted image: {image}")
                print()
    except Exception as e:
        print(f"❌ Error listing servers: {e}")
        return
    
    print("\n🐳 Current Docker images:")
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "images", "--format", "table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"❌ Error listing Docker images: {result.stderr}")
    except Exception as e:
        print(f"❌ Error running docker images: {e}")
    
    print("\n💡 To test removal, run:")
    print("   mcp-manager remove <server-name>")
    print("   (with --debug flag to see detailed logging)")

if __name__ == "__main__":
    asyncio.run(debug_docker_removal())