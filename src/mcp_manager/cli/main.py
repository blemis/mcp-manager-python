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
from mcp_manager.utils.config import get_config
from mcp_manager.utils.logging import setup_logging
from mcp_manager.utils.logging import get_logger
from mcp_manager.cli import enhanced_commands

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
        
        value = Prompt.ask(
            prompt_config['prompt'],
            default=prompt_config['default']
        )
        
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
    
    console.print(f"[green]✓[/green] Updated Docker MCP configuration for {server_name}")


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
        level=config.logging.level,
        log_file=config.get_log_file(),
        format_type=config.logging.format_type,
        enable_rich=config.logging.enable_rich,
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
    
    # Get servers
    servers = asyncio.run(manager.list_servers())
    
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
    
    # Use enhanced validation
    enhanced_commands.validate_and_add_server(
        manager=manager,
        name=name,
        command=command,
        scope=scope,
        server_type=server_type,
        description=description,
        env=env,
        args=args,
    )


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
    
    # Use enhanced validation and confirmation
    enhanced_commands.validate_and_remove_server(
        manager=manager,
        name=name,
        scope=scope,
        force=force,
    )


@cli.command()
@click.argument("name")
@handle_errors
def enable(name: str):
    """Enable an MCP server."""
    manager = cli_context.get_manager()
    
    # Use enhanced validation
    enhanced_commands.validate_and_enable_server(
        manager=manager,
        name=name,
    )


@cli.command()
@click.argument("name")
@handle_errors  
def disable(name: str):
    """Disable an MCP server."""
    manager = cli_context.get_manager()
    
    # Use enhanced validation
    enhanced_commands.validate_and_disable_server(
        manager=manager,
        name=name,
    )


@cli.command()
@click.option(
    "--query", "-q",
    help="Search query"
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
    """Discover available MCP servers."""
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
        existing_servers = await manager.list_servers()
        if any(s.name == server_name for s in existing_servers):
            console.print(f"[yellow]⚠[/yellow] Server '{server_name}' already exists")
            from rich.prompt import Confirm
            if not Confirm.ask("Replace existing server?"):
                console.print("[dim]Installation cancelled[/dim]")
                return
        
        # Check for similar servers that might provide the same functionality
        from mcp_manager.cli.enhanced_commands import _find_similar_servers
        similar_servers = _find_similar_servers(server_name, target_result.server_type.value, existing_servers)
        if similar_servers:
            console.print(f"[yellow]⚠[/yellow] Found similar servers that might provide the same functionality:")
            for similar in similar_servers:
                console.print(f"  • {similar.name} ({similar.server_type.value}) - {similar.description or 'No description'}")
            console.print(f"\n[yellow]Installing multiple servers for the same functionality may cause conflicts.[/yellow]")
            from rich.prompt import Confirm
            if not Confirm.ask("Continue anyway?"):
                console.print("[dim]Installation cancelled[/dim]")
                return
        
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
        
        # Install the server
        try:
            server = await manager.add_server(
                name=server_name,
                server_type=target_result.server_type,
                command=target_result.install_command,
                description=target_result.description,
                args=install_args,
            )
            console.print(f"[green]✓[/green] Installed server: {server.name}")
            console.print("[dim]Server is now active in Claude Code![/dim]")
            
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
        
        # Install the server
        server = await manager.add_server(
            name=exact_match.name,
            server_type=exact_match.server_type,
            command=exact_match.install_command,
            description=exact_match.description,
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