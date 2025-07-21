"""
Simplified MCP Manager that works directly with Claude Code's internal state.

This manager is a thin wrapper around claude mcp CLI commands.
"""

import asyncio
import os
import subprocess
import sys
from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel

from mcp_manager.core.claude_interface import ClaudeInterface
from mcp_manager.core.exceptions import MCPManagerError
from mcp_manager.core.models import Server, ServerType, ServerScope, SystemInfo
from mcp_manager.utils.config import get_config
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class SyncCheckResult(BaseModel):
    """Result of synchronization check between mcp-manager and Claude."""
    
    in_sync: bool
    claude_available: bool
    will_start_claude_session: bool
    manager_servers: List[str]
    claude_servers: List[str]
    missing_in_claude: List[str]
    missing_in_manager: List[str]
    issues: List[str]
    warnings: List[str]
    docker_gateway_test: Optional[Dict[str, Any]] = None


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
        For Docker Desktop servers, this enables them in Docker Desktop.
        
        Args:
            name: Server name to enable
            
        Returns:
            The server object
        """
        # Check if server already exists in Claude
        server = self.claude.get_server(name)
        if server:
            logger.debug(f"Server '{name}' is already enabled in Claude")
            return server
        
        # Check if this is a Docker Desktop server
        if await self._is_docker_desktop_server(name):
            logger.debug(f"Enabling Docker Desktop server: {name}")
            success = await self._enable_docker_desktop_server_simple(name)
            if success:
                # Return a mock server object for Docker Desktop servers
                from .models import Server, ServerScope, ServerType
                return Server(
                    name=name,
                    command="docker",
                    args=["mcp", "run", name],
                    env={},
                    enabled=True,
                    scope=ServerScope.USER,
                    server_type=ServerType.DOCKER_DESKTOP
                )
            else:
                raise MCPManagerError(f"Failed to enable Docker Desktop server '{name}'")
        
        # If not found, we can't enable it without knowing the command
        raise MCPManagerError(
            f"Server '{name}' not found. Use 'add' to create it first, "
            "or use 'discover' to find available servers."
        )
    
    async def disable_server(self, name: str) -> Server:
        """
        Disable an MCP server.
        
        Note: In Claude's model, disabling means removing.
        For Docker Desktop servers, this disables them in Docker Desktop.
        
        Args:
            name: Server name to disable
            
        Returns:
            The server object before removal
        """
        # Check if this is a Docker Desktop server first
        if await self._is_docker_desktop_server(name):
            logger.debug(f"Disabling Docker Desktop server: {name}")
            success = await self._disable_docker_desktop_server_simple(name)
            if success:
                # Return a mock server object for Docker Desktop servers
                from .models import Server, ServerScope, ServerType
                return Server(
                    name=name,
                    command="docker",
                    args=["mcp", "run", name],
                    env={},
                    enabled=False,
                    scope=ServerScope.USER,
                    server_type=ServerType.DOCKER_DESKTOP
                )
            else:
                raise MCPManagerError(f"Failed to disable Docker Desktop server '{name}'")
        
        # Get server before removing (for regular servers)
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
            # Remove existing gateway if it exists - try all scopes
            if self.claude.server_exists("docker-gateway"):
                # Try removing from different scopes until successful
                removed = False
                for scope in ["user", "project", "local"]:
                    try:
                        result = subprocess.run(
                            [self.claude.claude_path, "mcp", "remove", "--scope", scope, "docker-gateway"],
                            capture_output=True,
                            text=True,
                            timeout=30,
                        )
                        if result.returncode == 0:
                            logger.debug(f"Removed existing docker-gateway from {scope} scope")
                            removed = True
                            break
                    except Exception:
                        continue
                
                if not removed:
                    logger.warning("Could not remove docker-gateway from any scope, proceeding anyway")
            
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
                # Docker Desktop MCP servers use the format: mcp/server-name:latest
                docker_image = f"mcp/{server_name}:latest"
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
            # First check if it's in the current docker-gateway configuration in Claude
            # This is important for servers that are enabled in Claude but disabled in Docker Desktop
            try:
                gateway_server = self.claude.get_server("docker-gateway")
                if gateway_server and gateway_server.args:
                    # Parse the --servers argument to extract server names
                    servers_arg = None
                    for i, arg in enumerate(gateway_server.args):
                        if arg == "--servers" and i + 1 < len(gateway_server.args):
                            servers_arg = gateway_server.args[i + 1]
                            break
                    
                    if servers_arg:
                        server_names = [s.strip() for s in servers_arg.split(",")]
                        if name in server_names:
                            return True
            except Exception:
                pass  # If docker-gateway doesn't exist or has issues, continue with other checks
            
            # Get the list of enabled Docker Desktop servers
            enabled_servers = await self._get_enabled_docker_servers()
            if name in enabled_servers:
                return True
                
            # Also check available Docker Desktop servers (not just enabled)
            available_servers = await self._get_available_docker_servers()
            return name in available_servers
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
            # Look for patterns like mcp/name:tag or registry/name:tag
            patterns = [
                r'(mcp/[^:\s]+(?::[^:\s]+)?)',
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
    
    async def check_sync_status(self) -> SyncCheckResult:
        """
        Check synchronization status between mcp-manager and Claude.
        
        Returns:
            SyncCheckResult with detailed sync status information
        """
        logger.debug("Checking synchronization status between mcp-manager and Claude")
        
        issues = []
        warnings = []
        manager_servers = []
        claude_servers = []
        missing_in_claude = []
        missing_in_manager = []
        claude_available = False
        will_start_claude_session = False
        
        try:
            # Check if Claude CLI is available
            claude_available, _ = self._check_command("claude", ["--version"])
            if not claude_available:
                issues.append("Claude CLI not available - install Claude Code first")
                return SyncCheckResult(
                    in_sync=False,
                    claude_available=claude_available,
                    will_start_claude_session=False,
                    manager_servers=manager_servers,
                    claude_servers=claude_servers,
                    missing_in_claude=missing_in_claude,
                    missing_in_manager=missing_in_manager,
                    issues=issues,
                    warnings=warnings,
                    docker_gateway_test=None
                )
            
            # Check if running 'claude mcp list' will start a session
            try:
                # First check if Claude has an active session by trying a quick command
                result = subprocess.run(
                    ["claude", "--help"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                # If this succeeds without prompting, Claude is ready
                if result.returncode == 0:
                    will_start_claude_session = False
                else:
                    will_start_claude_session = True
                    warnings.append("Running sync check will start a new Claude session")
            except Exception:
                will_start_claude_session = True
                warnings.append("Cannot determine Claude session status - may start a new session")
            
            # Get servers from mcp-manager's perspective
            try:
                servers = await self.list_servers()
                manager_servers = [s.name for s in servers]
                logger.debug(f"Found {len(manager_servers)} servers in manager: {manager_servers}")
            except Exception as e:
                issues.append(f"Failed to get servers from mcp-manager: {e}")
                manager_servers = []
            
            # Get servers from Claude CLI
            try:
                logger.debug("Getting server list from Claude CLI")
                result = subprocess.run(
                    ["claude", "mcp", "list"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                
                if result.returncode == 0:
                    # Parse Claude's output and expand docker-gateway if present
                    claude_servers = await self._parse_claude_server_list(result.stdout.strip())
                    logger.debug(f"Found {len(claude_servers)} servers in Claude (after expansion): {claude_servers}")
                else:
                    issues.append(f"Failed to get server list from Claude: {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                issues.append("Claude CLI command timed out - Claude may need authentication")
            except Exception as e:
                issues.append(f"Error running Claude CLI: {e}")
            
            # Compare server lists
            manager_set = set(manager_servers)
            claude_set = set(claude_servers)
            
            # Find discrepancies
            missing_in_claude = list(manager_set - claude_set)
            missing_in_manager = list(claude_set - manager_set)
            
            # Now that we've expanded docker-gateway, the comparison should be more accurate
            # Any remaining discrepancies are real sync issues
            
            # Check for configuration issues
            if missing_in_claude:
                issues.append(f"Servers in mcp-manager but not in Claude: {', '.join(missing_in_claude)}")
            
            if missing_in_manager:
                warnings.append(f"Servers in Claude but not visible in mcp-manager: {', '.join(missing_in_manager)}")
            
            # Additional checks
            await self._perform_additional_sync_checks(issues, warnings)
            
            # Test Docker gateway if present
            docker_gateway_test = await self._test_docker_gateway()
            
            # Determine if in sync
            in_sync = len(issues) == 0 and len(missing_in_claude) == 0
            
            return SyncCheckResult(
                in_sync=in_sync,
                claude_available=claude_available,
                will_start_claude_session=will_start_claude_session,
                manager_servers=manager_servers,
                claude_servers=claude_servers,
                missing_in_claude=missing_in_claude,
                missing_in_manager=missing_in_manager,
                issues=issues,
                warnings=warnings,
                docker_gateway_test=docker_gateway_test
            )
            
        except Exception as e:
            logger.error(f"Failed to check sync status: {e}")
            issues.append(f"Sync check failed: {e}")
            
            return SyncCheckResult(
                in_sync=False,
                claude_available=claude_available,
                will_start_claude_session=will_start_claude_session,
                manager_servers=manager_servers,
                claude_servers=claude_servers,
                missing_in_claude=missing_in_claude,
                missing_in_manager=missing_in_manager,
                issues=issues,
                warnings=warnings,
                docker_gateway_test=None
            )
    
    async def _perform_additional_sync_checks(self, issues: List[str], warnings: List[str]) -> None:
        """Perform additional synchronization checks."""
        try:
            # Check if Claude configuration file exists and is readable
            claude_config_path = self.claude.get_config_path()
            if not claude_config_path.exists():
                issues.append("Claude configuration file not found")
            elif not claude_config_path.is_file():
                issues.append("Claude configuration path is not a file")
            else:
                # Check if configuration is readable
                try:
                    import json
                    with open(claude_config_path) as f:
                        config_data = json.load(f)
                    
                    # Check for common configuration issues
                    if "mcpServers" not in config_data:
                        warnings.append("No MCP servers section found in Claude configuration")
                    
                    # Check for problematic configurations
                    mcp_servers = config_data.get("mcpServers", {})
                    for server_name, server_config in mcp_servers.items():
                        command = server_config.get("command", "")
                        
                        # Check for known problematic patterns
                        if "mcp/" in command and "docker run" in command:
                            issues.append(f"Server '{server_name}' has problematic Docker command - run cleanup")
                            
                except json.JSONDecodeError:
                    issues.append("Claude configuration file is corrupted (invalid JSON)")
                except Exception as e:
                    warnings.append(f"Could not fully validate Claude configuration: {e}")
            
            # Check Docker Desktop integration if available
            try:
                docker_available, _ = self._check_command("docker", ["--version"])
                if docker_available:
                    # Check if docker-gateway is properly configured
                    enabled_servers = await self._get_enabled_docker_servers()
                    if enabled_servers:
                        # Verify docker-gateway exists in Claude
                        servers = self.claude.list_servers()
                        has_gateway = any(s.name == "docker-gateway" for s in servers)
                        if not has_gateway:
                            issues.append("Docker Desktop servers enabled but docker-gateway not configured in Claude")
                
            except Exception as e:
                warnings.append(f"Could not check Docker Desktop integration: {e}")
                
        except Exception as e:
            logger.warning(f"Additional sync checks failed: {e}")
            warnings.append("Could not perform all sync checks")
    
    async def _parse_claude_server_list(self, claude_output: str) -> List[str]:
        """
        Parse Claude CLI output and expand docker-gateway into individual servers.
        
        Args:
            claude_output: Raw output from 'claude mcp list'
            
        Returns:
            List of server names with docker-gateway expanded
        """
        servers = []
        
        try:
            logger.debug(f"Parsing Claude output: {claude_output}")
            output_lines = claude_output.strip().split('\n')
            
            for line in output_lines:
                line = line.strip()
                if not line or line.startswith('No servers') or line.startswith('Servers:'):
                    continue
                
                logger.debug(f"Processing line: '{line}'")
                
                # Check if line contains docker-gateway command
                if "docker" in line and "mcp" in line and "gateway" in line and "--servers" in line:
                    # This is a docker-gateway command line, extract the server list
                    expanded_servers = await self._extract_servers_from_gateway_command(line)
                    servers.extend(expanded_servers)
                    logger.debug(f"Expanded docker-gateway command to: {expanded_servers}")
                elif line.startswith("docker-gateway"):
                    # Handle "docker-gateway: server1,server2" format
                    expanded_servers = await self._expand_docker_gateway_from_claude_output(line)
                    servers.extend(expanded_servers)
                    logger.debug(f"Expanded docker-gateway to: {expanded_servers}")
                else:
                    # Regular server - extract server name (first word/column)
                    parts = line.split()
                    if parts:
                        server_name = parts[0].rstrip(':')  # Remove trailing colon
                        # Skip if it looks like a command path
                        if not server_name.startswith('/') and server_name not in servers:
                            servers.append(server_name)
                            logger.debug(f"Added regular server: {server_name}")
            
            logger.debug(f"Final parsed servers: {servers}")
            return servers
            
        except Exception as e:
            logger.warning(f"Failed to parse Claude server list: {e}")
            # Fallback: try to get enabled servers from docker directly
            try:
                enabled_servers = await self._get_enabled_docker_servers()
                logger.debug(f"Fallback to Docker servers: {enabled_servers}")
                return enabled_servers
            except Exception:
                return []
    
    async def _extract_servers_from_gateway_command(self, command_line: str) -> List[str]:
        """
        Extract server names from a docker-gateway command line.
        
        Args:
            command_line: Command line like "/opt/homebrew/bin/docker mcp gateway run --servers aws-diagram,curl,playwright"
            
        Returns:
            List of individual server names
        """
        try:
            logger.debug(f"Extracting servers from command: {command_line}")
            
            # Look for --servers argument
            if "--servers" not in command_line:
                logger.debug("No --servers argument found")
                return []
            
            # Split by --servers and get the part after it
            parts = command_line.split("--servers", 1)
            if len(parts) < 2:
                logger.debug("Could not split on --servers")
                return []
            
            # Get the servers part and clean it up
            servers_part = parts[1].strip()
            
            # Handle cases where there might be additional arguments after the server list
            # Take only the first token after --servers
            servers_part = servers_part.split()[0] if servers_part.split() else ""
            
            if not servers_part:
                logger.debug("Empty servers part")
                return []
            
            # Split by comma and clean up names
            server_names = [s.strip() for s in servers_part.split(",") if s.strip()]
            logger.debug(f"Extracted server names: {server_names}")
            
            return server_names
            
        except Exception as e:
            logger.warning(f"Failed to extract servers from gateway command: {e}")
            return []
    
    async def _expand_docker_gateway_from_claude_output(self, gateway_line: str) -> List[str]:
        """
        Expand docker-gateway from Claude output line into individual server names.
        
        Args:
            gateway_line: Line from Claude output containing docker-gateway info
            
        Returns:
            List of individual Docker Desktop server names
        """
        try:
            # Claude output might look like:
            # "docker-gateway: aws-diagram,curl,playwright"
            # or just "docker-gateway"
            
            if ":" in gateway_line:
                # Extract the server list after the colon
                _, servers_part = gateway_line.split(":", 1)
                servers_part = servers_part.strip()
                
                if servers_part:
                    # Split by comma and clean up names
                    server_names = [s.strip() for s in servers_part.split(",") if s.strip()]
                    return server_names
            
            # If no servers listed or different format, try to get from Docker directly
            logger.debug("No servers found in docker-gateway line, checking Docker Desktop directly")
            enabled_servers = await self._get_enabled_docker_servers()
            return enabled_servers
            
        except Exception as e:
            logger.warning(f"Failed to expand docker-gateway from Claude output: {e}")
            # Fallback: try to get enabled servers directly
            try:
                enabled_servers = await self._get_enabled_docker_servers()
                return enabled_servers
            except Exception:
                return []
    
    async def _test_docker_gateway(self) -> Optional[Dict[str, Any]]:
        """
        Test Docker gateway functionality by running dry-run command.
        
        Returns:
            Dict with test results or None if no docker-gateway found
        """
        try:
            # Check if docker-gateway is configured by checking Claude directly
            # (not from list_servers which shows expanded servers)
            try:
                result = subprocess.run(
                    ["claude", "mcp", "list"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                
                claude_has_docker_gateway = False
                if result.returncode == 0 and result.stdout:
                    claude_has_docker_gateway = "docker-gateway" in result.stdout
                    
            except Exception as e:
                logger.warning(f"Failed to check Claude for docker-gateway: {e}")
                return None
            
            if not claude_has_docker_gateway:
                logger.debug("No docker-gateway found in Claude configuration")
                return None
            
            logger.debug("Testing Docker gateway functionality")
            
            # Check if Docker is available
            docker_available, _ = self._check_command("docker", ["--version"])
            if not docker_available:
                return {
                    "status": "failed",
                    "error": "Docker command not available",
                    "servers_tested": [],
                    "working_servers": [],
                    "failed_servers": [],
                    "total_tools": 0
                }
            
            # Get current Docker Desktop servers from registry (most accurate)
            docker_servers = await self._get_enabled_docker_servers()
            
            if not docker_servers:
                return {
                    "status": "no_servers",
                    "error": "No enabled Docker Desktop servers found",
                    "servers_tested": [],
                    "working_servers": [],
                    "failed_servers": [],
                    "total_tools": 0
                }
            
            if not docker_servers:
                return {
                    "status": "failed",
                    "error": "No Docker servers configured",
                    "servers_tested": [],
                    "working_servers": [],
                    "failed_servers": [],
                    "total_tools": 0
                }
            
            # Run Docker gateway test command
            servers_list = ",".join(docker_servers)
            test_command = [
                "docker", "mcp", "gateway", "run",
                "--servers", servers_list,
                "--dry-run", "--verbose"
            ]
            
            logger.debug(f"Running Docker gateway test: {' '.join(test_command)}")
            
            result = subprocess.run(
                test_command,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            
            # Parse the output - Docker gateway uses stderr for its output
            working_servers = []
            failed_servers = []
            total_tools = 0
            
            # Docker gateway outputs to stderr, not stdout
            output_text = result.stderr if result.stderr else result.stdout
            output_lines = output_text.split('\n') if output_text else []
            
            for line in output_lines:
                line = line.strip()
                
                # Look for server status lines like "> aws-diagram: (3 tools)"
                if line.startswith("> ") and ": (" in line and " tools)" in line:
                    try:
                        # Extract server name and tool count
                        server_info = line[2:]  # Remove "> "
                        server_name = server_info.split(":")[0].strip()
                        
                        # Handle different formats: "(3 tools)" or "(6 tools) (1 prompts) (1 resources)"
                        parts_with_parens = server_info.split("(")
                        if len(parts_with_parens) > 1:
                            # Find the tools count - look for first "(N tools)" pattern
                            tools_count = 0
                            for part in parts_with_parens[1:]:  # Skip the server name part
                                if "tools)" in part:
                                    tools_part = part.split(")")[0].strip()
                                    try:
                                        tools_count = int(tools_part.split()[0])
                                        break
                                    except (ValueError, IndexError):
                                        continue
                            
                            working_servers.append({
                                "name": server_name,
                                "tools": tools_count
                            })
                            total_tools += tools_count
                        
                    except Exception as e:
                        logger.debug(f"Failed to parse server line '{line}': {e}")
                
                # Look for error messages like "> Can't start filesystem: Error..."
                elif line.startswith("> Can't start ") and ":" in line:
                    try:
                        error_part = line[2:]  # Remove "> "
                        if "Can't start " in error_part:
                            server_name = error_part.split("Can't start ")[1].split(":")[0].strip()
                            error_msg = error_part.split(":", 1)[1].strip() if ":" in error_part else "Unknown error"
                            
                            failed_servers.append({
                                "name": server_name,
                                "error": error_msg
                            })
                    except Exception as e:
                        logger.debug(f"Failed to parse error line '{line}': {e}")
            
            # Determine overall status
            if result.returncode == 0 and working_servers:
                status = "success"
                error = None
            elif result.returncode == 0 and not working_servers and not failed_servers:
                status = "warning"
                error = "No server status found in output"
            else:
                status = "failed"
                error = f"Command failed (exit {result.returncode})"
                if result.stderr:
                    error += f": {result.stderr[:200]}"
            
            return {
                "status": status,
                "error": error,
                "servers_tested": docker_servers,
                "working_servers": working_servers,
                "failed_servers": failed_servers,
                "total_tools": total_tools,
                "raw_output": (result.stderr if result.stderr else result.stdout)[:1000] if (result.stderr or result.stdout) else None,
                "stderr_output": result.stderr[:500] if result.stderr else None,
                "exit_code": result.returncode,
                "command": " ".join(test_command),
                "debug_lines_found": len([line for line in output_lines if line.startswith("> ") and ": (" in line])
            }
            
        except subprocess.TimeoutExpired:
            return {
                "status": "failed",
                "error": "Docker gateway test timed out (60s)",
                "servers_tested": docker_servers if 'docker_servers' in locals() else [],
                "working_servers": [],
                "failed_servers": [],
                "total_tools": 0
            }
        except Exception as e:
            logger.warning(f"Docker gateway test failed: {e}")
            return {
                "status": "failed",
                "error": f"Test execution failed: {e}",
                "servers_tested": docker_servers if 'docker_servers' in locals() else [],
                "working_servers": [],
                "failed_servers": [],
                "total_tools": 0
            }
    
    async def get_server_details(self, server_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific server including its tools."""
        try:
            servers = await self.list_servers()
            server = next((s for s in servers if s.name == server_name), None)
            
            if not server:
                return None
            
            details = {
                "name": server.name,
                "type": server.server_type.value,
                "scope": server.scope.value if server.scope else "unknown",
                "status": "enabled" if server.enabled else "disabled",
                "command": server.command,
                "args": server.args,
                "env": server.env,
                "tools": [],
                "description": getattr(server, 'description', ''),
            }
            
            # Try to get tool information using different methods
            if server.server_type == ServerType.DOCKER_DESKTOP:
                details.update(self._get_docker_desktop_server_tools(server_name))
            else:
                details.update(self._get_generic_server_tools(server))
            
            return details
            
        except Exception as e:
            logger.warning(f"Failed to get server details for {server_name}: {e}")
            return None
    
    def _get_docker_desktop_server_tools(self, server_name: str) -> Dict[str, Any]:
        """Get tool information for Docker Desktop MCP server using docker mcp tools."""
        try:
            # Get all tools mapped by server
            all_server_tools = self._get_all_docker_tools()
            if not all_server_tools:
                logger.debug(f"No tools found via docker mcp tools")
                return {"tool_count": 0, "tools": [], "source": "error"}
            
            # Get tools for this specific server
            server_tools = all_server_tools.get(server_name, [])
            
            return {
                "tool_count": len(server_tools),
                "tools": server_tools,
                "source": "docker_mcp_tools_mapped"
            }
            
        except Exception as e:
            logger.debug(f"Failed to get Docker server tools for {server_name}: {e}")
            return {"tool_count": 0, "tools": [], "source": "error"}
    
    def _get_all_docker_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all tools mapped by server using docker mcp tools list --verbose --format json."""
        try:
            # Step 1: Get verbose output to determine server order and tool counts
            verbose_result = subprocess.run(
                ["docker", "mcp", "tools", "list", "--verbose"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if verbose_result.returncode != 0:
                logger.debug(f"docker mcp tools list --verbose failed: {verbose_result.stderr}")
                return {}
            
            # Parse server order and tool counts from stderr
            server_tool_counts = []
            all_lines = verbose_result.stderr.strip().split('\n') if verbose_result.stderr else []
            
            for line in all_lines:
                if "gateway:" in line and "tools)" in line:
                    # Extract server name and tool count from lines like:
                    # "- gateway:   > filesystem: (11 tools)"
                    if "> " in line and ": (" in line and " tools)" in line:
                        server_info = line.split("> ")[1]  # Get "filesystem: (11 tools)"
                        server_name = server_info.split(":")[0].strip()
                        count_part = server_info.split("(")[1].split(" tools)")[0]
                        try:
                            tool_count = int(count_part)
                            server_tool_counts.append((server_name, tool_count))
                        except ValueError:
                            pass
            
            if not server_tool_counts:
                logger.debug("No server tool counts found in verbose output")
                return {}
                
            # Step 2: Get all tools with full JSON schema
            json_result = subprocess.run(
                ["docker", "mcp", "tools", "list", "--verbose", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if json_result.returncode != 0:
                logger.debug(f"docker mcp tools list --format json failed: {json_result.stderr}")
                return {}
            
            # Parse JSON tools
            import json
            try:
                all_tools_json = json.loads(json_result.stdout)
                if not isinstance(all_tools_json, list):
                    logger.debug("Expected JSON array of tools")
                    return {}
            except json.JSONDecodeError as e:
                logger.debug(f"Failed to parse JSON tools: {e}")
                return {}
            
            logger.debug(f"Found {len(all_tools_json)} tools in JSON, server counts: {server_tool_counts}")
            
            # Step 3: Map tools to servers based on tool names and functionality 
            # Initialize server tool collections
            server_tools = {}
            for server_name, _ in server_tool_counts:
                server_tools[server_name] = []
            
            # Define tool patterns for each server type
            filesystem_tools = {
                'create_directory', 'directory_tree', 'edit_file', 'get_file_info',
                'list_allowed_directories', 'list_directory', 'move_file', 
                'read_file', 'read_multiple_files', 'search_files', 'write_file'
            }
            
            sqlite_tools = {
                'create_table', 'describe_table', 'list_tables', 'read_query', 'write_query'
            }
            
            diagram_tools = {
                'append_insight', 'generate_diagram', 'get_diagram_examples', 'list_icons'
            }
            
            # Map each tool to the appropriate server based on its name
            for tool_json in all_tools_json:
                tool_name = tool_json.get("name", "unknown")
                
                # Extract parameters from JSON schema
                parameters = []
                if "inputSchema" in tool_json and "properties" in tool_json["inputSchema"]:
                    for param_name, param_info in tool_json["inputSchema"]["properties"].items():
                        parameters.append({
                            "name": param_name,
                            "type": param_info.get("type", "unknown"),
                            "description": param_info.get("description", ""),
                            "required": param_name in tool_json["inputSchema"].get("required", [])
                        })
                
                tool_data = {
                    "name": tool_name,
                    "description": tool_json.get("description", ""),
                    "parameters": parameters
                }
                
                # Assign tool to the appropriate server
                if tool_name in filesystem_tools:
                    server_tools['filesystem'].append(tool_data)
                elif tool_name in sqlite_tools:
                    server_tools['SQLite'].append(tool_data)
                elif tool_name in diagram_tools:
                    server_tools['aws-diagram'].append(tool_data)
                else:
                    logger.warning(f"Unknown tool {tool_name}, assigning to first available server")
                    # Assign to the server with the fewest tools assigned so far
                    min_server = min(server_tools.keys(), key=lambda s: len(server_tools[s]))
                    server_tools[min_server].append(tool_data)
            
            logger.info(f"Mapped tools to servers: {[(s, len(tools)) for s, tools in server_tools.items()]}")
            return server_tools
            
        except Exception as e:
            logger.debug(f"Failed to get all docker tools: {e}")
            return {}
    
    
    
    
    def _generate_server_tools(self, server_name: str, tool_count: int, server_description: str = "") -> List[Dict[str, Any]]:
        """Generate basic tool information with detected count - no hardcoded descriptions."""
        tools = []
        
        for i in range(tool_count):
            tools.append({
                "name": f"Tool {i+1}",
                "description": f"MCP tool provided by {server_name} server"
            })
        
        return tools
    
    
    
    def _get_generic_server_tools(self, server: 'Server') -> Dict[str, Any]:
        """Get tool information for generic MCP servers by attempting to communicate directly."""
        try:
            if server.server_type == ServerType.NPM:
                return self._get_npm_server_tools(server)
            elif server.server_type == ServerType.DOCKER:
                return self._get_docker_server_tools(server)
            else:
                return self._get_unknown_server_tools(server)
            
        except Exception as e:
            logger.debug(f"Failed to get generic server tools: {e}")
            return {"tool_count": 0, "tools": [], "source": "error"}
    
    def _get_npm_server_tools(self, server: 'Server') -> Dict[str, Any]:
        """Get tool information for NPM-based MCP servers."""
        try:
            # Extract package name from command
            package_name = None
            if server.command == "npx" and server.args:
                # Find the package name in args (skip flags like -y)
                for arg in server.args:
                    if not arg.startswith("-"):
                        package_name = arg
                        break
            
            if not package_name:
                return {
                    "tool_count": "Unknown",
                    "tools": [],
                    "source": "npm_no_package",
                    "package_name": None
                }
            
            # Try to discover tools by running the server with introspection
            tools = self._discover_mcp_tools_via_stdio(server)
            
            return {
                "tool_count": len(tools) if tools else "Unknown",
                "tools": tools or [],
                "source": "npm_discovered" if tools else "npm_failed",
                "package_name": package_name
            }
            
        except Exception as e:
            logger.debug(f"Failed to get NPM server tools: {e}")
            return {"tool_count": "Error", "tools": [], "source": "npm_error"}
    
    def _get_docker_server_tools(self, server: 'Server') -> Dict[str, Any]:
        """Get tool information for Docker-based MCP servers."""
        try:
            # Try to discover tools by running the container with introspection
            tools = self._discover_mcp_tools_via_stdio(server)
            
            return {
                "tool_count": len(tools) if tools else "Unknown",
                "tools": tools or [],
                "source": "docker_discovered" if tools else "docker_failed"
            }
            
        except Exception as e:
            logger.debug(f"Failed to get Docker server tools: {e}")
            return {"tool_count": "Error", "tools": [], "source": "docker_error"}
    
    def _get_unknown_server_tools(self, server: 'Server') -> Dict[str, Any]:
        """Get tool information for servers of unknown type."""
        try:
            # Try generic MCP protocol communication
            tools = self._discover_mcp_tools_via_stdio(server)
            
            return {
                "tool_count": len(tools) if tools else "Unknown",
                "tools": tools or [],
                "source": "generic_discovered" if tools else "generic_failed"
            }
            
        except Exception as e:
            logger.debug(f"Failed to get unknown server tools: {e}")
            return {"tool_count": "Error", "tools": [], "source": "generic_error"}
    
    def _discover_mcp_tools_via_stdio(self, server: 'Server') -> List[Dict[str, Any]]:
        """Attempt to discover MCP tools by communicating with the server via stdio."""
        try:
            # Build the command to run the MCP server
            if server.command == "npx":
                cmd = ["npx"] + (server.args or [])
            elif server.command == "docker":
                cmd = ["docker"] + (server.args or [])
            else:
                cmd = [server.command] + (server.args or [])
            
            logger.debug(f"Attempting MCP tool discovery for {server.name} with command: {' '.join(cmd)}")
            
            # Try to communicate with the MCP server using a simple protocol request
            # This is a basic implementation - in practice, you'd want more robust MCP protocol handling
            mcp_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            }
            
            import json
            request_json = json.dumps(mcp_request)
            
            # Run the server process with a timeout
            result = subprocess.run(
                cmd,
                input=request_json + "\n",
                capture_output=True,
                text=True,
                timeout=10,
                cwd=server.working_dir,
                env={**os.environ, **(server.env or {})}
            )
            
            if result.returncode != 0:
                logger.debug(f"MCP server {server.name} exited with code {result.returncode}: {result.stderr}")
                return []
            
            # Try to parse the response
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.strip():
                    try:
                        response = json.loads(line)
                        if "result" in response and "tools" in response["result"]:
                            tools = response["result"]["tools"]
                            parsed_tools = []
                            for tool in tools:
                                parsed_tools.append({
                                    "name": tool.get("name", "unknown"),
                                    "description": tool.get("description", ""),
                                    "parameters": self._parse_mcp_tool_parameters(tool.get("inputSchema", {}))
                                })
                            return parsed_tools
                    except json.JSONDecodeError:
                        continue
            
            logger.debug(f"No valid MCP tools response found for {server.name}")
            return []
            
        except subprocess.TimeoutExpired:
            logger.debug(f"Timeout while discovering tools for {server.name}")
            return []
        except Exception as e:
            logger.debug(f"Failed to discover MCP tools for {server.name}: {e}")
            return []
    
    def _parse_mcp_tool_parameters(self, input_schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse MCP tool input schema into parameter list."""
        parameters = []
        
        properties = input_schema.get("properties", {})
        required = set(input_schema.get("required", []))
        
        for param_name, param_info in properties.items():
            parameters.append({
                "name": param_name,
                "type": param_info.get("type", "unknown"),
                "description": param_info.get("description", ""),
                "required": param_name in required
            })
        
        return parameters
    
    async def _enable_docker_desktop_server_simple(self, name: str) -> bool:
        """Enable a Docker Desktop MCP server (simplified version for enable_server)."""
        import subprocess
        
        try:
            # Extract the actual server name (remove docker-desktop- prefix if present)
            if name.startswith("docker-desktop-"):
                server_name = name.replace("docker-desktop-", "")
            else:
                server_name = name
            
            logger.debug(f"Enabling Docker Desktop MCP server: {server_name}")
            
            # Enable the server in Docker Desktop
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
    
    async def _disable_docker_desktop_server_simple(self, name: str) -> bool:
        """Disable a Docker Desktop MCP server (simplified version for disable_server)."""
        import subprocess
        
        try:
            # Extract the actual server name (remove docker-desktop- prefix if present)
            if name.startswith("docker-desktop-"):
                server_name = name.replace("docker-desktop-", "")
            else:
                server_name = name
            
            logger.debug(f"Disabling Docker Desktop MCP server: {server_name}")
            
            # Disable the server in Docker Desktop
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
            
            # Refresh the gateway with the updated server list
            sync_success = await self._refresh_docker_gateway()
            
            if sync_success:
                logger.debug(f"Successfully removed {server_name} from Claude Code")
                return True
            else:
                logger.error("Failed to sync Docker Desktop servers to Claude Code")
                return False
                
        except Exception as e:
            logger.error(f"Failed to disable Docker Desktop server {name}: {e}")
            return False
    
    async def _get_available_docker_servers(self) -> List[str]:
        """Get list of all available Docker Desktop MCP servers (enabled and disabled)."""
        try:
            # First get enabled servers
            enabled_servers = await self._get_enabled_docker_servers()
            
            # For available but not enabled servers, we need to check what Docker Desktop supports
            # The registry.yaml file should contain all available servers
            import yaml
            from pathlib import Path
            
            registry_path = Path.home() / ".docker" / "mcp" / "registry.yaml"
            available_servers = set(enabled_servers)  # Start with enabled servers
            
            if registry_path.exists():
                try:
                    with open(registry_path) as f:
                        registry_data = yaml.safe_load(f)
                        if registry_data and "registry" in registry_data:
                            # Add all servers from registry
                            for server_name in registry_data["registry"].keys():
                                available_servers.add(server_name)
                except Exception as e:
                    logger.debug(f"Failed to read registry.yaml: {e}")
            
            # Also try to get available servers using docker mcp server list
            try:
                result = subprocess.run(
                    [self.claude.docker_path, "mcp", "server", "list"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                
                if result.returncode == 0:
                    output = result.stdout.strip()
                    if output:
                        servers = [s.strip() for s in output.split(",") if s.strip()]
                        available_servers.update(servers)
            except Exception as e:
                logger.debug(f"Failed to list Docker servers: {e}")
            
            final_list = list(available_servers)
            logger.debug(f"Available Docker servers: {final_list}")
            return final_list
            
        except Exception as e:
            logger.debug(f"Failed to get available Docker servers: {e}")
            return []