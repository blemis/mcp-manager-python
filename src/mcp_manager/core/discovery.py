"""
Server discovery functionality for MCP Manager.

Provides discovery of MCP servers from NPM registry, Docker registry,
and other sources with caching and filtering capabilities.
"""

import asyncio
import json
import logging
import re
import fnmatch
from datetime import datetime, timedelta
from pathlib import Path
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
        
        # Suppress verbose HTTP logging from httpx
        logging.getLogger("httpx").setLevel(logging.WARNING)
        
    def _matches_pattern(self, text: str, pattern: str) -> bool:
        """
        Check if text matches pattern using wildcards and regex.
        
        Supports:
        - Wildcards: aws* matches aws-s3, aws-dynamodb, etc.
        - Regex: if pattern starts with 'regex:' it's treated as regex
        - Case-insensitive matching
        
        Args:
            text: Text to match against
            pattern: Pattern to match (supports wildcards and regex)
            
        Returns:
            True if text matches pattern
        """
        if not pattern:
            return True
            
        text = text.lower()
        pattern = pattern.lower()
        
        # Handle regex patterns (prefix with 'regex:')
        if pattern.startswith('regex:'):
            try:
                regex_pattern = pattern[6:]  # Remove 'regex:' prefix
                return bool(re.search(regex_pattern, text))
            except re.error:
                # If regex is invalid, fall back to literal matching
                return pattern[6:] in text
        
        # Handle wildcard patterns (*, ?, [])
        if any(char in pattern for char in ['*', '?', '[']):
            return fnmatch.fnmatch(text, pattern)
        
        # Default: substring matching
        return pattern in text
    
    def _filter_results_by_pattern(self, results: List[DiscoveryResult], query: str) -> List[DiscoveryResult]:
        """
        Filter discovery results by pattern matching on name, package, and description.
        
        Args:
            results: List of discovery results
            query: Pattern to match
            
        Returns:
            Filtered list of results
        """
        if not query:
            return results
            
        filtered = []
        for result in results:
            # Check name, package, and description
            if (self._matches_pattern(result.name, query) or 
                self._matches_pattern(result.package or "", query) or
                self._matches_pattern(result.description or "", query)):
                filtered.append(result)
                
        return filtered
        
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
        is_pattern_search = query and (any(char in query for char in ['*', '?', '[']) or query.startswith('regex:'))
        
        # For pattern searches, use broader search terms for APIs, then filter results
        if is_pattern_search:
            # Extract base search term from pattern (e.g., 'aws*' -> 'aws')
            if query.startswith('regex:'):
                api_query = None  # Use broad search for regex
            else:
                base_term = query.split('*')[0].split('?')[0].split('[')[0]
                api_query = base_term if len(base_term) >= 2 else None
        else:
            api_query = query
        
        if not server_type or server_type == ServerType.NPM:
            tasks.append(self._discover_npm_servers(api_query, per_source_limit))
            
        if not server_type or server_type == ServerType.DOCKER:
            tasks.append(self._discover_docker_hub_servers(api_query, per_source_limit))
            
        if not server_type or server_type == ServerType.DOCKER_DESKTOP:
            tasks.append(self._discover_docker_desktop_servers(api_query, per_source_limit))
        
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
            results = self._filter_results_by_pattern(results, query)
        
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
        
    async def _discover_npm_servers(
        self,
        query: Optional[str] = None,
        limit: int = 25,
    ) -> List[DiscoveryResult]:
        """Discover NPM-based MCP servers."""
        logger.debug("Discovering NPM servers")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                results = []
                search_url = f"{self.config.discovery.npm_registry}/-/v1/search"
                
                # Strategy 1: Search for MCP-specific packages if query provided
                if query:
                    search_queries = [
                        f"{query} mcp",  # Query + MCP
                        f"mcp {query}",  # MCP + Query  
                        f"@{query}/mcp", # Scoped package format like @playwright/mcp
                        query,  # Direct query
                    ]
                else:
                    search_queries = ["mcp server", "@modelcontextprotocol"]
                
                for search_query in search_queries:
                    params = {
                        "text": search_query,
                        "size": min(limit, 20),
                        "quality": 0.4,  # Lower quality threshold to find more packages
                        "popularity": 0.1,  # Much lower popularity threshold
                        "maintenance": 0.1,
                    }
                    
                    try:
                        response = await client.get(search_url, params=params)
                        response.raise_for_status()
                        
                        data = response.json()
                        
                        for package in data.get("objects", []):
                            pkg_info = package.get("package", {})
                            name = pkg_info.get("name", "")
                            
                            # Avoid duplicates
                            if any(r.package == name for r in results):
                                continue
                            
                            description = pkg_info.get("description", "")
                            keywords = pkg_info.get("keywords", [])
                            
                            is_mcp = self._is_mcp_package(name, description, keywords)
                            
                            if is_mcp:
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
                                    install_command="npx",
                                    install_args=["-y", name],
                                    downloads=package.get("score", {}).get("detail", {}).get("popularity"),
                                    last_updated=self._parse_date(pkg_info.get("date")),
                                )
                                results.append(result)
                                
                                if len(results) >= limit:
                                    break
                    
                    except httpx.HTTPStatusError:
                        continue  # Try next search query
                    
                    if len(results) >= limit:
                        break
                
                return results[:limit]
                
        except httpx.RequestError as e:
            raise NetworkError(f"Failed to search NPM registry: {e}")
        except Exception as e:
            raise DiscoveryError(f"NPM discovery failed: {e}")
            
    async def _discover_docker_hub_servers(
        self,
        query: Optional[str] = None,
        limit: int = 25,
    ) -> List[DiscoveryResult]:
        """Discover Docker Hub MCP servers by checking known organizations."""
        logger.debug("Discovering Docker Hub servers")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                results = []
                
                # Known MCP server organizations and repositories
                known_orgs = [
                    "modelcontextprotocol",
                    "anthropics", 
                    "mcp-docker",
                    "mcp-server",
                ]
                
                # Strategy 1: Check known organizations for repositories
                for org in known_orgs:
                    try:
                        repos_url = f"https://hub.docker.com/v2/repositories/{org}/"
                        response = await client.get(repos_url, params={"page_size": 50})
                        
                        if response.status_code == 200:
                            data = response.json()
                            
                            for repo in data.get("results", []):
                                name = repo.get("name", "")
                                namespace = repo.get("namespace", "")
                                full_name = f"{namespace}/{name}" if namespace else name
                                description = repo.get("short_description", "")
                                
                                # Filter by query if provided
                                if query:
                                    query_lower = query.lower()
                                    name_match = query_lower in name.lower()
                                    desc_match = query_lower in description.lower()
                                    if not (name_match or desc_match):
                                        continue
                                
                                # Extract server name
                                server_name = self._extract_docker_server_name(name)
                                
                                # Avoid duplicates
                                if any(r.package == full_name for r in results):
                                    continue
                                
                                result = DiscoveryResult(
                                    name=server_name,
                                    package=full_name,
                                    version="latest",
                                    description=description or f"Docker MCP server: {server_name}",
                                    author=namespace,
                                    server_type=ServerType.DOCKER,
                                    install_command="docker",
                                    install_args=["run", "-i", "--rm", "--pull", "always", f"{full_name}:latest"],
                                    keywords=["mcp", "docker", server_name],
                                    downloads=repo.get("pull_count"),
                                    last_updated=self._parse_date(repo.get("last_updated")),
                                )
                                results.append(result)
                                
                                if len(results) >= limit:
                                    break
                    
                    except (httpx.HTTPStatusError, httpx.RequestError):
                        continue  # Try next organization
                    
                    if len(results) >= limit:
                        break
                
                # Strategy 2: Use Docker Index API (v1) which actually works
                search_url = "https://index.docker.io/v1/search"
                search_terms = []
                
                if query:
                    search_terms = [query, f"mcp {query}", f"{query} mcp"]
                else:
                    search_terms = ["mcp"]
                
                for term in search_terms:
                    try:
                        params = {"q": term, "n": min(limit, 25)}
                        response = await client.get(search_url, params=params)
                        
                        if response.status_code == 200:
                            data = response.json()
                            
                            for repo in data.get("results", []):
                                name = repo.get("name", "")
                                description = repo.get("description", "")
                                
                                # Filter for MCP servers or query matches
                                is_mcp = (
                                    "mcp" in name.lower() or 
                                    "mcp" in description.lower() or
                                    "model-context" in description.lower()
                                )
                                
                                is_query_match = query and (
                                    query.lower() in name.lower() or 
                                    query.lower() in description.lower()
                                )
                                
                                if not (is_mcp or is_query_match):
                                    continue
                                
                                # Extract namespace and name
                                if "/" in name:
                                    namespace, repo_name = name.split("/", 1)
                                else:
                                    namespace = ""
                                    repo_name = name
                                
                                server_name = self._extract_docker_server_name(repo_name)
                                
                                # Avoid duplicates
                                if any(r.package == name for r in results):
                                    continue
                                
                                result = DiscoveryResult(
                                    name=server_name,
                                    package=name,
                                    version="latest",
                                    description=description or f"Docker MCP server: {server_name}",
                                    author=namespace,
                                    server_type=ServerType.DOCKER,
                                    install_command="docker",
                                    install_args=["run", "-i", "--rm", "--pull", "always", f"{name}:latest"],
                                    keywords=["mcp", "docker", server_name],
                                    downloads=repo.get("pull_count"),
                                )
                                results.append(result)
                                
                                if len(results) >= limit:
                                    break
                    
                    except (httpx.HTTPStatusError, httpx.RequestError):
                        continue
                    
                    if len(results) >= limit:
                        break
                
                return results[:limit]
                
        except Exception as e:
            logger.warning(f"Docker Hub discovery failed: {e}")
            return []
    
    
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
            import shutil
            
            # Use proper Docker path discovery
            docker_path = shutil.which("docker")
            if not docker_path:
                # Fallback to common locations
                for path in ["/opt/homebrew/bin/docker", "/usr/local/bin/docker", "/usr/bin/docker"]:
                    if Path(path).exists():
                        docker_path = path
                        break
            
            if not docker_path:
                logger.warning("Docker command not found")
                return {}
            
            # First try to get the full catalog
            result = subprocess.run(
                [docker_path, "mcp", "catalog", "show"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                logger.warning(f"Failed to get Docker MCP catalog: {result.stderr}")
                return {}
            
            # Parse the catalog output
            catalog = {}
            
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if line and ':' in line and not line.startswith(' ') and not line.startswith('-'):
                    # New server entry: "server-name: description"
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        server_name = parts[0].strip()
                        description = parts[1].strip()
                        
                        catalog[server_name] = {
                            "description": description,
                            "package": server_name,
                            "version": "latest"
                        }
            
            logger.debug(f"Found {len(catalog)} servers in Docker MCP catalog")
            return catalog
            
        except Exception as e:
            logger.warning(f"Failed to get Docker MCP catalog: {e}")
            return {}
    
    async def _get_docker_mcp_enabled_servers(self) -> list:
        """Get currently enabled servers using docker mcp server list command."""
        try:
            import subprocess
            import shutil
            
            # Use proper Docker path discovery
            docker_path = shutil.which("docker")
            if not docker_path:
                # Fallback to common locations
                for path in ["/opt/homebrew/bin/docker", "/usr/local/bin/docker", "/usr/bin/docker"]:
                    if Path(path).exists():
                        docker_path = path
                        break
            
            if not docker_path:
                logger.warning("Docker command not found")
                return []
            
            # Use docker mcp server list to get enabled servers
            result = subprocess.run(
                [docker_path, "mcp", "server", "list"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            if result.returncode != 0:
                logger.warning(f"Failed to get enabled Docker MCP servers: {result.stderr}")
                return []
            
            # Parse the output - it should be a comma-separated list
            enabled_servers = []
            output = result.stdout.strip()
            if output:
                enabled_servers = [s.strip() for s in output.split(',') if s.strip()]
            
            logger.debug(f"Found {len(enabled_servers)} enabled Docker MCP servers: {enabled_servers}")
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
    
    def _is_mcp_docker_image(self, name: str, description: str) -> bool:
        """Check if Docker image is MCP-related."""
        mcp_indicators = ["mcp", "model-context-protocol", "server"]
        
        # Check name
        name_lower = name.lower()
        for indicator in mcp_indicators:
            if indicator in name_lower:
                return True
        
        # Check description
        desc_lower = description.lower()
        for indicator in mcp_indicators:
            if indicator in desc_lower:
                return True
                
        return False
    
    def _extract_docker_server_name(self, image_name: str) -> str:
        """Extract server name from Docker image name."""
        # Remove common prefixes and suffixes
        name = image_name
        
        # Remove server- prefix
        if name.startswith("server-"):
            name = name[7:]
        
        # Remove -mcp suffix
        if name.endswith("-mcp"):
            name = name[:-4]
        
        # Remove mcp- prefix
        if name.startswith("mcp-"):
            name = name[4:]
            
        return name or image_name
    
    async def update_docker_catalog(self) -> bool:
        """Update Docker MCP catalog using docker mcp catalog update."""
        try:
            import subprocess
            import shutil
            
            # Use proper Docker path discovery
            docker_path = shutil.which("docker")
            if not docker_path:
                # Fallback to common locations
                for path in ["/opt/homebrew/bin/docker", "/usr/local/bin/docker", "/usr/bin/docker"]:
                    if Path(path).exists():
                        docker_path = path
                        break
            
            if not docker_path:
                logger.warning("Docker command not found")
                return False
            
            logger.debug("Updating Docker MCP catalog...")
            result = subprocess.run(
                [docker_path, "mcp", "catalog", "update"],
                capture_output=True,
                text=True,
                timeout=60,  # Longer timeout for network operations
            )
            
            if result.returncode != 0:
                logger.warning(f"Failed to update Docker MCP catalog: {result.stderr}")
                return False
            
            logger.debug("Docker MCP catalog updated successfully")
            # Clear cache after update
            self.clear_cache()
            return True
            
        except Exception as e:
            logger.warning(f"Failed to update Docker MCP catalog: {e}")
            return False
        
    def clear_cache(self) -> None:
        """Clear discovery cache."""
        self._cache.clear()
        logger.debug("Discovery cache cleared")