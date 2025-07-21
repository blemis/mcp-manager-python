"""
Change detection engine for external MCP configuration changes.

This module compares current external state (Docker registry, Claude configs)
against the internal MCP Manager catalog to detect changes made by external tools.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Set, Optional, Any, Tuple
from enum import Enum

from mcp_manager.core.parsers import DockerRegistryParser, ClaudeConfigParser
from mcp_manager.core.parsers.docker_parser import DockerRegistryState
from mcp_manager.core.parsers.claude_parser import ClaudeConfigState, ClaudeServerDefinition
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ChangeType(Enum):
    """Types of changes that can be detected."""
    SERVER_ADDED = "server_added"
    SERVER_REMOVED = "server_removed"
    SERVER_MODIFIED = "server_modified"
    SERVER_ENABLED = "server_enabled"
    SERVER_DISABLED = "server_disabled"


class ChangeSource(Enum):
    """Sources of changes."""
    DOCKER = "docker"
    CLAUDE_USER = "claude_user"
    CLAUDE_PROJECT = "claude_project"
    CLAUDE_INTERNAL = "claude_internal"
    UNKNOWN = "unknown"


class DetectedChange:
    """Represents a detected change in external configuration."""
    
    def __init__(
        self,
        change_type: ChangeType,
        source: ChangeSource,
        server_name: str,
        details: Dict[str, Any] = None,
        timestamp: datetime = None
    ):
        self.change_type = change_type
        self.source = source
        self.server_name = server_name
        self.details = details or {}
        self.timestamp = timestamp or datetime.now()
    
    def __str__(self) -> str:
        return f"Change({self.change_type.value}:{self.source.value}:{self.server_name})"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'change_type': self.change_type.value,
            'source': self.source.value,
            'server_name': self.server_name,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }


class ExternalState:
    """Represents the current state of external MCP configurations."""
    
    def __init__(self):
        self.docker_state: Optional[DockerRegistryState] = None
        self.claude_states: Dict[str, ClaudeConfigState] = {}
        self.last_updated = datetime.now()
    
    def get_all_external_servers(self) -> Dict[str, Dict[str, Any]]:
        """Get all servers from external sources with metadata."""
        servers = {}
        
        # Add Docker servers
        if self.docker_state:
            for server_name, server_state in self.docker_state.servers.items():
                servers[server_name] = {
                    'source': 'docker',
                    'enabled': server_state.enabled,
                    'type': 'docker-desktop',
                    'command': 'docker',
                    'args': ['mcp', 'server', server_name],
                    'ref': server_state.ref
                }
        
        # Add Claude servers (with scope precedence)
        claude_servers = {}
        
        # Internal scope (lowest precedence)
        for scope in ['internal', 'user', 'project']:
            if scope in self.claude_states:
                for server_name, server_def in self.claude_states[scope].servers.items():
                    claude_servers[server_name] = {
                        'source': f'claude_{scope}',
                        'enabled': True,  # If in Claude config, it's enabled
                        'type': 'custom',  # Will be refined based on command
                        'command': server_def.command,
                        'args': server_def.args,
                        'env': server_def.env,
                        'scope': scope
                    }
        
        servers.update(claude_servers)
        return servers


class ChangeDetector:
    """Detects changes in external MCP configurations."""
    
    def __init__(self, catalog_manager=None):
        self.catalog_manager = catalog_manager
        self.docker_parser = DockerRegistryParser()
        self.claude_parser = ClaudeConfigParser()
        
        self._last_external_state: Optional[ExternalState] = None
        self._detection_history: List[DetectedChange] = []
    
    async def detect_changes(self) -> List[DetectedChange]:
        """Detect all changes since last detection."""
        changes = []
        
        try:
            # Get current external state
            current_state = await self._get_current_external_state()
            
            # Get catalog state
            catalog_servers = await self._get_catalog_servers()
            
            # Compare with last state and catalog
            if self._last_external_state:
                external_changes = self._compare_external_states(
                    current_state, self._last_external_state
                )
                changes.extend(external_changes)
            
            # Compare external state with catalog
            catalog_sync_changes = self._compare_with_catalog(current_state, catalog_servers)
            changes.extend(catalog_sync_changes)
            
            # Update last state
            self._last_external_state = current_state
            
            # Store in history
            self._detection_history.extend(changes)
            
            if changes:
                logger.info(f"Detected {len(changes)} configuration changes")
                for change in changes:
                    logger.debug(f"  {change}")
            
            return changes
            
        except Exception as e:
            logger.error(f"Error detecting changes: {e}")
            return []
    
    async def _get_current_external_state(self) -> ExternalState:
        """Get the current state of all external configurations."""
        state = ExternalState()
        
        # Parse Docker registry
        try:
            state.docker_state = self.docker_parser.parse_registry()
        except Exception as e:
            logger.warning(f"Failed to parse Docker registry: {e}")
        
        # Parse Claude configurations
        try:
            state.claude_states = self.claude_parser.parse_all_configs()
        except Exception as e:
            logger.warning(f"Failed to parse Claude configurations: {e}")
        
        return state
    
    async def _get_catalog_servers(self) -> Dict[str, Dict[str, Any]]:
        """Get servers from the MCP Manager catalog."""
        if not self.catalog_manager:
            return {}
        
        try:
            catalog = await self.catalog_manager._get_server_catalog()
            return catalog.get('servers', {})
        except Exception as e:
            logger.warning(f"Failed to get catalog servers: {e}")
            return {}
    
    def _compare_external_states(
        self, current: ExternalState, previous: ExternalState
    ) -> List[DetectedChange]:
        """Compare two external states to find changes."""
        changes = []
        
        # Compare Docker states
        if current.docker_state and previous.docker_state:
            docker_changes = current.docker_state.compare_with(previous.docker_state)
            
            for server_name in docker_changes['newly_enabled']:
                changes.append(DetectedChange(
                    change_type=ChangeType.SERVER_ENABLED,
                    source=ChangeSource.DOCKER,
                    server_name=server_name,
                    details={'previous_state': 'disabled', 'current_state': 'enabled'}
                ))
            
            for server_name in docker_changes['newly_disabled']:
                changes.append(DetectedChange(
                    change_type=ChangeType.SERVER_DISABLED,
                    source=ChangeSource.DOCKER,
                    server_name=server_name,
                    details={'previous_state': 'enabled', 'current_state': 'disabled'}
                ))
        
        # Compare Claude states
        for scope in ['user', 'project', 'internal']:
            current_claude = current.claude_states.get(scope)
            previous_claude = previous.claude_states.get(scope)
            
            if current_claude and previous_claude:
                claude_changes = current_claude.compare_with(previous_claude)
                source = ChangeSource.CLAUDE_USER if scope == 'user' else \
                        ChangeSource.CLAUDE_PROJECT if scope == 'project' else \
                        ChangeSource.CLAUDE_INTERNAL
                
                for server_name in claude_changes['added_servers']:
                    server_def = current_claude.servers[server_name]
                    changes.append(DetectedChange(
                        change_type=ChangeType.SERVER_ADDED,
                        source=source,
                        server_name=server_name,
                        details={
                            'command': server_def.command,
                            'args': server_def.args,
                            'env': server_def.env
                        }
                    ))
                
                for server_name in claude_changes['removed_servers']:
                    changes.append(DetectedChange(
                        change_type=ChangeType.SERVER_REMOVED,
                        source=source,
                        server_name=server_name
                    ))
                
                for server_name in claude_changes['modified_servers']:
                    current_def = current_claude.servers[server_name]
                    previous_def = previous_claude.servers[server_name]
                    changes.append(DetectedChange(
                        change_type=ChangeType.SERVER_MODIFIED,
                        source=source,
                        server_name=server_name,
                        details={
                            'previous': {
                                'command': previous_def.command,
                                'args': previous_def.args,
                                'env': previous_def.env
                            },
                            'current': {
                                'command': current_def.command,
                                'args': current_def.args,
                                'env': current_def.env
                            }
                        }
                    ))
        
        return changes
    
    def _compare_with_catalog(
        self, external_state: ExternalState, catalog_servers: Dict[str, Dict[str, Any]]
    ) -> List[DetectedChange]:
        """Compare external state with catalog to find sync issues."""
        changes = []
        
        external_servers = external_state.get_all_external_servers()
        catalog_server_names = set(catalog_servers.keys())
        external_server_names = set(external_servers.keys())
        
        # Find servers that exist externally but not in catalog
        new_external_servers = external_server_names - catalog_server_names
        
        for server_name in new_external_servers:
            server_info = external_servers[server_name]
            source_mapping = {
                'docker': ChangeSource.DOCKER,
                'claude_user': ChangeSource.CLAUDE_USER,
                'claude_project': ChangeSource.CLAUDE_PROJECT,
                'claude_internal': ChangeSource.CLAUDE_INTERNAL
            }
            
            source = source_mapping.get(server_info['source'], ChangeSource.UNKNOWN)
            
            changes.append(DetectedChange(
                change_type=ChangeType.SERVER_ADDED,
                source=source,
                server_name=server_name,
                details={
                    'reason': 'external_server_not_in_catalog',
                    'server_info': server_info
                }
            ))
        
        # Find servers that exist in catalog but not externally
        removed_servers = catalog_server_names - external_server_names
        
        for server_name in removed_servers:
            catalog_info = catalog_servers[server_name]
            # Determine likely source based on server type
            server_type = catalog_info.get('type', 'unknown')
            
            if server_type == 'docker-desktop':
                source = ChangeSource.DOCKER
            else:
                source = ChangeSource.UNKNOWN
            
            changes.append(DetectedChange(
                change_type=ChangeType.SERVER_REMOVED,
                source=source,
                server_name=server_name,
                details={
                    'reason': 'catalog_server_not_external',
                    'catalog_info': catalog_info
                }
            ))
        
        # Find servers with state mismatches
        common_servers = catalog_server_names & external_server_names
        
        for server_name in common_servers:
            catalog_info = catalog_servers[server_name]
            external_info = external_servers[server_name]
            
            catalog_enabled = catalog_info.get('enabled', True)
            external_enabled = external_info.get('enabled', True)
            
            if catalog_enabled != external_enabled:
                source_mapping = {
                    'docker': ChangeSource.DOCKER,
                    'claude_user': ChangeSource.CLAUDE_USER,
                    'claude_project': ChangeSource.CLAUDE_PROJECT,
                    'claude_internal': ChangeSource.CLAUDE_INTERNAL
                }
                source = source_mapping.get(external_info['source'], ChangeSource.UNKNOWN)
                
                change_type = ChangeType.SERVER_ENABLED if external_enabled else ChangeType.SERVER_DISABLED
                
                changes.append(DetectedChange(
                    change_type=change_type,
                    source=source,
                    server_name=server_name,
                    details={
                        'reason': 'state_mismatch',
                        'catalog_enabled': catalog_enabled,
                        'external_enabled': external_enabled
                    }
                ))
        
        return changes
    
    def get_detection_history(self, limit: Optional[int] = None) -> List[DetectedChange]:
        """Get the history of detected changes."""
        if limit:
            return self._detection_history[-limit:]
        return self._detection_history.copy()
    
    def clear_history(self):
        """Clear the detection history."""
        self._detection_history.clear()
    
    def reset_state(self):
        """Reset the detector state."""
        self._last_external_state = None
        self.clear_history()


async def detect_external_changes(catalog_manager=None) -> List[DetectedChange]:
    """Convenience function to detect external configuration changes."""
    detector = ChangeDetector(catalog_manager)
    return await detector.detect_changes()