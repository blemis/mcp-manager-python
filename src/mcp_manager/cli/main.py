"""
Main CLI interface for MCP Manager.

Provides comprehensive command-line interface using Click with
rich help formatting and professional command structure.
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.table import Table
from rich.text import Text

from mcp_manager import __version__
from mcp_manager.core.discovery import ServerDiscovery
from mcp_manager.core.exceptions import MCPManagerError
from mcp_manager.core.simple_manager import SimpleMCPManager
from mcp_manager.core.models import ServerScope, ServerType
from mcp_manager.core.change_detector import detect_external_changes, ChangeDetector
from mcp_manager.core.background_monitor import BackgroundMonitor
from mcp_manager.utils.config import get_config
from mcp_manager.utils.logging import setup_logging
from mcp_manager.utils.logging import get_logger
# from mcp_manager.cli import enhanced_commands  # TODO: Add enhanced commands module

console = Console()
logger = get_logger(__name__)


class CLIContext:
    """CLI context for passing state between commands."""
    
    def __init__(self):
        self.manager: Optional[SimpleMCPManager] = None
        self.discovery: Optional[ServerDiscovery] = None
        
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


# Global CLI context
cli_context = CLIContext()


def _generate_install_id(result) -> str:
    """Generate consistent install ID for a discovery result."""
    if result.server_type == ServerType.NPM:
        return result.package.replace("@", "").replace("/", "-").replace("server-", "")
    elif result.server_type == ServerType.DOCKER:
        return result.package.replace("/", "-")
    elif result.server_type == ServerType.DOCKER_DESKTOP:
        return f"dd-{result.name.replace('docker-desktop-', '')}"
    else:
        return result.name


def _prompt_for_server_configuration(server_name: str, server_type: ServerType, package: Optional[str]) -> Optional[dict]:
    """Prompt user for server configuration if needed."""
    from rich.prompt import Prompt
    import os
    
    # Define servers that need configuration
    config_requirements = {
        # Filesystem servers
        'filesystem': {
            'description': 'Filesystem access requires specifying allowed directories',
            'prompts': [
                {
                    'key': 'directory',
                    'prompt': 'Enter directory path to allow access to',
                    'default': os.path.expanduser("~"),
                    'help': 'This directory will be accessible to the MCP server'
                }
            ]
        },
        # SQLite servers
        'sqlite': {
            'description': 'SQLite server requires a database file path',
            'prompts': [
                {
                    'key': 'db_path',
                    'prompt': 'Enter SQLite database file path',
                    'default': '/tmp/claude-mcp.db',
                    'help': 'Path to SQLite database file (will be created if it doesn\'t exist)'
                }
            ]
        },
        # PostgreSQL servers
        'postgres': {
            'description': 'PostgreSQL server requires database connection details',
            'prompts': [
                {
                    'key': 'connection_string',
                    'prompt': 'Enter PostgreSQL connection string',
                    'default': 'postgresql://localhost:5432/claude',
                    'help': 'Format: postgresql://user:password@host:port/database'
                }
            ]
        }
    }
    
    # Check if this server needs configuration
    server_key = None
    for key in config_requirements:
        if key in server_name.lower() or (package and key in package.lower()):
            server_key = key
            break
    
    if not server_key:
        return None
    
    config_req = config_requirements[server_key]
    console.print(f"\n[blue]ℹ[/blue] {config_req['description']}")
    
    config = {'args': []}
    for prompt_config in config_req['prompts']:
        console.print(f"[dim]{prompt_config['help']}[/dim]")
        
        try:
            value = Prompt.ask(
                prompt_config['prompt'],
                default=prompt_config['default']
            )
        except (EOFError, KeyboardInterrupt):
            # Use default value if prompting fails (non-interactive context)
            value = prompt_config['default']
            console.print(f"[dim]Using default: {value}[/dim]")
        
        if server_key == 'filesystem':
            # Expand user path
            value = os.path.expanduser(value)
            if server_type == ServerType.DOCKER_DESKTOP:
                config['directory'] = value
            else:
                config['args'].append(value)
                
        elif server_key == 'sqlite':
            # Create database file if it doesn't exist
            db_path = os.path.expanduser(value)
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            if not os.path.exists(db_path):
                # Create empty SQLite database
                import sqlite3
                with sqlite3.connect(db_path):
                    pass
                console.print(f"[green]✓[/green] Created database file: {db_path}")
            
            if server_type == ServerType.DOCKER_DESKTOP:
                config['db_path'] = db_path
            else:
                config['args'].extend(['--db-path', db_path])
                
        elif server_key == 'postgres':
            if server_type == ServerType.DOCKER_DESKTOP:
                config['connection_string'] = value
            else:
                config['args'].extend(['--connection-string', value])
    
    return config if config.get('args') or any(k != 'args' for k in config.keys()) else None


def _update_docker_mcp_config(server_name: str, config: dict):
    """Update Docker MCP configuration file with server-specific config."""
    import yaml
    from pathlib import Path
    
    config_file = Path.home() / ".docker" / "mcp" / "config.yaml"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing config or create new
    existing_config = {}
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                existing_config = yaml.safe_load(f) or {}
        except yaml.YAMLError:
            pass
    
    # Update with new server config
    server_config = {'env': {}}
    
    if 'directory' in config:
        server_config['args'] = [config['directory']]
    elif 'db_path' in config:
        server_config['args'] = [f"--db-path={config['db_path']}"]
    elif 'connection_string' in config:
        server_config['args'] = [f"--connection-string={config['connection_string']}"]
    
    existing_config[server_name] = server_config
    
    # Save updated config
    with open(config_file, 'w') as f:
        yaml.dump(existing_config, f, default_flow_style=False)


async def _tag_server_with_suite(server_name: str, category: str, priority: str, install_id: str):
    """Tag a server with suite information in the database."""
    import sqlite3
    import json
    from datetime import datetime
    from pathlib import Path
    
    # Get database path
    db_path = Path.home() / ".config" / "mcp-manager" / "mcp_manager.db"
    
    # Ensure migrations are run
    try:
        from mcp_manager.core.migrations.manager import MigrationManager
        migration_manager = MigrationManager(db_path)
        migration_manager.run_migrations()
    except Exception as e:
        logger.debug(f"Failed to run migrations: {e}")
        return
    
    try:
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.cursor()
            
            # Create or update suite
            suite_id = f"test-suite-{category}"
            suite_name = f"Test Suite - {category.title()}"
            suite_description = f"Automated test suite for {category} category MCP servers"
            
            cursor.execute("""
                INSERT OR REPLACE INTO mcp_suites (id, name, description, category, config, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                suite_id, suite_name, suite_description, category,
                json.dumps({"auto_generated": True, "test_suite": True}),
                datetime.now().isoformat(), datetime.now().isoformat()
            ))
            
            # Add server to suite membership
            priority_value = {"high": 90, "medium": 50, "low": 20}.get(priority, 50)
            cursor.execute("""
                INSERT OR REPLACE INTO suite_memberships 
                (suite_id, server_name, role, priority, config_overrides, added_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                suite_id, server_name, "member", priority_value,
                json.dumps({"category": category, "priority": priority}),
                datetime.now().isoformat()
            ))
            
            # Update server metadata
            cursor.execute("""
                INSERT OR REPLACE INTO server_metadata 
                (server_name, server_type, suites, tags, install_source, install_id, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                server_name, "unknown",  # We'd need to determine server type
                json.dumps([suite_id]),
                json.dumps([category, "test-suite", priority]),
                "test-suite", install_id,
                json.dumps({"category": category, "priority": priority, "suite": suite_id}),
                datetime.now().isoformat(), datetime.now().isoformat()
            ))
            
            conn.commit()
            logger.debug(f"Tagged server {server_name} with suite {suite_id}")
            
    except Exception as e:
        logger.debug(f"Failed to tag server {server_name}: {e}")

async def _show_server_details_after_install(manager, server_name: str):
    """Show server details after installation."""
    try:
        console.print(f"[blue]Fetching details for '{server_name}'...[/blue]")
        
        # Get server details with timeout handling
        server_details = await manager.get_server_details(server_name)
        
        if not server_details:
            console.print(f"[yellow]⚠[/yellow] Could not fetch detailed information for '{server_name}'")
            console.print(f"[dim]This may be due to connection timeouts or server unavailability[/dim]")
            console.print(f"[dim]The server is still installed and should work normally[/dim]")
            return
        
        from rich.panel import Panel
        from rich.syntax import Syntax
        
        # Create details display
        details_content = []
        
        # Basic server info
        details_content.append(f"[bold cyan]Server:[/bold cyan] {server_details['name']}")
        if server_details.get('description'):
            details_content.append(f"[bold cyan]Description:[/bold cyan] {server_details['description']}")
        details_content.append(f"[bold cyan]Type:[/bold cyan] {server_details.get('type', 'Unknown')}")
        details_content.append(f"[bold cyan]Status:[/bold cyan] {server_details.get('status', 'Unknown')}")
        
        # Tools information
        tools = server_details.get('tools', [])
        if tools:
            details_content.append(f"\n[bold cyan]Available Tools ({len(tools)}):[/bold cyan]")
            for tool in tools:
                tool_name = tool.get('name', 'Unknown')
                tool_desc = tool.get('description', 'No description available')
                details_content.append(f"  • [bold green]{tool_name}[/bold green]: {tool_desc}")
                
                # Show parameters if available
                params = tool.get('parameters', [])
                if params:
                    details_content.append("    [dim]Parameters:[/dim]")
                    for param in params:
                        param_name = param.get('name', 'unknown')
                        param_type = param.get('type', 'unknown')
                        param_required = " [red](required)[/red]" if param.get('required') else ""
                        param_desc = param.get('description', '')
                        details_content.append(f"      - [yellow]{param_name}[/yellow] ([cyan]{param_type}[/cyan]){param_required}: {param_desc}")
        else:
            # Enhanced display for cases where tool discovery failed
            source = server_details.get('source', 'unknown')
            if source == "docker_container_introspection_failed":
                details_content.append(f"\n[yellow]Tool discovery failed for Docker container[/yellow]")
                
                # Show fallback information
                fallback_info = server_details.get('fallback_info', {})
                docker_image = server_details.get('docker_image')
                
                if docker_image:
                    details_content.append(f"[dim]Docker Image: {docker_image}[/dim]")
                
                # Show likely tools
                likely_tools = fallback_info.get('likely_tools', [])
                if likely_tools:
                    details_content.append(f"\n[bold cyan]Likely Available Tools:[/bold cyan]")
                    for tool in likely_tools:
                        details_content.append(f"  • [bold green]{tool['name']}[/bold green]: {tool['description']}")
                
                # Show troubleshooting suggestions
                suggestions = fallback_info.get('suggestions', [])
                if suggestions:
                    details_content.append(f"\n[bold cyan]Troubleshooting:[/bold cyan]")
                    for suggestion in suggestions:
                        details_content.append(f"  • {suggestion}")
            else:
                details_content.append(f"\n[yellow]No tool information available yet[/yellow]")
        
        # Claude usage instructions
        details_content.append(f"\n[bold cyan]Usage in Claude:[/bold cyan]")
        details_content.append(f"This server is now active in Claude Code. You can use its tools directly in your conversations!")
        
        if tools:
            details_content.append(f"\n[bold cyan]Example Usage:[/bold cyan]")
            first_tool = tools[0]
            tool_name = first_tool.get('name', 'tool_name')
            details_content.append(f"Just ask Claude: \"Use the [green]{tool_name}[/green] tool to...\"")
        
        # Display in a panel
        content = "\n".join(details_content)
        panel = Panel(
            content,
            title=f"📋 Server Details: {server_name}",
            title_align="left",
            border_style="cyan",
            padding=(1, 2)
        )
        
        console.print("")  # Add spacing
        console.print(panel)
        
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to get server details: {e}")
        console.print(f"[dim]Server '{server_name}' is still installed and active[/dim]")


