"""
Server discovery functionality for MCP Manager.

Provides discovery of MCP servers from NPM registry, Docker registry,
and other sources with caching and filtering capabilities.
"""

import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel

from mcp_manager.core.exceptions import DiscoveryError, NetworkError
from mcp_manager.core.models import DiscoveryResult, ServerType
from mcp_manager.utils.config import Config, get_config
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class CacheEntry(BaseModel):
    """Cache entry for discovery results."""
    
    data: List[DiscoveryResult]
    timestamp: datetime
    ttl: int  # Time to live in seconds
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return datetime.now() > self.timestamp + timedelta(seconds=self.ttl)


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
        logger.info(f"Discovering servers (query: {query}, type: {server_type})")
        
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
            source_count += 2  # Docker Hub and Docker Desktop
        
        per_source_limit = limit // source_count if source_count > 0 else limit
        
        if not server_type or server_type == ServerType.NPM:
            tasks.append(self._discover_npm_servers(query, per_source_limit))
            
        if not server_type or server_type == ServerType.DOCKER:
            tasks.append(self._discover_docker_hub_servers(query, per_source_limit))
            tasks.append(self._discover_docker_desktop_servers(query, per_source_limit))
        
        # Run discovery tasks concurrently
        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            for task_result in task_results:
                if isinstance(task_result, Exception):
                    logger.warning(f"Discovery task failed: {task_result}")
                else:
                    results.extend(task_result)
            
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
            
        logger.info(f"Found {len(results)} servers")
        return results
        
    async def _discover_npm_servers(
        self,
        query: Optional[str] = None,
        limit: int = 25,
    ) -> List[DiscoveryResult]:
        """Discover NPM-based MCP servers."""
        logger.debug("Discovering NPM servers")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Search NPM registry
                search_query = query or "mcp server"
                search_url = f"{self.config.discovery.npm_registry}/-/v1/search"
                
                params = {
                    "text": search_query,
                    "size": limit,
                    "quality": 0.65,
                    "popularity": 0.98,
                    "maintenance": 0.5,
                }
                
                response = await client.get(search_url, params=params)
                response.raise_for_status()
                
                data = response.json()
                results = []
                
                for package in data.get("objects", []):
                    pkg_info = package.get("package", {})
                    
                    # Filter MCP-related packages
                    name = pkg_info.get("name", "")
                    description = pkg_info.get("description", "")
                    keywords = pkg_info.get("keywords", [])
                    
                    if self._is_mcp_package(name, description, keywords):
                        result = DiscoveryResult(
                            name=self._extract_server_name(name),
                            package=name,
                            version=pkg_info.get("version", "unknown"),
                            description=description,
                            author=self._get_author_name(pkg_info.get("author")),
                            homepage=pkg_info.get("homepage"),
                            repository=self._get_repo_url(pkg_info.get("links", {})),
                            keywords=keywords,
                            server_type=ServerType.NPM,
                            install_command=f"npx -y {name}",
                            downloads=package.get("score", {}).get("detail", {}).get("popularity"),
                            last_updated=self._parse_date(pkg_info.get("date")),
                        )
                        results.append(result)
                        
                return results
                
        except httpx.RequestError as e:
            raise NetworkError(f"Failed to search NPM registry: {e}")
        except Exception as e:
            raise DiscoveryError(f"NPM discovery failed: {e}")
            
    async def _discover_docker_hub_servers(
        self,
        query: Optional[str] = None,
        limit: int = 25,
    ) -> List[DiscoveryResult]:
        """Discover Docker Hub MCP servers."""
        logger.debug("Discovering Docker Hub servers")
        
        # Known Docker MCP servers (Docker Hub API is complex for search)
        known_servers = [
            {
                "name": "puppeteer",
                "package": "mcp-docker-desktop/puppeteer",
                "description": "MCP server for Puppeteer browser automation",
                "version": "latest",
            },
            {
                "name": "search",
                "package": "mcp-docker-desktop/search", 
                "description": "MCP server for web search capabilities",
                "version": "latest",
            },
            {
                "name": "http",
                "package": "mcp-docker-desktop/http",
                "description": "MCP server for HTTP requests",
                "version": "latest",
            },
            {
                "name": "k8s",
                "package": "mcp-docker-desktop/k8s",
                "description": "MCP server for Kubernetes management",
                "version": "latest",
            },
            {
                "name": "terraform",
                "package": "mcp-docker-desktop/terraform",
                "description": "MCP server for Terraform operations", 
                "version": "latest",
            },
            {
                "name": "aws",
                "package": "mcp-docker-desktop/aws",
                "description": "MCP server for AWS operations",
                "version": "latest",
            },
        ]
        
        results = []
        
        for server_info in known_servers:
            # Filter by query if provided
            if query and query.lower() not in server_info["name"].lower():
                continue
                
            result = DiscoveryResult(
                name=server_info["name"],
                package=server_info["package"],
                version=server_info["version"],
                description=server_info["description"],
                server_type=ServerType.DOCKER,
                install_command="docker",
                install_args=["run", "-i", "--rm", "--pull", "always", f"{server_info['package']}:latest"],
                keywords=["mcp", "docker", server_info["name"]],
            )
            results.append(result)
            
        return results[:limit]
    
    async def _discover_docker_desktop_servers(
        self,
        query: Optional[str] = None,
        limit: int = 25,
    ) -> List[DiscoveryResult]:
        """Discover Docker Desktop MCP servers dynamically."""
        logger.debug("Discovering Docker Desktop MCP servers")
        
        try:
            # Get available servers from Docker MCP catalog
            available_servers = await self._get_docker_mcp_catalog()
            
            # Get currently enabled servers from registry
            enabled_servers = await self._get_docker_mcp_enabled_servers()
            
            results = []
            
            # Add individual servers from catalog
            for server_name, server_info in available_servers.items():
                # Filter by query if provided
                if query:
                    query_lower = query.lower()
                    name_match = query_lower in server_name.lower()
                    desc_match = query_lower in server_info.get("description", "").lower()
                    if not (name_match or desc_match):
                        continue
                
                result = DiscoveryResult(
                    name=f"docker-desktop-{server_name}",
                    package=server_info.get("package", server_name),
                    version=server_info.get("version", "latest"),
                    description=server_info.get("description", f"Docker Desktop MCP server: {server_name}"),
                    server_type=ServerType.DOCKER_DESKTOP,
                    install_command="docker",
                    install_args=["mcp", "server", "enable", server_name],
                    keywords=["mcp", "docker-desktop", server_name],
                )
                results.append(result)
            
            # Add gateway option if enabled servers exist
            if enabled_servers:
                if not query or "gateway" in query.lower():
                    gateway_result = DiscoveryResult(
                        name="docker-gateway",
                        package="docker-gateway",
                        version="latest",
                        description=f"Docker Desktop MCP Gateway - currently provides: {', '.join(enabled_servers)}",
                        server_type=ServerType.DOCKER_DESKTOP,
                        install_command="docker",
                        install_args=["mcp", "gateway", "run", "--servers", ",".join(enabled_servers)],
                        keywords=["mcp", "docker-desktop", "gateway"] + enabled_servers,
                    )
                    results.append(gateway_result)
            
            return results[:limit]
            
        except Exception as e:
            logger.warning(f"Failed to discover Docker Desktop servers: {e}")
            return []
    
    async def _get_docker_mcp_catalog(self) -> dict:
        """Get available servers from Docker MCP catalog."""
        try:
            import subprocess
            result = subprocess.run(
                ["docker", "mcp", "catalog", "show", "docker-mcp"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                logger.warning("Failed to get Docker MCP catalog")
                return {}
            
            # Parse the catalog output
            catalog = {}
            current_server = None
            
            for line in result.stdout.strip().split('\n'):
                if line and ':' in line and not line.startswith(' '):
                    # New server entry
                    server_name, description = line.split(':', 1)
                    current_server = server_name.strip()
                    catalog[current_server] = {
                        "description": description.strip(),
                        "package": current_server,
                        "version": "latest"
                    }
            
            logger.debug(f"Found {len(catalog)} servers in Docker MCP catalog")
            return catalog
            
        except Exception as e:
            logger.warning(f"Failed to get Docker MCP catalog: {e}")
            return {}
    
    async def _get_docker_mcp_enabled_servers(self) -> list:
        """Get currently enabled servers from Docker MCP registry."""
        try:
            import yaml
            from pathlib import Path
            
            registry_path = Path.home() / ".docker" / "mcp" / "registry.yaml"
            if not registry_path.exists():
                return []
            
            with open(registry_path) as f:
                registry_data = yaml.safe_load(f)
            
            enabled_servers = list(registry_data.get("registry", {}).keys())
            logger.debug(f"Found {len(enabled_servers)} enabled Docker MCP servers")
            return enabled_servers
            
        except Exception as e:
            logger.warning(f"Failed to get enabled Docker MCP servers: {e}")
            return []
        
    def _is_mcp_package(
        self,
        name: str,
        description: str,
        keywords: List[str],
    ) -> bool:
        """Check if package is MCP-related."""
        mcp_indicators = [
            "mcp",
            "model-context-protocol",
            "claude-mcp",
            "@modelcontextprotocol",
        ]
        
        # Check name
        for indicator in mcp_indicators:
            if indicator in name.lower():
                return True
                
        # Check keywords
        for keyword in keywords:
            if any(indicator in keyword.lower() for indicator in mcp_indicators):
                return True
                
        # Check description
        for indicator in mcp_indicators:
            if indicator in description.lower():
                return True
                
        return False
        
    def _extract_server_name(self, package_name: str) -> str:
        """Extract server name from package name."""
        # Remove common prefixes
        name = package_name
        prefixes = [
            "@modelcontextprotocol/server-",
            "mcp-server-", 
            "claude-mcp-",
            "mcp-",
        ]
        
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
                
        return name
        
    def _get_author_name(self, author: Any) -> Optional[str]:
        """Extract author name from author field."""
        if isinstance(author, str):
            return author
        elif isinstance(author, dict):
            return author.get("name")
        return None
        
    def _get_repo_url(self, links: Dict[str, Any]) -> Optional[str]:
        """Extract repository URL from links."""
        repo = links.get("repository")
        if isinstance(repo, str):
            return repo
        elif isinstance(repo, dict):
            return repo.get("url")
        return None
        
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None
            
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None
            
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
        
    def clear_cache(self) -> None:
        """Clear discovery cache."""
        self._cache.clear()
        logger.debug("Discovery cache cleared")