"""
Main hybrid server state management system.
"""

import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from mcp_manager.core.claude_interface import ClaudeInterface
from mcp_manager.core.models import Server
from mcp_manager.utils.logging import get_logger

from .database import StateDatabase
from .models import (
    ServerState, ServerStatus, ServerAnalytics, ConfigDrift, 
    UsageEvent, ConnectionStatus
)

logger = get_logger(__name__)


class RuntimeCache:
    """In-memory cache for session data."""
    
    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, float] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        if key not in self._cache:
            return None
        
        if time.time() - self._timestamps[key] > self.ttl_seconds:
            del self._cache[key]
            del self._timestamps[key]
            return None
        
        return self._cache[key]
    
    def set(self, key: str, value: Any):
        """Set cached value with timestamp."""
        self._cache[key] = value
        self._timestamps[key] = time.time()
    
    def clear(self):
        """Clear all cached data."""
        self._cache.clear()
        self._timestamps.clear()


class LiveStatusChecker:
    """Interface for checking live server status via claude mcp list."""
    
    def __init__(self):
        self.claude = ClaudeInterface()
    
    async def get_all_status(self) -> List[ServerStatus]:
        """Get live status for all servers."""
        try:
            # This would call claude mcp list and parse output
            # For now, using the existing claude interface
            servers = self.claude.list_servers()
            
            # Convert to ServerStatus objects
            status_list = []
            for server in servers:
                # Determine status based on server.enabled and other factors
                if server.enabled:
                    status = ConnectionStatus.CONNECTED
                else:
                    status = ConnectionStatus.FAILED
                
                server_status = ServerStatus(
                    server_name=server.name,
                    status=status,
                    response_time_ms=None,  # Would be populated by actual health check
                    error_message=None if server.enabled else "Server disabled",
                    tool_count=None,  # Would be populated by actual tool query
                    checked_at=datetime.now()
                )
                status_list.append(server_status)
            
            return status_list
            
        except Exception as e:
            logger.error(f"Failed to get live status: {e}")
            return []
    
    async def get_server_status(self, server_name: str) -> Optional[ServerStatus]:
        """Get live status for a specific server."""
        try:
            server = self.claude.get_server(server_name)
            if not server:
                return None
            
            # Determine status
            if server.enabled:
                status = ConnectionStatus.CONNECTED
                error_message = None
            else:
                status = ConnectionStatus.FAILED
                error_message = "Server disabled"
            
            return ServerStatus(
                server_name=server_name,
                status=status,
                response_time_ms=None,
                error_message=error_message,
                tool_count=None,
                checked_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Failed to get status for {server_name}: {e}")
            return None


class MCPServerStateManager:
    """Main hybrid server state management system."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the hybrid state manager."""
        self.claude = ClaudeInterface()
        self.db = StateDatabase(db_path)
        self.runtime_cache = RuntimeCache()
        self.live_checker = LiveStatusChecker()
        
        logger.debug("Initialized MCPServerStateManager")
    
    # Fast Methods (Config Files Only)
    def list_servers_fast(self) -> List[Server]:
        """Ultra-fast config file access - <50ms"""
        try:
            return self.claude.list_servers()
        except Exception as e:
            logger.error(f"Failed to list servers fast: {e}")
            return []
    
    def get_server_fast(self, name: str) -> Optional[Server]:
        """Fast config lookup for single server."""
        try:
            return self.claude.get_server(name)
        except Exception as e:
            logger.error(f"Failed to get server fast {name}: {e}")
            return None
    
    # Cached Methods (Database + Runtime Cache)
    async def list_servers_cached(self, max_age_seconds: int = 300) -> List[ServerState]:
        """Fast cached access with optional live status - 50-200ms"""
        cache_key = f"servers_cached_{max_age_seconds}"
        
        # Try runtime cache first
        cached = self.runtime_cache.get(cache_key)
        if cached:
            return cached
        
        try:
            # Get servers from config
            servers = self.list_servers_fast()
            
            # Get recent status from database
            recent_status = await self.db.get_servers_with_recent_status(max_age_seconds)
            
            # Combine into ServerState objects
            server_states = []
            for server in servers:
                status = recent_status.get(server.name)
                server_state = ServerState(
                    server=server,
                    status=status,
                    last_seen=status.checked_at if status else None
                )
                server_states.append(server_state)
            
            # Cache the result
            self.runtime_cache.set(cache_key, server_states)
            return server_states
            
        except Exception as e:
            logger.error(f"Failed to list servers cached: {e}")
            # Fallback to fast method
            servers = self.list_servers_fast()
            return [ServerState(server=s) for s in servers]
    
    async def get_server_status_cached(self, name: str) -> Optional[ServerStatus]:
        """Get cached connection status."""
        cache_key = f"status_{name}"
        
        # Try runtime cache first
        cached = self.runtime_cache.get(cache_key)
        if cached:
            return cached
        
        try:
            # Get from database
            status = await self.db.get_latest_status(name)
            if status:
                self.runtime_cache.set(cache_key, status)
            return status
            
        except Exception as e:
            logger.error(f"Failed to get cached status for {name}: {e}")
            return None
    
    # Live Methods (Real-time Status)
    async def list_servers_live(self) -> List[ServerState]:
        """Full live status check - 1-2 seconds"""
        try:
            # Get live status
            live_status_list = await self.live_checker.get_all_status()
            
            # Record in database
            for status in live_status_list:
                await self.db.record_status_check(status.server_name, status)
            
            # Get servers from config
            servers = self.list_servers_fast()
            server_map = {s.name: s for s in servers}
            
            # Combine into ServerState objects
            server_states = []
            for status in live_status_list:
                server = server_map.get(status.server_name)
                if server:
                    server_state = ServerState(
                        server=server,
                        status=status,
                        last_seen=status.checked_at
                    )
                    server_states.append(server_state)
            
            # Clear relevant caches
            self.runtime_cache.clear()
            
            return server_states
            
        except Exception as e:
            logger.error(f"Failed to get live server status: {e}")
            # Fallback to cached method
            return await self.list_servers_cached()
    
    async def get_server_live_status(self, name: str) -> Optional[ServerStatus]:
        """Live status check for single server."""
        try:
            status = await self.live_checker.get_server_status(name)
            if status:
                await self.db.record_status_check(name, status)
                # Update runtime cache
                cache_key = f"status_{name}"
                self.runtime_cache.set(cache_key, status)
            return status
            
        except Exception as e:
            logger.error(f"Failed to get live status for {name}: {e}")
            return None
    
    # Analytics Methods (Database)
    async def get_server_analytics(self, name: str) -> Optional[ServerAnalytics]:
        """Historical usage and health analytics."""
        try:
            return await self.db.get_server_analytics(name)
        except Exception as e:
            logger.error(f"Failed to get analytics for {name}: {e}")
            return None
    
    async def get_usage_patterns(self) -> Dict[str, Any]:
        """System-wide usage patterns."""
        # This would be implemented with more complex database queries
        # For now, return basic structure
        return {
            "total_servers": len(self.list_servers_fast()),
            "analysis_timestamp": datetime.now().isoformat()
        }
    
    # Event Recording
    async def record_usage_event(self, server_name: str, event_type: str, 
                                event_data: Optional[Dict[str, Any]] = None,
                                user_context: Optional[str] = None):
        """Record a usage event for analytics."""
        try:
            event = UsageEvent(
                server_name=server_name,
                event_type=event_type,
                event_data=event_data or {},
                user_context=user_context
            )
            await self.db.record_usage_event(event)
        except Exception as e:
            logger.error(f"Failed to record usage event: {e}")
    
    # Sync Methods (Config Drift Detection)
    async def detect_config_drift(self) -> List[ConfigDrift]:
        """Detect differences between config and live state."""
        try:
            config_servers = {s.name: s for s in self.list_servers_fast()}
            live_states = await self.list_servers_live()
            live_servers = {s.server.name: s for s in live_states}
            
            drifts = []
            
            # Check for servers in config but not live
            for name, server in config_servers.items():
                if name not in live_servers:
                    drift = ConfigDrift(
                        server_name=name,
                        drift_type="missing_in_live",
                        config_value=server.enabled,
                        live_value=None,
                        description=f"Server {name} exists in config but not found in live state"
                    )
                    drifts.append(drift)
            
            # Check for servers live but not in config
            for name, state in live_servers.items():
                if name not in config_servers:
                    drift = ConfigDrift(
                        server_name=name,
                        drift_type="extra_in_live",
                        config_value=None,
                        live_value=state.status.status.value if state.status else "unknown",
                        description=f"Server {name} found in live state but not in config"
                    )
                    drifts.append(drift)
            
            # Check for configuration mismatches
            for name in set(config_servers.keys()) & set(live_servers.keys()):
                config_server = config_servers[name]
                live_state = live_servers[name]
                
                # Check enabled state mismatch
                if live_state.status:
                    config_enabled = config_server.enabled
                    live_connected = live_state.status.status == ConnectionStatus.CONNECTED
                    
                    if config_enabled and not live_connected:
                        drift = ConfigDrift(
                            server_name=name,
                            drift_type="config_mismatch",
                            config_value=True,
                            live_value=False,
                            description=f"Server {name} enabled in config but not connected in live state"
                        )
                        drifts.append(drift)
            
            return drifts
            
        except Exception as e:
            logger.error(f"Failed to detect config drift: {e}")
            return []
    
    # Maintenance
    async def cleanup_old_data(self, days_to_keep: int = 30):
        """Clean up old historical data."""
        try:
            await self.db.cleanup_old_data(days_to_keep)
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
    
    def clear_cache(self):
        """Clear runtime cache."""
        self.runtime_cache.clear()