async def _show_discovery_for_next_install(discovery):
    """Show discovery results for the user to choose another server to install."""
    try:
        console.print("[bold cyan]🔍 Discovering available MCP servers...[/bold cyan]")
        
        # Get discovery results
        results = await discovery.discover_servers(limit=20)
        
        if not results:
            console.print("[yellow]No servers found[/yellow]")
            return
        
        from rich.table import Table
        
        # Create table for discovery results
        table = Table(
            title="Available MCP Servers",
            show_header=True,
            header_style="bold cyan",
            title_style="bold cyan",
            show_lines=True
        )
        
        table.add_column("Install ID", style="green", width=25)
        table.add_column("Type", style="blue", width=8)
        table.add_column("Description", style="white", width=40)
        table.add_column("Install Command", style="dim", width=35)
        
        # Add rows for each result
        for result in results:
            # Generate install ID using same logic as discover command
            install_id = _generate_install_id(result)
            
            # Create simple install command
            install_cmd = f"mcp-manager install-package {install_id}"
            
            table.add_row(
                install_id,
                result.server_type.value,
                result.description[:37] + "..." if result.description and len(result.description) > 40 else (result.description or ""),
                install_cmd[:32] + "..." if len(install_cmd) > 35 else install_cmd
            )
        
        console.print("")
        console.print(table)
        console.print("")
        console.print("[dim]💡 Copy and paste the install command for the server you want[/dim]")
        console.print("[dim]   Example: [cyan]mcp-manager install-package modelcontextprotocol-filesystem[/cyan][/dim]")
        
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to discover servers: {e}")



def handle_errors(func):
    """Decorator to handle common CLI errors."""
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except MCPManagerError as e:
            console.print(f"[red]Error:[/red] {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Operation cancelled by user[/yellow]")
            sys.exit(130)
        except Exception as e:
            console.print(f"[red]Unexpected error:[/red] {e}")
            if logger.isEnabledFor(10):  # DEBUG level
                console.print_exception()
            sys.exit(1)
    return wrapper


@click.group(name="mcp-manager", invoke_without_command=True)
@click.version_option(__version__)
@click.option(
    "--debug",
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
    type=click.Path(path_type=Path),
    help="Configuration directory"
)
@click.option(
    "--menu", "-m",
    is_flag=True,
    help="Launch interactive menu (default when no command given)"
)
@click.pass_context
def cli(ctx: click.Context, debug: bool, verbose: bool, config_dir: Optional[Path], menu: bool):
    """
    Enterprise-grade MCP server management tool.
    
    Manage MCP (Model Context Protocol) servers with professional CLI and TUI interfaces.
    
    When called without a command, launches an interactive menu interface.
    """
    # Ensure context object exists
    ctx.ensure_object(dict)
    
    # Setup logging
    config = get_config()
    
    if debug:
        config.logging.level = "DEBUG"
    elif verbose:
        config.logging.level = "INFO"
        
    setup_logging(
        enabled=config.logging.enabled,
        level=config.logging.level,
        console_level=config.logging.console_level,
        log_file=config.get_log_file(),
        format_type=config.logging.format_type,
        enable_rich=config.logging.enable_rich,
        suppress_http=config.logging.suppress_http,
        max_bytes=config.logging.max_bytes,
        backup_count=config.logging.backup_count,
    )
    
    # Override config directory if provided
    if config_dir:
        config.config_dir = str(config_dir)
        
    logger.debug("CLI initialized")
    
    # If no subcommand was provided, launch interactive menu
    if ctx.invoked_subcommand is None:
        launch_interactive_menu()


