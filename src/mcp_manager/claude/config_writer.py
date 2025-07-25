"""
Configuration writing and management for Claude interface.

Direct config file manipulation without relying on Claude CLI.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from mcp_manager.core.models import Server, ServerScope
from mcp_manager.core.exceptions import MCPManagerError
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ConfigWriter:
    """Manages writing to Claude configuration files."""
    
    def __init__(self):
        """Initialize config writer."""
        self.config_paths = self._get_config_paths()
    
    def add_server(self, server: Server) -> bool:
        """
        Add server to appropriate config file.
        
        Args:
            server: Server to add
            
        Returns:
            True if successful
            
        Raises:
            MCPManagerError: If addition fails
        """
        try:
            config_path = self._get_config_path_for_scope(server.scope)
            
            # Load existing config
            config_data = self._load_config(config_path)
            
            # Ensure mcpServers section exists
            if 'mcpServers' not in config_data:
                config_data['mcpServers'] = {}
            
            # Add server
            config_data['mcpServers'][server.name] = self._server_to_config(server)
            
            # Save config
            self._save_config(config_path, config_data)
            
            logger.info(f"Added server '{server.name}' to {server.scope.value} config")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add server '{server.name}': {e}")
            raise MCPManagerError(f"Failed to add server: {e}")
    
    def remove_server(self, name: str, scope: Optional[ServerScope] = None) -> bool:
        """
        Remove server from config files.
        
        Args:
            name: Server name to remove
            scope: Specific scope to remove from, or None to remove from any scope
            
        Returns:
            True if server was found and removed
        """
        removed = False
        
        if scope:
            # Remove from specific scope
            config_path = self._get_config_path_for_scope(scope)
            if self._remove_server_from_config(config_path, name):
                removed = True
                logger.info(f"Removed server '{name}' from {scope.value} config")
        else:
            # Remove from any scope where found
            for scope_enum in ServerScope:
                config_path = self._get_config_path_for_scope(scope_enum)
                if self._remove_server_from_config(config_path, name):
                    removed = True
                    logger.info(f"Removed server '{name}' from {scope_enum.value} config")
        
        if not removed:
            logger.warning(f"Server '{name}' not found in any config")
        
        return removed
    
    def update_server(self, server: Server) -> bool:
        """
        Update existing server configuration.
        
        Args:
            server: Updated server configuration
            
        Returns:
            True if successful
        """
        try:
            config_path = self._get_config_path_for_scope(server.scope)
            config_data = self._load_config(config_path)
            
            if 'mcpServers' not in config_data:
                config_data['mcpServers'] = {}
            
            if server.name not in config_data['mcpServers']:
                raise MCPManagerError(f"Server '{server.name}' not found in {server.scope.value} config")
            
            # Update server
            config_data['mcpServers'][server.name] = self._server_to_config(server)
            
            # Save config
            self._save_config(config_path, config_data)
            
            logger.info(f"Updated server '{server.name}' in {server.scope.value} config")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update server '{server.name}': {e}")
            raise MCPManagerError(f"Failed to update server: {e}")
    
    def server_exists(self, name: str, scope: Optional[ServerScope] = None) -> bool:
        """
        Check if server exists in config.
        
        Args:
            name: Server name
            scope: Specific scope to check, or None to check all scopes
            
        Returns:
            True if server exists
        """
        if scope:
            # Check specific scope
            config_path = self._get_config_path_for_scope(scope)
            config_data = self._load_config(config_path)
            return name in config_data.get('mcpServers', {})
        else:
            # Check all scopes
            for scope_enum in ServerScope:
                if self.server_exists(name, scope_enum):
                    return True
            return False
    
    def _get_config_paths(self) -> Dict[str, Path]:
        """Get all Claude configuration file paths."""
        paths = {}
        
        # User-level config
        user_config = Path.home() / ".config" / "claude-code" / "mcp-servers.json"
        paths['user'] = user_config
        
        # Project-level config
        project_config = Path.cwd() / ".mcp.json"
        paths['project'] = project_config
        
        return paths
    
    def _get_config_path_for_scope(self, scope: ServerScope) -> Path:
        """Get config file path for given scope."""
        if scope == ServerScope.USER:
            return self.config_paths['user']
        elif scope == ServerScope.PROJECT:
            return self.config_paths['project']
        else:
            # Default to user scope
            return self.config_paths['user']
    
    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load config from file, creating if it doesn't exist."""
        if not config_path.exists():
            # Create directory if needed
            config_path.parent.mkdir(parents=True, exist_ok=True)
            # Create empty config
            return {"mcpServers": {}}
        
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in {config_path}, creating new config")
            return {"mcpServers": {}}
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            return {"mcpServers": {}}
    
    def _save_config(self, config_path: Path, config_data: Dict[str, Any]) -> None:
        """Save config to file with backup."""
        try:
            # Create backup if file exists
            if config_path.exists():
                backup_path = config_path.with_suffix(
                    f".json.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                )
                shutil.copy2(config_path, backup_path)
                logger.debug(f"Created backup: {backup_path}")
            
            # Ensure directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write config
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2, sort_keys=True)
            
            logger.debug(f"Saved config to {config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save config to {config_path}: {e}")
            raise MCPManagerError(f"Failed to save config: {e}")
    
    def _remove_server_from_config(self, config_path: Path, name: str) -> bool:
        """Remove server from specific config file."""
        try:
            config_data = self._load_config(config_path)
            
            if 'mcpServers' not in config_data:
                return False
            
            if name not in config_data['mcpServers']:
                return False
            
            # Remove server
            del config_data['mcpServers'][name]
            
            # Save config
            self._save_config(config_path, config_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove server '{name}' from {config_path}: {e}")
            return False
    
    def _server_to_config(self, server: Server) -> Dict[str, Any]:
        """Convert Server object to config format."""
        config = {
            "command": server.command,
            "args": server.args or []
        }
        
        if server.env:
            config["env"] = server.env
        
        if server.working_dir:
            config["workingDirectory"] = server.working_dir
        
        if not server.enabled:
            config["enabled"] = False
        
        if server.description:
            config["description"] = server.description
        
        return config