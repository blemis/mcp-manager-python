"""
Server CRUD operations for Claude interface.

This module handles adding, removing, and managing MCP servers in Claude's
configuration, including proper command argument handling and environment setup.
"""

import subprocess
from typing import Dict, List, Optional

from mcp_manager.core.exceptions import MCPManagerError
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ServerOperations:
    """Handles server CRUD operations for Claude interface."""
    
    def __init__(self, claude_path: str, env_provider):
        """
        Initialize server operations.
        
        Args:
            claude_path: Path to Claude CLI
            env_provider: Function that returns environment dict
        """
        self.claude_path = claude_path
        self.get_env = env_provider
        
        logger.debug("ServerOperations initialized", extra={"claude_path": claude_path})
    
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
            
        Raises:
            MCPManagerError: If addition fails
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
            cmd_env = self.get_env()
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
                logger.info(f"Added server '{name}' to Claude", extra={
                    "server_name": name,
                    "command": command,
                    "args": args
                })
                return True
            else:
                error_msg = result.stderr.strip()
                logger.error(f"Failed to add server '{name}': {error_msg}")
                raise MCPManagerError(f"Failed to add server: {error_msg}")
                
        except subprocess.TimeoutExpired:
            error_msg = f"Adding server '{name}' timed out"
            logger.error(error_msg)
            raise MCPManagerError(error_msg)
        except Exception as e:
            logger.error(f"Failed to add server '{name}': {e}")
            raise MCPManagerError(f"Failed to add server: {e}")
    
    def remove_server(self, name: str) -> bool:
        """
        Remove a server from Claude's configuration.
        
        Args:
            name: Server name to remove
            
        Returns:
            True if successful, False if server not found
            
        Raises:
            MCPManagerError: If removal fails due to system error
        """
        try:
            # Don't specify scope - let Claude find it in any scope
            result = subprocess.run(
                [self.claude_path, "mcp", "remove", name],
                capture_output=True,
                text=True,
                timeout=30,
                env=self.get_env(),
                input="y\n",  # Provide confirmation input if prompted
            )
            
            if result.returncode == 0:
                logger.info(f"Removed server '{name}' from Claude", extra={
                    "server_name": name
                })
                return True
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                
                # Check for "not found" errors - handle gracefully
                if ("not found" in error_msg.lower() or 
                    ("no" in error_msg.lower() and "server" in error_msg.lower()) or
                    "does not exist" in error_msg.lower()):
                    logger.warning(f"Server '{name}' not found in Claude configuration")
                    return False  # Return False instead of raising error for not found
                else:
                    logger.error(f"Failed to remove server '{name}': {error_msg}")
                    raise MCPManagerError(f"Failed to remove server: {error_msg}")
                
        except subprocess.TimeoutExpired:
            error_msg = f"Removing server '{name}' timed out"
            logger.error(error_msg)
            raise MCPManagerError(error_msg)
        except Exception as e:
            logger.error(f"Failed to remove server '{name}': {e}")
            raise MCPManagerError(f"Failed to remove server: {e}")
    
    def update_server(
        self,
        name: str,
        command: str = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Update an existing server configuration.
        
        This is implemented as remove + add since Claude CLI doesn't have
        a native update command.
        
        Args:
            name: Server name to update
            command: New server command (optional)
            args: New command arguments (optional)
            env: New environment variables (optional)
            
        Returns:
            True if successful
            
        Raises:
            MCPManagerError: If update fails
        """
        try:
            # For now, we need to remove and re-add since Claude CLI
            # doesn't have a native update command
            
            # First check if server exists
            from .claude_client import ClaudeClient
            client = ClaudeClient()
            existing_server = client.get_server(name)
            
            if not existing_server:
                raise MCPManagerError(f"Server '{name}' not found")
            
            # Use existing values if new ones not provided
            final_command = command or existing_server.command
            final_args = args if args is not None else existing_server.args
            final_env = env or existing_server.env
            
            # Remove existing server
            self.remove_server(name)
            
            # Add with new configuration
            self.add_server(name, final_command, final_args, final_env)
            
            logger.info(f"Updated server '{name}'", extra={
                "server_name": name,
                "command": final_command,
                "args": final_args
            })
            return True
            
        except Exception as e:
            logger.error(f"Failed to update server '{name}': {e}")
            raise MCPManagerError(f"Failed to update server: {e}")
    
    def enable_server(self, name: str) -> bool:
        """
        Enable a server in Claude's configuration.
        
        Note: Claude CLI doesn't have explicit enable/disable commands,
        so this is primarily for compatibility.
        
        Args:
            name: Server name to enable
            
        Returns:
            True if server exists
        """
        try:
            from .claude_client import ClaudeClient
            client = ClaudeClient()
            
            if client.server_exists(name):
                logger.debug(f"Server '{name}' is already enabled")
                return True
            else:
                logger.warning(f"Server '{name}' not found - cannot enable")
                return False
                
        except Exception as e:
            logger.error(f"Failed to enable server '{name}': {e}")
            return False
    
    def disable_server(self, name: str) -> bool:
        """
        Disable a server in Claude's configuration.
        
        Note: Claude CLI doesn't have explicit disable command,
        so this removes the server entirely.
        
        Args:
            name: Server name to disable
            
        Returns:
            True if successful
        """
        try:
            return self.remove_server(name)
        except Exception as e:
            logger.error(f"Failed to disable server '{name}': {e}")
            return False
    
    def validate_server_config(
        self,
        name: str,
        command: str,
        args: Optional[List[str]] = None
    ) -> bool:
        """
        Validate server configuration before adding.
        
        Args:
            name: Server name
            command: Server command
            args: Command arguments
            
        Returns:
            True if configuration is valid
        """
        if not name or not name.strip():
            logger.error("Server name cannot be empty")
            return False
        
        if not command or not command.strip():
            logger.error("Server command cannot be empty")
            return False
        
        # Check for invalid characters in name
        invalid_chars = [' ', '\t', '\n', ':', '"', "'"]
        if any(char in name for char in invalid_chars):
            logger.error(f"Server name contains invalid characters: {name}")
            return False
        
        logger.debug(f"Server configuration validated for '{name}'")
        return True