@cli.command("list")
@click.option(
    "--scope",
    type=click.Choice([s.value for s in ServerScope], case_sensitive=False),
    help="Filter by scope"
)
@click.option(
    "--format",
    "output_format", 
    type=click.Choice(["table", "json", "yaml"], case_sensitive=False),
    default="table",
    help="Output format"
)
@handle_errors
def list_cmd(scope: Optional[str], output_format: str):
    """List configured MCP servers."""
    manager = cli_context.get_manager()
    
    # Parse scope
    scope_filter = ServerScope(scope) if scope else None
    
    # Get servers (use fast method for basic listing)
    servers = manager.list_servers_fast()
    
    if output_format == "json":
        import json
        data = [server.model_dump() for server in servers]
        console.print(json.dumps(data, indent=2, default=str))
        return
    elif output_format == "yaml":
        import yaml
        data = [server.model_dump() for server in servers]
        console.print(yaml.dump(data, default_flow_style=False))
        return
        
    # Table format
    if not servers:
        console.print("[yellow]No servers configured[/yellow]")
        return
        
    table = Table(title="MCP Servers", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan")
    table.add_column("Scope", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Type", justify="center")
    table.add_column("Command", style="dim")
    
    for server in servers:
        status_style = "green" if server.enabled else "red"
        status_text = "enabled" if server.enabled else "disabled"
        
        scope_emoji = {
            ServerScope.LOCAL: "🔒",
            ServerScope.PROJECT: "🔄", 
            ServerScope.USER: "🌐",
        }
        
        table.add_row(
            server.name,
            f"{scope_emoji.get(server.scope, '')} {server.scope.value}",
            f"[{status_style}]{status_text}[/{status_style}]",
            server.server_type.value,
            server.command[:50] + "..." if len(server.command) > 50 else server.command,
        )
        
    console.print(table)


@cli.command()
@click.argument("name")
@click.argument("command", required=False)
@click.option(
    "--scope",
    type=click.Choice([s.value for s in ServerScope], case_sensitive=False),
    default=ServerScope.USER.value,
    help="Configuration scope"
)
@click.option(
    "--type",
    "server_type",
    type=click.Choice([t.value for t in ServerType], case_sensitive=False),
    default=ServerType.CUSTOM.value,
    help="Server type"
)
@click.option(
    "--description",
    help="Server description"
)
@click.option(
    "--env",
    multiple=True,
    help="Environment variables (KEY=VALUE)"
)
@click.option(
    "--arg",
    "args",
    multiple=True,
    help="Command arguments"
)
@handle_errors
def add(
    name: str,
    command: str, 
    scope: str,
    server_type: str,
    description: Optional[str],
    env: List[str],
    args: List[str],
):
    """Add a new MCP server."""
    manager = cli_context.get_manager()
    
    # Add server using simple manager
    async def add_server_async():
        try:
            if server_type:
                detected_server_type = server_type
            else:
                # Auto-detect server type based on command
                if command == 'npx':
                    detected_server_type = ServerType.NPM
                elif command.endswith('/docker') or command == 'docker':
                    detected_server_type = ServerType.DOCKER
                else:
                    detected_server_type = ServerType.CUSTOM
            
            # Check for similar servers first (don't treat as error)
            similar_servers = await manager.check_for_similar_servers(
                name=name,
                server_type=detected_server_type,
                command=command,
                args=args
            )
            
            # If similar servers found, warn user and ask for confirmation
            if similar_servers:
                console.print(f"[yellow]⚠ Warning:[/yellow] Found {len(similar_servers)} similar server(s) that might provide the same functionality:")
                
                for similar_info in similar_servers:
                    similar_server = similar_info["server"]
                    score = similar_info["similarity_score"]
                    reasons = similar_info["reasons"]
                    recommendation = similar_info["recommendation"]
                    server_type_str = similar_server.server_type.value if hasattr(similar_server.server_type, 'value') else str(similar_server.server_type)
                    
                    console.print(f"  • [cyan]{similar_server.name}[/cyan] ({server_type_str}) - Similarity: {score}%")
                    console.print(f"    [dim]Reasons: {', '.join(reasons)}[/dim]")
                    console.print(f"    [dim]Recommendation: {recommendation}[/dim]")
                
                console.print(f"\n[yellow]Installing multiple servers for the same functionality may cause conflicts.[/yellow]")
                console.print(f"[yellow]Do you accept the risks and want to continue?[/yellow]")
                
                from rich.prompt import Confirm
                try:
                    if not Confirm.ask("Continue with installation?"):
                        console.print("[dim]Installation cancelled by user[/dim]")
                        return
                except (EOFError, KeyboardInterrupt):
                    console.print("[dim]Installation cancelled (non-interactive terminal)[/dim]")
                    return
            
            # Proceed with installation (no duplicate checking since we handled it above)
            server = await manager.add_server(
                name=name,
                server_type=detected_server_type,
                command=command,
                args=args
            )
            console.print(f"✅ Successfully added server: {name}")
                
        except Exception as e:
            console.print(f"❌ Failed to add server {name}: {e}")
    
    asyncio.run(add_server_async())


@cli.command()
@click.argument("name")
@click.option(
    "--scope",
    type=click.Choice([s.value for s in ServerScope], case_sensitive=False),
    help="Configuration scope"
)
@click.option(
    "--force", "-f",
    is_flag=True,
    help="Force removal without confirmation"
)
@handle_errors
def remove(name: str, scope: Optional[str], force: bool):
    """Remove an MCP server."""
    manager = cli_context.get_manager()
    
    # Remove server using simple manager
    try:
        manager.remove_server(name)
        console.print(f"✅ Successfully removed server: {name}")
    except Exception as e:
        console.print(f"❌ Failed to remove server {name}: {e}")


@cli.command()
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
@handle_errors
def nuke(force: bool):
    """Remove ALL MCP servers (nuclear option)."""
    manager = cli_context.get_manager()
    
    # Get all servers first
    try:
        servers = manager.list_servers()
        if not servers:
            console.print("🚫 No MCP servers found to remove")
            return
            
        console.print(f"🚨 [red bold]WARNING: This will remove ALL {len(servers)} MCP servers![/red bold]")
        console.print("\nServers to be removed:")
        for server in servers:
            console.print(f"  • [cyan]{server.name}[/cyan] ({server.server_type.value})")
        
        # Confirmation prompt unless --force is used
        if not force:
            from rich.prompt import Confirm
            try:
                if not Confirm.ask("\n[red]Are you absolutely sure you want to remove ALL servers?[/red]", default=False):
                    console.print("[dim]Nuclear option cancelled[/dim]")
                    return
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Nuclear option cancelled[/dim]")
                return
        
        # Remove all servers
        console.print(f"\n💥 [red]Nuking all {len(servers)} MCP servers...[/red]")
        removed_count = 0
        failed_count = 0
        
        for server in servers:
            try:
                manager.remove_server(server.name)
                console.print(f"  ✅ Removed: [cyan]{server.name}[/cyan]")
                removed_count += 1
            except Exception as e:
                console.print(f"  ❌ Failed to remove [cyan]{server.name}[/cyan]: {e}")
                failed_count += 1
        
        # Summary
        console.print(f"\n🎯 [green]Nuclear option complete![/green]")
        console.print(f"  ✅ Removed: {removed_count} servers")
        if failed_count > 0:
            console.print(f"  ❌ Failed: {failed_count} servers")
        console.print(f"  🧹 Clean slate ready for fresh installations")
        
        if removed_count > 0:
            console.print(f"\n💡 [dim]To start fresh, use:[/dim]")
            console.print(f"   [cyan]mcp-manager discover[/cyan]")
            console.print(f"   [cyan]mcp-manager install-package <install-id>[/cyan]")
            
    except Exception as e:
        console.print(f"❌ Failed to nuke servers: {e}")


@cli.command("install-test-suite")
@click.option("--category", "-c", multiple=True, help="Specific categories to install (filesystem, database, web, ai, etc.)")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompts")
@click.option("--dry-run", is_flag=True, help="Show what would be installed without installing")
@handle_errors
def install_test_suite(category: List[str], force: bool, dry_run: bool):
    """Install a comprehensive test suite of MCP servers from different categories.
    
    This installs a curated set of MCP servers covering major categories:
    - Filesystem: File operations and management
    - Database: SQLite and PostgreSQL access
    - Web: HTTP requests and web scraping
    - AI: LLM and AI service integrations
    - Development: Git, Docker, and development tools
    - Cloud: AWS, Google Cloud integrations
    - Productivity: Calendar, email, note-taking
    
    Perfect for testing MCP functionality and as a foundation for task-specific configs like web development workflows.
    """
    # Define test suite categories with curated servers
    test_suite_categories = {
        "filesystem": {
            "description": "File operations and management",
            "servers": [
                {"id": "dd-filesystem", "name": "docker-desktop-filesystem", "priority": "high"},
                {"id": "modelcontextprotocol-filesystem", "name": "official-filesystem", "priority": "medium"},
            ]
        },
        "database": {
            "description": "Database access and management", 
            "servers": [
                {"id": "modelcontextprotocol-sqlite", "name": "official-sqlite", "priority": "high"},
                {"id": "mcp-postgres", "name": "postgres-server", "priority": "medium"},
            ]
        },
        "web": {
            "description": "HTTP requests and web operations",
            "servers": [
                {"id": "mcp-fetch", "name": "official-fetch", "priority": "high"},
                {"id": "dd-github", "name": "github-integration", "priority": "medium"},
            ]
        },
        "development": {
            "description": "Development tools and workflows",
            "servers": [
                {"id": "modelcontextprotocol-git", "name": "git-operations", "priority": "high"},
                {"id": "dd-github", "name": "github-integration", "priority": "medium"},
            ]
        },
        "cloud": {
            "description": "Cloud service integrations",
            "servers": [
                {"id": "dd-aws-diagram", "name": "aws-diagrams", "priority": "medium"},
                {"id": "mcp-aws-s3", "name": "aws-s3-access", "priority": "low"},
            ]
        },
        "ai": {
            "description": "AI and LLM integrations", 
            "servers": [
                {"id": "modelcontextprotocol-memory", "name": "memory-storage", "priority": "medium"},
                {"id": "mcp-openai", "name": "openai-integration", "priority": "low"},
            ]
        },
        "productivity": {
            "description": "Productivity and workflow tools",
            "servers": [
                {"id": "modelcontextprotocol-slack", "name": "slack-integration", "priority": "low"},
                {"id": "mcp-calendar", "name": "calendar-access", "priority": "low"},
            ]
        }
    }
    
    # Filter categories if specified
    if category:
        categories_to_install = {k: v for k, v in test_suite_categories.items() if k in category}
        if not categories_to_install:
            console.print(f"[red]❌ No valid categories found. Available: {', '.join(test_suite_categories.keys())}[/red]")
            return
    else:
        categories_to_install = test_suite_categories
    
    # Calculate total servers
    total_servers = sum(len(cat["servers"]) for cat in categories_to_install.values())
    
    console.print("🧪 [bold blue]MCP Test Suite Installation[/bold blue]")
    console.print(f"📦 Installing {total_servers} servers across {len(categories_to_install)} categories")
    console.print()
    
    # Show what will be installed
    for cat_name, cat_info in categories_to_install.items():
        console.print(f"📁 [cyan bold]{cat_name.title()}[/cyan bold]: {cat_info['description']}")
        for server in cat_info["servers"]:
            priority_color = {"high": "green", "medium": "yellow", "low": "dim"}.get(server["priority"], "white")
            console.print(f"   • [{priority_color}]{server['name']}[/{priority_color}] ({server['id']}) - {server['priority']} priority")
        console.print()
    
    if dry_run:
        console.print("[dim]🔍 Dry run complete - no servers were installed[/dim]")
        return
    
    # Confirmation prompt unless --force is used
    if not force:
        from rich.prompt import Confirm
        try:
            if not Confirm.ask(f"\n[cyan]Install {total_servers} MCP servers for comprehensive testing?[/cyan]", default=True):
                console.print("[dim]Test suite installation cancelled[/dim]")
                return
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Test suite installation cancelled[/dim]")
            return
    
    # Install servers
    console.print(f"\n🚀 [green]Installing MCP test suite...[/green]")
    
    manager = cli_context.get_manager()
    discovery = cli_context.get_discovery()
    
    installed_count = 0
    failed_count = 0
    skipped_count = 0
    
    async def install_test_suite():
        nonlocal installed_count, failed_count, skipped_count
        
        for cat_name, cat_info in categories_to_install.items():
            console.print(f"\n📁 [cyan bold]Installing {cat_name.title()} servers...[/cyan bold]")
            
            for server_info in cat_info["servers"]:
                install_id = server_info["id"]
                server_name = server_info["name"]
                
                try:
                    console.print(f"   🔄 Installing [cyan]{server_name}[/cyan] ({install_id})...")
                    
                    # Check if server already exists
                    existing_servers = manager.list_servers()
                    if any(s.name == server_name for s in existing_servers):
                        console.print(f"   ⏭️  [yellow]Skipped[/yellow]: {server_name} already exists")
                        skipped_count += 1
                        continue
                    
                    # Find the server in discovery results
                    results = await discovery.discover_servers(limit=200)
                    target_result = None
                    
                    for result in results:
                        if _generate_install_id(result) == install_id:
                            target_result = result
                            break
                    
                    if not target_result:
                        console.print(f"   ❌ [red]Failed[/red]: {server_name} not found in discovery")
                        failed_count += 1
                        continue
                    
                    # Install with minimal config (use defaults)
                    if target_result.server_type == ServerType.DOCKER_DESKTOP:
                        # Enable in Docker Desktop first
                        import subprocess
                        enable_result = subprocess.run(
                            ["docker", "mcp", "server", "enable", server_name.replace("docker-desktop-", "").replace("dd-", "")],
                            capture_output=True, text=True
                        )
                        
                        if enable_result.returncode == 0:
                            # Add proper runtime command
                            server = await manager.add_server(
                                name=server_name,
                                server_type=target_result.server_type,
                                command="docker",
                                description=target_result.description,
                                args=["run", "-i", "--rm", "-v", "/Users/jestes:/Users/jestes", "mcp/filesystem", "/Users/jestes"]
                            )
                        else:
                            raise Exception(f"Failed to enable in Docker Desktop: {enable_result.stderr}")
                    else:
                        # Regular installation
                        server = await manager.add_server(
                            name=server_name,
                            server_type=target_result.server_type,
                            command=target_result.install_command,
                            description=target_result.description,
                            args=target_result.install_args
                        )
                    
                    console.print(f"   ✅ [green]Installed[/green]: {server_name}")
                    installed_count += 1
                    
                    # Tag server with suite information
                    try:
                        await _tag_server_with_suite(server_name, cat_name, server_info["priority"], install_id)
                    except Exception as e:
                        logger.debug(f"Failed to tag server {server_name} with suite info: {e}")
                    
                except Exception as e:
                    console.print(f"   ❌ [red]Failed[/red]: {server_name} - {e}")
                    failed_count += 1
    
    # Run installation
    import asyncio
    asyncio.run(install_test_suite())
    
    # Summary
    console.print(f"\n🎯 [green bold]Test Suite Installation Complete![/green bold]")
    console.print(f"   ✅ Installed: {installed_count} servers")
    console.print(f"   ⏭️  Skipped: {skipped_count} servers (already existed)")
    console.print(f"   ❌ Failed: {failed_count} servers")
    
    if installed_count > 0:
        console.print(f"\n💡 [dim]Next steps:[/dim]")
        console.print(f"   • [cyan]claude mcp list[/cyan] - View all installed servers")
        console.print(f"   • [cyan]mcp-manager list[/cyan] - Detailed server information")
        console.print(f"   • Create task-specific configs for web development, data analysis, etc.")
        console.print(f"\n🔧 [dim]Future: Use these servers in task configs like 'web-dev-suite' or 'data-analysis-stack'[/dim]")


@cli.command()
@click.argument("name")
@handle_errors
def enable(name: str):
    """Enable an MCP server."""
    manager = cli_context.get_manager()
    
    # Enable server using simple manager
    try:
        manager.enable_server(name)
        console.print(f"✅ Successfully enabled server: {name}")
    except Exception as e:
        console.print(f"❌ Failed to enable server {name}: {e}")


@cli.command()
@click.argument("name")
@handle_errors  
def disable(name: str):
    """Disable an MCP server."""
    manager = cli_context.get_manager()
    
    # Disable server using simple manager
    try:
        manager.disable_server(name)
        console.print(f"✅ Successfully disabled server: {name}")
    except Exception as e:
        console.print(f"❌ Failed to disable server {name}: {e}")


@cli.command()
@click.option(
    "--query", "-q",
    help="Search query (supports wildcards like 'aws*' and regex like 'regex:^file.*')"
)
@click.option(
    "--type",
    "server_type",
    type=click.Choice([t.value for t in ServerType], case_sensitive=False),
    help="Server type filter"
)
@click.option(
    "--limit", "-l",
    type=int,
    default=20,
    help="Maximum results"
)
@click.option(
    "--update-catalog", 
    is_flag=True,
    help="Update Docker MCP catalog before discovery"
)
@handle_errors
def discover(query: Optional[str], server_type: Optional[str], limit: int, update_catalog: bool):
    """
    Discover available MCP servers with pattern matching support.
    
    Query supports:
    - Wildcards: 'aws*' matches aws-s3, aws-dynamodb, etc.
    - Regex: 'regex:^file.*server$' for advanced patterns
    - Simple text: 'filesystem' for substring matching
    """
    discovery = cli_context.get_discovery()
    
    type_filter = ServerType(server_type) if server_type else None
    
    # Run async discovery
    async def run_discovery():
        # Update catalog if requested
        if update_catalog:
            console.print("[blue]Updating Docker MCP catalog...[/blue]")
            success = await discovery.update_docker_catalog()
            if success:
                console.print("[green]✅ Docker MCP catalog updated[/green]")
            else:
                console.print("[yellow]⚠️ Failed to update Docker MCP catalog[/yellow]")
        
        return await discovery.discover_servers(
            query=query,
            server_type=type_filter,
            limit=limit
        )
        
    results = asyncio.run(run_discovery())
    
    if not results:
        console.print("[yellow]No servers found[/yellow]")
        return
        
    table = Table(title="Available MCP Servers", show_header=True, header_style="bold blue")
    table.add_column("Install ID", style="cyan", width=20)
    table.add_column("Type", justify="center", width=15)
    table.add_column("Description", style="dim", width=30)
    table.add_column("Package", style="green", width=25)
    table.add_column("Install Command", style="yellow", width=30)
    
    for result in results:
        # Create unique install ID - use same logic as in install-package command
        install_id = _generate_install_id(result)
        
        # Create simple install command
        install_cmd = f"mcp-manager install-package {install_id}"
        
        table.add_row(
            install_id,
            result.server_type.value,
            result.description[:30] + "..." if result.description and len(result.description) > 30 else (result.description or ""),
            result.package or "",
            install_cmd
        )
        
    console.print(table)
    
    if results:
        console.print("\n[dim]💡 To install a server, copy the command from the 'Install Command' column[/dim]")
        console.print("[dim]   Example: [cyan]mcp-manager install-package modelcontextprotocol-filesystem[/cyan][/dim]")


@cli.command("install-package")
@click.argument("install_id")
@handle_errors
def install_package(install_id: str):
    """Install a server using its unique install ID from discovery."""
    discovery = cli_context.get_discovery()
    manager = cli_context.get_manager()
    
    # Resolve install ID back to package info
    async def find_and_install():
        # Try to extract search terms from install_id to improve discovery
        search_query = None
        if install_id.startswith("dd-"):
            # Docker Desktop server - extract server name
            search_query = install_id[3:]  # Remove 'dd-' prefix
        elif "-" in install_id:
            # Extract likely server name from install_id
            search_query = install_id.split("-")[-1]  # Take last part
            
        # Search with higher limits to ensure we find all servers
        # Try with query first, then without query as fallback
        target_result = None
        
        for query_attempt in [search_query, None]:
            results = await discovery.discover_servers(
                query=query_attempt, 
                limit=200  # Higher limit to ensure we find all servers
            )
            
            for result in results:
                # Generate install_id using same logic as discover command
                result_id = _generate_install_id(result)
                
                if result_id == install_id:
                    target_result = result
                    break
            
            if target_result:
                break
        
        if not target_result:
            console.print(f"[red]✗[/red] Install ID '{install_id}' not found")
            console.print("[yellow]💡[/yellow] Run [cyan]mcp-manager discover[/cyan] to see available install IDs")
            return
        
        # Create unique server name to avoid conflicts
        if target_result.server_type == ServerType.NPM:
            server_name = install_id.replace("modelcontextprotocol-", "official-")
        elif target_result.server_type == ServerType.DOCKER:
            server_name = install_id.replace("-", "_")
        elif target_result.server_type == ServerType.DOCKER_DESKTOP:
            # For Docker Desktop, use the actual server name (remove dd- prefix)
            server_name = install_id.replace("dd-", "")
        else:
            server_name = install_id
        
        console.print(f"[blue]Installing[/blue] {target_result.package} as [cyan]{server_name}[/cyan]")
        
        # Check if server already exists
        existing_servers = manager.list_servers()
        if any(s.name == server_name for s in existing_servers):
            console.print(f"[yellow]⚠[/yellow] Server '{server_name}' already exists")
            from rich.prompt import Confirm
            if not Confirm.ask("Replace existing server?"):
                console.print("[dim]Installation cancelled[/dim]")
                return
        
        # Check for similar servers that might provide the same functionality
        try:
            existing_servers = manager.list_servers()
            similar_servers = discovery.detect_similar_servers(target_result, existing_servers)
            
            if similar_servers:
                console.print(f"[yellow]⚠[/yellow] Found {len(similar_servers)} similar server(s) that might provide the same functionality:")
                for similar_info in similar_servers:
                    similar_server = similar_info["server"]
                    score = similar_info["similarity_score"]
                    reasons = similar_info["reasons"]
                    recommendation = similar_info["recommendation"]
                    
                    console.print(f"  • [cyan]{similar_server.name}[/cyan] ({similar_server.server_type.value}) - Similarity: {score}%")
                    console.print(f"    [dim]Reasons: {', '.join(reasons)}[/dim]")
                    console.print(f"    [dim]Recommendation: {recommendation}[/dim]")
                
                console.print(f"\n[yellow]Installing multiple servers for the same functionality may cause conflicts.[/yellow]")
                from rich.prompt import Confirm
                if not Confirm.ask("Continue anyway?"):
                    console.print("[dim]Installation cancelled[/dim]")
                    return
        except Exception as e:
            logger.debug(f"Failed to check for similar servers: {e}")
            # Continue with installation even if similarity check fails
        
        # Check if server needs additional configuration
        install_args = target_result.install_args or []
        additional_config = _prompt_for_server_configuration(
            server_name=server_name,
            server_type=target_result.server_type,
            package=target_result.package
        )
        
        if additional_config:
            # For Docker Desktop servers, update the config file
            if target_result.server_type == ServerType.DOCKER_DESKTOP:
                _update_docker_mcp_config(server_name, additional_config)
            else:
                # For other servers, add to install args
                install_args.extend(additional_config.get('args', []))
        
        # Handle different server types with proper commands
        try:
            if target_result.server_type == ServerType.DOCKER_DESKTOP:
                # For Docker Desktop servers, first enable in Docker Desktop, then set up docker-gateway
                console.print(f"[blue]Enabling[/blue] {server_name} in Docker Desktop...")
                
                # Enable server in Docker Desktop using subprocess
                import subprocess
                enable_result = subprocess.run(
                    ["docker", "mcp", "server", "enable", server_name],
                    capture_output=True,
                    text=True
                )
                
                if enable_result.returncode != 0:
                    console.print(f"[red]✗[/red] Failed to enable server in Docker Desktop: {enable_result.stderr}")
                    return
                
                # Now set up docker-gateway (or ensure it exists)
                console.print("[blue]Setting up[/blue] docker-gateway integration...")
                
                # Check if docker-gateway already exists
                existing_gateway = None
                for server in manager.list_servers():
                    if server.name == "docker-gateway":
                        existing_gateway = server
                        break
                
                if existing_gateway:
                    console.print("[yellow]docker-gateway already exists - refreshing...[/yellow]")
                    # Remove and re-add to refresh enabled servers list
                    manager.remove_server("docker-gateway")
                
                # Now add the proper runtime command for the specific server
                if server_name == "filesystem":
                    # Use the proper Docker Desktop filesystem command with user's allowed directory
                    directory = additional_config.get('directory', '/Users/jestes')
                    server = await manager.add_server(
                        name=server_name,
                        server_type=ServerType.DOCKER_DESKTOP,
                        command="docker",
                        description=f"Local filesystem access with allowed directory: {directory}",
                        args=["run", "-i", "--rm", "-v", f"{directory}:{directory}", "mcp/filesystem", directory]
                    )
                else:
                    # For other Docker Desktop servers, use generic docker-gateway approach
                    server = await manager.add_server(
                        name="docker-gateway",
                        server_type=ServerType.DOCKER_DESKTOP,
                        command="claude",
                        description="Docker Desktop MCP Gateway - provides access to enabled DD servers",
                        args=["mcp", "add-from-claude-desktop", "docker-gateway"]
                    )
                
                console.print(f"[green]✓[/green] Enabled {server_name} and configured docker-gateway")
                
            else:
                # For NPM and Docker servers, use the discovery command directly
                server = await manager.add_server(
                    name=server_name,
                    server_type=target_result.server_type,
                    command=target_result.install_command,
                    description=target_result.description,
                    args=install_args
                )
            console.print(f"[green]✓[/green] Installed server: {server.name}")
            console.print("[dim]Server is now active in Claude Code![/dim]")
            
            # Ask if user wants to view server details (with error handling for non-interactive contexts)
            try:
                from rich.prompt import Confirm
                if Confirm.ask(f"\n[cyan]View details for '{server.name}'?[/cyan]", default=True):
                    # Show server details
                    await _show_server_details_after_install(manager, server.name)
                    
                    # Wait for user to press Enter
                    console.print("\n[dim]Press Enter to continue...[/dim]", end="")
                    input()
                
                # Ask if user wants to search for another server
                if Confirm.ask(f"\n[cyan]Search for another server to install?[/cyan]", default=False):
                    console.print("")  # Add spacing
                    # Show discovery results
                    await _show_discovery_for_next_install(discovery)
            except (EOFError, KeyboardInterrupt):
                # Skip interactive prompts in non-interactive contexts
                console.print("[dim]Installation completed (non-interactive mode)[/dim]")
            
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to install: {e}")
    
    asyncio.run(find_and_install())


@cli.command()
@click.argument("name")
@handle_errors
def install(name: str):
    """Install a server from discovery results."""
    discovery = cli_context.get_discovery()
    manager = cli_context.get_manager()
    
    # Search for the server
    async def find_and_install():
        results = await discovery.discover_servers(query=name, limit=10)
        
        # Find exact match or best match
        exact_match = next((r for r in results if r.name == name), None)
        if not exact_match:
            # Try partial match
            partial_matches = [r for r in results if name.lower() in r.name.lower()]
            if not partial_matches:
                console.print(f"[red]✗[/red] Server '{name}' not found in discovery")
                console.print("[yellow]💡[/yellow] Try: [cyan]mcp-manager discover --query {name}[/cyan]")
                return
            exact_match = partial_matches[0]
            console.print(f"[yellow]ℹ[/yellow] Using closest match: {exact_match.name}")
        
        # Check for similar servers first (don't treat as error)
        similar_servers = await manager.check_for_similar_servers(
            name=exact_match.name,
            server_type=exact_match.server_type,
            command=exact_match.install_command,
            args=[]
        )
        
        # If similar servers found, warn user and ask for confirmation
        if similar_servers:
            console.print(f"[yellow]⚠ Warning:[/yellow] Found {len(similar_servers)} similar server(s) that might provide the same functionality:")
            
            for similar_info in similar_servers:
                similar_server = similar_info["server"]
                score = similar_info["similarity_score"]
                reasons = similar_info["reasons"]
                recommendation = similar_info["recommendation"]
                server_type_str = similar_server.server_type.value if hasattr(similar_server.server_type, 'value') else str(similar_server.server_type)
                
                console.print(f"  • [cyan]{similar_server.name}[/cyan] ({server_type_str}) - Similarity: {score}%")
                console.print(f"    [dim]Reasons: {', '.join(reasons)}[/dim]")
                console.print(f"    [dim]Recommendation: {recommendation}[/dim]")
            
            console.print(f"\n[yellow]Installing multiple servers for the same functionality may cause conflicts.[/yellow]")
            console.print(f"[yellow]Do you accept the risks and want to continue?[/yellow]")
            
            from rich.prompt import Confirm
            try:
                if not Confirm.ask("Continue with installation?"):
                    console.print("[dim]Installation cancelled by user[/dim]")
                    return
            except (EOFError, KeyboardInterrupt):
                console.print("[dim]Installation cancelled (non-interactive terminal)[/dim]")
                return
        
        # Install the server
        server = await manager.add_server(
            name=exact_match.name,
            server_type=exact_match.server_type,
            command=exact_match.install_command,
            description=exact_match.description
        )
        
        console.print(f"[green]✓[/green] Installed server: {server.name}")
        console.print(f"[dim]Command: {exact_match.install_command}[/dim]")
        console.print("\n[green]✓[/green] Server is now active in Claude Code!")
    
    asyncio.run(find_and_install())


@cli.command()
@handle_errors
def sync():
    """No longer needed - MCP Manager works directly with Claude's internal state."""
    console.print("[yellow]ℹ[/yellow] Sync is no longer needed!")
    console.print("[dim]MCP Manager now works directly with Claude's internal state.[/dim]")
    console.print("[dim]All changes are immediately reflected in Claude Code.[/dim]")


@cli.command("check-sync")
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed sync status information"
)
@handle_errors
def check_sync(verbose: bool):
    """Check synchronization status between mcp-manager and Claude."""
    manager = cli_context.get_manager()
    
    console.print("[blue]🔄 Checking synchronization status...[/blue]")
    
    try:
        sync_result = asyncio.run(manager.check_sync_status())
    except Exception as e:
        console.print(f"[red]✗ Failed to check sync status: {e}[/red]")
        sys.exit(1)
    
    # Overall status
    if sync_result.in_sync:
        console.print("[green]✅ MCP Manager and Claude are in sync![/green]")
    else:
        console.print("[red]❌ MCP Manager and Claude are out of sync[/red]")
    
    console.print()
    
    # Show issues
    if sync_result.issues:
        console.print("[bold red]Issues Found:[/bold red]")
        for issue in sync_result.issues:
            console.print(f"  [red]✗[/red] {issue}")
        console.print()
    
    # Show warnings
    if sync_result.warnings:
        console.print("[bold yellow]Warnings:[/bold yellow]")
        for warning in sync_result.warnings:
            console.print(f"  [yellow]⚠[/yellow] {warning}")
        console.print()
    
    # Docker gateway test results
    if sync_result.docker_gateway_test:
        console.print("[bold]Docker Gateway Test:[/bold]")
        test = sync_result.docker_gateway_test
        
        status = test.get("status", "unknown")
        if status == "success":
            console.print("  [green]✅ PASSED[/green]")
        elif status == "warning":
            console.print("  [yellow]⚠️ WARNING[/yellow]")
        else:
            console.print("  [red]❌ FAILED[/red]")
        
        # Show error if any
        if test.get("error"):
            console.print(f"  [red]Error:[/red] {test['error']}")
        
        # Show working servers
        working_servers = test.get("working_servers", [])
        failed_servers = test.get("failed_servers", [])
        total_tools = test.get("total_tools", 0)
        
        if working_servers:
            console.print("  [green]Working servers:[/green]")
            for server in working_servers:
                name = server.get("name", "Unknown")
                tools = server.get("tools", 0)
                console.print(f"    • {name}: {tools} tools")
        
        if failed_servers:
            console.print("  [red]Failed servers:[/red]")
            for server in failed_servers:
                name = server.get("name", "Unknown")
                error = server.get("error", "Unknown error")
                console.print(f"    • {name}: {error}")
        
        if total_tools > 0:
            console.print(f"  [cyan]Total tools available:[/cyan] {total_tools}")
        
        if verbose and test.get("command"):
            console.print(f"  [dim]Command tested:[/dim] {test['command']}")
            if test.get("raw_output"):
                console.print(f"  [dim]Raw output (first 500 chars):[/dim] {test['raw_output'][:500]}")
            if test.get("debug_lines_found"):
                console.print(f"  [dim]Server status lines found:[/dim] {test['debug_lines_found']}")
        
        console.print()
    
    # Show detailed information if verbose
    if verbose:
        console.print("[bold]Detailed Information:[/bold]")
        
        if sync_result.claude_available:
            console.print("  [green]✅ Claude CLI available[/green]")
        else:
            console.print("  [red]❌ Claude CLI not available[/red]")
        
        console.print(f"  [cyan]MCP Manager servers:[/cyan] {len(sync_result.manager_servers)}")
        for server in sync_result.manager_servers:
            console.print(f"    • {server}")
        
        console.print(f"  [cyan]Claude servers:[/cyan] {len(sync_result.claude_servers)}")
        for server in sync_result.claude_servers:
            console.print(f"    • {server}")
        
        if sync_result.missing_in_claude:
            console.print(f"  [yellow]Missing in Claude:[/yellow] {', '.join(sync_result.missing_in_claude)}")
        
        if sync_result.missing_in_manager:
            console.print(f"  [blue]Missing in Manager:[/blue] {', '.join(sync_result.missing_in_manager)}")
    
    # Exit with error code if not in sync
    if not sync_result.in_sync:
        sys.exit(1)


@cli.command(name="system-info")
@handle_errors
def system_info():
    """Show system information and dependencies."""
    manager = cli_context.get_manager()
    
    info = manager.get_system_info()
    
    table = Table(title="System Information", show_header=True, header_style="bold cyan")
    table.add_column("Component", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Version", style="dim")
    
    # System info
    table.add_row("Python", "[green]✓[/green]", info.python_version)
    table.add_row("Platform", "[green]✓[/green]", info.platform)
    
    # Dependencies
    deps = [
        ("Claude CLI", info.claude_cli_available, info.claude_cli_version),
        ("NPM", info.npm_available, info.npm_version),
        ("Docker", info.docker_available, info.docker_version),
        ("Git", info.git_available, info.git_version),
    ]
    
    for name, available, version in deps:
        status = "[green]✓[/green]" if available else "[red]✗[/red]"
        table.add_row(name, status, version or "not available")
        
    console.print(table)
    
    # Paths
    console.print(f"\n[bold]Configuration:[/bold]")
    console.print(f"Config dir: {info.config_dir}")
    if info.log_file:
        console.print(f"Log file: {info.log_file}")


@cli.command()
@handle_errors 
def tui():
    """Launch the Rich-based terminal user interface."""
    try:
        from mcp_manager.tui.main import main as tui_main
        tui_main()
    except ImportError:
        console.print("[red]TUI dependencies not available[/red]")
        console.print("Install with: pip install mcp-manager[tui]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]TUI Error: {e}[/red]")
        sys.exit(1)


@cli.command("tui-simple")
@handle_errors
def tui_simple():
    """Launch the simple Rich-based terminal user interface."""
    try:
        from mcp_manager.tui.simple_tui import main as simple_main
        import asyncio
        asyncio.run(simple_main())
    except Exception as e:
        console.print(f"[red]Simple TUI Error: {e}[/red]")
        sys.exit(1)

@cli.command("tui-textual")
@handle_errors
def tui_textual():
    """Launch the Textual-based terminal user interface (same as 'tui')."""
    try:
        from mcp_manager.tui.main import main as tui_main
        tui_main()
    except ImportError:
        console.print("[red]Textual TUI dependencies not available[/red]")
        console.print("Install with: pip install mcp-manager[tui]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Textual TUI Error: {e}[/red]")
        sys.exit(1)



@cli.command()
@click.option(
    "--dry-run", 
    is_flag=True, 
    help="Show what would be cleaned up without making changes"
)
@click.option(
    "--no-backup", 
    is_flag=True, 
    help="Skip creating backup (not recommended)"
)
@handle_errors
def cleanup(dry_run: bool, no_backup: bool):
    """Clean up problematic MCP server configurations.
    
    This command removes old or broken MCP server configurations that can
    cause connection errors, such as:
    - Old Docker commands with incorrect image names
    - Servers with invalid command formats
    - Configurations causing ENOENT errors
    """
    asyncio.run(_cleanup_impl(dry_run, no_backup))


async def _cleanup_impl(dry_run: bool, no_backup: bool):
    """Implementation of cleanup command."""
    import json
    import shutil
    from datetime import datetime
    from pathlib import Path
    
    console.print("[bold blue]🧹 MCP Configuration Cleanup[/bold blue]")
    
    # Check Claude configuration file
    claude_config = Path.home() / ".claude.json"
    if not claude_config.exists():
        console.print("[yellow]No Claude configuration found[/yellow]")
        return
    
    # Create backup unless disabled
    backup_path = None
    if not no_backup and not dry_run:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = claude_config.with_suffix(f".backup_{timestamp}")
        shutil.copy2(claude_config, backup_path)
        console.print(f"✅ Created backup: {backup_path}")
    
    # Load and analyze configuration
    try:
        with open(claude_config) as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        console.print(f"[red]Error reading Claude configuration: {e}[/red]")
        return
    
    # Find problematic configurations
    problems_found = []
    projects_to_clean = {}
    
    if "projectConfigs" in config:
        for project_path, project_config in config["projectConfigs"].items():
            if "mcpServers" in project_config and project_config["mcpServers"]:
                servers_to_remove = []
                
                for server_name, server_config in project_config["mcpServers"].items():
                    # Check for problematic Docker commands
                    command = server_config.get("command", "")
                    
                    # Pattern 1: Old incorrect Docker MCP commands
                    if command.startswith("docker run -i --rm --pull always mcp/"):
                        problems_found.append(f"❌ {project_path}:{server_name} - Invalid Docker command")
                        servers_to_remove.append(server_name)
                    
                    # Pattern 2: Commands that cause ENOENT
                    elif "mcp/" in command and "docker run" in command:
                        problems_found.append(f"⚠️  {project_path}:{server_name} - Likely ENOENT error")
                        servers_to_remove.append(server_name)
                
                if servers_to_remove:
                    projects_to_clean[project_path] = servers_to_remove
    
    # Report findings
    if not problems_found:
        console.print("[green]✅ No problematic MCP configurations found[/green]")
        return
    
    console.print(f"\n[yellow]Found {len(problems_found)} problematic configurations:[/yellow]")
    for problem in problems_found:
        console.print(f"  {problem}")
    
    if dry_run:
        console.print("\n[blue]🔍 Dry run mode - no changes made[/blue]")
        return
    
    # Apply fixes
    if projects_to_clean:
        console.print(f"\n[blue]🔧 Cleaning up configurations...[/blue]")
        
        for project_path, servers_to_remove in projects_to_clean.items():
            for server_name in servers_to_remove:
                del config["projectConfigs"][project_path]["mcpServers"][server_name]
                console.print(f"  ✅ Removed {project_path}:{server_name}")
        
        # Save updated configuration
        try:
            with open(claude_config, 'w') as f:
                json.dump(config, f, indent=2)
            console.print(f"\n[green]✅ Configuration cleaned successfully[/green]")
            if backup_path:
                console.print(f"[green]📁 Backup saved to: {backup_path}[/green]")
        except Exception as e:
            console.print(f"[red]Error saving configuration: {e}[/red]")
            if backup_path:
                console.print(f"[yellow]Restoring from backup...[/yellow]")
                shutil.copy2(backup_path, claude_config)


@cli.command("server-details")
@click.argument("server_name")
@handle_errors
def server_details(server_name: str):
    """Show detailed information about a specific server including its tools.
    
    Displays comprehensive information about an MCP server including:
    - Basic server information (type, status, command)
    - Available tools and their descriptions
    - Usage examples for Claude Code
    
    Example:
      mcp-manager server-details SQLite
      mcp-manager server-details filesystem
    """
    asyncio.run(_server_details_impl(server_name))


async def _server_details_impl(server_name: str):
    """Implementation of server-details command."""
    manager = cli_context.get_manager()
    
    console.print(f"[blue]🔍 Getting details for server: {server_name}[/blue]")
    console.print()
    
    # Get detailed server information
    details = await manager.get_server_details(server_name)
    
    if not details:
        console.print(f"[red]❌ Server '{server_name}' not found[/red]")
        console.print()
        
        # Show available servers
        servers = await manager.list_servers()
        if servers:
            console.print("[yellow]💡 Available servers:[/yellow]")
            for server in servers:
                console.print(f"  • {server.name} ({server.server_type.value})")
        else:
            console.print("[yellow]💡 No servers configured[/yellow]")
        return
    
    # Display server details
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    
    # Server header
    status_color = "green" if details['status'] == "enabled" else "red"
    console.print(Panel(
        f"[bold cyan]{details['name']}[/bold cyan] - [{status_color}]{details['status'].upper()}[/{status_color}]",
        title="📦 MCP Server Details",
        style="blue",
        box=box.ROUNDED
    ))
    console.print()
    
    # Basic information table
    info_table = Table(
        title="Server Information",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold white on blue"
    )
    info_table.add_column("Property", style="cyan", width=15)
    info_table.add_column("Value", style="white")
    
    info_table.add_row("Name", details['name'])
    info_table.add_row("Type", details['type'])
    info_table.add_row("Scope", details.get('scope', 'unknown'))
    info_table.add_row("Status", f"[{status_color}]{details['status']}[/{status_color}]")
    info_table.add_row("Command", details.get('command', 'N/A'))
    
    if details.get('args'):
        args_str = ' '.join(details['args']) if isinstance(details['args'], list) else str(details['args'])
        info_table.add_row("Arguments", args_str)
    
    if details.get('env'):
        env_count = len(details['env']) if isinstance(details['env'], dict) else 0
        info_table.add_row("Environment", f"{env_count} variables")
    
    console.print(info_table)
    console.print()
    
    # Tools information
    tool_count = details.get('tool_count', 'Unknown')
    tools = details.get('tools', [])
    source = details.get('source', 'unknown')
    
    if tool_count != 'Unknown' and isinstance(tool_count, int) and tool_count > 0:
        console.print(f"[bold green]🔧 {tool_count} Tools Available[/bold green] [dim]({source})[/dim]")
        console.print()
        
        if tools:
            tools_table = Table(
                title="Available Tools",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold white on green"
            )
            tools_table.add_column("#", style="dim", width=4, justify="center")
            tools_table.add_column("Tool Name", style="cyan", width=25)
            tools_table.add_column("Description", style="white")
            
            for i, tool in enumerate(tools, 1):
                tool_name = tool.get('name', f'Tool {i}')
                tool_desc = tool.get('description', 'No description available')
                tools_table.add_row(str(i), tool_name, tool_desc)
            
            console.print(tools_table)
        else:
            console.print("[dim]Individual tool names not available - tools accessible via MCP protocol[/dim]")
        
        console.print()
        
        # Usage examples
        console.print("[bold]💡 Usage in Claude Code:[/bold]")
        
        if details['type'] == 'docker-desktop':
            console.print("[dim]These tools are available via Docker Desktop MCP integration:[/dim]")
            console.print(f"  [yellow]@{details['name']} <tool-command>[/yellow]")
            console.print()
            
            console.print("[cyan]General usage:[/cyan]")
            console.print(f"  [yellow]@{details['name']} <command> [arguments][/yellow]")
            console.print(f"  [yellow]@{details['name']} help[/yellow] - Show available commands")
        else:
            console.print(f"[dim]General MCP server usage:[/dim]")
            console.print(f"  [yellow]@{details['name']} <command>[/yellow]")
            
    elif tool_count == 'Unknown':
        console.print(f"[yellow]🔧 Tool Information Not Available[/yellow] [dim]({source})[/dim]")
        console.print()
        
        # Enhanced display for Docker containers
        if source == "docker_container_introspection_failed":
            fallback_info = details.get('fallback_info', {})
            docker_image = details.get('docker_image')
            
            console.print("[dim]Docker container tool discovery failed.[/dim]")
            
            if docker_image:
                console.print(f"[dim]Docker Image: {docker_image}[/dim]")
            
            # Show likely tools if available
            likely_tools = fallback_info.get('likely_tools', [])
            if likely_tools:
                console.print()
                console.print("[bold cyan]🔍 Likely Available Tools:[/bold cyan]")
                
                tools_table = Table(
                    box=box.SIMPLE,
                    show_header=True,
                    header_style="bold cyan"
                )
                tools_table.add_column("Tool", style="green", width=20)
                tools_table.add_column("Description", style="white")
                
                for tool in likely_tools:
                    tools_table.add_row(tool['name'], tool['description'])
                
                console.print(tools_table)
            
            # Show troubleshooting suggestions
            suggestions = fallback_info.get('suggestions', [])
            if suggestions:
                console.print()
                console.print("[bold cyan]💡 Troubleshooting:[/bold cyan]")
                for suggestion in suggestions:
                    console.print(f"  [dim]• {suggestion}[/dim]")
        else:
            console.print("[dim]This server type does not provide detailed tool information.[/dim]")
            console.print(f"[dim]Try using:[/dim] [yellow]@{details['name']} help[/yellow]")
        
    else:
        console.print(f"[red]⚠️ No Tools Detected[/red] [dim]({source})[/dim]")
        console.print()
        console.print("[dim]This may indicate a server configuration issue.[/dim]")
        console.print("Consider checking the server configuration or status.")


@cli.command()
@click.argument("name")
@click.option(
    "--interactive", "-i",
    is_flag=True,
    help="Interactive configuration mode with prompts"
)
@click.option(
    "--show", "-s",
    is_flag=True,
    help="Show current configuration without modifying"
)
@handle_errors
def configure(name: str, interactive: bool, show: bool):
    """Configure or reconfigure an MCP server that requires additional settings.
    
    This command allows you to:
    - View current configuration for servers like filesystem, SQLite, PostgreSQL
    - Modify configuration interactively 
    - Update Docker Desktop MCP server settings
    
    Examples:
      mcp-manager configure filesystem --interactive
      mcp-manager configure SQLite --show
      mcp-manager configure postgresql --interactive
    """
    asyncio.run(_configure_impl(name, interactive, show))


async def _configure_impl(name: str, interactive: bool, show: bool):
    """Implementation of configure command."""
    import os
    import yaml
    from pathlib import Path
    from rich.prompt import Prompt, Confirm
    
    manager = cli_context.get_manager()
    
    console.print(f"[bold blue]🔧 Configuring MCP Server: {name}[/bold blue]")
    
    # Get current server configuration
    servers = await manager.list_servers()
    target_server = next((s for s in servers if s.name == name), None)
    
    if not target_server:
        console.print(f"[red]✗[/red] Server '{name}' not found")
        console.print("[yellow]💡[/yellow] Available servers:")
        for server in servers:
            console.print(f"  • {server.name} ({server.server_type.value})")
        return
    
    console.print(f"[cyan]Server Type:[/cyan] {target_server.server_type.value}")
    console.print(f"[cyan]Current Command:[/cyan] {target_server.command}")
    
    # Check if this is a configurable server
    configurable_servers = {
        'filesystem': {
            'description': 'Filesystem access requires specifying allowed directories',
            'config_type': 'docker_mcp' if 'docker' in target_server.command else 'args',
            'settings': ['directory_paths']
        },
        'sqlite': {
            'description': 'SQLite server requires a database file path',
            'config_type': 'docker_mcp' if 'docker' in target_server.command else 'args',
            'settings': ['db_path']
        },
        'postgresql': {
            'description': 'PostgreSQL server requires database connection details',
            'config_type': 'args',
            'settings': ['connection_string']
        }
    }
    
    # Find matching configurable server
    config_info = None
    for key, info in configurable_servers.items():
        if key in name.lower():
            config_info = info
            break
    
    if not config_info:
        console.print(f"[yellow]⚠[/yellow] Server '{name}' does not require additional configuration")
        console.print(f"[dim]Current configuration is sufficient for this server type[/dim]")
        return
    
    console.print(f"[blue]ℹ[/blue] {config_info['description']}")
    
    # Show current configuration
    if config_info['config_type'] == 'docker_mcp':
        # Docker Desktop MCP server - check config.yaml
        docker_config_file = Path.home() / ".docker" / "mcp" / "config.yaml"
        current_config = {}
        
        if docker_config_file.exists():
            try:
                with open(docker_config_file, 'r') as f:
                    docker_config = yaml.safe_load(f) or {}
                    current_config = docker_config.get(name, {})
            except Exception as e:
                console.print(f"[yellow]⚠[/yellow] Could not read Docker MCP config: {e}")
        
        console.print(f"\n[bold]Current Docker MCP Configuration:[/bold]")
        if current_config:
            console.print(yaml.dump({name: current_config}, default_flow_style=False))
        else:
            console.print(f"[dim]No configuration found for {name}[/dim]")
        
        if show:
            return
            
        if not interactive:
            console.print(f"[yellow]💡[/yellow] Use --interactive to modify configuration")
            console.print(f"[yellow]💡[/yellow] Or edit directly: {docker_config_file}")
            return
        
        # Interactive configuration for Docker MCP servers
        if 'filesystem' in name.lower():
            console.print(f"\n[bold]Configure Filesystem Paths:[/bold]")
            console.print(f"[dim]Current paths: {current_config.get('paths', ['None configured'])}[/dim]")
            
            if Confirm.ask("Modify filesystem paths?"):
                new_paths = []
                console.print(f"[blue]Enter directory paths (press Enter with empty path to finish):[/blue]")
                
                # Add current paths as defaults
                existing_paths = current_config.get('paths', [])
                for i, path in enumerate(existing_paths):
                    console.print(f"[dim]Current path {i+1}: {path}[/dim]")
                    new_path = Prompt.ask(f"Path {i+1}", default=path)
                    if new_path.strip():
                        new_paths.append(os.path.expanduser(new_path.strip()))
                
                # Add new paths
                path_num = len(existing_paths) + 1
                while True:
                    new_path = Prompt.ask(f"Path {path_num} (empty to finish)", default="")
                    if not new_path.strip():
                        break
                    new_paths.append(os.path.expanduser(new_path.strip()))
                    path_num += 1
                
                if new_paths:
                    # Update Docker MCP config
                    docker_config_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    full_config = {}
                    if docker_config_file.exists():
                        try:
                            with open(docker_config_file, 'r') as f:
                                full_config = yaml.safe_load(f) or {}
                        except:
                            pass
                    
                    full_config[name] = {'paths': new_paths, 'env': {}}
                    
                    with open(docker_config_file, 'w') as f:
                        yaml.dump(full_config, f, default_flow_style=False)
                    
                    console.print(f"[green]✓[/green] Updated filesystem paths: {new_paths}")
                    console.print(f"[green]📁[/green] Configuration saved to: {docker_config_file}")
                else:
                    console.print(f"[yellow]No paths specified - configuration unchanged[/yellow]")
        
        elif 'sqlite' in name.lower():
            console.print(f"\n[bold]Configure SQLite Database:[/bold]")
            current_db = current_config.get('args', [])
            if current_db and len(current_db) >= 2:
                current_path = current_db[1]  # --db-path VALUE
            else:
                current_path = "/tmp/mcp-database.db"
            
            console.print(f"[dim]Current database: {current_path}[/dim]")
            
            if Confirm.ask("Modify database path?"):
                new_db_path = Prompt.ask("Database file path", default=current_path)
                new_db_path = os.path.expanduser(new_db_path.strip())
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(new_db_path), exist_ok=True)
                
                # Create database if it doesn't exist
                if not os.path.exists(new_db_path):
                    import sqlite3
                    with sqlite3.connect(new_db_path):
                        pass
                    console.print(f"[green]✓[/green] Created database file: {new_db_path}")
                
                # Update Docker MCP config
                docker_config_file.parent.mkdir(parents=True, exist_ok=True)
                
                full_config = {}
                if docker_config_file.exists():
                    try:
                        with open(docker_config_file, 'r') as f:
                            full_config = yaml.safe_load(f) or {}
                    except:
                        pass
                
                full_config[name] = {
                    'args': ['--db-path', new_db_path],
                    'env': {}
                }
                
                with open(docker_config_file, 'w') as f:
                    yaml.dump(full_config, f, default_flow_style=False)
                
                console.print(f"[green]✓[/green] Updated database path: {new_db_path}")
                console.print(f"[green]📁[/green] Configuration saved to: {docker_config_file}")
        
    else:
        # Non-Docker server - show args
        console.print(f"\n[bold]Current Arguments:[/bold] {target_server.args}")
        
        if show:
            return
            
        console.print(f"[yellow]💡[/yellow] This server uses command-line arguments")
        console.print(f"[yellow]💡[/yellow] Use 'mcp-manager remove {name}' and 'mcp-manager add {name} <new-command>' to reconfigure")


@cli.command("sync")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be synchronized without making changes"
)
@click.option(
    "--auto-apply",
    is_flag=True,
    help="Automatically apply detected changes without prompts"
)
@handle_errors
def sync_external(dry_run: bool, auto_apply: bool):
    """Synchronize with external MCP configuration changes.
    
    Detects changes made by external tools (docker mcp, claude mcp) and
    synchronizes the local MCP Manager catalog to match.
    
    Examples:
      mcp-manager sync              # Interactive sync with prompts
      mcp-manager sync --dry-run    # Show changes without applying
      mcp-manager sync --auto-apply # Apply all changes automatically
    """
    asyncio.run(_sync_external_impl(dry_run, auto_apply))


