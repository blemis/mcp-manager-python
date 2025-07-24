"""
Server membership management for MCP Suite Management System.

Handles operations related to server membership in suites.
"""

import json
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple

from .database import SuiteDatabase
from mcp_manager.core.models import Server
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class MembershipManager:
    """Manages server membership operations in suites."""
    
    def __init__(self, db: SuiteDatabase):
        """Initialize membership manager with database instance."""
        self.db = db
    
    async def add_server_to_suite(self, suite_id: str, server_name: str, role: str = "member",
                                priority: int = 50, config_overrides: Optional[Dict[str, Any]] = None) -> bool:
        """Add a server to a suite with specified role and priority."""
        try:
            config_overrides = config_overrides or {}
            now = datetime.now().isoformat()
            
            with self.db.get_connection() as conn:
                # Check if suite exists
                cursor = conn.execute("SELECT id FROM mcp_suites WHERE id = ?", (suite_id,))
                if not cursor.fetchone():
                    logger.error(f"Suite {suite_id} does not exist")
                    return False
                
                # Insert or update membership
                conn.execute("""
                    INSERT OR REPLACE INTO suite_memberships 
                    (suite_id, server_name, role, priority, config_overrides, added_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (suite_id, server_name, role, priority, json.dumps(config_overrides), now))
                
                # Update suite's updated_at timestamp
                conn.execute("UPDATE mcp_suites SET updated_at = ? WHERE id = ?", (now, suite_id))
                
                conn.commit()
                logger.info(f"Added {server_name} to suite {suite_id} as {role}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to add server {server_name} to suite {suite_id}: {e}")
            return False
    
    async def remove_server_from_suite(self, suite_id: str, server_name: str) -> bool:
        """Remove a server from a suite."""
        try:
            with self.db.get_connection() as conn:
                # Remove membership
                cursor = conn.execute("""
                    DELETE FROM suite_memberships 
                    WHERE suite_id = ? AND server_name = ?
                """, (suite_id, server_name))
                
                if cursor.rowcount == 0:
                    logger.warning(f"Server {server_name} not found in suite {suite_id}")
                    return False
                
                # Update suite's updated_at timestamp
                now = datetime.now().isoformat()
                conn.execute("UPDATE mcp_suites SET updated_at = ? WHERE id = ?", (now, suite_id))
                
                conn.commit()
                logger.info(f"Removed {server_name} from suite {suite_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to remove server {server_name} from suite {suite_id}: {e}")
            return False
    
    async def get_server_suites(self, server_name: str) -> List[Tuple[str, str, str, int]]:
        """Get all suites that contain a specific server."""
        try:
            with self.db.get_row_connection() as conn:
                cursor = conn.execute("""
                    SELECT s.id, s.name, sm.role, sm.priority
                    FROM mcp_suites s
                    JOIN suite_memberships sm ON s.id = sm.suite_id
                    WHERE sm.server_name = ?
                    ORDER BY sm.priority DESC
                """, (server_name,))
                
                results = []
                for row in cursor.fetchall():
                    results.append((row['id'], row['name'], row['role'], row['priority']))
                
                return results
                
        except Exception as e:
            logger.error(f"Failed to get suites for server {server_name}: {e}")
            return []
    
    async def update_server_suites_field(self, server: Server) -> bool:
        """Update a server's suites field based on database memberships."""
        try:
            # Get all suites for this server
            suites_info = await self.get_server_suites(server.name)
            suite_ids = [suite_id for suite_id, _, _, _ in suites_info]
            
            # Update the server's suites field
            server.suites = suite_ids
            
            logger.debug(f"Updated server {server.name} suites field: {suite_ids}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update server suites field for {server.name}: {e}")
            return False
    
    async def sync_all_server_suites(self, servers: List[Server]) -> int:
        """Sync the suites field for all servers based on database."""
        try:
            updated_count = 0
            
            for server in servers:
                success = await self.update_server_suites_field(server)
                if success:
                    updated_count += 1
            
            logger.info(f"Synced suites field for {updated_count}/{len(servers)} servers")
            return updated_count
            
        except Exception as e:
            logger.error(f"Failed to sync server suites: {e}")
            return 0
    
    async def cleanup_orphaned_memberships(self) -> int:
        """Remove memberships for suites that no longer exist."""
        try:
            with self.db.get_connection() as conn:
                # Remove memberships without corresponding suites
                cursor = conn.execute("""
                    DELETE FROM suite_memberships 
                    WHERE suite_id NOT IN (SELECT id FROM mcp_suites)
                """)
                
                removed_count = cursor.rowcount
                conn.commit()
                
                if removed_count > 0:
                    logger.info(f"Cleaned up {removed_count} orphaned suite memberships")
                
                return removed_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned memberships: {e}")
            return 0