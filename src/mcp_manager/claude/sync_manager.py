"""
Background sync operations for Claude interface caching.

This module handles background synchronization between the Claude interface
cache and the database, including file modification tracking and cache
invalidation strategies.
"""

import asyncio
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional

from mcp_manager.core.models import Server
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class SyncManager:
    """Manages background sync operations for Claude interface caching."""
    
    def __init__(self, cache_ttl: float = 30.0, sync_interval: float = 60.0):
        """
        Initialize sync manager.
        
        Args:
            cache_ttl: Cache time-to-live in seconds
            sync_interval: Background sync interval in seconds
        """
        self.cache_ttl = cache_ttl
        self.sync_interval = sync_interval
        
        # Background sync settings
        self._sync_thread: Optional[threading.Thread] = None
        self._sync_stop_event = threading.Event()
        
        # File modification tracking for cache invalidation
        self._config_files = [
            Path.home() / ".config" / "claude-code" / "mcp-servers.json",
            Path.cwd() / ".mcp.json",
            Path.home() / ".claude.json"
        ]
        self._last_modified_times: Dict[str, float] = {}
        
        logger.debug("SyncManager initialized", extra={
            "cache_ttl": self.cache_ttl,
            "sync_interval": self.sync_interval
        })
    
    def start_background_sync(self, refresh_callback, sync_callback):
        """
        Start background sync thread.
        
        Args:
            refresh_callback: Function to call when cache needs refresh
            sync_callback: Async function to call for database sync
        """
        if self._sync_thread and self._sync_thread.is_alive():
            return
        
        self._sync_stop_event.clear()
        self._sync_thread = threading.Thread(
            target=self._background_sync_worker,
            args=(refresh_callback, sync_callback),
            daemon=True
        )
        self._sync_thread.start()
        logger.debug("Background sync thread started")
    
    def stop_background_sync(self):
        """Stop background sync thread."""
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_stop_event.set()
            self._sync_thread.join(timeout=5.0)
            logger.debug("Background sync thread stopped")
    
    def _background_sync_worker(self, refresh_callback, sync_callback):
        """
        Background worker that syncs cache with database.
        
        Args:
            refresh_callback: Function to call when cache needs refresh
            sync_callback: Async function to call for database sync
        """
        while not self._sync_stop_event.wait(self.sync_interval):
            try:
                if self.should_refresh_cache():
                    refresh_callback()
                    
                # Async database sync (run in thread pool to avoid blocking)
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.run_coroutine_threadsafe(sync_callback(), loop)
                    else:
                        asyncio.run(sync_callback())
                except RuntimeError:
                    # Create new event loop if none exists
                    asyncio.run(sync_callback())
                    
            except Exception as e:
                logger.warning(f"Background sync error: {e}")
    
    def should_refresh_cache(self) -> bool:
        """Check if cache should be refreshed based on file modifications."""
        for config_file in self._config_files:
            if not config_file.exists():
                continue
                
            try:
                current_mtime = config_file.stat().st_mtime
                last_mtime = self._last_modified_times.get(str(config_file), 0)
                
                if current_mtime > last_mtime:
                    self._last_modified_times[str(config_file)] = current_mtime
                    return True
            except Exception as e:
                logger.debug(f"Error checking file modification time for {config_file}: {e}")
        
        return False
    
    def is_cache_valid(self, cache_timestamp: float) -> bool:
        """
        Check if cache is still valid based on timestamp.
        
        Args:
            cache_timestamp: When cache was last updated
            
        Returns:
            True if cache is still valid
        """
        current_time = time.time()
        return current_time - cache_timestamp < self.cache_ttl
    
    async def sync_to_database(self, servers: List[Server]):
        """
        Async sync server list to database.
        
        Args:
            servers: List of servers to sync
        """
        try:
            # Import here to avoid circular imports
            from mcp_manager.core.tool_registry import ToolRegistryService
            
            if not servers:
                return
            
            # Update database with current server list
            registry = ToolRegistryService()
            for server in servers:
                # Update server availability in database
                registry.update_tool_availability(server.name, True)  # Assume enabled if in config
            
            logger.debug(f"Synced {len(servers)} servers to database")
            
        except Exception as e:
            logger.warning(f"Database sync failed: {e}")