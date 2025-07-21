"""
Interactive menu-based TUI for MCP Manager.

Provides a guided, menu-driven interface that launches when
mcp-manager is called without arguments.
"""

import asyncio
from typing import List, Optional, Any, Dict

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, Center, Grid
from textual.widgets import (
    Button, Header, Footer, Label, Static, 
    SelectionList, OptionList, Input, DataTable
)
from textual.binding import Binding
from textual.screen import Screen
from rich.text import Text

from mcp_manager import __version__
from mcp_manager.core.discovery import ServerDiscovery
from mcp_manager.core.simple_manager import SimpleMCPManager
from mcp_manager.core.models import Server, ServerScope, ServerType
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ConfirmScreen(Screen):
    """Screen for confirmation dialogs."""
    
    def __init__(self, message: str, title: str = "Confirm") -> None:
        super().__init__()
        self.message = message
        self.title = title
        
    def compose(self) -> ComposeResult:
        """Create confirmation dialog."""
        with Container(id="confirm-dialog"):
            yield Static(self.title, id="confirm-title")
            yield Static(self.message, id="confirm-message")
            with Horizontal(id="confirm-buttons"):
                yield Button("Yes", id="confirm-yes", variant="success")
                yield Button("No", id="confirm-no", variant="error")
    
    @on(Button.Pressed, "#confirm-yes")
    def on_confirm_yes(self) -> None:
        """Handle yes button."""
        self.dismiss(True)
    
    @on(Button.Pressed, "#confirm-no")    
    def on_confirm_no(self) -> None:
        """Handle no button."""
        self.dismiss(False)


