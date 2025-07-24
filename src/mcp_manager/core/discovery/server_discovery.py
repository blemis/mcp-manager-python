"""
Main server discovery orchestration class.

Coordinates discovery from multiple sources (NPM, Docker Hub, Docker Desktop)
with caching and filtering capabilities.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from mcp_manager.core.exceptions import DiscoveryError
from mcp_manager.core.models import DiscoveryResult, ServerType
from mcp_manager.utils.config import Config, get_config
from mcp_manager.utils.logging import get_logger

from .cache import CacheEntry
from .npm import NPMDiscovery
from .docker import DockerDiscovery
from .similarity import SimilarityDetector
from .helpers import PatternMatcher

logger = get_logger(__name__)


class ServerDiscovery:
    """Server discovery service."""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize server discovery.
        
        Args:
            config: Configuration instance
        """
        self.config = config or get_config()
        self._cache: Dict[str, CacheEntry] = {}
        
        # Initialize discovery services
        self.npm_discovery = NPMDiscovery(self.config)
        self.docker_discovery = DockerDiscovery(self.config)
        self.similarity_detector = SimilarityDetector()
        self.pattern_matcher = PatternMatcher()
        
        # Suppress verbose HTTP logging from httpx
        logging.getLogger("httpx").setLevel(logging.WARNING)
        
    async def discover_servers(
        self,
        query: Optional[str] = None,
        server_type: Optional[ServerType] = None,
        limit: int = 50,
        use_cache: bool = True,
    ) -> List[DiscoveryResult]:
        """
        Discover MCP servers from various sources.
        
        Args:
            query: Search query
            server_type: Filter by server type
            limit: Maximum number of results
            use_cache: Whether to use cached results
            
        Returns:
            List of discovery results
        """
        logger.debug(f"Discovering servers (query: {query}, type: {server_type})")
        
        cache_key = f"{query}:{server_type}:{limit}"
        
        # Check cache first
        if use_cache and cache_key in self._cache:
            entry = self._cache[cache_key]
            if not entry.is_expired():
                logger.debug("Using cached discovery results")
                return entry.data
                
        # Discover from sources
        results = []
        tasks = []
        
        # Distribute limit across sources
        source_count = 0
        if not server_type or server_type == ServerType.NPM:
            source_count += 1
        if not server_type or server_type == ServerType.DOCKER:
            source_count += 1
        if not server_type or server_type == ServerType.DOCKER_DESKTOP:
            source_count += 1
        
        per_source_limit = limit // source_count if source_count > 0 else limit
        
        # Determine if this is a pattern search that needs broader API queries
        is_pattern_search = self.pattern_matcher.is_pattern_query(query)
        
        # For pattern searches, use broader search terms for APIs, then filter results
        if is_pattern_search:
            api_query = self.pattern_matcher.extract_base_query(query)
        else:
            api_query = query
        
        if not server_type or server_type == ServerType.NPM:
            tasks.append(self.npm_discovery.discover_servers(api_query, per_source_limit))
            
        if not server_type or server_type == ServerType.DOCKER:
            tasks.append(self.docker_discovery.discover_docker_hub_servers(api_query, per_source_limit))
            
        if not server_type or server_type == ServerType.DOCKER_DESKTOP:
            tasks.append(self.docker_discovery.discover_docker_desktop_servers(api_query, per_source_limit))
        
        # Run discovery tasks concurrently
        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            for task_result in task_results:
                if isinstance(task_result, Exception):
                    logger.warning(f"Discovery task failed: {task_result}")
                else:
                    results.extend(task_result)
            
        # Apply pattern filtering if this was a pattern search
        if is_pattern_search:
            results = self.pattern_matcher.filter_results_by_pattern(results, query)
        
        # Sort by relevance (downloads, update time, etc.)
        results.sort(key=self._calculate_relevance_score, reverse=True)
        
        # Limit results
        results = results[:limit]
        
        # Cache results
        if use_cache:
            self._cache[cache_key] = CacheEntry(
                data=results,
                timestamp=datetime.now(),
                ttl=self.config.discovery.cache_ttl,
            )
            
        logger.debug(f"Found {len(results)} servers")
        return results
        
    def _calculate_relevance_score(self, result: DiscoveryResult) -> float:
        """Calculate relevance score for sorting."""
        score = 0.0
        
        # Downloads/popularity
        if result.downloads:
            score += min(result.downloads * 1000, 10000)
            
        # Recency
        if result.last_updated:
            days_old = (datetime.now() - result.last_updated.replace(tzinfo=None)).days
            score += max(0, 1000 - days_old)
            
        # Name matching (if query provided)
        # This would need to be implemented with the original query
        
        return score
    
    async def update_docker_catalog(self) -> bool:
        """Update Docker MCP catalog using docker mcp catalog update."""
        success = await self.docker_discovery.update_docker_catalog()
        if success:
            # Clear cache after update
            self.clear_cache()
        return success
        
    def clear_cache(self) -> None:
        """Clear discovery cache."""
        self._cache.clear()
        logger.debug("Discovery cache cleared")
    
    def detect_similar_servers(self, target_server: DiscoveryResult, existing_servers: List[Any]) -> List[Dict[str, Any]]:
        """
        Detect servers that provide similar functionality to the target server.
        
        Args:
            target_server: The server to check for similarities
            existing_servers: List of currently installed servers
            
        Returns:
            List of similar servers with similarity details
        """
        return self.similarity_detector.detect_similar_servers(target_server, existing_servers)