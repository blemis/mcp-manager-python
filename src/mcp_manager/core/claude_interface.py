"""
Interface to Claude Code's native MCP management.

This module provides a Python interface to Claude Code's internal MCP state
via the claude mcp CLI commands.
"""

import json
import os
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from mcp_manager.core.exceptions import ClaudeError, MCPManagerError
from mcp_manager.core.models import Server, ServerType, ServerScope
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ClaudeInterface:
    """Interface to Claude Code's MCP management."""
    
    def __init__(self):
        """Initialize Claude interface."""
        self.claude_path = self._discover_claude_path()
        self.docker_path = self._discover_docker_path()
        self._check_claude_availability()
    
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
                    
                    # Split command and args
                    cmd_parts = command_and_args.split()
                    command = cmd_parts[0] if cmd_parts else ""
                    args = cmd_parts[1:] if len(cmd_parts) > 1 else []
                    
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
                [self.claude_path, "mcp", "get", "--scope", "user", name],
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


