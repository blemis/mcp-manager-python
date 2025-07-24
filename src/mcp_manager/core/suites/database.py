"""
Database schema and connection management for MCP Suite Management System.

Handles database initialization, schema creation, and connection management.
"""

import sqlite3
from pathlib import Path
from typing import Optional

from mcp_manager.utils.config import get_config
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class SuiteDatabase:
    """Manages database operations for suite management."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize database manager."""
        self.config = get_config()
        raw_path = db_path or self.config.database_path
        self.db_path = Path(raw_path) if isinstance(raw_path, str) else raw_path
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
    
    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection with proper configuration."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    
    def get_row_connection(self) -> sqlite3.Connection:
        """Get a database connection configured for row access."""
        conn = self.get_connection()
        conn.row_factory = sqlite3.Row
        return conn