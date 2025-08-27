"""
Docker MCP Gateway HTTP API client.

This module provides a REST API wrapper for communicating with the Docker MCP Gateway
HTTP server, enabling programmatic control over Docker Desktop MCP servers.
"""

import asyncio
import json
import os
import time
from typing import Dict, List, Optional, Tuple
import aiohttp
import subprocess
from dataclasses import dataclass
from pathlib import Path

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class GatewayServerInfo:
    """Information about a server available through the gateway."""
    name: str
    enabled: bool
    status: str
    description: Optional[str] = None
    tools: Optional[List[Dict]] = None


@dataclass
class GatewayStatus:
    """Status information about the Docker MCP Gateway."""
    running: bool
    port: int
    servers_enabled: List[str]
    servers_available: List[str]
    health: str


class DockerMCPGatewayClient:
    """
    MCP protocol client for Docker MCP Gateway over HTTP/SSE.
    
    Implements real JSON-RPC 2.0 over SSE transport for communicating with
    Docker MCP Gateway, providing proper session management and bidirectional communication.
    """
    
    def __init__(self, host: str = "localhost", port: int = 8080, auto_start: bool = True):
        """
        Initialize the Docker MCP Gateway client.
        
        Args:
            host: Gateway host (default: localhost)
            port: Gateway port (default: 8080)
            auto_start: Whether to automatically start gateway if not running
        """
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.auto_start = auto_start
        self.session: Optional[aiohttp.ClientSession] = None
        self._gateway_process: Optional[subprocess.Popen] = None
        self._startup_timeout = 30  # seconds
        
        # MCP session state
        self._sse_response: Optional[aiohttp.ClientResponse] = None
        self._endpoint_url: Optional[str] = None
        self._message_id = 0
        self._initialized = False
        
        logger.debug(f"DockerMCPGatewayClient initialized for {self.base_url}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
    
    async def start(self):
        """Start the HTTP session, ensure gateway is running, and establish MCP session."""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=30)  # Longer timeout for MCP operations
            self.session = aiohttp.ClientSession(timeout=timeout)
            
        if self.auto_start:
            await self._ensure_gateway_running()
            
        # Establish SSE connection and MCP session
        await self._establish_mcp_session()
    
    async def stop(self):
        """Stop MCP session, HTTP session and optionally stop gateway."""
        # Close SSE connection
        if self._sse_response:
            self._sse_response.close()
            self._sse_response = None
            
        if self.session:
            await self.session.close()
            self.session = None
            
        # Reset MCP session state
        self._endpoint_url = None
        self._message_id = 0
        self._initialized = False
        
        # Optionally stop the gateway process we started
        if self._gateway_process:
            try:
                self._gateway_process.terminate()
                self._gateway_process.wait(timeout=5)
                self._gateway_process = None
                logger.info("Docker MCP Gateway stopped")
            except subprocess.TimeoutExpired:
                self._gateway_process.kill()
                self._gateway_process = None
                logger.warning("Docker MCP Gateway force killed")
            except Exception as e:
                logger.error(f"Error stopping gateway: {e}")
    
    async def _ensure_gateway_running(self):
        """Ensure the Docker MCP Gateway is running."""
        # Step 1: Check if Gateway HTTP server is responding (simple HTTP check)
        if await self._check_gateway_http_available():
            logger.debug("Gateway HTTP server already running - using existing server")
            return
            
        # Step 2: Gateway not running, start it once
        logger.info("Docker MCP Gateway not running - starting persistent server...")
        await self._start_gateway_process()
        
        # Step 3: Wait for gateway HTTP server to become available
        start_time = time.time()
        while time.time() - start_time < self._startup_timeout:
            if await self._check_gateway_http_available():
                logger.info("Docker MCP Gateway started successfully - HTTP server ready")
                return
            await asyncio.sleep(1)
        
        raise RuntimeError(f"Gateway failed to start within {self._startup_timeout} seconds")
    
    async def _check_gateway_http_available(self) -> bool:
        """Simple check if Gateway HTTP server is responding (before MCP session)."""
        try:
            timeout = aiohttp.ClientTimeout(total=2)
            async with aiohttp.ClientSession(timeout=timeout) as temp_session:
                async with temp_session.get(f"{self.base_url}/sse") as response:
                    return response.status == 200
        except Exception as e:
            logger.debug(f"Gateway HTTP check failed: {e}")
            return False
    
    async def _start_gateway_process(self):
        """Start the persistent Docker MCP Gateway HTTP server process."""
        try:
            # Start the gateway in HTTP server mode with all available servers
            cmd = [
                "docker", "mcp", "gateway", "run",
                "--port", str(self.port),
                "--servers", "Ref,SQLite,filesystem",  # Enable all available DD servers
                "--transport", "sse"  # Use Server-Sent Events transport for HTTP API
            ]
            
            logger.info(f"Starting persistent Gateway API server: {' '.join(cmd)}")
            self._gateway_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,  # Don't capture output for persistent process
                stderr=subprocess.DEVNULL,
                text=True
            )
            
            # Give it time to start (Gateway needs to pull images potentially)
            await asyncio.sleep(5)
            
        except Exception as e:
            logger.error(f"Failed to start gateway process: {e}")
            raise
    
    async def restart_gateway(self):
        """Restart the gateway if it's having issues."""
        logger.warning("Restarting Docker MCP Gateway due to health issues")
        
        # Stop the current process
        if self._gateway_process:
            try:
                self._gateway_process.terminate()
                self._gateway_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._gateway_process.kill()
            except Exception as e:
                logger.error(f"Error stopping gateway for restart: {e}")
            finally:
                self._gateway_process = None
        
        # Start a new process
        await self._start_gateway_process()
        
        # Wait for it to become healthy
        start_time = time.time()
        while time.time() - start_time < self._startup_timeout:
            if await self.is_healthy():
                logger.info("Docker MCP Gateway restarted successfully")
                return
            await asyncio.sleep(1)
        
        raise RuntimeError("Gateway restart failed")
    
    def _get_next_message_id(self) -> int:
        """Get next message ID for JSON-RPC requests."""
        self._message_id += 1
        return self._message_id
    
    async def _establish_mcp_session(self):
        """Establish SSE connection and initialize MCP session."""
        if self._initialized:
            return
            
        logger.debug("Establishing MCP session with Docker Gateway")
        
        # Connect to SSE endpoint
        self._sse_response = await self.session.get(f"{self.base_url}/sse")
        if self._sse_response.status != 200:
            raise RuntimeError(f"SSE connection failed with status {self._sse_response.status}")
        
        # Read endpoint event from SSE stream
        async for line in self._sse_response.content:
            line = line.decode('utf-8').strip()
            logger.debug(f"SSE line: {line}")
            
            if line.startswith('data: '):
                self._endpoint_url = line[6:]  # Remove 'data: '
                logger.debug(f"Got message endpoint: {self._endpoint_url}")
                break
        
        if not self._endpoint_url:
            raise RuntimeError("No endpoint URL received from SSE stream")
        
        # Initialize MCP session
        await self._initialize_mcp_protocol()
        
        logger.info("MCP session established successfully")
    
    async def _initialize_mcp_protocol(self):
        """Send MCP initialize message and wait for response."""
        logger.debug("Initializing MCP protocol")
        
        init_params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True}
            },
            "clientInfo": {
                "name": "mcp-manager",
                "version": "1.0.0"
            }
        }
        
        result = await self._send_mcp_request("initialize", init_params)
        if not result or "serverInfo" not in result:
            raise RuntimeError(f"MCP initialization failed: {result}")
        
        server_info = result["serverInfo"]
        logger.info(f"MCP initialized with {server_info.get('name', 'unknown')} v{server_info.get('version', 'unknown')}")
        
        self._initialized = True
    
    async def _send_mcp_request(self, method: str, params: dict = None, timeout: int = 30) -> Optional[dict]:
        """Send MCP JSON-RPC request and wait for response via SSE."""
        if not self.session or not self._endpoint_url:
            raise RuntimeError("MCP session not established - call start() first")
        
        message_id = self._get_next_message_id()
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "id": message_id,
            "params": params or {}
        }
        
        logger.debug(f"Sending MCP request: {method} (id: {message_id})")
        
        # Send POST request
        full_url = f"{self.base_url}{self._endpoint_url}"
        try:
            async with self.session.post(full_url, json=message) as resp:
                logger.debug(f"MCP request status: {resp.status}")
                
                if resp.status == 202:  # Accepted - response will come via SSE
                    # Listen for response on SSE stream
                    timeout_count = 0
                    max_timeout_count = timeout * 2  # Roughly timeout seconds (checking every 0.5s)
                    
                    async for line in self._sse_response.content:
                        line = line.decode('utf-8').strip()
                        
                        if line.startswith('data: '):
                            response_json = line[6:]  # Remove 'data: '
                            try:
                                response_data = json.loads(response_json)
                                if response_data.get("id") == message_id:
                                    logger.debug(f"Got MCP response for {method}")
                                    
                                    if "result" in response_data:
                                        return response_data["result"]
                                    elif "error" in response_data:
                                        logger.error(f"MCP error for {method}: {response_data['error']}")
                                        return None
                                    else:
                                        return response_data
                            except json.JSONDecodeError:
                                pass  # Not JSON, continue listening
                        
                        timeout_count += 1
                        if timeout_count > max_timeout_count:
                            logger.error(f"Timeout waiting for MCP response to {method}")
                            return None
                            
                elif resp.status == 200:
                    # Direct response (less common with SSE transport)
                    response_text = await resp.text()
                    if response_text:
                        response_data = json.loads(response_text)
                        return response_data.get("result")
                    return {}
                else:
                    logger.error(f"MCP request failed with HTTP {resp.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error sending MCP request {method}: {e}")
            return None
    
    async def ensure_healthy(self):
        """Ensure gateway is healthy, restart if needed."""
        if not await self.is_healthy():
            logger.warning("Gateway unhealthy, attempting restart")
            await self.restart_gateway()
    
    async def is_healthy(self) -> bool:
        """Check if the gateway is healthy and MCP session is established."""
        try:
            if not self.session or not self._initialized:
                return False
                
            # Quick health check - try to get tools list
            result = await self._send_mcp_request("tools/list", {}, timeout=5)
            return result is not None and "tools" in result
            
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
        
        return False
    
    async def get_status(self) -> GatewayStatus:
        """Get comprehensive status information about the gateway."""
        if not self.session:
            raise RuntimeError("Client not started - call start() first")
            
        try:
            async with self.session.get(f"{self.base_url}/status") as response:
                response.raise_for_status()
                data = await response.json()
                
                return GatewayStatus(
                    running=data.get("running", False),
                    port=data.get("port", self.port),
                    servers_enabled=data.get("servers_enabled", []),
                    servers_available=data.get("servers_available", []),
                    health=data.get("health", "unknown")
                )
        except Exception as e:
            logger.error(f"Failed to get gateway status: {e}")
            raise
    
    async def list_servers(self) -> List[GatewayServerInfo]:
        """List all available servers via MCP tools/list request."""
        try:
            if not self._initialized:
                logger.warning("MCP session not initialized, cannot list servers")
                return []
            
            # Get tools list from MCP Gateway
            result = await self._send_mcp_request("tools/list")
            if not result or "tools" not in result:
                logger.error(f"Failed to get tools list: {result}")
                return []
            
            tools = result["tools"]
            logger.debug(f"Retrieved {len(tools)} tools from MCP Gateway")
            
            # Group tools by server (infer server from tool name prefixes)
            server_tools = {}
            for tool in tools:
                tool_name = tool.get("name", "")
                
                # Determine server based on tool naming patterns
                if any(name in tool_name.lower() for name in ["sqlite", "database", "query", "table"]):
                    server_name = "SQLite"
                elif any(name in tool_name.lower() for name in ["ref", "documentation", "search"]):
                    server_name = "Ref"
                elif any(name in tool_name.lower() for name in ["file", "directory", "path"]):
                    server_name = "filesystem"
                else:
                    # Group under generic server name or skip
                    server_name = "Unknown"
                
                if server_name not in server_tools:
                    server_tools[server_name] = []
                server_tools[server_name].append(tool)
            
            # Create server info objects
            servers = []
            for server_name, tools_list in server_tools.items():
                if server_name != "Unknown":  # Skip unknown servers
                    servers.append(GatewayServerInfo(
                        name=server_name,
                        enabled=True,  # If tools are available, server is enabled
                        status="running",
                        description=f"MCP server with {len(tools_list)} tools",
                        tools=tools_list
                    ))
            
            logger.debug(f"Identified {len(servers)} servers from tools analysis")
            return servers
            
        except Exception as e:
            logger.error(f"Failed to list servers via MCP: {e}")
            return []
    
    async def enable_server(self, server_name: str) -> bool:
        """
        Enable a Docker Desktop MCP server by updating enabled servers list.
        
        Args:
            server_name: Name of the server to enable (e.g., "SQLite", "filesystem")
            
        Returns:
            True if server is enabled/already enabled
        """
        try:
            # Check if already enabled
            servers = await self.list_servers()
            for server in servers:
                if server.name == server_name:
                    logger.info(f"Server {server_name} is already enabled in gateway")
                    return True
            
            # Get the CURRENT servers from the gateway (not database!)
            # The database has already been updated, we need to know what's actually in Claude
            from mcp_manager.core.claude_interface import ClaudeInterface
            claude = ClaudeInterface()
            gateway_server = claude.get_server("docker-gateway")
            
            current_servers = []
            if gateway_server and gateway_server.args:
                # Parse --servers argument from current gateway
                args_str = " ".join(gateway_server.args)
                if "--servers" in args_str:
                    servers_part = args_str.split("--servers")[1].split()[0]
                    current_servers = [s.strip() for s in servers_part.split(",")]
            
            # Add the server we're enabling if not already there
            if server_name not in current_servers:
                current_servers.append(server_name)
            
            logger.info(f"Enabling server {server_name}, gateway will serve: {sorted(current_servers)}")
            
            # Restart gateway with all enabled servers
            logger.info(f"Calling _restart_gateway_with_servers with: {current_servers}")
            await self._restart_gateway_with_servers(current_servers)
            logger.info(f"_restart_gateway_with_servers completed")
            
            return True
            
        except Exception as e:
            logger.error(f"Error enabling server {server_name}: {e}")
            return False
    
    async def disable_server(self, server_name: str) -> bool:
        """
        Disable a Docker Desktop MCP server by updating enabled servers list.
        
        Args:
            server_name: Name of the server to disable
            
        Returns:
            True if successfully disabled
        """
        try:
            # Get the CURRENT servers from the gateway (not database!)
            # The database has already been updated, we need to know what's actually in Claude
            from mcp_manager.core.claude_interface import ClaudeInterface
            claude = ClaudeInterface()
            gateway_server = claude.get_server("docker-gateway")
            
            current_servers = []
            if gateway_server and gateway_server.args:
                # Parse --servers argument from current gateway
                args_str = " ".join(gateway_server.args)
                if "--servers" in args_str:
                    servers_part = args_str.split("--servers")[1].split()[0]
                    current_servers = [s.strip() for s in servers_part.split(",")]
            
            # Remove the server we're disabling
            if server_name in current_servers:
                current_servers.remove(server_name)
            
            logger.info(f"Disabling server {server_name}, gateway will serve: {sorted(current_servers)}")
            
            # Restart gateway with remaining enabled servers
            await self._restart_gateway_with_servers(current_servers)
            
            return True
                
        except Exception as e:
            logger.error(f"Error disabling server {server_name}: {e}")
            return False
    
    async def get_server_info(self, server_name: str) -> Optional[GatewayServerInfo]:
        """
        Get detailed information about a specific server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            Server information or None if not found
        """
        try:
            servers = await self.list_servers()
            for server in servers:
                if server.name == server_name:
                    return server
            
            return None
        except Exception as e:
            logger.error(f"Failed to get server info for {server_name}: {e}")
            return None
    
    async def enable_multiple_servers(self, server_names: List[str]) -> Dict[str, bool]:
        """
        Enable multiple servers in parallel.
        
        Args:
            server_names: List of server names to enable
            
        Returns:
            Dictionary mapping server name to success status
        """
        if not server_names:
            return {}
            
        # Use asyncio.gather to enable all servers in parallel
        tasks = [self.enable_server(name) for name in server_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Map results back to server names
        status_map = {}
        for server_name, result in zip(server_names, results):
            if isinstance(result, Exception):
                logger.error(f"Exception enabling {server_name}: {result}")
                status_map[server_name] = False
            else:
                status_map[server_name] = result
        
        return status_map
    
    async def disable_multiple_servers(self, server_names: List[str]) -> Dict[str, bool]:
        """
        Disable multiple servers in parallel.
        
        Args:
            server_names: List of server names to disable
            
        Returns:
            Dictionary mapping server name to success status
        """
        if not server_names:
            return {}
            
        tasks = [self.disable_server(name) for name in server_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        status_map = {}
        for server_name, result in zip(server_names, results):
            if isinstance(result, Exception):
                logger.error(f"Exception disabling {server_name}: {result}")
                status_map[server_name] = False
            else:
                status_map[server_name] = result
        
        return status_map
    
    async def _restart_gateway_with_servers(self, server_list: List[str]):
        """
        Update Claude's docker-gateway configuration with new server list.
        This keeps the gateway process running but updates what Claude sees.
        
        Args:
            server_list: List of server names to enable (e.g., ["Ref", "SQLite"])
        """
        from mcp_manager.core.claude_interface import ClaudeInterface
        import subprocess
        
        try:
            # Initialize Claude interface
            claude = ClaudeInterface()
            
            # Remove existing docker-gateway from Claude config (if it exists)
            # First check if it exists
            if claude.server_exists("docker-gateway"):
                # Try removing without scope first (uses default)
                try:
                    result = subprocess.run(
                        [claude.claude_path, "mcp", "remove", "docker-gateway"],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if result.returncode == 0:
                        logger.debug("Removed existing docker-gateway")
                    else:
                        # Try with explicit scopes
                        for scope in ["user", "project", "local"]:
                            try:
                                result = subprocess.run(
                                    [claude.claude_path, "mcp", "remove", "--scope", scope, "docker-gateway"],
                                    capture_output=True,
                                    text=True,
                                    timeout=30,
                                )
                                if result.returncode == 0:
                                    logger.debug(f"Removed existing docker-gateway from {scope} scope")
                                    break
                            except Exception:
                                continue
                except Exception as e:
                    logger.warning(f"Failed to remove docker-gateway: {e}")
            else:
                logger.debug("docker-gateway not found, will create new entry")
            
            # Only add gateway if we have servers to expose
            if server_list:
                # Re-add docker-gateway with updated server list
                servers_arg = ",".join(server_list)
                success = claude.add_server(
                    name="docker-gateway",
                    command="docker",
                    args=["mcp", "gateway", "run", "--servers", servers_arg],
                    env=None,
                )
                
                if success:
                    logger.info(f"Updated docker-gateway configuration with servers: {server_list}")
                else:
                    logger.error("Failed to add docker-gateway to Claude Code")
                    raise RuntimeError("Failed to update docker-gateway configuration")
            else:
                logger.info("No servers enabled, docker-gateway removed from Claude configuration")
            
        except Exception as e:
            logger.error(f"Failed to update docker-gateway configuration: {e}")
            raise
    
    async def sync_servers(self, desired_servers: List[str]) -> Tuple[List[str], List[str]]:
        """
        Synchronize server states to match desired configuration.
        
        Args:
            desired_servers: List of servers that should be enabled
            
        Returns:
            Tuple of (successfully_enabled, successfully_disabled)
        """
        if not self.session:
            raise RuntimeError("Client not started - call start() first")
            
        # Get current state
        current_servers = await self.list_servers()
        currently_enabled = {s.name for s in current_servers if s.enabled}
        desired_set = set(desired_servers)
        
        # Determine what needs to change
        to_enable = desired_set - currently_enabled
        to_disable = currently_enabled - desired_set
        
        # Execute changes in parallel
        enable_results = {}
        disable_results = {}
        
        if to_enable:
            enable_results = await self.enable_multiple_servers(list(to_enable))
        if to_disable:
            disable_results = await self.disable_multiple_servers(list(to_disable))
        
        # Collect successful operations
        successfully_enabled = [name for name, success in enable_results.items() if success]
        successfully_disabled = [name for name, success in disable_results.items() if success]
        
        logger.info(f"Sync completed - enabled: {successfully_enabled}, disabled: {successfully_disabled}")
        return successfully_enabled, successfully_disabled


# Fallback implementation using CLI commands when HTTP API is not available
class DockerMCPGatewayCLIFallback:
    """
    Fallback implementation using Docker MCP CLI commands.
    
    This class provides the same interface as DockerMCPGatewayClient
    but uses subprocess calls to docker mcp commands instead of HTTP API.
    """
    
    def __init__(self):
        """Initialize CLI fallback client."""
        logger.debug("DockerMCPGatewayCLIFallback initialized")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass
    
    async def start(self):
        """Start method for compatibility."""
        pass
    
    async def stop(self):
        """Stop method for compatibility."""
        pass
    
    async def is_healthy(self) -> bool:
        """Check if docker mcp commands are available."""
        try:
            result = subprocess.run(
                ["docker", "mcp", "--help"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    async def enable_server(self, server_name: str) -> bool:
        """Enable server using CLI command."""
        try:
            result = subprocess.run(
                ["docker", "mcp", "server", "enable", server_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            success = result.returncode == 0
            if success:
                logger.info(f"Successfully enabled server: {server_name}")
            else:
                logger.warning(f"Failed to enable server {server_name}: {result.stderr}")
            
            return success
        except Exception as e:
            logger.error(f"Failed to enable server {server_name}: {e}")
            return False
    
    async def disable_server(self, server_name: str) -> bool:
        """Disable server using CLI command."""
        try:
            result = subprocess.run(
                ["docker", "mcp", "server", "disable", server_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            success = result.returncode == 0
            if success:
                logger.info(f"Successfully disabled server: {server_name}")
            else:
                logger.warning(f"Failed to disable server {server_name}: {result.stderr}")
            
            return success
        except Exception as e:
            logger.error(f"Failed to disable server {server_name}: {e}")
            return False
    
    async def list_servers(self) -> List[GatewayServerInfo]:
        """List servers using CLI command."""
        try:
            result = subprocess.run(
                ["docker", "mcp", "server", "list"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to list servers: {result.stderr}")
                return []
            
            # Parse CLI output (this would need to be adapted based on actual CLI format)
            servers = []
            for line in result.stdout.split('\n'):
                if line.strip() and not line.startswith('#'):
                    # Assuming format: name status enabled
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        name = parts[0]
                        enabled = len(parts) > 2 and parts[2].lower() == 'enabled'
                        status = parts[1] if len(parts) > 1 else 'unknown'
                        
                        servers.append(GatewayServerInfo(
                            name=name,
                            enabled=enabled,
                            status=status
                        ))
            
            return servers
        except Exception as e:
            logger.error(f"Failed to list servers: {e}")
            return []
    
    async def get_server_info(self, server_name: str) -> Optional[GatewayServerInfo]:
        """Get server info using CLI command."""
        try:
            # First try to inspect the server
            result = subprocess.run(
                ["docker", "mcp", "server", "inspect", server_name],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0:
                # Server exists and is enabled
                return GatewayServerInfo(
                    name=server_name,
                    enabled=True,
                    status="running"
                )
            else:
                # Check if server is in the available list but disabled
                available_result = subprocess.run(
                    ["docker", "mcp", "server", "list"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if available_result.returncode == 0:
                    available_servers = [s.strip() for s in available_result.stdout.strip().split(',')]
                    if server_name in available_servers:
                        return GatewayServerInfo(
                            name=server_name,
                            enabled=False,
                            status="disabled"
                        )
                
                # Server not found
                return None
                
        except Exception as e:
            logger.error(f"Failed to get server info for {server_name}: {e}")
            return None


# Factory function to create appropriate client
async def create_docker_gateway_client(prefer_http: bool = True, **kwargs) -> DockerMCPGatewayClient:
    """
    Create a Docker MCP Gateway client, preferring HTTP API over CLI.
    
    Args:
        prefer_http: Whether to prefer HTTP API over CLI fallback
        **kwargs: Additional arguments for the client constructor
        
    Returns:
        Configured gateway client
    """
    try:
        client = DockerMCPGatewayClient(**kwargs)
        await client.start()
        
        # Test if HTTP API is working
        if await client.is_healthy():
            logger.info("Using Docker MCP Gateway HTTP/SSE API")
            return client
        else:
            await client.stop()
            raise RuntimeError("Docker MCP Gateway not available on HTTP/SSE")
    except Exception as e:
        logger.error(f"Docker MCP Gateway HTTP/SSE API failed: {e}")
        raise RuntimeError(f"Docker MCP Gateway not available: {e}")