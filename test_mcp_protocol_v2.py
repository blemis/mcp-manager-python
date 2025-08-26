#!/usr/bin/env python3
"""
Test script to properly communicate with Docker MCP Gateway using SSE + JSON-RPC protocol.
Fixed version with proper session management.
"""

import asyncio
import aiohttp
import json

class MCPGatewayTest:
    """Test class for MCP Gateway communication with proper session management."""
    
    def __init__(self):
        self.session = None
        self.sse_resp = None
        self.endpoint_url = None
        self.message_id = 0
    
    def get_next_id(self):
        """Get next message ID."""
        self.message_id += 1
        return self.message_id
    
    async def start(self):
        """Initialize session and establish SSE connection."""
        print("=== Step 3: Verify servers actually respond to MCP calls ===")
        print("1. Starting session and connecting to SSE...")
        
        # Create persistent session
        self.session = aiohttp.ClientSession()
        
        # Connect to SSE endpoint
        self.sse_resp = await self.session.get('http://localhost:8080/sse')
        if self.sse_resp.status != 200:
            print(f"ERROR: SSE connection failed with status {self.sse_resp.status}")
            return False
        
        # Read endpoint event
        async for line in self.sse_resp.content:
            line = line.decode('utf-8').strip()
            print(f"SSE: {line}")
            
            if line.startswith('data: '):
                self.endpoint_url = line[6:]  # Remove 'data: '
                print(f"Got endpoint: {self.endpoint_url}")
                break
        
        if not self.endpoint_url:
            print("ERROR: No endpoint received")
            return False
            
        return True
    
    async def send_message(self, method, params=None):
        """Send JSON-RPC message and wait for response via SSE."""
        message_id = self.get_next_id()
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "id": message_id,
            "params": params or {}
        }
        
        print(f"\n-> Sending {method} (id: {message_id})")
        
        # Send POST request
        full_url = f"http://localhost:8080{self.endpoint_url}"
        async with self.session.post(full_url, json=message) as resp:
            print(f"   HTTP Status: {resp.status}")
            
            if resp.status == 202:  # Accepted - response via SSE
                print("   Waiting for SSE response...")
                
                # Listen for response on SSE stream
                timeout_count = 0
                async for line in self.sse_resp.content:
                    line = line.decode('utf-8').strip()
                    
                    if line.startswith('data: '):
                        response_json = line[6:]
                        try:
                            response_data = json.loads(response_json)
                            if response_data.get("id") == message_id:
                                print(f"<- Got response for {method}")
                                return response_data
                        except json.JSONDecodeError:
                            pass  # Not JSON, continue
                    
                    timeout_count += 1
                    if timeout_count > 50:
                        print(f"   TIMEOUT waiting for {method} response")
                        return None
            else:
                print(f"   HTTP ERROR: {resp.status}")
                return None
    
    async def test_initialize(self):
        """Test MCP initialize."""
        print("\n2. Testing initialize...")
        
        result = await self.send_message("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True}
            },
            "clientInfo": {
                "name": "mcp-manager-test",
                "version": "1.0.0"
            }
        })
        
        if result and "result" in result:
            print("✅ Initialize successful!")
            capabilities = result["result"].get("capabilities", {})
            server_info = result["result"].get("serverInfo", {})
            print(f"   Server: {server_info.get('name', 'unknown')} v{server_info.get('version', 'unknown')}")
            print(f"   Tools: {capabilities.get('tools', {})}")
            return True
        else:
            print("❌ Initialize failed")
            return False
    
    async def test_tools_list(self):
        """Test tools/list."""
        print("\n3. Testing tools/list...")
        
        result = await self.send_message("tools/list")
        
        if result and "result" in result:
            tools = result["result"].get("tools", [])
            print(f"✅ Found {len(tools)} tools:")
            for tool in tools:
                name = tool.get('name', 'unknown')
                desc = tool.get('description', 'no description')[:80]
                print(f"   - {name}: {desc}...")
            return True, tools
        else:
            print("❌ Tools list failed")
            return False, []
    
    async def test_tool_call(self, tool_name, args):
        """Test calling a specific tool."""
        print(f"\n4. Testing tool call: {tool_name}")
        
        result = await self.send_message("tools/call", {
            "name": tool_name,
            "arguments": args
        })
        
        if result and "result" in result:
            tool_result = result["result"]
            print(f"✅ Tool call successful!")
            print(f"   Content: {str(tool_result.get('content', []))[:100]}...")
            print(f"   Is Error: {tool_result.get('isError', False)}")
            return True, tool_result
        else:
            error = result.get('error') if result else "No response"
            print(f"❌ Tool call failed: {error}")
            return False, None
    
    async def run_full_test(self):
        """Run complete MCP test workflow."""
        try:
            # Start session and SSE connection
            if not await self.start():
                return False
            
            # Test initialize
            if not await self.test_initialize():
                return False
            
            # Test tools list
            tools_success, tools = await self.test_tools_list()
            if not tools_success:
                return False
            
            # Test tool call (try SQLite first)
            sqlite_tools = [t for t in tools if 'sqlite' in t.get('name', '').lower()]
            if sqlite_tools:
                tool_name = sqlite_tools[0]['name']
                call_success, result = await self.test_tool_call(
                    tool_name, 
                    {"query": "SELECT 1 as test_value, 'hello' as message;"}
                )
                
                if call_success:
                    print(f"\n🎉 SUCCESS: Full MCP communication working!")
                    print(f"✓ Initialize: OK")
                    print(f"✓ Tools list: {len(tools)} tools")
                    print(f"✓ Tool call: {tool_name} executed successfully")
                    return True
                else:
                    print(f"\n⚠️  PARTIAL: Tools work but tool call failed")
                    return False
            else:
                print(f"\n⚠️  No SQLite tools found, testing first available tool...")
                if tools:
                    tool_name = tools[0]['name']
                    call_success, result = await self.test_tool_call(tool_name, {})
                    return call_success
                return False
        
        finally:
            await self.close()
    
    async def close(self):
        """Close connections."""
        if self.sse_resp:
            self.sse_resp.close()
        if self.session:
            await self.session.close()

async def main():
    """Main test function."""
    test = MCPGatewayTest()
    success = await test.run_full_test()
    
    if success:
        print("\n🚀 All MCP tests passed!")
        return True
    else:
        print("\n❌ Some MCP tests failed")
        return False

if __name__ == "__main__":
    asyncio.run(main())