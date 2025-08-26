"""
Seamless synchronization manager for MCP data sources.

This module ensures all MCP data sources stay synchronized:
- Claude's internal state (.claude.json)
- MCP Manager's database
- User configuration files  
- Project configuration files
"""

import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from rich.console import Console

from mcp_manager.core.context_detector import MCPContext, ContextDetector
from mcp_manager.core.models import Server, ServerScope, ServerType
from mcp_manager.core.database.server_state import MCPServerStateManager, ServerInfo, ServerType as DBServerType
from mcp_manager.utils.logging import get_logger
from datetime import datetime, timezone

console = Console()
logger = get_logger(__name__)


@dataclass
class SyncReport:
    """Report of synchronization results."""
    claude_servers: List[str]
    database_servers: List[str]
    added_to_db: List[str]
    removed_from_db: List[str]
    conflicts_resolved: List[str]
    errors: List[str]
    
    @property
    def has_changes(self) -> bool:
        return bool(self.added_to_db or self.removed_from_db or self.conflicts_resolved)
    
    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


class SyncManager:
    """Manages synchronization between all MCP data sources."""
    
    def __init__(self, claude_interface=None, db_manager=None):
        self.claude = claude_interface
        self.db_manager = db_manager
        self.context_detector = ContextDetector()
        
    def sync_all_sources(self, context: MCPContext, silent: bool = False) -> SyncReport:
        """
        Synchronize all MCP data sources for the given context.
        
        Args:
            context: The MCP context to sync
            silent: Whether to suppress output messages
            
        Returns:
            SyncReport with synchronization results
        """
        if not silent:
            scope_desc = context.description
            console.print(f"[blue]🔄 Synchronizing MCP data sources ({scope_desc})...[/blue]")
        
        report = SyncReport(
            claude_servers=[],
            database_servers=[],
            added_to_db=[],
            removed_from_db=[],
            conflicts_resolved=[],
            errors=[]
        )
        
        try:
            # 1. Get Claude's current state (source of truth)
            claude_servers = self._get_claude_servers(context)
            report.claude_servers = [s.name for s in claude_servers]
            
            # 2. Get database state
            db_servers = self._get_database_servers()
            report.database_servers = [s.name for s in db_servers]
            
            # 3. Sync database to match Claude
            self._sync_database_to_claude(claude_servers, db_servers, report)
            
            # 4. Clean up stale entries
            self._cleanup_stale_entries(context, report)
            
            # 5. Verify configuration files are consistent
            self._verify_config_files(context, claude_servers, report)
            
            if not silent and report.has_changes:
                console.print(f"[green]✅ Synchronization complete[/green]")
                if report.added_to_db:
                    console.print(f"  Added to database: {', '.join(report.added_to_db)}")
                if report.removed_from_db:
                    console.print(f"  Removed from database: {', '.join(report.removed_from_db)}")
                if report.conflicts_resolved:
                    console.print(f"  Conflicts resolved: {', '.join(report.conflicts_resolved)}")
            
        except Exception as e:
            error_msg = f"Sync failed: {e}"
            report.errors.append(error_msg)
            logger.error(error_msg)
            if not silent:
                console.print(f"[red]❌ {error_msg}[/red]")
        
        return report
    
    def _get_claude_servers(self, context: MCPContext) -> List[Server]:
        """Get servers from Claude's internal state."""
        if not self.claude:
            return []
        
        try:
            # Use Claude's list_servers which reads from .claude.json
            return self.claude.list_servers()
        except Exception as e:
            logger.error(f"Failed to get Claude servers: {e}")
            return []
    
    def _get_database_servers(self) -> List[Server]:
        """Get servers from local database."""
        if not self.db_manager:
            return []
        
        try:
            return self.db_manager.list_servers_fast()
        except Exception as e:
            logger.error(f"Failed to get database servers: {e}")
            return []
    
    def _sync_database_to_claude(self, claude_servers: List[Server], db_servers: List[Server], report: SyncReport):
        """Synchronize database to match Claude's state."""
        if not self.db_manager:
            return
        
        claude_names = {s.name for s in claude_servers}
        db_names = {s.name for s in db_servers}
        
        # Sync enabled state for servers in DB but not in Claude
        for db_server in db_servers:
            if db_server.name not in claude_names:
                try:
                    # If server was enabled but isn't in Claude, mark it as disabled
                    # Don't remove - user might want to re-enable it later
                    if db_server.enabled:
                        self.db_manager.update_server_status(db_server.name, enabled=False)
                        report.removed_from_db.append(db_server.name)
                        logger.info(f"Disabled server that's no longer in Claude: {db_server.name}")
                    # If already disabled, no action needed - keep the discovered server info
                except Exception as e:
                    error_msg = f"Failed to update server {db_server.name}: {e}"
                    report.errors.append(error_msg)
                    logger.error(error_msg)
        
        # Add servers to DB that are in Claude but not in DB
        for claude_server in claude_servers:
            if claude_server.name not in db_names:
                try:
                    # Create database entry for Claude server
                    self._add_server_to_database(claude_server)
                    report.added_to_db.append(claude_server.name)
                    logger.info(f"Added server to database: {claude_server.name}")
                except Exception as e:
                    error_msg = f"Failed to add server {claude_server.name}: {e}"
                    report.errors.append(error_msg)
                    logger.error(error_msg)
    
    def _add_server_to_database(self, server: Server):
        """Add a server to the database with proper metadata."""
        if not self.db_manager:
            return
        
        # Generate install_id if not present
        install_id = getattr(server, 'install_id', None)
        if not install_id:
            install_id = self._generate_install_id(server)
        
        # Create ServerInfo object
        server_info = ServerInfo(
            name=server.name,
            server_type=DBServerType(server.server_type.value),
            command=server.command,
            args=server.args or [],
            env=server.env or {},
            enabled=True,  # If it's in Claude, it's enabled
            scope=server.scope.value if server.scope else ServerScope.USER.value,
            description=server.description or f"{server.server_type.value} server",
            install_id=install_id,
            created_at=datetime.now(timezone.utc)
        )
        
        # Add to database
        self.db_manager.add_server(server_info)
    
    def _generate_install_id(self, server: Server) -> str:
        """Generate a reasonable install_id for a server."""
        if server.server_type == ServerType.DOCKER:
            return f"docker-{server.name}"
        elif server.server_type == ServerType.NPM:
            return f"npm-{server.name}"
        elif server.server_type == ServerType.DOCKER_DESKTOP:
            return f"dd-{server.name}"
        else:
            return f"custom-{server.name}"
    
    def _cleanup_stale_entries(self, context: MCPContext, report: SyncReport):
        """Clean up stale entries and resolve conflicts."""
        # This could include:
        # - Removing duplicate entries
        # - Fixing broken references
        # - Updating metadata
        # For now, just log what we would clean up
        logger.debug(f"Cleanup check for context: {context.scope_name}")
    
    def _verify_config_files(self, context: MCPContext, claude_servers: List[Server], report: SyncReport):
        """Verify configuration files are consistent with Claude's state."""
        config_paths = self.context_detector.get_config_paths(context)
        
        # Check user config file
        user_config = config_paths["user_config"]
        if user_config and user_config.exists():
            self._verify_config_file(user_config, claude_servers, "user", report)
        
        # Check project config file  
        project_config = config_paths["project_config"]
        if project_config and project_config.exists():
            self._verify_config_file(project_config, claude_servers, "project", report)
    
    def _verify_config_file(self, config_file: Path, claude_servers: List[Server], scope: str, report: SyncReport):
        """Verify a specific configuration file."""
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            config_servers = config_data.get("mcpServers", {})
            claude_names = {s.name for s in claude_servers}
            
            # Check for servers in config that aren't in Claude
            for server_name in config_servers:
                if server_name not in claude_names:
                    logger.warning(f"Server {server_name} in {scope} config but not in Claude")
            
        except Exception as e:
            error_msg = f"Failed to verify {scope} config {config_file}: {e}"
            report.errors.append(error_msg)
            logger.error(error_msg)
    
    def force_sync_from_claude(self, context: MCPContext) -> SyncReport:
        """Force complete synchronization from Claude's state."""
        console.print(f"[yellow]🔄 Force syncing from Claude's internal state...[/yellow]")
        
        # Clear local database
        if self.db_manager:
            try:
                # Mark all servers as disabled instead of deleting
                servers = self.db_manager.list_servers_fast()
                for server in servers:
                    self.db_manager.update_server_status(server.name, enabled=False)
                console.print(f"  🗑️ Cleared local database ({len(servers)} servers disabled)")
            except Exception as e:
                console.print(f"  ⚠️ Failed to clear database: {e}")
        
        # Re-sync everything
        return self.sync_all_sources(context, silent=False)
    
    def auto_detect_and_sync(self, explicit_scope: Optional[str] = None, interactive: bool = True) -> tuple[MCPContext, SyncReport]:
        """Auto-detect context and perform synchronization."""
        # Detect context
        context = self.context_detector.detect_context(explicit_scope, interactive)
        
        # Sync based on context
        report = self.sync_all_sources(context)
        
        return context, report