"""
Docker Desktop server handler using Docker MCP CLI commands.

This handler manages Docker Desktop MCP servers through Docker Desktop's
native CLI commands, providing proper enable/disable/status functionality
by directly querying Docker Desktop's actual state.
"""

import subprocess
from typing import Optional, Dict, List
import asyncio

from mcp_manager.core.handlers import ServerHandler
from mcp_manager.core.models import Server, ServerType
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
            # Check if it matches any known DD server (case-sensitive)
            available_servers = self._get_available_dd_servers()
            if potential_name in available_servers:
                return potential_name
        
        logger.debug(f"Could not determine Docker Desktop server name for: {server.name}")
        return None
    
    def _get_available_dd_servers(self) -> List[str]:
        """Get list of available Docker Desktop servers."""
        try:
            result = subprocess.run(
                ['docker', 'mcp', 'server', 'list'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Parse the output - it's a comma-separated list
                servers = [s.strip() for s in result.stdout.strip().split(',')]
                return servers
            else:
                logger.error(f"Failed to list DD servers: {result.stderr}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting available DD servers: {e}")
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
    
    def _get_dd_server_status(self, dd_server_name: str) -> str:
        """
        Check if a Docker Desktop server is available and working.
        
        Args:
            dd_server_name: Docker Desktop server name (e.g., 'SQLite', 'Ref')
            
        Returns:
            'enabled' if server is available, 'disabled' if not available, 'error' if check failed
        """
        try:
            # First check if server is in the available list
            available_servers = self._get_available_dd_servers()
            if dd_server_name not in available_servers:
                return 'disabled'
            
            # Try to inspect the server to see if it's actually working
            result = subprocess.run(
                ['docker', 'mcp', 'server', 'inspect', dd_server_name],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0:
                # Server is available and responding
                return 'enabled'
            else:
                logger.debug(f"DD server {dd_server_name} inspect failed: {result.stderr}")
                return 'disabled'
                
        except subprocess.TimeoutExpired:
            logger.debug(f"DD server {dd_server_name} inspect timed out")
            return 'error'
        except Exception as e:
            logger.error(f"Error checking DD server {dd_server_name} status: {e}")
            return 'error'
    
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
            # Use docker mcp server enable command
            result = subprocess.run(
                ['docker', 'mcp', 'server', 'enable', dd_server_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            success = result.returncode == 0
            if success:
                logger.info(f"Successfully enabled Docker Desktop server: {server.name} ({dd_server_name})")
            else:
                logger.warning(f"Failed to enable Docker Desktop server {server.name} ({dd_server_name}): {result.stderr}")
            
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
            # Use docker mcp server disable command
            result = subprocess.run(
                ['docker', 'mcp', 'server', 'disable', dd_server_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            success = result.returncode == 0
            if success:
                logger.info(f"Successfully disabled Docker Desktop server: {server.name} ({dd_server_name})")
            else:
                logger.warning(f"Failed to disable Docker Desktop server {server.name} ({dd_server_name}): {result.stderr}")
            
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
        
        # Get the actual status from Docker Desktop
        status = self._get_dd_server_status(dd_server_name)
        logger.debug(f"Docker Desktop server {server.name} ({dd_server_name}) status: {status}")
        return status
    
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
        
        available_servers = self._get_available_dd_servers()
        return dd_server_name in available_servers
    
    def supports_server(self, server: Server) -> bool:
        """
        Check if this handler supports the given server.
        
        Args:
            server: Server to check
            
        Returns:
            True if this handler can manage the server
        """
        return self._is_docker_desktop_server(server)