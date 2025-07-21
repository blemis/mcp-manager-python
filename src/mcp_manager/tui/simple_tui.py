"""
Simple, clean TUI for MCP Manager using basic Python.

No fancy frameworks - just clean, keyboard-driven menus that actually work.
"""

import os
import sys
import asyncio
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.panel import Panel
from rich.columns import Columns
from rich import box

from mcp_manager.core.simple_manager import SimpleMCPManager
from mcp_manager.core.discovery import ServerDiscovery
from mcp_manager.core.models import Server, ServerType, ServerScope
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)
console = Console()


class SimpleTUI:
    """Simple, clean TUI that actually works."""
    
    def __init__(self):
        self.manager = SimpleMCPManager()
        self.discovery = ServerDiscovery()
        self.servers: List[Server] = []
        self.running = True
        
    def clear_screen(self):
        """Clear the terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
        
    def show_header(self):
        """Show clean header."""
        header = Panel(
            "[bold blue]MCP Manager[/bold blue]\n[dim]Simple Server Management[/dim]",
            style="blue",
            padding=(1, 2)
        )
        console.print(header)
        console.print()
    
    async def load_servers(self):
        """Load servers and update display."""
        try:
            self.servers = await self.manager.list_servers()
            return True
        except Exception as e:
            console.print(f"[red]Error loading servers: {e}[/red]")
            return False
    
    def show_servers(self):
        """Show servers in a clean table."""
        if not self.servers:
            console.print("[yellow]No servers configured[/yellow]")
            return
            
        table = Table(title="MCP Servers", box=box.ROUNDED)
        table.add_column("#", style="dim", width=3)
        table.add_column("Name", style="cyan", width=20)
        table.add_column("Status", width=10)
        table.add_column("Type", style="yellow", width=15)
        table.add_column("Command", style="dim", width=40)
        
        for i, server in enumerate(self.servers, 1):
            status = "[green]✓ Enabled[/green]" if server.enabled else "[red]✗ Disabled[/red]"
            cmd = server.command[:37] + "..." if len(server.command) > 40 else server.command
            table.add_row(
                str(i),
                server.name,
                status,
                server.server_type.value,
                cmd
            )
        
        console.print(table)
        console.print()
    
    def show_menu(self):
        """Show main menu options."""
        options = [
            ("1", "📋 List Servers", "View all configured servers"),
            ("2", "✅ Enable Server", "Enable a server"),
            ("3", "❌ Disable Server", "Disable a server"),
            ("4", "🗑️ Remove Server", "Remove a server"),
            ("5", "➕ Add Server", "Add new server (CLI)"),
            ("6", "🔍 Discover", "Find servers (CLI)"),
            ("7", "📦 Install Package", "Install by ID (CLI)"),
            ("8", "🧹 Cleanup", "Fix configurations"),
            ("9", "ℹ️ System Info", "Show system status"),
            ("m", "🔲 Multi-Select", "Bulk operations"),
            ("h", "❓ Help", "Show help"),
            ("q", "🚪 Quit", "Exit program"),
        ]
        
        # Create a clean menu
        menu_items = []
        for key, title, desc in options:
            menu_items.append(f"[bold cyan]{key}[/bold cyan] {title}")
        
        # Split into columns for better layout
        col1 = menu_items[:6]
        col2 = menu_items[6:]
        
        columns = Columns([
            Panel("\n".join(col1), title="Main Options", box=box.SIMPLE),
            Panel("\n".join(col2), title="Advanced", box=box.SIMPLE)
        ])
        
        console.print(columns)
        console.print()
    
    def get_server_choice(self, action: str = "select") -> Optional[Server]:
        """Get user's server choice."""
        if not self.servers:
            console.print("[yellow]No servers available[/yellow]")
            return None
            
        while True:
            try:
                choice = IntPrompt.ask(
                    f"Enter server number to {action} (1-{len(self.servers)}, 0 to cancel)",
                    default=0
                )
                
                if choice == 0:
                    return None
                elif 1 <= choice <= len(self.servers):
                    return self.servers[choice - 1]
                else:
                    console.print("[red]Invalid choice. Try again.[/red]")
            except:
                console.print("[red]Invalid input. Try again.[/red]")
    
    def get_multi_server_choice(self) -> List[Server]:
        """Get multiple server selections."""
        if not self.servers:
            console.print("[yellow]No servers available[/yellow]")
            return []
        
        console.print("[blue]Multi-Select Mode[/blue]")
        console.print("Enter server numbers separated by spaces (e.g. '1 3 5')")
        console.print("Or 'all' for all servers, 'none' to cancel")
        
        while True:
            try:
                choice = Prompt.ask("Select servers").strip()
                
                if choice.lower() == 'none':
                    return []
                elif choice.lower() == 'all':
                    return self.servers.copy()
                else:
                    # Parse numbers
                    numbers = [int(x.strip()) for x in choice.split() if x.strip()]
                    selected_servers = []
                    
                    for num in numbers:
                        if 1 <= num <= len(self.servers):
                            selected_servers.append(self.servers[num - 1])
                        else:
                            console.print(f"[yellow]Warning: Invalid server number {num}[/yellow]")
                    
                    if selected_servers:
                        return selected_servers
                    else:
                        console.print("[red]No valid servers selected. Try again.[/red]")
                        
            except ValueError:
                console.print("[red]Invalid input. Enter numbers separated by spaces.[/red]")
    
    async def enable_server(self):
        """Enable a single server."""
        self.show_servers()
        server = self.get_server_choice("enable")
        if not server:
            return
            
        try:
            await self.manager.enable_server(server.name)
            console.print(f"[green]✓ Enabled {server.name}[/green]")
        except Exception as e:
            console.print(f"[red]Failed to enable {server.name}: {e}[/red]")
    
    async def disable_server(self):
        """Disable a single server."""
        self.show_servers()
        server = self.get_server_choice("disable")
        if not server:
            return
            
        try:
            await self.manager.disable_server(server.name)
            console.print(f"[green]✓ Disabled {server.name}[/green]")
        except Exception as e:
            console.print(f"[red]Failed to disable {server.name}: {e}[/red]")
    
    async def remove_server(self):
        """Remove a single server."""
        self.show_servers()
        server = self.get_server_choice("remove")
        if not server:
            return
            
        if Confirm.ask(f"Really remove '{server.name}'? This cannot be undone"):
            try:
                await self.manager.remove_server(server.name)
                console.print(f"[green]✓ Removed {server.name}[/green]")
            except Exception as e:
                console.print(f"[red]Failed to remove {server.name}: {e}[/red]")
    
    async def multi_select_operations(self):
        """Handle multi-select operations."""
        await self.load_servers()
        self.show_servers()
        
        selected = self.get_multi_server_choice()
        if not selected:
            console.print("[dim]No servers selected[/dim]")
            return
        
        # Show selected servers
        console.print(f"[blue]Selected {len(selected)} servers:[/blue]")
        for server in selected:
            status = "✓" if server.enabled else "✗"
            console.print(f"  {status} {server.name}")
        console.print()
        
        # Multi-select menu
        while True:
            action = Prompt.ask(
                "Action: [E]nable all, [D]isable all, [R]emove all, [C]ancel",
                choices=['e', 'd', 'r', 'c'],
                default='c'
            ).lower()
            
            if action == 'c':
                break
            elif action == 'e':
                await self.bulk_enable(selected)
                break
            elif action == 'd':
                await self.bulk_disable(selected)
                break
            elif action == 'r':
                if Confirm.ask(f"Really remove {len(selected)} servers? This cannot be undone"):
                    await self.bulk_remove(selected)
                break
    
    async def bulk_enable(self, servers: List[Server]):
        """Enable multiple servers."""
        success_count = 0
        for server in servers:
            try:
                await self.manager.enable_server(server.name)
                console.print(f"[green]✓ Enabled {server.name}[/green]")
                success_count += 1
            except Exception as e:
                console.print(f"[red]✗ Failed to enable {server.name}: {e}[/red]")
        
        console.print(f"[blue]Enabled {success_count}/{len(servers)} servers[/blue]")
    
    async def bulk_disable(self, servers: List[Server]):
        """Disable multiple servers."""
        success_count = 0
        for server in servers:
            try:
                await self.manager.disable_server(server.name)
                console.print(f"[green]✓ Disabled {server.name}[/green]")
                success_count += 1
            except Exception as e:
                console.print(f"[red]✗ Failed to disable {server.name}: {e}[/red]")
        
        console.print(f"[blue]Disabled {success_count}/{len(servers)} servers[/blue]")
    
    async def bulk_remove(self, servers: List[Server]):
        """Remove multiple servers."""
        success_count = 0
        for server in servers:
            try:
                await self.manager.remove_server(server.name)
                console.print(f"[green]✓ Removed {server.name}[/green]")
                success_count += 1
            except Exception as e:
                console.print(f"[red]✗ Failed to remove {server.name}: {e}[/red]")
        
        console.print(f"[blue]Removed {success_count}/{len(servers)} servers[/blue]")
    
    async def cleanup_config(self):
        """Run configuration cleanup."""
        console.print("[blue]Running configuration cleanup...[/blue]")
        # This calls the existing CLI cleanup functionality
        from mcp_manager.cli.main import _cleanup_impl
        await _cleanup_impl(dry_run=False, no_backup=False)
    
    def show_system_info(self):
        """Show system information."""
        info = self.manager.get_system_info()
        
        table = Table(title="System Information", box=box.ROUNDED)
        table.add_column("Component", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Version", style="dim")
        
        table.add_row("Python", "[green]✓[/green]", info.python_version)
        table.add_row("Platform", "[green]✓[/green]", info.platform)
        
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
    
    def show_help(self):
        """Show help information."""
        help_text = """
[bold]MCP Manager - Simple TUI[/bold]

[bold cyan]Navigation:[/bold cyan]
• Use number keys (1-9) or letters (m, h, q) to select options
• Follow the prompts for each operation
• Type your choice and press Enter

[bold cyan]Multi-Select:[/bold cyan]
• Choose option 'm' for multi-select mode
• Enter server numbers: '1 3 5' for servers 1, 3, and 5
• Or 'all' to select all servers
• Then choose bulk action: Enable, Disable, or Remove

[bold cyan]Tips:[/bold cyan]
• Server list is refreshed automatically before operations
• Use Ctrl+C to cancel any operation
• All operations show clear success/error messages
"""
        console.print(Panel(help_text, box=box.ROUNDED))
    
    async def discover_servers(self):
        """Interactive server discovery with regex support."""
        console.print("[blue]🔍 Server Discovery[/blue]")
        console.print("Search for MCP servers with pattern support:")
        console.print("[dim]• Wildcards: 'aws*', 'file*', '?sql'[/dim]")
        console.print("[dim]• Regex: 'regex:^aws.*db$'[/dim]")
        console.print("[dim]• Simple text: 'filesystem'[/dim]")
        
        # Get search query from user
        query = Prompt.ask(
            "Enter search term (or press Enter for all servers)",
            default=""
        ).strip()
        
        if not query:
            query = None
            
        try:
            console.print("[dim]Searching for servers...[/dim]")
            results = await self.discovery.discover_servers(query=query, limit=20)
            
            if not results:
                console.print("[yellow]No servers found[/yellow]")
                return
            
            # Display results in a table
            table = Table(title=f"Found {len(results)} servers", show_header=True, header_style="bold blue")
            table.add_column("ID", style="cyan", width=3)
            table.add_column("Install ID", style="green", width=25)
            table.add_column("Type", style="yellow", width=10)
            table.add_column("Description", style="dim", width=40)
            
            # Import the same install ID generation logic from CLI
            from mcp_manager.cli.main import _generate_install_id
            
            for i, result in enumerate(results, 1):
                install_id = _generate_install_id(result)
                desc = result.description[:37] + "..." if result.description and len(result.description) > 40 else (result.description or "")
                table.add_row(str(i), install_id, result.server_type.value, desc)
            
            console.print(table)
            
            # Ask if user wants to install any
            install_choice = Prompt.ask(
                "\nEnter server number to install (or press Enter to skip)",
                default=""
            ).strip()
            
            if install_choice and install_choice.isdigit():
                choice_idx = int(install_choice) - 1
                if 0 <= choice_idx < len(results):
                    result = results[choice_idx]
                    install_id = _generate_install_id(result)
                    await self.install_server_by_id(install_id)
                else:
                    console.print("[red]Invalid selection[/red]")
                    
        except Exception as e:
            console.print(f"[red]Discovery failed: {e}[/red]")
    
    async def install_server_by_id(self, install_id: str):
        """Install a server using its install ID."""
        try:
            console.print(f"[blue]Installing[/blue] server with ID: [cyan]{install_id}[/cyan]")
            
            # Use the CLI logic but call it programmatically
            from mcp_manager.cli.main import cli_context
            discovery = cli_context.get_discovery()
            manager = cli_context.get_manager()
            
            # Search for the server
            results = await discovery.discover_servers(limit=200)
            from mcp_manager.cli.main import _generate_install_id
            
            target_result = None
            for result in results:
                if _generate_install_id(result) == install_id:
                    target_result = result
                    break
            
            if not target_result:
                console.print(f"[red]✗[/red] Install ID '{install_id}' not found")
                return
            
            # Create server name
            if target_result.server_type.value == "npm":
                server_name = install_id.replace("modelcontextprotocol-", "official-")
            elif target_result.server_type.value == "docker":
                server_name = install_id.replace("-", "_")
            elif target_result.server_type.value == "docker-desktop":
                server_name = install_id.replace("dd-", "")
            else:
                server_name = install_id
            
            # Check if server already exists
            existing_servers = await manager.list_servers()
            if any(s.name == server_name for s in existing_servers):
                if not Confirm.ask(f"Server '{server_name}' already exists. Replace it?"):
                    console.print("[dim]Installation cancelled[/dim]")
                    return
            
            # Install the server
            server = await manager.add_server(
                name=server_name,
                server_type=target_result.server_type,
                command=target_result.install_command,
                description=target_result.description,
                args=target_result.install_args or [],
            )
            console.print(f"[green]✓[/green] Installed server: {server.name}")
            console.print("[dim]Server is now active in Claude Code![/dim]")
            
        except Exception as e:
            console.print(f"[red]Installation failed: {e}[/red]")
    
    def call_cli_command(self, command: str, description: str):
        """Call a CLI command with instructions."""
        console.print(f"[blue]{description}[/blue]")
        
        if Confirm.ask("Run this command now?"):
            os.system(f"mcp-manager {command}")
    
    async def main_loop(self):
        """Main interactive loop."""
        while self.running:
            self.clear_screen()
            self.show_header()
            
            # Always refresh server list
            await self.load_servers()
            self.show_servers()
            
            self.show_menu()
            
            choice = Prompt.ask(
                "[bold cyan]Choose an option[/bold cyan]",
                default="1"
            ).lower().strip()
            
            try:
                if choice == '1':
                    # Just refresh (already done above)
                    input("\nPress Enter to continue...")
                elif choice == '2':
                    await self.enable_server()
                    input("\nPress Enter to continue...")
                elif choice == '3':
                    await self.disable_server()
                    input("\nPress Enter to continue...")
                elif choice == '4':
                    await self.remove_server()
                    input("\nPress Enter to continue...")
                elif choice == '5':
                    self.call_cli_command("add", "Add a new server manually")
                elif choice == '6':
                    await self.discover_servers()
                    input("\nPress Enter to continue...")
                elif choice == '7':
                    self.call_cli_command("install-package", "Install server by package ID")
                elif choice == '8':
                    await self.cleanup_config()
                    input("\nPress Enter to continue...")
                elif choice == '9':
                    self.show_system_info()
                    input("\nPress Enter to continue...")
                elif choice == 'm':
                    await self.multi_select_operations()
                    input("\nPress Enter to continue...")
                elif choice == 'h':
                    self.show_help()
                    input("\nPress Enter to continue...")
                elif choice == 'q':
                    self.running = False
                else:
                    console.print("[red]Invalid choice. Try again.[/red]")
                    input("Press Enter to continue...")
                    
            except KeyboardInterrupt:
                console.print("\n[yellow]Operation cancelled[/yellow]")
                input("Press Enter to continue...")
            except Exception as e:
                console.print(f"\n[red]Error: {e}[/red]")
                input("Press Enter to continue...")
    
    async def run(self):
        """Start the TUI."""
        try:
            await self.main_loop()
        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")


async def main():
    """Main entry point for simple TUI."""
    tui = SimpleTUI()
    await tui.run()


if __name__ == "__main__":
    asyncio.run(main())