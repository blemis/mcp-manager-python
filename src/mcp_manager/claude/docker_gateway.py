"""
Docker gateway expansion for Claude interface.

This module handles the expansion of docker-gateway configurations into
individual Docker Desktop servers and manages Docker Desktop MCP integration.
"""

from typing import Dict, List

from mcp_manager.core.models import Server, ServerType, ServerScope
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class DockerGatewayExpander:
    """Handles expansion of docker-gateway configurations."""
    
    def __init__(self):
        """Initialize Docker gateway expander."""
        logger.debug("DockerGatewayExpander initialized")
    
    def expand_docker_gateway_from_config(self, gateway_config: Dict) -> List[Server]:
        """
        Expand docker-gateway configuration into individual Docker Desktop servers.
        
        Args:
            gateway_config: Docker gateway configuration dict
            
        Returns:
            List of individual Docker Desktop servers
        """
        servers = []
        
        try:
            command = gateway_config.get("command", "")
            args = gateway_config.get("args", [])
            
            # Look for --servers argument in command or args
            servers_list = self._extract_servers_list(command, args)
            
            if servers_list:
                for server_name in servers_list:
                    server_name = server_name.strip()
                    if server_name:
                        server = Server(
                            name=server_name,
                            command="docker",
                            args=["mcp", "gateway", "run", "--servers", server_name],
                            env=gateway_config.get("env", {}),
                            server_type=ServerType.DOCKER_DESKTOP,
                            scope=ServerScope.USER,
                            description=f"Docker Desktop MCP server: {server_name}"
                        )
                        servers.append(server)
                        
                logger.debug(f"Expanded docker-gateway into {len(servers)} servers")
            else:
                logger.warning("No servers found in docker-gateway configuration")
            
        except Exception as e:
            logger.warning(f"Failed to expand docker-gateway: {e}")
        
        return servers
    
    def _extract_servers_list(self, command: str, args: List[str]) -> List[str]:
        """
        Extract server list from command or args.
        
        Args:
            command: Command string
            args: Arguments list
            
        Returns:
            List of server names
        """
        servers_list = None
        
        # Check if servers are in the command string
        if "--servers" in command:
            parts = command.split("--servers")
            if len(parts) > 1:
                servers_part = parts[1].strip().split()[0]
                servers_list = servers_part.split(",")
        
        # Check if servers are in args list
        elif args and "--servers" in args:
            try:
                servers_idx = args.index("--servers")
                if servers_idx + 1 < len(args):
                    servers_list = args[servers_idx + 1].split(",")
            except (ValueError, IndexError):
                logger.warning("Invalid --servers argument format in args")
        
        return servers_list or []
    
    def create_docker_gateway_config(self, server_names: List[str]) -> Dict:
        """
        Create a docker-gateway configuration for multiple servers.
        
        Args:
            server_names: List of Docker Desktop server names
            
        Returns:
            Docker gateway configuration dict
        """
        if not server_names:
            raise ValueError("Server names list cannot be empty")
        
        servers_arg = ",".join(server_names)
        
        config = {
            "command": "docker",
            "args": ["mcp", "gateway", "run", "--servers", servers_arg],
            "env": {},
            "description": f"Docker gateway for servers: {', '.join(server_names)}"
        }
        
        logger.debug(f"Created docker-gateway config for {len(server_names)} servers")
        return config
    
    def get_available_docker_desktop_servers(self) -> List[str]:
        """
        Get list of available Docker Desktop MCP servers.
        
        Returns:
            List of available server names
        """
        # These are the known Docker Desktop MCP servers
        # In a real implementation, this might query Docker Desktop
        known_servers = [
            "sqlite",
            "filesystem", 
            "search",
            "http",
            "k8s",
            "terraform",
            "aws"
        ]
        
        logger.debug(f"Available Docker Desktop servers: {known_servers}")
        return known_servers
    
    def validate_docker_desktop_server(self, server_name: str) -> bool:
        """
        Validate if a server name is a valid Docker Desktop MCP server.
        
        Args:
            server_name: Server name to validate
            
        Returns:
            True if valid Docker Desktop server
        """
        available_servers = self.get_available_docker_desktop_servers()
        is_valid = server_name in available_servers
        
        if not is_valid:
            logger.warning(f"Invalid Docker Desktop server: {server_name}")
        
        return is_valid
    
    def merge_docker_gateway_configs(self, configs: List[Dict]) -> Dict:
        """
        Merge multiple docker-gateway configurations into one.
        
        Args:
            configs: List of docker-gateway configurations
            
        Returns:
            Merged configuration
        """
        if not configs:
            return {}
        
        if len(configs) == 1:
            return configs[0]
        
        # Extract all server names from all configs
        all_servers = []
        merged_env = {}
        
        for config in configs:
            servers_list = self._extract_servers_list(
                config.get("command", ""),
                config.get("args", [])
            )
            all_servers.extend(servers_list)
            
            # Merge environment variables
            env = config.get("env", {})
            merged_env.update(env)
        
        # Remove duplicates while preserving order
        unique_servers = []
        seen = set()
        for server in all_servers:
            if server not in seen:
                unique_servers.append(server)
                seen.add(server)
        
        # Create merged configuration
        merged_config = self.create_docker_gateway_config(unique_servers)
        merged_config["env"] = merged_env
        
        logger.debug(f"Merged {len(configs)} docker-gateway configs into one with {len(unique_servers)} servers")
        return merged_config