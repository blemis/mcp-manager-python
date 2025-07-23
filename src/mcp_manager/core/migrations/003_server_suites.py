"""
Migration 003: Add server suite management tables.

Creates tables for managing MCP server suites and their memberships:
- mcp_suites: Suite definitions with metadata
- suite_memberships: Many-to-many relationship between servers and suites
- server_metadata: Additional server metadata including suite tags
"""

import os
import sqlite3
from pathlib import Path
from typing import Optional

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)

MIGRATION_VERSION = "003"
MIGRATION_NAME = "server_suites"

# SQL for mcp_suites table
CREATE_SUITES_TABLE = """
CREATE TABLE IF NOT EXISTS mcp_suites (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    category TEXT DEFAULT '',
    config TEXT DEFAULT '{}',  -- JSON configuration as TEXT
    created_at TEXT NOT NULL,  -- ISO datetime string
    updated_at TEXT NOT NULL   -- ISO datetime string
);
"""

# SQL for suite_memberships table
CREATE_SUITE_MEMBERSHIPS_TABLE = """
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
);
"""

# SQL for server_metadata table
CREATE_SERVER_METADATA_TABLE = """
CREATE TABLE IF NOT EXISTS server_metadata (
    server_name TEXT PRIMARY KEY,
    server_type TEXT NOT NULL,
    suites TEXT DEFAULT '[]',    -- JSON array of suite IDs as TEXT
    tags TEXT DEFAULT '[]',      -- JSON array of tags as TEXT
    install_source TEXT DEFAULT '',  -- 'discovery', 'manual', 'test-suite'
    install_id TEXT DEFAULT '',      -- Original install ID from discovery
    metadata TEXT DEFAULT '{}',      -- Additional JSON metadata as TEXT
    created_at TEXT NOT NULL,    -- ISO datetime string
    updated_at TEXT NOT NULL     -- ISO datetime string
);
"""

# Indexes for performance
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_mcp_suites_name ON mcp_suites(name);",
    "CREATE INDEX IF NOT EXISTS idx_mcp_suites_category ON mcp_suites(category);",
    "CREATE INDEX IF NOT EXISTS idx_suite_memberships_suite_id ON suite_memberships(suite_id);",
    "CREATE INDEX IF NOT EXISTS idx_suite_memberships_server_name ON suite_memberships(server_name);", 
    "CREATE INDEX IF NOT EXISTS idx_suite_memberships_role ON suite_memberships(role);",
    "CREATE INDEX IF NOT EXISTS idx_suite_memberships_priority ON suite_memberships(priority);",
    "CREATE INDEX IF NOT EXISTS idx_server_metadata_server_type ON server_metadata(server_type);",
    "CREATE INDEX IF NOT EXISTS idx_server_metadata_suites ON server_metadata(suites);",
    "CREATE INDEX IF NOT EXISTS idx_server_metadata_tags ON server_metadata(tags);",
    "CREATE INDEX IF NOT EXISTS idx_server_metadata_install_source ON server_metadata(install_source);",
]

def get_default_db_path() -> Path:
    """Get the default database path from environment or config."""
    db_path = os.getenv("MCP_MANAGER_DB_PATH")
    if db_path:
        return Path(db_path)
    
    # Default to user config directory
    config_dir = Path.home() / ".config" / "mcp-manager"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "mcp_manager.db"

def run_migration(db_path: Optional[Path] = None) -> bool:
    """
    Run the server suites migration.
    
    Args:
        db_path: Path to SQLite database file. If None, uses default path.
        
    Returns:
        True if migration successful, False otherwise.
    """
    if db_path is None:
        db_path = get_default_db_path()
    
    logger.info(f"Running migration {MIGRATION_VERSION}_{MIGRATION_NAME}", extra={
        "migration_version": MIGRATION_VERSION,
        "migration_name": MIGRATION_NAME,
        "db_path": str(db_path)
    })
    
    try:
        # Ensure database directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            
            # Create tables
            logger.debug("Creating mcp_suites table")
            cursor.execute(CREATE_SUITES_TABLE)
            
            logger.debug("Creating suite_memberships table")
            cursor.execute(CREATE_SUITE_MEMBERSHIPS_TABLE)
            
            logger.debug("Creating server_metadata table")
            cursor.execute(CREATE_SERVER_METADATA_TABLE)
            
            # Create indexes
            logger.debug("Creating database indexes")
            for index_sql in CREATE_INDEXES:
                cursor.execute(index_sql)
            
            # Create migrations tracking table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    version TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                );
            """)
            
            # Record this migration
            cursor.execute("""
                INSERT OR REPLACE INTO migrations (version, name, applied_at)
                VALUES (?, ?, datetime('now'));
            """, (MIGRATION_VERSION, MIGRATION_NAME))
            
            conn.commit()
            
        logger.info(f"Migration {MIGRATION_VERSION}_{MIGRATION_NAME} completed successfully", extra={
            "migration_version": MIGRATION_VERSION,
            "db_path": str(db_path)
        })
        return True
        
    except Exception as e:
        logger.error(f"Migration {MIGRATION_VERSION}_{MIGRATION_NAME} failed", extra={
            "migration_version": MIGRATION_VERSION,
            "error": str(e),
            "error_type": type(e).__name__,
            "db_path": str(db_path)
        })
        return False

def rollback_migration(db_path: Optional[Path] = None) -> bool:
    """
    Rollback the server suites migration.
    
    Args:
        db_path: Path to SQLite database file. If None, uses default path.
        
    Returns:
        True if rollback successful, False otherwise.
    """
    if db_path is None:
        db_path = get_default_db_path()
    
    logger.info(f"Rolling back migration {MIGRATION_VERSION}_{MIGRATION_NAME}", extra={
        "migration_version": MIGRATION_VERSION,
        "migration_name": MIGRATION_NAME,
        "db_path": str(db_path)
    })
    
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            
            # Drop tables (indexes will be dropped automatically)
            cursor.execute("DROP TABLE IF EXISTS suite_memberships;")
            cursor.execute("DROP TABLE IF EXISTS server_metadata;")
            cursor.execute("DROP TABLE IF EXISTS mcp_suites;")
            
            # Remove migration record
            cursor.execute("DELETE FROM migrations WHERE version = ?;", (MIGRATION_VERSION,))
            
            conn.commit()
            
        logger.info(f"Migration {MIGRATION_VERSION}_{MIGRATION_NAME} rolled back successfully", extra={
            "migration_version": MIGRATION_VERSION,
            "db_path": str(db_path)
        })
        return True
        
    except Exception as e:
        logger.error(f"Migration rollback {MIGRATION_VERSION}_{MIGRATION_NAME} failed", extra={
            "migration_version": MIGRATION_VERSION,
            "error": str(e),
            "error_type": type(e).__name__,
            "db_path": str(db_path)
        })
        return False

if __name__ == "__main__":
    # Allow running migration directly
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        success = rollback_migration()
    else:
        success = run_migration()
    
    sys.exit(0 if success else 1)