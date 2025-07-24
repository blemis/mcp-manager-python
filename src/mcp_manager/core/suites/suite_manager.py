"""
Main orchestration for MCP Suite Management System.

Provides high-level interface for managing MCP server suites with
import/export capabilities and orchestrates all suite operations.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from .database import SuiteDatabase
from .crud_operations import SuiteCRUDOperations
from .membership import MembershipManager
from .models import Suite, SuiteMembership
from mcp_manager.core.models import Server
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class SuiteManager:
    """Main orchestration class for MCP suite management."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize suite manager with all required components."""
        self.db = SuiteDatabase(db_path)
        self.crud = SuiteCRUDOperations(self.db)
        self.membership = MembershipManager(self.db)
    
    # Suite CRUD operations - delegate to crud module
    async def create_or_update_suite(self, suite_id: str, name: str, description: str = "",
                                   category: str = "", config: Optional[Dict[str, Any]] = None) -> bool:
        """Create a new suite or update an existing one."""
        return await self.crud.create_or_update_suite(suite_id, name, description, category, config)
    
    async def get_suite(self, suite_id: str) -> Optional[Suite]:
        """Get a complete suite with all memberships."""
        return await self.crud.get_suite(suite_id)
    
    async def list_suites(self, category: Optional[str] = None) -> List[Suite]:
        """List all suites, optionally filtered by category."""
        return await self.crud.list_suites(category)
    
    async def delete_suite(self, suite_id: str) -> bool:
        """Delete a suite and all its memberships."""
        return await self.crud.delete_suite(suite_id)
    
    async def get_suite_summary(self) -> Dict[str, Any]:
        """Get summary statistics about suites."""
        return await self.crud.get_suite_summary()
    
    # Membership operations - delegate to membership module
    async def add_server_to_suite(self, suite_id: str, server_name: str, role: str = "member",
                                priority: int = 50, config_overrides: Optional[Dict[str, Any]] = None) -> bool:
        """Add a server to a suite with specified role and priority."""
        return await self.membership.add_server_to_suite(suite_id, server_name, role, priority, config_overrides)
    
    async def remove_server_from_suite(self, suite_id: str, server_name: str) -> bool:
        """Remove a server from a suite."""
        return await self.membership.remove_server_from_suite(suite_id, server_name)
    
    async def get_server_suites(self, server_name: str) -> List[Tuple[str, str, str, int]]:
        """Get all suites that contain a specific server."""
        return await self.membership.get_server_suites(server_name)
    
    async def update_server_suites_field(self, server: Server) -> bool:
        """Update a server's suites field based on database memberships."""
        return await self.membership.update_server_suites_field(server)
    
    async def sync_all_server_suites(self, servers: List[Server]) -> int:
        """Sync the suites field for all servers based on database."""
        return await self.membership.sync_all_server_suites(servers)
    
    async def cleanup_orphaned_memberships(self) -> int:
        """Remove memberships for suites that no longer exist."""
        return await self.membership.cleanup_orphaned_memberships()
    
    # Import/Export operations - orchestrated here
    async def export_suites(self, export_path: Path) -> bool:
        """Export all suites to a JSON file."""
        try:
            suites = await self.list_suites()
            
            export_data = {
                "export_timestamp": datetime.now().isoformat(),
                "total_suites": len(suites),
                "suites": []
            }
            
            for suite in suites:
                suite_data = {
                    "id": suite.id,
                    "name": suite.name,
                    "description": suite.description,
                    "category": suite.category,
                    "config": suite.config,
                    "created_at": suite.created_at.isoformat(),
                    "updated_at": suite.updated_at.isoformat(),
                    "memberships": []
                }
                
                for membership in suite.memberships:
                    membership_data = {
                        "server_name": membership.server_name,
                        "role": membership.role,
                        "priority": membership.priority,
                        "config_overrides": membership.config_overrides,
                        "added_at": membership.added_at.isoformat()
                    }
                    suite_data["memberships"].append(membership_data)
                
                export_data["suites"].append(suite_data)
            
            # Write to file
            export_path.parent.mkdir(parents=True, exist_ok=True)
            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            logger.info(f"Exported {len(suites)} suites to {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export suites: {e}")
            return False
    
    async def import_suites(self, import_path: Path, overwrite: bool = False) -> Tuple[int, int]:
        """Import suites from a JSON file. Returns (imported, skipped) counts."""
        try:
            with open(import_path, 'r') as f:
                import_data = json.load(f)
            
            imported_count = 0
            skipped_count = 0
            
            for suite_data in import_data.get("suites", []):
                suite_id = suite_data["id"]
                
                # Check if suite already exists
                existing_suite = await self.get_suite(suite_id)
                if existing_suite and not overwrite:
                    skipped_count += 1
                    continue
                
                # Create/update suite
                success = await self.create_or_update_suite(
                    suite_id=suite_id,
                    name=suite_data["name"],
                    description=suite_data["description"],
                    category=suite_data["category"],
                    config=suite_data["config"]
                )
                
                if success:
                    # Add memberships
                    for membership_data in suite_data.get("memberships", []):
                        await self.add_server_to_suite(
                            suite_id=suite_id,
                            server_name=membership_data["server_name"],
                            role=membership_data["role"],
                            priority=membership_data["priority"],
                            config_overrides=membership_data["config_overrides"]
                        )
                    
                    imported_count += 1
                else:
                    skipped_count += 1
            
            logger.info(f"Imported {imported_count} suites, skipped {skipped_count}")
            return imported_count, skipped_count
            
        except Exception as e:
            logger.error(f"Failed to import suites: {e}")
            return 0, 0


# Global instance for easy access
suite_manager = SuiteManager()