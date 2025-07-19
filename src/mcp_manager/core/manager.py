"""
Core MCP Manager implementation.

Provides the main MCPManager class that handles server management,
configuration, and Claude CLI integration.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mcp_manager.core.exceptions import (
    ClaudeError,
    ConfigError,
    ServerError,
    ValidationError,
)
from mcp_manager.core.models import (
    Server,
    ServerCollection,
    ServerScope,
    ServerStatus,
    SystemInfo,
)
from mcp_manager.utils.config import Config, get_config
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class MCPManager:
    """Main MCP server management class."""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize MCP Manager.
        
        Args:
            config: Configuration instance (optional)
        """
        self.config = config or get_config()
        self.servers = ServerCollection()
        self._system_info: Optional[SystemInfo] = None
        
        # Initialize manager
        self._load_servers()
        
    def get_system_info(self) -> SystemInfo:
        """Get system information and dependency status."""
        if self._system_info is not None:
            return self._system_info
            
        logger.debug("Gathering system information")
        
        # Python version
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        
        # Platform
        import platform
        platform_name = platform.system()
        
        # Check Claude CLI
        claude_available, claude_version = self._check_command("claude", ["--version"])
        
        # Check NPM
        npm_available, npm_version = self._check_command("npm", ["--version"])
        
        # Check Docker  
        docker_available, docker_version = self._check_command("docker", ["--version"])
        
        # Check Git
        git_available, git_version = self._check_command("git", ["--version"])
        
        self._system_info = SystemInfo(
            python_version=python_version,
            platform=platform_name,
            claude_cli_available=claude_available,
            claude_cli_version=claude_version,
            npm_available=npm_available,
            npm_version=npm_version,
            docker_available=docker_available,
            docker_version=docker_version,
            git_available=git_available,
            git_version=git_version,
            config_dir=self.config.get_config_dir(),
            log_file=self.config.get_log_file(),
        )
        
        return self._system_info
        
    def _check_command(self, command: str, args: List[str]) -> Tuple[bool, Optional[str]]:
        """Check if a command is available and get its version."""
        try:
            result = subprocess.run(
                [command] + args,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                version = result.stdout.strip().split()[-1] if result.stdout else None
                return True, version
        except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return False, None
        
    def list_servers(self, scope: Optional[ServerScope] = None) -> List[Server]:
        """
        List MCP servers.
        
        Args:
            scope: Optional scope filter
            
        Returns:
            List of servers
        """
        logger.debug(f"Listing servers (scope: {scope})")
        
        if scope:
            return self.servers.get_by_scope(scope)
        return self.servers.all_servers()
        
    def add_server(
        self,
        name: str,
        command: str,
        scope: ServerScope = ServerScope.USER,
        **kwargs: Any,
    ) -> Server:
        """
        Add a new MCP server.
        
        Args:
            name: Server name
            command: Server command
            scope: Configuration scope
            **kwargs: Additional server options
            
        Returns:
            Created server
            
        Raises:
            ServerError: If server already exists or validation fails
        """
        logger.info(f"Adding server: {name} ({scope.value})")
        
        # Check if server already exists
        existing = self.servers.get_by_name(name)
        if existing:
            raise ServerError(f"Server '{name}' already exists")
            
        # Create server
        server = Server(
            name=name,
            command=command,
            scope=scope,
            **kwargs
        )
        
        # Add to collection
        self.servers.add_server(server)
        
        # Save configuration
        self._save_servers()
        
        logger.info(f"Successfully added server: {name}")
        return server
        
    def remove_server(self, name: str, scope: Optional[ServerScope] = None) -> bool:
        """
        Remove an MCP server.
        
        Args:
            name: Server name
            scope: Optional scope filter
            
        Returns:
            True if server was removed
            
        Raises:
            ServerError: If server not found
        """
        logger.info(f"Removing server: {name} (scope: {scope})")
        
        if not self.servers.remove_server(name, scope):
            raise ServerError(f"Server '{name}' not found")
            
        # Save configuration
        self._save_servers()
        
        logger.info(f"Successfully removed server: {name}")
        return True
        
    def enable_server(self, name: str) -> Server:
        """
        Enable an MCP server.
        
        Args:
            name: Server name
            
        Returns:
            Updated server
            
        Raises:
            ServerError: If server not found
        """
        logger.info(f"Enabling server: {name}")
        
        server = self.servers.get_by_name(name)
        if not server:
            raise ServerError(f"Server '{name}' not found")
            
        server.enabled = True
        self._save_servers()
        
        logger.info(f"Successfully enabled server: {name}")
        return server
        
    def disable_server(self, name: str) -> Server:
        """
        Disable an MCP server.
        
        Args:
            name: Server name
            
        Returns:
            Updated server
            
        Raises:
            ServerError: If server not found
        """
        logger.info(f"Disabling server: {name}")
        
        server = self.servers.get_by_name(name)
        if not server:
            raise ServerError(f"Server '{name}' not found")
            
        server.enabled = False
        self._save_servers()
        
        logger.info(f"Successfully disabled server: {name}")
        return server
        
    def get_server(self, name: str) -> Optional[Server]:
        """Get server by name."""
        return self.servers.get_by_name(name)
        
    def sync_with_claude(self) -> None:
        """Sync server configuration with Claude CLI."""
        logger.info("Syncing configuration with Claude CLI")
        
        # Check if Claude CLI is available
        system_info = self.get_system_info()
        if not system_info.claude_cli_available:
            raise ClaudeError("Claude CLI not available")
            
        # Get enabled servers
        enabled_servers = [s for s in self.servers.all_servers() if s.enabled]
        
        # Build Claude configuration
        claude_config = {
            "mcpServers": {
                server.name: server.to_claude_config()
                for server in enabled_servers
            }
        }
        
        # Write to Claude configuration file
        config_path = self.config.get_claude_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, "w") as f:
            json.dump(claude_config, f, indent=2)
            
        logger.info(f"Synced {len(enabled_servers)} servers to Claude configuration")
        
    def _load_servers(self) -> None:
        """Load servers from configuration files."""
        logger.debug("Loading server configurations")
        
        # Load from different scopes
        self._load_scope_servers(ServerScope.LOCAL)
        self._load_scope_servers(ServerScope.PROJECT)  
        self._load_scope_servers(ServerScope.USER)
        
        logger.debug(f"Loaded {len(self.servers.all_servers())} servers")
        
    def _load_scope_servers(self, scope: ServerScope) -> None:
        """Load servers for a specific scope."""
        config_file = self._get_scope_config_file(scope)
        
        if not config_file.exists():
            return
            
        try:
            with open(config_file) as f:
                data = json.load(f)
                
            servers_data = data.get("servers", [])
            for server_data in servers_data:
                server_data["scope"] = scope.value
                server = Server(**server_data)
                self.servers.add_server(server)
                
        except Exception as e:
            logger.error(f"Failed to load {scope.value} servers: {e}")
            
    def _save_servers(self) -> None:
        """Save servers to configuration files."""
        logger.debug("Saving server configurations")
        
        for scope in ServerScope:
            self._save_scope_servers(scope)
            
    def _save_scope_servers(self, scope: ServerScope) -> None:
        """Save servers for a specific scope."""
        config_file = self._get_scope_config_file(scope)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        servers = self.servers.get_by_scope(scope)
        
        data = {
            "servers": [
                server.model_dump(exclude={"scope"})
                for server in servers
            ]
        }
        
        with open(config_file, "w") as f:
            json.dump(data, f, indent=2, default=str)
            
    def _get_scope_config_file(self, scope: ServerScope) -> Path:
        """Get configuration file path for a scope."""
        if scope == ServerScope.LOCAL:
            return self.config.get_config_dir() / "local-servers.json"
        elif scope == ServerScope.PROJECT:
            return Path.cwd() / ".mcp-servers.json"
        elif scope == ServerScope.USER:
            return self.config.get_config_dir() / "user-servers.json"
        else:
            raise ValueError(f"Unknown scope: {scope}")