#!/usr/bin/env python3
"""
Inspect servers to see their actual structure.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp_manager.core.simple_manager import SimpleMCPManager
from mcp_manager.utils.logging import setup_logging

async def inspect_servers():
    """Inspect all servers to see their structure."""
    # Enable debug logging
    setup_logging(level="DEBUG")
    
    manager = SimpleMCPManager()
    
    print("🔍 Inspecting server structure...")
    print()
    
    servers = await manager.list_servers()
    
    for i, server in enumerate(servers, 1):
        print(f"Server {i}: {server.name}")
        print(f"  Type: {server.server_type} ({type(server.server_type)})")
        print(f"  Value: {server.server_type.value}")
        print(f"  Command: {server.command}")
        print(f"  Args: {server.args}")
        print(f"  Enabled: {server.enabled}")
        print(f"  Scope: {server.scope}")
        
        # Check if this would be considered a Docker server
        is_docker = server.server_type.value in ["docker", "docker_desktop"]
        print(f"  Is Docker: {is_docker}")
        
        print()

if __name__ == "__main__":
    asyncio.run(inspect_servers())