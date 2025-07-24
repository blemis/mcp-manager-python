"""
Configuration loading and parsing for Claude interface.

Handles loading from user/project/internal config files.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

from mcp_manager.core.models import Server, ServerType, ServerScope
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ConfigLoader:
    """Loads and parses Claude configuration files."""
    
    def __init__(self):
        """Initialize config loader."""
        self.config_paths = self._get_config_paths()
    
    def load_all_servers(self) -> List[Server]:
        """Load servers from all config sources."""
        all_servers = []
        
        # Load from each config source in order of precedence
        for config_type, config_path in self.config_paths.items():
            try:
                servers = self._load_servers_from_config(config_path, config_type)
                if servers:
                    all_servers.extend(servers)
                    logger.debug(f"Loaded {len(servers)} servers from {config_type}")
            except Exception as e:
                logger.warning(f"Failed to load {config_type} config from {config_path}: {e}")
        
        return all_servers
    
    def load_config_by_type(self, config_type: str) -> Dict[str, Any]:
        """Load specific configuration type."""
        config_path = self.config_paths.get(config_type)
        if not config_path or not config_path.exists():
            return {}
        
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load {config_type} config: {e}")
            return {}
    
    def _get_config_paths(self) -> Dict[str, Path]:
        """Get all Claude configuration file paths."""
        paths = {}
        
        # User-level config
        user_config = Path.home() / ".config" / "claude-code" / "mcp-servers.json"
        if user_config.exists():
            paths['user'] = user_config
        
        # Project-level config
        project_config = Path.cwd() / ".mcp.json"
        if project_config.exists():
            paths['project'] = project_config
        
        # Claude internal config
        claude_config = Path.home() / ".claude.json"
        if claude_config.exists():
            paths['internal'] = claude_config
        
        logger.debug(f"Found config files: {list(paths.keys())}")
        return paths
    
    def _load_servers_from_config(self, config_path: Path, config_type: str) -> List[Server]:
        """Load servers from a specific config file."""
        try:
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            servers = []
            
            if config_type == 'internal':
                # Handle Claude internal config structure
                servers.extend(self._parse_internal_config(config_data))
            else:
                # Handle user/project config structure
                servers.extend(self._parse_standard_config(config_data, config_type))
            
            return servers
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {config_type} config: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to parse {config_type} config: {e}")
            return []
    
    def _parse_standard_config(self, config_data: Dict[str, Any], config_type: str) -> List[Server]:
        """Parse standard MCP config format."""
        servers = []
        mcp_servers = config_data.get('mcpServers', {})
        
        for server_name, server_config in mcp_servers.items():
            try:
                server = self._create_server_from_config(
                    server_name, server_config, config_type
                )
                if server:
                    servers.append(server)
            except Exception as e:
                logger.warning(f"Failed to parse server {server_name}: {e}")
        
        return servers
    
    def _parse_internal_config(self, config_data: Dict[str, Any]) -> List[Server]:
        """Parse Claude internal config format."""
        servers = []
        
        # Global MCP servers
        global_servers = config_data.get('mcpServers', {})
        for server_name, server_config in global_servers.items():
            try:
                server = self._create_server_from_config(
                    server_name, server_config, 'internal'
                )
                if server:
                    servers.append(server)
            except Exception as e:
                logger.warning(f"Failed to parse global server {server_name}: {e}")
        
        # Project-specific MCP servers
        project_configs = config_data.get('projectConfigs', {})
        for project_path, project_config in project_configs.items():
            project_servers = project_config.get('mcpServers', {})
            for server_name, server_config in project_servers.items():
                try:
                    server = self._create_server_from_config(
                        server_name, server_config, 'project', project_path
                    )
                    if server:
                        servers.append(server)
                except Exception as e:
                    logger.warning(f"Failed to parse project server {server_name}: {e}")
        
        return servers
    
    def _create_server_from_config(
        self, 
        server_name: str, 
        server_config: Dict[str, Any], 
        config_type: str,
        project_path: Optional[str] = None
    ) -> Optional[Server]:
        """Create Server object from config data."""
        try:
            # Extract command and args
            command = server_config.get('command', '')
            args = server_config.get('args', [])
            
            # Handle special case where command is in first arg
            if not command and args:
                command = args[0]
                args = args[1:]
            
            # Extract environment variables
            env = server_config.get('env', {})
            
            # Determine server type
            server_type = self._infer_server_type(command, args)
            
            # Determine scope
            if config_type == 'project':
                scope = ServerScope.PROJECT
            else:
                scope = ServerScope.USER
            
            # Handle enabled/disabled status
            enabled = server_config.get('enabled', True)
            
            # Working directory
            working_dir = server_config.get('workingDirectory')
            
            # Description (if available)
            description = server_config.get('description', '')
            
            server = Server(
                name=server_name,
                command=command,
                args=args,
                env=env,
                server_type=server_type,
                scope=scope,
                enabled=enabled,
                working_dir=working_dir,
                description=description
            )
            
            return server
            
        except Exception as e:
            logger.error(f"Failed to create server {server_name}: {e}")
            return None
    
    def _infer_server_type(self, command: str, args: List[str]) -> ServerType:
        """Infer server type from command and arguments."""
        if not command:
            return ServerType.CUSTOM
        
        command_lower = command.lower()
        
        # Check for common patterns
        if 'docker' in command_lower:
            return ServerType.DOCKER
        elif 'npx' in command_lower or 'node' in command_lower:
            return ServerType.NPM
        elif any('docker' in arg.lower() for arg in args):
            return ServerType.DOCKER_DESKTOP
        elif command_lower.endswith('.py') or 'python' in command_lower:
            return ServerType.PYTHON
        
        return ServerType.CUSTOM
    
    def get_config_file_mtimes(self) -> Dict[str, float]:
        """Get modification times for all config files."""
        mtimes = {}
        
        for config_type, config_path in self.config_paths.items():
            try:
                if config_path.exists():
                    mtimes[config_type] = config_path.stat().st_mtime
            except Exception as e:
                logger.warning(f"Failed to get mtime for {config_type}: {e}")
        
        return mtimes
    
    def validate_config_syntax(self, config_path: Path) -> tuple[bool, Optional[str]]:
        """Validate JSON syntax of config file."""
        try:
            with open(config_path, 'r') as f:
                json.load(f)
            return True, None
        except json.JSONDecodeError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Failed to read file: {e}"