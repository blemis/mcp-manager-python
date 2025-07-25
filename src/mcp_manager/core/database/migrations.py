"""
Database Migration Manager

Handles migration from old schema to new Option 3 schema.
Single responsibility: Data migration and schema versioning.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .connection import get_database_connection
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class DatabaseMigrator:
    """Handles database migrations and data transfer."""
    
    def __init__(self, old_db_path: Optional[Path] = None, new_db_path: Optional[Path] = None):
        """Initialize migrator with old and new database paths."""
        self.old_db_path = old_db_path or Path("tests/fixtures/test_suites.db")
        self.new_db_connection = get_database_connection(new_db_path)
        
    async def migrate_test_suites_data(self) -> bool:
        """Migrate existing test suite data to new schema."""
        try:
            logger.info("🔄 Starting migration of test suite data...")
            
            # Read old data
            old_data = await self._extract_old_data()
            if not old_data:
                logger.warning("No old data found to migrate")
                return True
            
            # Transform and insert into new schema
            await self._migrate_server_registry(old_data['servers'])
            await self._migrate_suites(old_data['suites'])
            await self._migrate_memberships(old_data['memberships'])
            await self._migrate_scenarios(old_data['scenarios'])
            
            logger.info("✅ Test suite data migration completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            return False
    
    async def _extract_old_data(self) -> Dict:
        """Extract data from old database format."""
        try:
            import sqlite3
            
            if not self.old_db_path.exists():
                logger.warning(f"Old database not found: {self.old_db_path}")
                return {}
            
            with sqlite3.connect(self.old_db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Extract suites
                suites = []
                cursor = conn.execute("SELECT * FROM mcp_suites")
                for row in cursor.fetchall():
                    suites.append(dict(row))
                
                # Extract memberships (with new fields if they exist)
                memberships = []
                cursor = conn.execute("SELECT * FROM suite_memberships")
                for row in cursor.fetchall():
                    memberships.append(dict(row))
                
                # Extract scenarios if they exist
                scenarios = []
                try:
                    cursor = conn.execute("SELECT * FROM test_scenarios")
                    for row in cursor.fetchall():
                        scenarios.append(dict(row))
                except Exception:
                    logger.info("No test_scenarios table found in old database")
                
                # Extract unique servers from memberships
                servers = []
                unique_servers = set()
                for membership in memberships:
                    server_name = membership['server_name']
                    if server_name not in unique_servers:
                        unique_servers.add(server_name)
                        servers.append({
                            'server_name': server_name,
                            'server_type': membership.get('server_type', 'custom'),
                            'server_command': membership.get('server_command', ''),
                            'config_overrides': membership.get('config_overrides', '{}')
                        })
                
            logger.info(f"📊 Extracted: {len(suites)} suites, {len(servers)} servers, {len(memberships)} memberships, {len(scenarios)} scenarios")
            return {
                'suites': suites,
                'servers': servers, 
                'memberships': memberships,
                'scenarios': scenarios
            }
            
        except Exception as e:
            logger.error(f"Failed to extract old data: {e}")
            return {}
    
    async def _migrate_server_registry(self, servers: List[Dict]):
        """Migrate servers to mcp_server_registry table."""
        if not servers:
            return
            
        logger.info(f"🔄 Migrating {len(servers)} servers to registry...")
        
        async with self.new_db_connection.get_connection() as conn:
            for server in servers:
                # Parse config for additional metadata
                config = {}
                try:
                    if server.get('config_overrides'):
                        config = json.loads(server['config_overrides'])
                except Exception:
                    config = {}
                
                # Determine server details based on type and name
                description = self._infer_server_description(server['server_name'], server['server_type'])
                package_name = self._extract_package_name(server['server_name'], server['server_type'])
                
                await conn.execute("""
                    INSERT OR REPLACE INTO mcp_server_registry (
                        server_name, description, server_type, install_command,
                        package_name, discovery_metadata, last_discovered
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    server['server_name'],
                    description,
                    server['server_type'],
                    server['server_command'],
                    package_name,
                    json.dumps({
                        'migrated_from': 'old_suite_system',
                        'original_config': config,
                        'migration_date': datetime.now().isoformat()
                    }),
                    datetime.now().isoformat()
                ))
    
    async def _migrate_suites(self, suites: List[Dict]):
        """Migrate suites to mcp_suites table."""
        if not suites:
            return
            
        logger.info(f"🔄 Migrating {len(suites)} suites...")
        
        async with self.new_db_connection.get_connection() as conn:
            for suite in suites:
                await conn.execute("""
                    INSERT OR REPLACE INTO mcp_suites (
                        id, name, description, category, purpose, config, 
                        created_at, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    suite['id'],
                    suite['name'],
                    suite['description'],
                    suite.get('category', 'migrated'),
                    f"Migrated from old test suite system",
                    json.dumps(suite.get('config', {})),
                    suite.get('created_at', datetime.now().isoformat()),
                    'migration'
                ))
    
    async def _migrate_memberships(self, memberships: List[Dict]):
        """Migrate memberships to suite_memberships table."""
        if not memberships:
            return
            
        logger.info(f"🔄 Migrating {len(memberships)} suite memberships...")
        
        async with self.new_db_connection.get_connection() as conn:
            for membership in memberships:
                # Parse suite-specific config
                suite_config = {}
                try:
                    if membership.get('config_overrides'):
                        suite_config = json.loads(membership['config_overrides'])
                except Exception:
                    suite_config = {}
                
                await conn.execute("""
                    INSERT OR REPLACE INTO suite_memberships (
                        suite_id, server_name, role, priority, suite_specific_config,
                        notes, added_at, added_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    membership['suite_id'],
                    membership['server_name'], 
                    membership.get('role', 'member'),
                    membership.get('priority', 50),
                    json.dumps(suite_config),
                    f"Migrated from old system",
                    membership.get('added_at', datetime.now().isoformat()),
                    'migration'
                ))
    
    async def _migrate_scenarios(self, scenarios: List[Dict]):
        """Migrate test scenarios if they exist."""
        if not scenarios:
            return
            
        logger.info(f"🔄 Migrating {len(scenarios)} test scenarios...")
        
        async with self.new_db_connection.get_connection() as conn:
            for scenario in scenarios:
                await conn.execute("""
                    INSERT OR REPLACE INTO test_scenarios (
                        id, name, description, category, priority, created_by,
                        scenario_json, tags, confidence_score, ai_reasoning,
                        suite_id, execution_count, success_rate, average_duration,
                        created_date, last_modified, enabled
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    scenario['id'],
                    scenario['name'],
                    scenario['description'],
                    scenario['category'],
                    scenario['priority'],
                    scenario['created_by'],
                    scenario['scenario_json'],
                    scenario.get('tags'),
                    scenario.get('confidence_score', 0.0),
                    scenario.get('ai_reasoning'),
                    scenario.get('suite_id'),
                    scenario.get('execution_count', 0),
                    scenario.get('success_rate', 0.0),
                    scenario.get('average_duration', 0.0),
                    scenario.get('created_date'),
                    scenario.get('last_modified'),
                    scenario.get('enabled', True)
                ))
    
    def _infer_server_description(self, server_name: str, server_type: str) -> str:
        """Infer server description from name and type."""
        # This will be replaced by discovery system
        descriptions = {
            'dd-SQLite': 'SQLite database operations and business intelligence',
            'dd-Ref': 'Powerful search tool connecting coding to documentation',
        }
        return descriptions.get(server_name, f"{server_type} MCP server: {server_name}")
    
    def _extract_package_name(self, server_name: str, server_type: str) -> Optional[str]:
        """Extract package name from server name."""
        if server_type == 'npm' and server_name.startswith('@'):
            return server_name
        elif server_type == 'docker-desktop' and server_name.startswith('dd-'):
            return server_name[3:]  # Remove 'dd-' prefix
        return server_name
    
    async def verify_migration(self) -> Dict[str, int]:
        """Verify migration completed successfully."""
        try:
            async with self.new_db_connection.get_connection() as conn:
                counts = {}
                
                tables = ['mcp_server_registry', 'mcp_suites', 'suite_memberships', 'test_scenarios']
                for table in tables:
                    result = await conn.execute(f"SELECT COUNT(*) FROM {table}")
                    count = await result.fetchone()
                    counts[table] = count[0] if count else 0
                
                return counts
        except Exception as e:
            logger.error(f"Failed to verify migration: {e}")
            return {}


async def run_migration(old_db_path: Optional[Path] = None) -> bool:
    """Run complete migration process."""
    migrator = DatabaseMigrator(old_db_path)
    success = await migrator.migrate_test_suites_data()
    
    if success:
        counts = await migrator.verify_migration()
        logger.info("📊 Migration verification:")
        for table, count in counts.items():
            logger.info(f"   {table}: {count} records")
    
    return success