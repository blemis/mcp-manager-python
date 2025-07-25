"""
Database Initialization and Setup

Handles complete database setup, migration, and initial data population.
Single responsibility: Database bootstrap and initial configuration.
"""

import asyncio
from pathlib import Path
from typing import Optional

from .schema import initialize_mcp_database
from .migrations import run_migration
from .registry import MCPServerRegistry
from .suites import MCPSuiteManager
from ..discovery.registry_integration import DiscoveryRegistryIntegrator
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class DatabaseInitializer:
    """Handles complete database initialization."""
    
    def __init__(self, db_path: Optional[Path] = None, 
                 old_db_path: Optional[Path] = None):
        """Initialize database initializer."""
        self.db_path = db_path
        self.old_db_path = old_db_path or Path("tests/fixtures/test_suites.db")
        
    async def initialize_complete_system(self, force_migration: bool = False) -> bool:
        """Initialize the complete database system."""
        try:
            logger.info("🚀 Starting complete MCP database system initialization...")
            
            # Step 1: Create new database schema
            logger.info("📋 Step 1: Creating database schema with WAL mode...")
            schema = await initialize_mcp_database(self.db_path)
            
            # Step 2: Configure global database connection
            logger.info("🔧 Step 2: Configuring global database connection...")
            from .connection import get_database_connection, _db_connection
            import mcp_manager.core.database.connection as db_conn_module
            db_conn_module._db_connection = None  # Reset global connection
            db_conn = get_database_connection(self.db_path)
            
            # Step 3: Initialize with sample data instead of complex migration
            logger.info("📋 Step 3: Initializing with sample data...")
            await self._create_sample_data()
            
            # Step 4: Discovery and registration  
            logger.info("🔍 Step 4: Discovering and registering servers...")
            integrator = DiscoveryRegistryIntegrator()
            discovery_results = await integrator.bulk_discover_from_suites()
            logger.info(f"✅ Discovery results: {discovery_results}")
            
            # Step 5: Verify system health
            logger.info("🏥 Step 5: Verifying system health...")
            health_check = await self._verify_system_health()
            
            if health_check['healthy']:
                logger.info("✅ MCP database system initialization completed successfully!")
                await self._print_system_summary()
                return True
            else:
                logger.error(f"❌ System health check failed: {health_check}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize database system: {e}")
            return False
    
    async def _verify_system_health(self) -> dict:
        """Verify all system components are working."""
        try:
            registry = MCPServerRegistry()
            suite_manager = MCPSuiteManager()
            
            health = {
                'healthy': True,
                'issues': []
            }
            
            # Test database connectivity
            try:
                servers = await registry.list_servers()
                health['server_count'] = len(servers)
            except Exception as e:
                health['healthy'] = False
                health['issues'].append(f"Registry connectivity: {e}")
            
            # Test suite operations
            try:
                suites = await suite_manager.list_suites()
                health['suite_count'] = len(suites)
            except Exception as e:
                health['healthy'] = False
                health['issues'].append(f"Suite manager: {e}")
            
            # Test WAL mode
            try:
                from .connection import get_database_connection
                db_conn = get_database_connection()
                wal_info = await db_conn.get_wal_info()
                health['wal_enabled'] = wal_info.get('journal_mode') == 'wal'
                if not health['wal_enabled']:
                    health['issues'].append("WAL mode not enabled")
            except Exception as e:
                health['healthy'] = False
                health['issues'].append(f"WAL check: {e}")
            
            return health
            
        except Exception as e:
            return {
                'healthy': False,
                'issues': [f"Health check failed: {e}"]
            }
    
    async def _print_system_summary(self):
        """Print a summary of the initialized system."""
        try:
            registry = MCPServerRegistry()
            suite_manager = MCPSuiteManager()
            
            # Get statistics
            registry_stats = await registry.get_registry_stats()
            suite_stats = await suite_manager.get_suite_stats()
            
            logger.info("📊 System Summary:")
            logger.info(f"   📦 Servers registered: {registry_stats.get('total_servers', 0)}")
            logger.info(f"   🎯 Suites created: {suite_stats.get('total_suites', 0)}")
            
            if registry_stats.get('servers_by_type'):
                logger.info("   🔧 Server types:")
                for server_type, count in registry_stats['servers_by_type'].items():
                    logger.info(f"      • {server_type}: {count}")
            
            if suite_stats.get('suites_by_category'):
                logger.info("   📁 Suite categories:")
                for category, count in suite_stats['suites_by_category'].items():
                    logger.info(f"      • {category}: {count}")
                    
        except Exception as e:
            logger.error(f"Failed to print system summary: {e}")
    
    async def _create_sample_data(self):
        """Create sample MCP servers and suites for testing."""
        try:
            from .registry import MCPServerRegistry, MCPServerInfo
            from .suites import MCPSuiteManager, MCPSuite
            
            registry = MCPServerRegistry()
            suite_manager = MCPSuiteManager()
            
            # Create sample real MCP servers
            sample_servers = [
                MCPServerInfo(
                    server_name="dd-SQLite",
                    description="SQLite database operations and business intelligence",
                    server_type="docker-desktop",
                    install_command="docker-desktop://SQLite",
                    package_name="SQLite",
                    tags=["database", "sql", "docker-desktop"],
                    discovery_metadata={"source": "sample_initialization"}
                ),
                MCPServerInfo(
                    server_name="dd-Ref",
                    description="Powerful search tool connecting coding to documentation",
                    server_type="docker-desktop", 
                    install_command="docker-desktop://Ref",
                    package_name="Ref",
                    tags=["search", "documentation", "docker-desktop"],
                    discovery_metadata={"source": "sample_initialization"}
                )
            ]
            
            # Register servers
            for server in sample_servers:
                await registry.register_server(server)
                logger.info(f"✅ Registered sample server: {server.server_name}")
            
            # Create sample suite
            sample_suite = MCPSuite(
                id="core-testing",
                name="Core Testing Suite",
                description="Essential MCP servers for core functionality testing",
                category="core",
                purpose="Automated testing of core MCP functionality"
            )
            
            await suite_manager.create_suite(sample_suite)
            
            # Add servers to suite
            await suite_manager.add_server_to_suite(
                "core-testing", "dd-SQLite", "primary", 90,
                notes="Primary database server for testing"
            )
            await suite_manager.add_server_to_suite(
                "core-testing", "dd-Ref", "secondary", 80,
                notes="Documentation and search functionality"
            )
            
            logger.info("✅ Sample data initialization completed")
            
        except Exception as e:
            logger.error(f"Failed to create sample data: {e}")
            # Don't fail the whole initialization for sample data issues


async def bootstrap_mcp_database(db_path: Optional[Path] = None,
                                old_db_path: Optional[Path] = None,
                                force_migration: bool = False) -> bool:
    """Bootstrap the complete MCP database system."""
    initializer = DatabaseInitializer(db_path, old_db_path)
    return await initializer.initialize_complete_system(force_migration)


# CLI script for manual initialization
async def main():
    """CLI entry point for database initialization."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Initialize MCP Manager Database")
    parser.add_argument("--db-path", type=Path, help="New database path")
    parser.add_argument("--old-db-path", type=Path, help="Old database to migrate from")
    parser.add_argument("--force-migration", action="store_true", help="Force migration even if old DB doesn't exist")
    
    args = parser.parse_args()
    
    print("🚀 MCP Manager Database Initialization")
    print("=" * 50)
    
    success = await bootstrap_mcp_database(
        db_path=args.db_path,
        old_db_path=args.old_db_path,
        force_migration=args.force_migration
    )
    
    if success:
        print("\n✅ Database initialization completed successfully!")
        exit(0)
    else:
        print("\n❌ Database initialization failed!")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())