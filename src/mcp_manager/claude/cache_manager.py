"""
Cache management for Claude interface operations.

Provides memory cache with TTL and thread-safe operations.
"""

import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from mcp_manager.core.models import Server
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class CacheManager:
    """Thread-safe cache manager with TTL support."""
    
    def __init__(self, ttl_seconds: int = 300):  # 5 minute default TTL
        """Initialize cache manager."""
        self.ttl = timedelta(seconds=ttl_seconds)
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, datetime] = {}
        self._lock = threading.RLock()
        
        # Cache statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
    
    def get_servers(self) -> Optional[List[Server]]:
        """Get cached server list if not expired."""
        with self._lock:
            if self._is_cached('servers') and not self._is_expired('servers'):
                self._hits += 1
                logger.debug("Cache hit for servers")
                return self._cache['servers']
            
            self._misses += 1
            logger.debug("Cache miss for servers")
            return None
    
    def set_servers(self, servers: List[Server]) -> None:
        """Cache server list with timestamp."""
        with self._lock:
            self._cache['servers'] = servers
            self._timestamps['servers'] = datetime.now()
            logger.debug(f"Cached {len(servers)} servers")
    
    def get_server_config(self, config_type: str) -> Optional[Dict[str, Any]]:
        """Get cached server configuration."""
        cache_key = f"config_{config_type}"
        with self._lock:
            if self._is_cached(cache_key) and not self._is_expired(cache_key):
                self._hits += 1
                logger.debug(f"Cache hit for {config_type} config")
                return self._cache[cache_key]
            
            self._misses += 1
            logger.debug(f"Cache miss for {config_type} config")
            return None
    
    def set_server_config(self, config_type: str, config: Dict[str, Any]) -> None:
        """Cache server configuration."""
        cache_key = f"config_{config_type}"
        with self._lock:
            self._cache[cache_key] = config
            self._timestamps[cache_key] = datetime.now()
            logger.debug(f"Cached {config_type} config")
    
    def get_file_mtime(self, file_path: str) -> Optional[datetime]:
        """Get cached file modification time."""
        cache_key = f"mtime_{file_path}"
        with self._lock:
            return self._cache.get(cache_key)
    
    def set_file_mtime(self, file_path: str, mtime: datetime) -> None:
        """Cache file modification time."""
        cache_key = f"mtime_{file_path}"
        with self._lock:
            self._cache[cache_key] = mtime
            self._timestamps[cache_key] = datetime.now()
    
    def invalidate_servers(self) -> None:
        """Invalidate cached server list."""
        with self._lock:
            if 'servers' in self._cache:
                del self._cache['servers']
                del self._timestamps['servers']
                self._evictions += 1
                logger.debug("Invalidated server cache")
    
    def invalidate_config(self, config_type: str) -> None:
        """Invalidate cached configuration."""
        cache_key = f"config_{config_type}"
        with self._lock:
            if cache_key in self._cache:
                del self._cache[cache_key]
                del self._timestamps[cache_key]
                self._evictions += 1
                logger.debug(f"Invalidated {config_type} config cache")
    
    def invalidate_all(self) -> None:
        """Clear all cached data."""
        with self._lock:
            evicted_count = len(self._cache)
            self._cache.clear()
            self._timestamps.clear()
            self._evictions += evicted_count
            logger.debug("Cleared all cache")
    
    def cleanup_expired(self) -> int:
        """Remove expired cache entries."""
        expired_count = 0
        with self._lock:
            expired_keys = []
            for key in list(self._cache.keys()):
                if self._is_expired(key):
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
                del self._timestamps[key]
                expired_count += 1
            
            self._evictions += expired_count
            
        if expired_count > 0:
            logger.debug(f"Cleaned up {expired_count} expired cache entries")
        
        return expired_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0
            
            return {
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': hit_rate,
                'evictions': self._evictions,
                'cached_items': len(self._cache),
                'ttl_seconds': self.ttl.total_seconds()
            }
    
    def reset_stats(self) -> None:
        """Reset cache statistics."""
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._evictions = 0
    
    def _is_cached(self, key: str) -> bool:
        """Check if key exists in cache."""
        return key in self._cache
    
    def _is_expired(self, key: str) -> bool:
        """Check if cached item is expired."""
        if key not in self._timestamps:
            return True
        
        return datetime.now() - self._timestamps[key] > self.ttl