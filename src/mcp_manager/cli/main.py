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
    manager = cli_context.get_manager()
    
    try:
        servers = manager.list_servers()
        
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
            
            table.add_column("Name", style="green", width=20)
            table.add_column("Type", style="blue", width=12)
            table.add_column("Scope", style="yellow", width=8)
            table.add_column("Status", style="white", width=8)
            table.add_column("Command", style="dim", width=40)
            
            for server in servers:
                status = "✅ Enabled" if server.enabled else "❌ Disabled"
                scope_str = server.scope.value if server.scope else "unknown"
                command_str = f"{server.command} {' '.join(server.args[:2])}"
                if len(server.args) > 2:
                    command_str += "..."
                
                table.add_row(
                    server.name,
                    server.server_type.value,
                    scope_str,
                    status,
                    command_str[:37] + "..." if len(command_str) > 40 else command_str
                )
            
            console.print("")
            console.print(table)
            console.print("")
            console.print("[dim]💡 Use 'mcp-manager server-details <name>' for detailed information[/dim]")
            
    except Exception as e:
        console.print(f"[red]Failed to list servers: {e}[/red]")
        sys.exit(1)


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
            manager = cli_context.get_manager()
            
            # Parse environment variables
            env_dict = {}
            for env_var in env:
                if '=' in env_var:
                    key, value = env_var.split('=', 1)
                    env_dict[key] = value
                else:
                    console.print(f"[yellow]Warning: Invalid environment variable format: {env_var}[/yellow]")
            
            # Convert string types to enums
            scope_enum = ServerScope(scope)
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
        
        success = manager.remove_server(name, scope_enum)
        
        if success:
            console.print(f"[green]✅ Removed server '{name}'[/green]")
        else:
            console.print(f"[red]❌ Server '{name}' not found or could not be removed[/red]")
            sys.exit(1)
            
    except Exception as e:
        console.print(f"[red]Failed to remove server: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
@handle_errors
def nuke(force: bool):
    """Remove ALL MCP servers (nuclear option) - Fast config reset."""
    import json
    import os
    import shutil
    import subprocess
    from pathlib import Path
    
    if not force:
        from rich.prompt import Confirm
        console.print("[red]⚠️ WARNING: This will remove ALL MCP servers![/red]")
        console.print("[dim]This action cannot be undone.[/dim]")
        if not Confirm.ask("Are you absolutely sure?"):
            console.print("[dim]Operation cancelled[/dim]")
            return
    
    console.print("💥 💥 💥 💥 💥 💥 💥 💥 💥 💥 💥 💥")
    console.print("[red]🚀 NUCLEAR OPTION - REMOVING ALL MCPs![/red]")
    console.print("💥 💥 💥 💥 💥 💥 💥 💥 💥 💥 💥 💥")
    
    try:
        # 1. Kill zombie MCP processes
        console.print("[blue]Step 1: Killing zombie MCP processes...[/blue]")
        try:
            subprocess.run(["pkill", "-f", "mcp"], capture_output=True)
            subprocess.run(["pkill", "-f", "npx.*mcp"], capture_output=True)
        except:
            pass
        
        # 2. Clean up Docker containers
        console.print("[blue]Step 2: Cleaning Docker MCP containers...[/blue]")
        try:
            subprocess.run(["docker", "stop", "$(docker ps -q --filter ancestor=*mcp*)"], shell=True, capture_output=True)
            subprocess.run(["docker", "rm", "$(docker ps -aq --filter ancestor=*mcp*)"], shell=True, capture_output=True)
        except:
            pass
        
        # 3. Disable Docker Desktop MCP servers
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
        
        # 4. Clean configuration files
        console.print("[blue]Step 4: Cleaning configuration files...[/blue]")
        
        # Claude Code user config
        user_config = Path.home() / ".config" / "claude-code" / "mcp-servers.json"
        if user_config.exists():
            with open(user_config, 'w') as f:
                json.dump({"mcpServers": {}}, f, indent=2)
            console.print(f"  ✅ Cleared: {user_config}")
        
        # Claude Code project config
        project_config = Path.cwd() / ".mcp.json"
        if project_config.exists():
            with open(project_config, 'w') as f:
                json.dump({"mcpServers": {}}, f, indent=2)
            console.print(f"  ✅ Cleared: {project_config}")
        
        # Claude internal config
        claude_config = Path.home() / ".claude.json"
        if claude_config.exists():
            try:
                with open(claude_config, 'r') as f:
                    config = json.load(f)
                
                # Clear global MCP servers
                if "mcpServers" in config:
                    config["mcpServers"] = {}
                
                # Clear project-specific MCP servers
                if "projectConfigs" in config:
                    for project_path, project_config in config["projectConfigs"].items():
                        if "mcpServers" in project_config:
                            project_config["mcpServers"] = {}
                
                with open(claude_config, 'w') as f:
                    json.dump(config, f, indent=2)
                
                console.print(f"  ✅ Cleared: {claude_config}")
            except:
                pass
        
        # MCP Manager database
        db_path = Path.home() / ".config" / "mcp-manager" / "mcp_manager.db"
        if db_path.exists():
            try:
                os.remove(db_path)
                console.print(f"  ✅ Removed: {db_path}")
            except:
                pass
        
        console.print("💥 💥 💥 💥 💥 💥 💥 💥 💥 💥 💥 💥")
        console.print("  🚀 Ready for fresh MCP server installation!")
        console.print("💥 💥 💥 💥 💥 💥 💥 💥 💥 💥 💥 💥")
        console.print(f"\n💡 [dim]To start fresh, use:[/dim]")
        console.print(f"   [cyan]mcp-manager install-package modelcontextprotocol-filesystem[/cyan]")
        console.print(f"   [cyan]mcp-manager install-suite --suite-name test[/cyan]")
        
    except Exception as e:
        console.print(f"[red]❌ Nuclear cleanup failed: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("name")
@handle_errors
def enable(name: str):
    """Enable an MCP server."""
    manager = cli_context.get_manager()
    
    try:
        success = manager.enable_server(name)
        if success:
            console.print(f"[green]✅ Enabled server '{name}'[/green]")
        else:
            console.print(f"[red]❌ Server '{name}' not found or could not be enabled[/red]")
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]Failed to enable server: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("name")
@handle_errors
def disable(name: str):
    """Disable an MCP server."""
    manager = cli_context.get_manager()
    
    try:
        success = manager.disable_server(name)
        if success:
            console.print(f"[green]✅ Disabled server '{name}'[/green]")
        else:
            console.print(f"[red]❌ Server '{name}' not found or could not be disabled[/red]")
            sys.exit(1)
    except Exception as e:
        console.print(f"[red]Failed to disable server: {e}[/red]")
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