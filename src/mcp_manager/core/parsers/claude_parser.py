"""
Claude configuration parser for monitoring Claude MCP server changes.

This module parses Claude configuration files across all scopes (user, project, internal)
to track changes in MCP server definitions made by external `claude mcp` commands.
"""

import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from datetime import datetime

from mcp_manager.core.models import Server, ServerType, ServerScope
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ClaudeServerDefinition:
    """Represents a Claude MCP server definition."""
    
    def __init__(
        self,
        name: str,
        command: str,
        args: List[str] = None,
        env: Dict[str, str] = None,
        scope: str = 'user'
    ):
        self.name = name
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.scope = scope
        self.last_seen = datetime.now()
    
    def to_server(self) -> Server:
        """Convert to MCP Manager Server object."""
        # Determine server type based on command
        if self.command == 'docker':
            server_type = ServerType.DOCKER_DESKTOP
        elif self.command == 'npx':
            server_type = ServerType.NPM
        elif 'docker' in self.command:
            server_type = ServerType.DOCKER
        else:
            server_type = ServerType.CUSTOM
        
        # Determine scope
        scope_mapping = {
            'user': ServerScope.USER,
            'project': ServerScope.PROJECT,
            'local': ServerScope.LOCAL
        }
        server_scope = scope_mapping.get(self.scope, ServerScope.USER)
        
        return Server(
            name=self.name,
            command=self.command,
            args=self.args,
            env=self.env,
            server_type=server_type,
            scope=server_scope,
            enabled=True,  # If it's in Claude config, it's enabled
            description=f"Claude MCP server: {self.name}"
        )
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, ClaudeServerDefinition):
            return False
        return (
            self.name == other.name and
            self.command == other.command and
            self.args == other.args and
            self.env == other.env
        )
    
    def __str__(self) -> str:
        return f"ClaudeServer({self.name}:{self.command})"


class ClaudeConfigState:
    """Represents the complete state of Claude MCP configurations."""
    
    def __init__(self, servers: Dict[str, ClaudeServerDefinition] = None, scope: str = 'user'):
        self.servers = servers or {}
        self.scope = scope
        self.last_updated = datetime.now()
    
    def get_server_names(self) -> Set[str]:
        """Get set of all server names."""
        return set(self.servers.keys())
    
    def compare_with(self, other: 'ClaudeConfigState') -> Dict[str, List[str]]:
        """Compare with another state and return differences."""
        if not isinstance(other, ClaudeConfigState):
            raise ValueError("Can only compare with another ClaudeConfigState")
        
        current_servers = self.get_server_names()
        other_servers = other.get_server_names()
        
        added = current_servers - other_servers
        removed = other_servers - current_servers
        modified = []
        
        # Check for modifications in common servers
        common_servers = current_servers & other_servers
        for server_name in common_servers:
            if self.servers[server_name] != other.servers[server_name]:
                modified.append(server_name)
        
        return {
            'added_servers': list(added),
            'removed_servers': list(removed),
            'modified_servers': modified,
        }