async def _sync_external_impl(dry_run: bool, auto_apply: bool):
    """Implementation of sync command."""
    from rich.prompt import Confirm
    from rich.panel import Panel
    from rich import box
    
    manager = cli_context.get_manager()
    console.print("[bold blue]🔄 External Configuration Sync[/bold blue]")
    console.print()
    
    # Detect changes
    console.print("[blue]🔍 Detecting external changes...[/blue]")
    changes = await detect_external_changes(manager)
    
    if not changes:
        console.print("[green]✅ No external changes detected - configurations are in sync[/green]")
        return
    
    console.print(f"[yellow]📋 Detected {len(changes)} configuration changes:[/yellow]")
    console.print()
    
    # Group changes by source
    changes_by_source = {}
    for change in changes:
        source = change.source.value
        if source not in changes_by_source:
            changes_by_source[source] = []
        changes_by_source[source].append(change)
    
    # Display changes by source
    for source, source_changes in changes_by_source.items():
        source_name = {
            'docker': 'Docker Desktop MCP',
            'claude_user': 'Claude User Config',
            'claude_project': 'Claude Project Config',
            'claude_internal': 'Claude Internal Config'
        }.get(source, source)
        
        console.print(Panel(
            f"[bold cyan]{len(source_changes)} changes[/bold cyan]",
            title=f"📦 {source_name}",
            style="cyan",
            box=box.ROUNDED
        ))
        
        # Create changes table
        changes_table = Table(
            box=box.SIMPLE,
            show_header=True,
            header_style="bold cyan"
        )
        changes_table.add_column("Change", style="yellow", width=15)
        changes_table.add_column("Server", style="green", width=20)
        changes_table.add_column("Details", style="white")
        
        for change in source_changes:
            change_desc = {
                'server_added': '➕ Added',
                'server_removed': '➖ Removed',
                'server_modified': '🔄 Modified',
                'server_enabled': '✅ Enabled',
                'server_disabled': '❌ Disabled'
            }.get(change.change_type.value, change.change_type.value)
            
            # Format details
            details_parts = []
            if 'command' in change.details:
                details_parts.append(f"cmd: {change.details['command']}")
            if 'reason' in change.details:
                details_parts.append(f"({change.details['reason']})")
            
            details = ', '.join(details_parts) if details_parts else 'No details'
            
            changes_table.add_row(change_desc, change.server_name, details)
        
        console.print(changes_table)
        console.print()
    
    if dry_run:
        console.print("[blue]🔍 Dry run mode - no changes applied[/blue]")
        return
    
    # Apply changes
    if not auto_apply:
        if not Confirm.ask("Apply these changes to synchronize configurations?"):
            console.print("[yellow]⏸️ Synchronization cancelled by user[/yellow]")
            return
    
    console.print("[blue]🔄 Applying synchronization changes...[/blue]")
    
    success_count = 0
    error_count = 0
    
    for change in changes:
        try:
            change_desc = f"{change.change_type.value} {change.server_name}"
            
            if change.change_type.value == 'server_added':
                # Add server to catalog based on external configuration
                server_info = change.details.get('server_info', {})
                command = server_info.get('command', '')
                args = server_info.get('args', [])
                env = server_info.get('env', {})
                
                # Simple server type detection - don't overthink it
                if command == 'npx':
                    server_type = ServerType.NPM
                elif command.endswith('/docker') or command == 'docker':
                    server_type = ServerType.CUSTOM  # Let Claude handle Docker servers
                else:
                    server_type = ServerType.CUSTOM
                
                try:
                    await manager.add_server(
                        name=change.server_name,
                        server_type=server_type,
                        command=command,
                        args=args,
                        env=env,
                        scope=ServerScope.USER
                    )
                    console.print(f"  ✅ Added server: {change.server_name}")
                except Exception as e:
                    # If server already exists in Claude, just add to catalog
                    if "already exists" in str(e).lower():
                        catalog = await manager._get_server_catalog()
                        servers = catalog.setdefault('servers', {})
                        servers[change.server_name] = {
                            'name': change.server_name,
                            'type': server_type.value,
                            'command': command,
                            'args': args,
                            'env': env,
                            'enabled': True,
                            'scope': 'user'
                        }
                        await manager._save_server_catalog(catalog)
                        console.print(f"  ✅ Synced server to catalog: {change.server_name}")
                    else:
                        raise
                
            elif change.change_type.value == 'server_removed':
                # For servers that don't exist externally, remove from catalog directly
                # This handles cases where servers were removed externally and we need to sync our catalog
                try:
                    # First try regular removal (works if server exists in Claude)
                    await manager.remove_server(change.server_name)
                    console.print(f"  ➖ Removed server: {change.server_name}")
                except Exception as e:
                    # If regular removal fails, remove from catalog directly
                    logger.debug(f"Regular removal failed: {e}, removing from catalog directly")
                    catalog = await manager._get_server_catalog()
                    servers = catalog.get('servers', {})
                    if change.server_name in servers:
                        del servers[change.server_name]
                        await manager._save_server_catalog(catalog)
                        console.print(f"  ➖ Removed server from catalog: {change.server_name}")
                    else:
                        raise
                
            elif change.change_type.value in ['server_enabled', 'server_disabled']:
                enabled = change.change_type.value == 'server_enabled'
                # Update server status in catalog
                await manager._update_server_status(change.server_name, enabled)
                status = "enabled" if enabled else "disabled"
                console.print(f"  🔄 {change.server_name}: {status}")
                
            success_count += 1
            
        except Exception as e:
            console.print(f"  ❌ Failed to apply change for {change.server_name}: {e}")
            error_count += 1
    
    # Summary
    console.print()
    if success_count > 0:
        console.print(f"[green]✅ Successfully applied {success_count} changes[/green]")
    if error_count > 0:
        console.print(f"[red]❌ Failed to apply {error_count} changes[/red]")
    
    console.print("[blue]🎉 Synchronization complete[/blue]")


