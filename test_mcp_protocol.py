#!/usr/bin/env python3
"""
Test script to properly communicate with Docker MCP Gateway using SSE + JSON-RPC protocol.
"""

import asyncio
import aiohttp
import json
import uuid

async def test_mcp_communication():
    """Test real MCP communication with Docker MCP Gateway."""
    
    print("=== Step 2: Testing Real MCP Communication ===")
    
    async with aiohttp.ClientSession() as http_session:
        try:
            print("1. Connecting to SSE endpoint...")
            
            # Start SSE connection and keep it alive
            sse_resp = await http_session.get('http://localhost:8080/sse')
            if sse_resp.status != 200:
                print(f"ERROR: SSE connection failed with status {sse_resp.status}")
                return False, None
            
            # Read the endpoint event from SSE stream
            endpoint_url = None
            async for line in sse_resp.content:
                line = line.decode('utf-8').strip()
                print(f"SSE line: {line}")
                
                if line.startswith('data: '):
                    endpoint_url = line[6:]  # Remove 'data: '
                    print(f"Got message endpoint: {endpoint_url}")
                    break
            
            if not endpoint_url:
                print("ERROR: No endpoint event received")
                return False, None
            
            # Step 2: Send initialize message immediately while SSE is still connected
            print("\n2. Sending JSON-RPC initialize message...")
            
            init_message = {
                "jsonrpc": "2.0",
                "method": "initialize", 
                "id": 1,
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "roots": {"listChanged": True}
                    },
                    "clientInfo": {
                        "name": "mcp-manager",
                        "version": "1.0.0"
                    }
                }
            }
            
            full_url = f"http://localhost:8080{endpoint_url}"
            print(f"Posting to: {full_url}")
            
            # Send POST request while keeping SSE connection alive
            async with http_session.post(full_url, json=init_message) as post_resp:
                response_text = await post_resp.text()
                print(f"Response status: {post_resp.status}")
                print(f"Response: {response_text}")
                
                if post_resp.status == 202:  # Accepted - response will come via SSE
                    print("✅ Request accepted, waiting for response via SSE...")
                    
                    # Listen for response on SSE stream
                    timeout_count = 0
                    async for line in sse_resp.content:
                        line = line.decode('utf-8').strip()
                        print(f"SSE response: {line}")
                        
                        if line.startswith('data: '):
                            response_json = line[6:]  # Remove 'data: '
                            try:
                                response_data = json.loads(response_json)
                                if "result" in response_data and response_data.get("id") == 1:
                                    print("✅ Initialize successful via SSE!")
                                    server_capabilities = response_data["result"].get("capabilities", {})
                                    print(f"Server capabilities: {json.dumps(server_capabilities, indent=2)}")
                                    # Keep SSE connection, endpoint URL, and session for further communication
                                    return True, (sse_resp, endpoint_url, http_session)
                                elif "error" in response_data:
                                    print(f"❌ Initialize failed: {response_data['error']}")
                                    return False, None
                            except json.JSONDecodeError:
                                pass  # Not a JSON response, continue listening
                        
                        timeout_count += 1
                        if timeout_count > 10:  # Timeout after 10 lines
                            print("❌ Timeout waiting for initialize response")
                            return False, None
                            
                elif post_resp.status == 200:
                    response_data = json.loads(response_text) if response_text else {}
                    if "result" in response_data:
                        print("✅ Initialize successful!")
                        server_capabilities = response_data["result"].get("capabilities", {})
                        print(f"Server capabilities: {json.dumps(server_capabilities, indent=2)}")
                        return True, (sse_resp, endpoint_url, http_session)
                    else:
                        print(f"❌ Initialize failed: {response_data}")
                        return False, None
                else:
                    print(f"❌ HTTP error: {post_resp.status}")
                    return False, None
                    
        except Exception as e:
            print(f"ERROR: {e}")
            return False, None

async def test_tools_list(sse_resp, endpoint_url, session):
    """Test tools/list after successful initialization."""
    
    print("\n3. Testing tools/list...")
    
    tools_message = {
        "jsonrpc": "2.0",
        "method": "tools/list",
        "id": 2,
        "params": {}
    }
    
    try:
        full_url = f"http://localhost:8080{endpoint_url}"
        print(f"Sending tools/list to: {full_url}")
        
        async with session.post(full_url, json=tools_message) as resp:
            response_text = await resp.text()
            print(f"Tools list response status: {resp.status}")
            print(f"Tools list response body: {response_text}")
            
            if resp.status == 202:  # Accepted - response will come via SSE
                print("✅ Tools/list request accepted, waiting for response via SSE...")
                
                # Listen for response on SSE stream
                timeout_count = 0
                async for line in sse_resp.content:
                    line = line.decode('utf-8').strip()
                    print(f"SSE tools response: {line}")
                    
                    if line.startswith('data: '):
                        response_json = line[6:]  # Remove 'data: '
                        try:
                            response_data = json.loads(response_json)
                            if "result" in response_data and response_data.get("id") == 2:
                                tools = response_data["result"].get("tools", [])
                                print(f"✅ Found {len(tools)} tools:")
                                for tool in tools:
                                    print(f"  - {tool.get('name', 'unknown')}: {tool.get('description', 'no description')[:100]}...")
                                return True, tools
                            elif "error" in response_data and response_data.get("id") == 2:
                                print(f"❌ Tools list failed: {response_data['error']}")
                                return False, []
                        except json.JSONDecodeError:
                            pass  # Not a JSON response, continue listening
                    
                    timeout_count += 1
                    if timeout_count > 20:  # Timeout after 20 lines
                        print("❌ Timeout waiting for tools/list response")
                        return False, []
            elif resp.status == 200:
                response_data = json.loads(response_text) if response_text else {}
                if "result" in response_data:
                    tools = response_data["result"].get("tools", [])
                    print(f"✅ Found {len(tools)} tools:")
                    for tool in tools:
                        print(f"  - {tool.get('name', 'unknown')}: {tool.get('description', 'no description')[:100]}...")
                    return True, tools
                else:
                    print(f"❌ Tools list failed: {response_data}")
                    return False, []
            else:
                print(f"❌ HTTP error: {resp.status}")
                return False, []
                        
    except Exception as e:
        print(f"ERROR: {e}")
        return False, []

