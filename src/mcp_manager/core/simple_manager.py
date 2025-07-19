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
        
        # Handle Docker Desktop servers specially
        if server_type == ServerType.DOCKER_DESKTOP:
            # For Docker Desktop, we need to enable the server in Docker Desktop first
            success = await self._enable_docker_desktop_server(name, command, args or [])
        else:
            # Add to Claude normally
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
    
    async def _enable_docker_desktop_server(self, name: str, command: str, args: List[str]) -> bool:
        """Enable a Docker Desktop MCP server."""
        import subprocess
        
        try:
            # Extract the actual server name (remove docker-desktop- prefix)
            if name.startswith("docker-desktop-"):
                server_name = name.replace("docker-desktop-", "")
            else:
                server_name = name
            
            # Check if this is a gateway request
            if name == "docker-gateway":
                # For gateway, we just add it to Claude with the gateway command
                return self.claude.add_server(
                    name=name,
                    command=command,
                    args=args,
                    env=None,
                )
            
            # For individual servers, enable them in Docker Desktop first
            logger.info(f"Enabling Docker Desktop MCP server: {server_name}")
            
            result = subprocess.run(
                ["docker", "mcp", "server", "enable", server_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to enable Docker Desktop server {server_name}: {result.stderr}")
                return False
            
            logger.info(f"Successfully enabled {server_name} in Docker Desktop")
            
            # Get the updated list of enabled servers from registry
            enabled_servers = await self._get_enabled_docker_servers()
            
            if not enabled_servers:
                logger.error("No enabled servers found in Docker registry after enabling")
                return False
            
            logger.info(f"Current enabled Docker servers: {enabled_servers}")
            
            # Update Claude Desktop config with all enabled servers
            desktop_success = await self._update_claude_desktop_gateway(enabled_servers)
            if not desktop_success:
                logger.error("Failed to update Claude Desktop config")
                return False
            
            # Import/update the gateway in Claude Code
            gateway_success = await self._import_docker_gateway_from_claude_desktop()
            
            if gateway_success:
                logger.info(f"Successfully enabled {server_name} via Docker Desktop gateway")
                return True
            else:
                logger.error("Failed to update Docker gateway in Claude Code")
                return False
                
        except Exception as e:
            logger.error(f"Failed to enable Docker Desktop server {name}: {e}")
            return False
    
    async def _get_enabled_docker_servers(self) -> List[str]:
        """Get list of enabled Docker Desktop MCP servers."""
        try:
            import yaml
            from pathlib import Path
            
            registry_path = Path.home() / ".docker" / "mcp" / "registry.yaml"
            if not registry_path.exists():
                return []
            
            with open(registry_path) as f:
                registry_data = yaml.safe_load(f)
            
            return list(registry_data.get("registry", {}).keys())
            
        except Exception as e:
            logger.warning(f"Failed to get enabled Docker servers: {e}")
            return []
    
    async def _update_claude_desktop_gateway(self, enabled_servers: List[str]) -> bool:
        """Update Claude Desktop config with current enabled servers."""
        try:
            import json
            from pathlib import Path
            
            claude_desktop_config = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
            
            if claude_desktop_config.exists():
                with open(claude_desktop_config) as f:
                    config = json.load(f)
            else:
                config = {"mcpServers": {}}
            
            # Ensure mcpServers exists
            if "mcpServers" not in config:
                config["mcpServers"] = {}
            
            # Update the docker-gateway configuration with all enabled servers
            config["mcpServers"]["docker-gateway"] = {
                "command": "docker",
                "args": ["mcp", "gateway", "run", "--servers", ",".join(sorted(enabled_servers))]
            }
            
            # Ensure directory exists
            claude_desktop_config.parent.mkdir(parents=True, exist_ok=True)
            
            # Write back to config
            with open(claude_desktop_config, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Updated Claude Desktop config with servers: {enabled_servers}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update Claude Desktop config: {e}")
            return False
    
    async def _import_docker_gateway_from_claude_desktop(self) -> bool:
        """Import the docker-gateway from Claude Desktop to Claude Code."""
        try:
            import subprocess
            
            # Use claude mcp add with the correct format by reading from Claude Desktop config
            import json
            from pathlib import Path
            
            claude_desktop_config = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
            
            with open(claude_desktop_config) as f:
                config = json.load(f)
            
            gateway_config = config.get("mcpServers", {}).get("docker-gateway", {})
            if not gateway_config:
                return False
            
            command = gateway_config["command"]
            args = gateway_config["args"]
            
            # Add to Claude Code using the correct format
            return self.claude.add_server(
                name="docker-gateway",
                command=command,
                args=args,
                env=None,
            )
            
        except Exception as e:
            logger.error(f"Failed to import docker-gateway: {e}")
            return False