class ClaudeConfigParser:
    """Parser for Claude MCP configuration files."""
    
    def __init__(self):
        self._config_paths = self._get_config_paths()
        self._last_states: Dict[str, ClaudeConfigState] = {}
        self._last_parsed: Dict[str, datetime] = {}
    
    def _get_config_paths(self) -> Dict[str, str]:
        """Get Claude configuration file paths by scope."""
        home_dir = Path.home()
        
        return {
            'user': str(home_dir / '.config' / 'claude-code' / 'mcp-servers.json'),
            'internal': str(home_dir / '.claude.json'),
            'project': './.mcp.json',  # Relative to current directory
        }
    
    def parse_config(self, scope: str = 'user') -> Optional[ClaudeConfigState]:
        """Parse a Claude configuration file for the given scope."""
        if scope not in self._config_paths:
            logger.error(f"Invalid scope: {scope}")
            return None
        
        config_path = Path(self._config_paths[scope])
        
        try:
            if not config_path.exists():
                logger.debug(f"Claude config file not found: {config_path}")
                return ClaudeConfigState(scope=scope)  # Empty state
            
            with open(config_path, 'r') as f:
                content = f.read().strip()
                
            if not content:
                logger.debug(f"Claude config file is empty: {config_path}")
                return ClaudeConfigState(scope=scope)  # Empty state
            
            config_data = json.loads(content)
            
            servers = {}
            
            if scope == 'internal':
                # Internal config has different structure: { "mcpServers": { ... } }
                mcp_servers = config_data.get('mcpServers', {})
            else:
                # User and project configs: { "mcpServers": { ... } }
                mcp_servers = config_data.get('mcpServers', {})
            
            for server_name, server_config in mcp_servers.items():
                if not isinstance(server_config, dict):
                    continue
                
                command = server_config.get('command', '')
                args = server_config.get('args', [])
                env = server_config.get('env', {})
                
                server_def = ClaudeServerDefinition(
                    name=server_name,
                    command=command,
                    args=args,
                    env=env,
                    scope=scope
                )
                servers[server_name] = server_def
            
            state = ClaudeConfigState(servers, scope)
            self._last_states[scope] = state
            self._last_parsed[scope] = datetime.now()
            
            logger.debug(f"Parsed Claude {scope} config: {len(servers)} servers")
            return state
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON in Claude config {config_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to parse Claude config {config_path}: {e}")
            return None
    
    def parse_all_configs(self) -> Dict[str, ClaudeConfigState]:
        """Parse all Claude configuration files."""
        results = {}
        
        for scope in self._config_paths.keys():
            state = self.parse_config(scope)
            if state is not None:
                results[scope] = state
        
        return results
    
    def get_changes_since_last_parse(self, scope: str = 'user') -> Optional[Dict[str, List[str]]]:
        """Get changes since the last parse for a specific scope."""
        if scope not in self._last_states:
            return None
        
        current_state = self.parse_config(scope)
        if not current_state:
            return None
        
        return current_state.compare_with(self._last_states[scope])
    
    def has_changed(self, scope: str = 'user') -> bool:
        """Check if the config has changed since last parse."""
        config_path = Path(self._config_paths[scope])
        
        if not config_path.exists():
            # File doesn't exist - has it been deleted?
            return scope in self._last_states and len(self._last_states[scope].servers) > 0
        
        try:
            current_mtime = config_path.stat().st_mtime
            
            if scope not in self._last_parsed:
                return True
            
            last_parsed_timestamp = self._last_parsed[scope].timestamp()
            return current_mtime > last_parsed_timestamp
            
        except Exception as e:
            logger.debug(f"Error checking config file modification time: {e}")
            return True  # Assume changed if we can't determine
    
    def get_all_servers(self) -> List[ClaudeServerDefinition]:
        """Get all servers from all scopes, with proper precedence."""
        all_configs = self.parse_all_configs()
        
        # Collect servers with scope precedence: project > user > internal
        servers_by_name = {}
        
        # Start with internal (lowest precedence)
        if 'internal' in all_configs:
            for server_name, server_def in all_configs['internal'].servers.items():
                servers_by_name[server_name] = server_def
        
        # Override with user scope
        if 'user' in all_configs:
            for server_name, server_def in all_configs['user'].servers.items():
                servers_by_name[server_name] = server_def
        
        # Override with project scope (highest precedence)  
        if 'project' in all_configs:
            for server_name, server_def in all_configs['project'].servers.items():
                servers_by_name[server_name] = server_def
        
        return list(servers_by_name.values())
    
    def find_project_configs(self, start_path: str = '.') -> List[str]:
        """Find all .mcp.json files in current and parent directories."""
        project_configs = []
        current_path = Path(start_path).resolve()
        home_path = Path.home()
        
        while current_path != home_path and current_path != current_path.parent:
            mcp_config = current_path / '.mcp.json'
            if mcp_config.exists():
                project_configs.append(str(mcp_config))
            current_path = current_path.parent
        
        return project_configs
    
    def get_last_state(self, scope: str = 'user') -> Optional[ClaudeConfigState]:
        """Get the last parsed state for a scope."""
        return self._last_states.get(scope)
    
    def reset_state(self, scope: Optional[str] = None):
        """Reset parser state for a specific scope or all scopes."""
        if scope:
            self._last_states.pop(scope, None)
            self._last_parsed.pop(scope, None)
        else:
            self._last_states.clear()
            self._last_parsed.clear()


def parse_claude_config(scope: str = 'user') -> Optional[ClaudeConfigState]:
    """Convenience function to parse a Claude configuration file."""
    parser = ClaudeConfigParser()
    return parser.parse_config(scope)


def get_all_claude_servers() -> List[ClaudeServerDefinition]:
    """Get all Claude MCP servers across all scopes."""
    parser = ClaudeConfigParser()
    return parser.get_all_servers()