@cli.command("detect-changes")
@click.option(
    "--watch",
    is_flag=True,
    help="Continuously monitor for changes (press Ctrl+C to stop)"
)
@click.option(
    "--interval",
    type=int,
    default=5,
    help="Watch interval in seconds (default: 5)"
)
@handle_errors
def detect_changes(watch: bool, interval: int):
    """Detect external MCP configuration changes.
    
    Monitor changes made by external tools like 'docker mcp' and 'claude mcp'
    commands without applying them.
    
    Examples:
      mcp-manager detect-changes           # One-time change detection
      mcp-manager detect-changes --watch   # Continuous monitoring
    """
    asyncio.run(_detect_changes_impl(watch, interval))


async def _detect_changes_impl(watch: bool, interval: int):
    """Implementation of detect-changes command."""
    import time
    from rich.live import Live
    from rich.panel import Panel
    from rich import box
    
    manager = cli_context.get_manager()
    detector = ChangeDetector(manager)
    
    if not watch:
        # Single detection
        console.print("[blue]🔍 Detecting external configuration changes...[/blue]")
        changes = await detector.detect_changes()
        
        if not changes:
            console.print("[green]✅ No external changes detected[/green]")
            return
        
        console.print(f"[yellow]📋 Detected {len(changes)} changes:[/yellow]")
        for change in changes:
            console.print(f"  • {change}")
        
        console.print("\n[dim]💡 Use 'mcp-manager sync' to apply these changes[/dim]")
        return
    
    # Watch mode
    console.print(f"[blue]👀 Monitoring external changes (interval: {interval}s, press Ctrl+C to stop)...[/blue]")
    console.print()
    
    try:
        last_changes = []
        
        while True:
            changes = await detector.detect_changes()
            
            # Only show new changes
            new_changes = [c for c in changes if c not in last_changes]
            
            if new_changes:
                timestamp = time.strftime("%H:%M:%S")
                console.print(Panel(
                    f"[yellow]{len(new_changes)} new changes detected at {timestamp}[/yellow]",
                    style="yellow",
                    box=box.ROUNDED
                ))
                
                for change in new_changes:
                    console.print(f"  • {change}")
                
                console.print()
            
            last_changes = changes
            await asyncio.sleep(interval)
            
    except KeyboardInterrupt:
        console.print("\n[blue]📊 Change detection stopped[/blue]")
        
        # Show final summary
        history = detector.get_detection_history()
        if history:
            console.print(f"[cyan]Total changes detected in this session: {len(history)}[/cyan]")


