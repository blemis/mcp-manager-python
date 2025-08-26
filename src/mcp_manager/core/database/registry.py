"""
MCP Server Registry Manager

Handles server registration and discovery integration.
Single responsibility: Server registry CRUD operations.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .connection import get_database_connection
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MCPServerInfo:
    """Represents an MCP server in the registry."""
    server_name: str
    description: str
    server_type: str
    install_command: str
    package_name: Optional[str] = None
    discovery_metadata: Dict[str, Any] = None
    version: Optional[str] = None
    author: Optional[str] = None
    repository_url: Optional[str] = None
    documentation_url: Optional[str] = None
    tags: List[str] = None
    last_discovered: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.discovery_metadata is None:
            self.discovery_metadata = {}
        if self.tags is None:
            self.tags = []


class MCPServerRegistry:
    """Manages the MCP server registry with discovery integration."""
    
    def __init__(self):
        """Initialize registry manager."""
        self.db_connection = get_database_connection()
    
    async def register_server(self, server_info: MCPServerInfo) -> bool:
        """Register a new server or update existing one."""
        try:
            async with self.db_connection.get_connection() as conn:
                now = datetime.now().isoformat()
                
                await conn.execute("""
                    INSERT OR REPLACE INTO mcp_server_registry (
                        server_name, description, server_type, install_command,
                        package_name, discovery_metadata, version, author,
                        repository_url, documentation_url, tags,
                        last_discovered, updated_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                             COALESCE((SELECT created_at FROM mcp_server_registry WHERE server_name = ?), ?))
                """, (
                    server_info.server_name,
                    server_info.description,
                    server_info.server_type,
                    server_info.install_command,
                    server_info.package_name,
                    json.dumps(server_info.discovery_metadata),
                    server_info.version,
                    server_info.author,
                    server_info.repository_url,
                    server_info.documentation_url,
                    json.dumps(server_info.tags),
                    now,
                    now,
                    server_info.server_name,  # For COALESCE check
                    now  # Default created_at if new
                ))
                
                logger.info(f"✅ Registered server: {server_info.server_name}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to register server {server_info.server_name}: {e}")
            return False
    
    async def get_server(self, server_name: str) -> Optional[MCPServerInfo]:
        """Get server information by name."""
        try:
            async with self.db_connection.get_connection() as conn:
                result = await conn.execute("""
                    SELECT * FROM mcp_server_registry WHERE server_name = ?
                """, (server_name,))
                row = await result.fetchone()
                
                if row:
                    return MCPServerInfo(
                        server_name=row[0],
                        description=row[1],
                        server_type=row[2],
                        install_command=row[3],
                        package_name=row[4],
                        discovery_metadata=json.loads(row[5]) if row[5] else {},
                        version=row[6],
                        author=row[7],
                        repository_url=row[8],
                        documentation_url=row[9],
                        tags=json.loads(row[10]) if row[10] else [],
                        last_discovered=datetime.fromisoformat(row[11]) if row[11] else None,
                        created_at=datetime.fromisoformat(row[12]) if row[12] else None,
                        updated_at=datetime.fromisoformat(row[13]) if row[13] else None
                    )
                return None
                
        except Exception as e:
            logger.error(f"Failed to get server {server_name}: {e}")
            return None
    
    async def list_servers(self, server_type: Optional[str] = None, 
                          include_metadata: bool = False) -> List[MCPServerInfo]:
        """List all registered servers."""
        try:
            async with self.db_connection.get_connection() as conn:
                query = "SELECT * FROM mcp_server_registry"
                params = []
                
                if server_type:
                    query += " WHERE server_type = ?"
                    params.append(server_type)
                
                query += " ORDER BY server_name"
                
                result = await conn.execute(query, params)
                rows = await result.fetchall()
                
                servers = []
                for row in rows:
                    server = MCPServerInfo(
                        server_name=row[0],
                        description=row[1],
                        server_type=row[2],
                        install_command=row[3],
                        package_name=row[4],
                        discovery_metadata=json.loads(row[5]) if row[5] and include_metadata else {},
                        version=row[6],
                        author=row[7],
                        repository_url=row[8],
                        documentation_url=row[9],
                        tags=json.loads(row[10]) if row[10] else [],
                        last_discovered=datetime.fromisoformat(row[11]) if row[11] else None,
                        created_at=datetime.fromisoformat(row[12]) if row[12] else None,
                        updated_at=datetime.fromisoformat(row[13]) if row[13] else None
                    )
                    servers.append(server)
                
                return servers
                
        except Exception as e:
            logger.error(f"Failed to list servers: {e}")
            return []
    
    async def search_servers(self, query: str, server_type: Optional[str] = None) -> List[MCPServerInfo]:
        """Search servers by name, description, or tags."""
        try:
            async with self.db_connection.get_connection() as conn:
                sql_query = """
                    SELECT * FROM mcp_server_registry 
                    WHERE (server_name LIKE ? OR description LIKE ? OR tags LIKE ?)
                """
                params = [f"%{query}%", f"%{query}%", f"%{query}%"]
                
                if server_type:
                    sql_query += " AND server_type = ?"
                    params.append(server_type)
                
                sql_query += " ORDER BY server_name"
                
                result = await conn.execute(sql_query, params)
                rows = await result.fetchall()
                
                servers = []
                for row in rows:
                    server = MCPServerInfo(
                        server_name=row[0],
                        description=row[1],
                        server_type=row[2],
                        install_command=row[3],
                        package_name=row[4],
                        discovery_metadata=json.loads(row[5]) if row[5] else {},
                        version=row[6],
                        author=row[7],
                        repository_url=row[8],
                        documentation_url=row[9],
                        tags=json.loads(row[10]) if row[10] else [],
                        last_discovered=datetime.fromisoformat(row[11]) if row[11] else None,
                        created_at=datetime.fromisoformat(row[12]) if row[12] else None,
                        updated_at=datetime.fromisoformat(row[13]) if row[13] else None
                    )
                    servers.append(server)
                
                return servers
                
        except Exception as e:
            logger.error(f"Failed to search servers: {e}")
            return []
    
    async def remove_server(self, server_name: str) -> bool:
        """Remove a server from the registry."""
        try:
            async with self.db_connection.get_connection() as conn:
                # Check if server is used in any suites
                result = await conn.execute("""
                    SELECT COUNT(*) FROM suite_memberships WHERE server_name = ?
                """, (server_name,))
                count = await result.fetchone()
                
                if count and count[0] > 0:
                    logger.warning(f"Cannot remove server {server_name}: used in {count[0]} suites")
                    return False
                
                # Remove from registry
                await conn.execute("""
                    DELETE FROM mcp_server_registry WHERE server_name = ?
                """, (server_name,))
                
                logger.info(f"✅ Removed server: {server_name}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to remove server {server_name}: {e}")
            return False
    
    async def get_registry_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        try:
            async with self.db_connection.get_connection() as conn:
                stats = {}
                
                # Total servers
                result = await conn.execute("SELECT COUNT(*) FROM mcp_server_registry")
                count = await result.fetchone()
                stats['total_servers'] = count[0] if count else 0
                
                # Servers by type
                result = await conn.execute("""
                    SELECT server_type, COUNT(*) 
                    FROM mcp_server_registry 
                    GROUP BY server_type
                """)
                rows = await result.fetchall()
                stats['servers_by_type'] = {row[0]: row[1] for row in rows}
                
                # Recently discovered (last 24 hours)
                yesterday = (datetime.now() - timedelta(days=1)).isoformat()
                result = await conn.execute("""
                    SELECT COUNT(*) FROM mcp_server_registry 
                    WHERE last_discovered > ?
                """, (yesterday,))
                count = await result.fetchone()
                stats['recently_discovered'] = count[0] if count else 0
                
                # Most used servers (in suites)
                result = await conn.execute("""
                    SELECT sm.server_name, COUNT(*) as usage_count
                    FROM suite_memberships sm
                    JOIN mcp_server_registry r ON sm.server_name = r.server_name
                    GROUP BY sm.server_name
                    ORDER BY usage_count DESC
                    LIMIT 5
                """)
                rows = await result.fetchall()
                stats['most_used_servers'] = [{'name': row[0], 'usage_count': row[1]} for row in rows]
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get registry stats: {e}")
            return {}