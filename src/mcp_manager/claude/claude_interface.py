"""
Main orchestrator for Claude Code's MCP management interface.

This module provides a unified interface to Claude Code's internal MCP state
by coordinating the focused modules for client operations, server management,
sync operations, and Docker gateway handling.
"""

import json
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from mcp_manager.claude.claude_client import ClaudeClient
from mcp_manager.claude.docker_gateway import DockerGatewayExpander
from mcp_manager.claude.server_operations import ServerOperations
from mcp_manager.claude.sync_manager import SyncManager
from mcp_manager.core.models import Server, ServerScope, ServerType
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ClaudeInterface:
    """
    Main interface to Claude Code's MCP management with memory cache and background sync.
    
    This class orchestrates all Claude interface operations by delegating to
    focused modules for specific responsibilities.
    """
    
    def __init__(self, cache_ttl: float = 30.0, sync_interval: float = 60.0):
        """
        Initialize Claude interface with caching and sync.
        
        Args:
            cache_ttl: Cache time-to-live in seconds
            sync_interval: Background sync interval in seconds
        """
        # Initialize core components
        self.client = ClaudeClient()
        self.server_ops = ServerOperations(self.client.claude_path, self.client._get_env)
        self.docker_gateway = DockerGatewayExpander()
        self.sync_manager = SyncManager(cache_ttl, sync_interval)
        
        # Memory cache for server list
        self._server_cache: Optional[List[Server]] = None
        self._cache_timestamp: float = 0
        self._cache_lock = threading.RLock()
        
        # Start background sync if enabled
        sync_enabled = True  # Could be made configurable
        if sync_enabled:
            self.sync_manager.start_background_sync(
                refresh_callback=self._refresh_cache,
                sync_callback=self._sync_to_database
            )
        
        logger.info("ClaudeInterface initialized", extra={
            "cache_ttl": cache_ttl,
            "sync_interval": sync_interval,
            "sync_enabled": sync_enabled
        })
    
    def __del__(self):
        """Cleanup background sync thread."""
        if hasattr(self, 'sync_manager'):
            self.sync_manager.stop_background_sync()
    
    def get_config_path(self) -> Path:
        """Get the path to Claude's configuration file."""
        return Path.home() / ".claude.json"
    
    def list_servers_cached(self) -> List[Server]:
        """
        Get servers from memory cache (ultra-fast).
        
        Returns:
            Cached list of servers, refreshed if expired or invalid
        """
        with self._cache_lock:
            # Check if cache is valid
            if (self._server_cache is not None and 
                self.sync_manager.is_cache_valid(self._cache_timestamp)):
                return self._server_cache.copy()
            
            # Cache expired or invalid, refresh
            self._server_cache = self._load_servers_from_config()
            self._cache_timestamp = time.time()
            
            logger.debug(f"Cache miss - loaded {len(self._server_cache)} servers")
            return self._server_cache.copy()
    
    def invalidate_cache(self):
        """Manually invalidate the cache."""
        with self._cache_lock:
            self._server_cache = None
            self._cache_timestamp = 0
            logger.debug("Cache manually invalidated")
    
    def _refresh_cache(self):
        """Refresh the server cache."""
        with self._cache_lock:
            try:
                self._server_cache = self._load_servers_from_config()
                self._cache_timestamp = time.time()
                logger.debug(f"Cache refreshed with {len(self._server_cache)} servers")
            except Exception as e:
                logger.warning(f"Failed to refresh cache: {e}")
    
    async def _sync_to_database(self):
        """Async sync server list to database."""
        with self._cache_lock:
            servers = self._server_cache.copy() if self._server_cache else []
        
        if servers:
            await self.sync_manager.sync_to_database(servers)
    
    def _load_servers_from_config(self) -> List[Server]:
        """
        Fast server listing by reading config files directly.
        
        Returns:
            List of servers from config files without health checks
        """
        servers = []
        
        # Read user-level config
        servers.extend(self._load_user_config())
        
        # Read project-level config
        servers.extend(self._load_project_config())
        
        # Read internal state from ~/.claude.json
        servers.extend(self._load_internal_config())
        
        logger.debug(f"Found {len(servers)} servers from config files")
        return servers
    
    def _load_user_config(self) -> List[Server]:
        """Load servers from user-level configuration."""
        servers = []
        user_config_path = Path.home() / ".config" / "claude-code" / "mcp-servers.json"
        
        if not user_config_path.exists():
            return servers
        
        try:
            with open(user_config_path, 'r') as f:
                user_config = json.load(f)
                mcp_servers = user_config.get("mcpServers", {})
                
                for name, config in mcp_servers.items():
                    server = Server(
                        name=name,
                        command=config.get("command", ""),
                        args=config.get("args", []),
                        env=config.get("env", {}),
                        server_type=self._infer_server_type(config.get("command", "")),
                        scope=ServerScope.USER,
                        description=config.get("description", f"User-level server: {name}")
                    )
                    servers.append(server)
                    
        except Exception as e:
            logger.warning(f"Failed to read user config: {e}")
        
        return servers
    
    def _load_project_config(self) -> List[Server]:
        """Load servers from project-level configuration."""
        servers = []
        project_config_path = Path.cwd() / ".mcp.json"
        
        if not project_config_path.exists():
            return servers
        
        try:
            with open(project_config_path, 'r') as f:
                project_config = json.load(f)
                mcp_servers = project_config.get("mcpServers", {})
                
                for name, config in mcp_servers.items():
                    server = Server(
                        name=name,
                        command=config.get("command", ""),
                        args=config.get("args", []),
                        env=config.get("env", {}),
                        server_type=self._infer_server_type(config.get("command", "")),
                        scope=ServerScope.PROJECT,
                        description=config.get("description", f"Project-level server: {name}")
                    )
                    servers.append(server)
                    
        except Exception as e:
            logger.warning(f"Failed to read project config: {e}")
        
        return servers
    
    def _load_internal_config(self) -> List[Server]:
        """Load servers from Claude's internal configuration."""
        servers = []
        claude_config_path = self.get_config_path()
        
        if not claude_config_path.exists():
            return servers
        
        try:
            with open(claude_config_path, 'r') as f:
                claude_config = json.load(f)
                
            # Look for both project-specific and global MCP servers in internal state
            current_project = str(Path.cwd())
            project_configs = claude_config.get("projectConfigs", {})
            
            # Check project-specific servers
            if current_project in project_configs:
                project_mcp = project_configs[current_project].get("mcpServers", {})
                servers.extend(self._process_mcp_config(project_mcp, ServerScope.PROJECT))
            
            # Also check for global user-level servers in internal state
            global_mcp = claude_config.get("mcpServers", {})
            servers.extend(self._process_mcp_config(global_mcp, ServerScope.USER))
                    
        except Exception as e:
            logger.warning(f"Failed to read internal Claude config: {e}")
        
        return servers
    
    def _process_mcp_config(self, mcp_config: Dict, scope: ServerScope) -> List[Server]:
        """Process MCP server configuration dict."""
        servers = []
        
        for name, config in mcp_config.items():
            # Handle docker-gateway expansion
            if name == "docker-gateway":
                docker_servers = self.docker_gateway.expand_docker_gateway_from_config(config)
                servers.extend(docker_servers)
            else:
                server = Server(
                    name=name,
                    command=config.get("command", ""),
                    args=config.get("args", []),
                    env=config.get("env", {}),
                    server_type=self._infer_server_type(config.get("command", "")),
                    scope=scope,
                    description=config.get("description", f"Server: {name}")
                )
                servers.append(server)
        
        return servers
    
    def _infer_server_type(self, command: str) -> ServerType:
        """Infer server type from command."""
        if not command:
            return ServerType.CUSTOM
        
        if command.startswith("npx"):
            return ServerType.NPM
        elif command.startswith("docker"):
            return ServerType.DOCKER
        elif "docker" in command.lower():
            return ServerType.DOCKER_DESKTOP
        else:
            return ServerType.CUSTOM
    
    # Delegate methods to appropriate modules
    def list_servers(self) -> List[Server]:
        """List all MCP servers known to Claude."""
        return self.client.list_servers()
    
    def get_server(self, name: str) -> Optional[Server]:
        """Get details about a specific server."""
        return self.client.get_server(name)
    
    def server_exists(self, name: str) -> bool:
        """Check if a server exists in Claude's configuration."""
        return self.client.server_exists(name)
    
    def add_server(
        self,
        name: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Add a server to Claude's configuration."""
        if not self.server_ops.validate_server_config(name, command, args):
            return False
        
        result = self.server_ops.add_server(name, command, args, env)
        if result:
            self.invalidate_cache()
        return result
    
    def remove_server(self, name: str) -> bool:
        """Remove a server from Claude's configuration."""
        result = self.server_ops.remove_server(name)
        if result:
            self.invalidate_cache()
        return result
    
    def update_server(
        self,
        name: str,
        command: str = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Update an existing server configuration."""
        result = self.server_ops.update_server(name, command, args, env)
        if result:
            self.invalidate_cache()
        return result
    
    def is_claude_cli_available(self) -> bool:
        """Check if Claude CLI is available and working."""
        return self.client.is_claude_cli_available()
    
    def is_docker_available(self) -> bool:
        """Check if Docker is available and working."""
        return self.client.is_docker_available()