@cli.command("monitor")
@click.option(
    "--start",
    is_flag=True,
    help="Start the background monitor service"
)
@click.option(
    "--stop", 
    is_flag=True,
    help="Stop the background monitor service"
)
@click.option(
    "--status",
    is_flag=True,
    help="Show monitor service status"
)
@click.option(
    "--interval",
    type=int,
    default=60,
    help="Check interval in seconds (default: 60)"
)
@click.option(
    "--auto-sync",
    is_flag=True,
    help="Enable automatic synchronization of changes"
)
@handle_errors
def monitor_service(start: bool, stop: bool, status: bool, interval: int, auto_sync: bool):
    """Manage the background monitoring service.
    
    The monitor service continuously watches for external MCP configuration
    changes and can automatically sync them or notify when changes are detected.
    
    Examples:
      mcp-manager monitor --start --auto-sync    # Start with auto-sync
      mcp-manager monitor --status               # Check service status
      mcp-manager monitor --stop                 # Stop the service
    """
    asyncio.run(_monitor_service_impl(start, stop, status, interval, auto_sync))


async def _monitor_service_impl(start: bool, stop: bool, status: bool, interval: int, auto_sync: bool):
    """Implementation of monitor service command."""
    from rich.panel import Panel
    from rich import box
    
    if not any([start, stop, status]):
        # Default to showing status
        status = True
    
    if status:
        console.print("[blue]🔍 Background Monitor Service Status[/blue]")
        console.print()
        
        # Check if service is running (this is a simplified check)
        # In a real implementation, you'd check if a daemon process is running
        console.print(Panel(
            "[dim]Service status checking not implemented yet[/dim]\n\n"
            "[yellow]To start monitoring:[/yellow] mcp-manager monitor --start\n"
            "[yellow]For real-time monitoring:[/yellow] mcp-manager detect-changes --watch",
            title="Monitor Status",
            style="blue",
            box=box.ROUNDED
        ))
        return
    
    if start:
        console.print("[blue]🚀 Starting background monitor service...[/blue]")
        console.print()
        
        manager = cli_context.get_manager()
        
        def notification_callback(changes):
            """Handle change notifications."""
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.info(f"[{timestamp}] Detected {len(changes)} configuration changes")
            for change in changes:
                logger.info(f"  • {change}")
        
        monitor = BackgroundMonitor(
            manager=manager,
            check_interval=interval,
            auto_sync=auto_sync,
            notification_callback=notification_callback
        )
        
        console.print(f"[green]Monitor configuration:[/green]")
        console.print(f"  • Check interval: {interval} seconds")
        console.print(f"  • Auto-sync: {'enabled' if auto_sync else 'disabled'}")
        console.print()
        console.print("[dim]Press Ctrl+C to stop monitoring[/dim]")
        console.print()
        
        try:
            await monitor.start()
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping monitor...[/yellow]")
            await monitor.stop()
            console.print("[blue]Monitor stopped[/blue]")
    
    if stop:
        console.print("[yellow]⏸️ Stop command not implemented yet[/yellow]")
        console.print("[dim]Use Ctrl+C to stop a running monitor session[/dim]")


