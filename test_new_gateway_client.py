#!/usr/bin/env python3
"""
Test the new DockerMCPGatewayClient with real JSON-RPC over SSE implementation.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mcp_manager.core.integrations.docker_mcp_gateway import create_docker_gateway_client

async def test_new_implementation():
    """Test the new MCP Gateway client implementation."""
    
    print("=== Testing New DockerMCPGatewayClient Implementation ===")
    
    try:
        # Create and start the client
        print("1. Creating Docker MCP Gateway client...")
        client = await create_docker_gateway_client()
        
        print("2. Testing health check...")
        is_healthy = await client.is_healthy()
        print(f"   Health status: {'✅ Healthy' if is_healthy else '❌ Unhealthy'}")
        
        if is_healthy:
            print("3. Testing list_servers...")
            servers = await client.list_servers()
            print(f"   Found {len(servers)} servers:")
            for server in servers:
                print(f"   - {server.name}: {server.description}")
                print(f"     Status: {server.status}, Enabled: {server.enabled}")
                if server.tools:
                    print(f"     Tools: {len(server.tools)} available")
        
            print("4. Testing get_server_info...")
            if servers:
                server_info = await client.get_server_info(servers[0].name)
                if server_info:
                    print(f"   Server info for {server_info.name}:")
                    print(f"   - Description: {server_info.description}")
                    print(f"   - Status: {server_info.status}")
                    print(f"   - Tools count: {len(server_info.tools or [])}")
                else:
                    print("   No server info retrieved")
        
            print("5. Testing enable_server...")
            if servers:
                result = await client.enable_server(servers[0].name) 
                print(f"   Enable result: {'✅ Success' if result else '❌ Failed'}")
        
        print("\n🎉 New implementation test completed!")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if 'client' in locals():
            await client.stop()
            print("Client stopped")

if __name__ == "__main__":
    asyncio.run(test_new_implementation())