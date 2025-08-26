"""
Docker Desktop server handler using Docker MCP Gateway API.

This handler manages Docker Desktop MCP servers through the Docker MCP Gateway
HTTP API, providing proper enable/disable/status functionality that integrates
with the overall mcp-manager architecture.
"""

from typing import Optional, Dict, Any
import asyncio

from mcp_manager.core.handlers import ServerHandler
from mcp_manager.core.models import Server, ServerType
from mcp_manager.core.integrations.docker_mcp_gateway import (
    DockerMCPGatewayClient, 
    create_docker_gateway_client,
    GatewayServerInfo
)
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class DockerDesktopServerHandler(ServerHandler):
    """
    Server handler for Docker Desktop MCP servers.
    
    Uses the Docker MCP Gateway HTTP API to provide consistent enable/disable
    operations that properly synchronize with Claude Code's internal state.
    """
    
    def __init__(self, gateway_host: str = "localhost", gateway_port: int = 8080):
        """
        Initialize Docker Desktop server handler.
        
        Args:
            gateway_host: Docker MCP Gateway host
            gateway_port: Docker MCP Gateway port
        """
        self.gateway_host = gateway_host
        self.gateway_port = gateway_port
        self._gateway_client: Optional[DockerMCPGatewayClient] = None
        self._client_lock = asyncio.Lock()
        
        # Known Docker Desktop server mappings
        # Maps mcp-manager server names to Docker Desktop server names
        self._server_name_mapping = {
            'dd-SQLite': 'sqlite',
            'dd-Ref': 'filesystem', 
            'dd-Search': 'search',
            'dd-HTTP': 'http',
            'dd-K8s': 'k8s',
            'dd-Terraform': 'terraform', 
            'dd-AWS': 'aws'
        }
        
        # Reverse mapping for looking up mcp-manager names
        self._reverse_mapping = {v: k for k, v in self._server_name_mapping.items()}
        
        logger.debug(f"DockerDesktopServerHandler initialized for {gateway_host}:{gateway_port}")
    
    async def _get_gateway_client(self) -> DockerMCPGatewayClient:
        """Get or create the gateway client with proper lifecycle management."""
        async with self._client_lock:
            if self._gateway_client is None:
                self._gateway_client = await create_docker_gateway_client(
                    prefer_http=True,
                    host=self.gateway_host,
                    port=self.gateway_port,
                    auto_start=True
                )
                logger.debug("Created new gateway client")
            return self._gateway_client
    
    async def close(self):
        """Close the gateway client and cleanup resources."""
        async with self._client_lock:
            if self._gateway_client:
                await self._gateway_client.stop()
                self._gateway_client = None
                logger.debug("Gateway client closed")
    
    def _get_dd_server_name(self, server: Server) -> Optional[str]:
        """
        Get Docker Desktop server name from mcp-manager server.
        
        Args:
            server: MCP Manager server
            
        Returns:
            Docker Desktop server name or None if not a DD server
        """
        # Check direct mapping first
        dd_name = self._server_name_mapping.get(server.name)
        if dd_name:
            return dd_name
        
        # Check if name starts with 'dd-' prefix
        if server.name.startswith('dd-'):
            potential_name = server.name[3:].lower()  # Remove 'dd-' prefix
            if potential_name in self._reverse_mapping.values():
                return potential_name
        
        # Check server type
        if server.server_type == ServerType.DOCKER_DESKTOP:
            # Try to extract from args or command
            if server.args:
                for arg in server.args:
                    if arg in self._reverse_mapping.values():
                        return arg
        
        logger.debug(f"Could not determine Docker Desktop server name for: {server.name}")
        return None
    
    def _is_docker_desktop_server(self, server: Server) -> bool:
        """
        Check if server is a Docker Desktop MCP server.
        
        Args:
            server: Server to check
            
        Returns:
            True if this is a Docker Desktop server
        """
        return (
            server.server_type == ServerType.DOCKER_DESKTOP or
            server.name in self._server_name_mapping or
            server.name.startswith('dd-') or
            (server.command == 'docker' and 'mcp' in (server.args or []))
        )
    
    async def enable_server(self, server: Server) -> bool:
        """
        Enable a Docker Desktop MCP server.
        
        Args:
            server: Server to enable
            
        Returns:
            True if successfully enabled
        """
        if not self._is_docker_desktop_server(server):
            logger.warning(f"Server {server.name} is not a Docker Desktop server")
            return False
        
        dd_server_name = self._get_dd_server_name(server)
        if not dd_server_name:
            logger.error(f"Could not determine Docker Desktop server name for {server.name}")
            return False
        
        try:
            client = await self._get_gateway_client()
            success = await client.enable_server(dd_server_name)
            
            if success:
                logger.info(f"Successfully enabled Docker Desktop server: {server.name} ({dd_server_name})")
            else:
                logger.warning(f"Failed to enable Docker Desktop server: {server.name} ({dd_server_name})")
            
            return success
            
        except Exception as e:
            logger.error(f"Error enabling Docker Desktop server {server.name}: {e}")
            return False
    
    async def disable_server(self, server: Server) -> bool:
        """
        Disable a Docker Desktop MCP server.
        
        Args:
            server: Server to disable
            
        Returns:
            True if successfully disabled
        """
        if not self._is_docker_desktop_server(server):
            logger.warning(f"Server {server.name} is not a Docker Desktop server")
            return False
        
        dd_server_name = self._get_dd_server_name(server)
        if not dd_server_name:
            logger.error(f"Could not determine Docker Desktop server name for {server.name}")
            return False
        
        try:
            client = await self._get_gateway_client()
            success = await client.disable_server(dd_server_name)
            
            if success:
                logger.info(f"Successfully disabled Docker Desktop server: {server.name} ({dd_server_name})")
            else:
                logger.warning(f"Failed to disable Docker Desktop server: {server.name} ({dd_server_name})")
            
            return success
            
        except Exception as e:
            logger.error(f"Error disabling Docker Desktop server {server.name}: {e}")
            return False
    
    async def get_server_status(self, server: Server) -> str:
        """
        Get the current status of a Docker Desktop MCP server.
        
        Args:
            server: Server to check
            
        Returns:
            Status string ('enabled', 'disabled', 'error', 'unavailable')
        """
        if not self._is_docker_desktop_server(server):
            return 'unavailable'
        
        dd_server_name = self._get_dd_server_name(server)
        if not dd_server_name:
            return 'error'
        
        try:
            client = await self._get_gateway_client()
            server_info = await client.get_server_info(dd_server_name)
            
            if server_info is None:
                return 'unavailable'
            
            # Map gateway status to our status
            if server_info.enabled:
                return 'enabled'
            else:
                return 'disabled'
                
        except Exception as e:
            logger.error(f"Error getting status for Docker Desktop server {server.name}: {e}")
            return 'error'
    
    async def is_server_available(self, server: Server) -> bool:
        """
        Check if Docker Desktop MCP server is available.
        
        Args:
            server: Server to check
            
        Returns:
            True if server is available
        """
        if not self._is_docker_desktop_server(server):
            return False
        
        dd_server_name = self._get_dd_server_name(server)
        if not dd_server_name:
            return False
        
        try:
            client = await self._get_gateway_client()
            server_info = await client.get_server_info(dd_server_name)
            return server_info is not None
            
        except Exception as e:
            logger.error(f"Error checking availability of Docker Desktop server {server.name}: {e}")
            return False
    
    async def list_available_servers(self) -> Dict[str, GatewayServerInfo]:
        """
        List all available Docker Desktop servers.
        
        Returns:
            Dictionary mapping server names to their info
        """
        try:
            client = await self._get_gateway_client()
            servers = await client.list_servers()
            
            return {server.name: server for server in servers}
            
        except Exception as e:
            logger.error(f"Error listing Docker Desktop servers: {e}")
            return {}
    
    async def sync_all_servers(self, desired_enabled_servers: list) -> tuple:
        """
        Synchronize all Docker Desktop servers to match desired state.
        
        Args:
            desired_enabled_servers: List of server names that should be enabled
            
        Returns:
            Tuple of (successfully_enabled, successfully_disabled)
        """
        try:
            # Map mcp-manager names to DD names
            dd_server_names = []
            for server_name in desired_enabled_servers:
                if server_name in self._server_name_mapping:
                    dd_server_names.append(self._server_name_mapping[server_name])
                elif server_name.startswith('dd-'):
                    potential_name = server_name[3:].lower()
                    if potential_name in self._reverse_mapping.values():
                        dd_server_names.append(potential_name)
            
            client = await self._get_gateway_client()
            enabled, disabled = await client.sync_servers(dd_server_names)
            
            # Map back to mcp-manager names
            enabled_mm_names = [self._reverse_mapping.get(name, f'dd-{name.title()}') for name in enabled]
            disabled_mm_names = [self._reverse_mapping.get(name, f'dd-{name.title()}') for name in disabled]
            
            return enabled_mm_names, disabled_mm_names
            
        except Exception as e:
            logger.error(f"Error synchronizing Docker Desktop servers: {e}")
            return [], []
    
    def get_server_name_mapping(self) -> Dict[str, str]:
        """Get the mapping of mcp-manager names to Docker Desktop names."""
        return self._server_name_mapping.copy()
    
    def supports_server(self, server: Server) -> bool:
        """
        Check if this handler supports the given server.
        
        Args:
            server: Server to check
            
        Returns:
            True if this handler can manage the server
        """
        return self._is_docker_desktop_server(server)