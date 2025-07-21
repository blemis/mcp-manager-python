"""
Docker registry parser for monitoring Docker Desktop MCP server changes.

This module parses the ~/.docker/mcp/registry.yaml file to track changes
in Docker Desktop MCP server enable/disable states.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Set, Optional
from datetime import datetime

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class DockerServerState:
    """Represents the state of a Docker Desktop MCP server."""
    
    def __init__(self, name: str, enabled: bool, ref: str = ""):
        self.name = name
        self.enabled = enabled
        self.ref = ref  # Docker image reference
        self.last_seen = datetime.now()
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, DockerServerState):
            return False
        return self.name == other.name and self.enabled == other.enabled
    
    def __str__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"DockerServer({self.name}:{status})"


class DockerRegistryState:
    """Represents the complete state of the Docker MCP registry."""
    
    def __init__(self, servers: Dict[str, DockerServerState] = None):
        self.servers = servers or {}
        self.last_updated = datetime.now()
    
    def get_enabled_servers(self) -> Set[str]:
        """Get set of enabled server names."""
        return {name for name, server in self.servers.items() if server.enabled}
    
    def get_disabled_servers(self) -> Set[str]:
        """Get set of disabled server names."""
        return {name for name, server in self.servers.items() if not server.enabled}
    
    def get_all_servers(self) -> Set[str]:
        """Get set of all server names."""
        return set(self.servers.keys())
    
    def compare_with(self, other: 'DockerRegistryState') -> Dict[str, List[str]]:
        """Compare with another state and return differences."""
        if not isinstance(other, DockerRegistryState):
            raise ValueError("Can only compare with another DockerRegistryState")
        
        current_servers = self.get_all_servers()
        other_servers = other.get_all_servers()
        
        current_enabled = self.get_enabled_servers()
        other_enabled = other.get_enabled_servers()
        
        return {
            'added_servers': list(current_servers - other_servers),
            'removed_servers': list(other_servers - current_servers),
            'newly_enabled': list(current_enabled - other_enabled),
            'newly_disabled': list(other_enabled - current_enabled),
        }


class DockerRegistryParser:
    """Parser for Docker Desktop MCP registry files."""
    
    def __init__(self, registry_path: Optional[str] = None):
        if registry_path:
            self.registry_path = Path(registry_path)
        else:
            self.registry_path = Path.home() / '.docker' / 'mcp' / 'registry.yaml'
        
        self._last_state: Optional[DockerRegistryState] = None
        self._last_parsed: Optional[datetime] = None
    
    def parse_registry(self) -> Optional[DockerRegistryState]:
        """Parse the Docker registry file and return the current state."""
        try:
            if not self.registry_path.exists():
                logger.debug(f"Docker registry file not found: {self.registry_path}")
                return DockerRegistryState()  # Empty state
            
            with open(self.registry_path, 'r') as f:
                content = f.read().strip()
                
            if not content:
                logger.debug("Docker registry file is empty")
                return DockerRegistryState()  # Empty state
                
            registry_data = yaml.safe_load(content)
            
            if not registry_data or 'registry' not in registry_data:
                logger.debug("Invalid registry file format")
                return DockerRegistryState()  # Empty state
            
            servers = {}
            registry_section = registry_data['registry']
            
            if registry_section is None:
                # Empty registry section
                logger.debug("Registry section is empty")
                return DockerRegistryState()
            
            for server_name, server_config in registry_section.items():
                if server_config is None:
                    server_config = {}
                
                # If a server is in the registry, it's enabled
                # Disabled servers are removed from the registry
                server_state = DockerServerState(
                    name=server_name,
                    enabled=True,  # Present in registry means enabled
                    ref=server_config.get('ref', '')
                )
                servers[server_name] = server_state
            
            state = DockerRegistryState(servers)
            self._last_state = state
            self._last_parsed = datetime.now()
            
            logger.debug(f"Parsed Docker registry: {len(servers)} servers")
            return state
            
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML in Docker registry: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to parse Docker registry: {e}")
            return None
    
    def get_changes_since_last_parse(self) -> Optional[Dict[str, List[str]]]:
        """Get changes since the last parse."""
        if not self._last_state:
            return None
        
        current_state = self.parse_registry()
        if not current_state:
            return None
        
        return current_state.compare_with(self._last_state)
    
    def has_changed(self) -> bool:
        """Check if the registry has changed since last parse."""
        if not self.registry_path.exists():
            return self._last_state is not None and len(self._last_state.servers) > 0
        
        try:
            current_mtime = self.registry_path.stat().st_mtime
            
            if not self._last_parsed:
                return True
                
            last_parsed_timestamp = self._last_parsed.timestamp()
            return current_mtime > last_parsed_timestamp
            
        except Exception as e:
            logger.debug(f"Error checking registry file modification time: {e}")
            return True  # Assume changed if we can't determine
    
    def get_last_state(self) -> Optional[DockerRegistryState]:
        """Get the last parsed state."""
        return self._last_state
    
    def reset_state(self):
        """Reset the parser state."""
        self._last_state = None
        self._last_parsed = None


def parse_docker_registry(registry_path: Optional[str] = None) -> Optional[DockerRegistryState]:
    """Convenience function to parse Docker registry file."""
    parser = DockerRegistryParser(registry_path)
    return parser.parse_registry()


def get_enabled_docker_servers(registry_path: Optional[str] = None) -> Set[str]:
    """Get list of enabled Docker Desktop MCP servers."""
    state = parse_docker_registry(registry_path)
    if state:
        return state.get_enabled_servers()
    return set()