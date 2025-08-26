"""
Suite management commands for MCP Manager CLI.
"""

import asyncio
from typing import Optional

import click
from rich.console import Console

from mcp_manager.cli.helpers import handle_errors, generate_install_id
from mcp_manager.core.models import ServerScope, ServerType

console = Console()


def suite_commands(cli_context):
    """Add suite commands to the CLI."""
    
    
    @click.group("suite")
    def suite():
        """Manage MCP server suites for task-specific configurations."""
        pass
    
    
    @suite.command("install")
    @click.argument("suite_name") 
    @click.option("--force", "-f", is_flag=True, help="Skip confirmation prompts")
    @click.option("--dry-run", is_flag=True, help="Show what would be installed without installing")
    @handle_errors
    def suite_install(suite_name: str, force: bool, dry_run: bool):
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
                console.print(f"Expanded Server Count: [cyan]{summary.get('expanded_server_count', 0)}[/cyan] [dim](Docker Desktop servers counted individually)[/dim]")
                console.print(f"Active Suites: [cyan]{summary.get('active_suites', 0)}[/cyan]")
                
                console.print(f"\n[bold cyan]By Category:[/bold cyan]")
                categories = summary.get('categories', {})
                if categories:
                    for category, count in categories.items():
                        console.print(f"  • {category}: [yellow]{count}[/yellow] suites")
                else:
                    console.print("  • [dim]No categories configured[/dim]")
                
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
    
    
    @suite.command("remove-suite")
    @click.argument("suite_id")
    @click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
    @handle_errors
    def suite_remove_suite(suite_id: str, force: bool):
        """Remove all servers from a suite while keeping the suite definition."""
        
        async def remove_suite_servers():
            try:
                from mcp_manager.core.suite_manager import suite_manager
                
                # Get suite info first
                suite = await suite_manager.get_suite(suite_id)
                if not suite:
                    console.print(f"[red]❌ Suite '{suite_id}' not found[/red]")
                    console.print(f"[yellow]💡 Available suites:[/yellow]")
                    
                    all_suites = await suite_manager.list_suites()
                    for available_suite in all_suites:
                        console.print(f"   • [cyan]{available_suite.id}[/cyan]: {available_suite.name}")
                    return
                
                if not suite.memberships:
                    console.print(f"[yellow]📭 Suite '{suite.name}' has no servers to remove[/yellow]")
                    return
                
                server_count = len(suite.memberships)
                console.print(f"[blue]📦 Suite: {suite.name}[/blue]")
                console.print(f"Servers to remove: {server_count}")
                
                # Show servers that will be removed
                console.print(f"\\n[dim]🔍 Servers that will be removed from Claude Code:[/dim]")
                for membership in sorted(suite.memberships, key=lambda m: m.priority, reverse=True):
                    console.print(f"   • [cyan]{membership.server_name}[/cyan] (role: {membership.role}, priority: {membership.priority})")
                
                # Confirmation
                if not force:
                    try:
                        response = input(f"\\nRemove {server_count} servers from Claude Code? The suite definition will remain intact. [y/N]: ")
                        if response.lower() not in ['y', 'yes']:
                            console.print("[dim]Removal cancelled[/dim]")
                            return
                    except (EOFError, KeyboardInterrupt):
                        console.print("\\n[dim]Removal cancelled[/dim]")
                        return
                
                # Remove each server from Claude Code
                manager = cli_context.get_manager()
                removed_count = 0
                failed_count = 0
                
                console.print(f"\\n[blue]🚀 Removing servers from Claude Code...[/blue]")
                
                for membership in sorted(suite.memberships, key=lambda m: m.priority, reverse=True):
                    server_name = membership.server_name
                    
                    try:
                        console.print(f"   🔄 Removing [cyan]{server_name}[/cyan]...")
                        
                        # Check if server exists in Claude Code
                        existing_servers = await manager.list_servers()
                        server_exists = any(s.name == server_name for s in existing_servers)
                        
                        if not server_exists:
                            console.print(f"   ⏭️  [yellow]Skipped[/yellow]: {server_name} not found in Claude Code")
                            continue
                        
                        # Remove server from Claude Code
                        from mcp_manager.core.models import ServerScope, ServerType
                        success = await manager.remove_server(server_name, ServerScope.USER)
                        
                        if success:
                            console.print(f"   ✅ [green]Removed[/green]: {server_name}")
                            removed_count += 1
                        else:
                            console.print(f"   ❌ [red]Failed[/red]: Could not remove server '{server_name}'")
                            failed_count += 1
                                
                    except Exception as e:
                        console.print(f"   ❌ [red]Failed[/red]: {server_name} - {e}")
                        failed_count += 1
                
                console.print(f"\\n🎯 [green]Suite Server Removal Complete![/green]")
                console.print(f"   ✅ Removed: {removed_count}")
                console.print(f"   ❌ Failed: {failed_count}")
                console.print(f"\\n[dim]💡 Suite definition '{suite.name}' remains intact for future reinstallation[/dim]")
                console.print(f"[dim]💡 To reinstall: [cyan]mcp-manager install-suite --suite-name {suite_id}[/cyan][/dim]")
                
            except Exception as e:
                console.print(f"[red]❌ Failed to remove suite servers: {e}[/red]")
        
        asyncio.run(remove_suite_servers())
    
    
    @suite.command("enable")
    @click.argument("suite_name")
    @click.option("--dry-run", is_flag=True, help="Show what would be changed without making changes")
    @handle_errors
    def suite_enable(suite_name: str, dry_run: bool):
        """Enable all servers in the specified suite (additive - leaves other servers unchanged). Use 'all' to enable all servers."""
        
        async def enable_suite_async():
            try:
                manager, context = cli_context.auto_sync_and_get_manager(silent=True)
                console.print(f"[dim]Suite enable in: {context.description}[/dim]")
                
                if dry_run:
                    console.print("[yellow]🔍 DRY RUN MODE - No changes will be made[/yellow]")
                    console.print("")
                
                # Handle 'all' case - enable all servers
                if suite_name.lower() == "all":
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
                        else:
                            console.print("")
                            console.print("[dim]All servers are already enabled[/dim]")
                    else:
                        console.print("")
                        console.print("[dim]Dry run complete - no changes made[/dim]")
                    return
                
                console.print(f"[blue]🎯 Enabling suite: {suite_name}[/blue]")
                console.print("[dim]This will install missing servers and enable all servers in this suite[/dim]")
                console.print("")
                
                # Get suite definition and all servers in the suite
                from mcp_manager.core.suites.database import SuiteDatabase
                from mcp_manager.core.suites.membership import MembershipManager
                
                suite_db = SuiteDatabase()
                membership_mgr = MembershipManager(suite_db)
                
                # Get all servers defined in this suite (whether installed or not)
                try:
                    suite_members = await membership_mgr.get_suite_servers(suite_name)
                    if not suite_members:
                        console.print(f"[red]❌ No servers found in suite: {suite_name}[/red]")
                        console.print("[yellow]💡 Use 'mcp-manager suite list' to see available suites[/yellow]")
                        return
                except Exception as e:
                    console.print(f"[red]❌ Failed to get suite members: {e}[/red]")
                    return
                
                # Get all currently installed servers
                all_installed_servers = await manager.list_servers()
                installed_server_names = {server.name for server in all_installed_servers}
                
                # Categorize suite servers: installed vs need installation
                servers_to_install = []
                servers_to_enable = []
                servers_already_enabled = []
                
                for suite_member in suite_members:
                    server_name = suite_member[2]  # Assuming format is (suite_id, suite_name, server_name)
                    
                    if server_name in installed_server_names:
                        # Server is installed - check if enabled
                        installed_server = next(s for s in all_installed_servers if s.name == server_name)
                        if installed_server.enabled:
                            servers_already_enabled.append(installed_server)
                        else:
                            servers_to_enable.append(installed_server)
                    else:
                        # Server needs installation
                        servers_to_install.append(server_name)
                
                # Show what will happen
                if servers_to_install:
                    console.print(f"[blue]📦 Servers to INSTALL ({len(servers_to_install)}):[/blue]")
                    for server_name in servers_to_install:
                        console.print(f"  📥 {server_name} (needs installation)")
                    console.print("")
                
                if servers_to_enable:
                    console.print(f"[green]📦 Servers to ENABLE ({len(servers_to_enable)}):[/green]")
                    for server in servers_to_enable:
                        console.print(f"  ✅ {server.name} (will enable)")
                    console.print("")
                
                if servers_already_enabled:
                    console.print(f"[dim]📦 Already enabled ({len(servers_already_enabled)}):[/dim]")
                    for server in servers_already_enabled:
                        console.print(f"  ➡️ {server.name} (already enabled)")
                    console.print("")
                
                total_suite_servers = len(servers_to_install) + len(servers_to_enable) + len(servers_already_enabled)
                if total_suite_servers == 0:
                    console.print(f"[red]❌ No servers found in suite: {suite_name}[/red]")
                    return
                
                if not dry_run:
                    console.print("")
                    from rich.prompt import Confirm
                    
                    actions_needed = len(servers_to_install) + len(servers_to_enable)
                    if actions_needed > 0:
                        action_summary = []
                        if servers_to_install:
                            action_summary.append(f"install {len(servers_to_install)}")
                        if servers_to_enable:
                            action_summary.append(f"enable {len(servers_to_enable)}")
                        
                        confirm_msg = f"[bold]{' and '.join(action_summary)} servers for suite '{suite_name}'?[/bold]"
                    else:
                        confirm_msg = f"[bold]Suite '{suite_name}' is already fully enabled. Continue anyway?[/bold]"
                        
                    if not Confirm.ask(confirm_msg):
                        console.print("[dim]Suite enable cancelled[/dim]")
                        return
                    
                    console.print("")
                    console.print("[blue]🔄 Processing suite servers...[/blue]")
                    
                    installed_count = 0
                    enabled_count = 0
                    
                    # Step 1: Install missing servers
                    if servers_to_install:
                        console.print("[blue]📥 Installing missing servers...[/blue]")
                        for server_name in servers_to_install:
                            try:
                                # Special handling for Docker Desktop servers
                                if server_name.startswith('dd-'):
                                    # Extract the Docker Desktop server name
                                    dd_server_name = server_name.replace('dd-', '')
                                    
                                    # For Docker Desktop servers, we need to add them directly
                                    success = await manager.add_server(
                                        name=server_name,
                                        server_type=ServerType.DOCKER_DESKTOP,
                                        command="/opt/homebrew/bin/docker",
                                        args=["mcp", "gateway", "run", "--servers", dd_server_name],
                                        env={},
                                        scope=ServerScope.USER
                                    )
                                    if success:
                                        installed_count += 1
                                        console.print(f"  [green]✅ Installed: {server_name}[/green]")
                                    else:
                                        console.print(f"  [red]❌ Failed to install: {server_name}[/red]")
                                else:
                                    # Try to discover and install the server
                                    discovery = cli_context.get_discovery()
                                    results = await discovery.discover_servers(query=server_name, limit=5)
                                    
                                    # Find exact match
                                    exact_match = next((r for r in results if r.name == server_name or 
                                                      generate_install_id(r) == server_name), None)
                                    
                                    if exact_match:
                                        # Install the server
                                        install_name = generate_install_id(exact_match)
                                        success = await manager.add_server(
                                            name=install_name,
                                            server_type=exact_match.server_type,
                                            command=exact_match.install_command,
                                            args=exact_match.install_args or [],
                                            env={},
                                            scope=ServerScope.USER
                                        )
                                        if success:
                                            installed_count += 1
                                            console.print(f"  [green]✅ Installed: {server_name}[/green]")
                                        else:
                                            console.print(f"  [red]❌ Failed to install: {server_name}[/red]")
                                    else:
                                        console.print(f"  [yellow]⚠️ Server not found in discovery: {server_name}[/yellow]")
                            except Exception as e:
                                console.print(f"  [red]❌ Error installing {server_name}: {e}[/red]")
                    
                    # Step 2: Enable servers (including newly installed ones)
                    if servers_to_enable or installed_count > 0:
                        console.print("[blue]🔄 Enabling servers...[/blue]")
                        
                        # Refresh server list to include newly installed servers
                        updated_servers = await manager.list_servers()
                        
                        for server_name in [s.name for s in servers_to_enable] + servers_to_install:
                            server_to_enable = next((s for s in updated_servers if s.name == server_name), None)
                            if server_to_enable and not server_to_enable.enabled:
                                try:
                                    success = await manager.enable_server(server_to_enable.name)
                                    if success:
                                        enabled_count += 1
                                        console.print(f"  [green]✅ Enabled: {server_to_enable.name}[/green]")
                                    else:
                                        console.print(f"  [red]❌ Failed to enable: {server_to_enable.name}[/red]")
                                except Exception as e:
                                    console.print(f"  [red]❌ Error enabling {server_to_enable.name}: {e}[/red]")
                    
                    console.print("")
                    if installed_count > 0 or enabled_count > 0:
                        console.print(f"[bold green]🎯 Suite '{suite_name}' activated successfully![/bold green]")
                        summary_parts = []
                        if installed_count > 0:
                            summary_parts.append(f"installed {installed_count}")
                        if enabled_count > 0:
                            summary_parts.append(f"enabled {enabled_count}")
                        console.print(f"[dim]{' and '.join(summary_parts)} servers[/dim]")
                    else:
                        console.print(f"[bold green]🎯 Suite '{suite_name}' already fully active![/bold green]")
                        console.print(f"[dim]All servers in suite were already installed and enabled[/dim]")
                else:
                    console.print("")
                    console.print("[dim]Dry run complete - no changes made[/dim]")
                    
            except Exception as e:
                console.print(f"[red]Failed to enable suite: {e}[/red]")
                import sys
                sys.exit(1)
        
        asyncio.run(enable_suite_async())

    
    @suite.command("disable")
    @click.argument("suite_name")
    @click.option("--dry-run", is_flag=True, help="Show what would be changed without making changes")
    @handle_errors
    def suite_disable(suite_name: str, dry_run: bool):
        """Disable servers in the specified suite, leave others unchanged. Use 'all' to disable all servers."""
        
        async def disable_suite_async():
            try:
                manager, context = cli_context.auto_sync_and_get_manager(silent=True)
                console.print(f"[dim]Suite disable in: {context.description}[/dim]")
                
                if dry_run:
                    console.print("[yellow]🔍 DRY RUN MODE - No changes will be made[/yellow]")
                    console.print("")
                
                # Handle 'all' case - disable all servers
                if suite_name.lower() == "all":
                    console.print("[blue]🎯 Disabling ALL servers[/blue]")
                    console.print("")
                    
                    # Get all servers
                    all_servers = await manager.list_servers()
                    
                    if not all_servers:
                        console.print("[yellow]📭 No servers found to disable[/yellow]")
                        return
                    
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
                        else:
                            console.print("")
                            console.print("[dim]All servers are already disabled[/dim]")
                    else:
                        console.print("")
                        console.print("[dim]Dry run complete - no changes made[/dim]")
                    return
                
                console.print(f"[blue]🎯 Disabling suite: {suite_name}[/blue]")
                console.print("[dim]This will disable ONLY servers in this suite, others remain unchanged[/dim]")
                console.print("")
                
                # Get all servers
                all_servers = await manager.list_servers()
                
                # Get suite membership for all servers
                from mcp_manager.core.suites.database import SuiteDatabase
                from mcp_manager.core.suites.membership import MembershipManager
                
                suite_db = SuiteDatabase()
                membership_mgr = MembershipManager(suite_db)
                
                # Find servers in the target suite
                suite_servers = []
                other_servers = []
                
                for server in all_servers:
                    try:
                        suites = await membership_mgr.get_server_suites(server.name)
                        server_suite_names = [suite[1] for suite in suites]  # suite[1] is the name
                        
                        # Check if server is in target suite
                        if suite_name in server_suite_names:
                            suite_servers.append(server)
                        else:
                            other_servers.append(server)
                    except Exception:
                        # If can't get suite info, treat as other server
                        other_servers.append(server)
                
                if not suite_servers:
                    console.print(f"[red]❌ No servers found in suite: {suite_name}[/red]")
                    console.print("[yellow]💡 Use 'mcp-manager suite list' to see available suites[/yellow]")
                    return
                
                console.print(f"[red]📦 Servers to DISABLE ({len(suite_servers)}):[/red]")
                for server in suite_servers:
                    status = "already disabled" if not server.enabled else "will disable"
                    console.print(f"  ❌ {server.name} ({status})")
                
                console.print("")
                console.print(f"[dim]📦 Servers UNCHANGED ({len(other_servers)}):[/dim]")
                for server in other_servers:
                    status = "enabled" if server.enabled else "disabled"
                    console.print(f"  ➖ {server.name} (stays {status})")
                
                if not dry_run:
                    console.print("")
                    from rich.prompt import Confirm
                    if not Confirm.ask(f"[bold]Proceed with disabling suite '{suite_name}'?[/bold]"):
                        console.print("[dim]Suite disable cancelled[/dim]")
                        return
                    
                    console.print("")
                    console.print("[blue]🔄 Applying changes...[/blue]")
                    
                    # Disable suite servers only
                    disabled_count = 0
                    for server in suite_servers:
                        if server.enabled:
                            success = await manager.disable_server(server.name)
                            if success:
                                disabled_count += 1
                                console.print(f"  [yellow]❌ Disabled: {server.name}[/yellow]")
                            else:
                                console.print(f"  [red]❌ Failed to disable: {server.name}[/red]")
                    
                    console.print("")
                    console.print(f"[bold green]🎯 Suite '{suite_name}' disabled successfully![/bold green]")
                    console.print(f"[dim]Disabled {disabled_count} servers[/dim]")
                else:
                    console.print("")
                    console.print("[dim]Dry run complete - no changes made[/dim]")
                    
            except Exception as e:
                console.print(f"[red]Failed to disable suite: {e}[/red]")
                import sys
                sys.exit(1)
        
        asyncio.run(disable_suite_async())

    
    @suite.command("activate")
    @click.argument("suite_names", nargs=-1, required=True)
    @click.option("--dry-run", is_flag=True, help="Show what would be changed without making changes")
    @click.option("--include-individual", is_flag=True, help="Also keep individual servers (not in any suite) enabled")
    @handle_errors
    def suite_activate(suite_names: tuple, dry_run: bool, include_individual: bool):
        """Activate ONLY servers in the specified suites, disable all others."""
        
        async def activate_suites_async():
            try:
                manager, context = cli_context.auto_sync_and_get_manager(silent=True)
                console.print(f"[dim]Suite activation in: {context.description}[/dim]")
                
                if dry_run:
                    console.print("[yellow]🔍 DRY RUN MODE - No changes will be made[/yellow]")
                    console.print("")
                
                suite_list = ", ".join(suite_names)
                console.print(f"[blue]🎯 Activating suites: {suite_list}[/blue]")
                console.print("[dim]This will enable ONLY servers in these suites and disable all others[/dim]")
                if include_individual:
                    console.print("[dim](Individual servers not in any suite will also be kept enabled)[/dim]")
                console.print("")
                
                # Get all servers
                all_servers = await manager.list_servers()
                
                # Get suite membership for all servers
                from mcp_manager.core.suites.database import SuiteDatabase
                from mcp_manager.core.suites.membership import MembershipManager
                
                suite_db = SuiteDatabase()
                membership_mgr = MembershipManager(suite_db)
                
                # Find servers in the target suites
                suite_servers = []
                individual_servers = []
                other_servers = []
                
                for server in all_servers:
                    try:
                        suites = await membership_mgr.get_server_suites(server.name)
                        server_suite_names = [suite[1] for suite in suites]  # suite[1] is the name
                        
                        # Check if server is in any of our target suites
                        if any(suite_name in server_suite_names for suite_name in suite_names):
                            suite_servers.append(server)
                        elif not server_suite_names:  # No suites = individual server
                            individual_servers.append(server)
                        else:
                            other_servers.append(server)
                    except Exception:
                        # If can't get suite info, treat as individual server
                        individual_servers.append(server)
                
                if not suite_servers:
                    console.print(f"[red]❌ No servers found in suites: {suite_list}[/red]")
                    console.print("[yellow]💡 Use 'mcp-manager suite list' to see available suites[/yellow]")
                    return
                
                servers_to_enable = suite_servers[:]
                if include_individual:
                    servers_to_enable.extend(individual_servers)
                    
                servers_to_disable = other_servers[:]
                if not include_individual:
                    servers_to_disable.extend(individual_servers)
                
                console.print(f"[green]📦 Servers to ENABLE ({len(servers_to_enable)}):[/green]")
                for server in servers_to_enable:
                    status = "already enabled" if server.enabled else "will enable"
                    suite_info = " (suite)" if server in suite_servers else " (individual)"
                    console.print(f"  ✅ {server.name} ({status}){suite_info}")
                
                console.print("")
                console.print(f"[red]📦 Servers to DISABLE ({len(servers_to_disable)}):[/red]")
                for server in servers_to_disable:
                    status = "already disabled" if not server.enabled else "will disable"
                    console.print(f"  ❌ {server.name} ({status})")
                
                if not dry_run:
                    console.print("")
                    from rich.prompt import Confirm
                    if not Confirm.ask(f"[bold]Proceed with suite activation?[/bold]"):
                        console.print("[dim]Suite activation cancelled[/dim]")
                        return
                    
                    console.print("")
                    console.print("[blue]🔄 Applying changes...[/blue]")
                    
                    # Enable selected servers
                    enabled_count = 0
                    for server in servers_to_enable:
                        if not server.enabled:
                            success = await manager.enable_server(server.name)
                            if success:
                                enabled_count += 1
                                console.print(f"  [green]✅ Enabled: {server.name}[/green]")
                            else:
                                console.print(f"  [red]❌ Failed to enable: {server.name}[/red]")
                    
                    # Disable other servers  
                    disabled_count = 0
                    for server in servers_to_disable:
                        if server.enabled:
                            success = await manager.disable_server(server.name)
                            if success:
                                disabled_count += 1
                                console.print(f"  [yellow]❌ Disabled: {server.name}[/yellow]")
                            else:
                                console.print(f"  [red]❌ Failed to disable: {server.name}[/red]")
                    
                    console.print("")
                    console.print(f"[bold green]🎯 Suites '{suite_list}' activated successfully![/bold green]")
                    console.print(f"[dim]Enabled {enabled_count} servers, disabled {disabled_count} servers[/dim]")
                else:
                    console.print("")
                    console.print("[dim]Dry run complete - no changes made[/dim]")
                    
            except Exception as e:
                console.print(f"[red]Failed to activate suites: {e}[/red]")
                import sys
                sys.exit(1)
        
        asyncio.run(activate_suites_async())

    
    @suite.command("activate-except")
    @click.argument("suite_name")
    @click.option("--dry-run", is_flag=True, help="Show what would be changed without making changes")
    @handle_errors
    def suite_activate_except(suite_name: str, dry_run: bool):
        """Activate all servers EXCEPT those in the specified suite."""
        
        async def activate_except_suite_async():
            try:
                manager, context = cli_context.auto_sync_and_get_manager(silent=True)
                console.print(f"[dim]Suite activation (except) in: {context.description}[/dim]")
                
                if dry_run:
                    console.print("[yellow]🔍 DRY RUN MODE - No changes will be made[/yellow]")
                    console.print("")
                
                console.print(f"[blue]🎯 Activating all servers EXCEPT suite: {suite_name}[/blue]")
                console.print("")
                
                # Get all servers
                all_servers = await manager.list_servers()
                
                # Get suite membership for all servers
                from mcp_manager.core.suites.database import SuiteDatabase
                from mcp_manager.core.suites.membership import MembershipManager
                
                suite_db = SuiteDatabase()
                membership_mgr = MembershipManager(suite_db)
                
                # Find servers in the target suite vs others
                excluded_servers = []
                other_servers = []
                
                for server in all_servers:
                    try:
                        suites = await membership_mgr.get_server_suites(server.name)
                        server_suite_names = [suite[1] for suite in suites]  # suite[1] is the name
                        
                        # Check if server is in the excluded suite
                        if suite_name in server_suite_names:
                            excluded_servers.append(server)
                        else:
                            other_servers.append(server)
                    except Exception:
                        # If can't get suite info, treat as other server (enable it)
                        other_servers.append(server)
                
                console.print(f"[green]📦 Servers to ENABLE ({len(other_servers)}):[/green]")
                for server in other_servers:
                    status = "already enabled" if server.enabled else "will enable"
                    console.print(f"  ✅ {server.name} ({status})")
                
                console.print("")
                console.print(f"[red]📦 Servers to DISABLE ({len(excluded_servers)}):[/red]")
                for server in excluded_servers:
                    status = "already disabled" if not server.enabled else "will disable"
                    console.print(f"  ❌ {server.name} ({status}) [excluded suite]")
                
                if not dry_run:
                    console.print("")
                    from rich.prompt import Confirm
                    if not Confirm.ask(f"[bold]Proceed with activation (except '{suite_name}')?[/bold]"):
                        console.print("[dim]Activation cancelled[/dim]")
                        return
                    
                    console.print("")
                    console.print("[blue]🔄 Applying changes...[/blue]")
                    
                    # Enable other servers
                    enabled_count = 0
                    for server in other_servers:
                        if not server.enabled:
                            success = await manager.enable_server(server.name)
                            if success:
                                enabled_count += 1
                                console.print(f"  [green]✅ Enabled: {server.name}[/green]")
                            else:
                                console.print(f"  [red]❌ Failed to enable: {server.name}[/red]")
                    
                    # Disable excluded servers  
                    disabled_count = 0
                    for server in excluded_servers:
                        if server.enabled:
                            success = await manager.disable_server(server.name)
                            if success:
                                disabled_count += 1
                                console.print(f"  [yellow]❌ Disabled: {server.name}[/yellow]")
                            else:
                                console.print(f"  [red]❌ Failed to disable: {server.name}[/red]")
                    
                    console.print("")
                    console.print(f"[bold green]🎯 Activated all servers except '{suite_name}' successfully![/bold green]")
                    console.print(f"[dim]Enabled {enabled_count} servers, disabled {disabled_count} servers[/dim]")
                else:
                    console.print("")
                    console.print("[dim]Dry run complete - no changes made[/dim]")
                    
            except Exception as e:
                console.print(f"[red]Failed to activate except suite: {e}[/red]")
                import sys
                sys.exit(1)
        
        asyncio.run(activate_except_suite_async())
    
    return [suite]