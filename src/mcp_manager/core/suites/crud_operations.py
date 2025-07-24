"""
Suite CRUD operations for MCP Suite Management System.

Handles create, read, update, delete operations for suites.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from .database import SuiteDatabase
from .models import Suite, SuiteMembership
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class SuiteCRUDOperations:
    """Handles CRUD operations for suites."""
    
    def __init__(self, db: SuiteDatabase):
        """Initialize CRUD operations with database instance."""
        self.db = db
    
    async def create_or_update_suite(self, suite_id: str, name: str, description: str = "",
                                   category: str = "", config: Optional[Dict[str, Any]] = None) -> bool:
        """Create a new suite or update an existing one."""
        try:
            config = config or {}
            now = datetime.now().isoformat()
            
            with self.db.get_connection() as conn:
                # Check if suite exists
                cursor = conn.execute("SELECT id, created_at FROM mcp_suites WHERE id = ?", (suite_id,))
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing suite
                    conn.execute("""
                        UPDATE mcp_suites 
                        SET name = ?, description = ?, category = ?, config = ?, updated_at = ?
                        WHERE id = ?
                    """, (name, description, category, json.dumps(config), now, suite_id))
                    logger.info(f"Updated suite {suite_id}")
                else:
                    # Create new suite
                    conn.execute("""
                        INSERT INTO mcp_suites (id, name, description, category, config, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (suite_id, name, description, category, json.dumps(config), now, now))
                    logger.info(f"Created suite {suite_id}")
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to create/update suite {suite_id}: {e}")
            return False
    
    async def get_suite(self, suite_id: str) -> Optional[Suite]:
        """Get a complete suite with all memberships."""
        try:
            with self.db.get_row_connection() as conn:
                # Get suite info
                cursor = conn.execute("SELECT * FROM mcp_suites WHERE id = ?", (suite_id,))
                suite_row = cursor.fetchone()
                
                if not suite_row:
                    return None
                
                # Get memberships
                cursor = conn.execute("""
                    SELECT * FROM suite_memberships WHERE suite_id = ?
                    ORDER BY priority DESC, added_at ASC
                """, (suite_id,))
                membership_rows = cursor.fetchall()
                
                # Build memberships
                memberships = []
                for row in membership_rows:
                    membership = SuiteMembership(
                        suite_id=row['suite_id'],
                        server_name=row['server_name'],
                        role=row['role'],
                        priority=row['priority'],
                        config_overrides=json.loads(row['config_overrides']),
                        added_at=datetime.fromisoformat(row['added_at'])
                    )
                    memberships.append(membership)
                
                # Build suite
                suite = Suite(
                    id=suite_row['id'],
                    name=suite_row['name'],
                    description=suite_row['description'],
                    category=suite_row['category'],
                    config=json.loads(suite_row['config']),
                    created_at=datetime.fromisoformat(suite_row['created_at']),
                    updated_at=datetime.fromisoformat(suite_row['updated_at']),
                    memberships=memberships
                )
                
                return suite
                
        except Exception as e:
            logger.error(f"Failed to get suite {suite_id}: {e}")
            return None
    
    async def list_suites(self, category: Optional[str] = None) -> List[Suite]:
        """List all suites, optionally filtered by category."""
        try:
            suites = []
            
            with self.db.get_row_connection() as conn:
                # Build query
                if category:
                    query = "SELECT * FROM mcp_suites WHERE category = ? ORDER BY name"
                    params = (category,)
                else:
                    query = "SELECT * FROM mcp_suites ORDER BY name"
                    params = ()
                
                cursor = conn.execute(query, params)
                suite_rows = cursor.fetchall()
                
                # Get each suite with memberships
                for suite_row in suite_rows:
                    suite = await self.get_suite(suite_row['id'])
                    if suite:
                        suites.append(suite)
                
                return suites
                
        except Exception as e:
            logger.error(f"Failed to list suites: {e}")
            return []
    
    async def delete_suite(self, suite_id: str) -> bool:
        """Delete a suite and all its memberships."""
        try:
            with self.db.get_connection() as conn:
                # Delete suite (memberships will be cascade deleted)
                cursor = conn.execute("DELETE FROM mcp_suites WHERE id = ?", (suite_id,))
                
                if cursor.rowcount == 0:
                    logger.warning(f"Suite {suite_id} not found")
                    return False
                
                conn.commit()
                logger.info(f"Deleted suite {suite_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete suite {suite_id}: {e}")
            return False
    
    async def get_suite_summary(self) -> Dict[str, Any]:
        """Get summary statistics about suites."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM mcp_suites")
                total_suites = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(DISTINCT suite_id) FROM suite_memberships")
                suites_with_servers = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(DISTINCT server_name) FROM suite_memberships")
                servers_in_suites = cursor.fetchone()[0]
                
                cursor = conn.execute("""
                    SELECT category, COUNT(*) as count 
                    FROM mcp_suites 
                    WHERE category != '' 
                    GROUP BY category
                """)
                categories = dict(cursor.fetchall())
                
                cursor = conn.execute("""
                    SELECT role, COUNT(*) as count 
                    FROM suite_memberships 
                    GROUP BY role
                """)
                roles = dict(cursor.fetchall())
                
                return {
                    "total_suites": total_suites,
                    "suites_with_servers": suites_with_servers,
                    "servers_in_suites": servers_in_suites,
                    "categories": categories,
                    "roles": roles
                }
                
        except Exception as e:
            logger.error(f"Failed to get suite summary: {e}")
            return {}