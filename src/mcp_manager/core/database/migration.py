"""
Migration script to move from JSON catalog to database-based server state management.

This script:
1. Reads existing server_catalog.json
2. Migrates data to the new server_state.db 
3. Backs up the JSON file
4. Verifies migration success
"""

import json
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List
import logging

from .server_state import MCPServerStateManager, ServerInfo, ServerType

logger = logging.getLogger(__name__)

class ServerStateMigration:
    """Handles migration from JSON catalog to database."""
    
    def __init__(self):
        self.config_dir = Path.home() / ".config" / "mcp-manager"
        self.json_catalog_path = self.config_dir / "server_catalog.json"
        self.backup_path = self.config_dir / f"server_catalog_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self.db_manager = MCPServerStateManager()
    
    def needs_migration(self) -> bool:
        """Check if migration is needed."""
        if not self.json_catalog_path.exists():
            logger.info("No JSON catalog found, no migration needed")
            return False
        
        # Check if database has any servers
        servers = self.db_manager.list_servers_fast()
        if servers:
            logger.info("Database already has servers, migration may have been done")
            return False
        
        logger.info("JSON catalog exists and database is empty, migration needed")
        return True
    
    def migrate(self) -> bool:
        """Perform the migration from JSON to database."""
        try:
            logger.info("Starting migration from JSON catalog to database")
            
            # Read JSON catalog
            catalog_data = self._read_json_catalog()
            if not catalog_data:
                logger.warning("No data in JSON catalog to migrate")
                return True
            
            # Verify WAL mode is enabled
            self._verify_wal_mode()
            
            # Migrate servers
            migrated_count = self._migrate_servers(catalog_data)
            
            # Backup JSON file
            self._backup_json_catalog()
            
            # Verify migration
            verification_result = self._verify_migration(migrated_count)
            
            if verification_result:
                logger.info(f"Migration completed successfully. Migrated {migrated_count} servers.")
                return True
            else:
                logger.error("Migration verification failed!")
                return False
                
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
    
    def _read_json_catalog(self) -> Dict[str, Any]:
        """Read the existing JSON catalog."""
        try:
            with open(self.json_catalog_path, 'r') as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.error(f"Failed to read JSON catalog: {e}")
            return {}
    
    def _verify_wal_mode(self):
        """Verify that WAL mode is properly enabled."""
        try:
            with sqlite3.connect(str(self.db_manager.db_path)) as conn:
                cursor = conn.execute("PRAGMA journal_mode")
                mode = cursor.fetchone()[0]
                if mode.lower() != 'wal':
                    logger.warning(f"Database is not in WAL mode (current: {mode})")
                    # Force WAL mode
                    conn.execute("PRAGMA journal_mode=WAL")
                    cursor = conn.execute("PRAGMA journal_mode")
                    mode = cursor.fetchone()[0]
                    if mode.lower() == 'wal':
                        logger.info("Successfully enabled WAL mode")
                    else:
                        raise Exception(f"Failed to enable WAL mode, still in {mode}")
                else:
                    logger.info("WAL mode is properly enabled")
        except Exception as e:
            logger.error(f"WAL mode verification failed: {e}")
            raise
    
    def _migrate_servers(self, catalog_data: Dict[str, Any]) -> int:
        """Migrate servers from JSON to database."""
        servers_data = catalog_data.get("servers", {})
        migrated_count = 0
        
        for server_name, server_config in servers_data.items():
            try:
                # Convert JSON config to ServerInfo
                server_info = self._convert_json_to_server_info(server_name, server_config)
                
                # Add to database
                success = self.db_manager.add_server(server_info)
                if success:
                    migrated_count += 1
                    logger.debug(f"Migrated server: {server_name}")
                else:
                    logger.error(f"Failed to migrate server: {server_name}")
                    
            except Exception as e:
                logger.error(f"Error migrating server {server_name}: {e}")
                continue
        
        return migrated_count
    
    def _convert_json_to_server_info(self, name: str, config: Dict[str, Any]) -> ServerInfo:
        """Convert JSON config to ServerInfo object."""
        
        # Map server types
        server_type_mapping = {
            "npm": ServerType.NPM,
            "docker": ServerType.DOCKER,
            "docker-desktop": ServerType.DOCKER_DESKTOP,
            "custom": ServerType.CUSTOM
        }
        
        server_type = server_type_mapping.get(config.get("type", "custom"), ServerType.CUSTOM)
        
        # Parse timestamps
        created_at = None
        if "installed_at" in config:
            try:
                created_at = datetime.fromisoformat(config["installed_at"].replace('Z', '+00:00'))
            except:
                created_at = datetime.now(timezone.utc)
        
        updated_at = None
        if "updated_at" in config:
            try:
                updated_at = datetime.fromisoformat(config["updated_at"].replace('Z', '+00:00'))
            except:
                updated_at = datetime.now(timezone.utc)
        
        # Generate install_id if not present
        install_id = None
        if server_type == ServerType.DOCKER_DESKTOP:
            install_id = f"dd-{name}"
        elif server_type == ServerType.NPM and "args" in config:
            # Try to extract package name from args
            args = config.get("args", [])
            if args and len(args) > 0:
                package = args[0].replace("@", "").replace("/", "-")
                install_id = package
        elif server_type == ServerType.DOCKER:
            # Extract from command if docker run
            command = config.get("command", "")
            args = config.get("args", [])
            if "docker" in command and "run" in args:
                # Find the image name
                for i, arg in enumerate(args):
                    if ":" in arg and not arg.startswith("-"):
                        install_id = arg.replace("/", "-").replace(":", "-")
                        break
        
        return ServerInfo(
            name=name,
            server_type=server_type,
            command=config.get("command", ""),
            args=config.get("args", []),
            env=config.get("env", {}),
            enabled=config.get("enabled", True),
            scope=config.get("scope", "user"),
            description=config.get("description"),
            install_id=install_id,
            package=install_id,  # Use install_id as package for now
            created_at=created_at or datetime.now(timezone.utc),
            updated_at=updated_at or datetime.now(timezone.utc)
        )
    
    def _backup_json_catalog(self):
        """Backup the JSON catalog file."""
        try:
            shutil.copy2(self.json_catalog_path, self.backup_path)
            logger.info(f"Backed up JSON catalog to {self.backup_path}")
        except Exception as e:
            logger.error(f"Failed to backup JSON catalog: {e}")
            # Don't fail migration for backup failure
    
    def _verify_migration(self, expected_count: int) -> bool:
        """Verify that migration was successful."""
        try:
            # Check server count in database
            servers = self.db_manager.list_servers_fast()
            actual_count = len(servers)
            
            if actual_count != expected_count:
                logger.error(f"Server count mismatch: expected {expected_count}, got {actual_count}")
                return False
            
            # Check that all servers have required fields
            for server in servers:
                if not server.name or not server.command:
                    logger.error(f"Server {server.name} missing required fields")
                    return False
            
            logger.info(f"Migration verification passed: {actual_count} servers migrated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Migration verification failed: {e}")
            return False
    
    def rollback(self) -> bool:
        """Rollback migration by restoring JSON catalog."""
        try:
            if self.backup_path.exists():
                shutil.copy2(self.backup_path, self.json_catalog_path)
                logger.info("Rolled back to JSON catalog")
                return True
            else:
                logger.error("No backup file found for rollback")
                return False
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

def run_migration():
    """Convenience function to run migration."""
    migration = ServerStateMigration()
    
    if not migration.needs_migration():
        return True
    
    logger.info("Running server state migration...")
    success = migration.migrate()
    
    if not success:
        logger.error("Migration failed! Consider running rollback if needed.")
        return False
    
    return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = run_migration()
    exit(0 if success else 1)