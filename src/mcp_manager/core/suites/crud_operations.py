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
                        added_at=datetime.fromisoformat(row['added_at']),
                        server_type=row['server_type'] if 'server_type' in row.keys() else 'custom',
                        server_command=row['server_command'] if 'server_command' in row.keys() else ''
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
        """Get summary statistics about suites with Docker Desktop server expansion."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM mcp_suites")
                total_suites = cursor.fetchone()[0]
                
                # Count total memberships (this was the main bug - was showing 0)
                cursor = conn.execute("SELECT COUNT(*) FROM suite_memberships")
                total_memberships = cursor.fetchone()[0]
                
                cursor = conn.execute("SELECT COUNT(DISTINCT suite_id) FROM suite_memberships")
                active_suites = cursor.fetchone()[0]
                
                # Get all server memberships for Docker Desktop server expansion
                cursor = conn.execute("SELECT server_name FROM suite_memberships")
                all_servers = [row[0] for row in cursor.fetchall()]
                
                # Count expanded servers (including Docker Desktop individual servers)
                expanded_server_count = self._count_expanded_servers_sync(all_servers)
                
                cursor = conn.execute("""
                    SELECT category, COUNT(*) as count 
                    FROM mcp_suites 
                    WHERE category != '' 
                    GROUP BY category
                """)
                categories = dict(cursor.fetchall())
                
                # Get popular servers with Docker Desktop expansion
                cursor = conn.execute("""
                    SELECT server_name, COUNT(*) as usage_count
                    FROM suite_memberships 
                    GROUP BY server_name 
                    ORDER BY usage_count DESC
                    LIMIT 10
                """)
                popular_servers = []
                for server_name, usage_count in cursor.fetchall():
                    if self._is_docker_desktop_server_sync(server_name):
                        # Expand Docker Desktop server into individual servers
                        individual_servers = self._get_docker_desktop_servers_sync()
                        for individual_server in individual_servers:
                            popular_servers.append({
                                'server_name': individual_server,
                                'usage_count': usage_count
                            })
                    else:
                        popular_servers.append({
                            'server_name': server_name,
                            'usage_count': usage_count
                        })
                
                return {
                    "total_suites": total_suites,
                    "total_memberships": total_memberships,
                    "active_suites": active_suites,
                    "expanded_server_count": expanded_server_count,
                    "categories": categories,
                    "popular_servers": popular_servers[:10]
                }
                
        except Exception as e:
            logger.error(f"Failed to get suite summary: {e}")
            return {}
    
    def _count_expanded_servers_sync(self, server_names: List[str]) -> int:
        """Count servers with Docker Desktop servers expanded (synchronous version)."""
        total = 0
        docker_desktop_servers = self._get_docker_desktop_servers_sync()
        has_docker_desktop = False
        
        for server_name in server_names:
            if self._is_docker_desktop_server_sync(server_name):
                # Mark that we found Docker Desktop servers, but don't count yet
                has_docker_desktop = True
            else:
                total += 1
        
        # If we found any Docker Desktop servers, count all individual DD servers once
        if has_docker_desktop:
            total += len(docker_desktop_servers)
            
        return total
    
    def _is_docker_desktop_server_sync(self, server_name: str) -> bool:
        """Check if server is a Docker Desktop server (synchronous version)."""
        # Known Docker Desktop servers based on our working suite
        known_dd_servers = ["SQLite", "Ref", "aws-diagram", "filesystem"]
        return server_name in known_dd_servers
    
    def _get_docker_desktop_servers_sync(self) -> List[str]:
        """Get list of Docker Desktop servers from docker-gateway (synchronous version)."""
        try:
            # Try to parse docker-gateway command to extract individual servers
            # This is a simplified version that uses our known working servers
            import subprocess
            result = subprocess.run(
                ["claude", "mcp", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                # Parse the output to find docker-gateway servers
                for line in result.stdout.split('\n'):
                    if 'docker-gateway:' in line and '--servers' in line:
                        # Extract servers from --servers argument
                        servers_part = line.split('--servers')[1].split()[0]
                        return [s.strip() for s in servers_part.split(',') if s.strip()]
            
            # Fallback to known servers if parsing fails
            return ["Ref", "SQLite", "aws-diagram", "filesystem"]
            
        except Exception as e:
            logger.debug(f"Could not get Docker Desktop servers: {e}")
            # Fallback to known servers
            return ["Ref", "SQLite", "aws-diagram", "filesystem"]