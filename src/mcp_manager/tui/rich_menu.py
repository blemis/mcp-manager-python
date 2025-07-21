"""
Rich-based interactive menu for MCP Manager.

Provides a clean, reliable menu interface using Rich and Prompt Toolkit
instead of the problematic Textual framework.
"""

import asyncio
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
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)
console = Console()


class RichMenuApp:
    """Rich-based interactive menu for MCP Manager."""
    
    def __init__(self):
        self.manager = SimpleMCPManager()
        self.discovery = ServerDiscovery()
        self.running = True
    
    def show_header(self):
        """Display the application header."""
        console.clear()
        
        # Create header panel
        header_text = Text()
        header_text.append("MCP Manager", style="bold blue")
        header_text.append(f" v{__version__}", style="dim")
        header_text.append("\n")
        header_text.append("Complete MCP Server Management", style="italic")
        
        header_panel = Panel(
            Align.center(header_text),
            box=box.DOUBLE,
            style="blue",
            padding=(1, 2)
        )
        
        console.print(header_panel)
        console.print()
    
    def show_main_menu(self) -> str:
        """Display main menu and get user choice."""
        menu_options = [
            ("1", "Manage Servers", "View and manage your MCP servers", "🔧"),
            ("2", "Add Server", "Add a new MCP server manually", "➕"),
            ("3", "Discover & Install", "Find and install servers", "🔍"),
            ("4", "Install Package", "Install by package ID", "📦"),
            ("5", "Clean Configuration", "Fix broken configurations", "🧹"),
            ("6", "System Information", "View system status", "ℹ️"),
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
        table.add_column("Key", style="bold cyan", width=4)
        table.add_column("Icon", width=3)
        table.add_column("Option", style="bold white", width=20)
        table.add_column("Description", style="dim", width=35)
        
        for key, option, desc, icon in menu_options:
            table.add_row(f"[{key}]", icon, option, desc)
        
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
                console.print("[yellow]No servers configured[/yellow]")
                console.print()
            else:
                # Create servers table
                table = Table(
                    title=f"[bold]Configured Servers ({len(servers)})[/bold]",
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
            
            # Server management options
            actions = [
                ("r", "Refresh", "🔄"),
                ("a", "Add Server", "➕"),
                ("e", "Enable Server", "✅"),
                ("d", "Disable Server", "❌"),
                ("x", "Remove Server", "🗑️"),
                ("b", "Back to Main Menu", "⬅️"),
            ]
            
            action_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
            action_table.add_column("Key", style="bold cyan", width=4)
            action_table.add_column("Icon", width=3)
            action_table.add_column("Action", style="white")
            
            for key, action, icon in actions:
                action_table.add_row(f"[{key}]", icon, action)
            
            console.print(action_table)
            console.print()
            
            choice = Prompt.ask(
                "[bold cyan]Action[/bold cyan]",
                choices=[a[0] for a in actions],
                default="b"
            )
            
            if choice == "b":
                return
            elif choice == "r":
                continue  # Refresh by reloading the loop
            elif choice == "a":
                await self.add_server_interactive()
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
        
        query = Prompt.ask(
            "[cyan]Search for servers[/cyan] (e.g., filesystem, database, browser)",
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
        
        if not Confirm.ask("Proceed with installation?"):
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
    
    def show_help(self):
        """Display help information."""
        console.clear()
        self.show_header()
        
        console.print("[bold]Help & Usage[/bold]", style="blue")
        console.print()
        
        help_text = """
[bold cyan]MCP Manager[/bold cyan] - Complete MCP Server Management

[bold]Navigation:[/bold]
• Use number keys (1-6) or letters (h, q) to select options
• Type your choice and press Enter
• Most screens allow you to go back or cancel

[bold]Key Features:[/bold]
• [green]Manage Servers[/green] - View, enable, disable, and remove MCP servers
• [green]Add Server[/green] - Manually add custom MCP servers
• [green]Discover & Install[/green] - Find servers from NPM, Docker Hub, Docker Desktop
• [green]Install Package[/green] - Install by unique Install ID (e.g., dd-SQLite)
• [green]Clean Configuration[/green] - Fix broken MCP configurations
• [green]System Information[/green] - Check dependencies and system status

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
                    self.show_system_info()
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