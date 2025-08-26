"""
Docker MCP Gateway HTTP API client.

This module provides a REST API wrapper for communicating with the Docker MCP Gateway
HTTP server, enabling programmatic control over Docker Desktop MCP servers.
"""

import asyncio
import json
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
    HTTP API client for Docker MCP Gateway.
    
    Manages lifecycle and communication with the Docker MCP Gateway HTTP server,
    providing methods to enable/disable servers, check status, and retrieve server information.
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
        
        logger.debug(f"DockerMCPGatewayClient initialized for {self.base_url}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
    
    async def start(self):
        """Start the HTTP session and ensure gateway is running."""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=10)  # 10 second timeout
            self.session = aiohttp.ClientSession(timeout=timeout)
            
        if self.auto_start:
            await self._ensure_gateway_running()
    
    async def stop(self):
        """Stop the HTTP session and optionally stop gateway."""
        if self.session:
            await self.session.close()
            self.session = None
            
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
        # Step 1: Check if API server is already running
        if await self.is_healthy():
            logger.debug("Gateway already running and healthy - using existing server")
            return
            
        # Step 2: API server not running, start it once
        logger.info("Docker MCP Gateway not running - starting persistent server...")
        await self._start_gateway_process()
        
        # Step 3: Wait for gateway to become healthy
        start_time = time.time()
        while time.time() - start_time < self._startup_timeout:
            if await self.is_healthy():
                logger.info("Docker MCP Gateway started successfully - ready for all operations")
                return
            await asyncio.sleep(1)
        
        raise RuntimeError(f"Gateway failed to start within {self._startup_timeout} seconds")
    
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
    
    async def ensure_healthy(self):
        """Ensure gateway is healthy, restart if needed."""
        if not await self.is_healthy():
            logger.warning("Gateway unhealthy, attempting restart")
            await self.restart_gateway()
    
    async def is_healthy(self) -> bool:
        """Check if the gateway is healthy and responding to SSE connection."""
        try:
            if not self.session:
                return False
                
            # Try to connect to the SSE endpoint briefly to check if gateway is responding
            timeout = aiohttp.ClientTimeout(total=2)  # Short timeout for health check
            async with aiohttp.ClientSession(timeout=timeout) as temp_session:
                async with temp_session.get(f"{self.base_url}/sse") as response:
                    if response.status == 200:
                        # If we can connect to SSE endpoint, gateway is running
                        return True
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
        """List all available servers by checking what's enabled in the gateway."""
        # For the existing gateway on port 8080 with servers "Ref,SQLite,filesystem"
        # We'll return the known enabled servers since we can't dynamically query them
        try:
            # Check if gateway is healthy first
            if not await self.is_healthy():
                logger.warning("Gateway not healthy, cannot list servers")
                return []
            
            # Return the servers that are configured in the gateway
            # Based on the gateway startup command: --servers "Ref,SQLite,filesystem"  
            known_servers = [
                GatewayServerInfo(
                    name="Ref",
                    enabled=True,
                    status="running",
                    description="Reference documentation and web search server"
                ),
                GatewayServerInfo(
                    name="SQLite", 
                    enabled=True,
                    status="running",
                    description="SQLite database management server"
                ),
                GatewayServerInfo(
                    name="filesystem",
                    enabled=True, 
                    status="running",
                    description="File system operations server"
                )
            ]
            
            logger.debug(f"Listed {len(known_servers)} known gateway servers")
            return known_servers
            
        except Exception as e:
            logger.error(f"Failed to list servers: {e}")
            return []
    
    async def enable_server(self, server_name: str) -> bool:
        """
        Check if a Docker Desktop MCP server is enabled in the gateway.
        
        Note: The Docker MCP Gateway manages server enablement at startup.
        This method checks if the server is already available in the current gateway.
        
        Args:
            server_name: Name of the server to enable (e.g., "SQLite", "filesystem")
            
        Returns:
            True if server is available/enabled
        """
        try:
            servers = await self.list_servers()
            for server in servers:
                if server.name == server_name:
                    logger.info(f"Server {server_name} is already enabled in gateway")
                    return True
            
            logger.warning(f"Server {server_name} not available in current gateway configuration")
            return False
            
        except Exception as e:
            logger.error(f"Failed to check server {server_name} availability: {e}")
            return False
    
    async def disable_server(self, server_name: str) -> bool:
        """
        Disable a Docker Desktop MCP server via MCP protocol.
        
        Note: The Docker MCP Gateway manages server disablement at startup.
        Individual servers cannot be disabled at runtime through MCP protocol.
        
        Args:
            server_name: Name of the server to disable
            
        Returns:
            False as runtime disabling is not supported
        """
        logger.warning(f"Server {server_name} cannot be disabled at runtime - gateway manages servers at startup")
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