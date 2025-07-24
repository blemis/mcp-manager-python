"""
Suite management commands for MCP Manager CLI.
"""

import asyncio
from typing import Optional

import click
from rich.console import Console

from mcp_manager.cli.helpers import handle_errors

console = Console()


def suite_commands(cli_context):
    """Add suite commands to the CLI."""
    
    @click.command("install-suite")
    @click.option("--suite-name", "-s", default="test", help="Suite name to install (AI-curated or user-created)")
    @click.option("--force", "-f", is_flag=True, help="Skip confirmation prompts")
    @click.option("--dry-run", is_flag=True, help="Show what would be installed without installing")
    @handle_errors
    def install_suite(suite_name: str, force: bool, dry_run: bool):
        """Install MCP servers tagged with a specific suite name.
        
        Process:
        1. Get suite name from request
        2. Query database/memory for MCPs with that suite tag
        3. Install those MCPs with proper configuration
        """
        
        async def install_suite_async():
            from mcp_manager.utils.logging import get_logger
            logger = get_logger(__name__)
            
            logger.debug(f"[SUITE_INSTALL] Starting installation for suite: {suite_name}")
            
            # Step 1: Get suite name from request
            logger.debug(f"[SUITE_INSTALL] Step 1: Suite name requested: {suite_name}")
            
            # Step 2: Check database for MCPs with this suite tag
            logger.debug(f"[SUITE_INSTALL] Step 2: Querying database for MCPs tagged with '{suite_name}'")
            
            try:
                from mcp_manager.core.suite_manager import suite_manager
                suite = await suite_manager.get_suite(suite_name)
                
                if not suite:
                    logger.debug(f"[SUITE_INSTALL] Suite '{suite_name}' not found in database")
                    console.print(f"[red]❌ Suite '{suite_name}' not found[/red]")
                    console.print(f"[yellow]💡 Available suites:[/yellow]")
                    
                    all_suites = await suite_manager.list_suites()
                    for available_suite in all_suites:
                        console.print(f"   • [cyan]{available_suite.id}[/cyan]: {available_suite.description}")
                    return
                
                logger.debug(f"[SUITE_INSTALL] Found suite: {suite.name} with {len(suite.memberships)} MCPs")
                
                # Step 3: Process those MCPs
                console.print(f"[bold blue]📦 Installing Suite: {suite.name}[/bold blue]")
                console.print(f"Description: {suite.description}")
                console.print(f"MCPs to install: {len(suite.memberships)}")
                
                if dry_run:
                    console.print(f"\n[dim]🔍 Dry run - showing what would be installed:[/dim]")
                    for membership in suite.memberships:
                        console.print(f"   • [cyan]{membership.server_name}[/cyan] (role: {membership.role}, priority: {membership.priority})")
                    return
                
                # Confirmation
                if not force:
                    try:
                        response = input(f"\nInstall {len(suite.memberships)} MCPs from suite '{suite.name}'? [y/N]: ")
                        if response.lower() not in ['y', 'yes']:
                            console.print("[dim]Installation cancelled[/dim]")
                            return
                    except (EOFError, KeyboardInterrupt):
                        console.print("\n[dim]Installation cancelled[/dim]")
                        return
                
                # Step 4: Install each MCP
                manager = cli_context.get_manager()
                installed_count = 0
                failed_count = 0
                
                console.print(f"\n[blue]🚀 Installing MCPs from suite '{suite.name}'...[/blue]")
                
                for membership in sorted(suite.memberships, key=lambda m: m.priority, reverse=True):
                    server_name = membership.server_name
                    logger.debug(f"[SUITE_INSTALL] Step 4: Installing MCP '{server_name}' (priority: {membership.priority})")
                    
                    try:
                        console.print(f"   🔄 Installing [cyan]{server_name}[/cyan]...")
                        
                        # Check if already exists
                        existing_servers = manager.list_servers_fast()
                        if any(s.name == server_name for s in existing_servers):
                            console.print(f"   ⏭️  [yellow]Skipped[/yellow]: {server_name} already exists")
                            continue
                        
                        # Get server configuration from discovery system
                        try:
                            from mcp_manager.core.discovery.server_discovery import ServerDiscovery
                            from mcp_manager.core.models import ServerType
                            from mcp_manager.core.exceptions import MCPManagerError
                            
                            discovery = ServerDiscovery()
                            
                            # Search for the server by name
                            logger.debug(f"[SUITE_INSTALL] Searching for server: {server_name}")
                            discovery_results = await discovery.discover_servers(query=server_name, limit=10)
                            
                            # Find best match
                            best_match = None
                            for result in discovery_results:
                                if result.name.lower() == server_name.lower() or server_name.lower() in result.name.lower():
                                    best_match = result
                                    break
                            
                            if not best_match:
                                console.print(f"   ❌ [red]Failed[/red]: Server '{server_name}' not found in registry")
                                logger.warning(f"[SUITE_INSTALL] Server '{server_name}' not found in discovery results")
                                failed_count += 1
                                continue
                                
                            logger.debug(f"[SUITE_INSTALL] Found server: {best_match.name} (package: {best_match.package})")
                            
                            # Convert discovery result to server and add it
                            server = best_match.to_server()
                            
                            # Add server using the manager
                            success = await manager.add_server(
                                name=server.name,
                                server_type=server.server_type,
                                command=server.command,
                                description=server.description,
                                args=server.args,
                                env=server.env
                            )
                            
                            if success:
                                console.print(f"   ✅ [green]Installed[/green]: {server_name}")
                                installed_count += 1
                                logger.info(f"[SUITE_INSTALL] Successfully installed: {server_name}")
                            else:
                                console.print(f"   ❌ [red]Failed[/red]: Could not add server '{server_name}'")
                                failed_count += 1
                                logger.error(f"[SUITE_INSTALL] Failed to add server: {server_name}")
                                
                        except Exception as discovery_error:
                            console.print(f"   ❌ [red]Failed[/red]: Discovery error for '{server_name}': {discovery_error}")
                            logger.error(f"[SUITE_INSTALL] Discovery error for {server_name}: {discovery_error}")
                            failed_count += 1
                        
                    except Exception as e:
                        logger.error(f"[SUITE_INSTALL] Failed to install {server_name}: {e}")
                        console.print(f"   ❌ [red]Failed[/red]: {server_name} - {e}")
                        failed_count += 1
                
                logger.debug(f"[SUITE_INSTALL] Installation complete: {installed_count} installed, {failed_count} failed")
                console.print(f"\n🎯 [green]Suite Installation Complete![/green]")
                console.print(f"   ✅ Installed: {installed_count}")
                console.print(f"   ❌ Failed: {failed_count}")
                
            except Exception as e:
                logger.error(f"[SUITE_INSTALL] Suite installation failed: {e}")
                console.print(f"[red]❌ Failed to install suite: {e}[/red]")
        
        asyncio.run(install_suite_async())
    
    
    @click.group("suite")
    def suite():
        """Manage MCP server suites for task-specific configurations."""
        pass
    
    
    @suite.command("list")
    @click.option("--category", help="Filter by category")
    @handle_errors
    def suite_list(category: Optional[str]):
        """List all MCP server suites."""
        
        async def list_suites():
            try:
                from mcp_manager.core.suite_manager import suite_manager
                suites = await suite_manager.list_suites(category)
                
                if not suites:
                    if category:
                        console.print(f"[yellow]No suites found in category '{category}'[/yellow]")
                    else:
                        console.print("[yellow]No suites configured[/yellow]")
                        console.print("[dim]💡 Create your first suite with:[/dim]")
                        console.print("[dim]   [cyan]mcp-manager suite create my-suite --description 'My custom suite'[/cyan][/dim]")
                    return
                
                from rich.table import Table
                
                table = Table(
                    title=f"MCP Server Suites ({len(suites)} total)",
                    show_header=True,
                    header_style="bold cyan",
                    title_style="bold cyan",
                    show_lines=True
                )
                
                table.add_column("Suite ID", style="green", width=20)
                table.add_column("Name", style="bold white", width=25) 
                table.add_column("Category", style="blue", width=15)
                table.add_column("Servers", style="yellow", width=8)
                table.add_column("Description", style="dim", width=40)
                
                for suite in suites:
                    server_count = len(suite.memberships) if hasattr(suite, 'memberships') else 0
                    table.add_row(
                        suite.id,
                        suite.name,
                        suite.category or "general",
                        str(server_count),
                        (suite.description[:37] + "...") if suite.description and len(suite.description) > 40 else (suite.description or "")
                    )
                
                console.print("")
                console.print(table)
                console.print("")
                console.print("[dim]💡 To install a suite: [cyan]mcp-manager install-suite --suite-name <suite-id>[/cyan][/dim]")
                console.print("[dim]💡 To view suite details: [cyan]mcp-manager suite show <suite-id>[/cyan][/dim]")
                
            except Exception as e:
                console.print(f"[red]Failed to list suites: {e}[/red]")
        
        asyncio.run(list_suites())
    
    
    @suite.command("create")
    @click.argument("name")
    @click.option("--description", help="Suite description")
    @click.option("--category", help="Suite category")
    @click.option("--suite-id", help="Custom suite ID (auto-generated if not provided)")
    @handle_errors
    def suite_create(name: str, description: Optional[str], category: Optional[str], suite_id: Optional[str]):
        """Create a new MCP server suite."""
        
        async def create_suite():
            try:
                from mcp_manager.core.suite_manager import suite_manager
                
                # Generate ID if not provided
                if not suite_id:
                    import re
                    generated_id = re.sub(r'[^a-zA-Z0-9-]', '-', name.lower())
                    generated_id = re.sub(r'-+', '-', generated_id).strip('-')
                else:
                    generated_id = suite_id
                
                console.print(f"[blue]Creating suite '{name}' with ID '{generated_id}'...[/blue]")
                
                # Create the suite
                success = await suite_manager.create_or_update_suite(
                    suite_id=generated_id,
                    name=name,
                    description=description or f"Custom suite: {name}",
                    category=category or "custom"
                )
                
                if success:
                    console.print(f"[green]✅ Suite '{name}' created successfully![/green]")
                    console.print(f"[dim]Suite ID: {generated_id}[/dim]")
                    console.print(f"\n[dim]💡 Add servers to this suite with:[/dim]")
                    console.print(f"[dim]   [cyan]mcp-manager suite add {generated_id} <server-name> --role member --priority 50[/cyan][/dim]")
                else:
                    console.print(f"[red]❌ Failed to create suite[/red]")
                
            except Exception as e:
                console.print(f"[red]Failed to create suite: {e}[/red]")
        
        asyncio.run(create_suite())
    
    
    @suite.command("add")
    @click.argument("suite_id")
    @click.argument("server_name")
    @click.option("--role", default="member", help="Server role in suite (member, primary, optional)")
    @click.option("--priority", type=int, default=50, help="Priority (0-100, higher = more important)")
    @handle_errors
    def suite_add(suite_id: str, server_name: str, role: str, priority: int):
        """Add a server to a suite."""
        
        async def add_to_suite():
            try:
                from mcp_manager.core.suite_manager import suite_manager
                
                console.print(f"[blue]Adding {server_name} to suite {suite_id} as {role}...[/blue]")
                
                success = await suite_manager.add_server_to_suite(
                    suite_id=suite_id,
                    server_name=server_name,
                    role=role,
                    priority=priority
                )
                
                if success:
                    console.print(f"[green]✅ Added {server_name} to suite {suite_id}[/green]")
                else:
                    console.print(f"[red]❌ Failed to add server to suite[/red]")
                
            except Exception as e:
                console.print(f"[red]Failed to add server to suite: {e}[/red]")
        
        asyncio.run(add_to_suite())
    
    
    @suite.command("remove")
    @click.argument("suite_id")
    @click.argument("server_name")
    @handle_errors
    def suite_remove_server(suite_id: str, server_name: str):
        """Remove a server from a suite."""
        
        async def remove_from_suite():
            try:
                from mcp_manager.core.suite_manager import suite_manager
                
                console.print(f"[blue]Removing {server_name} from suite {suite_id}...[/blue]")
                
                success = await suite_manager.remove_server_from_suite(
                    suite_id=suite_id,
                    server_name=server_name
                )
                
                if success:
                    console.print(f"[green]✅ Removed {server_name} from suite {suite_id}[/green]")
                else:
                    console.print(f"[red]❌ Failed to remove server from suite[/red]")
                
            except Exception as e:
                console.print(f"[red]Failed to remove server from suite: {e}[/red]")
        
        asyncio.run(remove_from_suite())
    
    
    @suite.command("delete")
    @click.argument("suite_id")
    @click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
    @handle_errors
    def suite_delete(suite_id: str, force: bool):
        """Delete a suite and all its memberships."""
        
        async def delete_suite():
            try:
                from mcp_manager.core.suite_manager import suite_manager
                
                # Get suite info first
                suite = await suite_manager.get_suite(suite_id)
                if not suite:
                    console.print(f"[red]❌ Suite '{suite_id}' not found[/red]")
                    return
                
                if not force:
                    from rich.prompt import Confirm
                    server_count = len(suite.memberships) if hasattr(suite, 'memberships') else 0
                    if not Confirm.ask(f"Delete suite '{suite.name}' with {server_count} servers?"):
                        console.print("[dim]Deletion cancelled[/dim]")
                        return
                
                console.print(f"[blue]Deleting suite '{suite.name}'...[/blue]")
                
                success = await suite_manager.delete_suite(suite_id)
                
                if success:
                    console.print(f"[green]✅ Suite '{suite.name}' deleted successfully[/green]")
                else:
                    console.print(f"[red]❌ Failed to delete suite[/red]")
                
            except Exception as e:
                console.print(f"[red]Failed to delete suite: {e}[/red]")
        
        asyncio.run(delete_suite())
    
    
    @suite.command("show")
    @click.argument("suite_id")
    @handle_errors
    def suite_show(suite_id: str):
        """Show detailed information about a specific suite."""
        
        async def show_suite():
            try:
                from mcp_manager.core.suite_manager import suite_manager
                
                suite = await suite_manager.get_suite(suite_id)
                
                if not suite:
                    console.print(f"[red]❌ Suite '{suite_id}' not found[/red]")
                    console.print(f"[yellow]💡 Available suites:[/yellow]")
                    
                    all_suites = await suite_manager.list_suites()
                    for available_suite in all_suites:
                        console.print(f"   • [cyan]{available_suite.id}[/cyan]: {available_suite.name}")
                    return
                
                # Display suite header
                console.print(f"[bold blue]📦 Suite: {suite.name}[/bold blue]")
                console.print(f"[dim]ID: {suite.id}[/dim]")
                console.print(f"[dim]Category: {suite.category}[/dim]")
                console.print(f"Description: {suite.description}")
                
                # Display members
                if suite.memberships:
                    console.print(f"\n[bold cyan]🔧 Servers ({len(suite.memberships)}):[/bold cyan]")
                    
                    from rich.table import Table
                    
                    table = Table(show_header=True, header_style="bold cyan")
                    table.add_column("Server Name", style="green", width=25)
                    table.add_column("Role", style="yellow", width=12)
                    table.add_column("Priority", style="blue", width=10)
                    table.add_column("Status", style="white", width=12)
                    
                    # Sort by priority (highest first)
                    sorted_memberships = sorted(suite.memberships, key=lambda m: m.priority, reverse=True)
                    
                    for membership in sorted_memberships:
                        # Check if server exists
                        try:
                            manager = cli_context.get_manager()
                            existing_servers = manager.list_servers_fast()
                            server_exists = any(s.name == membership.server_name for s in existing_servers)
                            status = "[green]✅ Installed[/green]" if server_exists else "[dim]❌ Not Installed[/dim]"
                        except:
                            status = "[dim]❓ Unknown[/dim]"
                        
                        table.add_row(
                            membership.server_name,
                            membership.role,
                            str(membership.priority),
                            status
                        )
                    
                    console.print(table)
                    
                    # Installation info
                    console.print(f"\n[dim]💡 To install this suite:[/dim]")
                    console.print(f"[dim]   [cyan]mcp-manager install-suite --suite-name {suite_id}[/cyan][/dim]")
                else:
                    console.print(f"\n[yellow]📭 This suite has no servers yet[/yellow]")
                    console.print(f"[dim]💡 Add servers with:[/dim]")
                    console.print(f"[dim]   [cyan]mcp-manager suite add {suite_id} <server-name> --role member --priority 50[/cyan][/dim]")
                
            except Exception as e:
                console.print(f"[red]Failed to show suite details: {e}[/red]")
        
        asyncio.run(show_suite())
    
    
    @suite.command("summary")
    @handle_errors
    def suite_summary():
        """Show summary statistics about suites."""
        
        async def show_summary():
            try:
                from mcp_manager.core.suite_manager import suite_manager
                
                summary = await suite_manager.get_suite_summary()
                
                console.print("[bold blue]📊 Suite Summary[/bold blue]")
                console.print(f"Total Suites: [cyan]{summary.get('total_suites', 0)}[/cyan]")
                console.print(f"Total Server Memberships: [cyan]{summary.get('total_memberships', 0)}[/cyan]")
                console.print(f"Active Suites: [cyan]{summary.get('active_suites', 0)}[/cyan]")
                
                categories = summary.get('categories', {})
                if categories:
                    console.print(f"\n[bold cyan]By Category:[/bold cyan]")
                    for category, count in categories.items():
                        console.print(f"  • {category}: [yellow]{count}[/yellow] suites")
                
                popular_servers = summary.get('popular_servers', [])
                if popular_servers:
                    console.print(f"\n[bold cyan]Most Used Servers:[/bold cyan]")
                    for server_info in popular_servers[:5]:
                        server_name = server_info.get('server_name', 'Unknown')
                        usage_count = server_info.get('usage_count', 0)
                        console.print(f"  • [green]{server_name}[/green]: used in [yellow]{usage_count}[/yellow] suites")
                
            except Exception as e:
                console.print(f"[red]Failed to get suite summary: {e}[/red]")
        
        asyncio.run(show_summary())
    
    return [install_suite, suite]