async def test_tool_call(sse_resp, endpoint_url, session, tool_name, tool_args):
    """Test calling a specific tool."""
    
    print(f"\n4. Testing tool call: {tool_name}")
    
    tool_call_message = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": 3,
        "params": {
            "name": tool_name,
            "arguments": tool_args
        }
    }
    
    try:
        full_url = f"http://localhost:8080{endpoint_url}"
        print(f"Calling tool {tool_name} with args: {tool_args}")
        
        async with session.post(full_url, json=tool_call_message) as resp:
            response_text = await resp.text()
            print(f"Tool call response status: {resp.status}")
            
            if resp.status == 202:  # Accepted - response will come via SSE
                print("✅ Tool call request accepted, waiting for response via SSE...")
                
                # Listen for response on SSE stream
                timeout_count = 0
                async for line in sse_resp.content:
                    line = line.decode('utf-8').strip()
                    print(f"SSE tool call response: {line}")
                    
                    if line.startswith('data: '):
                        response_json = line[6:]  # Remove 'data: '
                        try:
                            response_data = json.loads(response_json)
                            if "result" in response_data and response_data.get("id") == 3:
                                result = response_data["result"]
                                print(f"✅ Tool call successful!")
                                print(f"Content: {str(result.get('content', []))[:200]}...")
                                print(f"Is Error: {result.get('isError', False)}")
                                return True, result
                            elif "error" in response_data and response_data.get("id") == 3:
                                print(f"❌ Tool call failed: {response_data['error']}")
                                return False, None
                        except json.JSONDecodeError:
                            pass  # Not a JSON response, continue listening
                    
                    timeout_count += 1
                    if timeout_count > 30:  # Longer timeout for tool calls
                        print("❌ Timeout waiting for tool call response")
                        return False, None
            else:
                print(f"❌ HTTP error: {resp.status}")
                return False, None
                        
    except Exception as e:
        print(f"ERROR: {e}")
        return False, None

async def main():
    """Main test function."""
    
    print("=== Step 3: Verify servers actually respond to MCP calls ===")
    
    # Test initialization
    success, connection = await test_mcp_communication()
    
    if success and connection:
        sse_resp, endpoint_url, session = connection
        
        # Use the same session that established the connection
        # Test tools list
        tools_success, tools = await test_tools_list(sse_resp, endpoint_url, session)
        
        if tools_success and tools:
            print(f"\n✅ Tools list successful - {len(tools)} tools found")
            
            # Test calling a specific tool (try SQLite first)
            sqlite_tools = [t for t in tools if 'sqlite' in t.get('name', '').lower()]
            if sqlite_tools:
                tool_name = sqlite_tools[0]['name']
                # Try a simple SQLite query
                tool_call_success, result = await test_tool_call(
                    sse_resp, endpoint_url, session,
                    tool_name,
                    {"query": "SELECT 1 as test;"}
                )
                
                if tool_call_success:
                    print(f"\n🎉 SUCCESS: Full MCP communication working!")
                    print(f"- Successfully initialized with Docker MCP Gateway")
                    print(f"- Server has {len(tools)} tools available")
                    print(f"- Successfully called tool: {tool_name}")
                    return True
                else:
                    print(f"\n⚠️  PARTIAL: Tools list works but tool call failed")
                    return False
            else:
                print(f"\n⚠️  PARTIAL: Tools list works but no SQLite tools found")
                # Try any available tool
                if tools:
                    tool_name = tools[0]['name']
                    print(f"Trying first available tool: {tool_name}")
                    tool_call_success, result = await test_tool_call(
                        sse_resp, endpoint_url, session,
                        tool_name, 
                        {}  # Empty args
                    )
                    return tool_call_success
                return False
        else:
            print(f"\n⚠️  PARTIAL: Initialized but tools/list failed")
            return False
    else:
        print(f"\n❌ FAILED: Could not establish MCP communication")
        return False

if __name__ == "__main__":
    asyncio.run(main())