"""
Server Manager for basic CRUD operations on MCP servers.

Handles server lifecycle management including add, remove, enable, disable operations.
"""

import asyncio
import os
import subprocess
import threading
import time
from typing import List, Optional, Dict, Any

from mcp_manager.core.claude_interface import ClaudeInterface
from mcp_manager.core.exceptions import MCPManagerError
from mcp_manager.core.models import Server, ServerType, ServerScope
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ServerManager:
    """Manages basic server operations with Claude Code integration."""
    
    # Class-level sync protection (shared across all instances)
    _sync_lock = threading.Lock()
    _last_operation_time = 0
    _operation_cooldown = 2.0  # seconds to wait after operations before allowing sync
    
    def __init__(self, claude_interface: Optional[ClaudeInterface] = None):
        """Initialize server manager.
        
        Args:
            claude_interface: Optional Claude interface (will create if not provided)
        """
        self.claude = claude_interface or ClaudeInterface()
        logger.debug("ServerManager initialized")
    
    def add_server(self, name: str, command: str, args: Optional[List[str]] = None, 
                   env: Optional[Dict[str, str]] = None, 
                   working_dir: Optional[str] = None,
                   server_type: ServerType = ServerType.CUSTOM,
                   scope: ServerScope = ServerScope.USER) -> bool:
        """
        Add a new MCP server.
        
        Args:
            name: Server name
            command: Command to start the server
            args: Command arguments
            env: Environment variables
            working_dir: Working directory
            server_type: Server type (defaults to CUSTOM)
            scope: Configuration scope (user or project)
            
        Returns:
            True if server was added successfully
        """
        with self._sync_lock:
            try:
                logger.info(f"Adding server: {name}")
                
                # Record operation time for sync cooldown
                self._last_operation_time = time.time()
                
                # Create server model
                server = Server(
                    name=name,
                    command=command,
                    args=args or [],
                    env=env or {},
                    working_dir=working_dir,
                    server_type=server_type,
                    scope=scope
                )
                
                # Add via Claude interface
                success = self.claude.add_server(
                    name=server.name,
                    command=server.command,
                    args=server.args,
                    env=server.env
                )
                
                if success:
                    logger.info(f"Successfully added server: {name}")
                else:
                    logger.error(f"Failed to add server: {name}")
                
                return success
                
            except Exception as e:
                logger.error(f"Error adding server {name}: {e}")
                raise MCPManagerError(f"Failed to add server {name}: {e}")
    
    def remove_server(self, name: str, scope: ServerScope = ServerScope.USER) -> bool:
        """
        Remove an MCP server.
        
        Args:
            name: Server name to remove
            scope: Configuration scope (user or project)
            
        Returns:
            True if server was removed successfully
        """
        with self._sync_lock:
            try:
                logger.info(f"Removing server: {name}")
                
                # Record operation time for sync cooldown
                self._last_operation_time = time.time()
                
                # Remove via Claude interface
                success = self.claude.remove_server(name, scope)
                
                if success:
                    logger.info(f"Successfully removed server: {name}")
                else:
                    logger.warning(f"Server {name} may not have existed")
                
                return success
                
            except Exception as e:
                logger.error(f"Error removing server {name}: {e}")
                raise MCPManagerError(f"Failed to remove server {name}: {e}")
    
    def enable_server(self, name: str, scope: ServerScope = ServerScope.USER) -> bool:
        """
        Enable an MCP server.
        
        Args:
            name: Server name to enable
            scope: Configuration scope
            
        Returns:
            True if server was enabled successfully
        """
        with self._sync_lock:
            try:
                logger.info(f"Enabling server: {name}")
                
                # Record operation time for sync cooldown
                self._last_operation_time = time.time()
                
                # Enable via Claude interface
                success = self.claude.enable_server(name, scope)
                
                if success:
                    logger.info(f"Successfully enabled server: {name}")
                else:
                    logger.error(f"Failed to enable server: {name}")
                
                return success
                
            except Exception as e:
                logger.error(f"Error enabling server {name}: {e}")
                raise MCPManagerError(f"Failed to enable server {name}: {e}")
    
    def disable_server(self, name: str, scope: ServerScope = ServerScope.USER) -> bool:
        """
        Disable an MCP server.
        
        Args:
            name: Server name to disable  
            scope: Configuration scope
            
        Returns:
            True if server was disabled successfully
        """
        with self._sync_lock:
            try:
                logger.info(f"Disabling server: {name}")
                
                # Record operation time for sync cooldown
                self._last_operation_time = time.time()
                
                # Disable via Claude interface
                success = self.claude.disable_server(name, scope)
                
                if success:
                    logger.info(f"Successfully disabled server: {name}")
                else:
                    logger.error(f"Failed to disable server: {name}")
                
                return success
                
            except Exception as e:
                logger.error(f"Error disabling server {name}: {e}")
                raise MCPManagerError(f"Failed to disable server {name}: {e}")
    
    def list_servers(self) -> List[Server]:
        """
        List all MCP servers.
        
        Returns:
            List of Server objects
        """
        try:
            logger.debug("Listing all servers")
            servers = self.claude.list_servers()
            logger.debug(f"Found {len(servers)} servers")
            return servers
            
        except Exception as e:
            logger.error(f"Error listing servers: {e}")
            raise MCPManagerError(f"Failed to list servers: {e}")
    
    def list_servers_fast(self) -> List[Server]:
        """
        List all MCP servers using fast cached method.
        
        Returns:
            List of Server objects
        """
        try:
            logger.debug("Listing all servers (fast cached)")
            servers = self.claude.list_servers_cached()
            logger.debug(f"Found {len(servers)} servers (cached)")
            return servers
            
        except Exception as e:
            logger.error(f"Error listing servers (fast): {e}")
            raise MCPManagerError(f"Failed to list servers (fast): {e}")
    
    def get_server(self, name: str) -> Optional[Server]:
        """
        Get a specific server by name.
        
        Args:
            name: Server name
            
        Returns:
            Server object if found, None otherwise
        """
        try:
            servers = self.list_servers_fast()
            for server in servers:
                if server.name == name:
                    return server
            return None
            
        except Exception as e:
            logger.error(f"Error getting server {name}: {e}")
            raise MCPManagerError(f"Failed to get server {name}: {e}")
    
    def server_exists(self, name: str) -> bool:
        """
        Check if a server exists.
        
        Args:
            name: Server name to check
            
        Returns:
            True if server exists
        """
        return self.get_server(name) is not None
    
    def wait_for_sync_cooldown(self) -> None:
        """Wait for sync cooldown period after operations."""
        with self._sync_lock:
            elapsed = time.time() - self._last_operation_time
            if elapsed < self._operation_cooldown:
                wait_time = self._operation_cooldown - elapsed
                logger.debug(f"Waiting {wait_time:.1f}s for sync cooldown")
                time.sleep(wait_time)