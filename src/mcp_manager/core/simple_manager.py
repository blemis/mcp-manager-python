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
        List all MCP servers, expanding docker-gateway to show individual servers.
        
        Returns:
            List of servers from Claude's internal state with docker-gateway expanded
        """
        servers = self.claude.list_servers()
        result = []
        
        for server in servers:
            if server.name == "docker-gateway":
                # Expand docker-gateway to show individual Docker Desktop servers
                docker_servers = await self._expand_docker_gateway(server)
                result.extend(docker_servers)
            else:
                result.append(server)
                
        return result
    
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
        
        # Check if this is a Docker Desktop server
        if name.startswith("docker-desktop-") or await self._is_docker_desktop_server(name):
            return await self._disable_docker_desktop_server(name)
        else:
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
        """Enable a Docker Desktop MCP server and sync with Claude Code."""
        import subprocess
        
        try:
            # Extract the actual server name (remove docker-desktop- prefix if present)
            if name.startswith("docker-desktop-"):
                server_name = name.replace("docker-desktop-", "")
            else:
                server_name = name
            
            logger.info(f"Enabling Docker Desktop MCP server: {server_name}")
            
            # Step 1: Enable the server in Docker Desktop
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
            
            # Step 2: Sync all Docker Desktop servers to Claude Code
            # This uses claude mcp add-from-claude-desktop to sync ALL enabled servers
            sync_success = await self._import_docker_gateway_to_claude_code()
            
            if sync_success:
                logger.info(f"Successfully synced {server_name} to Claude Code")
                return True
            else:
                logger.error("Failed to sync Docker Desktop servers to Claude Code")
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
    
    
    async def _import_docker_gateway_to_claude_code(self) -> bool:
        """Ensure docker-gateway is set up in Claude Code."""
        try:
            # Check if docker-gateway already exists
            if self.claude.server_exists("docker-gateway"):
                logger.info("docker-gateway already configured in Claude Code")
                return True
            
            # Docker Desktop MCP gateway requires one-time setup
            from rich.console import Console
            from rich.panel import Panel
            
            console = Console()
            
            console.print("\n[yellow]⚠ Docker Desktop Setup Required[/yellow]")
            console.print(Panel.fit(
                "[bold cyan]One-time setup needed:[/bold cyan]\n\n"
                "[white]Run this command to enable Docker Desktop MCPs:[/white]\n"
                "[green]claude mcp add-from-claude-desktop docker-gateway[/green]\n\n"
                "[dim]This will sync all enabled Docker Desktop servers to Claude Code.\n"
                "You only need to run this once - the MCP Manager will handle\n"
                "enabling/disabling individual servers in Docker Desktop.[/dim]",
                title="Docker Desktop Integration",
                border_style="blue"
            ))
            
            # Return True so the Docker Desktop server was enabled successfully
            # The user just needs to run the one-time setup command
            return True
            
        except Exception as e:
            logger.error(f"Failed to check docker-gateway: {e}")
            return False
    
    async def _disable_docker_desktop_server(self, name: str) -> bool:
        """Disable a Docker Desktop MCP server and sync with Claude Code."""
        import subprocess
        
        try:
            # Extract the actual server name (remove docker-desktop- prefix if present)
            if name.startswith("docker-desktop-"):
                server_name = name.replace("docker-desktop-", "")
            else:
                server_name = name
            
            logger.info(f"Disabling Docker Desktop MCP server: {server_name}")
            
            # Step 1: Disable the server in Docker Desktop
            result = subprocess.run(
                ["docker", "mcp", "server", "disable", server_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to disable Docker Desktop server {server_name}: {result.stderr}")
                return False
            
            logger.info(f"Successfully disabled {server_name} in Docker Desktop")
            
            # Step 2: Re-sync Docker Desktop servers to Claude Code
            # This uses claude mcp add-from-claude-desktop to sync the updated list
            sync_success = await self._import_docker_gateway_to_claude_code()
            
            if sync_success:
                logger.info(f"Successfully removed {server_name} from Claude Code")
                return True
            else:
                logger.error("Failed to sync Docker Desktop servers to Claude Code")
                return False
                
        except Exception as e:
            logger.error(f"Failed to disable Docker Desktop server {name}: {e}")
            return False
    
    async def _is_docker_desktop_server(self, name: str) -> bool:
        """Check if a server name corresponds to a Docker Desktop MCP server."""
        try:
            # Get the list of enabled Docker Desktop servers
            enabled_servers = await self._get_enabled_docker_servers()
            return name in enabled_servers
        except Exception:
            return False
    
    async def _expand_docker_gateway(self, gateway_server: Server) -> List[Server]:
        """Expand docker-gateway into individual Docker Desktop servers."""
        docker_servers = []
        
        try:
            # Extract server names from gateway args
            if gateway_server.args and len(gateway_server.args) >= 5:
                # Args format: ["mcp", "gateway", "run", "--servers", "server1,server2,server3"]
                servers_arg = gateway_server.args[4]
                server_names = [s.strip() for s in servers_arg.split(",")]
                
                for server_name in server_names:
                    # Create a Server object for each Docker Desktop server
                    docker_server = Server(
                        name=server_name,
                        command="docker",
                        args=["mcp", "server", server_name],
                        server_type=ServerType.DOCKER_DESKTOP,
                        scope=gateway_server.scope,
                        enabled=True,  # If it's in the gateway, it's enabled
                        description=f"Docker Desktop MCP server: {server_name}",
                        env={},
                    )
                    docker_servers.append(docker_server)
                    
            return docker_servers
            
        except Exception as e:
            logger.warning(f"Failed to expand docker-gateway: {e}")
            # If expansion fails, return the gateway as-is
            return [gateway_server]