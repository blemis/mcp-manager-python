"""
Simplified MCP Manager that works directly with Claude Code's internal state.

This manager is a thin wrapper around claude mcp CLI commands.
"""

import asyncio
import subprocess
import sys
from typing import List, Optional, Tuple

from mcp_manager.core.claude_interface import ClaudeInterface
from mcp_manager.core.exceptions import MCPManagerError
from mcp_manager.core.models import Server, ServerType, ServerScope, SystemInfo
from mcp_manager.utils.config import get_config
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
        logger.debug(f"Adding server '{name}' to Claude")
        
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
        Remove an MCP server and clean up Docker images if applicable.
        
        Args:
            name: Server name to remove
            scope: Server scope (ignored - Claude manages globally)
            
        Returns:
            True if removed successfully
        """
        logger.debug(f"Removing server '{name}' from Claude")
        
        # Get server details from Claude's list to find Docker images
        servers = await self.list_servers()
        server = next((s for s in servers if s.name == name), None)
        docker_image = None
        
        if server:
            logger.debug(f"Server details - Name: {server.name}, Type: {server.server_type}, Command: {server.command}, Args: {server.args}")
            if server.server_type in [ServerType.DOCKER, ServerType.DOCKER_DESKTOP]:
                docker_image = self._extract_docker_image(server.command, server.args)
                logger.debug(f"Extracted Docker image: {docker_image}")
                
                # If extraction failed, try alternative methods based on server type
                if not docker_image and server.server_type == ServerType.DOCKER_DESKTOP:
                    # For Docker Desktop servers, the image follows the pattern: mcp/server-name
                    docker_image = f"mcp/{server.name.lower()}"
                    logger.debug(f"Using Docker Desktop pattern: {docker_image}")
                
            else:
                logger.debug(f"Server type {server.server_type} is not Docker-based, skipping image cleanup")
        else:
            logger.debug(f"Could not find server details for {name}")
        
        # Remove the server
        success = False
        if name.startswith("docker-desktop-") or await self._is_docker_desktop_server(name):
            success = await self._disable_docker_desktop_server(name)
        else:
            success = self.claude.remove_server(name)
        
        # Clean up Docker image if removal was successful and we have an image
        if success and docker_image:
            logger.debug(f"Attempting to remove Docker image: {docker_image}")
            image_removed = await self._remove_docker_image(docker_image)
            if image_removed:
                logger.debug(f"Docker image cleanup completed for: {docker_image}")
            else:
                logger.warning(f"Docker image cleanup failed for: {docker_image}")
        
        return success
    
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
            logger.debug(f"Server '{name}' is already enabled in Claude")
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
            
            logger.debug(f"Enabling Docker Desktop MCP server: {server_name}")
            
            # Step 1: Enable the server in Docker Desktop
            result = subprocess.run(
                [self.claude.docker_path, "mcp", "server", "enable", server_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to enable Docker Desktop server {server_name}: {result.stderr}")
                return False
            
            logger.debug(f"Successfully enabled {server_name} in Docker Desktop")
            
            # Step 2: Sync all Docker Desktop servers to Claude Code
            # Refresh the gateway to include the newly enabled server
            sync_success = await self._refresh_docker_gateway()
            
            if sync_success:
                logger.debug(f"Successfully synced {server_name} to Claude Code")
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
    
    
    async def _refresh_docker_gateway(self) -> bool:
        """Refresh docker-gateway by removing and re-adding it with updated servers."""
        try:
            # Remove existing gateway if it exists
            if self.claude.server_exists("docker-gateway"):
                self.claude.remove_server("docker-gateway")
                logger.debug("Removed existing docker-gateway")
            
            # Re-add with current server list
            return await self._import_docker_gateway_to_claude_code()
            
        except Exception as e:
            logger.error(f"Failed to refresh docker-gateway: {e}")
            return False
    
    async def _import_docker_gateway_to_claude_code(self) -> bool:
        """Ensure docker-gateway is set up in Claude Code."""
        try:
            # Check if docker-gateway already exists
            if self.claude.server_exists("docker-gateway"):
                logger.debug("docker-gateway already configured in Claude Code")
                return True
            
            # Try to automatically add docker-gateway
            logger.debug("Setting up docker-gateway for Docker Desktop integration")
            
            # Get the list of enabled Docker servers from registry
            enabled_servers = await self._get_enabled_docker_servers()
            if not enabled_servers:
                logger.warning("No Docker Desktop servers enabled")
                return True  # Not an error, just nothing to sync
            
            # Build the docker-gateway command
            # The gateway runs and manages connections to enabled Docker Desktop servers
            servers_list = ",".join(enabled_servers)
            
            # Add docker-gateway to Claude Code with the current enabled servers
            success = self.claude.add_server(
                name="docker-gateway",
                command=self.claude.docker_path,
                args=["mcp", "gateway", "run", "--servers", servers_list],
                env=None,
            )
            
            if success:
                logger.debug(f"Successfully set up docker-gateway with servers: {servers_list}")
                return True
            else:
                logger.error("Failed to add docker-gateway to Claude Code")
                return False
            
        except Exception as e:
            logger.error(f"Failed to set up docker-gateway: {e}")
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
            
            logger.debug(f"Disabling Docker Desktop MCP server: {server_name}")
            
            # Step 1: Disable the server in Docker Desktop
            result = subprocess.run(
                [self.claude.docker_path, "mcp", "server", "disable", server_name],
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                logger.error(f"Failed to disable Docker Desktop server {server_name}: {result.stderr}")
                return False
            
            logger.debug(f"Successfully disabled {server_name} in Docker Desktop")
            
            # Step 2: Update docker-gateway with the new server list
            # Force refresh the gateway with updated server list
            sync_success = await self._refresh_docker_gateway()
            
            # Step 3: Clean up Docker Desktop MCP image if removal was successful
            if sync_success:
                # Docker Desktop MCP servers use the format: mcp-docker-desktop/server-name:latest
                docker_image = f"mcp-docker-desktop/{server_name}:latest"
                await self._remove_docker_image(docker_image)
                
                logger.debug(f"Successfully removed {server_name} from Claude Code")
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
    
    def get_system_info(self) -> SystemInfo:
        """Get system information and dependency status."""
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
        
        # Get config
        config = get_config()
        
        return SystemInfo(
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
            config_dir=config.get_config_dir(),
            log_file=config.get_log_file(),
        )
    
    def _check_command(self, command: str, args: List[str]) -> Tuple[bool, Optional[str]]:
        """Check if a command is available and get its version."""
        try:
            result = subprocess.run(
                [command] + args,
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )
            
            if result.returncode == 0:
                # Extract version from output
                output = result.stdout.strip()
                if not output:
                    output = result.stderr.strip()
                
                # Clean up version string
                version = output.split('\n')[0]
                if command == "claude":
                    # Claude output might be "claude 1.2.3"
                    parts = version.split()
                    if len(parts) >= 2:
                        version = parts[-1]
                elif command in ["npm", "docker", "git"]:
                    # Extract version number from common patterns
                    import re
                    match = re.search(r'(\d+\.\d+\.\d+)', version)
                    if match:
                        version = match.group(1)
                
                return True, version
            else:
                return False, None
                
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            return False, None
    
    def _extract_docker_image(self, command: str, args: List[str]) -> Optional[str]:
        """
        Extract Docker image name from server command and args.
        
        Args:
            command: Server command (typically 'docker')
            args: Command arguments
            
        Returns:
            Docker image name if found, None otherwise
        """
        if command != "docker":
            return None
        
        try:
            # Log the full command for debugging
            logger.debug(f"Extracting image from command: {command} {' '.join(args)}")
            
            # Look for the image name in Docker run command
            # Typical format: ["run", "-i", "--rm", "--pull", "always", "image:tag"]
            if "run" in args:
                run_index = args.index("run")
                
                # The image name is typically the last argument that doesn't start with -
                # and comes after all the flags
                for i in range(len(args) - 1, run_index, -1):
                    arg = args[i]
                    logger.debug(f"Checking arg[{i}]: '{arg}'")
                    # Image name should contain : or / and not start with -
                    if not arg.startswith("-") and (":" in arg or "/" in arg):
                        logger.debug(f"Found image with : or /: {arg}")
                        return arg
                
                # Fallback: find the last non-flag argument that isn't a known flag value
                for i in range(len(args) - 1, run_index, -1):
                    arg = args[i]
                    if (not arg.startswith("-") and 
                        arg not in ["always", "missing", "never", "run"] and
                        len(arg) > 3):  # Image names are typically longer than 3 chars
                        logger.debug(f"Found fallback image: {arg}")
                        return arg
            
            # Try to extract from the full command if it contains common Docker image patterns
            full_command = ' '.join(args)
            import re
            # Look for patterns like mcp-docker-desktop/name:tag or registry/name:tag
            patterns = [
                r'(mcp-docker-desktop/[^:\s]+(?::[^:\s]+)?)',
                r'([a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+(?::[a-zA-Z0-9._-]+)?)',
                r'([a-zA-Z0-9._-]+:[a-zA-Z0-9._-]+)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, full_command)
                if match:
                    image = match.group(1)
                    logger.debug(f"Found image via regex: {image}")
                    return image
            
            logger.debug("No Docker image found in command")
            return None
        except Exception as e:
            logger.warning(f"Failed to extract Docker image from command: {e}")
            return None
    
    async def _remove_docker_image(self, image: str) -> bool:
        """
        Remove a Docker image.
        
        Args:
            image: Docker image name to remove
            
        Returns:
            True if removed successfully or image doesn't exist
        """
        try:
            logger.debug(f"Removing Docker image: {image}")
            
            # Try multiple image variations (with/without tags)
            image_variations = [
                image,
                f"{image}:latest",
                image.replace(":latest", ""),  # Remove :latest if present
            ]
            
            # Remove duplicates while preserving order
            image_variations = list(dict.fromkeys(image_variations))
            
            removed_any = False
            for img_variant in image_variations:
                logger.debug(f"Trying to remove image variant: {img_variant}")
                
                # First check if image exists
                check_result = subprocess.run(
                    ["docker", "image", "inspect", img_variant],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                
                if check_result.returncode != 0:
                    logger.debug(f"Docker image {img_variant} not found")
                    continue
                
                # Try to remove this variant
                logger.debug(f"Found image {img_variant}, attempting removal")
                result = subprocess.run(
                    ["docker", "rmi", "-f", img_variant],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                
                if result.returncode == 0:
                    logger.debug(f"Successfully removed Docker image: {img_variant}")
                    removed_any = True
                else:
                    logger.debug(f"Failed to remove {img_variant}: {result.stderr}")
                    # Try alternative removal method for this variant
                    alt_result = subprocess.run(
                        ["docker", "image", "rm", "-f", img_variant],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    
                    if alt_result.returncode == 0:
                        logger.debug(f"Successfully removed {img_variant} with alternative method")
                        removed_any = True
            
            # Clean up dangling images if we removed anything
            if removed_any:
                cleanup_result = subprocess.run(
                    ["docker", "image", "prune", "-f"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if cleanup_result.returncode == 0:
                    logger.debug("Cleaned up dangling Docker images")
            
            return True  # Always return True to not fail the server removal
                
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout removing Docker image {image}")
            return True
        except Exception as e:
            logger.warning(f"Error removing Docker image {image}: {e}")
            return True