class ServerListScreen(Screen):
    """Screen for displaying and managing servers."""
    
    # Use minimal CSS, let Textual handle the styling
    CSS = """
    .title-row {
        dock: top;
        height: 3;
        content-align: center middle;
        text-style: bold;
    }
    
    .actions-row {
        dock: bottom;
        height: 3;
        margin: 1;
    }
    
    .help-row {
        dock: bottom;
        height: 1;
        content-align: center middle;
        text-style: italic;
        margin: 0 1;
    }
    
    Button {
        margin: 0 1;
        height: 3;
        min-width: 18;
        border: none;
        text-style: bold;
        content-align: center middle;
    }
    
    Button.success {
        background: #059669;
        color: white;
    }
    
    Button.success:hover {
        background: #047857;
    }
    
    Button.warning {
        background: #d97706;
        color: white;
    }
    
    Button.warning:hover {
        background: #b45309;
    }
    
    Button.error {
        background: #dc2626;
        color: white;
    }
    
    Button.error:hover {
        background: #b91c1c;
    }
    
    Button.primary {
        background: #2563eb;
        color: white;
    }
    
    Button.primary:hover {
        background: #1d4ed8;
    }
    """
    
    BINDINGS = [
        Binding("e", "enable_server", "Enable Server"),
        Binding("d", "disable_server", "Disable Server"),
        Binding("r", "remove_server", "Remove Server"),
        Binding("space", "toggle_selection", "Toggle Selection"),
        Binding("ctrl+a", "select_all", "Select All"),
        Binding("ctrl+d", "deselect_all", "Deselect All"),
        Binding("b", "bulk_enable", "Bulk Enable"),
        Binding("n", "bulk_disable", "Bulk Disable"),
        Binding("x", "bulk_remove", "Bulk Remove"),
        Binding("escape", "back_to_menu", "Back"),
    ]
    
    def __init__(self, manager: SimpleMCPManager) -> None:
        super().__init__()
        self.manager = manager
        self.selected_server: Optional[Server] = None
        self.selected_servers: set = set()  # Track multiple selected server names
        self.all_servers: List[Server] = []  # Cache all servers for bulk operations
        
    def compose(self) -> ComposeResult:
        """Create server list interface."""
        yield Header()
        
        yield Static("📊 MCP Server Management", classes="title-row")
        
        # DataTable fills remaining space
        yield DataTable(id="server-table")
            
        # Action buttons at bottom
        with Horizontal(classes="actions-row"):
            yield Button("Enable [E] • Bulk [B]", id="enable-server", variant="success")
            yield Button("Disable [D] • Bulk [N]", id="disable-server", variant="warning")
            yield Button("Remove [R] • Bulk [X]", id="remove-server", variant="error")
            yield Button("← Back [Esc]", id="back-to-menu", variant="primary")
        
        # Help text for selection
        yield Static(
            "💡 [bold]Space[/bold]=select, [bold]Ctrl+A[/bold]=select all, [bold]Ctrl+D[/bold]=deselect all, [bold]B/N/X[/bold]=bulk enable/disable/remove",
            classes="help-row"
        )
    
    async def on_mount(self) -> None:
        """Initialize the screen."""
        await self.refresh_servers()
    
    async def refresh_servers(self) -> None:
        """Refresh the server table."""
        table = self.query_one("#server-table", DataTable)
        table.clear(columns=True)  # Clear both rows and columns
        table.add_columns("☑", "Name", "Scope", "Type", "Status", "Command")
        
        try:
            servers = await self.manager.list_servers()
            self.all_servers = servers  # Cache for bulk operations
            
            for server in servers:
                # Show selection indicator
                selected_indicator = "✓" if server.name in self.selected_servers else ""
                
                scope_icon = {
                    ServerScope.LOCAL: "🔒",
                    ServerScope.PROJECT: "🔄",
                    ServerScope.USER: "🌐",
                }.get(server.scope, "")
                
                status = "✅ Enabled" if server.enabled else "❌ Disabled"
                command_short = (server.command[:35] + "..." 
                               if len(server.command) > 35 else server.command)
                
                table.add_row(
                    selected_indicator,
                    server.name,
                    f"{scope_icon} {server.scope.value}",
                    server.server_type.value,
                    status,
                    command_short,
                    key=server.name
                )
        except Exception as e:
            self.notify(f"Error loading servers: {e}", severity="error")
    
    @on(DataTable.RowSelected, "#server-table")
    def on_server_selected(self, event: DataTable.RowSelected) -> None:
        """Handle server selection."""
        if event.row_key:
            server_name = str(event.row_key.value)
            # Find the server in our list
            self.load_selected_server_worker(server_name)
    
    @work(exclusive=True)
    async def load_selected_server_worker(self, server_name: str) -> None:
        """Worker to load the selected server details."""
        await self._load_selected_server(server_name)
    
    async def _load_selected_server(self, server_name: str) -> None:
        """Load the selected server details."""
        try:
            servers = await self.manager.list_servers()
            self.selected_server = next((s for s in servers if s.name == server_name), None)
            if self.selected_server:
                self.notify(f"Selected server: {server_name}", severity="information")
            else:
                self.notify(f"Server {server_name} not found", severity="error")
        except Exception as e:
            self.notify(f"Error loading server: {e}", severity="error")
    
    @on(Button.Pressed, "#enable-server")
    def on_enable_server(self) -> None:
        """Enable selected server."""
        self.enable_server_worker()
    
    @work(exclusive=True)
    async def enable_server_worker(self) -> None:
        """Worker method to enable selected server."""
        if not self.selected_server:
            # Try to get selected server from table cursor position as fallback
            table = self.query_one("#server-table", DataTable)
            if table.cursor_row is not None:
                try:
                    servers = await self.manager.list_servers()
                    if 0 <= table.cursor_row < len(servers):
                        self.selected_server = servers[table.cursor_row]
                        self.notify(f"Using cursor selection: {self.selected_server.name}", severity="information")
                except Exception:
                    pass
        
        if not self.selected_server:
            self.notify("No server selected. Please click on a server row first.", severity="warning")
            return
            
        try:
            await self.manager.enable_server(self.selected_server.name)
            await self.refresh_servers()
            self.notify(f"Enabled {self.selected_server.name}", severity="information")
        except Exception as e:
            self.notify(f"Error enabling server: {e}", severity="error")
    
    @on(Button.Pressed, "#disable-server")
    def on_disable_server(self) -> None:
        """Disable selected server."""
        self.disable_server_worker()
    
    @work(exclusive=True)
    async def disable_server_worker(self) -> None:
        """Worker method to disable selected server."""
        if not self.selected_server:
            # Try to get selected server from table cursor position as fallback
            table = self.query_one("#server-table", DataTable)
            if table.cursor_row is not None:
                try:
                    servers = await self.manager.list_servers()
                    if 0 <= table.cursor_row < len(servers):
                        self.selected_server = servers[table.cursor_row]
                        self.notify(f"Using cursor selection: {self.selected_server.name}", severity="information")
                except Exception:
                    pass
        
        if not self.selected_server:
            self.notify("No server selected. Please click on a server row first.", severity="warning")
            return
            
        try:
            await self.manager.disable_server(self.selected_server.name)
            await self.refresh_servers()
            self.notify(f"Disabled {self.selected_server.name}", severity="information")
        except Exception as e:
            self.notify(f"Error disabling server: {e}", severity="error")
    
    @on(Button.Pressed, "#remove-server")
    def on_remove_server(self) -> None:
        """Remove selected server."""
        self.remove_server_worker()
    
    @work(exclusive=True)
    async def remove_server_worker(self) -> None:
        """Worker method to remove selected server."""
        if not self.selected_server:
            # Try to get selected server from table cursor position as fallback
            table = self.query_one("#server-table", DataTable)
            if table.cursor_row is not None:
                # Get the server name from the table at cursor position
                try:
                    cell_key = table.get_cell_at(table.cursor_coordinate)
                    if cell_key:
                        servers = await self.manager.list_servers()
                        if 0 <= table.cursor_row < len(servers):
                            self.selected_server = servers[table.cursor_row]
                            self.notify(f"Using cursor selection: {self.selected_server.name}", severity="information")
                except Exception:
                    pass
        
        if not self.selected_server:
            self.notify("No server selected. Please click on a server row first.", severity="warning")
            return
            
        # Confirm removal
        confirmed = await self.app.push_screen_wait(
            ConfirmScreen(f"Remove server '{self.selected_server.name}'?", "Confirm Removal")
        )
        
        if confirmed:
            try:
                await self.manager.remove_server(self.selected_server.name)
                await self.refresh_servers()
                self.notify(f"Removed {self.selected_server.name}", severity="information")
                self.selected_server = None
            except Exception as e:
                self.notify(f"Error removing server: {e}", severity="error")
    
    @on(Button.Pressed, "#back-to-menu")
    def on_back_to_menu(self) -> None:
        """Return to main menu."""
        self.dismiss()
    
    # Action methods for keyboard shortcuts
    def action_enable_server(self) -> None:
        """Enable server via keyboard shortcut."""
        self.enable_server_worker()
    
    def action_disable_server(self) -> None:
        """Disable server via keyboard shortcut."""
        self.disable_server_worker()
    
    def action_remove_server(self) -> None:
        """Remove server via keyboard shortcut."""
        self.remove_server_worker()
    
    def action_back_to_menu(self) -> None:
        """Return to main menu via keyboard shortcut."""
        self.dismiss()
    
    def action_toggle_selection(self) -> None:
        """Toggle selection of current server."""
        table = self.query_one("#server-table", DataTable)
        if table.cursor_row is not None and self.all_servers:
            if 0 <= table.cursor_row < len(self.all_servers):
                server = self.all_servers[table.cursor_row]
                if server.name in self.selected_servers:
                    self.selected_servers.remove(server.name)
                    self.notify(f"Deselected: {server.name}", severity="information")
                else:
                    self.selected_servers.add(server.name)
                    self.notify(f"Selected: {server.name}", severity="information")
                # Refresh to update visual indicators
                asyncio.create_task(self.refresh_servers())
    
    def action_select_all(self) -> None:
        """Select all servers."""
        self.selected_servers = {server.name for server in self.all_servers}
        self.notify(f"Selected all {len(self.selected_servers)} servers", severity="information")
        asyncio.create_task(self.refresh_servers())
    
    def action_deselect_all(self) -> None:
        """Deselect all servers."""
        count = len(self.selected_servers)
        self.selected_servers.clear()
        self.notify(f"Deselected all {count} servers", severity="information")
        asyncio.create_task(self.refresh_servers())
    
    def action_bulk_enable(self) -> None:
        """Enable all selected servers."""
        if not self.selected_servers:
            self.notify("No servers selected. Use Space to select servers.", severity="warning")
            return
        self.bulk_enable_worker()
    
    def action_bulk_disable(self) -> None:
        """Disable all selected servers."""
        if not self.selected_servers:
            self.notify("No servers selected. Use Space to select servers.", severity="warning")
            return
        self.bulk_disable_worker()
    
    def action_bulk_remove(self) -> None:
        """Remove all selected servers."""
        if not self.selected_servers:
            self.notify("No servers selected. Use Space to select servers.", severity="warning")
            return
        self.bulk_remove_worker()
    
    @work(exclusive=True)
    async def bulk_enable_worker(self) -> None:
        """Worker to enable multiple servers."""
        selected_names = list(self.selected_servers)
        confirmed = await self.app.push_screen_wait(
            ConfirmScreen(f"Enable {len(selected_names)} selected servers?", "Confirm Bulk Enable")
        )
        
        if confirmed:
            success_count = 0
            for server_name in selected_names:
                try:
                    await self.manager.enable_server(server_name)
                    success_count += 1
                except Exception as e:
                    self.notify(f"Failed to enable {server_name}: {e}", severity="error")
            
            self.notify(f"Enabled {success_count}/{len(selected_names)} servers", severity="information")
            await self.refresh_servers()
    
    @work(exclusive=True)
    async def bulk_disable_worker(self) -> None:
        """Worker to disable multiple servers."""
        selected_names = list(self.selected_servers)
        confirmed = await self.app.push_screen_wait(
            ConfirmScreen(f"Disable {len(selected_names)} selected servers?", "Confirm Bulk Disable")
        )
        
        if confirmed:
            success_count = 0
            for server_name in selected_names:
                try:
                    await self.manager.disable_server(server_name)
                    success_count += 1
                except Exception as e:
                    self.notify(f"Failed to disable {server_name}: {e}", severity="error")
            
            self.notify(f"Disabled {success_count}/{len(selected_names)} servers", severity="information")
            await self.refresh_servers()
    
    @work(exclusive=True)
    async def bulk_remove_worker(self) -> None:
        """Worker to remove multiple servers."""
        selected_names = list(self.selected_servers)
        confirmed = await self.app.push_screen_wait(
            ConfirmScreen(f"Remove {len(selected_names)} selected servers? This cannot be undone.", "Confirm Bulk Remove")
        )
        
        if confirmed:
            success_count = 0
            for server_name in selected_names:
                try:
                    await self.manager.remove_server(server_name)
                    success_count += 1
                    # Remove from selected set as we process
                    self.selected_servers.discard(server_name)
                except Exception as e:
                    self.notify(f"Failed to remove {server_name}: {e}", severity="error")
            
            self.notify(f"Removed {success_count}/{len(selected_names)} servers", severity="information")
            await self.refresh_servers()


