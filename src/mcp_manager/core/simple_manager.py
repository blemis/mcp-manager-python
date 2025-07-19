"""
Simplified MCP Manager that works directly with Claude Code's internal state.

This manager is a thin wrapper around claude mcp CLI commands.
"""

import asyncio
from typing import List, Optional

from mcp_manager.core.claude_interface import ClaudeInterface
from mcp_manager.core.exceptions import MCPManagerError
from mcp_manager.core.models import Server, ServerType, ServerScope
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class SimpleMCPManager:
    """Simplified MCP Manager that uses Claude Code's native state."""
    
    def __init__(self):
        """Initialize the manager."""
        self.claude = ClaudeInterface()
    
    async def list_servers(self) -> List[Server]:
        """
        List all MCP servers.
        
        Returns:
            List of servers from Claude's internal state
        """
        return self.claude.list_servers()
    
    async def add_server(
        self,
        name: str,
        server_type: ServerType,
        command: str,
        description: Optional[str] = None,
        env: Optional[dict] = None,
        args: Optional[List[str]] = None,
        scope: ServerScope = ServerScope.USER,
    ) -> Server:
        """
        Add a new MCP server.
        
        Args:
            name: Server name
            server_type: Type of server
            command: Server command
            description: Server description (ignored - Claude doesn't store this)
            env: Environment variables
            args: Command arguments
            scope: Server scope (ignored - Claude manages globally)
            
        Returns:
            The created server
        """
        logger.info(f"Adding server '{name}' to Claude")
        
        # Add to Claude
        success = self.claude.add_server(
            name=name,
            command=command,
            args=args,
            env=env,
        )
        
        if not success:
            raise MCPManagerError(f"Failed to add server '{name}'")
        
        # Return the server object
        server = Server(
            name=name,
            command=command,
            args=args or [],
            server_type=server_type,
            scope=ServerScope.USER,
            enabled=True,
            description=description,
            env=env or {},
        )
        
        return server
    
    async def remove_server(
        self,
        name: str,
        scope: Optional[ServerScope] = None,
    ) -> bool:
        """
        Remove an MCP server.
        
        Args:
            name: Server name to remove
            scope: Server scope (ignored - Claude manages globally)
            
        Returns:
            True if removed successfully
        """
        logger.info(f"Removing server '{name}' from Claude")
        
        return self.claude.remove_server(name)
    
    async def enable_server(self, name: str) -> Server:
        """
        Enable an MCP server.
        
        Note: In Claude's model, servers are enabled when added.
        This is a no-op if server exists, or adds it if discovered.
        
        Args:
            name: Server name to enable
            
        Returns:
            The server object
        """
        # Check if server already exists
        server = self.claude.get_server(name)
        if server:
            logger.info(f"Server '{name}' is already enabled in Claude")
            return server
        
        # If not found, we can't enable it without knowing the command
        raise MCPManagerError(
            f"Server '{name}' not found. Use 'add' to create it first, "
            "or use 'discover' to find available servers."
        )
    
    async def disable_server(self, name: str) -> Server:
        """
        Disable an MCP server.
        
        Note: In Claude's model, disabling means removing.
        
        Args:
            name: Server name to disable
            
        Returns:
            The server object before removal
        """
        # Get server before removing
        server = self.claude.get_server(name)
        if not server:
            raise MCPManagerError(f"Server '{name}' not found")
        
        # Remove from Claude (this is how we "disable")
        success = self.claude.remove_server(name)
        if not success:
            raise MCPManagerError(f"Failed to disable server '{name}'")
        
        # Return the server object with enabled=False
        server.enabled = False
        return server
    
    async def get_server(self, name: str) -> Optional[Server]:
        """
        Get details about a specific server.
        
        Args:
            name: Server name
            
        Returns:
            Server object if found, None otherwise
        """
        return self.claude.get_server(name)
    
    def server_exists(self, name: str) -> bool:
        """
        Check if a server exists.
        
        Args:
            name: Server name to check
            
        Returns:
            True if server exists
        """
        return self.claude.server_exists(name)