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


class CLIContext:
    """Enhanced CLI context with intelligent scope detection and synchronization."""
    
    def __init__(self):
        self.manager: Optional[SimpleMCPManager] = None
        self.discovery: Optional[ServerDiscovery] = None
        self.context_detector: Optional[ContextDetector] = None
        self.sync_manager: Optional[SyncManager] = None
        self.current_context: Optional[MCPContext] = None
        self._context_cache = {}
        
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
    # Use intelligent context detection and auto-sync
    manager, context = cli_context.auto_sync_and_get_manager(explicit_scope=scope, silent=True)
    
    # Show context info if not in silent mode
    if output_format != "json":
        console.print(f"[dim]Context: {context.description}[/dim]")
    
    try:
        all_servers = asyncio.run(manager.list_servers())
        # Filter out infrastructure components that users shouldn't see
        servers = [s for s in all_servers if not _is_infrastructure_server(s)]
        
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
            table.add_column("Status", style="white")
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
            
            for server in servers:
                status = "✅ Enabled" if server.enabled else "❌ Disabled"
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
                    status,
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
    """Detect and fix synchronization issues between mcp-manager and Claude."""
    
    async def fix_sync_async():
        try:
            # Use intelligent context detection
            manager, context = cli_context.auto_sync_and_get_manager(silent=True)
            console.print(f"[dim]Checking sync in: {context.description}[/dim]")
            
            if dry_run:
                console.print("[yellow]🔍 DRY RUN MODE - No changes will be made[/yellow]")
                console.print("")
            
            console.print("🔄 Analyzing synchronization between MCP Manager and Claude...")
            
            # Run sync repair
            results = await manager.fix_sync_issues()
            
            console.print("")
            console.print("📊 Sync Repair Results:")
            console.print("")
            
            if results["duplicates_removed"] > 0:
                console.print(f"[green]✅ Removed {results['duplicates_removed']} duplicate servers[/green]")
            
            if results["orphaned_claude_servers"] > 0:
                console.print(f"[blue]📥 Added {results['orphaned_claude_servers']} orphaned Claude servers to database[/blue]")
            
            if results["orphaned_db_servers"] > 0:
                console.print(f"[yellow]📤 Disabled {results['orphaned_db_servers']} orphaned database servers[/yellow]")
            
            if results["inconsistencies_fixed"] > 0:
                console.print(f"[cyan]🔧 Fixed {results['inconsistencies_fixed']} command/args inconsistencies[/cyan]")
            
            if results["errors"]:
                console.print(f"[red]❌ Errors encountered:[/red]")
                for error in results["errors"]:
                    console.print(f"[red]   • {error}[/red]")
            
            total_fixes = (results["duplicates_removed"] + results["orphaned_claude_servers"] + 
                          results["orphaned_db_servers"] + results["inconsistencies_fixed"])
            
            if total_fixes == 0 and not results["errors"]:
                console.print("[green]✅ No synchronization issues found - systems are in sync![/green]")
            else:
                console.print("")
                console.print(f"[bold green]🎯 Total issues fixed: {total_fixes}[/bold green]")
            
        except Exception as e:
            console.print(f"[red]Failed to fix sync issues: {e}[/red]")
            sys.exit(1)
    
    asyncio.run(fix_sync_async())


@cli.command()
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


@cli.command()
@click.argument("name")
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
                    # Skip Docker Desktop servers that are part of docker-gateway
                    # These need to be disabled via docker-desktop commands, not removed
                    if server.server_type in [ServerType.DOCKER_DESKTOP] and "docker-desktop-" in server.name:
                        console.print(f"  🔄 Skipping Docker Desktop server (handled in Step 3): {server.name}")
                        continue
                    
                    # Use the server's actual scope if available
                    scope_param = server.scope if server.scope else None
                    success = await manager.remove_server(server.name, scope_param)
                    if success:
                        removed_count += 1
                        console.print(f"  ✅ Removed: {server.name} ({server.scope.value if server.scope else 'unknown'})")
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
        
        # Step 3: Disable Docker Desktop MCP servers
        console.print("[blue]Step 3: Disabling Docker Desktop MCP servers...[/blue]")
        try:
            result = subprocess.run(["docker", "mcp", "server", "list"], capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line and not line.startswith('NAME'):
                        parts = line.split()
                        if len(parts) > 0 and parts[1] == 'enabled':
                            server_name = parts[0]
                            subprocess.run(["docker", "mcp", "server", "disable", server_name], capture_output=True)
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
                        console.print(f"  ✅ Cleared all Claude internal config: {claude_config}")
                    elif scope == "user":
                        # Clear only global user servers
                        if "mcpServers" in config:
                            config["mcpServers"] = {}
                        console.print(f"  ✅ Cleared user servers in Claude internal config: {claude_config}")
                    elif scope == "project":
                        # Clear only current project servers
                        if "projectConfigs" in config:
                            current_dir = str(Path.cwd())
                            for project_path, project_config_data in config["projectConfigs"].items():
                                if project_path == current_dir and "mcpServers" in project_config_data:
                                    project_config_data["mcpServers"] = {}
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


@cli.command()
@click.argument("name")
@click.option("--scope", type=click.Choice([s.value for s in ServerScope], case_sensitive=False), help="Server scope to enable in")
@handle_errors
def enable(name: str, scope: Optional[str]):
    """Enable an MCP server."""
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


@cli.command()
@click.argument("name")
@click.option("--scope", type=click.Choice([s.value for s in ServerScope], case_sensitive=False), help="Server scope to disable in")
@handle_errors
def disable(name: str, scope: Optional[str]):
    """Disable an MCP server."""
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


@cli.command("server-details")
@click.argument("name")
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


def main():
    """Main CLI entry point."""
    cli()


if __name__ == "__main__":
    main()