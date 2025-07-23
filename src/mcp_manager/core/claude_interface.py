"""
Interface to Claude Code's native MCP management.

This module provides a Python interface to Claude Code's internal MCP state
via the claude mcp CLI commands.
"""

import asyncio
import json
import os
import shutil
import subprocess
import threading
import time
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from mcp_manager.core.exceptions import ClaudeError, MCPManagerError
from mcp_manager.core.models import Server, ServerType, ServerScope
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ClaudeInterface:
    """Interface to Claude Code's MCP management with memory cache and background sync."""
    
    def __init__(self):
        """Initialize Claude interface with caching."""
        self.claude_path = self._discover_claude_path()
        self.docker_path = self._discover_docker_path()
        self._check_claude_availability()
        
        # Memory cache for server list
        self._server_cache: Optional[List[Server]] = None
        self._cache_timestamp: float = 0
        self._cache_ttl: float = 30.0  # Cache TTL in seconds
        self._cache_lock = threading.RLock()
        
        # Background sync settings
        self._sync_interval: float = 60.0  # Background sync every 60 seconds
        self._sync_thread: Optional[threading.Thread] = None
        self._sync_stop_event = threading.Event()
        self._sync_enabled = os.getenv("MCP_CACHE_SYNC_ENABLED", "true").lower() == "true"
        
        # File modification tracking for cache invalidation
        self._config_files = [
            Path.home() / ".config" / "claude-code" / "mcp-servers.json",
            Path.cwd() / ".mcp.json",
            self.get_config_path()
        ]
        self._last_modified_times: Dict[str, float] = {}
        
        if self._sync_enabled:
            self._start_background_sync()
        
        logger.debug("ClaudeInterface initialized with caching", extra={
            "cache_ttl": self._cache_ttl,
            "sync_interval": self._sync_interval,
            "sync_enabled": self._sync_enabled
        })
    
    def __del__(self):
        """Cleanup background sync thread."""
        self._stop_background_sync()
    
    def _start_background_sync(self):
        """Start background sync thread."""
        if self._sync_thread and self._sync_thread.is_alive():
            return
        
        self._sync_stop_event.clear()
        self._sync_thread = threading.Thread(target=self._background_sync_worker, daemon=True)
        self._sync_thread.start()
        logger.debug("Background sync thread started")
    
    def _stop_background_sync(self):
        """Stop background sync thread."""
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_stop_event.set()
            self._sync_thread.join(timeout=5.0)
            logger.debug("Background sync thread stopped")
    
    def _background_sync_worker(self):
        """Background worker that syncs cache with database."""
        while not self._sync_stop_event.wait(self._sync_interval):
            try:
                if self._should_refresh_cache():
                    self._refresh_cache()
                    
                # Async database sync (run in thread pool to avoid blocking)
                asyncio.run_coroutine_threadsafe(
                    self._sync_to_database(), 
                    asyncio.get_event_loop() if asyncio.get_event_loop().is_running() else asyncio.new_event_loop()
                )
            except Exception as e:
                logger.warning(f"Background sync error: {e}")
    
    def _should_refresh_cache(self) -> bool:
        """Check if cache should be refreshed based on file modifications."""
        for config_file in self._config_files:
            if not config_file.exists():
                continue
                
            try:
                current_mtime = config_file.stat().st_mtime
                last_mtime = self._last_modified_times.get(str(config_file), 0)
                
                if current_mtime > last_mtime:
                    self._last_modified_times[str(config_file)] = current_mtime
                    return True
            except Exception as e:
                logger.debug(f"Error checking file modification time for {config_file}: {e}")
        
        return False
    
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
        try:
            # Import here to avoid circular imports
            from mcp_manager.core.tool_registry import ToolRegistryService
            
            with self._cache_lock:
                servers = self._server_cache.copy() if self._server_cache else []
            
            if not servers:
                return
            
            # Update database with current server list
            registry = ToolRegistryService()
            for server in servers:
                # Update server availability in database
                registry.update_tool_availability(server.name, True)  # Assume enabled if in config
            
            logger.debug(f"Synced {len(servers)} servers to database")
            
        except Exception as e:
            logger.warning(f"Database sync failed: {e}")
    
    def get_config_path(self) -> Path:
        """Get the path to Claude's configuration file."""
        return Path.home() / ".claude.json"
    
    def _discover_claude_path(self) -> str:
        """Discover the path to claude executable."""
        # Try common locations and use 'which' command
        claude_path = shutil.which("claude")
        if claude_path:
            logger.debug(f"Found claude at: {claude_path}")
            return claude_path
        
        # Fallback to common homebrew locations
        common_paths = [
            "/opt/homebrew/bin/claude",
            "/usr/local/bin/claude",
            "/usr/bin/claude",
        ]
        
        for path in common_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                logger.debug(f"Found claude at fallback location: {path}")
                return path
        
        raise ClaudeError("Claude CLI not found in PATH or common locations")
    
    def _discover_docker_path(self) -> str:
        """Discover the path to docker executable."""
        # Try common locations and use 'which' command
        docker_path = shutil.which("docker")
        if docker_path:
            logger.debug(f"Found docker at: {docker_path}")
            return docker_path
        
        # Fallback to common locations
        common_paths = [
            "/opt/homebrew/bin/docker",
            "/usr/local/bin/docker",
            "/usr/bin/docker",
        ]
        
        for path in common_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                logger.debug(f"Found docker at fallback location: {path}")
                return path
        
        raise ClaudeError("Docker CLI not found in PATH or common locations")
    
    def _check_claude_availability(self) -> None:
        """Check if Claude CLI is available."""
        try:
            result = subprocess.run(
                [self.claude_path, "--version"],
                capture_output=True,
                timeout=10,
                env=self._get_env(),
            )
            if result.returncode != 0:
                raise ClaudeError("Claude CLI not responding")
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            raise ClaudeError(f"Claude CLI not available: {e}")
    
    def _get_env(self) -> dict:
        """Get environment with proper PATH."""
        env = dict(os.environ)
        # Ensure homebrew paths are included
        homebrew_paths = ["/opt/homebrew/bin", "/usr/local/bin"]
        current_path = env.get("PATH", "")
        
        for path in homebrew_paths:
            if path not in current_path:
                current_path = f"{path}:{current_path}"
        
        env["PATH"] = current_path
        return env
    
    def list_servers_cached(self) -> List[Server]:
        """
        Get servers from memory cache (ultra-fast).
        
        Returns:
            Cached list of servers, refreshed if expired or invalid
        """
        with self._cache_lock:
            current_time = time.time()
            
            # Check if cache is valid
            if (self._server_cache is not None and 
                current_time - self._cache_timestamp < self._cache_ttl):
                return self._server_cache.copy()
            
            # Cache expired or invalid, refresh
            self._server_cache = self._load_servers_from_config()
            self._cache_timestamp = current_time
            
            logger.debug(f"Cache miss - loaded {len(self._server_cache)} servers")
            return self._server_cache.copy()
    
    def invalidate_cache(self):
        """Manually invalidate the cache."""
        with self._cache_lock:
            self._server_cache = None
            self._cache_timestamp = 0
            logger.debug("Cache manually invalidated")
    
    def _load_servers_from_config(self) -> List[Server]:
        """
        Fast server listing by reading config files directly.
        
        Returns:
            List of servers from config files without health checks
        """
        servers = []
        
        # Read user-level config
        user_config_path = Path.home() / ".config" / "claude-code" / "mcp-servers.json"
        if user_config_path.exists():
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
        
        # Read project-level config
        project_config_path = Path.cwd() / ".mcp.json"
        if project_config_path.exists():
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
        
        # Read internal state from ~/.claude.json (only MCP sections)
        claude_config_path = self.get_config_path()
        if claude_config_path.exists():
            try:
                with open(claude_config_path, 'r') as f:
                    claude_config = json.load(f)
                    
                # Look for both project-specific and global MCP servers in internal state
                current_project = str(Path.cwd())
                project_configs = claude_config.get("projectConfigs", {})
                
                # Check project-specific servers
                if current_project in project_configs:
                    project_mcp = project_configs[current_project].get("mcpServers", {})
                    for name, config in project_mcp.items():
                        # Skip if already found in config files
                        if any(s.name == name for s in servers):
                            continue
                        
                        # Handle docker-gateway expansion
                        if name == "docker-gateway":
                            docker_servers = self._expand_docker_gateway_from_config(config)
                            servers.extend(docker_servers)
                        else:
                            server = Server(
                                name=name,
                                command=config.get("command", ""),
                                args=config.get("args", []),
                                env=config.get("env", {}),
                                server_type=self._infer_server_type(config.get("command", "")),
                                scope=ServerScope.PROJECT,
                                description=config.get("description", f"Internal state server: {name}")
                            )
                            servers.append(server)
                
                # Also check for global user-level servers in internal state
                global_mcp = claude_config.get("mcpServers", {})
                for name, config in global_mcp.items():
                    # Skip if already found
                    if any(s.name == name for s in servers):
                        continue
                    
                    # Handle docker-gateway expansion
                    if name == "docker-gateway":
                        docker_servers = self._expand_docker_gateway_from_config(config)
                        servers.extend(docker_servers)
                    else:
                        server = Server(
                            name=name,
                            command=config.get("command", ""),
                            args=config.get("args", []),
                            env=config.get("env", {}),
                            server_type=self._infer_server_type(config.get("command", "")),
                            scope=ServerScope.USER,
                            description=config.get("description", f"Global server: {name}")
                        )
                        servers.append(server)
                        
            except Exception as e:
                logger.warning(f"Failed to read internal Claude config: {e}")
        
        logger.debug(f"Found {len(servers)} servers from config files")
        return servers
    
    def _expand_docker_gateway_from_config(self, gateway_config: Dict) -> List[Server]:
        """Expand docker-gateway configuration into individual Docker Desktop servers."""
        servers = []
        
        try:
            command = gateway_config.get("command", "")
            args = gateway_config.get("args", [])
            
            # Look for --servers argument in command or args
            servers_list = None
            
            # Check if servers are in the command string
            if "--servers" in command:
                parts = command.split("--servers")
                if len(parts) > 1:
                    servers_part = parts[1].strip().split()[0]
                    servers_list = servers_part.split(",")
            
            # Check if servers are in args list
            elif args and "--servers" in args:
                servers_idx = args.index("--servers")
                if servers_idx + 1 < len(args):
                    servers_list = args[servers_idx + 1].split(",")
            
            if servers_list:
                for server_name in servers_list:
                    server_name = server_name.strip()
                    if server_name:
                        server = Server(
                            name=server_name,
                            command="docker",
                            args=["mcp", "gateway", "run", "--servers", server_name],
                            env=gateway_config.get("env", {}),
                            server_type=ServerType.DOCKER_DESKTOP,
                            scope=ServerScope.USER,
                            description=f"Docker Desktop MCP server: {server_name}"
                        )
                        servers.append(server)
            
        except Exception as e:
            logger.warning(f"Failed to expand docker-gateway: {e}")
        
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
    
    def list_servers(self) -> List[Server]:
        """
        List all MCP servers known to Claude.
        
        Returns:
            List of servers from Claude's internal state
        """
        try:
            result = subprocess.run(
                [self.claude_path, "mcp", "list"],
                capture_output=True,
                text=True,
                timeout=30,
                env=self._get_env(),
            )
            
            if result.returncode != 0:
                logger.warning(f"claude mcp list failed: {result.stderr}")
                return []
            
            servers = []
            for line in result.stdout.strip().split('\n'):
                if line and ':' in line:
                    # Parse "name: command args..."
                    parts = line.split(':', 1)
                    name = parts[0].strip()
                    command_and_args = parts[1].strip()
                    
                    # Split command and args, filtering out status indicators
                    cmd_parts = command_and_args.split()
                    command = cmd_parts[0] if cmd_parts else ""
                    
                    # Filter out status indicators like "-", "✓", "Connected", "Disconnected"
                    status_indicators = {"-", "✓", "Connected", "Disconnected", "Failed", "Error"}
                    args = []
                    for part in cmd_parts[1:]:
                        if part not in status_indicators:
                            args.append(part)
                        else:
                            # Stop processing once we hit a status indicator
                            break
                    
                    # Determine server type
                    server_type = self._determine_server_type(command)
                    
                    server = Server(
                        name=name,
                        command=command,
                        args=args,
                        server_type=server_type,
                        scope=ServerScope.USER,  # Claude manages globally
                        enabled=True,  # If it's in claude mcp list, it's enabled
                    )
                    servers.append(server)
            
            logger.debug(f"Found {len(servers)} servers in Claude")
            return servers
            
        except Exception as e:
            logger.error(f"Failed to list Claude servers: {e}")
            raise MCPManagerError(f"Failed to list servers: {e}")
    
    def add_server(
        self,
        name: str,
        command: str,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Add a server to Claude's configuration.
        
        Args:
            name: Server name
            command: Server command
            args: Command arguments
            env: Environment variables
            
        Returns:
            True if successful
        """
        try:
            # Build command args - Claude expects: claude mcp add <name> <command> [args...]
            # Use --scope user to store in user-wide configuration
            cmd_args = [self.claude_path, "mcp", "add", "--scope", "user", name, command]
            if args:
                # Check if any args start with - (options) - if so, use -- separator
                has_options = any(arg.startswith('-') for arg in args)
                if has_options:
                    cmd_args.append('--')
                cmd_args.extend(args)
            
            # Set up environment
            cmd_env = self._get_env()
            if env:
                cmd_env.update(env)
            
            result = subprocess.run(
                cmd_args,
                capture_output=True,
                text=True,
                timeout=30,
                env=cmd_env,
            )
            
            if result.returncode == 0:
                logger.debug(f"Added server '{name}' to Claude")
                return True
            else:
                logger.error(f"Failed to add server '{name}': {result.stderr}")
                raise MCPManagerError(f"Failed to add server: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Failed to add server '{name}': {e}")
            raise MCPManagerError(f"Failed to add server: {e}")
    
    def remove_server(self, name: str) -> bool:
        """
        Remove a server from Claude's configuration.
        
        Args:
            name: Server name to remove
            
        Returns:
            True if successful
        """
        try:
            result = subprocess.run(
                [self.claude_path, "mcp", "remove", "--scope", "user", name],
                capture_output=True,
                text=True,
                timeout=30,
                env=self._get_env(),
            )
            
            if result.returncode == 0:
                logger.debug(f"Removed server '{name}' from Claude")
                return True
            else:
                logger.error(f"Failed to remove server '{name}': {result.stderr}")
                raise MCPManagerError(f"Failed to remove server: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Failed to remove server '{name}': {e}")
            raise MCPManagerError(f"Failed to remove server: {e}")
    
    def get_server(self, name: str) -> Optional[Server]:
        """
        Get details about a specific server.
        
        Args:
            name: Server name
            
        Returns:
            Server object if found, None otherwise
        """
        try:
            result = subprocess.run(
                [self.claude_path, "mcp", "get", name],
                capture_output=True,
                text=True,
                timeout=30,
                env=self._get_env(),
            )
            
            if result.returncode != 0:
                return None
            
            # Parse the output (this might need adjustment based on actual format)
            # For now, fall back to listing all and finding the one
            servers = self.list_servers()
            return next((s for s in servers if s.name == name), None)
            
        except Exception as e:
            logger.warning(f"Failed to get server '{name}': {e}")
            return None
    
    def server_exists(self, name: str) -> bool:
        """
        Check if a server exists in Claude's configuration.
        
        Args:
            name: Server name to check
            
        Returns:
            True if server exists
        """
        # Use list_servers instead of get_server as it's more reliable
        servers = self.list_servers()
        return any(s.name == name for s in servers)
    
    def _determine_server_type(self, command: str) -> ServerType:
        """Determine server type from command."""
        if command.startswith(("npx", "npm", "node")):
            return ServerType.NPM
        elif command.startswith("docker"):
            return ServerType.DOCKER
        else:
            return ServerType.CUSTOM