@cli.command("monitor-status")
@handle_errors
def monitor_status_quick():
    """Quick status check for background monitor service."""
    console.print("[blue]🔍 Quick Monitor Status[/blue]")
    console.print()
    console.print("[dim]Full status available with: mcp-manager monitor --status[/dim]")


@cli.group("mode")
def mode():
    """Manage MCP Manager operation modes (Direct/Proxy/Hybrid)."""
    pass


@mode.command("status")
@handle_errors
def mode_status():
    """Show current operation mode and configuration."""
    try:
        from mcp_manager.core.modes import ModeManager
        from mcp_manager.core.config.proxy_config import ProxyModeConfig
        
        # Get configuration
        config = get_config()
        
        # Create proxy config
        try:
            proxy_config = ProxyModeConfig()
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load proxy config: {e}[/yellow]")
            proxy_config = None
        
        # Create mode manager
        try:
            # Add proxy config to main config if it doesn't exist
            if not hasattr(config, 'proxy'):
                config.proxy = proxy_config
            mode_manager = ModeManager(config)
        except Exception as e:
            console.print(f"[red]Error creating mode manager: {e}[/red]")
            # Fallback to basic status
            console.print("[blue]📋 MCP Manager Mode Status[/blue]")
            console.print()
            console.print("current_mode: direct")
            console.print("proxy_available: false")
            console.print("direct_available: true")
            return
        
        # Get mode information
        mode_info = mode_manager.get_mode_info()
        current_mode = mode_manager.get_current_mode()
        
        console.print("[blue]📋 MCP Manager Mode Status[/blue]")
        console.print()
        console.print(f"current_mode: {current_mode.value}")
        console.print(f"direct_available: {mode_info.get('direct_available', True)}")
        console.print(f"proxy_available: {mode_info.get('proxy_available', False)}")
        console.print()
        
        if proxy_config and proxy_config.enabled:
            console.print("[blue]🔧 Proxy Configuration[/blue]")
            console.print(f"  endpoint: {proxy_config.get_proxy_endpoint()}")
            console.print(f"  authentication: {'enabled' if proxy_config.is_authentication_required() else 'disabled'}")
            console.print(f"  caching: {'enabled' if proxy_config.enable_caching else 'disabled'}")
            console.print()
        
        console.print(f"supported_modes: {', '.join(mode_info.get('supported_modes', ['direct']))}")
        
    except Exception as e:
        console.print(f"[red]Error getting mode status: {e}[/red]")
        logger.error(f"Mode status error: {e}")


