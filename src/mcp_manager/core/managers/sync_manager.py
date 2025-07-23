"""
Sync Manager for Claude Code synchronization operations.

Handles synchronization between mcp-manager and Claude Code's internal state,
including Docker Desktop gateway management and sync validation.
"""

import json
import os
import re
import subprocess
import threading
import time
from typing import List, Optional, Dict, Any, Callable

from pydantic import BaseModel

from mcp_manager.core.claude_interface import ClaudeInterface
from mcp_manager.core.models import Server, ServerType, ServerScope
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


class SyncManager:
    """Manages synchronization between mcp-manager and Claude Code."""
    
    # Class-level sync protection (shared across all instances)
    _sync_lock = threading.Lock()
    _last_operation_time = 0
    _operation_cooldown = 2.0  # seconds to wait after operations before allowing sync
    
    def __init__(self, claude_interface: Optional[ClaudeInterface] = None,
                 server_list_callback: Optional[Callable[[], List[Server]]] = None):
        """Initialize sync manager.
        
        Args:
            claude_interface: Optional Claude interface (will create if not provided)
            server_list_callback: Optional callback to get server list
        """
        self.claude = claude_interface or ClaudeInterface()
        self._server_list_callback = server_list_callback
        logger.debug("SyncManager initialized")
    
    @classmethod
    def is_sync_safe(cls) -> bool:
        """
        Check if it's safe to perform sync operations.
        
        Returns:
            True if no recent mcp-manager operations occurred
        """
        with cls._sync_lock:
            elapsed = time.time() - cls._last_operation_time
            return elapsed >= cls._operation_cooldown
    
    def check_sync_status(self) -> SyncCheckResult:
        """
        Check synchronization status between mcp-manager and Claude Code.
        
        Returns:
            SyncCheckResult with detailed sync information
        """
        logger.debug("Checking sync status between mcp-manager and Claude Code")
        
        issues = []
        warnings = []
        
        # Check Claude CLI availability
        claude_available = self.claude.is_claude_cli_available()
        will_start_claude_session = not claude_available
        
        if not claude_available:
            issues.append("Claude CLI not available - some sync features limited")
        
        # Get server lists
        manager_servers = []
        if self._server_list_callback:
            try:
                servers = self._server_list_callback()
                manager_servers = [s.name for s in servers]
            except Exception as e:
                issues.append(f"Failed to get manager server list: {e}")
        
        claude_servers = []
        if claude_available:
            try:
                # Get Claude server list and expand docker-gateway
                claude_output = self.claude.get_raw_server_list()
                claude_servers = self._parse_claude_server_list(claude_output)
            except Exception as e:
                issues.append(f"Failed to get Claude server list: {e}")
        
        # Compare server lists
        missing_in_claude = [s for s in manager_servers if s not in claude_servers]
        missing_in_manager = [s for s in claude_servers if s not in manager_servers]
        
        # Perform additional sync checks
        self._perform_additional_sync_checks(issues, warnings)
        
        # Test Docker gateway if available
        docker_gateway_test = None
        if claude_available:
            docker_gateway_test = self._test_docker_gateway()
        
        # Determine if in sync
        in_sync = (
            len(missing_in_claude) == 0 and
            len(missing_in_manager) == 0 and
            len(issues) == 0 and
            claude_available
        )
        
        result = SyncCheckResult(
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
        
        logger.info(f"Sync check completed - In sync: {in_sync}", extra={
            "in_sync": in_sync,
            "manager_servers": len(manager_servers),
            "claude_servers": len(claude_servers),
            "missing_in_claude": len(missing_in_claude),
            "missing_in_manager": len(missing_in_manager),
            "issues": len(issues),
            "warnings": len(warnings)
        })
        
        return result
    
    def _perform_additional_sync_checks(self, issues: List[str], warnings: List[str]) -> None:
        """
        Perform additional synchronization checks.
        
        Args:
            issues: List to append critical issues to
            warnings: List to append warnings to
        """
        # Check Claude config file integrity
        try:
            claude_config_path = self.claude.get_claude_config_path()
            if not claude_config_path.exists():
                issues.append("Claude config file does not exist")
                return
            
            # Try to parse the config as JSON
            try:
                with open(claude_config_path) as f:
                    config_data = json.load(f)
                
                # Check for MCP servers section
                if "mcpServers" not in config_data:
                    warnings.append("No MCP servers section in Claude config")
                elif not isinstance(config_data["mcpServers"], dict):
                    issues.append("Invalid MCP servers section in Claude config")
                
            except json.JSONDecodeError as e:
                issues.append(f"Claude config file is not valid JSON: {e}")
                
        except Exception as e:
            warnings.append(f"Could not validate Claude config: {e}")
        
        # Check for Docker Desktop integration issues
        try:
            # Get enabled Docker servers
            enabled_docker_servers = self._get_enabled_docker_servers()
            
            if enabled_docker_servers:
                # Check if docker-gateway exists in Claude
                if not self.claude.server_exists("docker-gateway"):
                    warnings.append("Docker Desktop servers enabled but docker-gateway not configured in Claude")
                else:
                    # Validate docker-gateway configuration
                    gateway_server = self.claude.get_server("docker-gateway")
                    if gateway_server:
                        # Check if the gateway has the correct servers
                        gateway_servers = self._extract_servers_from_gateway_command(
                            " ".join([gateway_server.command] + gateway_server.args)
                        )
                        
                        missing_in_gateway = [s for s in enabled_docker_servers if s not in gateway_servers]
                        if missing_in_gateway:
                            warnings.append(f"Docker servers enabled but missing from gateway: {missing_in_gateway}")
                        
        except Exception as e:
            warnings.append(f"Could not validate Docker Desktop integration: {e}")
        
        # Check for problematic Docker commands
        if self._server_list_callback:
            try:
                servers = self._server_list_callback()
                for server in servers:
                    if server.server_type == ServerType.DOCKER and "docker run" in server.command:
                        if "--rm" not in server.args:
                            warnings.append(f"Docker server {server.name} missing --rm flag")
            except Exception as e:
                warnings.append(f"Could not validate Docker server configurations: {e}")
    
    def _parse_claude_server_list(self, claude_output: str) -> List[str]:
        """
        Parse Claude CLI output and expand docker-gateway into individual servers.
        
        Args:
            claude_output: Raw output from Claude CLI
            
        Returns:
            List of server names with docker-gateway expanded
        """
        servers = []
        
        for line in claude_output.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Handle different Claude output formats
            if '\t' in line:
                server_name = line.split('\t')[0]
            elif '  ' in line:
                server_name = line.split('  ')[0]
            else:
                server_name = line.split()[0] if line.split() else line
            
            if server_name == "docker-gateway":
                # Expand docker-gateway into individual servers
                expanded_servers = self._expand_docker_gateway_from_claude_output(line)
                servers.extend(expanded_servers)
            else:
                servers.append(server_name)
        
        return servers
    
    def _extract_servers_from_gateway_command(self, command_line: str) -> List[str]:
        """
        Extract server names from docker-gateway command line.
        
        Args:
            command_line: Full command line string
            
        Returns:
            List of server names
        """
        # Look for --servers argument
        match = re.search(r'--servers\s+([^\s]+)', command_line)
        if match:
            servers_arg = match.group(1)
            return [s.strip() for s in servers_arg.split(',') if s.strip()]
        
        return []
    
    def _expand_docker_gateway_from_claude_output(self, gateway_line: str) -> List[str]:
        """
        Expand docker-gateway from Claude output into individual server names.
        
        Args:
            gateway_line: Line from Claude output containing docker-gateway
            
        Returns:
            List of individual server names
        """
        try:
            # Try to extract from the command line in the output
            servers = self._extract_servers_from_gateway_command(gateway_line)
            if servers:
                return servers
            
            # Fallback: get enabled servers from Docker Desktop directly
            logger.debug("Could not parse gateway servers from Claude output, using Docker Desktop registry")
            return self._get_enabled_docker_servers()
            
        except Exception as e:
            logger.warning(f"Failed to expand docker-gateway from Claude output: {e}")
            return []
    
    def _get_enabled_docker_servers(self) -> List[str]:
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
    
    def _test_docker_gateway(self) -> Optional[Dict[str, Any]]:
        """
        Test Docker gateway functionality.
        
        Returns:
            Dictionary with test results or None if not available
        """
        try:
            if not self.claude.server_exists("docker-gateway"):
                return {
                    "available": False,
                    "error": "docker-gateway not configured"
                }
            
            # Get gateway server configuration
            gateway_server = self.claude.get_server("docker-gateway")
            if not gateway_server:
                return {
                    "available": False,
                    "error": "Could not retrieve docker-gateway configuration"
                }
            
            # Test with dry-run command
            try:
                cmd = [gateway_server.command] + gateway_server.args + ["--dry-run"]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                return {
                    "available": True,
                    "test_successful": result.returncode == 0,
                    "command": " ".join(cmd),
                    "output": result.stdout[:200],  # First 200 chars
                    "error": result.stderr[:200] if result.stderr else None
                }
                
            except subprocess.TimeoutExpired:
                return {
                    "available": True,
                    "test_successful": False,
                    "error": "Gateway test timed out"
                }
                
        except Exception as e:
            logger.error(f"Failed to test docker-gateway: {e}")
            return {
                "available": False,
                "error": str(e)
            }
    
    async def refresh_docker_gateway(self) -> bool:
        """
        Refresh docker-gateway by removing and re-adding it with updated servers.
        
        Returns:
            True if refresh was successful
        """
        try:
            logger.debug("Refreshing docker-gateway configuration")
            
            # Remove existing gateway if it exists - try all scopes
            if self.claude.server_exists("docker-gateway"):
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
        """
        Ensure docker-gateway is set up in Claude Code.
        
        Returns:
            True if setup was successful
        """
        try:
            # Check if docker-gateway already exists
            if self.claude.server_exists("docker-gateway"):
                logger.debug("docker-gateway already configured in Claude Code")
                return True
            
            # Try to automatically add docker-gateway
            logger.debug("Setting up docker-gateway for Docker Desktop integration")
            
            # Get the list of enabled Docker servers from registry
            enabled_servers = self._get_enabled_docker_servers()
            if not enabled_servers:
                logger.warning("No Docker Desktop servers enabled")
                return True  # Not an error, just nothing to sync
            
            # Build the docker-gateway command  
            servers_list = ",".join(enabled_servers)
            
            # Add docker-gateway to Claude Code with the current enabled servers
            server = Server(
                name="docker-gateway",
                command=self.claude.docker_path,
                args=["mcp", "gateway", "run", "--servers", servers_list],
                env={},
                server_type=ServerType.DOCKER_DESKTOP,
                scope=ServerScope.USER
            )
            
            success = self.claude.add_server(server)
            
            if success:
                logger.debug(f"Successfully set up docker-gateway with servers: {servers_list}")
                return True
            else:
                logger.error("Failed to add docker-gateway to Claude Code")
                return False
            
        except Exception as e:
            logger.error(f"Failed to set up docker-gateway: {e}")
            return False