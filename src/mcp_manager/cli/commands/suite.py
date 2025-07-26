"""
Suite management commands for MCP Manager.

Clean, modular CLI architecture where adding new subcommands is trivial.
"""

import asyncio
import click
from rich.console import Console
from rich.prompt import Confirm
from typing import Optional

from mcp_manager.cli.helpers.errors import handle_errors

console = Console()

def create_suite_commands(cli_context):
    """Create the suite command group with all subcommands."""
    
    @click.group("suite")
    def suite():
        """Manage MCP server suites for task-specific configurations."""
        pass

    @suite.command("install")
    @click.argument("suite_name")
    @click.option("--force", "-f", is_flag=True, help="Skip confirmation prompts")
    @click.option("--dry-run", is_flag=True, help="Show what would be installed without installing")
    @handle_errors
    def install(suite_name: str, force: bool, dry_run: bool):
        """Install MCP servers from a suite."""
        
        async def run():
            try:
                from mcp_manager.core.suite_manager import suite_manager
                
                # Check if suite exists
                suite_list = await suite_manager.list_suites()
                target_suite = None
                for suite in suite_list:
                    if suite.name == suite_name or suite.id == suite_name:
                        target_suite = suite
                        break
                
                if not target_suite:
                    console.print(f"[red]❌ Suite '{suite_name}' not found[/red]")
                    console.print("\\n[dim]💡 Available suites:[/dim]")
                    for suite in suite_list:
                        console.print(f"   • [cyan]{suite.id}[/cyan]: {suite.name}")
                    return
                
                # Get suite servers
                memberships = await suite_manager.get_suite_memberships(target_suite.id)
                
                if not memberships:
                    console.print(f"[yellow]⚠️ Suite '{suite_name}' has no servers[/yellow]")
                    return
                
                console.print(f"[blue]📦 Installing suite: {target_suite.name}[/blue]")
                console.print(f"[dim]Servers to install: {len(memberships)}[/dim]\\n")
                
                if dry_run:
                    console.print("[yellow]🔍 DRY RUN - Would install:[/yellow]")
                    for membership in memberships:
                        console.print(f"   • [cyan]{membership.server_name}[/cyan] ({membership.role}, priority: {membership.priority})")
                    return
                
                if not force:
                    if not Confirm.ask(f"Install {len(memberships)} servers from suite '{target_suite.name}'?"):
                        console.print("[yellow]❌ Installation cancelled[/yellow]")
                        return
                
                # Install servers
                manager = cli_context.get_manager()
                installed_count = 0
                failed_count = 0
                
                # Sort by priority (higher priority first)
                sorted_memberships = sorted(memberships, key=lambda x: x.priority, reverse=True)
                
                for membership in sorted_memberships:
                    server_name = membership.server_name
                    try:
                        console.print(f"[blue]📦 Installing: {server_name}[/blue]")
                        
                        # Check if already installed and enabled
                        existing_servers = manager.list_servers_fast()
                        existing_server = next((s for s in existing_servers if s.name == server_name), None)
                        
                        if existing_server and existing_server.enabled:
                            console.print(f"   [green]✅ Already installed and enabled[/green]")
                            installed_count += 1
                            continue
                        
                        # Try to enable if exists but disabled
                        if existing_server and not existing_server.enabled:
                            try:
                                await manager.enable_server(server_name)
                                console.print(f"   [green]✅ Enabled existing server[/green]")
                                installed_count += 1
                                continue
                            except Exception as enable_error:
                                console.print(f"   [yellow]⚠️ Failed to enable, trying discovery: {enable_error}[/yellow]")
                        
                        # Try discovery-based installation
                        discovery = cli_context.get_discovery()
                        results = await discovery.discover_servers(query=server_name, limit=10)
                        
                        # Find best match
                        matching_server = None
                        for result in results:
                            if result.name.lower() == server_name.lower():
                                matching_server = result
                                break
                        
                        if not matching_server and results:
                            for result in results:
                                if server_name.lower() in result.name.lower():
                                    matching_server = result
                                    break
                        
                        if matching_server:
                            install_result = await manager.add_server_from_discovery(matching_server)
                            if install_result:
                                console.print(f"   [green]✅ Installed from discovery[/green]")
                                installed_count += 1
                            else:
                                console.print(f"   [red]❌ Installation failed[/red]")
                                failed_count += 1
                        else:
                            console.print(f"   [red]❌ Server not found in discovery[/red]")
                            failed_count += 1
                            
                    except Exception as e:
                        console.print(f"   [red]❌ Failed: {e}[/red]")
                        failed_count += 1
                
                # Summary
                console.print(f"\\n[blue]📊 Installation Summary:[/blue]")
                console.print(f"   ✅ Installed: {installed_count}")
                if failed_count > 0:
                    console.print(f"   ❌ Failed: {failed_count}")
                
                if installed_count > 0:
                    console.print(f"\\n[green]🎉 Suite '{target_suite.name}' installed successfully![/green]")
                else:
                    console.print(f"\\n[yellow]⚠️ No servers were installed from suite '{target_suite.name}'[/yellow]")
                
            except Exception as e:
                console.print(f"[red]❌ Failed to install suite: {e}[/red]")
        
        asyncio.run(run())

    @suite.command("list")
    @click.option("--category", help="Filter by category")
    @handle_errors
    def list_suites(category: Optional[str]):
        """List all MCP server suites."""
        
        async def run():
            try:
                from mcp_manager.core.suite_manager import suite_manager
                suites = await suite_manager.list_suites()
                
                if category:
                    suites = [s for s in suites if s.category == category]
                
                if not suites:
                    filter_msg = f" in category '{category}'" if category else ""
                    console.print(f"[yellow]No suites found{filter_msg}[/yellow]")
                    return
                
                # Display table
                from rich.table import Table
                table = Table(title=f"MCP Server Suites ({len(suites)} total)")
                table.add_column("Suite ID", style="cyan")
                table.add_column("Name", style="bright_white")
                table.add_column("Category", style="blue")
                table.add_column("Servers", justify="center")
                table.add_column("Description", style="dim")
                
                for suite in suites:
                    memberships = await suite_manager.get_suite_memberships(suite.id)
                    server_count = len(memberships)
                    
                    table.add_row(
                        suite.id,
                        suite.name,
                        suite.category or "general",
                        str(server_count),
                        (suite.description or "No description")[:50] + "..." if len(suite.description or "") > 50 else (suite.description or "No description")
                    )
                
                console.print(table)
                console.print(f"\\n[dim]💡 To install a suite: [cyan]mcp-manager suite install <suite-id>[/cyan][/dim]")
                console.print(f"[dim]💡 To view suite details: [cyan]mcp-manager suite show <suite-id>[/cyan][/dim]")
                
            except Exception as e:
                console.print(f"[red]❌ Failed to list suites: {e}[/red]")
        
        asyncio.run(run())

    @suite.command("show")
    @click.argument("suite_id")
    @handle_errors
    def show(suite_id: str):
        """Show detailed information about a specific suite."""
        
        async def run():
            try:
                from mcp_manager.core.suite_manager import suite_manager
                
                # Get suite
                suite = await suite_manager.get_suite(suite_id)
                if not suite:
                    console.print(f"[red]❌ Suite '{suite_id}' not found[/red]")
                    return
                
                # Get memberships
                memberships = await suite_manager.get_suite_memberships(suite_id)
                
                # Display suite info
                console.print(f"[bold]📦 Suite: {suite.name}[/bold]")
                console.print(f"ID: {suite.id}")
                console.print(f"Category: {suite.category or 'general'}")
                console.print(f"Description: {suite.description or 'No description'}")
                
                if not memberships:
                    console.print("\\n[yellow]⚠️ No servers in this suite[/yellow]")
                    return
                
                # Display servers table
                from rich.table import Table
                table = Table(title=f"🔧 Servers ({len(memberships)}):")
                table.add_column("Server Name", style="cyan")
                table.add_column("Role", style="blue") 
                table.add_column("Priority", justify="center")
                table.add_column("Status", justify="center")
                
                # Check installation status
                manager = cli_context.get_manager()
                existing_servers = manager.list_servers_fast()
                
                for membership in sorted(memberships, key=lambda x: x.priority, reverse=True):
                    existing = next((s for s in existing_servers if s.name == membership.server_name), None)
                    if existing and existing.enabled:
                        status = "[green]✅ Installed[/green]"
                    elif existing:
                        status = "[yellow]⚠️ Disabled[/yellow]"
                    else:
                        status = "[red]❌ Not Installed[/red]"
                    
                    table.add_row(
                        membership.server_name,
                        membership.role,
                        str(membership.priority),
                        status
                    )
                
                console.print(table)
                console.print(f"\\n[dim]💡 To install this suite:[/dim]")
                console.print(f"   [cyan]mcp-manager suite install {suite.id}[/cyan]")
                
            except Exception as e:
                console.print(f"[red]❌ Failed to show suite: {e}[/red]")
        
        asyncio.run(run())

    # Add more subcommands here easily...
    @suite.command("create")
    @click.argument("suite_name")
    @click.option("--description", help="Suite description")
    @click.option("--category", help="Suite category")
    @handle_errors 
    def create(suite_name: str, description: str, category: str):
        """Create a new suite."""
        console.print("[yellow]Create command not implemented yet[/yellow]")

    return suite

# Legacy compatibility - export both old and new interfaces
def suite_commands(cli_context):
    """Legacy interface - returns list for compatibility."""
    return [create_suite_commands(cli_context)]