@mode.command("switch")
@click.argument('target_mode', type=click.Choice(['direct', 'proxy', 'hybrid']))
@click.option('--force', is_flag=True, help='Force mode switch without validation')
@handle_errors
def mode_switch(target_mode: str, force: bool):
    """Switch between operation modes."""
    try:
        from mcp_manager.core.modes import ModeManager, OperationMode
        from mcp_manager.core.config.proxy_config import ProxyModeConfig
        
        # Get configuration
        config = get_config()
        
        # Create proxy config
        try:
            proxy_config = ProxyModeConfig()
            if not hasattr(config, 'proxy'):
                config.proxy = proxy_config
        except Exception as e:
            console.print(f"[red]Error loading proxy config: {e}[/red]")
            return
        
        # Create mode manager
        mode_manager = ModeManager(config)
        target = OperationMode(target_mode)
        
        console.print(f"[blue]🔄 Switching to {target_mode} mode...[/blue]")
        
        if force:
            console.print("[yellow]⚠️  Force mode enabled - skipping validation[/yellow]")
        
        # Attempt mode switch
        success = mode_manager.switch_mode(target, force=force)
        
        if success:
            console.print(f"[green]✅ Successfully switched to {target_mode} mode[/green]")
        else:
            console.print(f"[red]❌ Failed to switch to {target_mode} mode[/red]")
            console.print("[dim]Use --force to override validation checks[/dim]")
    
    except Exception as e:
        console.print(f"[red]Error switching modes: {e}[/red]")
        logger.error(f"Mode switch error: {e}")


@cli.group("proxy")
def proxy():
    """Manage MCP proxy server (unified endpoint mode)."""
    pass


@proxy.command("status")
@handle_errors
def proxy_status():
    """Show proxy server status and statistics."""
    console.print("[blue]📊 MCP Proxy Status[/blue]")
    console.print()
    
    try:
        from mcp_manager.core.config.proxy_config import ProxyModeConfig
        
        proxy_config = ProxyModeConfig()
        
        if not proxy_config.enabled:
            console.print("[yellow]⚠️  Proxy mode is disabled[/yellow]")
            console.print("Enable with: export MCP_PROXY_MODE=true")
            return
        
        console.print(f"🌐 Endpoint: {proxy_config.get_proxy_endpoint()}")
        console.print(f"🔌 MCP Endpoint: {proxy_config.get_mcp_endpoint()}")
        console.print(f"🔐 Authentication: {'enabled' if proxy_config.is_authentication_required() else 'disabled'}")
        console.print(f"💾 Caching: {'enabled' if proxy_config.enable_caching else 'disabled'}")
        console.print(f"⚖️  Load Balancing: {'enabled' if proxy_config.enable_load_balancing else 'disabled'}")
        console.print()
        console.print("[dim]Note: Actual proxy server implementation pending[/dim]")
        
    except Exception as e:
        console.print(f"[red]Error getting proxy status: {e}[/red]")


@proxy.command("validate")
@handle_errors  
def proxy_validate():
    """Validate proxy configuration and requirements."""
    console.print("[blue]🔍 Validating Proxy Configuration[/blue]")
    console.print()
    
    try:
        from mcp_manager.core.modes import ModeManager
        from mcp_manager.core.config.proxy_config import ProxyModeConfig
        
        # Load configuration
        config = get_config()
        proxy_config = ProxyModeConfig()
        
        if not hasattr(config, 'proxy'):
            config.proxy = proxy_config
        
        # Create mode manager and validate
        mode_manager = ModeManager(config)
        validation_result = mode_manager.validate_proxy_requirements(proxy_config)
        
        if validation_result.valid:
            console.print("[green]✅ Proxy configuration is valid[/green]")
        else:
            console.print("[red]❌ Proxy configuration has issues[/red]")
        
        # Show validation details
        if validation_result.issues:
            console.print()
            console.print("[red]🚨 Issues:[/red]")
            for issue in validation_result.issues:
                console.print(f"  • {issue}")
        
        if validation_result.warnings:
            console.print()
            console.print("[yellow]⚠️  Warnings:[/yellow]")
            for warning in validation_result.warnings:
                console.print(f"  • {warning}")
        
        if validation_result.recommendations:
            console.print()
            console.print("[blue]💡 Recommendations:[/blue]")
            for rec in validation_result.recommendations:
                console.print(f"  • {rec}")
    
    except Exception as e:
        console.print(f"[red]Error validating proxy config: {e}[/red]")


def launch_interactive_menu():
    """Launch the interactive menu interface."""
    try:
        from mcp_manager.tui.rich_menu import main as rich_menu_main
        console.print("[blue]🚀 Launching interactive menu...[/blue]")
        rich_menu_main()
    except ImportError as e:
        console.print("[red]Interactive menu dependencies not available[/red]")
        console.print(f"Error: {e}")
        console.print("Install with: pip install mcp-manager[rich]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error launching interactive menu: {e}[/red]")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    cli()


if __name__ == "__main__":
    main()