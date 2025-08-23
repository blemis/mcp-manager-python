"""
Discovery and installation commands for MCP Manager CLI.
"""

import asyncio
import sys
from typing import Optional

import click
from rich.console import Console

from mcp_manager.core.models import ServerType
from mcp_manager.cli.helpers import (
    handle_errors, generate_install_id, prompt_for_server_configuration,
    show_server_details_after_install, show_discovery_for_next_install
)

console = Console()


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
        
        # Display results in a table
        scope_title = f" for {scope} scope" if scope else ""
        table = Table(
            title=f"Discovered MCP Servers ({len(results)} results{scope_title})",
            show_header=True,
            header_style="bold cyan",
            title_style="bold cyan",
            show_lines=True
        )
        
        table.add_column("Install ID", style="green", width=25)
        table.add_column("Type", style="blue", width=8)
        table.add_column("Name/Package", style="white", width=30)
        table.add_column("Description", style="dim", width=50)
        
        for result in results:
            install_id = generate_install_id(result)
            
            table.add_row(
                install_id,
                result.server_type.value,
                result.package or result.name,
                (result.description[:47] + "...") if result.description and len(result.description) > 50 else (result.description or "")
            )
        
        console.print("")
        console.print(table)
        console.print("")
        console.print("[dim]💡 To install a server, use:[/dim]")
        scope_flag = f" --scope {scope}" if scope else ""
        console.print(f"[dim]   [cyan]mcp-manager install-package <install-id>{scope_flag}[/cyan][/dim]")
        console.print(f"[dim]   Example: [cyan]mcp-manager install-package modelcontextprotocol-filesystem{scope_flag}[/cyan][/dim]")
    
    
    @click.command("install-package")
    @click.argument("install_id")
    @click.option("--scope", type=click.Choice(['local', 'project', 'user'], case_sensitive=False), default="user", help="Installation scope")
    @handle_errors
    def install_package(install_id: str, scope: str):
        """Install a server using its unique install ID from discovery."""
        discovery = cli_context.get_discovery()
        
        async def find_and_install():
            console.print(f"[blue]🔍 Searching for server with ID: {install_id}[/blue]")
            
            # Try multiple search strategies
            search_strategies = []
            
            # Strategy 1: Reverse-engineer package name from install_id 
            if not install_id.startswith("dd-") and "-" in install_id:
                # For NPM packages like browsermcp-mcp -> @browsermcp/mcp
                parts = install_id.split("-", 1)
                if len(parts) == 2:
                    possible_package = f"@{parts[0]}/{parts[1]}"
                    search_strategies.append(("package name", possible_package))
            
            # Strategy 2: Direct install_id search
            search_strategies.append(("install_id", install_id))
            
            # Strategy 3: Broader search
            search_strategies.append(("broad search", None))
            
            # Strategy 4: Fallback searches
            if "modelcontextprotocol" in install_id:
                search_strategies.append(("fallback", install_id.replace("modelcontextprotocol-", "")))
            elif install_id.startswith("dd-"):
                search_strategies.append(("fallback", install_id.replace("dd-", "")))
            elif "-" in install_id:
                search_strategies.append(("fallback", install_id.replace("-", " ")))
            
            results = []
            for strategy_name, query in search_strategies:
                try:
                    strategy_results = await discovery.discover_servers(query=query, limit=100)
                    if strategy_results:
                        results = strategy_results
                        break
                except Exception as e:
                    continue
            
            if not results:
                console.print("[red]No results found with any search strategy[/red]")
                sys.exit(1)
            
            
            # Find exact match by install ID
            matching_server = None
            for result in results:
                result_id = generate_install_id(result)
                if result_id == install_id:
                    matching_server = result
                    break
            
            if not matching_server:
                console.print(f"[red]❌ Server with install ID '{install_id}' not found[/red]")
                console.print(f"[yellow]💡 Try running 'mcp-manager discover' to see available servers[/yellow]")
                
                # Show similar results
                similar_results = [r for r in results if install_id.lower() in generate_install_id(r).lower()]
                if similar_results:
                    console.print(f"\n[dim]🔍 Did you mean one of these?[/dim]")
                    for result in similar_results[:3]:
                        similar_id = generate_install_id(result)
                        console.print(f"   • [cyan]{similar_id}[/cyan]: {result.description or 'No description'}")
                sys.exit(1)
            
            # Get manager and install
            manager = cli_context.get_manager()
            # Use install_id as server name to avoid conflicts with discovery result names
            server_name = install_id
            
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