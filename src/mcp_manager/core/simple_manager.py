"""
Simplified MCP Manager that works directly with Claude Code's internal state.

This manager is a thin wrapper around claude mcp CLI commands.
"""

import asyncio
import os
import subprocess
import sys
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from pydantic import BaseModel
import threading
import time

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
    all_servers_test: Optional[Dict[str, Any]] = None


class SimpleMCPManager:
    """Simplified MCP Manager that uses Claude Code's native state."""
    
    # Class-level sync protection (shared across all instances)
    _sync_lock = threading.Lock()
    _last_operation_time = 0
    _operation_cooldown = 2.0  # seconds to wait after operations before allowing sync
    
    def __init__(self):
        """Initialize the manager."""
        self.claude = ClaudeInterface()
    
    @classmethod
    def _mark_operation_start(cls):
        """Mark the start of an MCP operation to prevent sync loops."""
        with cls._sync_lock:
            cls._last_operation_time = time.time()
            logger.debug(f"Marked operation start at {cls._last_operation_time}")
    
    @classmethod
    def is_sync_safe(cls) -> bool:
        """Check if it's safe to perform sync operations (no recent mcp-manager activity)."""
        with cls._sync_lock:
            time_since_operation = time.time() - cls._last_operation_time
            is_safe = time_since_operation > cls._operation_cooldown
            if not is_safe:
                logger.debug(f"Sync blocked: only {time_since_operation:.1f}s since last operation (need {cls._operation_cooldown}s)")
            return is_safe
    
    async def list_servers(self) -> List[Server]:
        """
        List all MCP servers, expanding docker-gateway to show individual servers.
        Includes disabled servers that were previously installed.
        
        Returns:
            List of servers from Claude's internal state with docker-gateway expanded,
            plus any disabled Docker Desktop servers
        """
        servers = self.claude.list_servers()
        result = []
        enabled_docker_servers = set()
        
        for server in servers:
            if server.name == "docker-gateway":
                # Expand docker-gateway to show individual Docker Desktop servers
                docker_servers = await self._expand_docker_gateway(server)
                result.extend(docker_servers)
                # Keep track of enabled Docker Desktop servers
                enabled_docker_servers.update(s.name for s in docker_servers)
                
                # Auto-populate catalog for servers that aren't tracked yet
                catalog = await self._get_server_catalog()
                for docker_server in docker_servers:
                    if docker_server.name not in catalog["servers"]:
                        await self._add_server_to_catalog(
                            name=docker_server.name,
                            server_type=docker_server.server_type.value,
                            enabled=True,
                            command=docker_server.command,
                            args=docker_server.args,
                            env=docker_server.env,
                            description=docker_server.description,
                        )
            else:
                result.append(server)
                
                # Auto-populate catalog for non-docker-gateway servers too
                catalog = await self._get_server_catalog()
                if server.name not in catalog["servers"]:
                    await self._add_server_to_catalog(
                        name=server.name,
                        server_type=server.server_type.value,
                        enabled=True,
                        command=server.command,
                        args=server.args,
                        env=server.env,
                        description=server.description or f"{server.server_type.value} server: {server.name}",
                    )
        
        # Add disabled servers from our catalog that were previously installed
        catalog = await self._get_server_catalog()
        for server_name, server_info in catalog["servers"].items():
            # Only include if disabled and not already in enabled list
            if not server_info.get("enabled", True) and server_name not in enabled_docker_servers:
                # Create a disabled server entry based on catalog info
                server_type_str = server_info.get("type", "docker-desktop")
                server_type = ServerType(server_type_str)
                
                # Set appropriate command based on server type
                if server_type == ServerType.DOCKER_DESKTOP:
                    command = "docker"
                    args = ["mcp", "server", server_name]
                elif server_type == ServerType.NPM:
                    command = server_info.get("command", "npx")
                    args = server_info.get("args", [])
                else:
                    command = server_info.get("command", "unknown")
                    args = server_info.get("args", [])
                
                disabled_server = Server(
                    name=server_name,
                    command=command,
                    args=args,
                    server_type=server_type,
                    scope=ServerScope.USER,
                    enabled=False,  # Mark as disabled
                    description=server_info.get("description", f"{server_type_str} server: {server_name} (disabled)"),
                    env=server_info.get("env", {}),
                )
                result.append(disabled_server)
                
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
        check_duplicates: bool = True,
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
            check_duplicates: Whether to check for similar servers (default: True)
            
        Returns:
            The created server
        """
        # Mark operation start to prevent sync loops
        self._mark_operation_start()
        logger.debug(f"Adding server '{name}' to Claude")
        
        # Check for similar servers if requested
        if check_duplicates:
            similar_servers = await self._check_for_similar_servers(name, server_type, command, args)
            if similar_servers:
                logger.warning(f"Found {len(similar_servers)} similar server(s) to '{name}':")
                for similar_info in similar_servers:
                    similar_server = similar_info["server"]
                    score = similar_info["similarity_score"]
                    reasons = similar_info["reasons"]
                    server_type_str = similar_server.server_type.value if hasattr(similar_server.server_type, 'value') else str(similar_server.server_type)
                    logger.warning(f"  - {similar_server.name} ({server_type_str}) - {score}% similarity")
                    logger.warning(f"    Reasons: {', '.join(reasons)}")
                
                # For now, just log warnings. CLI can decide whether to prompt user.
                # This ensures duplicate detection works for all add_server calls.
        
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
        
        # Add to our catalog as enabled
        await self._add_server_to_catalog(
            name=name,
            server_type=server_type.value if hasattr(server_type, 'value') else str(server_type),
            enabled=True,
            command=command,
            args=args or [],
            env=env or {},
            description=description,
        )
        
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
    
    async def _check_for_similar_servers(
        self,
        name: str,
        server_type: ServerType,
        command: str,
        args: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Check for servers with similar functionality."""
        try:
            from mcp_manager.core.discovery import ServerDiscovery
            from mcp_manager.core.models import DiscoveryResult
            
            # Create a mock DiscoveryResult for the new server
            target_result = DiscoveryResult(
                name=name,
                package=name,  # Use name as package for simplicity
                version="unknown",
                description="",
                server_type=server_type,
                install_command=command,
                install_args=args or []
            )
            
            # Get existing servers
            existing_servers = await self.list_servers()
            
            # Use discovery service to detect similar servers
            discovery = ServerDiscovery()
            similar_servers = discovery.detect_similar_servers(target_result, existing_servers)
            
            return similar_servers
            
        except Exception as e:
            logger.debug(f"Failed to check for similar servers: {e}")
            return []
    
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
        # Mark operation start to prevent sync loops
        self._mark_operation_start()
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
        
        # Remove from our catalog if removal was successful
        if success:
            await self._remove_server_from_catalog(name)
        
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
        # Mark operation start to prevent sync loops
        self._mark_operation_start()
        
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
                # Mark as enabled in catalog or add if not exists
                catalog = await self._get_server_catalog()
                if name in catalog["servers"]:
                    await self._update_server_in_catalog(name, enabled=True)
                else:
                    # Add to catalog if not tracked yet
                    await self._add_server_to_catalog(
                        name=name,
                        server_type=ServerType.DOCKER_DESKTOP.value,
                        enabled=True,
                        command="docker",
                        args=["mcp", "server", name],
                        env={},
                        description=f"Docker Desktop MCP server: {name}",
                    )
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
        # Mark operation start to prevent sync loops
        self._mark_operation_start()
        
        # Check if this is a Docker Desktop server first
        if await self._is_docker_desktop_server(name):
            logger.debug(f"Disabling Docker Desktop server: {name}")
            success = await self._disable_docker_desktop_server_simple(name)
            if success:
                # Mark as disabled in catalog
                await self._update_server_in_catalog(name, enabled=False)
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
                # Docker Desktop MCP servers use the format: mcp/server-name:latest (lowercase)
                docker_image = f"mcp/{server_name.lower()}:latest"
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
            
            # First, try to find all matching images using docker images command
            # This handles both :latest tagged and digest-tagged images
            matching_images = await self._find_matching_docker_images(image)
            
            if not matching_images:
                logger.debug(f"No matching Docker images found for: {image}")
                return True  # Consider this success since the goal is achieved
            
            # Try multiple image variations (with/without tags)
            image_variations = [
                image,
                f"{image}:latest",
                image.replace(":latest", ""),  # Remove :latest if present
            ] + matching_images  # Add images found by docker images command
            
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
            
            # Test all servers (Docker, NPX, Docker Desktop)
            all_servers_test = await self._test_all_servers()
            
            # Keep Docker gateway test for backward compatibility
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
                docker_gateway_test=docker_gateway_test,
                all_servers_test=all_servers_test
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
                docker_gateway_test=None,
                all_servers_test=None
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
            
            # Use dynamic tool discovery - no hardcoded patterns
            
            # Use docker mcp server inspect for each individual server to get real tool data
            for server_name, expected_tool_count in server_tool_counts:
                try:
                    server_specific_tools = self._get_docker_desktop_server_tools_via_inspect(server_name)
                    server_tools[server_name] = server_specific_tools
                    logger.debug(f"Got {len(server_specific_tools)} tools for {server_name} via inspect")
                except Exception as e:
                    logger.debug(f"Failed to get tools for {server_name} via inspect: {e}")
                    # Fallback: distribute tools evenly based on expected counts
                    server_tools[server_name] = []
            
            logger.info(f"Mapped tools to servers: {[(s, len(tools)) for s, tools in server_tools.items()]}")
            return server_tools
            
        except Exception as e:
            logger.debug(f"Failed to get all docker tools: {e}")
            return {}
    
    def _get_docker_desktop_server_tools_via_inspect(self, server_name: str) -> List[Dict[str, Any]]:
        """Get tools for a specific Docker Desktop server using 'docker mcp server inspect'."""
        try:
            import subprocess
            import json
            
            # Use docker mcp server inspect to get real tool data
            result = subprocess.run(
                ["docker", "mcp", "server", "inspect", server_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.debug(f"docker mcp server inspect {server_name} failed: {result.stderr}")
                return []
            
            # Parse JSON response
            try:
                data = json.loads(result.stdout)
                tools = []
                
                # Extract tools from the inspect response
                if "tools" in data and isinstance(data["tools"], list):
                    for tool_json in data["tools"]:
                        # Extract parameters from JSON schema
                        parameters = []
                        if "arguments" in tool_json and isinstance(tool_json["arguments"], list):
                            for arg_info in tool_json["arguments"]:
                                parameters.append({
                                    "name": arg_info.get("name", "unknown"),
                                    "type": arg_info.get("type", "unknown"),
                                    "description": arg_info.get("desc", ""),
                                    "required": not arg_info.get("optional", False)
                                })
                        
                        tool_data = {
                            "name": tool_json.get("name", "unknown"),
                            "description": tool_json.get("description", ""),
                            "parameters": parameters,
                            "source": "docker_mcp_server_inspect"
                        }
                        tools.append(tool_data)
                
                logger.debug(f"Successfully extracted {len(tools)} tools for {server_name}")
                return tools
                
            except json.JSONDecodeError as e:
                logger.debug(f"Failed to parse inspect JSON for {server_name}: {e}")
                return []
                
        except Exception as e:
            logger.debug(f"Failed to inspect Docker Desktop server {server_name}: {e}")
            return []
    
    
    
    
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
            
            # Try multiple methods to discover NPM server tools
            tools = []
            
            # Method 1: MCP protocol communication
            try:
                tools = self._discover_npm_tools_via_mcp_protocol(server, package_name)
                if tools:
                    return {
                        "tool_count": len(tools),
                        "tools": tools,
                        "source": "npm_mcp_protocol",
                        "package_name": package_name
                    }
            except Exception as e:
                logger.debug(f"NPM MCP protocol discovery failed for {package_name}: {e}")
            
            # Method 2: Legacy stdio discovery (fallback)
            try:
                tools = self._discover_mcp_tools_via_stdio(server)
                if tools:
                    return {
                        "tool_count": len(tools),
                        "tools": tools,
                        "source": "npm_stdio_discovery",
                        "package_name": package_name
                    }
            except Exception as e:
                logger.debug(f"NPM stdio discovery failed for {package_name}: {e}")
            
            # Method 3: Package metadata analysis (informational fallback)
            try:
                package_info = self._get_npm_package_metadata(package_name)
                if package_info:
                    return {
                        "tool_count": "Unknown",
                        "tools": [],
                        "source": "npm_package_metadata",
                        "package_name": package_name,
                        "package_info": package_info
                    }
            except Exception as e:
                logger.debug(f"NPM package metadata retrieval failed for {package_name}: {e}")
            
            return {
                "tool_count": "Unknown",
                "tools": [],
                "source": "npm_all_methods_failed",
                "package_name": package_name
            }
            
        except Exception as e:
            logger.debug(f"Failed to get NPM server tools: {e}")
            return {"tool_count": "Error", "tools": [], "source": "npm_error"}
    
    def _get_docker_server_tools(self, server: 'Server') -> Dict[str, Any]:
        """Get tool information for Docker-based MCP servers."""
        try:
            # Extract Docker image for reference
            docker_image = self._extract_docker_image_from_args(server.args or [])
            
            # Try multiple methods to discover Docker container tools
            tools = []
            
            # Method 1: MCP protocol communication
            try:
                tools = self._discover_docker_tools_via_mcp_protocol(server, docker_image)
                if tools:
                    return {
                        "tool_count": len(tools),
                        "tools": tools,
                        "source": "docker_mcp_protocol",
                        "docker_image": docker_image
                    }
            except Exception as e:
                logger.debug(f"Docker MCP protocol discovery failed for {docker_image}: {e}")
            
            # Method 2: Legacy stdio discovery (fallback)
            try:
                tools = self._discover_mcp_tools_via_stdio(server)
                if tools:
                    return {
                        "tool_count": len(tools),
                        "tools": tools,
                        "source": "docker_stdio_discovery",
                        "docker_image": docker_image
                    }
            except Exception as e:
                logger.debug(f"Docker stdio discovery failed for {docker_image}: {e}")
            
            # Method 3: Container inspection (informational fallback)
            try:
                fallback_info = self._get_docker_fallback_info(docker_image, server)
                if fallback_info:
                    return {
                        "tool_count": "Unknown",
                        "tools": [],
                        "source": "docker_container_inspection_failed",
                        "docker_image": docker_image,
                        "fallback_info": fallback_info
                    }
            except Exception as e:
                logger.debug(f"Docker container inspection failed for {docker_image}: {e}")
            
            return {
                "tool_count": "Unknown",
                "tools": [],
                "source": "docker_all_methods_failed",
                "docker_image": docker_image
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
            # For Docker-based servers, try the help-based approach first
            if server.command == "docker":
                docker_tools = self._discover_docker_tools_via_help(server)
                if docker_tools:
                    return docker_tools
            
            # For NPX servers, try to discover tools using package information
            if server.command == "npx":
                npx_tools = self._discover_npx_tools(server)
                if npx_tools:
                    return npx_tools
                
            # Build the command to run the MCP server
            if server.command == "npx":
                cmd = ["npx"] + (server.args or [])
            elif server.command == "docker":
                cmd = ["docker"] + (server.args or [])
            else:
                cmd = [server.command] + (server.args or [])
            
            logger.debug(f"Attempting MCP protocol discovery for {server.name} with command: {' '.join(cmd)}")
            
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
    
    def _discover_npm_tools_via_mcp_protocol(self, server: 'Server', package_name: str) -> List[Dict[str, Any]]:
        """Discover NPM server tools using MCP protocol communication."""
        import subprocess
        import json
        import os
        
        try:
            # Build the command to run the NPM MCP server
            cmd = ["npx"] + (server.args or [])
            
            logger.debug(f"Attempting MCP protocol discovery for NPM server {package_name}")
            
            # MCP initialization handshake
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "clientInfo": {
                        "name": "mcp-manager",
                        "version": "1.0.0"
                    }
                }
            }
            
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            
            # Send both initialization and tools request
            requests = json.dumps(init_request) + "\n" + json.dumps(tools_request) + "\n"
            
            # Run the server process with a timeout
            result = subprocess.run(
                cmd,
                input=requests,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=server.working_dir,
                env={**os.environ, **(server.env or {})}
            )
            
            if result.returncode != 0:
                logger.debug(f"NPM MCP server {package_name} exited with code {result.returncode}: {result.stderr}")
                return []
            
            # Parse responses line by line
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.strip():
                    try:
                        response = json.loads(line)
                        # Look for tools/list response
                        if (response.get("id") == 2 and 
                            "result" in response and 
                            "tools" in response["result"]):
                            
                            tools_data = response["result"]["tools"]
                            parsed_tools = []
                            
                            for tool in tools_data:
                                parsed_tools.append({
                                    "name": tool.get("name", "unknown"),
                                    "description": tool.get("description", ""),
                                    "parameters": self._parse_mcp_tool_parameters(tool.get("inputSchema", {})),
                                    "source": "npm_mcp_protocol"
                                })
                            
                            logger.debug(f"Successfully discovered {len(parsed_tools)} tools for NPM server {package_name}")
                            return parsed_tools
                            
                    except json.JSONDecodeError:
                        continue
            
            logger.debug(f"No valid MCP tools response found for NPM server {package_name}")
            return []
            
        except subprocess.TimeoutExpired:
            logger.debug(f"Timeout while discovering tools for NPM server {package_name}")
            return []
        except Exception as e:
            logger.debug(f"Failed to discover NPM tools via MCP protocol for {package_name}: {e}")
            return []
    
    def _get_npm_package_metadata(self, package_name: str) -> Optional[Dict[str, Any]]:
        """Get metadata about an NPM package."""
        import subprocess
        import json
        
        try:
            # Use npm view to get package information
            result = subprocess.run(
                ["npm", "view", package_name, "--json"],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode == 0:
                package_data = json.loads(result.stdout)
                return {
                    "version": package_data.get("version"),
                    "description": package_data.get("description"),
                    "keywords": package_data.get("keywords", []),
                    "repository": package_data.get("repository"),
                    "homepage": package_data.get("homepage")
                }
            else:
                logger.debug(f"npm view failed for {package_name}: {result.stderr}")
                return None
                
        except Exception as e:
            logger.debug(f"Failed to get NPM package metadata for {package_name}: {e}")
            return None
    
    def _discover_docker_tools_via_mcp_protocol(self, server: 'Server', docker_image: str) -> List[Dict[str, Any]]:
        """Discover Docker server tools using MCP protocol communication."""
        import subprocess
        import json
        import os
        
        try:
            # Build the command to run the Docker MCP server
            cmd = ["docker"] + (server.args or [])
            
            logger.debug(f"Attempting MCP protocol discovery for Docker server {docker_image}")
            
            # MCP initialization handshake
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "clientInfo": {
                        "name": "mcp-manager",
                        "version": "1.0.0"
                    }
                }
            }
            
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            
            # Send both initialization and tools request
            requests = json.dumps(init_request) + "\n" + json.dumps(tools_request) + "\n"
            
            # Run the Docker container with a timeout
            result = subprocess.run(
                cmd,
                input=requests,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=server.working_dir,
                env={**os.environ, **(server.env or {})}
            )
            
            if result.returncode != 0:
                logger.debug(f"Docker MCP server {docker_image} exited with code {result.returncode}: {result.stderr}")
                return []
            
            # Parse responses line by line
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.strip():
                    try:
                        response = json.loads(line)
                        # Look for tools/list response
                        if (response.get("id") == 2 and 
                            "result" in response and 
                            "tools" in response["result"]):
                            
                            tools_data = response["result"]["tools"]
                            parsed_tools = []
                            
                            for tool in tools_data:
                                parsed_tools.append({
                                    "name": tool.get("name", "unknown"),
                                    "description": tool.get("description", ""),
                                    "parameters": self._parse_mcp_tool_parameters(tool.get("inputSchema", {})),
                                    "source": "docker_mcp_protocol"
                                })
                            
                            logger.debug(f"Successfully discovered {len(parsed_tools)} tools for Docker server {docker_image}")
                            return parsed_tools
                            
                    except json.JSONDecodeError:
                        continue
            
            logger.debug(f"No valid MCP tools response found for Docker server {docker_image}")
            return []
            
        except subprocess.TimeoutExpired:
            logger.debug(f"Timeout while discovering tools for Docker server {docker_image}")
            return []
        except Exception as e:
            logger.debug(f"Failed to discover Docker tools via MCP protocol for {docker_image}: {e}")
            return []
    
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
                # Clean up Docker Desktop MCP image if sync was successful
                # Docker image names are typically lowercase
                docker_image = f"mcp/{server_name.lower()}:latest"
                await self._remove_docker_image(docker_image)
                
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
                    if output and not output.startswith("No server"):
                        # Only parse if it's not an error message like "No server is enabled"
                        servers = [s.strip() for s in output.split(",") if s.strip()]
                        available_servers.update(servers)
            except Exception as e:
                logger.debug(f"Failed to list Docker servers: {e}")
            
            # If we still don't have any servers, try to get them from the catalog
            if not available_servers:
                try:
                    result = subprocess.run(
                        [self.claude.docker_path, "mcp", "catalog", "show"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    
                    if result.returncode == 0:
                        catalog_output = result.stdout.strip()
                        if catalog_output:
                            # Parse catalog output to extract server names
                            import re
                            # Look for lines that start with a server name followed by a colon
                            server_pattern = r'^([a-zA-Z][a-zA-Z0-9_-]*): '
                            for line in catalog_output.split('\n'):
                                match = re.match(server_pattern, line)
                                if match:
                                    server_name = match.group(1)
                                    available_servers.add(server_name)
                except Exception as e:
                    logger.debug(f"Failed to get catalog: {e}")
            
            final_list = list(available_servers)
            logger.debug(f"Available Docker servers: {final_list}")
            return final_list
            
        except Exception as e:
            logger.debug(f"Failed to get available Docker servers: {e}")
            return []
    
    async def _get_server_catalog(self) -> Dict[str, Any]:
        """Get the local server catalog that tracks installed servers."""
        try:
            from pathlib import Path
            import json
            
            config_dir = Path.home() / ".config" / "mcp-manager"
            config_dir.mkdir(parents=True, exist_ok=True)
            catalog_file = config_dir / "server_catalog.json"
            
            if catalog_file.exists():
                with open(catalog_file) as f:
                    return json.load(f)
            return {"servers": {}}
            
        except Exception as e:
            logger.debug(f"Failed to get server catalog: {e}")
            return {"servers": {}}
    
    async def _save_server_catalog(self, catalog: Dict[str, Any]):
        """Save the server catalog to disk."""
        try:
            from pathlib import Path
            import json
            
            config_dir = Path.home() / ".config" / "mcp-manager"
            config_dir.mkdir(parents=True, exist_ok=True)
            catalog_file = config_dir / "server_catalog.json"
            
            with open(catalog_file, "w") as f:
                json.dump(catalog, f, indent=2)
                
        except Exception as e:
            logger.debug(f"Failed to save server catalog: {e}")
    
    async def _add_server_to_catalog(self, name: str, server_type: str, enabled: bool = True, **metadata):
        """Add a server to the local catalog."""
        catalog = await self._get_server_catalog()
        catalog["servers"][name] = {
            "type": server_type,
            "enabled": enabled,
            "installed_at": datetime.now().isoformat(),
            **metadata
        }
        await self._save_server_catalog(catalog)
        logger.debug(f"Added server {name} to catalog with enabled={enabled}")
    
    async def _update_server_in_catalog(self, name: str, **updates):
        """Update server status in the catalog."""
        catalog = await self._get_server_catalog()
        if name in catalog["servers"]:
            catalog["servers"][name].update(updates)
            catalog["servers"][name]["updated_at"] = datetime.now().isoformat()
            await self._save_server_catalog(catalog)
            logger.debug(f"Updated server {name} in catalog: {updates}")
    
    async def _remove_server_from_catalog(self, name: str):
        """Remove a server from the catalog completely."""
        catalog = await self._get_server_catalog()
        if name in catalog["servers"]:
            del catalog["servers"][name]
            await self._save_server_catalog(catalog)
            logger.debug(f"Removed server {name} from catalog")
    
    async def _get_disabled_servers(self) -> List[str]:
        """Get list of servers that are in catalog but disabled."""
        catalog = await self._get_server_catalog()
        disabled_servers = []
        for name, info in catalog["servers"].items():
            if not info.get("enabled", True):
                disabled_servers.append(name)
        return disabled_servers
    
    async def _find_matching_docker_images(self, image_pattern: str) -> List[str]:
        """
        Find Docker images that match the given pattern.
        
        Args:
            image_pattern: Image name pattern to match (e.g., "mcp/sqlite")
            
        Returns:
            List of matching image names with full tags/digests
        """
        try:
            # Get all docker images and filter for matches
            result = subprocess.run(
                ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if result.returncode != 0:
                logger.debug(f"Failed to list Docker images: {result.stderr}")
                return []
            
            matching_images = []
            base_name = image_pattern.split(":")[0]  # Remove any existing tag/digest
            
            for line in result.stdout.strip().split('\n'):
                if line and base_name in line:
                    matching_images.append(line.strip())
            
            # Also try to get digest-tagged images using a different format
            digest_result = subprocess.run(
                ["docker", "images", "--digests", "--format", "table {{.Repository}}\t{{.Tag}}\t{{.Digest}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if digest_result.returncode == 0:
                lines = digest_result.stdout.strip().split('\n')
                # Skip the header line
                for line in lines[1:] if len(lines) > 1 else []:
                    if line and base_name in line:
                        parts = line.split('\t')
                        if len(parts) >= 3:
                            repo, tag, digest = parts[0].strip(), parts[1].strip(), parts[2].strip()
                            if digest and digest.startswith("sha256:"):
                                digest_image = f"{repo}@{digest}"
                                matching_images.append(digest_image)
            
            logger.debug(f"Found matching images for {image_pattern}: {matching_images}")
            return matching_images
            
        except Exception as e:
            logger.debug(f"Failed to find matching Docker images for {image_pattern}: {e}")
            return []
    
    def _extract_docker_image_from_args(self, args: List[str]) -> Optional[str]:
        """Extract Docker image name from command arguments."""
        # Look for image name in Docker run command
        # Format: docker run [...options...] image_name
        if "run" in args:
            run_index = args.index("run")
            # Skip options and find the image name (first non-option argument after 'run')
            for i in range(run_index + 1, len(args)):
                arg = args[i]
                # Skip common Docker options
                if arg.startswith('-'):
                    continue
                if arg in ['run', '-i', '--rm', '--pull', 'always', '-it', '--interactive', '--tty']:
                    continue
                # This should be the image name
                return arg
        return None
    
    def _get_docker_fallback_info(self, docker_image: Optional[str], server: 'Server') -> Dict[str, Any]:
        """Provide helpful fallback information for Docker-based MCP servers."""
        info = {
            "reason": "Docker container introspection failed",
            "suggestions": []
        }
        
        if docker_image:
            info["docker_image"] = docker_image
            info["suggestions"].extend([
                "Try running the container manually to see available tools:",
                f"docker run -it --rm {docker_image}",
                "Check the container documentation or Docker Hub page for tool information"
            ])
            
            # Provide common tools based on image name patterns
            if "filesystem" in docker_image.lower():
                info["likely_tools"] = [
                    {"name": "list_directory", "description": "List files and directories"},
                    {"name": "read_file", "description": "Read file contents"},
                    {"name": "write_file", "description": "Write or create files"},
                    {"name": "create_directory", "description": "Create directories"}
                ]
            elif "sqlite" in docker_image.lower():
                info["likely_tools"] = [
                    {"name": "execute_query", "description": "Execute SQL queries"},
                    {"name": "list_tables", "description": "List database tables"},
                    {"name": "describe_table", "description": "Get table schema"}
                ]
        else:
            info["suggestions"].append("Check the server configuration for correct Docker image")
        
        return info
    
    def _discover_docker_tools_via_help(self, server: 'Server') -> List[Dict[str, Any]]:
        """
        Discover MCP tools from Docker containers using the --help approach.
        
        This method runs `mcp --help` inside the Docker container to extract
        available commands/tools, which is more reliable than MCP protocol communication.
        
        Args:
            server: Server configuration for Docker-based MCP server
            
        Returns:
            List of tool dictionaries with name and description
        """
        import subprocess
        import re
        
        try:
            # Extract Docker image from server args
            docker_image = self._extract_docker_image_from_args(server.args or [])
            if not docker_image:
                logger.debug(f"Could not extract Docker image from server {server.name} args")
                return []
            
            logger.debug(f"Attempting Docker help-based tool discovery for {server.name} using image: {docker_image}")
            
            # Try multiple help command approaches
            help_commands = [
                ["mcp", "--help"],
                ["--help"],
                ["/app/mcp", "--help"],
                ["node", "index.js", "--help"],
                ["node", "/app/dist/index.js", "--help"]
            ]

            for help_cmd in help_commands:
                try:
                    result = subprocess.run(
                        ["docker", "run", "--rm", docker_image] + help_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=20
                    )

                    if result.returncode == 0 and result.stdout.strip():
                        tools = []
                        capture = False
                        
                        for line in result.stdout.splitlines():
                            if re.match(r"Commands:", line):
                                capture = True
                                continue
                            if capture:
                                if line.strip() == "":
                                    break  # stop when empty line after commands block
                                parts = line.strip().split(None, 1)
                                if len(parts) >= 1:
                                    cmd = parts[0]
                                    desc = parts[1] if len(parts) > 1 else f"Tool from {server.name}"
                                    tools.append({
                                        "name": cmd,
                                        "description": desc,
                                        "source": "docker_help"
                                    })

                        if tools:
                            logger.debug(f"Successfully discovered {len(tools)} tools from Docker container using: {' '.join(help_cmd)}")
                            return tools

                except subprocess.TimeoutExpired:
                    logger.debug(f"Timeout running help command: {' '.join(help_cmd)}")
                    continue
                except Exception as e:
                    logger.debug(f"Failed help command {' '.join(help_cmd)}: {e}")
                    continue
            
            # If help commands failed, try exploring the container filesystem
            logger.debug(f"Help commands failed, trying filesystem exploration for {server.name}")
            return self._discover_tools_via_filesystem_exploration(docker_image, server.name)

        except Exception as e:
            logger.debug(f"Failed Docker help-based discovery for {server.name}: {e}")
            return []
    
    def _discover_tools_via_filesystem_exploration(self, docker_image: str, server_name: str) -> List[Dict[str, Any]]:
        """
        Discover tools by inspecting Docker container configuration.
        
        This method inspects the container's entrypoint, cmd, and environment
        to understand the actual MCP server structure and available tools.
        """
        import subprocess
        import json
        
        try:
            tools = []
            
            # First, inspect the Docker image configuration
            logger.debug(f"Inspecting Docker image configuration for {server_name}")
            
            # Get entrypoint, cmd, and environment
            inspect_commands = {
                "entrypoint": "--format='{{.Config.Entrypoint}}'",
                "cmd": "--format='{{.Config.Cmd}}'", 
                "env": "--format='{{.Config.Env}}'"
            }
            
            container_info = {}
            
            for info_type, format_arg in inspect_commands.items():
                try:
                    result = subprocess.run(
                        ["docker", "inspect", docker_image, format_arg],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0:
                        output = result.stdout.strip().strip("'\"")
                        container_info[info_type] = output
                        logger.debug(f"{info_type}: {output}")
                
                except Exception as e:
                    logger.debug(f"Error getting {info_type}: {e}")
                    continue
            
            # Parse the configuration to understand MCP tools
            if container_info:
                # Look at entrypoint and cmd to understand the server structure
                entrypoint = container_info.get("entrypoint", "")
                cmd = container_info.get("cmd", "")
                env = container_info.get("env", "")
                
                # Extract information about the MCP server
                if "node" in entrypoint or "node" in cmd:
                    # This is a Node.js-based MCP server
                    tools.append({
                        "name": "filesystem_server", 
                        "description": "Node.js MCP filesystem server",
                        "source": "docker_inspect",
                        "details": f"Entrypoint: {entrypoint}, Cmd: {cmd}"
                    })
                
                elif "python" in entrypoint or "python" in cmd:
                    # This is a Python-based MCP server
                    tools.append({
                        "name": "mcp_server",
                        "description": "Python MCP server",
                        "source": "docker_inspect", 
                        "details": f"Entrypoint: {entrypoint}, Cmd: {cmd}"
                    })
                
                # Look for specific MCP patterns in the configuration
                config_text = f"{entrypoint} {cmd} {env}".lower()
                if "mcp" in config_text:
                    if "filesystem" in config_text:
                        tools.append({
                            "name": "read_file",
                            "description": "Read file contents",
                            "source": "docker_config_analysis"
                        })
                        tools.append({
                            "name": "write_file", 
                            "description": "Write file contents",
                            "source": "docker_config_analysis"
                        })
                        tools.append({
                            "name": "list_directory",
                            "description": "List directory contents", 
                            "source": "docker_config_analysis"
                        })
            
            # Try to get tools from container documentation
            if not tools:
                doc_tools = self._discover_tools_from_container_docs(docker_image, server_name)
                if doc_tools:
                    tools.extend(doc_tools)
            
            # Fallback: try to explore /app directory structure
            if not tools:
                try:
                    result = subprocess.run(
                        ["docker", "run", "--rm", docker_image, "ls", "-la", "/app"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0:
                        logger.debug(f"/app directory contents: {result.stdout}")
                        # Look for package.json or other indicators
                        if "package.json" in result.stdout or "index.js" in result.stdout:
                            tools.append({
                                "name": "mcp_server",
                                "description": "MCP server executable",
                                "source": "app_directory_analysis"
                            })
                
                except Exception as e:
                    logger.debug(f"Error exploring /app: {e}")
            
            if tools:
                logger.debug(f"Discovered {len(tools)} tools via Docker inspection")
                return tools
            
            logger.debug(f"No tools discovered via Docker inspection for {server_name}")
            return []
            
        except Exception as e:
            logger.debug(f"Failed Docker inspection: {e}")
            return []
    
    def _discover_tools_from_container_docs(self, docker_image: str, server_name: str) -> List[Dict[str, Any]]:
        """
        Discover tools from Docker container documentation and labels.
        
        This method extracts information from Docker Hub API, container labels,
        and any embedded documentation to understand available MCP tools.
        """
        import subprocess
        import re
        import json
        
        try:
            tools = []
            
            # First, check container labels which might contain tool information
            try:
                result = subprocess.run(
                    ["docker", "inspect", docker_image, "--format='{{.Config.Labels}}'"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    labels_output = result.stdout.strip().strip("'\"")
                    logger.debug(f"Container labels: {labels_output}")
                    
                    # Parse labels for tool information
                    if labels_output and labels_output != "map[]" and labels_output != "<no value>":
                        # Look for MCP-specific labels or descriptions
                        labels_text = labels_output.lower()
                        if "mcp" in labels_text and "tools" in labels_text:
                            # Try to extract tool names from labels
                            tool_matches = re.findall(r'tools?["\']?:\s*["\']?([^"\'}\]]+)', labels_text)
                            for match in tool_matches:
                                tool_names = [t.strip() for t in match.split(',')]
                                for tool_name in tool_names:
                                    if tool_name and len(tool_name) > 2:
                                        tools.append({
                                            "name": tool_name,
                                            "description": f"Tool from container labels",
                                            "source": "docker_labels"
                                        })
            
            except Exception as e:
                logger.debug(f"Error checking container labels: {e}")
            
            # Try to get documentation from Docker Hub API
            if not tools:
                try:
                    # Parse image name for Docker Hub API call
                    if "/" in docker_image:
                        namespace, repo_tag = docker_image.split("/", 1)
                        if ":" in repo_tag:
                            repo, tag = repo_tag.split(":", 1)
                        else:
                            repo = repo_tag
                            tag = "latest"
                    else:
                        namespace = "library"
                        if ":" in docker_image:
                            repo, tag = docker_image.split(":", 1)
                        else:
                            repo = docker_image
                            tag = "latest"
                    
                    # Use httpx to get Docker Hub repository information
                    import httpx
                    
                    # Get repository description from Docker Hub API
                    hub_url = f"https://hub.docker.com/v2/repositories/{namespace}/{repo}/"
                    
                    async def fetch_docker_hub_info():
                        async with httpx.AsyncClient(timeout=5.0) as client:
                            response = await client.get(hub_url)
                            if response.status_code == 200:
                                data = response.json()
                                description = data.get("description", "")
                                full_description = data.get("full_description", "")
                                
                                # Parse description for MCP tools
                                combined_text = f"{description} {full_description}".lower()
                                logger.debug(f"Docker Hub description: {description}")
                                
                                # Look for tool patterns in description
                                tool_patterns = [
                                    r'tools?:\s*([^.]+)',
                                    r'provides?\s+([^.]+)\s+tools?',
                                    r'supports?\s+([^.]+)\s+operations?',
                                    r'includes?\s+([^.]+)\s+functionality'
                                ]
                                
                                found_tools = []
                                for pattern in tool_patterns:
                                    matches = re.findall(pattern, combined_text)
                                    for match in matches:
                                        # Extract individual tool names
                                        tool_names = re.split(r'[,&\sand\s]+', match.strip())
                                        for tool_name in tool_names:
                                            tool_name = tool_name.strip()
                                            if tool_name and len(tool_name) > 2:
                                                found_tools.append({
                                                    "name": tool_name,
                                                    "description": f"Tool from Docker Hub description",
                                                    "source": "docker_hub_api"
                                                })
                                
                                return found_tools
                            return []
                    
                    # Use sync httpx to get Docker Hub repository information
                    with httpx.Client(timeout=5.0) as client:
                        try:
                            response = client.get(hub_url)
                            if response.status_code == 200:
                                data = response.json()
                                description = data.get("description", "")
                                full_description = data.get("full_description", "")
                                
                                logger.debug(f"Docker Hub description for {namespace}/{repo}: {description}")
                                
                                # Parse description for MCP tools
                                combined_text = f"{description} {full_description}".lower()
                                
                                # Look for tool patterns in Docker Hub documentation
                                # First, try to find the structured tools table
                                tools_table_match = re.search(r'tools provided by this server.*?\n(.+?)(?:\n---|\n##|\n\n|\Z)', combined_text, re.DOTALL | re.IGNORECASE)
                                
                                if tools_table_match:
                                    # Extract tools from the structured table
                                    table_content = tools_table_match.group(1)
                                    # Look for `tool_name`|description patterns
                                    tool_matches = re.findall(r'`([a-zA-Z_][a-zA-Z0-9_]*)`\s*\|\s*([^|]+)', table_content)
                                    for tool_name, description in tool_matches:
                                        tools.append({
                                            "name": tool_name,
                                            "description": description.strip(),
                                            "source": "docker_hub_documentation"
                                        })
                                
                                # Also look for individual tool headings like "#### Tool: **`tool_name`**"
                                tool_header_matches = re.findall(r'tool:\s*\*\*`([a-zA-Z_][a-zA-Z0-9_]*)`\*\*', combined_text, re.IGNORECASE)
                                for tool_name in tool_header_matches:
                                    # Only add if we haven't already found it in the table
                                    if not any(t["name"] == tool_name for t in tools):
                                        tools.append({
                                            "name": tool_name,
                                            "description": f"MCP tool from {docker_image}",
                                            "source": "docker_hub_documentation"
                                        })
                                
                                # Fallback: look for any `tool_name` patterns in backticks
                                if not tools:
                                    tool_patterns = [
                                        r'`([a-zA-Z_][a-zA-Z0-9_]*)`',  # `tool_name`
                                        r'\*\*`([a-zA-Z_][a-zA-Z0-9_]*)`\*\*',  # **`tool_name`**
                                    ]
                                    
                                    for pattern in tool_patterns:
                                        matches = re.findall(pattern, combined_text)
                                        for tool_name in matches:
                                            # Filter out common non-tool words
                                            if tool_name not in ["string", "array", "boolean", "object", "number", "file", "dir"]:
                                                tools.append({
                                                    "name": tool_name,
                                                    "description": f"Tool from Docker Hub documentation",
                                                    "source": "docker_hub_api"
                                                })
                                
                                # If it's a filesystem server, add standard filesystem tools
                                if "filesystem" in combined_text and not tools:
                                    tools.extend([
                                        {"name": "read_file", "description": "Read file contents", "source": "docker_hub_analysis"},
                                        {"name": "write_file", "description": "Write file contents", "source": "docker_hub_analysis"},
                                        {"name": "list_directory", "description": "List directory contents", "source": "docker_hub_analysis"},
                                        {"name": "create_directory", "description": "Create directories", "source": "docker_hub_analysis"}
                                    ])
                                
                                # For custom Docker containers not on Docker Hub, try pattern matching
                                elif not tools:
                                    custom_tools = self._predict_docker_tools_from_image_name(docker_image)
                                    if custom_tools:
                                        tools.extend(custom_tools)
                        
                        except httpx.RequestError as e:
                            logger.debug(f"Network error accessing Docker Hub: {e}")
                        except Exception as e:
                            logger.debug(f"Error parsing Docker Hub response: {e}")
                    
                except Exception as e:
                    logger.debug(f"Error fetching Docker Hub info: {e}")
            
            # Try to find README or documentation files in the container
            if not tools:
                doc_files = ["README.md", "README.txt", "README", "DOCS.md", "docs/README.md"]
                for doc_file in doc_files:
                    try:
                        result = subprocess.run(
                            ["docker", "run", "--rm", docker_image, "cat", f"/{doc_file}"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            timeout=5
                        )
                        
                        if result.returncode == 0 and result.stdout:
                            doc_content = result.stdout.lower()
                            logger.debug(f"Found documentation file: {doc_file}")
                            
                            # Look for MCP tool patterns in documentation
                            if "mcp" in doc_content and any(word in doc_content for word in ["tools", "commands", "functions"]):
                                # Extract tool information from documentation
                                tool_patterns = [
                                    r'- `(\w+)`[:\s]+([^\n]+)',  # - `tool_name`: description
                                    r'\*\*(\w+)\*\*[:\s]+([^\n]+)',  # **tool_name**: description
                                    r'### (\w+)\n([^\n]+)',  # ### tool_name\ndescription
                                ]
                                
                                for pattern in tool_patterns:
                                    matches = re.findall(pattern, doc_content)
                                    for name, desc in matches:
                                        if any(keyword in name.lower() for keyword in ["read", "write", "list", "create", "delete", "search"]):
                                            tools.append({
                                                "name": name,
                                                "description": desc.strip(),
                                                "source": f"container_docs_{doc_file}"
                                            })
                                
                                if tools:
                                    break
                    
                    except Exception as e:
                        logger.debug(f"Error checking {doc_file}: {e}")
                        continue
            
            if tools:
                logger.debug(f"Discovered {len(tools)} tools from container documentation")
                return tools[:10]  # Limit to first 10 tools to avoid overwhelming output
            
            return []
            
        except Exception as e:
            logger.debug(f"Failed to discover tools from container docs: {e}")
            return []
    
    def _discover_npx_tools(self, server: 'Server') -> List[Dict[str, Any]]:
        """
        Discover tools from NPX-based MCP servers.
        
        This method attempts various approaches to discover tools from NPX servers:
        1. Try --help commands
        2. Check package.json for tool information
        3. Query npm registry for package documentation
        4. Use pattern matching based on server name
        """
        import subprocess
        import json
        import re
        
        try:
            tools = []
            
            if not server.args:
                logger.debug(f"No args found for NPX server {server.name}")
                return []
            
            # Extract package name from NPX arguments
            package_name = None
            for arg in server.args:
                if not arg.startswith('-') and arg != 'npx':
                    package_name = arg
                    break
            
            if not package_name:
                logger.debug(f"Could not extract package name from NPX server {server.name}")
                return []
            
            logger.debug(f"Discovering tools for NPX package: {package_name}")
            
            # Method 1: Try --help command
            try:
                result = subprocess.run(
                    ["npx", package_name, "--help"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=15
                )
                
                if result.returncode == 0 and result.stdout:
                    help_tools = self._parse_npx_help_output(result.stdout, package_name)
                    if help_tools:
                        tools.extend(help_tools)
                        logger.debug(f"Found {len(help_tools)} tools from --help for {package_name}")
            
            except subprocess.TimeoutExpired:
                logger.debug(f"Timeout running --help for {package_name}")
            except Exception as e:
                logger.debug(f"Error running --help for {package_name}: {e}")
            
            # Method 2: Try npm info to get package documentation
            if not tools:
                try:
                    result = subprocess.run(
                        ["npm", "info", package_name, "--json"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode == 0 and result.stdout:
                        npm_info = json.loads(result.stdout)
                        npm_tools = self._parse_npm_package_info(npm_info, package_name)
                        if npm_tools:
                            tools.extend(npm_tools)
                            logger.debug(f"Found {len(npm_tools)} tools from npm info for {package_name}")
                
                except subprocess.TimeoutExpired:
                    logger.debug(f"Timeout running npm info for {package_name}")
                except Exception as e:
                    logger.debug(f"Error running npm info for {package_name}: {e}")
            
            # Method 3: Pattern-based tool prediction
            if not tools:
                pattern_tools = self._predict_tools_from_package_name(package_name)
                if pattern_tools:
                    tools.extend(pattern_tools)
                    logger.debug(f"Predicted {len(pattern_tools)} tools for {package_name}")
            
            return tools[:15]  # Limit to avoid overwhelming output
            
        except Exception as e:
            logger.debug(f"Failed NPX tool discovery for {server.name}: {e}")
            return []
    
    def _parse_npx_help_output(self, help_output: str, package_name: str) -> List[Dict[str, Any]]:
        """Parse help output from NPX packages to extract tool information."""
        tools = []
        
        try:
            lines = help_output.lower().split('\n')
            
            # Look for common help patterns
            in_commands_section = False
            for line in lines:
                line = line.strip()
                
                # Detect commands/tools section
                if any(keyword in line for keyword in ['commands:', 'tools:', 'actions:', 'available:']):
                    in_commands_section = True
                    continue
                
                if in_commands_section:
                    # Stop if we hit options or examples section
                    if any(keyword in line for keyword in ['options:', 'examples:', 'usage:', '--']):
                        break
                    
                    # Extract command patterns like "  command_name    description"
                    command_match = re.match(r'\s*([a-zA-Z_][a-zA-Z0-9_-]*)\s+(.+)', line)
                    if command_match:
                        cmd_name, description = command_match.groups()
                        tools.append({
                            "name": cmd_name.strip(),
                            "description": description.strip(),
                            "source": "npx_help"
                        })
            
            # Also look for any tool-like patterns in the entire output
            if not tools:
                # Look for patterns like "Available tools:" or similar
                tool_patterns = [
                    r'tools?:\s*([^.\n]+)',
                    r'provides?\s+([^.\n]+)\s+functionality',
                    r'supports?\s+([^.\n]+)\s+operations?'
                ]
                
                for pattern in tool_patterns:
                    matches = re.findall(pattern, help_output.lower())
                    for match in matches:
                        # Extract individual tool names
                        tool_names = re.split(r'[,&\sand\s]+', match.strip())
                        for tool_name in tool_names:
                            tool_name = tool_name.strip()
                            if tool_name and len(tool_name) > 2:
                                tools.append({
                                    "name": tool_name.replace(" ", "_"),
                                    "description": f"Tool from {package_name}",
                                    "source": "npx_help_pattern"
                                })
            
            return tools
            
        except Exception as e:
            logger.debug(f"Error parsing NPX help output: {e}")
            return []
    
    def _parse_npm_package_info(self, npm_info: dict, package_name: str) -> List[Dict[str, Any]]:
        """Parse npm package info to extract tool information."""
        tools = []
        
        try:
            # Check description for tool hints
            description = npm_info.get('description', '').lower()
            readme = npm_info.get('readme', '').lower()
            keywords = npm_info.get('keywords', [])
            
            combined_text = f"{description} {readme}"
            
            # Look for MCP-specific patterns
            if 'mcp' in combined_text or any('mcp' in str(k).lower() for k in keywords):
                # Extract tool names from documentation
                tool_patterns = [
                    r'tools?[:\s]+([^.\n]+)',
                    r'provides?\s+([^.\n]+)\s+tools?',
                    r'supports?\s+([^.\n]+)\s+operations?',
                    r'functions?[:\s]+([^.\n]+)',
                    r'commands?[:\s]+([^.\n]+)'
                ]
                
                for pattern in tool_patterns:
                    matches = re.findall(pattern, combined_text)
                    for match in matches:
                        # Extract individual tool names
                        tool_names = re.split(r'[,&\sand\s]+', match.strip())
                        for tool_name in tool_names:
                            tool_name = tool_name.strip()
                            if tool_name and len(tool_name) > 2 and tool_name not in ['the', 'and', 'or']:
                                tools.append({
                                    "name": tool_name.replace(" ", "_"),
                                    "description": f"Tool from {package_name} package",
                                    "source": "npm_package_info"
                                })
            
            return tools
            
        except Exception as e:
            logger.debug(f"Error parsing npm package info: {e}")
            return []
    
    def _predict_tools_from_package_name(self, package_name: str) -> List[Dict[str, Any]]:
        """Predict likely tools based on package name patterns."""
        tools = []
        
        try:
            package_lower = package_name.lower()
            
            # Common MCP server patterns and their likely tools
            tool_predictions = {
                'filesystem': [
                    {"name": "read_file", "description": "Read file contents"},
                    {"name": "write_file", "description": "Write file contents"},
                    {"name": "list_directory", "description": "List directory contents"},
                    {"name": "create_directory", "description": "Create directories"}
                ],
                'sqlite': [
                    {"name": "query", "description": "Execute SQL queries"},
                    {"name": "create_table", "description": "Create database tables"},
                    {"name": "insert_data", "description": "Insert data into tables"}
                ],
                'web': [
                    {"name": "fetch", "description": "Fetch web pages"},
                    {"name": "scrape", "description": "Scrape web content"}
                ],
                'search': [
                    {"name": "search", "description": "Search for information"},
                    {"name": "query", "description": "Query search engines"}
                ],
                'browser': [
                    {"name": "navigate", "description": "Navigate to web pages"},
                    {"name": "click", "description": "Click elements"},
                    {"name": "type", "description": "Type text into fields"}
                ]
            }
            
            # Check if package name contains any known patterns
            for pattern, predicted_tools in tool_predictions.items():
                if pattern in package_lower:
                    for tool in predicted_tools:
                        tools.append({
                            "name": tool["name"],
                            "description": tool["description"],
                            "source": "pattern_prediction"
                        })
                    break  # Only use the first matching pattern
            
            return tools
            
        except Exception as e:
            logger.debug(f"Error predicting tools from package name: {e}")
            return []
    
    def _predict_docker_tools_from_image_name(self, docker_image: str) -> List[Dict[str, Any]]:
        """Predict likely tools based on Docker image name patterns."""
        tools = []
        
        try:
            image_lower = docker_image.lower()
            
            # Common patterns in custom Docker MCP images
            if 'filesystem' in image_lower or 'files' in image_lower:
                tools.extend([
                    {"name": "read_file", "description": "Read file contents", "source": "custom_docker_prediction"},
                    {"name": "write_file", "description": "Write file contents", "source": "custom_docker_prediction"},
                    {"name": "list_directory", "description": "List directory contents", "source": "custom_docker_prediction"}
                ])
            elif 'database' in image_lower or 'sql' in image_lower or 'db' in image_lower:
                tools.extend([
                    {"name": "query", "description": "Execute database queries", "source": "custom_docker_prediction"},
                    {"name": "insert", "description": "Insert data into database", "source": "custom_docker_prediction"}
                ])
            elif 'web' in image_lower or 'http' in image_lower or 'api' in image_lower:
                tools.extend([
                    {"name": "fetch", "description": "Fetch web content", "source": "custom_docker_prediction"},
                    {"name": "post", "description": "Send HTTP POST requests", "source": "custom_docker_prediction"}
                ])
            elif 'search' in image_lower:
                tools.extend([
                    {"name": "search", "description": "Search for information", "source": "custom_docker_prediction"}
                ])
            elif 'browser' in image_lower or 'selenium' in image_lower:
                tools.extend([
                    {"name": "navigate", "description": "Navigate to web pages", "source": "custom_docker_prediction"},
                    {"name": "click", "description": "Click elements", "source": "custom_docker_prediction"},
                    {"name": "type", "description": "Type text", "source": "custom_docker_prediction"}
                ])
            
            return tools
            
        except Exception as e:
            logger.debug(f"Error predicting tools from Docker image name: {e}")
            return []
    
    def _is_likely_mcp_executable(self, filename: str) -> bool:
        """
        Determine if a filename is likely an MCP-related executable.
        
        Args:
            filename: Name of the executable file
            
        Returns:
            True if the file is likely MCP-related
        """
        # Skip common system executables
        system_executables = {
            'sh', 'bash', 'ls', 'cat', 'grep', 'sed', 'awk', 'find', 'chmod', 'chown',
            'cp', 'mv', 'rm', 'mkdir', 'rmdir', 'touch', 'tar', 'gzip', 'gunzip',
            'ps', 'top', 'kill', 'killall', 'mount', 'umount', 'df', 'du', 'free',
            'uname', 'whoami', 'id', 'groups', 'su', 'sudo', 'passwd', 'crontab',
            'curl', 'wget', 'ping', 'netstat', 'ss', 'iptables', 'systemctl',
            'service', 'nginx', 'apache2', 'mysql', 'postgres', 'redis-server',
            'docker', 'git', 'npm', 'node', 'python', 'python3', 'pip', 'pip3'
        }
        
        if filename.lower() in system_executables:
            return False
        
        # Look for MCP-related patterns
        mcp_patterns = [
            'mcp', 'server', 'tool', 'agent', 'context', 'protocol',
            'filesystem', 'database', 'web', 'api', 'search', 'browser'
        ]
        
        filename_lower = filename.lower()
        for pattern in mcp_patterns:
            if pattern in filename_lower:
                return True
        
        # Include any custom executables that aren't obviously system tools
        # This catches app-specific binaries that might be MCP servers
        return len(filename) > 2 and not filename.startswith('.')
    
    def _parse_docker_help_output(self, help_output: str, server_name: str) -> List[Dict[str, Any]]:
        """
        Parse help output from Docker MCP containers to extract tools/commands.
        
        Args:
            help_output: Raw help text from the container
            server_name: Name of the server for logging
            
        Returns:
            List of tool dictionaries
        """
        import re
        
        tools = []
        
        try:
            lines = help_output.splitlines()
            capture_commands = False
            
            for line in lines:
                line = line.strip()
                
                # Look for sections that indicate commands/tools
                if re.search(r"(commands?|tools?|available|usage):", line.lower()):
                    capture_commands = True
                    continue
                    
                if capture_commands:
                    # Stop capturing if we hit an empty line or new section
                    if line == "" or line.startswith("-") or line.lower().startswith("options"):
                        if tools:  # Only stop if we found some tools
                            break
                        capture_commands = False
                        continue
                    
                    # Extract command names - look for patterns like:
                    # "  command_name    Description here"
                    # "* command_name - Description"
                    # "command_name: Description"
                    command_patterns = [
                        r"^\s*\*?\s*([a-zA-Z_][a-zA-Z0-9_-]*)\s*[-:]\s*(.+)$",  # command - description
                        r"^\s*([a-zA-Z_][a-zA-Z0-9_-]*)\s{2,}(.+)$",           # command    description (2+ spaces)
                        r"^\s*([a-zA-Z_][a-zA-Z0-9_-]*)\s*$"                   # just command name
                    ]
                    
                    for pattern in command_patterns:
                        match = re.match(pattern, line)
                        if match:
                            tool_name = match.group(1).strip()
                            description = match.group(2).strip() if len(match.groups()) > 1 else f"Tool from {server_name}"
                            
                            # Skip generic help-related commands
                            if tool_name.lower() in ['help', 'version', '--help', '--version', '-h', '-v']:
                                break
                            
                            tools.append({
                                "name": tool_name,
                                "description": description,
                                "parameters": []  # Help output usually doesn't include detailed parameter info
                            })
                            break
            
            # If no structured commands found, try to find any command-like words
            if not tools:
                # Look for patterns that might indicate available tools
                all_text = help_output.lower()
                if "filesystem" in all_text or "file" in all_text:
                    tools.append({"name": "filesystem_operations", "description": "File system operations", "parameters": []})
                elif "sqlite" in all_text or "database" in all_text:
                    tools.append({"name": "database_operations", "description": "Database operations", "parameters": []})
                elif "http" in all_text or "web" in all_text:
                    tools.append({"name": "http_operations", "description": "HTTP operations", "parameters": []})
            
            logger.debug(f"Parsed {len(tools)} tools from help output for {server_name}")
            return tools
            
        except Exception as e:
            logger.debug(f"Error parsing help output for {server_name}: {e}")
            return []

    async def _test_all_servers(self) -> Optional[Dict[str, Any]]:
        """
        Test all MCP servers (Docker, NPX, Docker Desktop) to get comprehensive tool counts.
        
        Returns:
            Dict with test results including working_servers with tool counts for each server
        """
        try:
            servers = await self.list_servers()
            if not servers:
                return {
                    "status": "no_servers",
                    "servers_tested": [],
                    "working_servers": [],
                    "failed_servers": [],
                    "total_tools": 0
                }
            
            servers_tested = []
            working_servers = []
            failed_servers = []
            total_tools = 0
            
            logger.debug(f"Testing {len(servers)} servers for tool discovery")
            
            for server in servers:
                servers_tested.append(server.name)
                
                try:
                    # Get server details which includes tool discovery
                    details = await self.get_server_details(server.name)
                    
                    if details:
                        tool_count = details.get('tool_count', 0)
                        
                        # Convert "Unknown" to 0 for counting
                        if tool_count == "Unknown" or tool_count == "Error":
                            tool_count = 0
                        
                        if isinstance(tool_count, int) and tool_count > 0:
                            working_servers.append({
                                "name": server.name,
                                "tools": tool_count,
                                "type": server.server_type.value,
                                "source": details.get('source', 'unknown')
                            })
                            total_tools += tool_count
                            logger.debug(f"Server {server.name}: {tool_count} tools discovered")
                        else:
                            failed_servers.append({
                                "name": server.name,
                                "error": f"No tools discovered ({details.get('source', 'unknown')})",
                                "type": server.server_type.value
                            })
                            logger.debug(f"Server {server.name}: No tools discovered")
                    else:
                        failed_servers.append({
                            "name": server.name,
                            "error": "Server details not available",
                            "type": server.server_type.value if hasattr(server, 'server_type') else 'unknown'
                        })
                
                except Exception as e:
                    logger.debug(f"Error testing server {server.name}: {e}")
                    failed_servers.append({
                        "name": server.name,
                        "error": str(e),
                        "type": server.server_type.value if hasattr(server, 'server_type') else 'unknown'
                    })
            
            # Determine overall status
            if working_servers:
                status = "success" if not failed_servers else "partial_success"
            else:
                status = "failed"
            
            result = {
                "status": status,
                "servers_tested": servers_tested,
                "working_servers": working_servers,
                "failed_servers": failed_servers,
                "total_tools": total_tools,
                "summary": f"Found {total_tools} tools across {len(working_servers)} working servers"
            }
            
            logger.debug(f"All servers test complete: {len(working_servers)} working, {len(failed_servers)} failed, {total_tools} total tools")
            return result
            
        except Exception as e:
            logger.error(f"Failed to test all servers: {e}")
            return {
                "status": "error",
                "error": str(e),
                "servers_tested": [],
                "working_servers": [],
                "failed_servers": [],
                "total_tools": 0
            }

    async def _update_server_status(self, server_name: str, enabled: bool):
        """Update the enabled status of a server in the catalog."""
        await self._update_server_in_catalog(server_name, enabled=enabled)
