"""
NPM registry discovery for MCP servers.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from mcp_manager.core.models import DiscoveryResult, ServerType
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class NPMDiscovery:
    """NPM registry discovery service."""
    
    def __init__(self, config):
        """Initialize NPM discovery with configuration."""
        self.config = config
    
    async def discover_servers(
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
                                    install_args=["-y", name, "--"],
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
                
        except Exception as e:
            logger.error(f"NPM discovery failed: {e}")
            return []
    
    def _is_mcp_package(
        self,
        name: str,
        description: str,
        keywords: List[str]
    ) -> bool:
        """Check if a package is an MCP server."""
        # MCP indicators
        mcp_indicators = [
            "mcp",
            "model-context-protocol", 
            "claude-mcp",
            "anthropic-mcp",
            "@modelcontextprotocol"
        ]
        
        # Check package name
        name_lower = name.lower()
        for indicator in mcp_indicators:
            if indicator in name_lower:
                return True
        
        # Check description
        desc_lower = description.lower()
        for indicator in mcp_indicators:
            if indicator in desc_lower:
                return True
        
        # Check keywords
        keywords_lower = [k.lower() for k in keywords]
        for indicator in mcp_indicators:
            if indicator in keywords_lower:
                return True
        
        # Additional patterns
        mcp_patterns = [
            "mcp server",
            "context protocol",
            "claude server",
            "anthropic server"
        ]
        
        combined_text = f"{name_lower} {desc_lower} {' '.join(keywords_lower)}"
        for pattern in mcp_patterns:
            if pattern in combined_text:
                return True
        
        return False
    
    def _extract_server_name(self, package_name: str) -> str:
        """Extract server name from package name."""
        # Remove common prefixes/suffixes
        name = package_name
        
        # Remove scope if present (e.g., @org/package -> package)
        if name.startswith('@'):
            name = name.split('/')[-1]
        
        # Remove common prefixes
        prefixes = ['mcp-', 'claude-mcp-', 'anthropic-mcp-', 'modelcontextprotocol-']
        for prefix in prefixes:
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
        
        # Remove common suffixes
        suffixes = ['-mcp', '-server', '-mcp-server']
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)]
                break
        
        return name or package_name
    
    def _get_author_name(self, author: Any) -> Optional[str]:
        """Extract author name from various author formats."""
        if isinstance(author, dict):
            return author.get("name")
        elif isinstance(author, str):
            return author
        return None
    
    def _get_repo_url(self, links: Dict[str, Any]) -> Optional[str]:
        """Extract repository URL from links."""
        if isinstance(links, dict):
            return links.get("repository")
        return None
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None
        
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except ValueError:
            return None