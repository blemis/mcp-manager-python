#!/usr/bin/env python3
"""
Populate Database from Discovery System

Uses the discovery system to find real MCP servers and populate the database.
No hardcoding - gets servers from actual discovery APIs.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

async def populate_database():
    """Populate database using discovery system."""
    print("🔍 Populating database from discovery system...")
    print("=" * 50)
    
    # Import after path setup
    from src.mcp_manager.core.discovery import ServerDiscovery
    from src.mcp_manager.core.database.registry import MCPServerRegistry, MCPServerInfo
    from src.mcp_manager.core.database.suites import MCPSuiteManager, MCPSuite
    from src.mcp_manager.core.database.connection import get_database_connection
    
    # Set correct database path
    db_path = Path("data/mcp_manager.db")
    import src.mcp_manager.core.database.connection as db_conn_module
    db_conn_module._db_connection = None  # Reset global connection
    db_conn = get_database_connection(db_path)
    
    discovery = ServerDiscovery()
    registry = MCPServerRegistry()
    suite_manager = MCPSuiteManager()
    
    servers_added = []
    
    # Discover and add NPX servers
    print("\n📦 Discovering NPX servers...")
    try:
        npm_results = await discovery.discover_servers(
            query="mcp",
            server_type="npm", 
            limit=2
        )
        
        for result in npm_results:
            server_info = MCPServerInfo(
                server_name=result.name,
                description=result.description,
                server_type="npm",
                install_command=f"npx -y {result.package_name}" if hasattr(result, 'package_name') else f"npx -y {result.name}",
                package_name=getattr(result, 'package_name', result.name),
                discovery_metadata={"source": "npm_discovery", "install_id": getattr(result, 'install_id', result.name)}
            )
            
            if await registry.register_server(server_info):
                servers_added.append(server_info.server_name)
                print(f"   ✅ Added NPX server: {server_info.server_name}")
    
    except Exception as e:
        print(f"   ⚠️ NPX discovery failed: {e}")
    
    # Discover and add Docker Desktop servers  
    print("\n🐳 Discovering Docker Desktop servers...")
    try:
        dd_results = await discovery.discover_servers(
            query="",
            server_type="docker-desktop",
            limit=2
        )
        
        for result in dd_results:
            server_info = MCPServerInfo(
                server_name=f"dd-{result.name}",
                description=result.description,
                server_type="docker-desktop", 
                install_command=f"docker-desktop://{result.name}",
                package_name=result.name,
                discovery_metadata={"source": "docker_desktop_discovery", "install_id": getattr(result, 'install_id', result.name)}
            )
            
            if await registry.register_server(server_info):
                servers_added.append(server_info.server_name)
                print(f"   ✅ Added DD server: {server_info.server_name}")
                
    except Exception as e:
        print(f"   ⚠️ Docker Desktop discovery failed: {e}")
    
    # Discover and add Docker Hub servers
    print("\n🐋 Discovering Docker Hub servers...")
    try:
        docker_results = await discovery.discover_servers(
            query="mcp",
            server_type="docker",
            limit=2
        )
        
        for result in docker_results:
            server_info = MCPServerInfo(
                server_name=result.name.replace('/', '-'),
                description=result.description,
                server_type="docker",
                install_command=f"docker run {result.name}",
                package_name=result.name,
                discovery_metadata={"source": "docker_hub_discovery", "install_id": getattr(result, 'install_id', result.name)}
            )
            
            if await registry.register_server(server_info):
                servers_added.append(server_info.server_name)
                print(f"   ✅ Added Docker server: {server_info.server_name}")
                
    except Exception as e:
        print(f"   ⚠️ Docker Hub discovery failed: {e}")
    
    # Create test suite with discovered servers
    if servers_added:
        print(f"\n🎯 Creating test suite with {len(servers_added)} servers...")
        
        suite = MCPSuite(
            id="discovered-testing",
            name="Discovered MCP Testing Suite", 
            description="Real MCP servers found through discovery system",
            category="core",
            purpose="Testing with real discovered servers"
        )
        
        await suite_manager.create_suite(suite)
        
        # Add servers to suite
        for i, server_name in enumerate(servers_added):
            role = "primary" if i == 0 else "secondary" if i == 1 else "member"
            priority = 90 - (i * 10)
            
            await suite_manager.add_server_to_suite(
                "discovered-testing", 
                server_name, 
                role, 
                priority,
                notes=f"Discovered server #{i+1}"
            )
        
        print(f"   ✅ Created suite 'discovered-testing' with {len(servers_added)} servers")
    
    print(f"\n✅ Database populated with {len(servers_added)} real servers from discovery!")
    return len(servers_added) > 0

if __name__ == "__main__":
    success = asyncio.run(populate_database())
    sys.exit(0 if success else 1)