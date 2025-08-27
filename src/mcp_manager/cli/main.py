"""
Main CLI interface for MCP Manager.

Provides comprehensive command-line interface using Click with
rich help formatting and professional modular command structure.
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Optional

import click
from click.shell_completion import CompletionItem
from rich.console import Console
from rich.table import Table

from mcp_manager import __version__
from mcp_manager.core.discovery import ServerDiscovery
from mcp_manager.core.exceptions import MCPManagerError
from mcp_manager.core.simple_manager import SimpleMCPManager
from mcp_manager.core.models import ServerScope, ServerType
from mcp_manager.core.context_detector import ContextDetector, MCPContext
from mcp_manager.core.sync_manager import SyncManager
from mcp_manager.utils.config import get_config
from mcp_manager.utils.logging import setup_logging, get_logger

# Import modular command functions
from mcp_manager.cli.helpers import handle_errors
from mcp_manager.cli.commands.discovery import discovery_commands
from mcp_manager.cli.commands.suite import suite_commands
from mcp_manager.cli.commands.ai import ai_commands
from mcp_manager.cli.commands.analytics import analytics_commands
from mcp_manager.cli.commands.tools import tools_commands
from mcp_manager.cli.commands.system import system_commands
from mcp_manager.cli.commands.monitoring import monitoring_commands
from mcp_manager.cli.commands.ui import ui_commands
from mcp_manager.cli.commands.workflow import workflow_commands
from mcp_manager.cli.commands.api import api_commands
from mcp_manager.cli.commands.proxy import proxy_commands
from mcp_manager.cli.commands.quality import quality_commands
from mcp_manager.cli.test_admin import test_admin

console = Console()
logger = get_logger(__name__)


def _is_infrastructure_server(server) -> bool:
    """Check if a server is an infrastructure component that should be hidden from user lists."""
    # Hide docker-gateway as it's just a proxy for Docker Desktop servers
    if server.name == "docker-gateway":
        return True
    # Hide other internal infrastructure servers
    if server.name.startswith("_") or server.name.endswith("-gateway"):
        return True
    return False


def complete_server_name(ctx, param, incomplete):
    """Completion function for server names."""
    try:
        # Get the current CLI context and manager
        cli_ctx = ctx.find_root().obj
        if not cli_ctx:
            cli_ctx = CLIContext()
        
        manager, _ = cli_ctx.auto_sync_and_get_manager(silent=True)
        
        # Get all servers asynchronously
        import asyncio
        try:
            # Create new event loop if none exists (for completion context)
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            servers = loop.run_until_complete(manager.list_servers())
            
            # Filter by incomplete input and return matching names
            matching_names = [
                server.name for server in servers 
                if server.name.startswith(incomplete) and not _is_infrastructure_server(server)
            ]
            
            return [CompletionItem(name) for name in sorted(matching_names)]
            
        except Exception:
            # Fallback: return empty list if async fails
            return []
            
    except Exception:
        # If anything fails, return empty completion
        return []


class CLIContext:
    """Enhanced CLI context with intelligent scope detection and synchronization."""
    
    def __init__(self):
        self.manager: Optional[SimpleMCPManager] = None
        self.discovery: Optional[ServerDiscovery] = None
        self.context_detector: Optional[ContextDetector] = None
        self.sync_manager: Optional[SyncManager] = None
        self.current_context: Optional[MCPContext] = None
        self._context_cache = {}
        
        # Register cleanup handler
        import atexit
        atexit.register(self._cleanup_sync)
    
    def _cleanup_sync(self):
        """Synchronous cleanup for atexit handler."""
        import asyncio
        try:
            # Create event loop if none exists
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Run cleanup
            loop.run_until_complete(self.cleanup())
        except Exception:
            pass  # Ignore errors during cleanup
    
    async def cleanup(self):
        """Clean up all resources."""
        if self.manager:
            await self.manager.cleanup()
        
    def get_manager(self) -> SimpleMCPManager:
        """Get MCP manager instance."""
        if self.manager is None:
            self.manager = SimpleMCPManager()
        return self.manager
        
    def get_discovery(self) -> ServerDiscovery:
        """Get discovery service instance."""
        if self.discovery is None:
            self.discovery = ServerDiscovery()
        return self.discovery
    
    def get_context_detector(self) -> ContextDetector:
        """Get context detector instance."""
        if self.context_detector is None:
            self.context_detector = ContextDetector()
        return self.context_detector
    
    def get_sync_manager(self) -> SyncManager:
        """Get sync manager instance."""
        if self.sync_manager is None:
            manager = self.get_manager()
            self.sync_manager = SyncManager(
                claude_interface=manager.claude,
                db_manager=manager.db_manager
            )
        return self.sync_manager
    
    def detect_context(self, explicit_scope: Optional[str] = None, force_interactive: bool = False) -> MCPContext:
        """
        Detect and cache the current MCP context.
        
        Args:
            explicit_scope: User-specified scope override
            force_interactive: Force interactive prompts even if cached
            
        Returns:
            MCPContext for the current situation
        """
        # Create cache key
        cache_key = f"{Path.cwd()}:{explicit_scope}"
        
        # Return cached context if available and not forcing interactive
        if not force_interactive and cache_key in self._context_cache:
            return self._context_cache[cache_key]
        
        # Detect context
        detector = self.get_context_detector()
        context = detector.detect_context(explicit_scope, interactive=True)
        
        # Cache the result
        self._context_cache[cache_key] = context
        self.current_context = context
        
        return context
    
    def sync_context(self, context: Optional[MCPContext] = None, silent: bool = False):
        """
        Synchronize data sources for the given or current context.
        
        Args:
            context: MCP context to sync (uses current if None)
            silent: Whether to suppress output
        """
        if context is None:
            context = self.current_context or self.detect_context()
        
        sync_manager = self.get_sync_manager()
        return sync_manager.sync_all_sources(context, silent=silent)
    
    def auto_sync_and_get_manager(self, explicit_scope: Optional[str] = None, silent: bool = True) -> tuple[SimpleMCPManager, MCPContext]:
        """
        Auto-detect context, sync data sources, and return manager.
        This is the main entry point for commands.
        
        Args:
            explicit_scope: User-specified scope override
            silent: Whether to suppress sync output
            
        Returns:
            Tuple of (manager, context)
        """
        # Detect context
        context = self.detect_context(explicit_scope)
        
        # Sync if needed (based on context confidence)
        sync_manager = self.get_sync_manager()
        if sync_manager.context_detector.should_sync_databases(context):
            self.sync_context(context, silent=silent)
        
        # Return manager and context
        return self.get_manager(), context


# Global CLI context
cli_context = CLIContext()


@click.group(invoke_without_command=True)
@click.option(
    "--debug", "-d",
    is_flag=True,
    help="Enable debug logging"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Enable verbose output"
)
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Configuration directory path"
)
@click.option(
    "--menu", "-m",
    is_flag=True,
    help="Launch interactive menu"
)
@click.version_option(version=__version__, prog_name="MCP Manager")
@click.pass_context
def cli(ctx: click.Context, debug: bool, verbose: bool, config_dir: Optional[Path], menu: bool):
    """
    Enterprise-grade MCP server management tool.

    Manage MCP (Model Context Protocol) servers with professional CLI and TUI
    interfaces.

    When called without a command, launches an interactive menu interface.
    """
    # Set up logging
    log_level = "DEBUG" if debug else "INFO" if verbose else "WARNING"
    setup_logging(level=log_level)
    
    # Handle config directory
    if config_dir:
        # TODO: Set custom config directory
        pass
    
    # Launch menu if requested or no command provided
    if menu or ctx.invoked_subcommand is None:
        try:
            from mcp_manager.tui.rich_menu import launch_rich_menu
            launch_rich_menu()
        except ImportError:
            console.print("[red]Rich TUI not available - missing dependencies[/red]")
            console.print("[dim]Install with: pip install rich[/dim]")
        except Exception as e:
            console.print(f"[red]Failed to launch menu: {e}[/red]")
            sys.exit(1)


# Core server management commands
@cli.command("sync-status")
@handle_errors
def sync_status():
    """Sync Claude connection status to database."""
    manager, context = cli_context.auto_sync_and_get_manager()
    
    console.print("[blue]Syncing Claude status to database...[/blue]")
    updated_count = asyncio.run(manager.sync_claude_status())
    
    if updated_count > 0:
        console.print(f"[green]✅ Updated status for {updated_count} servers[/green]")
    else:
        console.print("[yellow]No status changes detected[/yellow]")

@cli.command("list")
@click.option(
    "--scope", "-s",
    type=click.Choice(["user", "project"], case_sensitive=False),
    help="Scope filter"
)
@click.option(
    "--output-format", "-o",
    type=click.Choice(["table", "json"], case_sensitive=False),
    default="table",
    help="Output format"
)
@handle_errors
def list_cmd(scope: Optional[str], output_format: str):
    """List configured MCP servers."""
    # Use manager directly without automatic sync
    manager = cli_context.get_manager()
    context = cli_context.detect_context(scope)
    
    # Show context info if not in silent mode
    if output_format != "json":
        console.print(f"[dim]Context: {context.description}[/dim]")
    
    try:
        all_servers = asyncio.run(manager.list_servers())
        servers = all_servers
        
        
        if output_format == "json":
            import json
            server_data = []
            for server in servers:
                server_data.append({
                    "name": server.name,
                    "type": server.server_type.value,
                    "scope": server.scope.value if server.scope else "unknown",
                    "enabled": server.enabled,
                    "command": server.command,
                    "args": server.args
                })
            console.print(json.dumps(server_data, indent=2))
        else:
            # Table format
            if not servers:
                console.print("[yellow]No MCP servers configured[/yellow]")
                console.print("[dim]💡 Discover and install servers with:[/dim]")
                console.print("[dim]   [cyan]mcp-manager discover[/cyan][/dim]")
                return
            
            table = Table(
                title=f"MCP Servers ({len(servers)} total)",
                show_header=True,
                header_style="bold cyan",
                title_style="bold cyan"
            )
            
            table.add_column("Name", style="green")
            table.add_column("Type", style="blue") 
            table.add_column("Scope", style="yellow")
            table.add_column("Status", style="white", width=12)
            table.add_column("Claude Status", style="cyan", width=12)
            table.add_column("Suites", style="magenta")
            table.add_column("Command", style="dim")
            
            # Get suite memberships for all servers
            from mcp_manager.core.suites.database import SuiteDatabase
            from mcp_manager.core.suites.membership import MembershipManager
            
            try:
                suite_db = SuiteDatabase()
                membership_mgr = MembershipManager(suite_db)
                server_suites = {}
                
                async def get_all_suites():
                    result = {}
                    for server in servers:
                        try:
                            suites = await membership_mgr.get_server_suites(server.name)
                            suite_names = [suite[1] for suite in suites]  # suite[1] is the name
                            result[server.name] = suite_names
                        except Exception:
                            result[server.name] = []
                    return result
                
                server_suites = asyncio.run(get_all_suites())
            except Exception:
                # If suite functionality not available, use empty dict
                server_suites = {}
            
            # Get Claude status from database (already synced)
            # No dynamic checks - database is the source of truth!
            
            # Use database status - it's the source of truth!
            for server in servers:
                # Database enabled flag is the source of truth
                if server.enabled:
                    db_status = "✅ Enabled"
                else:
                    db_status = "❌ Disabled"
                
                # Use database claude_status - it's the source of truth!
                claude_conn = server.claude_status
                
                # Display Claude status from database
                if claude_conn == "connected":
                    claude_status_display = "✓ Connected"
                elif claude_conn == "failed":
                    claude_status_display = "✗ Failed"
                elif claude_conn == "disabled":
                    claude_status_display = "-"  # Disabled servers show nothing
                elif claude_conn == "error_still_in_gateway":
                    claude_status_display = "🔴 ERROR: In Gateway"
                elif claude_conn == "error_still_in_claude":
                    claude_status_display = "🔴 ERROR: In Claude"
                elif claude_conn == "not_in_claude":
                    claude_status_display = "⚠️ Not in Claude"
                elif claude_conn == "not_enabled_in_dd":
                    claude_status_display = "⚠️ Not Enabled in DD"
                elif claude_conn == "gateway_failed":
                    claude_status_display = "✗ Gateway Failed"
                elif claude_conn == "gateway_missing":
                    claude_status_display = "⚠️ Gateway Missing"
                elif claude_conn == "unknown":
                    claude_status_display = "❓ Unknown"
                else:
                    claude_status_display = f"❓ {claude_conn}"
                
                scope_str = server.scope.value if server.scope else "unknown" 
                command_str = f"{server.command} {' '.join(server.args)}"
                
                # Get suite membership
                suites = server_suites.get(server.name, [])
                suite_str = ", ".join(suites[:2])  # Show first 2 suites
                if len(suites) > 2:
                    suite_str += f" +{len(suites)-2}"
                elif not suites:
                    suite_str = "-"
                
                table.add_row(
                    server.name,
                    server.server_type.value,
                    scope_str,
                    db_status,
                    claude_status_display,
                    suite_str,
                    command_str
                )
            
            console.print("")
            console.print(table)
            console.print("")
            console.print("[dim]💡 Use 'mcp-manager server-details <name>' for detailed information[/dim]")
            
    except Exception as e:
        console.print(f"[red]Failed to list servers: {e}[/red]")
        sys.exit(1)


@cli.command("cleanup-duplicates")
@click.option("--dry-run", is_flag=True, help="Show what duplicates would be removed without making changes")
@handle_errors
def cleanup_duplicates(dry_run: bool):
    """Detect and remove duplicate MCP servers based on functionality similarity."""
    
    async def cleanup_async():
        try:
            manager, context = cli_context.auto_sync_and_get_manager(silent=True)
            console.print(f"[dim]Checking for duplicates in: {context.description}[/dim]")
            
            if dry_run:
                console.print("[yellow]🔍 DRY RUN MODE - No changes will be made[/yellow]")
                console.print("")
            
            console.print("🔄 Analyzing servers for functionality duplicates...")
            
            # Run duplicate detection
            if not dry_run:
                results = await manager.detect_and_remove_duplicates()
            else:
                # TODO: Implement dry-run mode that shows what would be removed
                results = {"duplicates_removed": 0, "removal_details": []}
                console.print("[dim]Dry-run duplicate detection not yet implemented[/dim]")
            
            console.print("")
            console.print("📊 Duplicate Cleanup Results:")
            console.print("")
            
            if results["duplicates_removed"] > 0:
                console.print(f"[green]✅ Removed {results['duplicates_removed']} duplicate servers[/green]")
                console.print("")
                
                for detail in results.get("removal_details", []):
                    console.print(f"[red]❌ Removed:[/red] {detail['removed']}")
                    console.print(f"[green]✅ Kept:[/green] {detail['kept']}")
                    console.print(f"[dim]   Similarity: {detail['similarity_score']}% - {', '.join(detail.get('reasons', []))[:80]}[/dim]")
                    console.print("")
            else:
                console.print("[green]✅ No duplicate servers found![/green]")
            
            if "error" in results:
                console.print(f"[red]❌ Error during cleanup: {results['error']}[/red]")
            
        except Exception as e:
            console.print(f"[red]Failed to cleanup duplicates: {e}[/red]")
            sys.exit(1)
    
    asyncio.run(cleanup_async())


@cli.command("sync-fix")
@click.option("--dry-run", is_flag=True, help="Show what would be fixed without making changes")
@handle_errors
def sync_fix(dry_run: bool):
    """Synchronize enabled servers FROM mcp-manager TO Claude."""
    
    async def fix_sync_async():
        try:
            # Use manager directly (mcp-manager is source of truth)
            manager = cli_context.get_manager()
            context = cli_context.detect_context()
            console.print(f"[dim]Synchronizing in: {context.description}[/dim]")
            
            if dry_run:
                console.print("[yellow]🔍 DRY RUN MODE - No changes will be made[/yellow]")
                console.print("")
            
            console.print("🔄 Synchronizing: mcp-manager (master) → Claude (subset)...")
            
            # Get servers from mcp-manager database (source of truth)
            mcp_servers = await manager.list_servers()
            enabled_servers = [s for s in mcp_servers if s.enabled]
            disabled_servers = [s for s in mcp_servers if not s.enabled]
            
            # Get servers from Claude config
            claude_servers = manager.claude.list_servers()
            claude_names = set(s.name for s in claude_servers)
            
            console.print(f"[dim]📊 mcp-manager: {len(enabled_servers)} enabled, {len(disabled_servers)} disabled[/dim]")
            console.print(f"[dim]📊 Claude: {len(claude_servers)} servers configured[/dim]")
            console.print("")
            
            added_to_claude = []
            removed_from_claude = []
            errors = []
            
            # Push enabled servers TO Claude
            for server in enabled_servers:
                if server.name not in claude_names:
                    if not dry_run:
                        try:
                            success = manager.claude.add_server(
                                name=server.name,
                                command=server.command,
                                args=server.args,
                                env=server.env
                            )
                            if success:
                                added_to_claude.append(server.name)
                                console.print(f"[green]➕ Added to Claude: {server.name}[/green]")
                            else:
                                errors.append(f"Failed to add {server.name} to Claude")
                        except Exception as e:
                            errors.append(f"Error adding {server.name}: {e}")
                    else:
                        added_to_claude.append(server.name)
                        console.print(f"[green]➕ Would add to Claude: {server.name}[/green]")
            
            # Remove disabled servers FROM Claude  
            enabled_names = set(s.name for s in enabled_servers)
            for claude_server in claude_servers:
                if claude_server.name not in enabled_names:
                    if not dry_run:
                        try:
                            success = manager.claude.remove_server(claude_server.name)
                            if success:
                                removed_from_claude.append(claude_server.name)
                                console.print(f"[yellow]➖ Removed from Claude: {claude_server.name}[/yellow]")
                            else:
                                errors.append(f"Failed to remove {claude_server.name} from Claude")
                        except Exception as e:
                            errors.append(f"Error removing {claude_server.name}: {e}")
                    else:
                        removed_from_claude.append(claude_server.name)
                        console.print(f"[yellow]➖ Would remove from Claude: {claude_server.name}[/yellow]")
            
            # Show results
            console.print("")
            console.print("📊 Synchronization Results:")
            console.print("")
            
            if added_to_claude:
                console.print(f"[green]✅ Added {len(added_to_claude)} servers to Claude[/green]")
                
            if removed_from_claude:
                console.print(f"[yellow]📤 Removed {len(removed_from_claude)} servers from Claude[/yellow]")
                
            if errors:
                console.print(f"[red]❌ {len(errors)} errors encountered:[/red]")
                for error in errors:
                    console.print(f"[red]   • {error}[/red]")
            
            total_changes = len(added_to_claude) + len(removed_from_claude)
            if total_changes == 0 and not errors:
                console.print("[green]✅ Already synchronized - no changes needed![/green]")
            elif not dry_run:
                console.print(f"[bold green]🎯 Synchronization complete: {total_changes} changes made[/bold green]")
            else:
                console.print(f"[bold blue]🎯 Dry run complete: {total_changes} changes would be made[/bold blue]")
            
        except Exception as e:
            console.print(f"[red]Failed to fix sync issues: {e}[/red]")
            sys.exit(1)
    
    asyncio.run(fix_sync_async())


@cli.command("add")
@click.argument("name")
@click.option("--type", "server_type", type=click.Choice([t.value for t in ServerType], case_sensitive=False), help="Server type")
@click.option("--command", "-c", help="Server command")
@click.option("--args", "-a", multiple=True, help="Command arguments (can be used multiple times)")
@click.option("--env", "-e", multiple=True, help="Environment variables as KEY=VALUE (can be used multiple times)")
@click.option("--scope", type=click.Choice([s.value for s in ServerScope], case_sensitive=False), default="user", help="Installation scope")
@click.option("--working-dir", help="Working directory for the server")
@click.option("--description", help="Server description")
@handle_errors
def add(
    name: str,
    server_type: Optional[str],
    command: Optional[str],
    args: tuple,
    env: tuple,
    scope: str,
    working_dir: Optional[str],
    description: Optional[str]
):
    """Add a new MCP server."""
    
    async def add_server_async():
        try:
            # Use intelligent context detection
            manager, context = cli_context.auto_sync_and_get_manager(explicit_scope=scope, silent=True)
            console.print(f"[dim]Adding server in: {context.description}[/dim]")
            
            # Parse environment variables
            env_dict = {}
            for env_var in env:
                if '=' in env_var:
                    key, value = env_var.split('=', 1)
                    env_dict[key] = value
                else:
                    console.print(f"[yellow]Warning: Invalid environment variable format: {env_var}[/yellow]")
            
            # Convert string types to enums, use context scope if not explicitly provided
            scope_enum = context.scope if scope == "user" and context.scope != ServerScope.USER else ServerScope(scope)
            server_type_enum = ServerType(server_type) if server_type else ServerType.CUSTOM
            
            # Check for similar servers
            if command:
                similar_servers = await manager.check_for_similar_servers(
                    name, server_type_enum, command, list(args)
                )
                
                if similar_servers:
                    console.print(f"[yellow]⚠[/yellow] Found {len(similar_servers)} similar server(s):")
                    for similar in similar_servers:
                        console.print(f"   • {similar['name']}: {similar['description']}")
                    
                    from rich.prompt import Confirm
                    if not Confirm.ask("\nContinue with installation?"):
                        console.print("[dim]Installation cancelled[/dim]")
                        return
            
            # Add server
            server = await manager.add_server(
                name=name,
                server_type=server_type_enum,
                command=command or "",
                args=list(args),
                env=env_dict,
                scope=scope_enum,
                working_dir=working_dir,
                description=description
            )
            
            console.print(f"[green]✅ Added server '{name}' successfully[/green]")
            
            if server:
                console.print(f"[dim]Type: {server.server_type.value}[/dim]")
                console.print(f"[dim]Scope: {server.scope.value}[/dim]")
                if server.command:
                    console.print(f"[dim]Command: {server.command}[/dim]")
            
        except Exception as e:
            console.print(f"[red]❌ Failed to add server: {e}[/red]")
            sys.exit(1)
    
    asyncio.run(add_server_async())


@cli.command("remove")
@click.argument("name", shell_complete=complete_server_name)
@click.option("--scope", type=click.Choice([s.value for s in ServerScope], case_sensitive=False), help="Server scope")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
@handle_errors
def remove(name: str, scope: Optional[str], force: bool):
    """Remove an MCP server."""
    manager = cli_context.get_manager()
    
    try:
        scope_enum = ServerScope(scope) if scope else ServerScope.USER
        
        if not force:
            from rich.prompt import Confirm
            if not Confirm.ask(f"Remove server '{name}'?"):
                console.print("[dim]Removal cancelled[/dim]")
                return
        
        success = asyncio.run(manager.remove_server(name, scope_enum))
        
        if success:
            console.print(f"[green]✅ Removed server '{name}'[/green]")
        else:
            console.print(f"[red]❌ Server '{name}' not found and could not be removed[/red]")
            sys.exit(1)
            
    except Exception as e:
        console.print(f"[red]Failed to remove server: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
@click.option("--scope", type=click.Choice([s.value for s in ServerScope], case_sensitive=False), help="Limit nuke to specific scope (user/project/local)")
@handle_errors
def nuke(force: bool, scope: Optional[str]):
    """Remove ALL MCP servers (nuclear option) - Fast config reset."""
    import json
    import os
    import subprocess
    from pathlib import Path
    
    if not force:
        from rich.prompt import Confirm
        scope_msg = f" in scope '{scope}'" if scope else ""
        console.print(f"[red]⚠️ WARNING: This will remove ALL MCP servers{scope_msg}![/red]")
        console.print("[dim]This action cannot be undone.[/dim]")
        if not Confirm.ask("Are you absolutely sure?"):
            console.print("[dim]Operation cancelled[/dim]")
            return
    
    console.print("💥 💥 💥 💥 💥 💥 💥 💥 💥 💥 💥 💥")
    scope_banner = f" ({scope.upper()} SCOPE)" if scope else ""
    console.print(f"[red]🚀 NUCLEAR OPTION - REMOVING MCPs{scope_banner}![/red]")
    console.print("💥 💥 💥 💥 💥 💥 💥 💥 💥 💥 💥 💥")
    
    async def nuke_all_async():
        # Step 0: Intelligent context detection and comprehensive cleanup
        console.print(f"[blue]Step 0: Detecting context and preparing cleanup...[/blue]")
        
        try:
            # Use intelligent context detection
            manager, context = cli_context.auto_sync_and_get_manager(explicit_scope=scope, silent=True)
            console.print(f"  🎯 Detected context: {context.description}")
            
            # Get servers for cleanup - force sync first to get accurate state
            sync_manager = cli_context.get_sync_manager()
            sync_report = sync_manager.sync_all_sources(context, silent=True)
            
            all_servers = await manager.list_servers()
            if scope:
                servers = [s for s in all_servers if s.scope and s.scope.value == scope]
                console.print(f"  🎯 Filtering to {len(servers)} servers in '{scope}' scope (of {len(all_servers)} total)")
            else:
                servers = all_servers
                console.print(f"  🌍 Processing all {len(servers)} servers across all scopes")
            
            removed_count = 0
            for server in servers:
                try:
                    # REMOVE ALL SERVERS INCLUDING DOCKER DESKTOP - NO EXCEPTIONS!
                    # Use the server's actual scope if available
                    scope_param = server.scope if server.scope else None
                    success = await manager.remove_server(server.name, scope_param)
                    if success:
                        removed_count += 1
                        console.print(f"  ✅ Removed: {server.name} ({server.scope.value if server.scope else 'unknown'}) - {server.server_type.value}")
                    else:
                        console.print(f"  ⚠️ Server not found in Claude config: {server.name}")
                except Exception as e:
                    console.print(f"  ⚠️ Error removing {server.name}: {e}")
            
            console.print(f"  📊 Removed {removed_count} servers from database")
        except Exception as e:
            console.print(f"  ⚠️ Manager unavailable, skipping database cleanup: {e}")
            console.print("  ✨ Will proceed with file-based cleanup")
        
        # Step 1: Kill zombie MCP processes
        console.print("[blue]Step 1: Killing zombie MCP processes...[/blue]")
        try:
            subprocess.run(["pkill", "-f", "mcp"], capture_output=True)
            subprocess.run(["pkill", "-f", "npx.*mcp"], capture_output=True)
        except:
            pass
        
        # Step 2: Clean up Docker containers
        console.print("[blue]Step 2: Cleaning Docker MCP containers...[/blue]")
        try:
            subprocess.run(["docker", "stop", "$(docker ps -q --filter ancestor=*mcp*)"], shell=True, capture_output=True)
            subprocess.run(["docker", "rm", "$(docker ps -aq --filter ancestor=*mcp*)"], shell=True, capture_output=True)
        except:
            pass
        
        # Step 3: REMOVE Docker Desktop MCP servers completely
        console.print("[blue]Step 3: REMOVING Docker Desktop MCP servers completely...[/blue]")
        try:
            result = subprocess.run(["docker", "mcp", "server", "list"], capture_output=True, text=True)
            if result.returncode == 0:
                removed_dd_count = 0
                for line in result.stdout.strip().split('\n'):
                    if line and not line.startswith('NAME'):
                        parts = line.split()
                        if len(parts) > 0:
                            server_name = parts[0]
                            # First disable, then the manager will remove from database
                            subprocess.run(["docker", "mcp", "server", "disable", server_name], capture_output=True)
                            console.print(f"  ✅ Disabled Docker Desktop server: {server_name}")
                            removed_dd_count += 1
                
                # Now remove Docker Desktop servers from our database too
                try:
                    if 'manager' in locals():
                        dd_servers = [s for s in all_servers if s.server_type == ServerType.DOCKER_DESKTOP]
                        for server in dd_servers:
                            await manager.remove_server(server.name, server.scope)
                            console.print(f"  🗑️ Removed from database: {server.name}")
                except Exception as e:
                    console.print(f"  ⚠️ Error removing Docker Desktop servers from database: {e}")
                
                console.print(f"  📊 Processed {removed_dd_count} Docker Desktop servers")
        except:
            pass
        
        # Step 4: Clean configuration files
        scope_msg = f" (scope: {scope})" if scope else ""
        console.print(f"[blue]Step 4: Cleaning configuration files{scope_msg}...[/blue]")
        
        # Scope-aware configuration clearing
        if not scope or scope == "user":
            # Claude Code user config
            user_config = Path.home() / ".config" / "claude-code" / "mcp-servers.json"
            if user_config.exists():
                with open(user_config, 'w') as f:
                    json.dump({"mcpServers": {}}, f, indent=2)
                console.print(f"  ✅ Cleared user config: {user_config}")
        
        if not scope or scope == "project":
            # Claude Code project config
            project_config = Path.cwd() / ".mcp.json"
            if project_config.exists():
                with open(project_config, 'w') as f:
                    json.dump({"mcpServers": {}}, f, indent=2)
                console.print(f"  ✅ Cleared project config: {project_config}")
        
        if not scope or scope in ["user", "project"]:
            # Claude internal config (scope-aware)
            claude_config = Path.home() / ".claude.json"
            if claude_config.exists():
                try:
                    with open(claude_config, 'r') as f:
                        config = json.load(f)
                    
                    # Clear based on scope
                    if not scope:
                        # Clear everything
                        if "mcpServers" in config:
                            config["mcpServers"] = {}
                        if "projectConfigs" in config:
                            for project_path, project_config_data in config["projectConfigs"].items():
                                if "mcpServers" in project_config_data:
                                    project_config_data["mcpServers"] = {}
                        if "projects" in config:
                            for project_path, project_data in config["projects"].items():
                                if "mcpServers" in project_data:
                                    project_data["mcpServers"] = {}
                        console.print(f"  ✅ Cleared all Claude internal config: {claude_config}")
                    elif scope == "user":
                        # Clear only global user servers
                        if "mcpServers" in config:
                            config["mcpServers"] = {}
                        console.print(f"  ✅ Cleared user servers in Claude internal config: {claude_config}")
                    elif scope == "project":
                        # Clear only current project servers
                        current_dir = str(Path.cwd())
                        if "projectConfigs" in config:
                            for project_path, project_config_data in config["projectConfigs"].items():
                                if project_path == current_dir and "mcpServers" in project_config_data:
                                    project_config_data["mcpServers"] = {}
                        if "projects" in config:
                            for project_path, project_data in config["projects"].items():
                                if project_path == current_dir and "mcpServers" in project_data:
                                    project_data["mcpServers"] = {}
                        console.print(f"  ✅ Cleared project servers in Claude internal config: {claude_config}")
                    
                    with open(claude_config, 'w') as f:
                        json.dump(config, f, indent=2)
                        
                except:
                    pass
        
        if not scope or scope == "local":
            # MCP Manager database
            db_path = Path.home() / ".config" / "mcp-manager" / "mcp_manager.db"
            if db_path.exists():
                try:
                    os.remove(db_path)
                    console.print(f"  ✅ Removed local database: {db_path}")
                except:
                    pass
    
    try:
        # Run the async nuclear cleanup
        asyncio.run(nuke_all_async())
        
        # Force resync to ensure everything is clean
        console.print(f"[blue]Final Step: Verifying cleanup and syncing data sources...[/blue]")
        manager, context = cli_context.auto_sync_and_get_manager(explicit_scope=scope, silent=False)
        
        console.print("💥 💥 💥 💥 💥 💥 💥 💥 💥 💥 💥 💥")
        scope_completion = f" ({scope.upper()} SCOPE)" if scope else ""
        console.print(f"  🚀 Ready for fresh MCP server installation{scope_completion}!")
        console.print("💥 💥 💥 💥 💥 💥 💥 💥 💥 💥 💥 💥")
        if scope:
            console.print(f"\n💡 [dim]Note: Only {scope} scope was cleared. Other scopes remain intact.[/dim]")
        console.print(f"\n💡 [dim]To start fresh, use:[/dim]")
        scope_flag = f" --scope {scope}" if scope else ""
        console.print(f"   [cyan]mcp-manager install-package modelcontextprotocol-filesystem{scope_flag}[/cyan]")
        console.print(f"   [cyan]mcp-manager install-suite --suite-name test{scope_flag}[/cyan]")
        
    except Exception as e:
        console.print(f"[red]❌ Nuclear cleanup failed: {e}[/red]")
        sys.exit(1)


@cli.command("enable")
@click.argument("name", shell_complete=complete_server_name)
@click.option("--scope", type=click.Choice([s.value for s in ServerScope], case_sensitive=False), help="Server scope to enable in")
@click.option("--dry-run", is_flag=True, help="Show what would be changed without making changes")
@handle_errors
def enable(name: str, scope: Optional[str], dry_run: bool):
    """Enable an MCP server or all servers with 'all'."""
    
    # Handle 'all' argument
    if name.lower() == "all":
        async def enable_all_async():
            try:
                manager, context = cli_context.auto_sync_and_get_manager(silent=True)
                console.print(f"[dim]Enabling all servers in: {context.description}[/dim]")
                
                if dry_run:
                    console.print("[yellow]🔍 DRY RUN MODE - No changes will be made[/yellow]")
                    console.print("")
                
                console.print("[blue]🎯 Enabling ALL servers[/blue]")
                console.print("")
                
                # Get all servers
                all_servers = await manager.list_servers()
                
                if not all_servers:
                    console.print("[yellow]📭 No servers found to enable[/yellow]")
                    return
                
                disabled_servers = [server for server in all_servers if not server.enabled]
                already_enabled = [server for server in all_servers if server.enabled]
                
                console.print(f"[green]📦 Servers to ENABLE ({len(disabled_servers)}):[/green]")
                for server in disabled_servers:
                    console.print(f"  ✅ {server.name}")
                
                if already_enabled:
                    console.print("")
                    console.print(f"[dim]📦 Already enabled ({len(already_enabled)}):[/dim]")
                    for server in already_enabled:
                        console.print(f"  ➡️ {server.name}")
                
                if not dry_run:
                    if disabled_servers:
                        console.print("")
                        from rich.prompt import Confirm
                        if not Confirm.ask(f"[bold]Enable {len(disabled_servers)} servers?[/bold]"):
                            console.print("[dim]Enable all cancelled[/dim]")
                            return
                        
                        console.print("")
                        console.print("[blue]🔄 Enabling servers...[/blue]")
                        
                        enabled_count = 0
                        for server in disabled_servers:
                            success = await manager.enable_server(server.name)
                            if success:
                                enabled_count += 1
                                console.print(f"  [green]✅ Enabled: {server.name}[/green]")
                            else:
                                console.print(f"  [red]❌ Failed to enable: {server.name}[/red]")
                        
                        console.print("")
                        console.print(f"[bold green]🎯 Enabled {enabled_count} of {len(disabled_servers)} servers![/bold green]")
                        
                        # Sync Claude status after bulk enable operation
                        console.print("[dim]Syncing Claude status...[/dim]")
                        await manager.sync_claude_status()
                    else:
                        console.print("")
                        console.print("[dim]All servers are already enabled[/dim]")
                else:
                    console.print("")
                    console.print("[dim]Dry run complete - no changes made[/dim]")
                    
            except Exception as e:
                console.print(f"[red]Failed to enable all servers: {e}[/red]")
                import sys
                sys.exit(1)
        
        asyncio.run(enable_all_async())
        return
    
    # Handle single server enable
    manager = cli_context.get_manager()
    
    try:
        # Convert scope string to enum if provided
        scope_enum = ServerScope(scope) if scope else None
        
        success = asyncio.run(manager.enable_server(name))
        if success:
            scope_msg = f" in {scope} scope" if scope else ""
            console.print(f"[green]✅ Enabled server '{name}'{scope_msg}[/green]")
        else:
            scope_msg = f" in {scope} scope" if scope else ""
            console.print(f"[red]❌ Server '{name}' not found{scope_msg} and could not be enabled[/red]")
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]Failed to enable server: {e}[/red]")
        sys.exit(1)


@cli.command("disable")
@click.argument("name", shell_complete=complete_server_name)
@click.option("--scope", type=click.Choice([s.value for s in ServerScope], case_sensitive=False), help="Server scope to disable in")
@click.option("--dry-run", is_flag=True, help="Show what would be changed without making changes")
@handle_errors
def disable(name: str, scope: Optional[str], dry_run: bool):
    """Disable an MCP server or all servers with 'all'."""
    
    # Handle 'all' argument
    if name.lower() == "all":
        async def disable_all_async():
            try:
                manager, context = cli_context.auto_sync_and_get_manager(silent=True)
                console.print(f"[dim]Disabling all servers in: {context.description}[/dim]")
                
                if dry_run:
                    console.print("[yellow]🔍 DRY RUN MODE - No changes will be made[/yellow]")
                    console.print("")
                
                console.print("[blue]🎯 Disabling ALL servers[/blue]")
                console.print("")
                
                # Get all servers
                all_servers = await manager.list_servers()
                
                if not all_servers:
                    console.print("[yellow]📭 No servers found to disable[/yellow]")
                    return
                
                # Debug: Show actual enabled status
                for server in all_servers:
                    logger.debug(f"Server {server.name}: enabled={server.enabled}, claude_status={server.claude_status}")
                
                enabled_servers = [server for server in all_servers if server.enabled]
                already_disabled = [server for server in all_servers if not server.enabled]
                
                console.print(f"[red]📦 Servers to DISABLE ({len(enabled_servers)}):[/red]")
                for server in enabled_servers:
                    console.print(f"  ❌ {server.name}")
                
                if already_disabled:
                    console.print("")
                    console.print(f"[dim]📦 Already disabled ({len(already_disabled)}):[/dim]")
                    for server in already_disabled:
                        console.print(f"  ➡️ {server.name}")
                
                if not dry_run:
                    if enabled_servers:
                        console.print("")
                        from rich.prompt import Confirm
                        if not Confirm.ask(f"[bold]Disable {len(enabled_servers)} servers?[/bold]"):
                            console.print("[dim]Disable all cancelled[/dim]")
                            return
                        
                        console.print("")
                        console.print("[blue]🔄 Disabling servers...[/blue]")
                        
                        disabled_count = 0
                        for server in enabled_servers:
                            success = await manager.disable_server(server.name)
                            if success:
                                disabled_count += 1
                                console.print(f"  [yellow]❌ Disabled: {server.name}[/yellow]")
                            else:
                                console.print(f"  [red]❌ Failed to disable: {server.name}[/red]")
                        
                        console.print("")
                        console.print(f"[bold green]🎯 Disabled {disabled_count} of {len(enabled_servers)} servers![/bold green]")
                        
                        # Sync Claude status after bulk disable operation  
                        console.print("[dim]Syncing Claude status...[/dim]")
                        await manager.sync_claude_status()
                    else:
                        console.print("")
                        console.print("[dim]All servers are already disabled[/dim]")
                else:
                    console.print("")
                    console.print("[dim]Dry run complete - no changes made[/dim]")
                    
            except Exception as e:
                console.print(f"[red]Failed to disable all servers: {e}[/red]")
                import sys
                sys.exit(1)
        
        asyncio.run(disable_all_async())
        return
    
    # Handle single server disable
    manager = cli_context.get_manager()
    
    try:
        # Convert scope string to enum if provided
        scope_enum = ServerScope(scope) if scope else None
        
        success = asyncio.run(manager.disable_server(name))
        if success:
            scope_msg = f" in {scope} scope" if scope else ""
            console.print(f"[green]✅ Disabled server '{name}'{scope_msg}[/green]")
        else:
            scope_msg = f" in {scope} scope" if scope else ""
            console.print(f"[red]❌ Server '{name}' not found{scope_msg} and could not be disabled[/red]")
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]Failed to disable server: {e}[/red]")
        sys.exit(1)


# Old inconsistent suite commands cleaned up - now using mcp-manager suite subcommands


@cli.command("server-details")
@click.argument("name", shell_complete=complete_server_name)
@click.option("--scope", type=click.Choice([s.value for s in ServerScope], case_sensitive=False), help="Specify server scope for details")
@handle_errors
def server_details(name: str, scope: Optional[str]):
    """Show detailed information about a specific MCP server."""
    manager = cli_context.get_manager()
    
    try:
        # Convert scope string to enum if provided
        scope_enum = ServerScope(scope) if scope else None
        
        # Get server details
        details = asyncio.run(manager.get_server_details(name))
        
        if not details:
            scope_msg = f" in {scope} scope" if scope else ""
            console.print(f"[red]❌ Server '{name}' not found{scope_msg}[/red]")
            console.print("[yellow]💡 Use 'mcp-manager list' to see available servers[/yellow]")
            sys.exit(1)
        
        # Display server details
        from rich.panel import Panel
        from rich.table import Table
        
        # Create details table
        details_table = Table(show_header=False, box=None)
        details_table.add_column("Property", style="cyan", width=15)
        details_table.add_column("Value", style="white")
        
        details_table.add_row("Name", details.get("name", name))
        details_table.add_row("Type", details.get("type", "Unknown"))
        details_table.add_row("Status", "✅ Enabled" if details.get("enabled", False) else "❌ Disabled")
        details_table.add_row("Command", details.get("command", "N/A"))
        details_table.add_row("Args", ", ".join(details.get("args", [])) if details.get("args") else "None")
        
        if details.get("env"):
            env_str = ", ".join([f"{k}={v}" for k, v in details.get("env", {}).items()])
            details_table.add_row("Environment", env_str)
        
        if details.get("description"):
            details_table.add_row("Description", details.get("description"))
        
        # Show scope if specified
        scope_title = f" ({scope.upper()} SCOPE)" if scope else ""
        console.print(Panel(details_table, title=f"📋 Server Details: {name}{scope_title}", border_style="blue"))
        
        # Show available tools if any
        tools = details.get("tools", [])
        if tools:
            console.print(f"\n[bold]Available Tools ({len(tools)}):[/bold]")
            tools_table = Table(show_header=True, header_style="bold cyan")
            tools_table.add_column("Tool", style="green")
            tools_table.add_column("Description", style="dim")
            
            for tool in tools[:10]:  # Show first 10 tools
                tool_name = tool.get("name", "Unknown")
                tool_desc = tool.get("description", "No description")
                tools_table.add_row(tool_name, tool_desc)
            
            console.print(tools_table)
            
            if len(tools) > 10:
                console.print(f"[dim]... and {len(tools) - 10} more tools[/dim]")
        
        console.print(f"\n[dim]💡 Use 'mcp-manager enable {name}' or 'mcp-manager disable {name}' to control this server[/dim]")
        
    except Exception as e:
        console.print(f"[red]Failed to get server details: {e}[/red]")
        sys.exit(1)


# Register all modular command groups
def register_commands():
    """Register all modular command groups with the main CLI."""
    
    # Discovery commands
    for cmd in discovery_commands(cli_context):
        cli.add_command(cmd)
    
    # Suite commands
    for cmd in suite_commands(cli_context):
        cli.add_command(cmd)
    
    # AI commands
    for cmd in ai_commands(cli_context):
        cli.add_command(cmd)
    
    # Analytics commands
    for cmd in analytics_commands(cli_context):
        cli.add_command(cmd)
    
    # Tools commands
    for cmd in tools_commands(cli_context):
        cli.add_command(cmd)
    
    # System commands
    for cmd in system_commands(cli_context):
        cli.add_command(cmd)
    
    # Monitoring commands
    for cmd in monitoring_commands(cli_context):
        cli.add_command(cmd)
    
    # UI commands
    for cmd in ui_commands(cli_context):
        cli.add_command(cmd)
    
    # Workflow commands
    for cmd in workflow_commands(cli_context):
        cli.add_command(cmd)
    
    # API commands
    for cmd in api_commands(cli_context):
        cli.add_command(cmd)
    
    # Proxy commands
    for cmd in proxy_commands(cli_context):
        cli.add_command(cmd)
    
    # Quality commands
    for cmd in quality_commands(cli_context):
        cli.add_command(cmd)
    
    # Test admin commands
    cli.add_command(test_admin)


# Register all commands
register_commands()

# Add command aliases for shorter typing (with completion support)
cli.add_command(list_cmd, name="ls")  # mcp-manager ls
cli.add_command(remove, name="rm")  # mcp-manager rm  
cli.add_command(enable, name="en")  # mcp-manager en
cli.add_command(disable, name="dis")  # mcp-manager dis

# Suite command aliases for backwards compatibility and convenience
# Get the suite group that was registered earlier
suite_group = None
for command_name, command in cli.commands.items():
    if command_name == "suite":
        suite_group = command
        break

if suite_group:
    # Create convenient top-level aliases that map to suite subcommands
    @cli.command("activate-suites")
    @click.argument("suite_names", nargs=-1, required=True)
    @click.option("--dry-run", is_flag=True, help="Show what would be changed without making changes")
    @click.option("--include-individual", is_flag=True, help="Also keep individual servers (not in any suite) enabled")
    def activate_suites_alias(suite_names, dry_run, include_individual):
        """DEPRECATED: Use 'mcp-manager suite activate' instead. Activate ONLY servers in specified suites."""
        console.print("[yellow]⚠️  DEPRECATED: Use 'mcp-manager suite activate' for the new consistent interface[/yellow]")
        import subprocess
        import sys
        cmd = ["mcp-manager", "suite", "activate"] + list(suite_names)
        if dry_run:
            cmd.append("--dry-run")
        if include_individual:
            cmd.append("--include-individual")
        sys.exit(subprocess.call(cmd))
    
    @cli.command("activate-except-suite")
    @click.argument("suite_name")
    @click.option("--dry-run", is_flag=True, help="Show what would be changed without making changes")
    def activate_except_suite_alias(suite_name, dry_run):
        """DEPRECATED: Use 'mcp-manager suite activate-except' instead. Activate all except specified suite."""
        console.print("[yellow]⚠️  DEPRECATED: Use 'mcp-manager suite activate-except' for the new consistent interface[/yellow]")
        import subprocess
        import sys
        cmd = ["mcp-manager", "suite", "activate-except", suite_name]
        if dry_run:
            cmd.append("--dry-run")
        sys.exit(subprocess.call(cmd))
    
    # Short convenient aliases 
    cli.add_command(activate_suites_alias, name="act")  # mcp-manager act


@cli.command("install-completion")
@click.argument("shell", required=False, type=click.Choice(["bash", "zsh", "fish"]))
@click.option("--auto-install", "-y", is_flag=True, help="Automatically install to appropriate completion directory")
def install_completion(shell, auto_install):
    """Install shell completion for mcp-manager commands using SECURE static files.
    
    This enables Tab completion for server names in commands like:
    - mcp-manager remove <TAB> 
    - mcp-manager enable <TAB>
    - mcp-manager server-details <TAB>
    
    Uses static completion files instead of dangerous eval() for security.
    
    Examples:
        mcp-manager install-completion          # Show manual instructions
        mcp-manager install-completion -y       # Auto-install for current shell
        mcp-manager install-completion zsh -y   # Auto-install for specific shell
    """
    if not shell:
        # Auto-detect shell
        import os
        shell_path = os.environ.get("SHELL", "")
        if "bash" in shell_path:
            shell = "bash"
        elif "zsh" in shell_path:
            shell = "zsh"
        elif "fish" in shell_path:
            shell = "fish"
        else:
            console.print("[red]Could not detect shell. Please specify: bash, zsh, or fish[/red]")
            sys.exit(1)
    
    console.print(f"[blue]Setting up SECURE {shell} completion for mcp-manager...[/blue]")
    
    # Generate static completion script (secure approach)
    import subprocess
    import os
    try:
        env = os.environ.copy()
        env[f"_MCP_MANAGER_COMPLETE"] = f"{shell}_source"
        
        result = subprocess.run([
            "mcp-manager"
        ], env=env, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            console.print(f"[red]Failed to generate completion script: {result.stderr}[/red]")
            return
            
        completion_script = result.stdout
        
    except Exception as e:
        console.print(f"[red]Failed to generate completion: {e}[/red]")
        return
    
    if shell == "bash":
        # Bash completion using bash-completion system
        system_dir = Path("/usr/local/etc/bash_completion.d")
        user_dir = Path.home() / ".local" / "share" / "bash-completion" / "completions"
        completion_file = "mcp-manager"
        
        console.print(f"\n[bold]Bash completion (static file approach):[/bold]")
        
        if auto_install:
            # Try system directory first, fall back to user directory
            target_dir = system_dir if system_dir.exists() and os.access(system_dir, os.W_OK) else user_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / completion_file
            
            target_file.write_text(completion_script)
            console.print(f"[green]✅ Installed completion to: {target_file}[/green]")
            
        else:
            console.print(f"\n[bold]Manual installation:[/bold]")
            console.print(f"1. Save completion script to: {system_dir / completion_file}")
            console.print(f"   Or user directory: {user_dir / completion_file}")
            console.print(f"2. Ensure bash-completion is enabled")
            console.print(f"3. Restart terminal")
        
    elif shell == "zsh":
        # Zsh completion using fpath system (secure)
        system_dir = Path("/usr/local/share/zsh/site-functions") 
        user_dir = Path.home() / ".local" / "share" / "zsh" / "site-functions"
        completion_file = "_mcp-manager"
        
        console.print(f"\n[bold]Zsh completion (secure fpath approach):[/bold]")
        
        if auto_install:
            # Try system directory first, fall back to user directory  
            target_dir = system_dir if system_dir.exists() and os.access(system_dir, os.W_OK) else user_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / completion_file
            
            target_file.write_text(completion_script)
            console.print(f"[green]✅ Installed completion to: {target_file}[/green]")
            
            # Add to fpath if using user directory
            if target_dir == user_dir:
                zshrc = Path.home() / ".zshrc"
                zshrc_content = zshrc.read_text() if zshrc.exists() else ""
                
                fpath_line = f"fpath=({user_dir} $fpath)"
                if str(user_dir) not in zshrc_content:
                    # Insert before compinit
                    lines = zshrc_content.split('\n')
                    compinit_index = next((i for i, line in enumerate(lines) if 'compinit' in line), len(lines))
                    lines.insert(compinit_index, f"# MCP Manager completion")
                    lines.insert(compinit_index + 1, fpath_line)
                    
                    zshrc.write_text('\n'.join(lines))
                    console.print(f"[green]✅ Added {user_dir} to fpath in .zshrc[/green]")
            
            # Remove completion cache to force reload
            zcompdump = Path.home() / ".zcompdump"
            if zcompdump.exists():
                zcompdump.unlink()
                console.print("[green]✅ Cleared completion cache[/green]")
                
        else:
            console.print(f"\n[bold]Manual installation:[/bold]")
            console.print(f"1. Save completion script to: {system_dir / completion_file}")
            console.print(f"   Or user directory: {user_dir / completion_file}")
            console.print(f"2. If using user dir, add to .zshrc before compinit:")
            console.print(f"   [dim]fpath=({user_dir} $fpath)[/dim]")
            console.print(f"3. Remove ~/.zcompdump and restart zsh")
        
    elif shell == "fish":
        # Fish completion (already secure by design)
        completion_dir = Path.home() / ".config" / "fish" / "completions"
        completion_file = completion_dir / "mcp-manager.fish"
        
        console.print(f"\n[bold]Fish completion (secure by design):[/bold]")
        
        if auto_install:
            completion_dir.mkdir(parents=True, exist_ok=True)
            if completion_file.exists():
                console.print(f"[yellow]Completion file already exists: {completion_file}[/yellow]")
            else:
                completion_file.write_text(completion_script)
                console.print(f"[green]✅ Created fish completion: {completion_file}[/green]")
        else:
            console.print(f"\n[bold]Manual installation:[/bold]")
            console.print(f"Save completion script to: {completion_file}")
    
    if auto_install:
        console.print(f"\n[green]✅ SECURE {shell} completion installed![/green]")
        console.print("\n[bold]Restart your terminal to activate completion[/bold]")
    else:
        console.print(f"\n[green]✅ {shell} completion setup instructions provided![/green]")
    
    console.print(f"\n[yellow]🛡️  Security Note: Uses static completion files instead of dangerous eval()[/yellow]")
    console.print("\n💡 [bold]After installation, you can use Tab completion:[/bold]")
    console.print("   [dim]mcp-manager remove <TAB>           # Shows all server names[/dim]")
    console.print("   [dim]mcp-manager remove not<TAB>        # Shows notionhq-notion-mcp-server[/dim]")
    console.print("   [dim]mcp-manager rm up<TAB>             # Shows upstash-context7-mcp[/dim]")
    console.print("   [dim]mcp-manager server-details <TAB>   # Shows all server names[/dim]")


def main():
    """Main CLI entry point."""
    cli()


if __name__ == "__main__":
    main()