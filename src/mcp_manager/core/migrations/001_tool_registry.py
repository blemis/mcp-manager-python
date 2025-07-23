"""
Migration 001: Create tool registry and analytics tables.

Creates the initial database schema for the tool registry system including:
- tool_registry: Main table for discovered MCP tools
- tool_usage_analytics: Table for tracking tool usage and performance
"""

import os
import sqlite3
from pathlib import Path
from typing import Optional

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)

MIGRATION_VERSION = "001"
MIGRATION_NAME = "tool_registry"

# SQL for tool_registry table
CREATE_TOOL_REGISTRY_TABLE = """
CREATE TABLE IF NOT EXISTS tool_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    canonical_name TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    server_name TEXT NOT NULL,
    server_type TEXT NOT NULL,
    input_schema TEXT DEFAULT '{}',  -- JSON as TEXT
    output_schema TEXT DEFAULT '{}', -- JSON as TEXT  
    categories TEXT DEFAULT '[]',    -- JSON array as TEXT
    tags TEXT DEFAULT '[]',          -- JSON array as TEXT
    last_discovered TEXT NOT NULL,  -- ISO datetime string
    is_available BOOLEAN DEFAULT 1,
    usage_count INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 0.0,
    average_response_time REAL DEFAULT 0.0,
    created_at TEXT NOT NULL,       -- ISO datetime string
    updated_at TEXT NOT NULL,       -- ISO datetime string
    discovered_by TEXT DEFAULT 'manual'
);
"""

# SQL for tool_usage_analytics table
CREATE_TOOL_USAGE_ANALYTICS_TABLE = """
CREATE TABLE IF NOT EXISTS tool_usage_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_canonical_name TEXT NOT NULL,
    user_query TEXT DEFAULT '',
    selected BOOLEAN NOT NULL,
    success BOOLEAN DEFAULT 0,
    timestamp TEXT NOT NULL,        -- ISO datetime string
    context TEXT DEFAULT '{}',      -- JSON as TEXT
    response_time_ms INTEGER DEFAULT 0,
    error_details TEXT,
    session_id TEXT
);
"""

# Indexes for performance
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_tool_registry_canonical_name ON tool_registry(canonical_name);",
    "CREATE INDEX IF NOT EXISTS idx_tool_registry_server_name ON tool_registry(server_name);",
    "CREATE INDEX IF NOT EXISTS idx_tool_registry_server_type ON tool_registry(server_type);",
    "CREATE INDEX IF NOT EXISTS idx_tool_registry_categories ON tool_registry(categories);",
    "CREATE INDEX IF NOT EXISTS idx_tool_registry_is_available ON tool_registry(is_available);",
    "CREATE INDEX IF NOT EXISTS idx_tool_registry_usage_count ON tool_registry(usage_count);",
    "CREATE INDEX IF NOT EXISTS idx_tool_usage_analytics_canonical_name ON tool_usage_analytics(tool_canonical_name);",
    "CREATE INDEX IF NOT EXISTS idx_tool_usage_analytics_timestamp ON tool_usage_analytics(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_tool_usage_analytics_selected ON tool_usage_analytics(selected);",
    "CREATE INDEX IF NOT EXISTS idx_tool_usage_analytics_success ON tool_usage_analytics(success);",
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
    Run the tool registry migration.
    
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
            logger.debug("Creating tool_registry table")
            cursor.execute(CREATE_TOOL_REGISTRY_TABLE)
            
            logger.debug("Creating tool_usage_analytics table")
            cursor.execute(CREATE_TOOL_USAGE_ANALYTICS_TABLE)
            
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
    Rollback the tool registry migration.
    
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
            cursor.execute("DROP TABLE IF EXISTS tool_usage_analytics;")
            cursor.execute("DROP TABLE IF EXISTS tool_registry;")
            
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