"""
Claude CLI integration client.

This module provides a wrapper around the Claude CLI commands for MCP
server management, including path discovery and environment setup.
"""

import os
import shutil
import subprocess
from typing import Dict, List, Optional, Tuple

from mcp_manager.core.exceptions import ClaudeError, MCPManagerError
from mcp_manager.core.models import Server, ServerType, ServerScope
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ClaudeClient:
    """Client for interacting with Claude CLI."""
    
    def __init__(self):
        """Initialize Claude CLI client."""
        self.claude_path = self._discover_claude_path()
        self.docker_path = self._discover_docker_path()
        self._check_claude_availability()
        
        logger.debug("ClaudeClient initialized", extra={
            "claude_path": self.claude_path,
            "docker_path": self.docker_path
        })
    
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
    
    def is_claude_cli_available(self) -> bool:
        """Check if Claude CLI is available and working."""
        try:
            # Just check if the claude binary exists and is executable
            # Don't actually run it to avoid timeouts
            if not self.claude_path or not shutil.which(self.claude_path):
                return False
            
            # Quick version check with very short timeout
            result = subprocess.run(
                [self.claude_path, "--version"],
                capture_output=True,
                timeout=2,  # Very short timeout
                env=self._get_env(),
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            # If version check times out, assume it's available but slow
            logger.debug("Claude CLI version check timed out, assuming available")
            return True
        except Exception as e:
            logger.debug(f"Claude CLI availability check failed: {e}")
            return False
    
    def is_docker_available(self) -> bool:
        """Check if Docker is available and working."""
        try:
            # Just check if the docker binary exists and is executable
            if not self.docker_path or not shutil.which(self.docker_path):
                return False
            
            # Quick version check with very short timeout
            result = subprocess.run(
                [self.docker_path, "--version"],
                capture_output=True,
                timeout=2,  # Very short timeout
                env=self._get_env(),
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            # If version check times out, assume it's available but slow
            logger.debug("Docker version check timed out, assuming available")
            return True
        except Exception as e:
            logger.debug(f"Docker availability check failed: {e}")
            return False