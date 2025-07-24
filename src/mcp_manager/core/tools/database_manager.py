"""
Database management for the MCP Manager tool registry.

Handles database initialization, migrations, and connection management
for the tool registry SQLite database.
"""

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from mcp_manager.core.migrations.manager import MigrationManager
from mcp_manager.core.tools.models import ToolRegistryError
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """Manages database initialization and connections for tool registry."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to SQLite database. If None, uses default from environment.
        """
        if db_path is None:
            db_path = self._get_default_db_path()
        
        self.db_path = Path(db_path) if isinstance(db_path, str) else db_path
        self._ensure_database_ready()
        
        logger.info("Database manager initialized", extra={
            "db_path": str(self.db_path)
        })
    
    def _get_default_db_path(self) -> Path:
        """Get default database path from environment or config."""
        db_path = os.getenv("MCP_MANAGER_DB_PATH")
        if db_path:
            return Path(db_path)
        
        # Default to user config directory
        config_dir = Path.home() / ".config" / "mcp-manager"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "mcp_manager.db"
    
    def _ensure_database_ready(self) -> None:
        """Ensure database exists and migrations are applied."""
        try:
            # Create database directory if it doesn't exist
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            migration_manager = MigrationManager(self.db_path)
            
            # Check if we need to run migrations
            pending = migration_manager.get_pending_migrations()
            if pending:
                logger.info(f"Running {len(pending)} pending database migrations")
                success = migration_manager.run_pending_migrations()
                if not success:
                    raise ToolRegistryError("Failed to apply database migrations")
            
            # Verify database integrity
            self._verify_database_integrity()
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise ToolRegistryError(f"Database initialization failed: {e}")
    
    def _verify_database_integrity(self) -> None:
        """Verify database schema and integrity."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if tool_registry table exists with expected columns
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='tool_registry'
                """)
                
                if not cursor.fetchone():
                    raise ToolRegistryError("tool_registry table not found")
                
                # Check table schema
                cursor.execute("PRAGMA table_info(tool_registry)")
                columns = {row[1] for row in cursor.fetchall()}
                
                required_columns = {
                    'id', 'name', 'canonical_name', 'description', 'server_name',
                    'server_type', 'input_schema', 'output_schema', 'categories',
                    'tags', 'last_discovered', 'is_available', 'usage_count',
                    'success_rate', 'average_response_time', 'created_at',
                    'updated_at', 'discovered_by'
                }
                
                missing_columns = required_columns - columns
                if missing_columns:
                    raise ToolRegistryError(f"Missing required columns: {missing_columns}")
                
                logger.debug("Database integrity verification passed")
                
        except Exception as e:
            logger.error(f"Database integrity check failed: {e}")
            raise ToolRegistryError(f"Database integrity check failed: {e}")
    
    def get_connection(self) -> sqlite3.Connection:
        """
        Get a database connection.
        
        Returns:
            SQLite connection object
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            
            # Configure connection for better performance and safety
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA foreign_keys=ON")
            
            return conn
            
        except Exception as e:
            logger.error(f"Failed to create database connection: {e}")
            raise ToolRegistryError(f"Failed to create database connection: {e}")
    
    def backup_database(self, backup_path: Optional[Path] = None) -> Path:
        """
        Create a backup of the database.
        
        Args:
            backup_path: Path for backup file. If None, generates timestamp-based name.
            
        Returns:
            Path to the created backup file
        """
        try:
            if backup_path is None:
                timestamp = str(int(datetime.now().timestamp()))
                backup_path = self.db_path.parent / f"mcp_manager_backup_{timestamp}.db"
            
            # Use SQLite backup API for consistent backup
            with self.get_connection() as source_conn:
                with sqlite3.connect(str(backup_path)) as backup_conn:
                    source_conn.backup(backup_conn)
            
            logger.info(f"Database backup created: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Database backup failed: {e}")
            raise ToolRegistryError(f"Database backup failed: {e}")
    
    def get_database_info(self) -> dict:
        """
        Get information about the database.
        
        Returns:
            Dictionary with database information
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get database size
                db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
                
                # Get table count
                cursor.execute("""
                    SELECT COUNT(*) FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                table_count = cursor.fetchone()[0]
                
                # Get tool registry row count
                cursor.execute("SELECT COUNT(*) FROM tool_registry")
                tool_count = cursor.fetchone()[0]
                
                # Get database version from user_version pragma
                cursor.execute("PRAGMA user_version")
                schema_version = cursor.fetchone()[0]
                
                return {
                    "path": str(self.db_path),
                    "size_bytes": db_size,
                    "table_count": table_count,
                    "tool_count": tool_count,
                    "schema_version": schema_version,
                    "exists": self.db_path.exists()
                }
                
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {"error": str(e)}
    
    def vacuum_database(self) -> bool:
        """
        Vacuum the database to reclaim space and optimize.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                conn.execute("VACUUM")
                conn.commit()
            
            logger.info("Database vacuum completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Database vacuum failed: {e}")
            return False
    
    def close(self):
        """Clean up database manager resources."""
        # Currently no persistent connections to close
        # This method exists for future connection pooling
        logger.debug("Database manager closed")