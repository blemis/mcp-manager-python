"""
Docker Hub and Docker Desktop discovery for MCP servers.
"""

import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from mcp_manager.core.models import DiscoveryResult, ServerType
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class DockerDiscovery:
    """Docker discovery service for Hub and Desktop servers."""
    
    def __init__(self, config):
        """Initialize Docker discovery with configuration."""
        self.config = config
    
    async def discover_docker_hub_servers(
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
    
    async def discover_docker_desktop_servers(
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
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None
            
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None
            
    async def update_docker_catalog(self) -> bool:
        """Update Docker MCP catalog using docker mcp catalog update."""
        try:
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
            return True
            
        except Exception as e:
            logger.warning(f"Failed to update Docker MCP catalog: {e}")
            return False