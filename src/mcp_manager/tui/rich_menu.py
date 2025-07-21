"""
Rich-based interactive menu for MCP Manager.

Provides a clean, reliable menu interface using Rich and Prompt Toolkit
instead of the problematic Textual framework.
"""

import asyncio
import logging
import os
import sys
from typing import List, Optional, Dict, Any
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich.align import Align
from rich.columns import Columns
from rich.layout import Layout
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn

from mcp_manager import __version__
from mcp_manager.core.simple_manager import SimpleMCPManager
from mcp_manager.core.discovery import ServerDiscovery
from mcp_manager.core.models import Server, ServerType, ServerScope
from mcp_manager.utils.logging import get_logger, setup_logging
from mcp_manager.utils.config import get_config

logger = get_logger(__name__)
console = Console()


class RichMenuApp:
    """Rich-based interactive menu for MCP Manager."""
    
    def __init__(self):
        self.manager = SimpleMCPManager()
        self.discovery = ServerDiscovery()
        self.running = True
        self._ensure_logging_setup()
    
    def _ensure_logging_setup(self):
        """Ensure logging is properly configured."""
        try:
            # Check if logging is already configured
            root_logger = logging.getLogger()
            if root_logger.handlers:
                return  # Already configured
            
            # Setup logging with default configuration
            config = get_config()
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
        except Exception as e:
            # Fallback to basic console logging if setup fails
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
            )
            logger.warning(f"Failed to setup logging configuration: {e}")
    
    def show_header(self):
        """Display the application header."""
        console.clear()
        
        # Create header as a table to match server table styling exactly
        header_table = Table(
            title=f"[bold]MCP Manager v{__version__}[/bold]",
            box=box.ROUNDED,
            title_style="bold blue",
            show_header=False,
            width=97  # Match server table width (4+22+14+12+45 = 97 chars)
        )
        header_table.add_column("Header", justify="center", style="blue")
        header_table.add_row("Complete MCP Server Management")
        
        console.print(header_table)
        console.print()
    
    def show_main_menu(self) -> str:
        """Display main menu and get user choice."""
        menu_options = [
            ("1", "Manage Servers", "View and manage your MCP servers", "🔧"),
            ("2", "Add Server", "Add a new MCP server manually", "➕"),
            ("3", "Discover & Install", "Find and install servers", "🔍"),
            ("4", "Install Package", "Install by package ID", "📦"),
            ("5", "Clean Configuration", "Fix broken configurations", "🧹"),
            ("6", "Check Sync Status", "Verify mcp-manager and Claude sync", "🔄"),
            ("7", "System Information", "View system status", "ℹ"),
            ("8", "Review Logs", "View recent log entries", "📋"),
            ("9", "Debug Mode", "Toggle debug logging", "🐛"),
            ("h", "Help", "Show help and keyboard shortcuts", "❓"),
            ("q", "Exit", "Quit MCP Manager", "🚪"),
        ]
        
        # Create menu table
        table = Table(
            title="[bold]Main Menu[/bold]",
            box=box.ROUNDED,
            title_style="bold blue",
            show_header=False,
            padding=(0, 1)
        )
        table.add_column("Key", style="bold cyan", width=4, justify="center")
        table.add_column("Icon", width=4, justify="center")
        table.add_column("Option", style="bold white", width=20)
        table.add_column("Description", style="dim", width=35)
        
        for key, option, desc, icon in menu_options:
            table.add_row(f"[bold cyan]{key}[/bold cyan]", icon, option, desc)
        
        console.print(table)
        console.print()
        
        choice = Prompt.ask(
            "[bold cyan]Select an option[/bold cyan]",
            choices=[opt[0] for opt in menu_options],
            default="1"
        )
        
        return choice
    
    async def show_servers(self):
        """Display and manage servers."""
        while True:
            console.clear()
            self.show_header()
            
            console.print("[bold]Server Management[/bold]", style="blue")
            console.print()
            
            # Show loading spinner while fetching servers
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("Loading servers...", total=None)
                try:
                    servers = await self.manager.list_servers()
                except Exception as e:
                    console.print(f"[red]Error loading servers: {e}[/red]")
                    Prompt.ask("Press Enter to continue", default="")
                    return
            
            if not servers:
                console.print(Panel(
                    "[yellow]No servers configured[/yellow]\n\n"
                    "[dim]Use 'Add Server' or 'Discover & Install' to get started[/dim]",
                    title="Server Status",
                    style="yellow",
                    box=box.ROUNDED
                ))
                console.print()
            else:
                # Create clean, professional servers table
                table = Table(
                    title=f"[bold]Server Management - {len(servers)} Configured[/bold]",
                    box=box.ROUNDED,
                    title_style="bold blue",
                    show_header=True,
                    header_style="bold white on blue"
                )
                table.add_column("#", style="dim", width=4, justify="center")
                table.add_column("Server Name", style="bold cyan", width=22)
                table.add_column("Type", style="yellow", width=14, justify="center")
                table.add_column("Status", width=12, justify="center")
                table.add_column("Command", style="dim", width=45)
                
                for i, server in enumerate(servers, 1):
                    # Professional status indicators
                    if server.enabled:
                        status = "[green]●[/green] [green]Enabled[/green]"
                    else:
                        status = "[red]○[/red] [dim]Disabled[/dim]"
                    
                    # Clean command display
                    command = server.command
                    if len(command) > 42:
                        # Smart truncation - show beginning and end
                        command = command[:20] + "..." + command[-19:]
                    
                    # Type formatting
                    type_display = {
                        'npm': '[green]NPM[/green]',
                        'docker': '[blue]Docker[/blue]',
                        'docker-desktop': '[cyan]Docker Desktop[/cyan]',
                        'custom': '[yellow]Custom[/yellow]'
                    }.get(server.server_type.value, server.server_type.value)
                    
                    table.add_row(
                        str(i),
                        server.name,
                        type_display,
                        status,
                        command
                    )
                
                console.print(table)
                console.print()
            
            # Compact horizontal action bar
            from rich.columns import Columns
            
            # All actions in compact format with icons
            actions = [
                ("a", "Add", "blue", "➕"),
                ("c", "Configure", "magenta", "⚙️"),
                ("e", "Enable", "green", "✅"),
                ("d", "Disable", "red", "❌"),
                ("x", "Remove", "red", "🗑"),
                ("m", "Multi-Select", "yellow", "☰"),
                ("r", "Refresh", "cyan", "🔄"),
                ("h", "Help", "yellow", "❓"),
                ("q", "Quit", "red", "🚪"),
                ("b", "Back", "dim", "←")
            ]
            
            # Import needed components
            from rich.columns import Columns
            from rich.panel import Panel
            
            # Use a simple list format instead of table to avoid alignment issues
            console.print("[bold blue]Available Actions:[/bold blue]")
            console.print()
            
            # Display actions in a clean 3-column format
            
            action_panels = []
            for key, action, color, icon in actions:
                panel_content = f"[bold cyan]{key}[/bold cyan] - [{color}]{action}[/{color}]"
                panel = Panel(
                    panel_content,
                    width=25,
                    box=box.ROUNDED,
                    padding=(0, 1)
                )
                action_panels.append(panel)
            
            # Display panels in columns for better layout
            console.print(Columns(action_panels, equal=True, expand=True))
            console.print()
            
            # Add instruction for server details
            if servers:
                console.print(f"[dim]💡 Enter server number (1-{len(servers)}) to view details[/dim]")
                console.print()
            
            # Collect all valid choices - include action keys and server numbers
            all_choices = [a[0] for a in actions]
            if servers:
                all_choices.extend([str(i) for i in range(1, len(servers) + 1)])
            
            choice = Prompt.ask(
                "[bold cyan]Select Action or Server Number[/bold cyan]",
                choices=all_choices,
                default="b"
            )
            
            if choice == "b":
                return
            elif choice == "r":
                continue  # Refresh by reloading the loop
            elif choice == "h":
                self.show_help()
                Prompt.ask("Press Enter to continue", default="")
            elif choice == "q":
                self.running = False
                return
            elif choice == "a":
                await self.add_server_interactive()
            elif choice == "c":
                await self.configure_server()
            elif choice == "m":
                await self.multi_select_operations(servers)
            elif choice.isdigit():
                # Handle server number selection for details
                server_num = int(choice)
                if 1 <= server_num <= len(servers):
                    selected_server = servers[server_num - 1]
                    await self.show_single_server_details(selected_server)
                else:
                    console.print(f"[red]Invalid server number: {choice}[/red]")
                    Prompt.ask("Press Enter to continue", default="")
            elif choice in ["e", "d", "x"]:
                if not servers:
                    console.print("[yellow]No servers available[/yellow]")
                    Prompt.ask("Press Enter to continue", default="")
                    continue
                    
                # Select server
                server_choices = [f"{i}" for i in range(1, len(servers) + 1)]
                try:
                    server_idx = Prompt.ask(
                        f"Select server (1-{len(servers)})",
                        choices=server_choices
                    )
                    selected_server = servers[int(server_idx) - 1]
                    
                    if choice == "e":
                        await self.enable_server(selected_server)
                    elif choice == "d":
                        await self.disable_server(selected_server)
                    elif choice == "x":
                        await self.remove_server(selected_server)
                        
                except (ValueError, IndexError):
                    console.print("[red]Invalid selection[/red]")
                    Prompt.ask("Press Enter to continue", default="")
    
    async def enable_server(self, server: Server):
        """Enable a server."""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task(f"Enabling {server.name}...", total=None)
                await self.manager.enable_server(server.name)
            
            console.print(f"[green]✓ Enabled {server.name}[/green]")
        except Exception as e:
            console.print(f"[red]Failed to enable {server.name}: {e}[/red]")
        
        Prompt.ask("Press Enter to continue", default="")
    
    async def disable_server(self, server: Server):
        """Disable a server."""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task(f"Disabling {server.name}...", total=None)
                await self.manager.disable_server(server.name)
            
            console.print(f"[green]✓ Disabled {server.name}[/green]")
        except Exception as e:
            console.print(f"[red]Failed to disable {server.name}: {e}[/red]")
        
        Prompt.ask("Press Enter to continue", default="")
    
    async def remove_server(self, server: Server):
        """Remove a server."""
        if not Confirm.ask(f"Remove server '{server.name}'? This cannot be undone."):
            return
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task(f"Removing {server.name}...", total=None)
                await self.manager.remove_server(server.name)
            
            # Check if it was a Docker-based server for additional feedback
            if server.server_type in [ServerType.DOCKER, ServerType.DOCKER_DESKTOP]:
                console.print(f"[green]✓ Removed {server.name} and cleaned up Docker images[/green]")
            else:
                console.print(f"[green]✓ Removed {server.name}[/green]")
        except Exception as e:
            console.print(f"[red]Failed to remove {server.name}: {e}[/red]")
        
        Prompt.ask("Press Enter to continue", default="")
    
    async def multi_select_operations(self, servers):
        """Handle multi-select operations."""
        console.clear()
        self.show_header()
        
        console.print("[bold]Multi-Select Server Operations[/bold]", style="blue")
        console.print()
        
        # Show servers with numbers
        table = Table(
            title="[bold]Select Servers[/bold]",
            box=box.ROUNDED,
            title_style="bold green"
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("Name", style="bold cyan", width=20)
        table.add_column("Type", style="yellow", width=12)
        table.add_column("Status", width=8)
        table.add_column("Command", style="dim", width=40)
        
        for i, server in enumerate(servers, 1):
            status = "[green]✓ Enabled[/green]" if server.enabled else "[red]✗ Disabled[/red]"
            command_short = (server.command[:37] + "..." 
                           if len(server.command) > 40 else server.command)
            table.add_row(
                str(i),
                server.name,
                server.server_type.value,
                status,
                command_short
            )
        
        console.print(table)
        console.print()
        
        # Get server selection
        console.print("[bold]Selection Options:[/bold]")
        console.print("[dim]• Enter server numbers: [/dim][yellow]1 3 5[/yellow][dim] for servers 1, 3, and 5[/dim]")
        console.print("[dim]• Enter [/dim][yellow]all[/yellow][dim] to select all servers[/dim]")
        console.print("[dim]• Press Enter to cancel[/dim]")
        console.print()
        
        selection = Prompt.ask("[cyan]Select servers[/cyan]", default="").strip()
        
        if not selection:
            return
        
        # Parse selection
        selected_servers = []
        if selection.lower() == 'all':
            selected_servers = servers.copy()
        else:
            try:
                numbers = [int(x.strip()) for x in selection.split() if x.strip()]
                for num in numbers:
                    if 1 <= num <= len(servers):
                        selected_servers.append(servers[num - 1])
                    else:
                        console.print(f"[yellow]Warning: Invalid server number {num}[/yellow]")
            except ValueError:
                console.print("[red]Invalid input. Enter numbers separated by spaces.[/red]")
                Prompt.ask("Press Enter to continue", default="")
                return
        
        if not selected_servers:
            console.print("[yellow]No valid servers selected[/yellow]")
            Prompt.ask("Press Enter to continue", default="")
            return
        
        # Show selected servers
        console.print(f"[bold]Selected {len(selected_servers)} servers:[/bold]")
        for server in selected_servers:
            status_icon = "✓" if server.enabled else "✗"
            console.print(f"  {status_icon} {server.name}")
        console.print()
        
        # Create horizontal action bar matching main server management style
        actions = [
            ("e", "Enable", "green", "✅"),
            ("d", "Disable", "red", "❌"),
            ("r", "Remove", "red", "🗑"),
            ("h", "Help", "yellow", "❓"),
            ("q", "Quit", "red", "🚪"),
            ("c", "Cancel", "dim", "↩")
        ]
        
        # Create actions as a table to match server table styling exactly
        actions_table = Table(
            title="[bold]Bulk Actions[/bold]",
            box=box.ROUNDED,
            title_style="bold blue",
            show_header=False,
            width=97  # Match server table width
        )
        
        # Add columns for each action
        for key, action, color, icon in actions:
            actions_table.add_column(
                f"{key}", 
                width=15, 
                justify="center",
                style="white"
            )
        
        # Create action content for the single row
        action_contents = []
        for key, action, color, icon in actions:
            content = f"[bold cyan]{key}[/bold cyan]\n{icon}[{color}]{action}[/{color}]"
            action_contents.append(content)
        
        actions_table.add_row(*action_contents)
        console.print(actions_table)
        console.print()
        
        action = Prompt.ask(
            "[bold cyan]Bulk Action[/bold cyan]",
            choices=["e", "d", "r", "h", "q", "c"],
            default="c"
        )
        
        if action == "c":
            return
        elif action == "h":
            self.show_help()
            Prompt.ask("Press Enter to continue", default="")
        elif action == "q":
            self.running = False
            return
        elif action == "e":
            await self.bulk_enable(selected_servers)
        elif action == "d":
            await self.bulk_disable(selected_servers)
        elif action == "r":
            if Confirm.ask(f"Remove {len(selected_servers)} servers? This cannot be undone.", default=False):
                await self.bulk_remove(selected_servers)
        
        Prompt.ask("Press Enter to continue", default="")
    
    async def bulk_enable(self, servers):
        """Enable multiple servers."""
        console.print(f"[blue]Enabling {len(servers)} servers...[/blue]")
        success_count = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            for server in servers:
                task = progress.add_task(f"Enabling {server.name}...", total=None)
                try:
                    await self.manager.enable_server(server.name)
                    console.print(f"[green]✓ Enabled {server.name}[/green]")
                    success_count += 1
                except Exception as e:
                    console.print(f"[red]✗ Failed to enable {server.name}: {e}[/red]")
                progress.remove_task(task)
        
        console.print(f"[blue]Enabled {success_count}/{len(servers)} servers[/blue]")
    
    async def bulk_disable(self, servers):
        """Disable multiple servers."""
        console.print(f"[blue]Disabling {len(servers)} servers...[/blue]")
        success_count = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            for server in servers:
                task = progress.add_task(f"Disabling {server.name}...", total=None)
                try:
                    await self.manager.disable_server(server.name)
                    console.print(f"[green]✓ Disabled {server.name}[/green]")
                    success_count += 1
                except Exception as e:
                    console.print(f"[red]✗ Failed to disable {server.name}: {e}[/red]")
                progress.remove_task(task)
        
        console.print(f"[blue]Disabled {success_count}/{len(servers)} servers[/blue]")
    
    async def bulk_remove(self, servers):
        """Remove multiple servers."""
        console.print(f"[blue]Removing {len(servers)} servers...[/blue]")
        success_count = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            for server in servers:
                task = progress.add_task(f"Removing {server.name}...", total=None)
                try:
                    await self.manager.remove_server(server.name)
                    # Check if it was a Docker-based server for additional feedback
                    if server.server_type in [ServerType.DOCKER, ServerType.DOCKER_DESKTOP]:
                        console.print(f"[green]✓ Removed {server.name} and cleaned up Docker images[/green]")
                    else:
                        console.print(f"[green]✓ Removed {server.name}[/green]")
                    success_count += 1
                except Exception as e:
                    console.print(f"[red]✗ Failed to remove {server.name}: {e}[/red]")
                progress.remove_task(task)
        
        console.print(f"[blue]Removed {success_count}/{len(servers)} servers[/blue]")
    
    async def add_server_interactive(self):
        """Interactive server addition."""
        console.clear()
        self.show_header()
        
        console.print("[bold]Add New Server[/bold]", style="blue")
        console.print()
        
        # Get server details
        name = Prompt.ask("[cyan]Server name[/cyan]")
        if not name:
            console.print("[red]Server name is required[/red]")
            Prompt.ask("Press Enter to continue", default="")
            return
        
        command = Prompt.ask("[cyan]Command[/cyan] (e.g., npx @package/name)")
        if not command:
            console.print("[red]Command is required[/red]")
            Prompt.ask("Press Enter to continue", default="")
            return
        
        description = Prompt.ask("[cyan]Description[/cyan] (optional)", default="")
        
        # Server type selection
        type_choices = {
            "1": ServerType.NPM,
            "2": ServerType.DOCKER,
            "3": ServerType.DOCKER_DESKTOP,
            "4": ServerType.CUSTOM,
        }
        
        console.print("\n[bold]Server Types:[/bold]")
        console.print("1. NPM Package")
        console.print("2. Docker Container")
        console.print("3. Docker Desktop")
        console.print("4. Custom")
        
        type_choice = Prompt.ask(
            "[cyan]Server type[/cyan]",
            choices=list(type_choices.keys()),
            default="4"
        )
        server_type = type_choices[type_choice]
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("Adding server...", total=None)
                await self.manager.add_server(
                    name=name,
                    command=command,
                    description=description or None,
                    server_type=server_type,
                    scope=ServerScope.USER,
                )
            
            console.print(f"[green]✓ Added server: {name}[/green]")
        except Exception as e:
            console.print(f"[red]Failed to add server: {e}[/red]")
        
        Prompt.ask("Press Enter to continue", default="")
    
    async def discover_servers(self):
        """Discover and install servers."""
        console.clear()
        self.show_header()
        
        console.print("[bold]Server Discovery & Installation[/bold]", style="blue")
        console.print()
        
        console.print("[bold]Pattern Support:[/bold]")
        console.print("[dim]• Wildcards: [/dim][yellow]aws*[/yellow][dim], [/dim][yellow]file*[/yellow][dim], [/dim][yellow]?sql[/yellow]")
        console.print("[dim]• Regex: [/dim][yellow]regex:^aws.*db$[/yellow][dim], [/dim][yellow]regex:.*server.*[/yellow]")
        console.print("[dim]• Simple: [/dim][yellow]filesystem[/yellow][dim], [/dim][yellow]database[/yellow]")
        console.print()
        
        query = Prompt.ask(
            "[cyan]Search for servers[/cyan] (supports patterns above)",
            default="filesystem"
        )
        
        if not query:
            return
        
        # Search for servers
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task(f"Searching for '{query}'...", total=None)
            try:
                results = await self.discovery.discover_servers(query=query, limit=10)
            except Exception as e:
                console.print(f"[red]Search failed: {e}[/red]")
                Prompt.ask("Press Enter to continue", default="")
                return
        
        if not results:
            console.print(f"[yellow]No servers found for '{query}'[/yellow]")
            Prompt.ask("Press Enter to continue", default="")
            return
        
        # Display results
        table = Table(
            title=f"[bold]Found {len(results)} servers for '{query}'[/bold]",
            box=box.ROUNDED,
            title_style="bold green"
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("Package", style="bold cyan", width=25)
        table.add_column("Type", style="yellow", width=8)
        table.add_column("Description", style="white", width=50)
        
        for i, result in enumerate(results, 1):
            desc_short = (result.description[:47] + "..." 
                         if result.description and len(result.description) > 50 
                         else result.description or "No description")
            
            table.add_row(
                str(i),
                result.package or result.name,
                result.server_type.value,
                desc_short
            )
        
        console.print(table)
        console.print()
        
        # Install selection
        install_choice = Prompt.ask(
            f"[cyan]Select server to install (1-{len(results)})[/cyan] or [dim]Enter to skip[/dim]",
            default=""
        )
        
        if install_choice and install_choice.isdigit():
            try:
                idx = int(install_choice) - 1
                if 0 <= idx < len(results):
                    await self.install_discovered_server(results[idx])
            except (ValueError, IndexError):
                console.print("[red]Invalid selection[/red]")
                Prompt.ask("Press Enter to continue", default="")
    
    async def install_discovered_server(self, result):
        """Install a discovered server."""
        # Create server name from package
        if result.server_type == ServerType.NPM:
            server_name = result.package.replace("@", "").replace("/", "-").replace("server-", "")
            server_name = server_name.replace("modelcontextprotocol-", "official-")
        elif result.server_type == ServerType.DOCKER:
            server_name = result.package.replace("/", "_")
        elif result.server_type == ServerType.DOCKER_DESKTOP:
            server_name = result.name.replace("docker-desktop-", "")
        else:
            server_name = result.name
        
        console.print(f"\n[bold]Installing:[/bold] {result.package}")
        console.print(f"[bold]As:[/bold] {server_name}")
        
        if not Confirm.ask("Proceed with installation?", default=True):
            return
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("Installing server...", total=None)
                await self.manager.add_server(
                    name=server_name,
                    server_type=result.server_type,
                    command=result.install_command,
                    description=result.description,
                    args=result.install_args,
                )
            
            console.print(f"[green]✓ Installed {server_name}[/green]")
        except Exception as e:
            console.print(f"[red]Installation failed: {e}[/red]")
        
        Prompt.ask("Press Enter to continue", default="")
    
    async def install_package(self):
        """Install package by ID."""
        console.clear()
        self.show_header()
        
        console.print("[bold]Install Package by ID[/bold]", style="blue")
        console.print()
        console.print("Example IDs: [dim]dd-SQLite, modelcontextprotocol-filesystem, mcp-filesystem[/dim]")
        console.print()
        
        install_id = Prompt.ask("[cyan]Enter Install ID[/cyan]")
        if not install_id:
            return
        
        # Search for the specific package
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task(f"Finding '{install_id}'...", total=None)
            try:
                results = await self.discovery.discover_servers(limit=100)
            except Exception as e:
                console.print(f"[red]Search failed: {e}[/red]")
                Prompt.ask("Press Enter to continue", default="")
                return
        
        # Find matching result
        target_result = None
        for result in results:
            # Recreate install_id logic
            if result.server_type == ServerType.NPM:
                result_id = result.package.replace("@", "").replace("/", "-").replace("server-", "")
            elif result.server_type == ServerType.DOCKER:
                result_id = result.package.replace("/", "-")
            elif result.server_type == ServerType.DOCKER_DESKTOP:
                result_id = f"dd-{result.name.replace('docker-desktop-', '')}"
            else:
                result_id = result.name
            
            if result_id == install_id:
                target_result = result
                break
        
        if not target_result:
            console.print(f"[red]Install ID '{install_id}' not found[/red]")
            Prompt.ask("Press Enter to continue", default="")
            return
        
        await self.install_discovered_server(target_result)
    
    def show_system_info(self):
        """Display system information."""
        console.clear()
        self.show_header()
        
        console.print("[bold]System Information[/bold]", style="blue")
        console.print()
        
        try:
            info = self.manager.get_system_info()
            
            # Create info table
            table = Table(
                title="[bold]System Status[/bold]",
                box=box.ROUNDED,
                title_style="bold blue"
            )
            table.add_column("Component", style="bold cyan", width=20)
            table.add_column("Status", width=10)
            table.add_column("Version/Path", style="dim", width=40)
            
            # Add system info rows
            table.add_row("Python", "✓", info.python_version)
            table.add_row("Platform", "✓", info.platform)
            table.add_row("Config Directory", "✓", str(info.config_dir))
            table.add_row("Log File", "✓" if info.log_file else "✗", str(info.log_file) if info.log_file else "Not configured")
            
            # Dependencies
            table.add_section()
            table.add_row("Claude CLI", "✓" if info.claude_cli_available else "✗", info.claude_cli_version or "Not available")
            table.add_row("NPM", "✓" if info.npm_available else "✗", info.npm_version or "Not available")
            table.add_row("Docker", "✓" if info.docker_available else "✗", info.docker_version or "Not available")
            table.add_row("Git", "✓" if info.git_available else "✗", info.git_version or "Not available")
            
            console.print(table)
            
        except Exception as e:
            console.print(f"[red]Error getting system info: {e}[/red]")
        
        console.print()
        Prompt.ask("Press Enter to continue", default="")
    
    async def check_sync_status(self):
        """Check synchronization status between mcp-manager and Claude."""
        console.clear()
        self.show_header()
        
        console.print("[bold]Synchronization Status Check[/bold]", style="blue")
        console.print()
        
        # Show loading spinner while checking
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Checking synchronization status...", total=None)
            try:
                sync_result = await self.manager.check_sync_status()
            except Exception as e:
                console.print(f"[red]Failed to check sync status: {e}[/red]")
                Prompt.ask("Press Enter to continue", default="")
                return
        
        # Display results
        if sync_result.in_sync:
            console.print("[green]✅ MCP Manager and Claude are in sync![/green]")
        else:
            console.print("[red]❌ MCP Manager and Claude are out of sync[/red]")
        
        console.print()
        
        # Session warning
        if sync_result.will_start_claude_session:
            console.print("[yellow]⚠️ This check started or may start a new Claude session[/yellow]")
            console.print()
        
        # Claude availability
        if not sync_result.claude_available:
            console.print("[red]❌ Claude CLI not available[/red]")
            console.print("[dim]Install Claude Code to use sync checking[/dim]")
            console.print()
        
        # Create sync status table
        if sync_result.claude_available:
            table = Table(
                title="[bold]Sync Status Details[/bold]",
                box=box.ROUNDED,
                title_style="bold blue"
            )
            table.add_column("Component", style="cyan", width=20)
            table.add_column("MCP Manager", style="green", width=35)
            table.add_column("Claude (Expanded)", style="yellow", width=35)
            
            # Server counts
            table.add_row(
                "Server Count",
                str(len(sync_result.manager_servers)),
                str(len(sync_result.claude_servers))
            )
            
            # Server lists (show all servers or truncate if too many)
            def format_server_list(servers, max_display=8):
                if not servers:
                    return "[dim]None[/dim]"
                if len(servers) <= max_display:
                    return ", ".join(servers)
                else:
                    displayed = ", ".join(servers[:max_display])
                    return f"{displayed}\n[dim](+{len(servers) - max_display} more...)[/dim]"
            
            manager_list = format_server_list(sync_result.manager_servers)
            claude_list = format_server_list(sync_result.claude_servers)
            
            table.add_row(
                "Servers",
                manager_list,
                claude_list
            )
            
            console.print(table)
            console.print()
            
            # Show docker-gateway expansion note if applicable
            if any("docker-gateway" in s or "aws-diagram" in s for s in sync_result.claude_servers + sync_result.manager_servers):
                console.print("[dim]ℹ️ Claude's docker-gateway has been expanded to show individual servers[/dim]")
                console.print()
        
        # Issues
        if sync_result.issues:
            console.print("[bold red]Issues Found:[/bold red]")
            for issue in sync_result.issues:
                console.print(f"  [red]❌[/red] {issue}")
            console.print()
        
        # Missing servers
        if sync_result.missing_in_claude:
            console.print("[bold yellow]Servers in MCP Manager but missing in Claude:[/bold yellow]")
            for server in sync_result.missing_in_claude:
                console.print(f"  [yellow]⚠️[/yellow] {server}")
            console.print()
        
        if sync_result.missing_in_manager:
            console.print("[bold blue]Servers in Claude but not visible in MCP Manager:[/bold blue]")
            for server in sync_result.missing_in_manager:
                console.print(f"  [blue]ℹ️[/blue] {server}")
            console.print()
        
        # Warnings
        if sync_result.warnings:
            console.print("[bold yellow]Warnings:[/bold yellow]")
            for warning in sync_result.warnings:
                console.print(f"  [yellow]⚠️[/yellow] {warning}")
            console.print()
        
        # Docker Gateway Test Results
        if sync_result.docker_gateway_test:
            self._display_docker_gateway_test(sync_result.docker_gateway_test)
        
        # Recommendations
        console.print("[bold]Recommendations:[/bold]")
        if not sync_result.in_sync:
            if sync_result.issues:
                console.print("  [blue]•[/blue] Review and resolve the issues listed above")
            if sync_result.missing_in_claude:
                console.print("  [blue]•[/blue] Consider re-adding missing servers or running cleanup")
            console.print("  [blue]•[/blue] Use option 5 (Clean Configuration) to fix common issues")
        else:
            console.print("  [green]•[/green] Everything looks good! No action needed.")
        
        console.print()
        Prompt.ask("Press Enter to continue", default="")
    
    def show_help(self):
        """Display help information."""
        console.clear()
        self.show_header()
        
        console.print("[bold]Help & Usage[/bold]", style="blue")
        console.print()
        
        help_text = """
[bold cyan]MCP Manager[/bold cyan] - Complete MCP Server Management

[bold]Navigation:[/bold]
• Use number keys (1-9) or letters (h, q) to select options
• Type your choice and press Enter
• Most screens allow you to go back or cancel

[bold]Key Features:[/bold]
• [green]Manage Servers[/green] - View, enable, disable, and remove MCP servers
• [green]Add Server[/green] - Manually add custom MCP servers
• [green]Discover & Install[/green] - Find servers from NPM, Docker Hub, Docker Desktop
• [green]Install Package[/green] - Install by unique Install ID (e.g., dd-SQLite)
• [green]Clean Configuration[/green] - Fix broken MCP configurations
• [green]Check Sync Status[/green] - Verify mcp-manager and Claude are synchronized
• [green]System Information[/green] - Check dependencies and system status
• [green]Review Logs[/green] - View recent log entries and clear log files
• [green]Debug Mode[/green] - Toggle debug logging for troubleshooting

[bold]Server Types:[/bold]
• [yellow]NPM[/yellow] - JavaScript/TypeScript servers (npx @package/name)
• [yellow]Docker[/yellow] - Docker container servers
• [yellow]Docker Desktop[/yellow] - Pre-built Docker Desktop MCP servers
• [yellow]Custom[/yellow] - User-defined servers

[bold]Tips:[/bold]
• Use the discovery feature to find popular MCP servers
• Install IDs make it easy to install servers: [dim]mcp-manager install-package dd-SQLite[/dim]
• The CLI commands work great too: [dim]mcp-manager list[/dim], [dim]mcp-manager discover[/dim]
• Check system info if you have connection issues

[bold]Getting Help:[/bold]
• GitHub: [link]https://github.com/anthropics/claude-mcp-manager[/link]
• Documentation: [link]https://claude-mcp-manager.readthedocs.io[/link]
"""
        
        console.print(Panel(help_text, box=box.ROUNDED, padding=(1, 2)))
        console.print()
        Prompt.ask("Press Enter to continue", default="")
    
    async def cleanup_config(self):
        """Clean up configuration."""
        console.clear()
        self.show_header()
        
        console.print("[bold]Configuration Cleanup[/bold]", style="blue")
        console.print()
        console.print("This will clean up problematic MCP configurations and create a backup.")
        console.print()
        
        if not Confirm.ask("Proceed with cleanup?"):
            return
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("Cleaning up configurations...", total=None)
                # Import cleanup function from CLI
                from mcp_manager.cli.main import _cleanup_impl
                await _cleanup_impl(dry_run=False, no_backup=False)
            
            console.print("[green]✓ Configuration cleanup completed[/green]")
        except Exception as e:
            console.print(f"[red]Cleanup failed: {e}[/red]")
        
        console.print()
        Prompt.ask("Press Enter to continue", default="")
    
    async def review_logs(self):
        """Review recent log entries."""
        console.clear()
        self.show_header()
        
        console.print("[bold]Log Review[/bold]", style="blue")
        console.print()
        
        try:
            config = get_config()
            log_file = config.get_log_file()
            
            if not log_file or not log_file.exists():
                console.print(Panel(
                    "[yellow]No log file found[/yellow]\n\n"
                    "[dim]Logs may be configured to console-only or file path may be incorrect.[/dim]\n"
                    f"[dim]Expected location: {log_file}[/dim]",
                    title="Log Status",
                    style="yellow",
                    box=box.ROUNDED
                ))
                console.print()
                Prompt.ask("Press Enter to continue", default="")
                return
            
            # Read last 100 lines of log file
            console.print(f"[dim]Reading from: {log_file}[/dim]")
            import datetime
            import os
            file_size = log_file.stat().st_size
            mod_time = datetime.datetime.fromtimestamp(log_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            console.print(f"[dim]File size: {file_size} bytes, last modified: {mod_time}[/dim]")
            console.print()
            
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    recent_lines = lines[-100:] if len(lines) > 100 else lines
                
                if not recent_lines:
                    console.print(Panel(
                        "[yellow]Log file is empty[/yellow]",
                        title="Log Status",
                        style="yellow",
                        box=box.ROUNDED
                    ))
                else:
                    # Create table for log entries
                    table = Table(
                        title=f"[bold]Recent Log Entries ({len(recent_lines)} lines)[/bold]",
                        box=box.ROUNDED,
                        title_style="bold blue",
                        show_header=True,
                        header_style="bold white on blue"
                    )
                    table.add_column("Date & Time", style="dim", width=24)
                    table.add_column("Level", width=8, justify="center")
                    table.add_column("Logger", style="cyan", width=25)
                    table.add_column("Message", width=65)
                    
                    for line in recent_lines:
                        line = line.strip()
                        if not line:
                            continue
                            
                        # Parse log line (handle multiple formats)
                        # Format 1: "timestamp | level | logger | message"
                        # Format 2: "[timestamp] [level] message"
                        if ' | ' in line and line.count(' | ') >= 3:
                            # Standard format
                            parts = line.split(' | ')
                            timestamp = parts[0]
                            level = parts[1]
                            logger_name = parts[2]
                            message = ' | '.join(parts[3:])
                        elif line.startswith('[') and '] [' in line:
                            # Bracketed format: [timestamp] [level] message
                            import re
                            match = re.match(r'\[([^\]]+)\] \[([^\]]+)\] (.+)', line)
                            if match:
                                timestamp = match.group(1)
                                level = match.group(2)
                                logger_name = ""
                                message = match.group(3)
                            else:
                                # Fallback for malformed bracketed lines
                                timestamp = ""
                                level = ""
                                logger_name = ""
                                message = line
                        else:
                            # Unknown format - treat as plain message
                            timestamp = ""
                            level = ""
                            logger_name = ""
                            message = line
                        
                        # Color code log levels
                        if level == "ERROR":
                            level_colored = f"[red]{level}[/red]"
                        elif level == "WARNING":
                            level_colored = f"[yellow]{level}[/yellow]"
                        elif level == "INFO":
                            level_colored = f"[green]{level}[/green]"
                        elif level == "DEBUG":
                            level_colored = f"[blue]{level}[/blue]"
                        else:
                            level_colored = level if level else ""
                        
                        # Truncate long messages
                        if len(message) > 62:
                            message = message[:59] + "..."
                        
                        # Format timestamp for display
                        datetime_display = ""
                        if timestamp:
                            # Handle bracketed format: [2025-07-18 17:10:39] -> 07-18 17:10:39
                            if len(timestamp) > 10 and '-' in timestamp:
                                try:
                                    # Extract just month-day and time: "2025-07-18 17:10:39" -> "07-18 17:10:39"
                                    parts = timestamp.split()
                                    if len(parts) >= 2:
                                        date_part = parts[0].split('-')[-2:]  # Get month and day
                                        time_part = parts[1]
                                        datetime_display = '-'.join(date_part) + ' ' + time_part
                                    else:
                                        datetime_display = timestamp
                                except:
                                    datetime_display = timestamp
                            else:
                                datetime_display = timestamp
                        
                        table.add_row(
                            datetime_display,
                            level_colored,
                            logger_name[-22:] if len(logger_name) > 22 else logger_name,
                            message
                        )
                    
                    console.print(table)
                    
                    # Add helpful context
                    console.print()
                    console.print(Panel(
                        "[dim]These logs show MCP server management activities including:[/dim]\n"
                        "[dim]• Server enable/disable operations[/dim]\n"
                        "[dim]• Configuration sync with Claude Code[/dim]\n"
                        "[dim]• Docker server management[/dim]\n"
                        "[dim]• NPM package installations[/dim]",
                        title="Log Context",
                        style="dim",
                        box=box.ROUNDED
                    ))
                
            except Exception as e:
                console.print(f"[red]Error reading log file: {e}[/red]")
                
        except Exception as e:
            console.print(f"[red]Error accessing log configuration: {e}[/red]")
        
        console.print()
        console.print("[dim]Commands:[/dim]")
        console.print("  [bold]r[/bold] - Refresh logs")
        console.print("  [bold]c[/bold] - Clear logs (truncate file)")
        console.print("  [bold]h[/bold] - Help")
        console.print("  [bold]q[/bold] - Quit to main menu")
        console.print("  [bold]Enter[/bold] - Return to main menu")
        
        action = Prompt.ask("Action", choices=["r", "c", "h", "q", ""], default="")
        
        if action == "r":
            await self.review_logs()  # Recursive call to refresh
        elif action == "c":
            if Confirm.ask("Clear all log entries?"):
                try:
                    config = get_config()
                    log_file = config.get_log_file()
                    if log_file and log_file.exists():
                        log_file.write_text("")  # Truncate file
                        console.print("[green]✓ Logs cleared[/green]")
                        console.print()
                        Prompt.ask("Press Enter to continue", default="")
                except Exception as e:
                    console.print(f"[red]Error clearing logs: {e}[/red]")
                    console.print()
                    Prompt.ask("Press Enter to continue", default="")
        elif action == "h":
            self._show_log_review_help()
        elif action == "q":
            return  # Exit back to main menu
    
    async def toggle_debug_mode(self):
        """Toggle debug logging mode."""
        console.clear()
        self.show_header()
        
        console.print("[bold]Logging Configuration[/bold]", style="blue")
        console.print()
        
        # Check current logging configuration
        config = get_config()
        root_logger = logging.getLogger()
        current_level = root_logger.level
        is_debug = current_level == logging.DEBUG
        
        logging_enabled = config.logging.enabled
        file_level = config.logging.level
        console_level = config.logging.console_level
        
        status_color = "green" if logging_enabled else "red"
        status_text = "ENABLED" if logging_enabled else "DISABLED"
        
        console.print(Panel(
            f"[bold]Logging Status: [{status_color}]{status_text}[/{status_color}][/bold]\n\n"
            f"[dim]File logging level: {file_level}[/dim]\n"
            f"[dim]Console logging level: {console_level}[/dim]\n"
            f"[dim]Root logger level: {logging.getLevelName(current_level)}[/dim]\n"
            f"[dim]Active handlers: {len(root_logger.handlers)}[/dim]\n"
            f"[dim]HTTP suppression: {'ON' if config.logging.suppress_http else 'OFF'}[/dim]",
            title="Logging Configuration",
            style=status_color,
            box=box.ROUNDED
        ))
        console.print()
        
        console.print(f"[bold]Available Actions:[/bold]")
        if logging_enabled:
            console.print(f"  [bold]1[/bold] - Disable logging completely")
            console.print(f"  [bold]2[/bold] - Enable debug mode (file logging)")
            console.print(f"  [bold]3[/bold] - Enable verbose console (WARNING->INFO)")
            console.print(f"  [bold]4[/bold] - Reset to defaults")
        else:
            console.print(f"  [bold]1[/bold] - Enable logging")
        
        console.print(f"  [bold]5[/bold] - Show current loggers")
        console.print(f"  [bold]h[/bold] - Help")
        console.print(f"  [bold]q[/bold] - Quit to main menu") 
        console.print(f"  [bold]Enter[/bold] - Return to main menu")
        console.print()
        
        max_choice = "5" if logging_enabled else "5"
        choice = Prompt.ask("Select action", choices=["1", "2", "3", "4", "5", "h", "q", ""], default="")
        
        if choice == "1":
            try:
                if logging_enabled:
                    # Disable logging completely
                    root_logger.setLevel(logging.CRITICAL)
                    for handler in root_logger.handlers:
                        handler.setLevel(logging.CRITICAL)
                    
                    console.print()
                    console.print("[red]✓ Logging disabled[/red]")
                    console.print("[dim]Note: This change affects the current session only.[/dim]")
                else:
                    # Enable logging
                    root_logger.setLevel(logging.INFO)
                    for handler in root_logger.handlers:
                        if hasattr(handler, 'baseFilename'):  # File handler
                            handler.setLevel(logging.INFO)
                        else:  # Console handler
                            handler.setLevel(logging.WARNING)
                    
                    console.print()
                    console.print("[green]✓ Logging enabled[/green]")
                    logger.info("Logging re-enabled via Rich Menu")
                    console.print("[dim]Note: This change affects the current session only.[/dim]")
                
            except Exception as e:
                console.print(f"[red]Error toggling logging: {e}[/red]")
            
            console.print()
            Prompt.ask("Press Enter to continue", default="")
        
        elif choice == "2" and logging_enabled:
            # Enable debug mode (file logging)
            try:
                root_logger.setLevel(logging.DEBUG)
                for handler in root_logger.handlers:
                    if hasattr(handler, 'baseFilename'):  # File handler
                        handler.setLevel(logging.DEBUG)
                
                console.print()
                console.print("[green]✓ Debug mode enabled for file logging[/green]")
                logger.debug("Debug logging enabled - this is a test debug message")
                console.print("[dim]Test debug message logged to file[/dim]")
                console.print("[dim]Console logging level unchanged[/dim]")
                
            except Exception as e:
                console.print(f"[red]Error enabling debug mode: {e}[/red]")
            
            console.print()
            Prompt.ask("Press Enter to continue", default="")
        
        elif choice == "3" and logging_enabled:
            # Enable verbose console
            try:
                for handler in root_logger.handlers:
                    if not hasattr(handler, 'baseFilename'):  # Console handler
                        handler.setLevel(logging.INFO)
                
                console.print()
                console.print("[green]✓ Verbose console enabled (INFO level)[/green]")
                logger.info("Console logging now showing INFO messages")
                console.print("[dim]File logging level unchanged[/dim]")
                
            except Exception as e:
                console.print(f"[red]Error enabling verbose console: {e}[/red]")
            
            console.print()
            Prompt.ask("Press Enter to continue", default="")
        
        elif choice == "4" and logging_enabled:
            # Reset to defaults
            try:
                root_logger.setLevel(logging.INFO)
                for handler in root_logger.handlers:
                    if hasattr(handler, 'baseFilename'):  # File handler
                        handler.setLevel(logging.INFO)
                    else:  # Console handler
                        handler.setLevel(logging.WARNING)
                
                console.print()
                console.print("[green]✓ Logging reset to defaults[/green]")
                console.print("[dim]File: INFO level, Console: WARNING level[/dim]")
                logger.info("Logging configuration reset to defaults")
                
            except Exception as e:
                console.print(f"[red]Error resetting logging: {e}[/red]")
            
            console.print()
            Prompt.ask("Press Enter to continue", default="")
            
        elif choice == "5":
            # Show current loggers
            console.print()
            console.print("[bold]Current Loggers:[/bold]")
            
            table = Table(
                title="Logger Status",
                box=box.ROUNDED,
                title_style="bold blue",
                show_header=True,
                header_style="bold white on blue"
            )
            table.add_column("Logger Name", style="cyan", width=40)
            table.add_column("Level", width=12, justify="center")
            table.add_column("Handlers", width=10, justify="center")
            table.add_column("Disabled", width=10, justify="center")
            
            # Add root logger
            table.add_row(
                "ROOT",
                logging.getLevelName(root_logger.level),
                str(len(root_logger.handlers)),
                "No" if root_logger.disabled == 0 else "Yes"
            )
            
            # Add all other loggers
            logger_items = list(logging.Logger.manager.loggerDict.items())
            logger_items.sort(key=lambda x: x[0])  # Sort by name
            
            for name, logger_obj in logger_items[:20]:  # Limit to 20 loggers
                if isinstance(logger_obj, logging.Logger):
                    table.add_row(
                        name[-37:] if len(name) > 37 else name,
                        logging.getLevelName(logger_obj.level) if logger_obj.level != logging.NOTSET else "NOTSET",
                        str(len(logger_obj.handlers)),
                        "No" if logger_obj.disabled == 0 else "Yes"
                    )
            
            console.print(table)
            
            if len(logger_items) > 20:
                console.print(f"[dim]... and {len(logger_items) - 20} more loggers[/dim]")
            
            console.print()
            Prompt.ask("Press Enter to continue", default="")
        
        elif choice == "h":
            self._show_logging_config_help()
        elif choice == "q":
            return  # Exit back to main menu
    
    def _show_log_review_help(self):
        """Show help for log review functionality."""
        console.clear()
        self.show_header()
        
        console.print("[bold]Log Review Help[/bold]", style="blue")
        console.print()
        
        help_content = """
[bold cyan]Log Review Commands[/bold cyan]

[bold]r[/bold] - [green]Refresh logs[/green]
  • Reload and display the latest log entries
  • Useful to see new log entries after performing operations

[bold]c[/bold] - [yellow]Clear logs[/yellow]
  • Permanently delete all log entries from the file
  • [red]Warning:[/red] This action cannot be undone
  • You will be prompted for confirmation

[bold]h[/bold] - [cyan]Help[/cyan]
  • Show this help information

[bold]q[/bold] - [dim]Quit[/dim]
  • Return to the main menu

[bold]Enter[/bold] - [dim]Back[/dim]  
  • Return to the main menu

[bold cyan]About the Log Display[/bold cyan]

• [green]Date & Time:[/green] Shows when each log entry was created
• [green]Level:[/green] Log severity (INFO, WARNING, ERROR, etc.)
• [green]Logger:[/green] Which component generated the log entry
• [green]Message:[/green] The actual log message content

[bold cyan]Log Levels[/bold cyan]

• [blue]DEBUG:[/blue] Detailed diagnostic information
• [green]INFO:[/green] General operational messages
• [yellow]WARNING:[/yellow] Something unexpected happened
• [red]ERROR:[/red] A serious problem occurred
• [red]CRITICAL:[/red] Very serious error occurred

[bold cyan]Tips[/bold cyan]

• Log entries are shown in chronological order (oldest first)
• Use the [green]Debug Mode[/green] menu to enable DEBUG level logging
• Console only shows WARNING and ERROR levels for clean operation
• All levels are logged to the file for troubleshooting
        """
        
        console.print(Panel(help_content, box=box.ROUNDED, padding=(1, 2)))
        console.print()
        Prompt.ask("Press Enter to continue", default="")
    
    def _show_logging_config_help(self):
        """Show help for logging configuration functionality."""
        console.clear()
        self.show_header()
        
        console.print("[bold]Logging Configuration Help[/bold]", style="blue")
        console.print()
        
        help_content = """
[bold cyan]Logging Configuration Options[/bold cyan]

[bold]1[/bold] - [red]Disable/Enable logging completely[/red]
  • When disabled: No logs are written anywhere
  • When enabled: Logs go to file, warnings/errors to console

[bold]2[/bold] - [green]Enable debug mode (file logging)[/green]
  • Sets file logging to DEBUG level
  • Captures detailed diagnostic information
  • Console logging level unchanged

[bold]3[/bold] - [yellow]Enable verbose console[/yellow]  
  • Temporarily shows INFO messages on console
  • Useful for seeing detailed operation progress
  • File logging level unchanged

[bold]4[/bold] - [cyan]Reset to defaults[/cyan]
  • File logging: INFO level
  • Console logging: WARNING level
  • Recommended for normal operation

[bold]5[/bold] - [blue]Show current loggers[/blue]
  • Lists all active logging components
  • Shows their individual levels and handlers
  • Useful for debugging logging issues

[bold]h[/bold] - [cyan]Help[/cyan]
  • Show this help information

[bold]q[/bold] - [dim]Quit[/dim]
  • Return to the main menu

[bold cyan]Default Behavior[/bold cyan]

• [green]File Logging:[/green] INFO level - captures operation details
• [green]Console Logging:[/green] WARNING level - only shows user-relevant issues
• [green]HTTP Requests:[/green] Logged to file but not shown on console

[bold cyan]Session vs Persistent Changes[/bold cyan]

• All changes made here affect [yellow]current session only[/yellow]
• To make persistent changes, modify the configuration file
• Configuration file: [dim]~/.config/mcp-manager/config.toml[/dim]

[bold cyan]When to Use Each Option[/bold cyan]

• [green]Normal use:[/green] Keep defaults (option 4)
• [green]Troubleshooting:[/green] Enable debug mode (option 2)  
• [green]Detailed console output:[/green] Verbose console (option 3)
• [green]Clean operation:[/green] Disable logging (option 1)
        """
        
        console.print(Panel(help_content, box=box.ROUNDED, padding=(1, 2)))
        console.print()
        Prompt.ask("Press Enter to continue", default="")
    
    def _display_docker_gateway_test(self, test_result: Dict[str, Any]):
        """Display Docker gateway test results."""
        console.print("[bold]Docker Gateway Test:[/bold]")
        
        status = test_result.get("status", "unknown")
        if status == "success":
            console.print(f"  [green]✅ Docker Gateway Test: PASSED[/green]")
        elif status == "warning":
            console.print(f"  [yellow]⚠️ Docker Gateway Test: WARNING[/yellow]")
        else:
            console.print(f"  [red]❌ Docker Gateway Test: FAILED[/red]")
        
        # Show error if any
        error = test_result.get("error")
        if error:
            console.print(f"  [red]Error:[/red] {error}")
        
        # Show command that was tested
        command = test_result.get("command")
        if command:
            console.print(f"  [dim]Command:[/dim] {command}")
        
        # Show server results
        servers_tested = test_result.get("servers_tested", [])
        working_servers = test_result.get("working_servers", [])
        failed_servers = test_result.get("failed_servers", [])
        total_tools = test_result.get("total_tools", 0)
        
        if servers_tested:
            console.print(f"  [cyan]Servers tested:[/cyan] {', '.join(servers_tested)}")
        
        if working_servers:
            console.print(f"  [green]Working servers:[/green]")
            for server in working_servers:
                server_name = server.get("name", "Unknown")
                tools = server.get("tools", 0)
                console.print(f"    • {server_name}: {tools} tools")
        
        if failed_servers:
            console.print(f"  [red]Failed servers:[/red]")
            for server in failed_servers:
                server_name = server.get("name", "Unknown")
                error_msg = server.get("error", "Unknown error")
                console.print(f"    • {server_name}: {error_msg[:100]}...")  # Truncate long errors
        
        if total_tools > 0:
            console.print(f"  [cyan]Total tools available:[/cyan] {total_tools}")
        
        console.print()
    
    async def view_server_details(self, servers):
        """Display detailed information about a selected server including its tools."""
        if not servers:
            console.print("[yellow]No servers available[/yellow]")
            Prompt.ask("Press Enter to continue", default="")
            return
            
        # Select server
        server_choices = [f"{i}" for i in range(1, len(servers) + 1)]
        try:
            server_idx = Prompt.ask(
                f"Select server to view details (1-{len(servers)})",
                choices=server_choices
            )
            selected_server = servers[int(server_idx) - 1]
            
            # Get detailed server information
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task(f"Getting details for {selected_server.name}...", total=None)
                details = await self.manager.get_server_details(selected_server.name)
            
            console.clear()
            self.show_header()
            
            if not details:
                console.print(Panel(
                    f"[red]Could not get details for server: {selected_server.name}[/red]",
                    title="Error",
                    style="red",
                    box=box.ROUNDED
                ))
                console.print()
                Prompt.ask("Press Enter to continue", default="")
                return
            
            # Display server details
            console.print(Panel(
                f"[bold cyan]{details['name']}[/bold cyan]",
                title="Server Details",
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
            
            status_color = "green" if details['status'] == "enabled" else "red"
            info_table.add_row("Status", f"[{status_color}]{details['status']}[/{status_color}]")
            
            info_table.add_row("Command", details.get('command', 'N/A'))
            
            if details.get('args'):
                args_str = ' '.join(details['args']) if isinstance(details['args'], list) else str(details['args'])
                info_table.add_row("Arguments", args_str[:60] + "..." if len(args_str) > 60 else args_str)
            
            if details.get('env'):
                env_count = len(details['env']) if isinstance(details['env'], dict) else 0
                info_table.add_row("Environment", f"{env_count} variables")
            
            console.print(info_table)
            console.print()
            
            # Tools information
            tool_count = details.get('tool_count', 'Unknown')
            tools = details.get('tools', [])
            source = details.get('source', 'unknown')
            
            if tool_count != 'Unknown' and tool_count > 0:
                tools_panel_content = f"[bold green]{tool_count} tools available[/bold green]\n"
                tools_panel_content += f"[dim]Source: {source}[/dim]\n\n"
                
                if tools:
                    tools_panel_content += "[bold]Available Tools:[/bold]\n"
                    for i, tool in enumerate(tools, 1):
                        tool_name = tool.get('name', f'Tool {i}')
                        tool_desc = tool.get('description', 'No description available')
                        tools_panel_content += f"  {i}. [cyan]{tool_name}[/cyan]: {tool_desc}\n"
                else:
                    tools_panel_content += "[dim]Tool names not available - use Docker gateway for detailed tool information[/dim]\n"
                
                # Usage instructions
                if details['type'] == 'docker-desktop':
                    tools_panel_content += f"\n[bold]Usage in Claude Code:[/bold]\n"
                    tools_panel_content += f"[dim]These tools are available via the Docker Desktop MCP integration.\n"
                    tools_panel_content += f"Use commands like:[/dim]\n"
                    tools_panel_content += f"  • [yellow]@{details['name']} <tool-specific-command>[/yellow]\n"
                    tools_panel_content += f"  • [yellow]@{details['name']} <command> [arguments][/yellow]\n"
                    tools_panel_content += f"  • [yellow]@{details['name']} help[/yellow] - Show available commands\n"
                
                console.print(Panel(
                    tools_panel_content,
                    title="🔧 Tools & Usage",
                    style="green",
                    box=box.ROUNDED
                ))
            elif tool_count == 'Unknown':
                console.print(Panel(
                    f"[yellow]Tool information not available for this server type[/yellow]\n"
                    f"[dim]Source: {source}[/dim]\n\n"
                    f"[bold]General Usage in Claude Code:[/bold]\n"
                    f"[dim]Try using:[/dim] [yellow]@{details['name']} <command>[/yellow]",
                    title="🔧 Tools & Usage",
                    style="yellow",
                    box=box.ROUNDED
                ))
            else:
                console.print(Panel(
                    f"[red]No tools detected for this server[/red]\n"
                    f"[dim]This may indicate a configuration issue[/dim]",
                    title="⚠️ Tools Status",
                    style="red",
                    box=box.ROUNDED
                ))
            
            console.print()
            Prompt.ask("Press Enter to continue", default="")
            
        except (ValueError, IndexError):
            console.print("[red]Invalid selection[/red]")
            Prompt.ask("Press Enter to continue", default="")
    
    async def show_single_server_details(self, server: 'Server'):
        """Display detailed information for a single server (called via server number)."""
        console.clear()
        self.show_header()
        
        console.print(f"[bold blue]Server Details: {server.name}[/bold blue]")
        console.print()
        
        # Get detailed server information
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task(f"Getting details for {server.name}...", total=None)
            details = await self.manager.get_server_details(server.name)
        
        if not details:
            console.print(Panel(
                f"[red]Failed to get details for server '{server.name}'[/red]\n"
                f"[dim]The server may be misconfigured or unavailable.[/dim]",
                title="❌ Server Details Unavailable",
                style="red",
                box=box.ROUNDED
            ))
        else:
            # Basic server info
            info_content = f"[bold]Name:[/bold] {details['name']}\n"
            info_content += f"[bold]Type:[/bold] {details['type']}\n"
            info_content += f"[bold]Scope:[/bold] {details.get('scope', 'unknown')}\n"
            info_content += f"[bold]Status:[/bold] {'✅ Enabled' if details['status'] == 'enabled' else '❌ Disabled'}\n"
            info_content += f"[bold]Command:[/bold] {details.get('command', 'N/A')}\n"
            
            if details.get('args'):
                args_str = ' '.join(details['args']) if isinstance(details['args'], list) else str(details['args'])
                info_content += f"[bold]Arguments:[/bold] {args_str}\n"
            
            console.print(Panel(
                info_content,
                title="📋 Server Information",
                style="blue",
                box=box.ROUNDED
            ))
            console.print()
            
            # Tools information
            tool_count = details.get('tool_count', 'Unknown')
            tools = details.get('tools', [])
            source = details.get('source', 'unknown')
            
            if isinstance(tool_count, int) and tool_count > 0 and tools:
                tools_content = f"[bold]Available Tools ({tool_count}):[/bold]\n\n"
                for i, tool in enumerate(tools, 1):
                    tool_name = tool.get('name', f'Tool {i}')
                    tool_desc = tool.get('description', 'No description available')
                    # Limit description length for better display
                    if len(tool_desc) > 80:
                        tool_desc = tool_desc[:77] + "..."
                    tools_content += f"  [cyan]{i}. {tool_name}[/cyan]\n     {tool_desc}\n\n"
                
                # Usage instructions
                if details['type'] == 'docker-desktop':
                    tools_content += f"[bold]Usage in Claude Code:[/bold]\n"
                    tools_content += f"  • [yellow]@{details['name']} <tool-name> [args][/yellow]\n"
                    tools_content += f"  • [yellow]@{details['name']} help[/yellow] - Show available commands\n"
                else:
                    tools_content += f"[bold]Usage in Claude Code:[/bold]\n"
                    tools_content += f"  • [yellow]@{details['name']} <command>[/yellow]\n"
                
                console.print(Panel(
                    tools_content,
                    title="🔧 Tools & Usage",
                    style="green",
                    box=box.ROUNDED
                ))
            else:
                # Enhanced error display for Docker containers with fallback info
                error_content = f"[yellow]Tool information not available[/yellow]\n"
                
                # Show more descriptive source information
                if source == "docker_container_introspection_failed":
                    error_content += f"[dim]Reason: Docker container tool discovery failed[/dim]\n"
                elif source == "docker_failed":
                    error_content += f"[dim]Reason: Docker container communication failed[/dim]\n"
                else:
                    error_content += f"[dim]Source: {source}[/dim]\n"
                
                # Show fallback information if available
                fallback_info = details.get('fallback_info', {})
                docker_image = details.get('docker_image')
                
                if docker_image:
                    error_content += f"[dim]Docker Image: {docker_image}[/dim]\n"
                
                # Show likely tools if available
                likely_tools = fallback_info.get('likely_tools', [])
                if likely_tools:
                    error_content += f"\n[bold cyan]Likely Available Tools:[/bold cyan]\n"
                    for tool in likely_tools:
                        error_content += f"  • [green]{tool['name']}[/green]: {tool['description']}\n"
                
                error_content += f"\n[bold]General Usage:[/bold]\n"
                error_content += f"  • [yellow]@{details['name']} <command>[/yellow]\n"
                
                # Show suggestions if available
                suggestions = fallback_info.get('suggestions', [])
                if suggestions:
                    error_content += f"\n[bold cyan]Troubleshooting:[/bold cyan]\n"
                    for suggestion in suggestions:
                        error_content += f"  • [dim]{suggestion}[/dim]\n"
                
                console.print(Panel(
                    error_content.rstrip('\n'),
                    title="🔧 Tools & Usage", 
                    style="yellow",
                    box=box.ROUNDED
                ))
        
        console.print()
        Prompt.ask("Press Enter to continue", default="")
    
    async def configure_server(self):
        """Configure or reconfigure an MCP server that requires additional settings."""
        import os
        import yaml
        from pathlib import Path
        from rich.prompt import Prompt, Confirm
        
        while True:
            console.clear()
            self.show_header()
            
            console.print("[bold]Configure Server[/bold]", style="blue")
            console.print()
            
            # Get all servers
            try:
                servers = await self.manager.list_servers()
            except Exception as e:
                console.print(f"[red]Error loading servers: {e}[/red]")
                Prompt.ask("Press Enter to continue", default="")
                return
            
            if not servers:
                console.print(Panel(
                    "[yellow]No servers found[/yellow]\n\n"
                    "[dim]Add servers first before configuring them[/dim]",
                    title="No Servers",
                    style="yellow",
                    box=box.ROUNDED
                ))
                console.print()
                Prompt.ask("Press Enter to continue", default="")
                return
            
            # Show configurable servers
            configurable_servers = []
            for server in servers:
                server_name_lower = server.name.lower()
                if any(key in server_name_lower for key in ['filesystem', 'sqlite', 'postgres']):
                    configurable_servers.append(server)
            
            if not configurable_servers:
                console.print(Panel(
                    "[yellow]No configurable servers found[/yellow]\n\n"
                    "[dim]Currently supports: filesystem, SQLite, PostgreSQL servers[/dim]",
                    title="No Configurable Servers",
                    style="yellow",
                    box=box.ROUNDED
                ))
                console.print()
                Prompt.ask("Press Enter to continue", default="")
                return
            
            # Display configurable servers
            table = Table(
                title="Configurable Servers",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold magenta"
            )
            table.add_column("Index", style="cyan", width=6)
            table.add_column("Name", style="green")
            table.add_column("Type", style="blue", width=12)
            table.add_column("Status", justify="center", width=10)
            
            for i, server in enumerate(configurable_servers, 1):
                status_style = "green" if server.enabled else "red"
                status_text = "enabled" if server.enabled else "disabled"
                table.add_row(
                    str(i),
                    server.name,
                    server.server_type.value,
                    f"[{status_style}]{status_text}[/{status_style}]"
                )
            
            console.print(table)
            console.print()
            
            # Get user choice
            choices = [str(i) for i in range(1, len(configurable_servers) + 1)] + ["h", "q"]
            choice = Prompt.ask(
                "[bold cyan]Select server to configure[/bold cyan]",
                choices=choices,
                default="q"
            )
            
            if choice == "q":
                return
            elif choice == "h":
                console.print(Panel(
                    """[bold cyan]Server Configuration Help[/bold cyan]
                    
This menu allows you to configure servers that require additional settings:

[bold]Filesystem Servers:[/bold]
• Configure which directories are accessible
• Add/remove directory paths
• Supports multiple directories

[bold]SQLite Servers:[/bold] 
• Set database file path
• Create database if needed
• Configure connection settings

[bold]PostgreSQL Servers:[/bold]
• Set connection string
• Configure database details

[dim]Changes are saved to Docker MCP configuration files[/dim]""",
                    box=box.ROUNDED,
                    padding=(1, 2)
                ))
                console.print()
                Prompt.ask("Press Enter to continue", default="")
                continue
            
            # Configure selected server
            server_index = int(choice) - 1
            selected_server = configurable_servers[server_index]
            
            console.clear()
            self.show_header()
            
            console.print(f"[bold]Configuring: {selected_server.name}[/bold]", style="blue")
            console.print(f"[cyan]Type:[/cyan] {selected_server.server_type.value}")
            console.print()
            
            # Check if this is a Docker MCP server
            if 'docker' in selected_server.command.lower():
                docker_config_file = Path.home() / ".docker" / "mcp" / "config.yaml"
                
                # Read current config
                current_config = {}
                if docker_config_file.exists():
                    try:
                        with open(docker_config_file, 'r') as f:
                            docker_config = yaml.safe_load(f) or {}
                            current_config = docker_config.get(selected_server.name, {})
                    except Exception as e:
                        console.print(f"[yellow]Warning: Could not read Docker MCP config: {e}[/yellow]")
                
                # Show current configuration
                console.print("[bold]Current Configuration:[/bold]")
                if current_config:
                    config_text = yaml.dump({selected_server.name: current_config}, default_flow_style=False)
                    console.print(Panel(config_text, style="dim"))
                else:
                    console.print(Panel("[dim]No configuration found[/dim]", style="yellow"))
                console.print()
                
                # Configure based on server type
                if 'filesystem' in selected_server.name.lower():
                    console.print("[bold]Configure Filesystem Directories:[/bold]")
                    existing_paths = current_config.get('paths', [])
                    
                    if existing_paths:
                        console.print(f"[dim]Current paths: {', '.join(existing_paths)}[/dim]")
                    
                    if Confirm.ask("Configure directory paths?", default=True):
                        new_paths = []
                        console.print("[blue]Enter directory paths (empty to finish):[/blue]")
                        
                        # Show existing paths for modification
                        for i, path in enumerate(existing_paths):
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
                            # Save configuration
                            docker_config_file.parent.mkdir(parents=True, exist_ok=True)
                            
                            full_config = {}
                            if docker_config_file.exists():
                                try:
                                    with open(docker_config_file, 'r') as f:
                                        full_config = yaml.safe_load(f) or {}
                                except:
                                    pass
                            
                            full_config[selected_server.name] = {'paths': new_paths, 'env': {}}
                            
                            with open(docker_config_file, 'w') as f:
                                yaml.dump(full_config, f, default_flow_style=False)
                            
                            console.print(f"[green]✓ Updated paths: {new_paths}[/green]")
                            console.print(f"[green]📁 Configuration saved[/green]")
                        else:
                            console.print("[yellow]No paths specified - configuration unchanged[/yellow]")
                
                elif 'sqlite' in selected_server.name.lower():
                    console.print("[bold]Configure SQLite Database:[/bold]")
                    current_args = current_config.get('args', [])
                    current_path = "/tmp/mcp-database.db"
                    
                    if current_args and len(current_args) >= 2:
                        current_path = current_args[1]
                    
                    console.print(f"[dim]Current database: {current_path}[/dim]")
                    
                    if Confirm.ask("Configure database path?", default=True):
                        new_db_path = Prompt.ask("Database file path", default=current_path)
                        new_db_path = os.path.expanduser(new_db_path.strip())
                        
                        # Create directory and database
                        os.makedirs(os.path.dirname(new_db_path), exist_ok=True)
                        if not os.path.exists(new_db_path):
                            import sqlite3
                            with sqlite3.connect(new_db_path):
                                pass
                            console.print(f"[green]✓ Created database: {new_db_path}[/green]")
                        
                        # Save configuration
                        docker_config_file.parent.mkdir(parents=True, exist_ok=True)
                        
                        full_config = {}
                        if docker_config_file.exists():
                            try:
                                with open(docker_config_file, 'r') as f:
                                    full_config = yaml.safe_load(f) or {}
                            except:
                                pass
                        
                        full_config[selected_server.name] = {
                            'args': ['--db-path', new_db_path],
                            'env': {}
                        }
                        
                        with open(docker_config_file, 'w') as f:
                            yaml.dump(full_config, f, default_flow_style=False)
                        
                        console.print(f"[green]✓ Updated database path: {new_db_path}[/green]")
                        console.print(f"[green]📁 Configuration saved[/green]")
            
            else:
                # Non-Docker server
                console.print("[yellow]This server uses command-line arguments.[/yellow]")
                console.print(f"[dim]Current command: {selected_server.command}[/dim]")
                console.print(f"[dim]Current args: {selected_server.args}[/dim]")
                console.print()
                console.print("[blue]To reconfigure this server:[/blue]")
                console.print("1. Remove the server with 'Remove Server'")
                console.print("2. Add it again with 'Add Server' using new settings")
            
            console.print()
            if Confirm.ask("Configure another server?", default=False):
                continue
            else:
                return
    
    async def run(self):
        """Run the interactive menu."""
        try:
            while self.running:
                console.clear()
                self.show_header()
                
                choice = self.show_main_menu()
                
                if choice == "1":
                    await self.show_servers()
                elif choice == "2":
                    await self.add_server_interactive()
                elif choice == "3":
                    await self.discover_servers()
                elif choice == "4":
                    await self.install_package()
                elif choice == "5":
                    await self.cleanup_config()
                elif choice == "6":
                    await self.check_sync_status()
                elif choice == "7":
                    self.show_system_info()
                elif choice == "8":
                    await self.review_logs()
                elif choice == "9":
                    await self.toggle_debug_mode()
                elif choice == "h":
                    self.show_help()
                elif choice == "q":
                    self.running = False
        
        except KeyboardInterrupt:
            console.print("\n[yellow]Exiting...[/yellow]")
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            logger.exception("Menu application error")


def main():
    """Main entry point for the Rich-based menu."""
    app = RichMenuApp()
    asyncio.run(app.run())


if __name__ == "__main__":
    main()