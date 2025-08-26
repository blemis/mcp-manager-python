"""
MCP Suite Manager

Handles suite operations with server registry integration.
Single responsibility: Suite CRUD operations and server management.
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .connection import get_database_connection
from .registry import MCPServerInfo
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass 
class SuiteMembership:
    """Represents a server's membership in a suite."""
    suite_id: str
    server_name: str
    role: str = "member"
    priority: int = 50
    suite_specific_config: Dict[str, Any] = None
    notes: Optional[str] = None
    added_at: Optional[datetime] = None
    added_by: str = "system"
    
    def __post_init__(self):
        if self.suite_specific_config is None:
            self.suite_specific_config = {}


@dataclass
class MCPSuite:
    """Represents an MCP server suite."""
    id: str
    name: str
    description: str
    category: Optional[str] = None
    purpose: Optional[str] = None
    config: Dict[str, Any] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: str = "system"
    memberships: List[SuiteMembership] = None
    
    def __post_init__(self):
        if self.config is None:
            self.config = {}
        if self.memberships is None:
            self.memberships = []


class MCPSuiteManager:
    """Manages MCP server suites with registry integration."""
    
    def __init__(self):
        """Initialize suite manager."""
        self.db_connection = get_database_connection()
    
    async def create_suite(self, suite: MCPSuite) -> bool:
        """Create a new suite."""
        try:
            async with self.db_connection.get_connection() as conn:
                now = datetime.now().isoformat()
                
                await conn.execute("""
                    INSERT INTO mcp_suites (
                        id, name, description, category, purpose, config,
                        created_at, updated_at, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    suite.id,
                    suite.name,
                    suite.description,
                    suite.category,
                    suite.purpose,
                    json.dumps(suite.config),
                    now,
                    now,
                    suite.created_by
                ))
                
                logger.info(f"✅ Created suite: {suite.id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to create suite {suite.id}: {e}")
            return False
    
    async def get_suite(self, suite_id: str, include_servers: bool = True) -> Optional[MCPSuite]:
        """Get suite with optional server details."""
        try:
            async with self.db_connection.get_connection() as conn:
                # Get suite info
                result = await conn.execute("""
                    SELECT * FROM mcp_suites WHERE id = ?
                """, (suite_id,))
                suite_row = await result.fetchone()
                
                if not suite_row:
                    return None
                
                # Create suite object
                suite = MCPSuite(
                    id=suite_row[0],
                    name=suite_row[1],
                    description=suite_row[2],
                    category=suite_row[3],
                    purpose=suite_row[4],
                    config=json.loads(suite_row[5]) if suite_row[5] else {},
                    created_at=datetime.fromisoformat(suite_row[6]) if suite_row[6] else None,
                    updated_at=datetime.fromisoformat(suite_row[7]) if suite_row[7] else None,
                    created_by=suite_row[8]
                )
                
                if include_servers:
                    # Get memberships
                    result = await conn.execute("""
                        SELECT * FROM suite_memberships 
                        WHERE suite_id = ? 
                        ORDER BY priority DESC, added_at ASC
                    """, (suite_id,))
                    membership_rows = await result.fetchall()
                    
                    memberships = []
                    for row in membership_rows:
                        membership = SuiteMembership(
                            suite_id=row[0],
                            server_name=row[1],
                            role=row[2],
                            priority=row[3],
                            suite_specific_config=json.loads(row[4]) if row[4] else {},
                            notes=row[5],
                            added_at=datetime.fromisoformat(row[6]) if row[6] else None,
                            added_by=row[7]
                        )
                        memberships.append(membership)
                    
                    suite.memberships = memberships
                
                return suite
                
        except Exception as e:
            logger.error(f"Failed to get suite {suite_id}: {e}")
            return None
    
    async def list_suites(self, category: Optional[str] = None) -> List[MCPSuite]:
        """List all suites."""
        try:
            async with self.db_connection.get_connection() as conn:
                query = "SELECT * FROM mcp_suites"
                params = []
                
                if category:
                    query += " WHERE category = ?"
                    params.append(category)
                
                query += " ORDER BY name"
                
                result = await conn.execute(query, params)
                rows = await result.fetchall()
                
                suites = []
                for row in rows:
                    suite = MCPSuite(
                        id=row[0],
                        name=row[1],
                        description=row[2],
                        category=row[3],
                        purpose=row[4],
                        config=json.loads(row[5]) if row[5] else {},
                        created_at=datetime.fromisoformat(row[6]) if row[6] else None,
                        updated_at=datetime.fromisoformat(row[7]) if row[7] else None,
                        created_by=row[8]
                    )
                    suites.append(suite)
                
                return suites
                
        except Exception as e:
            logger.error(f"Failed to list suites: {e}")
            return []
    
    async def add_server_to_suite(self, suite_id: str, server_name: str, 
                                 role: str = "member", priority: int = 50,
                                 suite_config: Optional[Dict] = None,
                                 notes: Optional[str] = None) -> bool:
        """Add a server to a suite."""
        try:
            async with self.db_connection.get_connection() as conn:
                # Verify server exists in registry
                result = await conn.execute("""
                    SELECT server_name FROM mcp_server_registry WHERE server_name = ?
                """, (server_name,))
                if not await result.fetchone():
                    logger.error(f"Server {server_name} not found in registry")
                    return False
                
                # Verify suite exists
                result = await conn.execute("""
                    SELECT id FROM mcp_suites WHERE id = ?
                """, (suite_id,))
                if not await result.fetchone():
                    logger.error(f"Suite {suite_id} not found")
                    return False
                
                # Add membership
                await conn.execute("""
                    INSERT OR REPLACE INTO suite_memberships (
                        suite_id, server_name, role, priority, suite_specific_config,
                        notes, added_at, added_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    suite_id,
                    server_name,
                    role,
                    priority,
                    json.dumps(suite_config or {}),
                    notes,
                    datetime.now().isoformat(),
                    "api"
                ))
                
                logger.info(f"✅ Added {server_name} to suite {suite_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to add server {server_name} to suite {suite_id}: {e}")
            return False
    
    async def remove_server_from_suite(self, suite_id: str, server_name: str) -> bool:
        """Remove a server from a suite."""
        try:
            async with self.db_connection.get_connection() as conn:
                await conn.execute("""
                    DELETE FROM suite_memberships 
                    WHERE suite_id = ? AND server_name = ?
                """, (suite_id, server_name))
                
                logger.info(f"✅ Removed {server_name} from suite {suite_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to remove server {server_name} from suite {suite_id}: {e}")
            return False
    
    async def get_suite_with_server_details(self, suite_id: str) -> Optional[Dict[str, Any]]:
        """Get suite with full server registry details for deployment."""
        try:
            async with self.db_connection.get_connection() as conn:
                # Get suite and server details in one query
                result = await conn.execute("""
                    SELECT 
                        s.id, s.name, s.description, s.category, s.purpose,
                        r.server_name, r.description as server_desc, r.server_type,
                        r.install_command, r.package_name, r.discovery_metadata,
                        sm.role, sm.priority, sm.suite_specific_config, sm.notes
                    FROM mcp_suites s
                    JOIN suite_memberships sm ON s.id = sm.suite_id
                    JOIN mcp_server_registry r ON sm.server_name = r.server_name
                    WHERE s.id = ?
                    ORDER BY sm.priority DESC, sm.added_at ASC
                """, (suite_id,))
                
                rows = await result.fetchall()
                if not rows:
                    return None
                
                # Build response with suite info and servers
                first_row = rows[0]
                suite_info = {
                    'id': first_row[0],
                    'name': first_row[1],
                    'description': first_row[2],
                    'category': first_row[3],
                    'purpose': first_row[4],
                    'servers': []
                }
                
                for row in rows:
                    server_info = {
                        'server_name': row[5],
                        'description': row[6],
                        'server_type': row[7],
                        'install_command': row[8],
                        'package_name': row[9],
                        'discovery_metadata': json.loads(row[10]) if row[10] else {},
                        'role': row[11],
                        'priority': row[12],
                        'suite_config': json.loads(row[13]) if row[13] else {},
                        'notes': row[14]
                    }
                    suite_info['servers'].append(server_info)
                
                return suite_info
                
        except Exception as e:
            logger.error(f"Failed to get suite with server details {suite_id}: {e}")
            return None
    
    async def delete_suite(self, suite_id: str) -> bool:
        """Delete a suite and all its memberships."""
        try:
            async with self.db_connection.get_connection() as conn:
                # Foreign key constraints will handle cascade delete
                await conn.execute("DELETE FROM mcp_suites WHERE id = ?", (suite_id,))
                logger.info(f"✅ Deleted suite: {suite_id}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to delete suite {suite_id}: {e}")
            return False
    
    async def get_suite_stats(self) -> Dict[str, Any]:
        """Get suite statistics."""
        try:
            async with self.db_connection.get_connection() as conn:
                stats = {}
                
                # Total suites
                result = await conn.execute("SELECT COUNT(*) FROM mcp_suites")
                count = await result.fetchone()
                stats['total_suites'] = count[0] if count else 0
                
                # Suites by category
                result = await conn.execute("""
                    SELECT category, COUNT(*) 
                    FROM mcp_suites 
                    WHERE category IS NOT NULL
                    GROUP BY category
                """)
                rows = await result.fetchall()
                stats['suites_by_category'] = {row[0]: row[1] for row in rows}
                
                # Average servers per suite
                result = await conn.execute("""
                    SELECT AVG(server_count) FROM (
                        SELECT COUNT(*) as server_count 
                        FROM suite_memberships 
                        GROUP BY suite_id
                    )
                """)
                avg = await result.fetchone()
                stats['avg_servers_per_suite'] = round(avg[0], 2) if avg and avg[0] else 0
                
                # Most complex suites
                result = await conn.execute("""
                    SELECT s.name, COUNT(sm.server_name) as server_count
                    FROM mcp_suites s
                    JOIN suite_memberships sm ON s.id = sm.suite_id
                    GROUP BY s.id, s.name
                    ORDER BY server_count DESC
                    LIMIT 5
                """)
                rows = await result.fetchall()
                stats['most_complex_suites'] = [{'name': row[0], 'server_count': row[1]} for row in rows]
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get suite stats: {e}")
            return {}