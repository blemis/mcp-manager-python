"""
Docker Desktop server handler using Docker MCP CLI commands.

This handler manages Docker Desktop MCP servers through Docker Desktop's
native CLI commands, providing proper enable/disable/status functionality
by directly querying Docker Desktop's actual state.
"""

from typing import Optional, Dict, List
import asyncio

from mcp_manager.core.handlers import ServerHandler
from mcp_manager.core.models import Server, ServerType
from mcp_manager.core.integrations.docker_mcp_gateway import create_docker_gateway_client
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class DockerDesktopServerHandler(ServerHandler):
    """
    Server handler for Docker Desktop MCP servers.
    
    Uses Docker Desktop's native CLI commands to provide consistent enable/disable
    operations that properly synchronize with Docker Desktop's actual state.
    """
    
    def __init__(self):
        """Initialize Docker Desktop server handler."""
        # Known Docker Desktop server mappings
        # Maps mcp-manager server names to Docker Desktop server names
        self._server_name_mapping = {
            'dd-SQLite': 'SQLite',
            'dd-Ref': 'Ref', 
            'dd-Search': 'Search',
            'dd-HTTP': 'HTTP',
            'dd-K8s': 'K8s',
            'dd-Terraform': 'Terraform', 
            'dd-AWS': 'AWS',
            'dd-filesystem': 'filesystem'
        }
        
        # Reverse mapping for looking up mcp-manager names
        self._reverse_mapping = {v: k for k, v in self._server_name_mapping.items()}
        
        # Gateway client for HTTP API communication
        self._gateway_client = None
        
        logger.debug("DockerDesktopServerHandler initialized")
    
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
        
        # Check if name starts with 'dd-' prefix and map to actual DD name
        if server.name.startswith('dd-'):
            potential_name = server.name[3:]  # Remove 'dd-' prefix
            # Check if it matches any known DD server (case-sensitive) - use async
            try:
                available_servers = asyncio.create_task(self._get_available_dd_servers())
                if hasattr(available_servers, 'result') and potential_name in available_servers.result():
                    return potential_name
                # For now, trust the mapping if it's a known DD server pattern
                if potential_name in ['SQLite', 'Ref', 'Search', 'HTTP', 'K8s', 'Terraform', 'AWS', 'filesystem']:
                    return potential_name
            except Exception:
                # Fallback to known patterns
                if potential_name in ['SQLite', 'Ref', 'Search', 'HTTP', 'K8s', 'Terraform', 'AWS', 'filesystem']:
                    return potential_name
        
        logger.debug(f"Could not determine Docker Desktop server name for: {server.name}")
        return None
    
    async def _get_gateway_client(self):
        """Get or create the Gateway HTTP API client."""
        if self._gateway_client is None:
            self._gateway_client = await create_docker_gateway_client(prefer_http=True)
        return self._gateway_client
    
    async def cleanup(self):
        """Clean up resources including gateway client."""
        if self._gateway_client:
            try:
                await self._gateway_client.stop()
            except Exception as e:
                logger.warning(f"Error stopping gateway client: {e}")
            finally:
                self._gateway_client = None
    
    async def close(self):
        """Close handler and clean up all resources."""
        await self.cleanup()
        logger.debug("DockerDesktopServerHandler closed")
    
    async def _get_available_dd_servers(self) -> List[str]:
        """Get list of available Docker Desktop servers via HTTP API."""
        try:
            gateway = await self._get_gateway_client()
            servers = await gateway.list_servers()
            return [server.name for server in servers]
                
        except Exception as e:
            logger.error(f"Error getting available DD servers via HTTP API: {e}")
            return []
    
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
            (server.command == 'docker' and 'mcp' in (server.args or []) and 'gateway' in (server.args or []))
        )
    
    async def _get_dd_server_status(self, dd_server_name: str) -> str:
        """
        Check if a Docker Desktop server is available and working via HTTP API.
        
        Args:
            dd_server_name: Docker Desktop server name (e.g., 'SQLite', 'Ref')
            
        Returns:
            'enabled' if server is available, 'disabled' if not available, 'error' if check failed
        """
        try:
            gateway = await self._get_gateway_client()
            
            # Get server info via HTTP API
            server_info = await gateway.get_server_info(dd_server_name)
            if server_info is None:
                return 'disabled'
            
            # Return status based on enabled state and server status
            if server_info.enabled and server_info.status == 'running':
                return 'enabled'
            else:
                return 'disabled'
                
        except Exception as e:
            logger.error(f"Error checking DD server {dd_server_name} status via HTTP API: {e}")
            return 'error'
    
    async def enable_server(self, server: Server) -> bool:
        """
        Enable a Docker Desktop MCP server via HTTP API.
        
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
            # Use HTTP API to enable server
            gateway = await self._get_gateway_client()
            success = await gateway.enable_server(dd_server_name)
            
            if success:
                logger.info(f"Successfully enabled Docker Desktop server: {server.name} ({dd_server_name})")
            else:
                logger.warning(f"Failed to enable Docker Desktop server {server.name} ({dd_server_name}) via HTTP API")
            
            return success
            
        except Exception as e:
            logger.error(f"Error enabling Docker Desktop server {server.name} via HTTP API: {e}")
            return False
    
    async def disable_server(self, server: Server) -> bool:
        """
        Disable a Docker Desktop MCP server via HTTP API.
        
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
            # Use HTTP API to disable server
            gateway = await self._get_gateway_client()
            success = await gateway.disable_server(dd_server_name)
            
            if success:
                logger.info(f"Successfully disabled Docker Desktop server: {server.name} ({dd_server_name})")
            else:
                logger.warning(f"Failed to disable Docker Desktop server {server.name} ({dd_server_name}) via HTTP API")
            
            return success
            
        except Exception as e:
            logger.error(f"Error disabling Docker Desktop server {server.name} via HTTP API: {e}")
            return False
    
    async def get_server_status(self, server: Server) -> str:
        """
        Get the current status of a Docker Desktop MCP server from database.
        The database is the source of truth for enabled/disabled status.
        
        Args:
            server: Server to check
            
        Returns:
            Status string ('enabled', 'disabled', 'error', 'unavailable')
        """
        if not self._is_docker_desktop_server(server):
            return 'unavailable'
        
        # Return the database status - that's the source of truth!
        # The server object passed in has the current database state
        if server.enabled:
            return 'enabled'
        else:
            return 'disabled'
    
    async def is_server_available(self, server: Server) -> bool:
        """
        Check if Docker Desktop MCP server is available via HTTP API.
        
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
            available_servers = await self._get_available_dd_servers()
            return dd_server_name in available_servers
        except Exception as e:
            logger.error(f"Error checking if server {server.name} is available: {e}")
            return False
    
    def supports_server(self, server: Server) -> bool:
        """
        Check if this handler supports the given server.
        
        Args:
            server: Server to check
            
        Returns:
            True if this handler can manage the server
        """
        return self._is_docker_desktop_server(server)
    
    async def close(self):
        """Close the handler and cleanup gateway client."""
        if self._gateway_client:
            try:
                await self._gateway_client.stop()
            except Exception as e:
                logger.error(f"Error closing gateway client: {e}")
            finally:
                self._gateway_client = None
        logger.debug("DockerDesktopServerHandler closed")