"""
Migration manager for MCP Manager database schema evolution.

Handles running, tracking, and rolling back database migrations
in a consistent and safe manner.
"""

import importlib
import os
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)

class MigrationManager:
    """Manages database migrations for MCP Manager."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize migration manager.
        
        Args:
            db_path: Path to SQLite database. If None, uses default from environment.
        """
        if db_path is None:
            db_path = self._get_default_db_path()
        
        self.db_path = db_path
        self.migrations_dir = Path(__file__).parent
        
        logger.debug("Migration manager initialized", extra={
            "db_path": str(self.db_path),
            "migrations_dir": str(self.migrations_dir)
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
    
    def _ensure_migrations_table(self) -> None:
        """Ensure the migrations tracking table exists."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS migrations (
                    version TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                );
            """)
            conn.commit()
    
    def get_applied_migrations(self) -> List[Tuple[str, str, str]]:
        """
        Get list of applied migrations.
        
        Returns:
            List of (version, name, applied_at) tuples.
        """
        self._ensure_migrations_table()
        
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version, name, applied_at FROM migrations ORDER BY version;")
            return cursor.fetchall()
    
    def get_available_migrations(self) -> List[Tuple[str, str]]:
        """
        Get list of available migration files.
        
        Returns:
            List of (version, name) tuples from migration files.
        """
        migrations = []
        
        for file_path in self.migrations_dir.glob("[0-9][0-9][0-9]_*.py"):
            if file_path.name == "__init__.py" or file_path.name == "manager.py":
                continue
                
            # Parse version and name from filename
            stem = file_path.stem  # e.g., "001_tool_registry"
            if "_" in stem:
                version, name = stem.split("_", 1)
                migrations.append((version, name))
        
        return sorted(migrations)
    
    def get_pending_migrations(self) -> List[Tuple[str, str]]:
        """
        Get list of pending (unapplied) migrations.
        
        Returns:
            List of (version, name) tuples for pending migrations.
        """
        applied = {version for version, _, _ in self.get_applied_migrations()}
        available = self.get_available_migrations()
        
        return [(version, name) for version, name in available if version not in applied]
    
    def run_migration(self, version: str, name: str) -> bool:
        """
        Run a specific migration.
        
        Args:
            version: Migration version (e.g., "001")
            name: Migration name (e.g., "tool_registry")
            
        Returns:
            True if successful, False otherwise.
        """
        module_name = f"{version}_{name}"
        module_path = f"mcp_manager.core.migrations.{module_name}"
        
        logger.info("Running migration", extra={
            "migration_version": version,
            "migration_name": name,
            "module_path": module_path
        })
        
        try:
            # Import the migration module
            migration_module = importlib.import_module(module_path)
            
            # Check if migration has the required run_migration function
            if not hasattr(migration_module, "run_migration"):
                logger.error("Migration module missing run_migration function", extra={
                    "migration_version": version,
                    "module_path": module_path
                })
                return False
            
            # Run the migration
            success = migration_module.run_migration(self.db_path)
            
            if success:
                logger.info("Migration completed successfully", extra={
                    "migration_version": version,
                    "migration_name": name
                })
            else:
                logger.error("Migration failed", extra={
                    "migration_version": version,
                    "migration_name": name
                })
            
            return success
            
        except Exception as e:
            logger.error("Migration execution failed", extra={
                "migration_version": version,
                "migration_name": name,
                "error": str(e),
                "error_type": type(e).__name__
            })
            return False
    
    def run_pending_migrations(self) -> bool:
        """
        Run all pending migrations.
        
        Returns:
            True if all migrations successful, False if any failed.
        """
        pending = self.get_pending_migrations()
        
        if not pending:
            logger.info("No pending migrations to run")
            return True
        
        logger.info(f"Running {len(pending)} pending migrations", extra={
            "pending_count": len(pending),
            "migrations": [f"{v}_{n}" for v, n in pending]
        })
        
        success_count = 0
        for version, name in pending:
            if self.run_migration(version, name):
                success_count += 1
            else:
                logger.error("Migration failed, stopping migration run", extra={
                    "failed_migration": f"{version}_{name}",
                    "completed_migrations": success_count,
                    "total_migrations": len(pending)
                })
                return False
        
        logger.info("All pending migrations completed successfully", extra={
            "completed_count": success_count
        })
        return True
    
    def rollback_migration(self, version: str, name: str) -> bool:
        """
        Rollback a specific migration.
        
        Args:
            version: Migration version (e.g., "001")
            name: Migration name (e.g., "tool_registry")
            
        Returns:
            True if successful, False otherwise.
        """
        module_name = f"{version}_{name}"
        module_path = f"mcp_manager.core.migrations.{module_name}"
        
        logger.info("Rolling back migration", extra={
            "migration_version": version,
            "migration_name": name,
            "module_path": module_path
        })
        
        try:
            # Import the migration module
            migration_module = importlib.import_module(module_path)
            
            # Check if migration has the required rollback_migration function
            if not hasattr(migration_module, "rollback_migration"):
                logger.error("Migration module missing rollback_migration function", extra={
                    "migration_version": version,
                    "module_path": module_path
                })
                return False
            
            # Run the rollback
            success = migration_module.rollback_migration(self.db_path)
            
            if success:
                logger.info("Migration rollback completed successfully", extra={
                    "migration_version": version,
                    "migration_name": name
                })
            else:
                logger.error("Migration rollback failed", extra={
                    "migration_version": version,
                    "migration_name": name
                })
            
            return success
            
        except Exception as e:
            logger.error("Migration rollback execution failed", extra={
                "migration_version": version,
                "migration_name": name,
                "error": str(e),
                "error_type": type(e).__name__
            })
            return False
    
    def get_migration_status(self) -> Dict[str, any]:
        """
        Get comprehensive migration status information.
        
        Returns:
            Dictionary with migration status details.
        """
        applied = self.get_applied_migrations()
        available = self.get_available_migrations()
        pending = self.get_pending_migrations()
        
        return {
            "database_path": str(self.db_path),
            "database_exists": self.db_path.exists(),
            "applied_migrations": len(applied),
            "available_migrations": len(available),
            "pending_migrations": len(pending),
            "applied_list": [{"version": v, "name": n, "applied_at": a} for v, n, a in applied],
            "pending_list": [{"version": v, "name": n} for v, n in pending],
            "up_to_date": len(pending) == 0
        }