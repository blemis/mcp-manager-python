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


@click.group(name="mcp-manager")
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
@click.pass_context
def cli(ctx: click.Context, debug: bool, verbose: bool, config_dir: Optional[Path]):
    """
    Enterprise-grade MCP server management tool.
    
    Manage MCP (Model Context Protocol) servers with professional CLI and TUI interfaces.
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
@click.argument("command")
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
@handle_errors
def discover(query: Optional[str], server_type: Optional[str], limit: int):
    """Discover available MCP servers."""
    discovery = cli_context.get_discovery()
    
    type_filter = ServerType(server_type) if server_type else None
    
    # Run async discovery
    async def run_discovery():
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
    table.add_column("Name", style="cyan")
    table.add_column("Type", justify="center")
    table.add_column("Description", style="dim")
    table.add_column("Package", style="green")
    
    for result in results:
        table.add_row(
            result.name,
            result.server_type.value,
            result.description[:60] + "..." if result.description and len(result.description) > 60 else result.description or "",
            result.package,
        )
        
    console.print(table)


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
    """Launch the terminal user interface."""
    try:
        from mcp_manager.tui.main import main as tui_main
        tui_main()
    except ImportError:
        console.print("[red]TUI dependencies not available[/red]")
        console.print("Install with: pip install mcp-manager[tui]")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    cli()


if __name__ == "__main__":
    main()