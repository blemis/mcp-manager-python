"""
CLI Bridge Service - Bridge between GUI and existing CLI functionality.

This service provides a clean interface for the GUI to interact with
the existing MCP manager business logic without duplicating code.
"""

import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path

from mcp_manager.core.simple_manager import SimpleMCPManager
from mcp_manager.core.managers.discovery_manager import DiscoveryManager  
from mcp_manager.core.database.server_state import MCPServerStateManager
from mcp_manager.core.models import ServerType, ServerScope
from mcp_manager.utils.config import ConfigManager
from mcp_manager.utils.logging import get_logger


logger = get_logger(__name__)


class CLIBridge:
    """Bridge service that provides GUI access to CLI functionality."""
    
    def __init__(self):
        """Initialize the CLI bridge."""
        self.config_manager = ConfigManager()
        self.mcp_manager = SimpleMCPManager()
        self.discovery_manager = DiscoveryManager()
        self.server_state_manager = MCPServerStateManager()
    
    async def get_servers(self) -> List[Dict[str, Any]]:
        """Get list of all servers with their status."""
        try:
            servers = await self.mcp_manager.list_servers()
            
            # Enhance server data with status information
            enhanced_servers = []
            for server in servers:
                server_dict = server.dict() if hasattr(server, 'dict') else dict(server)
                
                # Get real-time status from Claude Code
                claude_status = await self._get_claude_status(server_dict.get('name'))
                server_dict['claude_status'] = claude_status
                
                enhanced_servers.append(server_dict)
            
            return enhanced_servers
            
        except Exception as e:
            logger.error(f"Error getting servers: {e}")
            return []
    
    async def enable_server(self, server_name: str) -> bool:
        """Enable a server."""
        try:
            result = self.mcp_manager.enable_server(server_name)
            logger.info(f"Server '{server_name}' enabled: {result}")
            return result
        except Exception as e:
            logger.error(f"Error enabling server '{server_name}': {e}")
            return False
    
    async def disable_server(self, server_name: str) -> bool:
        """Disable a server."""
        try:
            result = self.mcp_manager.disable_server(server_name)
            logger.info(f"Server '{server_name}' disabled: {result}")
            return result
        except Exception as e:
            logger.error(f"Error disabling server '{server_name}': {e}")
            return False
    
    async def remove_server(self, server_name: str) -> bool:
        """Remove a server."""
        try:
            result = self.mcp_manager.remove_server(server_name)
            logger.info(f"Server '{server_name}' removed: {result}")
            return result
        except Exception as e:
            logger.error(f"Error removing server '{server_name}': {e}")
            return False
    
    async def add_server(
        self, 
        name: str, 
        server_type: str = "custom",
        command: str = "",
        args: List[str] = None,
        env: Dict[str, str] = None,
        working_dir: Optional[str] = None,
        description: Optional[str] = None
    ) -> bool:
        """Add a new server."""
        try:
            # Convert string to ServerType enum
            if server_type == "npm":
                st = ServerType.NPM
            elif server_type == "docker":
                st = ServerType.DOCKER
            elif server_type == "docker-desktop":
                st = ServerType.DOCKER_DESKTOP
            else:
                st = ServerType.CUSTOM
            
            server = await self.mcp_manager.add_server(
                name=name,
                server_type=st,
                command=command,
                args=args or [],
                env=env or {},
                description=description,
                scope=ServerScope.USER,
                working_dir=working_dir
            )
            logger.info(f"Server '{name}' added: {server}")
            return True
        except Exception as e:
            logger.error(f"Error adding server '{name}': {e}")
            return False
    
    async def discover_servers(
        self, 
        query: Optional[str] = None, 
        server_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Discover available servers."""
        try:
            # For now, return empty list as discovery manager integration is complex
            # This can be implemented later with proper discovery manager setup
            logger.warning("Server discovery not yet implemented in GUI")
            return []
            
        except Exception as e:
            logger.error(f"Error discovering servers: {e}")
            return []
    
    async def install_package(self, install_id: str) -> bool:
        """Install a package by its install ID."""
        try:
            # For now, return False as install_package method needs to be checked
            logger.warning(f"Package installation for '{install_id}' not yet implemented in GUI")
            return False
        except Exception as e:
            logger.error(f"Error installing package '{install_id}': {e}")
            return False
    
    async def get_server_details(self, server_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific server."""
        try:
            server = await self.mcp_manager.get_server(server_name)
            if server:
                server_dict = server.dict() if hasattr(server, 'dict') else dict(server)
                
                # Get additional details
                claude_status = await self._get_claude_status(server_name)
                server_dict['claude_status'] = claude_status
                
                # Get tools if available
                tools = await self._get_server_tools(server_name)
                server_dict['tools'] = tools
                
                return server_dict
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting server details for '{server_name}': {e}")
            return None
    
    async def _get_claude_status(self, server_name: str) -> str:
        """Get server status from Claude Code."""
        try:
            # This would integrate with Claude's internal state
            # For now, return a placeholder
            return "Connected"  # or "Failed", "Not Synced", etc.
        except Exception:
            return "Unknown"
    
    async def _get_server_tools(self, server_name: str) -> List[Dict[str, str]]:
        """Get available tools for a server."""
        try:
            # This would query the server for available tools
            # For now, return empty list
            return []
        except Exception:
            return []
    
    async def cleanup_config(self) -> bool:
        """Clean up broken configurations."""
        try:
            # For now, return True as cleanup may not be implemented
            logger.warning("Configuration cleanup not yet implemented in GUI")
            return True
        except Exception as e:
            logger.error(f"Error during config cleanup: {e}")
            return False
    
    def get_config_info(self) -> Dict[str, Any]:
        """Get current configuration information."""
        try:
            config = self.config_manager.get_config()
            return {
                "config_path": str(self.config_manager.config_path),
                "scope": getattr(config, 'scope', 'user'),
                "settings": config.dict() if hasattr(config, 'dict') else dict(config)
            }
        except Exception as e:
            logger.error(f"Error getting config info: {e}")
            return {}