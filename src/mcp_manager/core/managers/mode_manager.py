"""
Mode Manager for proxy/direct mode switching operations.

Handles switching between proxy mode (docker-gateway) and direct mode,
mode validation, and configuration management.
"""

import os
import re
import subprocess
from typing import List, Optional, Dict, Any, Callable
from enum import Enum

from mcp_manager.core.claude_interface import ClaudeInterface
from mcp_manager.core.models import Server, ServerType, ServerScope
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class OperationMode(Enum):
    """MCP Manager operation modes."""
    DIRECT = "direct"
    PROXY = "proxy"
    HYBRID = "hybrid"


class ModeManager:
    """Manages operation modes and proxy/direct mode switching."""
    
    def __init__(self, claude_interface: Optional[ClaudeInterface] = None):
        """Initialize mode manager.
        
        Args:
            claude_interface: Optional Claude interface (will create if not provided)
        """
        self.claude = claude_interface or ClaudeInterface()
        
        # Configuration from environment
        self.default_mode = OperationMode(os.getenv("MCP_OPERATION_MODE", "hybrid"))
        self.proxy_enabled = os.getenv("MCP_PROXY_ENABLED", "true").lower() == "true"
        
        logger.debug(f"ModeManager initialized - Default mode: {self.default_mode.value}")
    
    def get_current_mode(self) -> OperationMode:
        """
        Detect current operation mode based on configuration.
        
        Returns:
            Current operation mode
        """
        try:
            # Check if docker-gateway exists in Claude
            has_docker_gateway = self.claude.server_exists("docker-gateway")
            
            # Check if there are enabled Docker Desktop servers
            enabled_docker_servers = self.get_enabled_docker_servers()
            has_docker_servers = len(enabled_docker_servers) > 0
            
            if has_docker_gateway and has_docker_servers:
                return OperationMode.PROXY
            elif has_docker_servers and not has_docker_gateway:
                return OperationMode.DIRECT
            elif has_docker_gateway or has_docker_servers:
                return OperationMode.HYBRID
            else:
                return OperationMode.DIRECT
                
        except Exception as e:
            logger.warning(f"Failed to detect current mode: {e}")
            return self.default_mode
    
    def switch_to_proxy_mode(self) -> bool:
        """
        Switch to proxy mode using docker-gateway.
        
        Returns:
            True if switch was successful
        """
        try:
            logger.info("Switching to proxy mode")
            
            # Get enabled Docker servers
            enabled_servers = self.get_enabled_docker_servers()
            if not enabled_servers:
                logger.warning("No Docker Desktop servers enabled - nothing to configure for proxy mode")
                return True
            
            # Set up docker-gateway
            success = self.setup_docker_gateway()
            
            if success:
                logger.info("Successfully switched to proxy mode")
            else:
                logger.error("Failed to switch to proxy mode")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to switch to proxy mode: {e}")
            return False
    
    def switch_to_direct_mode(self) -> bool:
        """
        Switch to direct mode by removing docker-gateway.
        
        Returns:
            True if switch was successful
        """
        try:
            logger.info("Switching to direct mode")
            
            # Remove docker-gateway if it exists
            if self.claude.server_exists("docker-gateway"):
                success = self.remove_docker_gateway()
                
                if success:
                    logger.info("Successfully switched to direct mode")
                else:
                    logger.error("Failed to remove docker-gateway")
                
                return success
            else:
                logger.info("Already in direct mode (no docker-gateway)")
                return True
                
        except Exception as e:
            logger.error(f"Failed to switch to direct mode: {e}")
            return False
    
    def setup_docker_gateway(self) -> bool:
        """
        Set up docker-gateway for proxy mode.
        
        Returns:
            True if setup was successful
        """
        try:
            # Check if docker-gateway already exists
            if self.claude.server_exists("docker-gateway"):
                logger.debug("docker-gateway already configured")
                # Refresh it to ensure it has current servers
                return self.refresh_docker_gateway()
            
            logger.debug("Setting up docker-gateway for Docker Desktop integration")
            
            # Get the list of enabled Docker servers
            enabled_servers = self.get_enabled_docker_servers()
            if not enabled_servers:
                logger.warning("No Docker Desktop servers enabled")
                return True  # Not an error, just nothing to set up
            
            # Build the docker-gateway command
            servers_list = ",".join(enabled_servers)
            
            # Create docker-gateway server
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
                logger.info(f"Successfully set up docker-gateway with servers: {servers_list}")
            else:
                logger.error("Failed to add docker-gateway to Claude Code")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to set up docker-gateway: {e}")
            return False
    
    def remove_docker_gateway(self) -> bool:
        """
        Remove docker-gateway configuration.
        
        Returns:
            True if removal was successful
        """
        try:
            logger.debug("Removing docker-gateway configuration")
            
            # Try removing from all scopes
            removed = False
            for scope in [ServerScope.USER, ServerScope.PROJECT]:
                try:
                    success = self.claude.remove_server("docker-gateway", scope)
                    if success:
                        logger.debug(f"Removed docker-gateway from {scope.value} scope")
                        removed = True
                        break
                except Exception as e:
                    logger.debug(f"Could not remove docker-gateway from {scope.value} scope: {e}")
                    continue
            
            if not removed:
                logger.warning("Could not remove docker-gateway from any scope")
            
            return removed
            
        except Exception as e:
            logger.error(f"Failed to remove docker-gateway: {e}")
            return False
    
    def refresh_docker_gateway(self) -> bool:
        """
        Refresh docker-gateway by removing and re-adding with updated servers.
        
        Returns:
            True if refresh was successful
        """
        try:
            logger.debug("Refreshing docker-gateway configuration")
            
            # Remove existing gateway
            self.remove_docker_gateway()
            
            # Re-add with current server list
            return self.setup_docker_gateway()
            
        except Exception as e:
            logger.error(f"Failed to refresh docker-gateway: {e}")
            return False
    
    def get_enabled_docker_servers(self) -> List[str]:
        """
        Get list of enabled Docker Desktop MCP servers.
        
        Returns:
            List of enabled server names
        """
        try:
            import yaml
            from pathlib import Path
            
            registry_path = Path.home() / ".docker" / "mcp" / "registry.yaml"
            if not registry_path.exists():
                return []
            
            with open(registry_path) as f:
                registry_data = yaml.safe_load(f)
            
            enabled_servers = list(registry_data.get("registry", {}).keys())
            logger.debug(f"Found {len(enabled_servers)} enabled Docker Desktop servers")
            return enabled_servers
            
        except Exception as e:
            logger.warning(f"Failed to get enabled Docker servers: {e}")
            return []
    
    def expand_docker_gateway(self, gateway_server: Server) -> List[Server]:
        """
        Expand docker-gateway into individual Docker Desktop server objects.
        
        Args:
            gateway_server: The docker-gateway server object
            
        Returns:
            List of individual server objects
        """
        servers = []
        
        try:
            # Extract server names from gateway command
            gateway_command = " ".join([gateway_server.command] + gateway_server.args)
            server_names = self.extract_servers_from_gateway_command(gateway_command)
            
            # Create individual server objects
            for server_name in server_names:
                server = Server(
                    name=f"docker-desktop-{server_name}",
                    command="docker",
                    args=["mcp", "server", "run", server_name],
                    env={},
                    server_type=ServerType.DOCKER_DESKTOP,
                    scope=ServerScope.USER,
                    enabled=True  # Assume enabled if in gateway
                )
                servers.append(server)
            
            logger.debug(f"Expanded docker-gateway into {len(servers)} individual servers")
            
        except Exception as e:
            logger.error(f"Failed to expand docker-gateway: {e}")
        
        return servers
    
    def extract_servers_from_gateway_command(self, command_line: str) -> List[str]:
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
    
    def test_docker_gateway(self) -> Dict[str, Any]:
        """
        Test Docker gateway functionality.
        
        Returns:
            Dictionary with test results
        """
        try:
            if not self.claude.server_exists("docker-gateway"):
                return {
                    "available": False,
                    "error": "docker-gateway not configured",
                    "mode": "direct"
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
                
                # Get server list from command
                server_names = self.extract_servers_from_gateway_command(" ".join(cmd))
                
                return {
                    "available": True,
                    "test_successful": result.returncode == 0,
                    "mode": "proxy",
                    "servers": server_names,
                    "command": " ".join(cmd[:3] + ["..."]),  # Truncate for security
                    "output": result.stdout[:200] if result.stdout else None,
                    "error": result.stderr[:200] if result.stderr else None
                }
                
            except subprocess.TimeoutExpired:
                return {
                    "available": True,
                    "test_successful": False,
                    "mode": "proxy",
                    "error": "Gateway test timed out"
                }
                
        except Exception as e:
            logger.error(f"Failed to test docker-gateway: {e}")
            return {
                "available": False,
                "error": str(e)
            }
    
    def validate_mode_consistency(self) -> Dict[str, Any]:
        """
        Validate consistency between detected mode and configuration.
        
        Returns:
            Dictionary with validation results
        """
        try:
            current_mode = self.get_current_mode()
            enabled_servers = self.get_enabled_docker_servers()
            has_docker_gateway = self.claude.server_exists("docker-gateway")
            
            issues = []
            warnings = []
            
            # Check for inconsistencies
            if enabled_servers and not has_docker_gateway and current_mode == OperationMode.PROXY:
                issues.append("Docker servers enabled but no docker-gateway configured")
            
            if has_docker_gateway and not enabled_servers:
                warnings.append("docker-gateway configured but no Docker servers enabled")
            
            if has_docker_gateway and enabled_servers:
                # Validate gateway configuration
                gateway_server = self.claude.get_server("docker-gateway")
                if gateway_server:
                    gateway_servers = self.extract_servers_from_gateway_command(
                        " ".join([gateway_server.command] + gateway_server.args)
                    )
                    
                    missing_in_gateway = [s for s in enabled_servers if s not in gateway_servers]
                    extra_in_gateway = [s for s in gateway_servers if s not in enabled_servers]
                    
                    if missing_in_gateway:
                        issues.append(f"Servers enabled but missing from gateway: {missing_in_gateway}")
                    
                    if extra_in_gateway:
                        warnings.append(f"Extra servers in gateway: {extra_in_gateway}")
            
            return {
                "current_mode": current_mode.value,
                "enabled_docker_servers": len(enabled_servers),
                "has_docker_gateway": has_docker_gateway,
                "consistent": len(issues) == 0,
                "issues": issues,
                "warnings": warnings
            }
            
        except Exception as e:
            logger.error(f"Failed to validate mode consistency: {e}")
            return {
                "current_mode": "unknown",
                "consistent": False,
                "error": str(e)
            }
    
    def get_mode_status(self) -> Dict[str, Any]:
        """
        Get comprehensive mode status information.
        
        Returns:
            Dictionary with mode status details
        """
        try:
            current_mode = self.get_current_mode()
            enabled_servers = self.get_enabled_docker_servers()
            gateway_test = self.test_docker_gateway()
            validation = self.validate_mode_consistency()
            
            return {
                "current_mode": current_mode.value,
                "default_mode": self.default_mode.value,
                "proxy_enabled": self.proxy_enabled,
                "docker_servers_count": len(enabled_servers),
                "docker_servers": enabled_servers,
                "docker_gateway": gateway_test,
                "validation": validation,
                "recommendations": self._generate_mode_recommendations(current_mode, enabled_servers, validation)
            }
            
        except Exception as e:
            logger.error(f"Failed to get mode status: {e}")
            return {
                "current_mode": "unknown",
                "error": str(e)
            }
    
    def _generate_mode_recommendations(self, current_mode: OperationMode, 
                                     enabled_servers: List[str], 
                                     validation: Dict[str, Any]) -> List[str]:
        """
        Generate mode recommendations based on current state.
        
        Args:
            current_mode: Current operation mode
            enabled_servers: List of enabled Docker servers
            validation: Validation results
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        if not validation.get("consistent", True):
            recommendations.append("Fix mode inconsistencies for optimal performance")
        
        if len(enabled_servers) > 1 and current_mode != OperationMode.PROXY:
            recommendations.append("Consider using proxy mode for multiple Docker servers")
        
        if len(enabled_servers) <= 1 and current_mode == OperationMode.PROXY:
            recommendations.append("Direct mode may be more efficient for single Docker server")
        
        if not enabled_servers and current_mode == OperationMode.PROXY:
            recommendations.append("Switch to direct mode if not using Docker Desktop servers")
        
        return recommendations