class DiscoveryScreen(Screen):
    """Screen for discovering and installing servers."""
    
    # Use minimal CSS, let Textual handle the styling
    CSS = """
    .search-row {
        dock: top;
        height: 3;
        margin: 1;
    }
    
    .help-row {
        dock: bottom;
        height: 3;
        margin: 1;
        content-align: center middle;
        text-style: italic;
    }
    
    Input {
        margin-right: 1;
        border: solid #374151;
        background: #1f2937;
        color: white;
        padding: 0 1;
    }
    
    Input:focus {
        border: solid #3b82f6;
    }
    
    Button {
        margin: 0 1;
        height: 3;
        min-width: 12;
        border: none;
        text-style: bold;
        content-align: center middle;
        background: #2563eb;
        color: white;
    }
    
    Button:hover {
        background: #1d4ed8;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+i", "install_selected", "Install Selected"),
        Binding("1", "install_number_1", "Install #1"),
        Binding("2", "install_number_2", "Install #2"),
        Binding("3", "install_number_3", "Install #3"),
        Binding("4", "install_number_4", "Install #4"),
        Binding("5", "install_number_5", "Install #5"),
        Binding("6", "install_number_6", "Install #6"),
        Binding("7", "install_number_7", "Install #7"),
        Binding("8", "install_number_8", "Install #8"),
        Binding("9", "install_number_9", "Install #9"),
        Binding("c", "clear_results", "Clear Results"),
        Binding("escape", "back_to_menu", "Back"),
    ]
    
    def __init__(self, manager: SimpleMCPManager, discovery: ServerDiscovery) -> None:
        super().__init__()
        self.manager = manager
        self.discovery = discovery
        self.selected_result: Optional[Any] = None
        self.discovery_results: List[Any] = []
        
    def compose(self) -> ComposeResult:
        """Create discovery interface."""
        yield Header()
        
        # Search row at top
        with Horizontal(classes="search-row"):
            yield Input(
                placeholder="Search for MCP servers (e.g., filesystem, database)... (Press Enter to search)",
                id="search-input"
            )
        
        # DataTable fills remaining space
        yield DataTable(id="discovery-table")
            
        # Help text at bottom
        yield Static(
            "💡 Press [bold]Enter[/bold] to search, [bold]1-9[/bold] to install by number, [bold]Ctrl+I[/bold] to install selected, [bold]C[/bold] to clear, [bold]Esc[/bold] to go back",
            classes="help-row"
        )
    
    def on_mount(self) -> None:
        """Initialize the screen."""
        # Setup the discovery table with initial columns
        table = self.query_one("#discovery-table", DataTable)
        table.add_columns("#", "Install ID", "Type", "Package", "Description")
        
        # Add a helpful initial message
        table.add_row("", "", "", "", "Enter a search term above and press Enter to find MCP servers", key="help")
        
        # Focus the search input
        search_input = self.query_one("#search-input", Input)
        search_input.focus()
    
    @on(Input.Submitted, "#search-input")
    def on_search_input_submitted(self) -> None:
        """Handle Enter key in search input."""
        self.search_worker()
    
    @work(exclusive=True)
    async def search_worker(self) -> None:
        """Worker method to search for servers."""
        search_input = self.query_one("#search-input", Input)
        query = search_input.value.strip()
        
        if not query:
            self.notify("Enter a search query", severity="warning")
            return
        
        try:
            self.notify("Searching servers...", severity="information")
            results = await self.discovery.discover_servers(query=query, limit=20)
            self.discovery_results = results
            
            # Populate table
            table = self.query_one("#discovery-table", DataTable)
            table.clear(columns=True)  # Clear both rows and columns
            table.add_columns("#", "Install ID", "Type", "Package", "Description")
            
            if not results:
                table.add_row("", "", "", "", f"No servers found for '{query}'. Try 'filesystem', 'database', or 'browser'", key="no-results")
                self.notify(f"No servers found for '{query}'", severity="warning")
                return
            
            for i, result in enumerate(results):
                # Create install ID (same logic as CLI)
                if result.server_type == ServerType.NPM:
                    install_id = result.package.replace("@", "").replace("/", "-").replace("server-", "")
                elif result.server_type == ServerType.DOCKER:
                    install_id = result.package.replace("/", "-")
                elif result.server_type == ServerType.DOCKER_DESKTOP:
                    install_id = f"dd-{result.name.replace('docker-desktop-', '')}"
                else:
                    install_id = result.name
                
                desc_short = (result.description[:35] + "..." 
                            if result.description and len(result.description) > 35 
                            else result.description or "No description")
                
                package_short = (result.package[:20] + "..." 
                               if result.package and len(result.package) > 20 
                               else result.package or "")
                
                # Show number for first 9 results
                number = str(i + 1) if i < 9 else ""
                
                table.add_row(
                    number,
                    install_id,
                    result.server_type.value,
                    package_short,
                    desc_short,
                    key=str(i)  # Use index as key
                )
            
            self.notify(f"Found {len(results)} servers for '{query}'", severity="information")
            
        except Exception as e:
            self.notify(f"Search failed: {e}", severity="error")
    
    @on(DataTable.RowSelected, "#discovery-table")
    def on_result_selected(self, event: DataTable.RowSelected) -> None:
        """Handle result selection."""
        if event.row_key and self.discovery_results:
            try:
                index = int(str(event.row_key.value))
                if 0 <= index < len(self.discovery_results):
                    self.selected_result = self.discovery_results[index]
                    # Provide feedback to user
                    result = self.selected_result
                    self.notify(f"Selected: {result.package}", severity="information")
            except (ValueError, IndexError):
                self.notify("Invalid selection", severity="warning")
    
    @on(Button.Pressed, "#install-server")
    def on_install_server(self) -> None:
        """Install selected server."""
        self.install_server_worker()
    
    @work(exclusive=True)
    async def install_server_worker(self) -> None:
        """Worker method to install selected server."""
        # Try to get selected result, fallback to cursor position
        if not self.selected_result:
            # Try to get current cursor position as fallback
            table = self.query_one("#discovery-table", DataTable)
            if table.cursor_row is not None and self.discovery_results:
                cursor_row = table.cursor_row
                if 0 <= cursor_row < len(self.discovery_results):
                    self.selected_result = self.discovery_results[cursor_row]
                    self.notify(f"Using cursor selection: {self.selected_result.package}", severity="information")
            
        if not self.selected_result:
            self.notify("Please select a server from the table first (click on a row)", severity="warning")
            return
        
        if not self.discovery_results:
            self.notify("No search results available", severity="warning")
            return
        
        # Create install ID
        result = self.selected_result
        if result.server_type == ServerType.NPM:
            install_id = result.package.replace("@", "").replace("/", "-").replace("server-", "")
            server_name = install_id.replace("modelcontextprotocol-", "official-")
        elif result.server_type == ServerType.DOCKER:
            install_id = result.package.replace("/", "-")
            server_name = install_id.replace("-", "_")
        elif result.server_type == ServerType.DOCKER_DESKTOP:
            install_id = f"dd-{result.name.replace('docker-desktop-', '')}"
            server_name = install_id.replace("dd-", "")
        else:
            install_id = result.name
            server_name = install_id
        
        # Confirm installation
        confirmed = await self.app.push_screen_wait(
            ConfirmScreen(
                f"Install '{result.package}' as '{server_name}'?",
                "Confirm Installation"
            )
        )
        
        if not confirmed:
            return
        
        try:
            self.notify(f"Installing {result.package}...", severity="information")
            
            server = await self.manager.add_server(
                name=server_name,
                server_type=result.server_type,
                command=result.install_command,
                description=result.description,
                args=result.install_args,
            )
            
            self.notify(f"✅ Installed {server.name}", severity="information")
            
        except Exception as e:
            self.notify(f"Installation failed: {e}", severity="error")
    
    # Action methods for keyboard shortcuts
    def action_install_selected(self) -> None:
        """Install the currently selected/highlighted server."""
        self.install_server_worker()
    
    def _install_by_number(self, number: int) -> None:
        """Install server by number (1-based)."""
        index = number - 1  # Convert to 0-based index
        if 0 <= index < len(self.discovery_results):
            self.selected_result = self.discovery_results[index]
            self.notify(f"Installing server #{number}: {self.selected_result.package}", severity="information")
            self.install_server_worker()
        else:
            self.notify(f"No server #{number}", severity="warning")
    
    def action_install_number_1(self) -> None: self._install_by_number(1)
    def action_install_number_2(self) -> None: self._install_by_number(2)
    def action_install_number_3(self) -> None: self._install_by_number(3)
    def action_install_number_4(self) -> None: self._install_by_number(4)
    def action_install_number_5(self) -> None: self._install_by_number(5)
    def action_install_number_6(self) -> None: self._install_by_number(6)
    def action_install_number_7(self) -> None: self._install_by_number(7)
    def action_install_number_8(self) -> None: self._install_by_number(8)
    def action_install_number_9(self) -> None: self._install_by_number(9)
    
    def action_clear_results(self) -> None:
        """Clear search results."""
        table = self.query_one("#discovery-table", DataTable)
        table.clear(columns=True)  # Clear both rows and columns
        table.add_columns("#", "Install ID", "Type", "Package", "Description")
        self.discovery_results = []
        self.selected_result = None
        table.add_row("", "", "", "", "Enter a search term above and press Enter to find MCP servers", key="help")
        self.notify("Results cleared", severity="information")
    
    def action_back_to_menu(self) -> None:
        """Return to main menu."""
        self.dismiss()


class AddServerScreen(Screen):
    """Screen for adding new servers."""
    
    CSS = """
    .form-container {
        align: center middle;
        width: 80;
        height: auto;
        border: solid #374151;
        background: #1f2937;
        padding: 2;
    }
    
    .form-field {
        margin: 1 0;
    }
    
    .form-buttons {
        height: 3;
        align: center middle;
        margin-top: 2;
    }
    
    Input {
        border: solid #374151;
        background: #111827;
        color: white;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    
    Input:focus {
        border: solid #3b82f6;
    }
    
    Label {
        color: #e5e7eb;
        text-style: bold;
        margin: 0 0 0 0;
    }
    
    SelectionList {
        border: solid #374151;
        background: #111827;
        height: 4;
    }
    
    Button {
        margin: 0 1;
        height: 3;
        min-width: 16;
        border: none;
        text-style: bold;
        content-align: center middle;
    }
    
    Button.success {
        background: #059669;
        color: white;
    }
    
    Button.success:hover {
        background: #047857;
    }
    
    Button.error {
        background: #dc2626;
        color: white;
    }
    
    Button.error:hover {
        background: #b91c1c;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+s", "add_server", "Add Server"),
        Binding("escape", "cancel", "Cancel"),
    ]
    
    def __init__(self, manager: SimpleMCPManager) -> None:
        super().__init__()
        self.manager = manager
        
    def compose(self) -> ComposeResult:
        """Create add server form."""
        yield Header()
        yield Static("➕ Add New MCP Server", id="screen-title")
        
        with Center():
            with Container(classes="form-container"):
                yield Label("Server Name:", classes="form-field")
                yield Input(placeholder="Enter server name...", id="server-name", classes="form-field")
                
                yield Label("Command:", classes="form-field")
                yield Input(placeholder="Enter command (e.g., npx @package/name)...", id="server-command", classes="form-field")
                
                yield Label("Description (optional):", classes="form-field")
                yield Input(placeholder="Enter description...", id="server-description", classes="form-field")
                
                yield Label("Server Type:", classes="form-field")
                yield SelectionList(
                    *[(t.value.title(), t.value) for t in ServerType],
                    id="server-type",
                    classes="form-field"
                )
                
                yield Label("Scope:", classes="form-field")  
                yield SelectionList(
                    *[(s.value.title(), s.value) for s in ServerScope],
                    id="server-scope",
                    classes="form-field"
                )
                
                with Horizontal(classes="form-buttons"):
                    yield Button("Add Server [Ctrl+S]", id="add-server", variant="success")
                    yield Button("Cancel [Esc]", id="cancel", variant="error")
    
    @on(Button.Pressed, "#add-server")
    def on_add_server(self) -> None:
        """Add the server."""
        self.add_server_worker()
    
    @work(exclusive=True)
    async def add_server_worker(self) -> None:
        """Worker method to add the server."""
        try:
            name = self.query_one("#server-name", Input).value.strip()
            command = self.query_one("#server-command", Input).value.strip()
            description = self.query_one("#server-description", Input).value.strip()
            
            server_type_list = self.query_one("#server-type", SelectionList)
            scope_list = self.query_one("#server-scope", SelectionList)
            
            if not name or not command:
                self.notify("Name and command are required", severity="error")
                return
            
            # Get selected values
            server_type = ServerType.CUSTOM
            if server_type_list.selected:
                server_type = ServerType(server_type_list.selected[0])
            
            scope = ServerScope.USER
            if scope_list.selected:
                scope = ServerScope(scope_list.selected[0])
            
            # Add the server
            await self.manager.add_server(
                name=name,
                command=command,
                description=description or None,
                server_type=server_type,
                scope=scope,
            )
            
            self.notify(f"✅ Added server: {name}", severity="information")
            self.dismiss(True)
            
        except Exception as e:
            self.notify(f"Error adding server: {e}", severity="error")
    
    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        """Cancel and return."""
        self.dismiss(False)
    
    # Action methods for keyboard shortcuts
    def action_add_server(self) -> None:
        """Add server via keyboard shortcut."""
        self.add_server_worker()
    
    def action_cancel(self) -> None:
        """Cancel via keyboard shortcut."""
        self.dismiss(False)


class MenuApp(App):
    """Main menu-driven MCP Manager application."""
    
    CSS = """
    Screen {
        background: #0f172a;
    }
    
    .menu-container {
        align: center middle;
        width: 70;
        height: auto;
        margin: 2;
        background: #1e293b;
        border: thick #334155;
        padding: 3;
    }
    
    .menu-title {
        height: 2;
        content-align: center middle;
        text-style: bold;
        color: #f1f5f9;
        margin: 0 0 1 0;
    }
    
    .menu-subtitle {
        height: 1;
        content-align: center middle;
        text-style: italic;
        color: #94a3b8;
        margin: 0 0 1 0;
    }
    
    .version-info {
        height: 1;
        content-align: center middle;
        color: #64748b;
        margin: 0 0 2 0;
    }
    
    .menu-grid {
        height: auto;
        grid-size: 2 4;
        grid-gutter: 1 1;
        margin: 1 0;
    }
    
    .menu-option {
        height: 2;
        width: 100%;
        margin: 0;
        border: solid #475569;
        text-style: bold;
        content-align: center middle;
        background: #334155;
        color: #f8fafc;
        text-opacity: 90%;
    }
    
    .menu-option:hover {
        background: #475569;
        border: solid #64748b;
        color: #ffffff;
        text-style: bold reverse;
        text-opacity: 100%;
    }
    
    .menu-option:focus {
        border: thick #3b82f6;
        background: #1e40af;
        color: white;
        text-style: bold reverse;
        text-opacity: 100%;
    }
    
    /* Semantic button variants */
    Button.primary {
        background: #2563eb;
        border: solid #3b82f6;
        color: white;
    }
    
    Button.primary:hover {
        background: #1d4ed8;
        border: solid #2563eb;
        text-style: bold reverse;
    }
    
    Button.success {
        background: #059669;
        border: solid #10b981;
        color: white;
    }
    
    Button.success:hover {
        background: #047857;
        border: solid #059669;
        text-style: bold reverse;
    }
    
    Button.warning {
        background: #d97706;
        border: solid #f59e0b;
        color: white;
    }
    
    Button.warning:hover {
        background: #b45309;
        border: solid #d97706;
        text-style: bold reverse;
    }
    
    Button.error {
        background: #dc2626;
        border: solid #ef4444;
        color: white;
    }
    
    Button.error:hover {
        background: #b91c1c;
        border: solid #dc2626;
        text-style: bold reverse;
    }
    
    Button.default {
        background: #6b7280;
        border: solid #9ca3af;
        color: white;
    }
    
    Button.default:hover {
        background: #4b5563;
        border: solid #6b7280;
        text-style: bold reverse;
    }
    """
    
    TITLE = f"MCP Manager v{__version__}"
    SUB_TITLE = "Interactive Menu"
    
    BINDINGS = [
        Binding("ctrl+c,q", "quit", "Quit", priority=True),
        Binding("escape", "quit", "Quit"),
        Binding("1", "manage_servers", "Manage Servers"),
        Binding("2", "add_server", "Add Server"),
        Binding("3", "discover_servers", "Discover & Install"),
        Binding("4", "install_package", "Install Package"),
        Binding("5", "cleanup_config", "Clean Configuration"),
        Binding("6", "system_info", "System Info"),
        Binding("h", "help", "Help"),
    ]
    
    def __init__(self) -> None:
        super().__init__()
        self.manager = SimpleMCPManager()
        self.discovery = ServerDiscovery()
    
    def compose(self) -> ComposeResult:
        """Create the main menu interface."""
        yield Header()
        
        with Center():
            with Container(classes="menu-container"):
                yield Static("MCP Manager", classes="menu-title")
                yield Static("Complete MCP Server Management", classes="menu-subtitle")
                yield Static(f"Version {__version__}", classes="version-info")
                
                # Use Grid for compact, modern layout
                with Grid(classes="menu-grid"):
                    yield Button(
                        "[1] Manage Servers",
                        id="manage-servers",
                        classes="menu-option",
                        variant="primary"
                    )
                    yield Button(
                        "[2] Add Server", 
                        id="add-server",
                        classes="menu-option",
                        variant="success"
                    )
                    yield Button(
                        "[3] Discover & Install",
                        id="discover-servers", 
                        classes="menu-option",
                        variant="success"
                    )
                    yield Button(
                        "[4] Install Package",
                        id="install-package",
                        classes="menu-option",
                        variant="success"
                    )
                    yield Button(
                        "[5] Clean Config",
                        id="cleanup-config",
                        classes="menu-option", 
                        variant="warning"
                    )
                    yield Button(
                        "[6] System Info",
                        id="system-info",
                        classes="menu-option",
                        variant="default"
                    )
                    yield Button(
                        "[H] Help",
                        id="help-menu",
                        classes="menu-option",
                        variant="default"
                    )
                    yield Button(
                        "[Q] Exit",
                        id="exit-app",
                        classes="menu-option",
                        variant="error"
                    )
        
        yield Footer()
    
    async def on_mount(self) -> None:
        """Initialize the application."""
        logger.debug("Menu TUI application started")
        self.notify("Welcome to MCP Manager! Select an option or use number keys.", severity="information")
    
    # Action methods for keyboard shortcuts
    async def action_manage_servers(self) -> None:
        """Open server management screen."""
        await self.push_screen(ServerListScreen(self.manager))
    
    async def action_add_server(self) -> None:
        """Open add server screen."""
        await self.push_screen(AddServerScreen(self.manager))
    
    async def action_discover_servers(self) -> None:
        """Open server discovery screen."""
        await self.push_screen(DiscoveryScreen(self.manager, self.discovery))
    
    async def action_install_package(self) -> None:
        """Install package by ID."""
        # Simple input dialog for install ID
        install_id = await self._get_input("Enter Install ID:", "Install Package")
        if install_id:
            await self._install_package_by_id(install_id.strip())
    
    async def action_cleanup_config(self) -> None:
        """Run configuration cleanup."""
        confirmed = await self.push_screen_wait(
            ConfirmScreen(
                "Clean up problematic MCP configurations?\n"
                "This will create a backup before making changes.",
                "Confirm Cleanup"
            )
        )
        
        if confirmed:
            try:
                self.notify("Cleaning up configurations...", severity="information")
                # Import the cleanup function from CLI
                from mcp_manager.cli.main import _cleanup_impl
                await _cleanup_impl(dry_run=False, no_backup=False)
                self.notify("✅ Configuration cleanup completed", severity="information")
            except Exception as e:
                self.notify(f"Cleanup failed: {e}", severity="error")
    
    async def action_system_info(self) -> None:
        """Show system information."""
        try:
            info = self.manager.get_system_info()
            
            # Create a detailed info display
            info_text = f"""System Information:
            
Python: {info.python_version}
Platform: {info.platform}
Config Directory: {info.config_dir}
Log File: {info.log_file or 'None'}

Dependencies:
Claude CLI: {'✅' if info.claude_cli_available else '❌'} {info.claude_cli_version or 'Not available'}
NPM: {'✅' if info.npm_available else '❌'} {info.npm_version or 'Not available'}
Docker: {'✅' if info.docker_available else '❌'} {info.docker_version or 'Not available'}
Git: {'✅' if info.git_available else '❌'} {info.git_version or 'Not available'}
"""
            
            # Simple info screen using confirm dialog
            await self.push_screen_wait(ConfirmScreen(info_text, "System Information"))
            
        except Exception as e:
            self.notify(f"Error getting system info: {e}", severity="error")
    
    async def action_help(self) -> None:
        """Show help information."""
        help_text = """MCP Manager Help

Keyboard Shortcuts:
• 1 - Manage Servers
• 2 - Add Server  
• 3 - Discover & Install
• 4 - Install Package
• 5 - Clean Configuration
• 6 - System Information
• H - This help
• Q/Ctrl+C/ESC - Quit

Features:
• Manage MCP servers for Claude Code
• Discover servers from NPM, Docker Hub, Docker Desktop
• Install servers with unique Install IDs
• Clean up problematic configurations
• Full CLI functionality in interactive mode

Navigation:
• Use mouse clicks or number keys
• ESC returns to previous screen
• Follow on-screen prompts
"""
        await self.push_screen_wait(ConfirmScreen(help_text, "Help & Usage"))
    
    # Button event handlers
    @on(Button.Pressed, "#manage-servers")
    def on_manage_servers(self) -> None:
        """Open server management screen."""
        self.manage_servers_worker()
    
    @work(exclusive=True)
    async def manage_servers_worker(self) -> None:
        """Worker to open server management screen."""
        await self.action_manage_servers()
    
    @on(Button.Pressed, "#add-server")
    def on_add_server(self) -> None:
        """Open add server screen."""
        self.add_server_menu_worker()
    
    @work(exclusive=True)
    async def add_server_menu_worker(self) -> None:
        """Worker to open add server screen."""
        await self.action_add_server()
    
    @on(Button.Pressed, "#discover-servers")
    def on_discover_servers(self) -> None:
        """Open server discovery screen."""
        self.discover_servers_worker()
    
    @work(exclusive=True)
    async def discover_servers_worker(self) -> None:
        """Worker to open server discovery screen."""
        await self.action_discover_servers()
    
    @on(Button.Pressed, "#install-package")
    def on_install_package(self) -> None:
        """Install package by ID."""
        self.install_package_worker()
    
    @work(exclusive=True)
    async def install_package_worker(self) -> None:
        """Worker to install package by ID."""
        await self.action_install_package()
    
    @on(Button.Pressed, "#cleanup-config")
    def on_cleanup_config(self) -> None:
        """Run configuration cleanup."""
        self.cleanup_config_worker()
    
    @work(exclusive=True)
    async def cleanup_config_worker(self) -> None:
        """Worker to run configuration cleanup."""
        await self.action_cleanup_config()
    
    @on(Button.Pressed, "#system-info")
    def on_system_info(self) -> None:
        """Show system information."""
        self.system_info_worker()
    
    @work(exclusive=True)
    async def system_info_worker(self) -> None:
        """Worker to show system information."""
        await self.action_system_info()
    
    @on(Button.Pressed, "#help-menu")
    def on_help_menu(self) -> None:
        """Show help information."""
        self.help_menu_worker()
    
    @work(exclusive=True)
    async def help_menu_worker(self) -> None:
        """Worker to show help information."""
        await self.action_help()
    
    @on(Button.Pressed, "#exit-app")
    def on_exit_app(self) -> None:
        """Exit the application."""
        self.exit()
    
    async def _get_input(self, prompt: str, title: str) -> Optional[str]:
        """Get input from user using a simple input screen."""
        # Create a simple input screen
        class InputScreen(Screen):
            def __init__(self, prompt: str, title: str):
                super().__init__()
                self.prompt = prompt
                self.title = title
            
            def compose(self) -> ComposeResult:
                with Center():
                    with Container(classes="form-container"):
                        yield Static(self.title, classes="menu-title")
                        yield Label(self.prompt)
                        yield Input(id="user-input")
                        with Horizontal(classes="form-buttons"):
                            yield Button("OK", id="ok", variant="success")
                            yield Button("Cancel", id="cancel", variant="error")
            
            @on(Button.Pressed, "#ok")
            def on_ok(self) -> None:
                value = self.query_one("#user-input", Input).value
                self.dismiss(value)
            
            @on(Button.Pressed, "#cancel")
            def on_cancel(self) -> None:
                self.dismiss(None)
        
        return await self.push_screen_wait(InputScreen(prompt, title))
    
    async def _install_package_by_id(self, install_id: str) -> None:
        """Install a package by its install ID."""
        try:
            self.notify(f"Searching for install ID: {install_id}", severity="information")
            
            # Search for servers to find the one with matching install_id
            results = await self.discovery.discover_servers(limit=100)
            
            target_result = None
            for result in results:
                # Recreate install_id logic to match
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
                self.notify(f"Install ID '{install_id}' not found", severity="error")
                return
            
            # Create unique server name to avoid conflicts
            if target_result.server_type == ServerType.NPM:
                server_name = install_id.replace("modelcontextprotocol-", "official-")
            elif target_result.server_type == ServerType.DOCKER:
                server_name = install_id.replace("-", "_")
            elif target_result.server_type == ServerType.DOCKER_DESKTOP:
                server_name = install_id.replace("dd-", "")
            else:
                server_name = install_id
            
            # Confirm installation
            confirmed = await self.push_screen_wait(
                ConfirmScreen(
                    f"Install '{target_result.package}' as '{server_name}'?",
                    "Confirm Installation"
                )
            )
            
            if confirmed:
                # Install the server
                server = await self.manager.add_server(
                    name=server_name,
                    server_type=target_result.server_type,
                    command=target_result.install_command,
                    description=target_result.description,
                    args=target_result.install_args,
                )
                self.notify(f"✅ Installed {server.name}", severity="information")
            
        except Exception as e:
            self.notify(f"Installation failed: {e}", severity="error")


def main() -> None:
    """Main entry point for the menu-driven TUI."""
    app = MenuApp()
    app.run()


if __name__ == "__main__":
    main()