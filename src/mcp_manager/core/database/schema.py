"""
SQLite + WAL Database Schema (Option 3 - Hybrid Approach)
Master server registry with lightweight suite references.
"""

import sqlite3
import aiosqlite
from pathlib import Path
from typing import Optional
from datetime import datetime

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)

class MCPDatabaseSchema:
    """Handles database schema creation and WAL configuration."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize with database path."""
        if db_path is None:
            from mcp_manager.utils.config import get_config
            config = get_config()
            data_dir = Path(getattr(config, 'data_dir', '~/.local/share/mcp-manager')).expanduser()
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = data_dir / 'mcp_manager.db'
        
        self.db_path = db_path
        logger.info(f"Database path: {self.db_path}")
    
    async def initialize_database(self) -> bool:
        """Initialize database with schema and WAL mode."""
        try:
            # Create database file if it doesn't exist
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiosqlite.connect(self.db_path) as db:
                # Enable WAL mode and optimization settings
                await self._configure_wal_mode(db)
                
                # Create schema
                await self._create_schema(db)
                
                # Create indexes
                await self._create_indexes(db)
                
                await db.commit()
                logger.info("✅ Database initialized successfully with WAL mode")
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            return False
    
    async def _configure_wal_mode(self, db: aiosqlite.Connection):
        """Configure SQLite for optimal performance with WAL mode."""
        logger.info("🔧 Configuring SQLite with WAL mode...")
        
        # Enable WAL mode for concurrent access
        await db.execute("PRAGMA journal_mode = WAL")
        
        # Optimize for performance and reliability
        await db.execute("PRAGMA synchronous = NORMAL")      # Balance safety/speed
        await db.execute("PRAGMA cache_size = -64000")       # 64MB cache (negative = KB)
        await db.execute("PRAGMA temp_store = memory")       # Temp tables in memory
        await db.execute("PRAGMA mmap_size = 134217728")     # 128MB memory-mapped I/O
        await db.execute("PRAGMA wal_autocheckpoint = 1000") # Checkpoint every 1000 pages
        
        # Enable foreign key constraints
        await db.execute("PRAGMA foreign_keys = ON")
        
        # Verify WAL mode is enabled
        result = await db.execute("PRAGMA journal_mode")
        mode = await result.fetchone()
        if mode and mode[0].upper() == 'WAL':
            logger.info("✅ WAL mode enabled successfully")
        else:
            logger.warning(f"⚠️ Unexpected journal mode: {mode}")
    
    async def _create_schema(self, db: aiosqlite.Connection):
        """Create the Option 3 database schema."""
        logger.info("📋 Creating database schema...")
        
        # Master server registry (single source of truth)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mcp_server_registry (
                server_name TEXT PRIMARY KEY,
                description TEXT,
                server_type TEXT NOT NULL,           -- npm, docker-desktop, custom
                install_command TEXT,
                package_name TEXT,
                discovery_metadata TEXT,             -- JSON with all discovery data
                version TEXT,
                author TEXT,
                repository_url TEXT,
                documentation_url TEXT,
                tags TEXT,                           -- JSON array of tags
                last_discovered TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # MCP Suites
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mcp_suites (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT,
                purpose TEXT,                        -- Brief purpose description
                config TEXT,                         -- JSON suite-level configuration
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT DEFAULT 'system'     -- user, ai, system, migration
            )
        """)
        
        # Suite memberships (lightweight references)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS suite_memberships (
                suite_id TEXT NOT NULL,
                server_name TEXT NOT NULL,
                role TEXT DEFAULT 'member',          -- primary, secondary, optional, member
                priority INTEGER DEFAULT 50,        -- 1-100, higher = more important
                suite_specific_config TEXT,          -- JSON overrides for this suite
                notes TEXT,                          -- Human-readable notes
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                added_by TEXT DEFAULT 'system',      -- user, ai, system
                PRIMARY KEY (suite_id, server_name),
                FOREIGN KEY (suite_id) REFERENCES mcp_suites(id) ON DELETE CASCADE,
                FOREIGN KEY (server_name) REFERENCES mcp_server_registry(server_name) ON DELETE CASCADE
            )
        """)
        
        # Test scenarios (existing table, updated to reference suites)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS test_scenarios (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                created_by TEXT NOT NULL,
                scenario_json TEXT NOT NULL,
                tags TEXT,                           -- JSON array of tags
                confidence_score REAL DEFAULT 0.0,
                ai_reasoning TEXT,
                suite_id TEXT,                       -- Reference to mcp_suites
                execution_count INTEGER DEFAULT 0,
                success_rate REAL DEFAULT 0.0,
                average_duration REAL DEFAULT 0.0,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_executed TIMESTAMP,
                enabled BOOLEAN DEFAULT 1,
                FOREIGN KEY (suite_id) REFERENCES mcp_suites(id) ON DELETE SET NULL
            )
        """)
        
        # Discovery cache (for performance)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS discovery_cache (
                cache_key TEXT PRIMARY KEY,          -- e.g., "npm:@modelcontextprotocol/server-filesystem"
                server_type TEXT NOT NULL,
                raw_data TEXT NOT NULL,              -- JSON discovery response
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,                -- TTL for cache invalidation
                fetch_duration_ms INTEGER            -- How long discovery took
            )
        """)
        
        # Suite usage analytics
        await db.execute("""
            CREATE TABLE IF NOT EXISTS suite_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                suite_id TEXT NOT NULL,
                operation TEXT NOT NULL,             -- load, test, deploy, etc.
                success BOOLEAN NOT NULL,
                duration_ms INTEGER,
                error_message TEXT,
                context TEXT,                        -- JSON with additional context
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (suite_id) REFERENCES mcp_suites(id) ON DELETE CASCADE
            )
        """)
        
        logger.info("✅ Database schema created")
    
    async def _create_indexes(self, db: aiosqlite.Connection):
        """Create indexes for optimal query performance."""
        logger.info("🔍 Creating database indexes...")
        
        # Registry indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_registry_type ON mcp_server_registry(server_type)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_registry_updated ON mcp_server_registry(updated_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_registry_package ON mcp_server_registry(package_name)")
        
        # Suite indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_suites_category ON mcp_suites(category)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_suites_created ON mcp_suites(created_at)")
        
        # Membership indexes (critical for join performance)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_memberships_suite ON suite_memberships(suite_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_memberships_server ON suite_memberships(server_name)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_memberships_priority ON suite_memberships(suite_id, priority DESC)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_memberships_role ON suite_memberships(role)")
        
        # Test scenario indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_scenarios_suite ON test_scenarios(suite_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_scenarios_category ON test_scenarios(category)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_scenarios_enabled ON test_scenarios(enabled)")
        
        # Discovery cache indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_cache_type ON discovery_cache(server_type)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_cache_expires ON discovery_cache(expires_at)")
        
        # Usage analytics indexes
        await db.execute("CREATE INDEX IF NOT EXISTS idx_usage_suite ON suite_usage(suite_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON suite_usage(timestamp)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_usage_operation ON suite_usage(operation)")
        
        logger.info("✅ Database indexes created")
    
    async def get_database_info(self) -> dict:
        """Get database information and WAL status."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                info = {}
                
                # Get journal mode
                result = await db.execute("PRAGMA journal_mode")
                mode = await result.fetchone()
                info['journal_mode'] = mode[0] if mode else 'unknown'
                
                # Get database size
                result = await db.execute("PRAGMA page_count")
                page_count = await result.fetchone()
                result = await db.execute("PRAGMA page_size")
                page_size = await result.fetchone()
                
                if page_count and page_size:
                    info['database_size_bytes'] = page_count[0] * page_size[0]
                    info['database_size_mb'] = round(info['database_size_bytes'] / 1024 / 1024, 2)
                
                # Get table counts
                tables = ['mcp_server_registry', 'mcp_suites', 'suite_memberships', 'test_scenarios']
                for table in tables:
                    result = await db.execute(f"SELECT COUNT(*) FROM {table}")
                    count = await result.fetchone()
                    info[f'{table}_count'] = count[0] if count else 0
                
                # WAL file info
                wal_file = Path(str(self.db_path) + '-wal')
                info['wal_file_exists'] = wal_file.exists()
                if wal_file.exists():
                    info['wal_file_size_bytes'] = wal_file.stat().st_size
                
                return info
                
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {'error': str(e)}
    
    async def checkpoint_wal(self) -> bool:
        """Force WAL checkpoint to optimize database."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                logger.info("✅ WAL checkpoint completed")
                return True
        except Exception as e:
            logger.error(f"❌ WAL checkpoint failed: {e}")
            return False


# Convenience function for easy initialization
async def initialize_mcp_database(db_path: Optional[Path] = None) -> MCPDatabaseSchema:
    """Initialize the MCP database with proper schema and WAL configuration."""
    schema = MCPDatabaseSchema(db_path)
    success = await schema.initialize_database()
    if not success:
        raise RuntimeError("Failed to initialize MCP database")
    return schema


if __name__ == "__main__":
    import asyncio
    
    async def main():
        print("🚀 Initializing MCP Manager Database...")
        schema = await initialize_mcp_database()
        info = await schema.get_database_info()
        
        print("\n📊 Database Information:")
        for key, value in info.items():
            print(f"   {key}: {value}")
        
        print("\n✅ Database initialization complete!")
    
    asyncio.run(main())