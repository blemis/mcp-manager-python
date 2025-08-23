"""
Discovery and installation commands for MCP Manager CLI.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from mcp_manager.core.models import ServerType
from mcp_manager.cli.helpers import (
    handle_errors, generate_install_id, prompt_for_server_configuration,
    show_server_details_after_install, show_discovery_for_next_install
)

console = Console()


def _store_discovery_results(results):
    """Store discovery results in database for numbered installation."""
    try:
        from mcp_manager.core.database.server_state import MCPServerStateManager
        db = MCPServerStateManager()
        
        # Clear previous discovery results and store new ones
        db.clear_discovery_cache()
        
        for i, result in enumerate(results, 1):
            db.store_discovery_result(i, result)
            
    except Exception as e:
        # Storage failure is not critical
        pass


def discovery_commands(cli_context):
    """Add discovery commands to the CLI."""
    
    @click.command()
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
    @click.option(
        "--scope",
        type=click.Choice(['local', 'project', 'user'], case_sensitive=False),
        help="Show only servers that would be installed in this scope"
    )
    @handle_errors
    def discover(query: Optional[str], server_type: Optional[str], limit: int, update_catalog: bool, scope: Optional[str]):
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
            console.print("[yellow]No servers found matching your criteria[/yellow]")
            console.print(f"[dim]Try a broader search or check available server types[/dim]")
            return
        
        from rich.table import Table
        
        # Store results in database for install-package command
        _store_discovery_results(results)
        
        # Display results in a table with numbers
        scope_title = f" for {scope} scope" if scope else ""
        table = Table(
            title=f"Discovered MCP Servers ({len(results)} results{scope_title})",
            show_header=True,
            header_style="bold cyan",
            title_style="bold cyan",
            show_lines=True
        )
        
        table.add_column("#", style="green", width=3, no_wrap=True)
        table.add_column("Name", style="cyan", width=18)  # What gets stored in DB
        table.add_column("Type", style="blue", width=8)
        table.add_column("Package/Source", style="white", width=22)
        table.add_column("Description", style="dim")
        
        for i, result in enumerate(results, 1):
            # Use install_id as the name that will be stored
            install_name = generate_install_id(result)
            
            table.add_row(
                str(i),
                install_name,  # This is what they'll use for uninstall
                result.server_type.value,
                result.package or result.name,
                (result.description[:37] + "...") if result.description and len(result.description) > 40 else (result.description or "")
            )
        
        console.print("")
        console.print(table)
        console.print("")
        console.print("[dim]💡 To install a server, use:[/dim]")
        scope_flag = f" --scope {scope}" if scope else ""
        console.print(f"[dim]   [cyan]mcp-manager install-package <number>{scope_flag}[/cyan][/dim]")
        console.print(f"[dim]   Example: [cyan]mcp-manager install-package 3{scope_flag}[/cyan][/dim]")
        console.print(f"[dim]   To uninstall later: [cyan]mcp-manager rm <name>[/cyan][/dim]")
    
    
    @click.command("install-package")
    @click.argument("number_or_name")
    @click.option("--scope", type=click.Choice(['local', 'project', 'user'], case_sensitive=False), default="user", help="Installation scope")
    @handle_errors
    def install_package(number_or_name: str, scope: str):
        """Install a server using number from discovery results."""
        discovery = cli_context.get_discovery()
        
        async def find_and_install():
            matching_server = None
            
            # Try to parse as number first
            try:
                number = int(number_or_name)
                console.print(f"[blue]🔍 Looking up discovery result #{number}[/blue]")
                
                from mcp_manager.core.database.server_state import MCPServerStateManager
                db = MCPServerStateManager()
                result_data = db.get_discovery_result(number)
                
                if result_data:
                    # Convert back to DiscoveryResult object
                    from mcp_manager.core.models import DiscoveryResult, ServerType
                    matching_server = DiscoveryResult(
                        name=result_data['name'],
                        package=result_data['package'],
                        version=result_data['version'],
                        description=result_data['description'],
                        server_type=ServerType(result_data['server_type']),
                        install_command=result_data['install_command'],
                        install_args=result_data['install_args']
                    )
                    console.print(f"[green]✅ Found: {matching_server.name}[/green]")
                else:
                    console.print(f"[red]❌ No discovery result #{number} found[/red]")
                    console.print(f"[yellow]💡 Run 'mcpm discover' first to see numbered options[/yellow]")
                    sys.exit(1)
                    
            except ValueError:
                # Not a number - show helpful message
                console.print(f"[yellow]💡 Please use the number from discovery results[/yellow]")
                console.print(f"[dim]Example: 'mcpm install-package 3'[/dim]")
                console.print(f"[dim]Run 'mcpm discover --query {number_or_name}' first to see numbered options[/dim]")
                sys.exit(1)
            
            # Get manager and install
            manager = cli_context.get_manager()
            # Use generated install_id as server name
            server_name = generate_install_id(matching_server)
            
            console.print(f"[blue]📦 Installing: {server_name}[/blue]")
            console.print(f"[dim]Package: {matching_server.package or 'N/A'}[/dim]")
            console.print(f"[dim]Type: {matching_server.server_type.value}[/dim]")
            
            # Check if server already exists
            if manager.server_exists(server_name):
                console.print(f"[yellow]Server '{server_name}' already exists[/yellow]")
                console.print("[dim]Use 'mcp-manager remove' to uninstall first if you want to reinstall[/dim]")
                return
            
            # Check for similar servers and prompt user
            similar_servers = await manager.check_for_similar_servers(
                server_name, matching_server.server_type, matching_server.install_command, matching_server.install_args
            )
            
            if similar_servers:
                console.print(f"\n[yellow]⚠️ WARNING: Found {len(similar_servers)} similar server(s) that may provide overlapping functionality:[/yellow]")
                console.print("")
                
                for similar in similar_servers:
                    similar_server = similar["server"]
                    score = similar["similarity_score"]
                    reasons = similar.get("reasons", [])
                    
                    console.print(f"[red]🔄 Existing server:[/red] [bold]{similar_server.name}[/bold]")
                    console.print(f"   [dim]Type: {similar_server.server_type.value}[/dim]")
                    console.print(f"   [dim]Status: {'✅ Enabled' if similar_server.enabled else '❌ Disabled'}[/dim]")
                    console.print(f"   [dim]Similarity: {score}% - {', '.join(reasons)}[/dim]")
                    console.print("")
                
                console.print("[yellow]Installing duplicate servers can cause:[/yellow]")
                console.print("   • [red]Conflicting functionality and tool names[/red]")
                console.print("   • [red]Increased resource usage[/red]") 
                console.print("   • [red]Confusion when using tools[/red]")
                console.print("")
                
                from rich.prompt import Confirm
                continue_install = Confirm.ask(
                    f"[bold]Do you want to install '{server_name}' anyway?[/bold]",
                    default=False
                )
                
                if not continue_install:
                    console.print("[dim]Installation cancelled by user[/dim]")
                    return
            
            # Prompt for configuration if needed
            config = prompt_for_server_configuration(
                server_name=server_name,
                server_type=matching_server.server_type,
                package=matching_server.package
            )
            
            try:
                # Separate args and env from config
                config = config or {}
                env_vars = {k: v for k, v in config.items() if k != 'args' and isinstance(v, str)}
                additional_args = config.get('args', []) if isinstance(config.get('args'), list) else []
                
                # Convert scope string to enum
                from mcp_manager.core.models import ServerScope
                scope_enum = ServerScope(scope) if scope else ServerScope.USER
                
                # Add server to manager
                server = await manager.add_server(
                    name=server_name,
                    server_type=matching_server.server_type,
                    command=matching_server.install_command,
                    args=(matching_server.install_args or []) + additional_args,
                    env=env_vars,
                    scope=scope_enum
                )
                
                console.print(f"[green]✅ Successfully installed '{server_name}' in {scope} scope[/green]")
                
                # Show server details
                await show_server_details_after_install(manager, server_name)
                
                # Show additional discovery options
                await show_discovery_for_next_install(discovery)
                
            except Exception as e:
                console.print(f"[red]❌ Installation failed: {e}[/red]")
                console.print("[dim]Check the error details above and try again[/dim]")
                sys.exit(1)
        
        asyncio.run(find_and_install())
    
    
    @click.command()
    @click.argument("name")
    @click.option("--scope", type=click.Choice(['local', 'project', 'user'], case_sensitive=False), default="user", help="Installation scope")
    @handle_errors
    def install(name: str, scope: str):
        """Install a server from discovery results."""
        discovery = cli_context.get_discovery()
        
        async def find_and_install():
            results = await discovery.discover_servers(query=name, limit=10)
            
            if not results:
                console.print(f"[red]No servers found matching '{name}'[/red]")
                console.print("[yellow]💡 Try 'mcp-manager discover' to see all available servers[/yellow]")
                return
            
            # If exactly one match, install it
            if len(results) == 1:
                server_result = results[0]
                console.print(f"[blue]Found exact match: {server_result.name}[/blue]")
            else:
                # Multiple matches - show options
                console.print(f"[yellow]Found {len(results)} servers matching '{name}':[/yellow]")
                for i, result in enumerate(results):
                    console.print(f"  {i + 1}. [cyan]{result.name}[/cyan]: {result.description or 'No description'}")
                
                from rich.prompt import IntPrompt
                try:
                    choice = IntPrompt.ask("Select a server to install", default=1, choices=[str(i + 1) for i in range(len(results))])
                    server_result = results[choice - 1]
                except (EOFError, KeyboardInterrupt):
                    console.print("[dim]Installation cancelled[/dim]")
                    return
            
            # Install the selected server
            manager = cli_context.get_manager()
            server_name = server_result.name
            
            console.print(f"[blue]📦 Installing: {server_name}[/blue]")
            
            # Check if server already exists
            if manager.server_exists(server_name):
                console.print(f"[yellow]Server '{server_name}' already exists[/yellow]")
                return
            
            # Prompt for configuration if needed
            config = prompt_for_server_configuration(
                server_name=server_name,
                server_type=server_result.server_type,
                package=server_result.package
            )
            
            try:
                # Separate args and env from config
                config = config or {}
                env_vars = {k: v for k, v in config.items() if k != 'args' and isinstance(v, str)}
                additional_args = config.get('args', []) if isinstance(config.get('args'), list) else []
                
                # Convert scope string to enum
                from mcp_manager.core.models import ServerScope
                scope_enum = ServerScope(scope) if scope else ServerScope.USER
                
                # Add server to manager
                server = await manager.add_server(
                    name=server_name,
                    server_type=server_result.server_type,
                    command=server_result.install_command,
                    args=(server_result.install_args or []) + additional_args,
                    env=env_vars,
                    scope=scope_enum
                )
                
                console.print(f"[green]✅ Successfully installed '{server_name}' in {scope} scope[/green]")
                
                # Show server details
                await show_server_details_after_install(manager, server_name)
                
            except Exception as e:
                console.print(f"[red]❌ Installation failed: {e}[/red]")
        
        asyncio.run(find_and_install())
    
    return [discover, install_package, install]