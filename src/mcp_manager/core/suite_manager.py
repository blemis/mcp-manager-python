"""
MCP Suite Management System.

Provides database-backed management of MCP server suites with
many-to-many relationships and metadata tracking.
"""

import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from dataclasses import dataclass

from mcp_manager.core.models import Server
from mcp_manager.utils.config import get_config
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SuiteMembership:
    """Represents a server's membership in a suite."""
    suite_id: str
    server_name: str
    role: str  # 'primary', 'secondary', 'optional', 'member'
    priority: int  # 1-100, higher = more important
    config_overrides: Dict[str, Any]
    added_at: datetime


@dataclass
class Suite:
    """Represents an MCP server suite."""
    id: str
    name: str
    description: str
    category: str
    config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    memberships: List[SuiteMembership]


class SuiteManager:
    """Manages MCP server suites with database persistence."""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.config = get_config()
        if db_path:
            self.db_path = db_path
        else:
            self.db_path = self.config.database_path
        
        # Ensure database exists and is migrated
        self._ensure_database()
    
    def _ensure_database(self):
        """Ensure database exists and has required tables."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                
                # Check if suite tables exist
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name IN ('mcp_suites', 'suite_memberships')
                """)
                existing_tables = {row[0] for row in cursor.fetchall()}
                
                if 'mcp_suites' not in existing_tables or 'suite_memberships' not in existing_tables:
                    logger.info("Creating suite management tables")
                    self._create_suite_tables(conn)
                    
        except Exception as e:
            logger.error(f"Failed to ensure suite database: {e}")
            raise
    
    def _create_suite_tables(self, conn: sqlite3.Connection):
        """Create suite management tables."""
        # Create mcp_suites table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mcp_suites (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                category TEXT DEFAULT '',
                config TEXT DEFAULT '{}',  -- JSON configuration as TEXT
                created_at TEXT NOT NULL,  -- ISO datetime string
                updated_at TEXT NOT NULL   -- ISO datetime string
            )
        """)
        
        # Create suite_memberships table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS suite_memberships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                suite_id TEXT NOT NULL,
                server_name TEXT NOT NULL,
                role TEXT DEFAULT 'member',  -- 'primary', 'secondary', 'optional', 'member'
                priority INTEGER DEFAULT 50,  -- 1-100, higher = more important
                config_overrides TEXT DEFAULT '{}',  -- JSON overrides as TEXT
                added_at TEXT NOT NULL,      -- ISO datetime string
                FOREIGN KEY (suite_id) REFERENCES mcp_suites(id) ON DELETE CASCADE,
                UNIQUE(suite_id, server_name)
            )
        """)
        
        # Create indexes for performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_suite_memberships_suite_id ON suite_memberships(suite_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_suite_memberships_server_name ON suite_memberships(server_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_suites_category ON mcp_suites(category)")
        
        conn.commit()
        logger.info("Suite management tables created successfully")
    
    async def create_or_update_suite(self, suite_id: str, name: str, description: str = "",
                                   category: str = "", config: Optional[Dict[str, Any]] = None) -> bool:
        """Create a new suite or update an existing one."""
        try:
            config = config or {}
            now = datetime.now().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                
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
    
    async def add_server_to_suite(self, suite_id: str, server_name: str, role: str = "member",
                                priority: int = 50, config_overrides: Optional[Dict[str, Any]] = None) -> bool:
        """Add a server to a suite with specified role and priority."""
        try:
            config_overrides = config_overrides or {}
            now = datetime.now().isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                
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
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                
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
    
    async def get_suite(self, suite_id: str) -> Optional[Suite]:
        """Get a complete suite with all memberships."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Get suite info
                cursor = conn.execute("""
                    SELECT * FROM mcp_suites WHERE id = ?
                """, (suite_id,))
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
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
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
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                
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
    
    async def get_server_suites(self, server_name: str) -> List[Tuple[str, str, int]]:
        """Get all suites that contain a specific server."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
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
    
    async def get_suite_summary(self) -> Dict[str, Any]:
        """Get summary statistics about suites."""
        try:
            with sqlite3.connect(self.db_path) as conn:
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
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                
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
    
    async def export_suites(self, export_path: Path) -> bool:
        """Export all suites to a JSON file."""
        try:
            suites = await self.list_suites()
            
            export_data = {
                "export_timestamp": datetime.now().isoformat(),
                "total_suites": len(suites),
                "suites": []
            }
            
            for suite in suites:
                suite_data = {
                    "id": suite.id,
                    "name": suite.name,
                    "description": suite.description,
                    "category": suite.category,
                    "config": suite.config,
                    "created_at": suite.created_at.isoformat(),
                    "updated_at": suite.updated_at.isoformat(),
                    "memberships": []
                }
                
                for membership in suite.memberships:
                    membership_data = {
                        "server_name": membership.server_name,
                        "role": membership.role,
                        "priority": membership.priority,
                        "config_overrides": membership.config_overrides,
                        "added_at": membership.added_at.isoformat()
                    }
                    suite_data["memberships"].append(membership_data)
                
                export_data["suites"].append(suite_data)
            
            # Write to file
            export_path.parent.mkdir(parents=True, exist_ok=True)
            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            logger.info(f"Exported {len(suites)} suites to {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export suites: {e}")
            return False
    
    async def import_suites(self, import_path: Path, overwrite: bool = False) -> Tuple[int, int]:
        """Import suites from a JSON file. Returns (imported, skipped) counts."""
        try:
            with open(import_path, 'r') as f:
                import_data = json.load(f)
            
            imported_count = 0
            skipped_count = 0
            
            for suite_data in import_data.get("suites", []):
                suite_id = suite_data["id"]
                
                # Check if suite already exists
                existing_suite = await self.get_suite(suite_id)
                if existing_suite and not overwrite:
                    skipped_count += 1
                    continue
                
                # Create/update suite
                success = await self.create_or_update_suite(
                    suite_id=suite_id,
                    name=suite_data["name"],
                    description=suite_data["description"],
                    category=suite_data["category"],
                    config=suite_data["config"]
                )
                
                if success:
                    # Add memberships
                    for membership_data in suite_data.get("memberships", []):
                        await self.add_server_to_suite(
                            suite_id=suite_id,
                            server_name=membership_data["server_name"],
                            role=membership_data["role"],
                            priority=membership_data["priority"],
                            config_overrides=membership_data["config_overrides"]
                        )
                    
                    imported_count += 1
                else:
                    skipped_count += 1
            
            logger.info(f"Imported {imported_count} suites, skipped {skipped_count}")
            return imported_count, skipped_count
            
        except Exception as e:
            logger.error(f"Failed to import suites: {e}")
            return 0, 0


# Global instance for easy access
suite_manager = SuiteManager()