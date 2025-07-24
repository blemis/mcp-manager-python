"""
Cache Manager Module for AI Curation Analysis.

Handles caching of server analysis results to improve performance and reduce
redundant analysis operations.
"""

from datetime import datetime, timedelta
from typing import Dict, Optional
import json
import hashlib
from pathlib import Path

from mcp_manager.ai.curation.models import ServerAnalysis
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class AnalysisCacheManager:
    """Manages caching of server analysis results."""
    
    def __init__(self, cache_dir: Optional[Path] = None, cache_duration_hours: int = 6):
        self.cache_duration = timedelta(hours=cache_duration_hours)
        self.cache_dir = cache_dir or Path.home() / ".cache" / "mcp-manager" / "analysis"
        self._memory_cache: Dict[str, ServerAnalysis] = {}
        self._cache_expiry: Dict[str, datetime] = {}
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get_cached_analysis(self, server_name: str, force_refresh: bool = False) -> Optional[ServerAnalysis]:
        """Get cached analysis for a server."""
        try:
            if force_refresh:
                logger.debug(f"Force refresh requested for {server_name}, ignoring cache")
                return None
            
            # Check memory cache first
            if self._is_memory_cache_valid(server_name):
                logger.debug(f"Using memory cache for {server_name}")
                return self._memory_cache[server_name]
            
            # Check disk cache
            cached_analysis = self._load_from_disk_cache(server_name)
            if cached_analysis:
                # Store in memory cache for faster access
                self._memory_cache[server_name] = cached_analysis
                self._cache_expiry[server_name] = datetime.now() + self.cache_duration
                logger.debug(f"Loaded {server_name} analysis from disk cache")
                return cached_analysis
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get cached analysis for {server_name}: {e}")
            return None
    
    def cache_analysis(self, server_name: str, analysis: ServerAnalysis) -> bool:
        """Cache analysis results both in memory and on disk."""
        try:
            # Store in memory cache
            self._memory_cache[server_name] = analysis
            self._cache_expiry[server_name] = datetime.now() + self.cache_duration
            
            # Store in disk cache
            success = self._save_to_disk_cache(server_name, analysis)
            
            if success:
                logger.debug(f"Cached analysis for {server_name}")
            else:
                logger.warning(f"Failed to cache analysis to disk for {server_name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to cache analysis for {server_name}: {e}")
            return False
    
    def invalidate_cache(self, server_name: Optional[str] = None) -> bool:
        """Invalidate cache for a specific server or all servers."""
        try:
            if server_name:
                # Invalidate specific server
                self._memory_cache.pop(server_name, None)
                self._cache_expiry.pop(server_name, None)
                
                cache_file = self._get_cache_file_path(server_name)
                if cache_file.exists():
                    cache_file.unlink()
                
                logger.debug(f"Invalidated cache for {server_name}")
            else:
                # Invalidate all caches
                self._memory_cache.clear()
                self._cache_expiry.clear()
                
                # Remove all cache files
                for cache_file in self.cache_dir.glob("*.json"):
                    try:
                        cache_file.unlink()
                    except Exception as e:
                        logger.warning(f"Failed to remove cache file {cache_file}: {e}")
                
                logger.info("Invalidated all analysis caches")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")
            return False
    
    def cleanup_expired_cache(self) -> int:
        """Remove expired cache entries from memory and disk."""
        try:
            removed_count = 0
            current_time = datetime.now()
            
            # Clean memory cache
            expired_keys = [
                key for key, expiry in self._cache_expiry.items()
                if current_time > expiry
            ]
            
            for key in expired_keys:
                self._memory_cache.pop(key, None)
                self._cache_expiry.pop(key, None)
                removed_count += 1
            
            # Clean disk cache
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    # Check file modification time
                    file_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
                    if current_time - file_time > self.cache_duration:
                        cache_file.unlink()
                        removed_count += 1
                except Exception as e:
                    logger.debug(f"Failed to check/remove cache file {cache_file}: {e}")
            
            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} expired cache entries")
            
            return removed_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired cache: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, any]:
        """Get cache statistics."""
        try:
            memory_count = len(self._memory_cache)
            disk_count = len(list(self.cache_dir.glob("*.json")))
            
            # Calculate cache hit ratio (placeholder for future implementation)
            cache_stats = {
                "memory_entries": memory_count,
                "disk_entries": disk_count,
                "cache_duration_hours": self.cache_duration.total_seconds() / 3600,
                "cache_directory": str(self.cache_dir),
                "last_cleanup": None  # TODO: Track last cleanup time
            }
            
            return cache_stats
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}
    
    def _is_memory_cache_valid(self, server_name: str) -> bool:
        """Check if memory cache entry is valid and not expired."""
        if server_name not in self._memory_cache:
            return False
        
        expiry = self._cache_expiry.get(server_name)
        if not expiry or datetime.now() > expiry:
            # Remove expired cache
            self._memory_cache.pop(server_name, None)
            self._cache_expiry.pop(server_name, None)
            return False
        
        return True
    
    def _get_cache_file_path(self, server_name: str) -> Path:
        """Get the cache file path for a server."""
        # Create a safe filename using hash of server name
        safe_name = hashlib.md5(server_name.encode()).hexdigest()
        return self.cache_dir / f"{safe_name}.json"
    
    def _save_to_disk_cache(self, server_name: str, analysis: ServerAnalysis) -> bool:
        """Save analysis to disk cache."""
        try:
            cache_file = self._get_cache_file_path(server_name)
            
            # Create cache data with metadata
            cache_data = {
                "server_name": server_name,
                "cached_at": datetime.now().isoformat(),
                "expires_at": (datetime.now() + self.cache_duration).isoformat(),
                "analysis": self._serialize_analysis(analysis)
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save cache to disk for {server_name}: {e}")
            return False
    
    def _load_from_disk_cache(self, server_name: str) -> Optional[ServerAnalysis]:
        """Load analysis from disk cache."""
        try:
            cache_file = self._get_cache_file_path(server_name)
            
            if not cache_file.exists():
                return None
            
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Check if cache is expired
            expires_at = datetime.fromisoformat(cache_data.get("expires_at", ""))
            if datetime.now() > expires_at:
                # Remove expired cache file
                cache_file.unlink()
                return None
            
            # Deserialize analysis
            analysis = self._deserialize_analysis(cache_data.get("analysis", {}))
            return analysis
            
        except Exception as e:
            logger.debug(f"Failed to load cache from disk for {server_name}: {e}")
            return None
    
    def _serialize_analysis(self, analysis: ServerAnalysis) -> Dict[str, any]:
        """Serialize ServerAnalysis to JSON-compatible format."""
        return {
            "server_name": analysis.server_name,
            "server_type": analysis.server_type.value if hasattr(analysis.server_type, 'value') else str(analysis.server_type),
            "reliability_score": analysis.reliability_score,
            "performance_score": analysis.performance_score,
            "compatibility_score": analysis.compatibility_score,
            "functionality_score": analysis.functionality_score,
            "documentation_score": analysis.documentation_score,
            "maintenance_score": analysis.maintenance_score,
            "overall_score": analysis.overall_score,
            "strengths": analysis.strengths,
            "weaknesses": analysis.weaknesses,
            "recommended_for": [cat.value if hasattr(cat, 'value') else str(cat) for cat in analysis.recommended_for],
            "conflicts_with": analysis.conflicts_with
        }
    
    def _deserialize_analysis(self, data: Dict[str, any]) -> Optional[ServerAnalysis]:
        """Deserialize JSON data to ServerAnalysis object."""
        try:
            from mcp_manager.core.models import ServerType
            from mcp_manager.ai.curation.models import TaskCategory
            
            # Convert server type
            server_type_str = data.get("server_type", "")
            server_type = ServerType(server_type_str) if server_type_str else ServerType.CUSTOM
            
            # Convert task categories
            recommended_for = []
            for cat_str in data.get("recommended_for", []):
                try:
                    recommended_for.append(TaskCategory(cat_str))
                except ValueError:
                    logger.debug(f"Unknown task category: {cat_str}")
            
            analysis = ServerAnalysis(
                server_name=data.get("server_name", ""),
                server_type=server_type,
                reliability_score=data.get("reliability_score", 0.5),
                performance_score=data.get("performance_score", 0.5),
                compatibility_score=data.get("compatibility_score", 0.5),
                functionality_score=data.get("functionality_score", 0.5),
                documentation_score=data.get("documentation_score", 0.5),
                maintenance_score=data.get("maintenance_score", 0.5),
                overall_score=data.get("overall_score", 0.5),
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
                recommended_for=recommended_for,
                conflicts_with=data.get("conflicts_with", [])
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to deserialize analysis: {e}")
            return None