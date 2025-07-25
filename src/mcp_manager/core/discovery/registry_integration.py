"""
Discovery to Registry Integration

Connects discovery system to server registry for automated server registration.
Single responsibility: Bridge discovery results to database storage.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set

from ..database.registry import MCPServerRegistry, MCPServerInfo
from ..database.connection import get_database_connection
from ..discovery import ServerDiscovery
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class DiscoveryRegistryIntegrator:
    """Integrates discovery system with server registry."""
    
    def __init__(self):
        """Initialize integrator."""
        self.registry = MCPServerRegistry()
        self.discovery = ServerDiscovery()
        self.db_connection = get_database_connection()
        
    async def discover_and_register_servers(self, server_names: List[str], 
                                          force_refresh: bool = False) -> Dict[str, bool]:
        """Discover servers and register them in the database."""
        results = {}
        
        logger.info(f"🔍 Discovering and registering {len(server_names)} servers...")
        
        for server_name in server_names:
            try:
                # Check if server needs discovery (not in cache or expired)
                if not force_refresh and await self._is_server_cached(server_name):
                    logger.debug(f"Server {server_name} already cached, skipping discovery")
                    results[server_name] = True
                    continue
                
                # Discover server details
                server_info = await self._discover_server_details(server_name)
                if server_info:
                    # Register in database
                    success = await self.registry.register_server(server_info)
                    results[server_name] = success
                    
                    # Cache discovery result
                    if success:
                        await self._cache_discovery_result(server_name, server_info)
                else:
                    logger.warning(f"Could not discover details for server: {server_name}")
                    results[server_name] = False
                    
            except Exception as e:
                logger.error(f"Failed to discover/register server {server_name}: {e}")
                results[server_name] = False
        
        successful = sum(1 for success in results.values() if success)
        logger.info(f"✅ Successfully registered {successful}/{len(server_names)} servers")
        
        return results
    
    async def _discover_server_details(self, server_name: str) -> Optional[MCPServerInfo]:
        """Discover detailed information about a server."""
        try:
            # Determine server type and discovery method
            server_type, discovery_method = self._determine_server_type(server_name)
            
            if server_type == 'npm':
                return await self._discover_npm_server(server_name)
            elif server_type == 'docker-desktop':
                return await self._discover_docker_desktop_server(server_name)
            elif server_type == 'docker':
                return await self._discover_docker_server(server_name)
            else:
                # Create basic server info for unknown types
                return MCPServerInfo(
                    server_name=server_name,
                    description=f"Custom MCP server: {server_name}",
                    server_type='custom',
                    install_command='',
                    discovery_metadata={'discovered_at': datetime.now().isoformat()}
                )
                
        except Exception as e:
            logger.error(f"Failed to discover server {server_name}: {e}")
            return None
    
    async def _discover_npm_server(self, server_name: str) -> Optional[MCPServerInfo]:
        """Discover NPM server details."""
        try:
            # Use existing discovery system
            discovery_results = await self.discovery.discover_servers(
                query=server_name,
                server_type='npm',
                limit=1
            )
            
            if not discovery_results:
                logger.warning(f"No NPM discovery results for {server_name}")
                return None
            
            result = discovery_results[0]
            
            return MCPServerInfo(
                server_name=server_name,
                description=result.description or f"NPM MCP server: {server_name}",
                server_type='npm',
                install_command=f"npx -y {server_name}",
                package_name=server_name,
                version=getattr(result, 'version', None),
                author=getattr(result, 'author', None),
                repository_url=getattr(result, 'repository_url', None),
                documentation_url=getattr(result, 'documentation_url', None),
                tags=getattr(result, 'tags', []),
                discovery_metadata={
                    'discovery_source': 'npm_registry',
                    'discovery_date': datetime.now().isoformat(),
                    'raw_result': result.__dict__ if hasattr(result, '__dict__') else str(result)
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to discover NPM server {server_name}: {e}")
            return None
    
    async def _discover_docker_desktop_server(self, server_name: str) -> Optional[MCPServerInfo]:
        """Discover Docker Desktop server details."""
        try:
            # Use existing discovery system for Docker Desktop
            discovery_results = await self.discovery.discover_servers(
                query=server_name.replace('dd-', ''),  # Remove dd- prefix
                server_type='docker-desktop',
                limit=1
            )
            
            if not discovery_results:
                logger.warning(f"No Docker Desktop discovery results for {server_name}")
                # Create basic info for known DD servers
                return self._create_docker_desktop_fallback(server_name)
            
            result = discovery_results[0]
            
            return MCPServerInfo(
                server_name=server_name,
                description=result.description or f"Docker Desktop MCP server: {server_name}",
                server_type='docker-desktop',
                install_command=f"docker-desktop://{server_name.replace('dd-', '')}",
                package_name=server_name.replace('dd-', ''),
                discovery_metadata={
                    'discovery_source': 'docker_desktop',
                    'discovery_date': datetime.now().isoformat(),
                    'raw_result': result.__dict__ if hasattr(result, '__dict__') else str(result)
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to discover Docker Desktop server {server_name}: {e}")
            return self._create_docker_desktop_fallback(server_name)
    
    def _create_docker_desktop_fallback(self, server_name: str) -> MCPServerInfo:
        """Create fallback info for known Docker Desktop servers."""
        descriptions = {
            'dd-SQLite': 'SQLite database operations and business intelligence',
            'dd-Ref': 'Powerful search tool connecting coding to documentation',
            'dd-Filesystem': 'File system operations through Docker Desktop',
        }
        
        return MCPServerInfo(
            server_name=server_name,
            description=descriptions.get(server_name, f"Docker Desktop MCP server: {server_name}"),
            server_type='docker-desktop',
            install_command=f"docker-desktop://{server_name.replace('dd-', '')}",
            package_name=server_name.replace('dd-', ''),
            tags=['docker-desktop', 'official'],
            discovery_metadata={
                'discovery_source': 'fallback',
                'discovery_date': datetime.now().isoformat(),
                'note': 'Created from known Docker Desktop server list'
            }
        )
    
    async def _discover_docker_server(self, server_name: str) -> Optional[MCPServerInfo]:
        """Discover Docker Hub server details."""
        try:
            # Use existing discovery system
            discovery_results = await self.discovery.discover_servers(
                query=server_name,
                server_type='docker',
                limit=1
            )
            
            if not discovery_results:
                logger.warning(f"No Docker discovery results for {server_name}")
                return None
            
            result = discovery_results[0]
            
            return MCPServerInfo(
                server_name=server_name,
                description=result.description or f"Docker MCP server: {server_name}",
                server_type='docker',
                install_command=f"docker run {server_name}",
                package_name=server_name,
                discovery_metadata={
                    'discovery_source': 'docker_hub',
                    'discovery_date': datetime.now().isoformat(),
                    'raw_result': result.__dict__ if hasattr(result, '__dict__') else str(result)
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to discover Docker server {server_name}: {e}")
            return None
    
    def _determine_server_type(self, server_name: str) -> tuple[str, str]:
        """Determine server type from server name."""
        if server_name.startswith('@') or '/' in server_name:
            return 'npm', 'npm_registry'
        elif server_name.startswith('dd-'):
            return 'docker-desktop', 'docker_desktop'
        elif ':' in server_name or server_name.count('/') >= 1:
            return 'docker', 'docker_hub'
        else:
            return 'custom', 'unknown'
    
    async def _is_server_cached(self, server_name: str, max_age_hours: int = 24) -> bool:
        """Check if server is already cached and not expired."""
        try:
            server_info = await self.registry.get_server(server_name)
            if not server_info or not server_info.last_discovered:
                return False
            
            # Check if discovery is recent enough
            age_threshold = datetime.now() - timedelta(hours=max_age_hours)
            return server_info.last_discovered > age_threshold
            
        except Exception as e:
            logger.error(f"Failed to check cache for {server_name}: {e}")
            return False
    
    async def _cache_discovery_result(self, server_name: str, server_info: MCPServerInfo):
        """Cache discovery result for performance."""
        try:
            async with self.db_connection.get_connection() as conn:
                cache_key = f"{server_info.server_type}:{server_name}"
                expires_at = datetime.now() + timedelta(hours=24)
                
                await conn.execute("""
                    INSERT OR REPLACE INTO discovery_cache (
                        cache_key, server_type, raw_data, cached_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    cache_key,
                    server_info.server_type,
                    json.dumps(server_info.discovery_metadata),
                    datetime.now().isoformat(),
                    expires_at.isoformat()
                ))
                
        except Exception as e:
            logger.error(f"Failed to cache discovery result for {server_name}: {e}")
    
    async def cleanup_expired_cache(self) -> int:
        """Clean up expired cache entries."""
        try:
            async with self.db_connection.get_connection() as conn:
                result = await conn.execute("""
                    DELETE FROM discovery_cache 
                    WHERE expires_at < ?
                """, (datetime.now().isoformat(),))
                
                # Get count of deleted rows (SQLite doesn't return this directly)
                result = await conn.execute("SELECT changes()")
                count = await result.fetchone()
                deleted_count = count[0] if count else 0
                
                if deleted_count > 0:
                    logger.info(f"🧹 Cleaned up {deleted_count} expired cache entries")
                
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired cache: {e}")
            return 0
    
    async def bulk_discover_from_suites(self, force_refresh: bool = False) -> Dict[str, int]:
        """Discover all servers referenced in existing suites."""
        try:
            async with self.db_connection.get_connection() as conn:
                # Get all unique server names from suite memberships
                result = await conn.execute("""
                    SELECT DISTINCT server_name FROM suite_memberships
                """)
                rows = await result.fetchall()
                
                server_names = [row[0] for row in rows]
                
                if not server_names:
                    logger.info("No servers found in suites to discover")
                    return {'discovered': 0, 'failed': 0}
                
                logger.info(f"🔍 Bulk discovering {len(server_names)} servers from suites")
                
                # Discover and register all servers
                results = await self.discover_and_register_servers(server_names, force_refresh)
                
                successful = sum(1 for success in results.values() if success)
                failed = len(results) - successful
                
                return {'discovered': successful, 'failed': failed}
                
        except Exception as e:
            logger.error(f"Failed bulk discovery from suites: {e}")
            return {'discovered': 0, 'failed': 1}