"""
Main TUI application for MCP Manager.

Provides modern terminal user interface using Textual with
professional styling and interactive components.
"""

import asyncio
from typing import List, Optional

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button, DataTable, Footer, Header, Input, Label, 
    SelectionList, Static, Switch, TabbedContent, TabPane
)
from textual.binding import Binding

from mcp_manager import __version__
from mcp_manager.core.discovery import ServerDiscovery
from mcp_manager.core.simple_manager import SimpleMCPManager
from mcp_manager.core.models import Server, ServerScope, ServerType
from mcp_manager.tui.widgets import ServerDetailWidget, SystemInfoWidget
from mcp_manager.tui.screens import AddServerScreen, EditServerScreen, HelpScreen, ConfirmDialog
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class MCPManagerApp(App):
    """Main MCP Manager TUI application."""
    
    CSS = """
    .title {
        dock: top;
        height: 3;
        background: $accent;
        color: $text;
        content-align: center middle;
        text-style: bold;
    }
    
    .sidebar {
        dock: left;
        width: 30;
        background: $surface;
        border-right: solid $primary;
    }
    
    .content {
        background: $background;
    }
    
    .server-table {
        height: 100%;
        border: solid $primary;
    }
    
    .action-bar {
        dock: bottom;
        height: 3;
        background: $surface;
    }
    
    .status-bar {
        dock: bottom;
        height: 1;
        background: $accent;
        color: $text;
    }
    
    Button {
        margin: 1;
        min-width: 12;
    }
    
    Button.-primary {
        background: $primary;
        color: $text;
    }
    
    Button.-secondary {
        background: $secondary;
        color: $text;
    }
    
    Button.-success {
        background: $success;
        color: $text;
    }
    
    Button.-warning {
        background: $warning;
        color: $text;
    }
    
    Button.-error {
        background: $error;
        color: $text;
    }
    
    .form-container {
        background: $surface;
        border: solid $primary;
        padding: 1;
        margin: 1;
    }
    
    .form-field {
        margin: 1 0;
    }
    
    Input {
        margin: 1 0;
    }
    
    SelectionList {
        height: 10;
        border: solid $primary;
    }
    """
    
    TITLE = f"MCP Manager v{__version__}"
    SUB_TITLE = "Enterprise MCP Server Management"
    
    BINDINGS = [
        Binding("ctrl+c,q", "quit", "Quit", priority=True),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("f1", "help", "Help"),
        Binding("f2", "add_server", "Add Server"),
        Binding("f3", "discover", "Discover"),
        Binding("f4", "system_info", "System Info"),
        Binding("delete", "remove_server", "Remove"),
        Binding("space", "toggle_server", "Enable/Disable"),
        Binding("enter", "edit_server", "Edit"),
    ]
    
    def __init__(self):
        super().__init__()
        self.manager = SimpleMCPManager()
        self.discovery = ServerDiscovery()
        self.selected_server: Optional[Server] = None
        
    def compose(self) -> ComposeResult:
        """Create the application layout."""
        yield Header()
        
        with Container():
            yield Static(self.TITLE, classes="title")
            
            with TabbedContent(initial="servers"):
                with TabPane("Servers", id="servers"):
                    yield from self._create_servers_tab()
                    
                with TabPane("Discovery", id="discovery"):
                    yield from self._create_discovery_tab()
                    
                with TabPane("System", id="system"):
                    yield SystemInfoWidget(self.manager)
                    
        yield Footer()
        
    def _create_servers_tab(self) -> ComposeResult:
        """Create the servers management tab."""
        with Horizontal():
            with Vertical(classes="sidebar"):
                yield Label("Server Actions", classes="sidebar-title")
                yield Button("Add Server", id="add-server", classes="-primary")
                yield Button("Remove Server", id="remove-server", classes="-error")
                yield Button("Enable Server", id="enable-server", classes="-success")
                yield Button("Disable Server", id="disable-server", classes="-warning")
                yield Button("Sync to Claude", id="sync-claude", classes="-secondary")
                yield Button("Refresh", id="refresh", classes="-secondary")
                
            with Vertical(classes="content"):
                yield self._create_server_table()
                
    def _create_discovery_tab(self) -> ComposeResult:
        """Create the server discovery tab."""
        with Vertical():
            with Horizontal(classes="form-container"):
                yield Label("Search Servers:")
                yield Input(placeholder="Enter search query...", id="search-input")
                yield Button("Search", id="search-button", classes="-primary")
                
            yield DataTable(id="discovery-table", classes="server-table")
            
            with Horizontal(classes="action-bar"):
                yield Button("Install Selected", id="install-server", classes="-success")
                yield Button("Clear Results", id="clear-results", classes="-secondary")
                
    def _create_server_table(self) -> DataTable:
        """Create the servers data table."""
        table = DataTable(id="server-table", classes="server-table")
        table.add_columns("Name", "Scope", "Type", "Status", "Command")
        asyncio.create_task(self._populate_server_table(table))
        return table
        
    async def _populate_server_table(self, table: DataTable) -> None:
        """Populate the server table with data."""
        table.clear()
        servers = await self.manager.list_servers()
        
        for server in servers:
            scope_icon = {
                ServerScope.LOCAL: "🔒",
                ServerScope.PROJECT: "🔄",
                ServerScope.USER: "🌐",
            }.get(server.scope, "")
            
            status = "✅ Enabled" if server.enabled else "❌ Disabled"
            command_short = server.command[:30] + "..." if len(server.command) > 30 else server.command
            
            table.add_row(
                server.name,
                f"{scope_icon} {server.scope.value}",
                server.server_type.value,
                status,
                command_short,
                key=server.name
            )
            
    async def on_mount(self) -> None:
        """Initialize the application."""
        logger.info("TUI application started")
        await self.refresh_servers()
        
    def action_refresh(self) -> None:
        """Refresh server data."""
        asyncio.create_task(self.refresh_servers())
        self.notify("Servers refreshed", severity="information")
        
    async def refresh_servers(self) -> None:
        """Refresh the server table."""
        table = self.query_one("#server-table", DataTable)
        await self._populate_server_table(table)
        
    @on(DataTable.RowSelected, "#server-table")
    async def on_server_selected(self, event: DataTable.RowSelected) -> None:
        """Handle server selection."""
        if event.row_key:
            server_name = str(event.row_key.value)
            servers = await self.manager.list_servers()
            self.selected_server = next((s for s in servers if s.name == server_name), None)
            
    @on(Button.Pressed, "#add-server")
    async def action_add_server(self) -> None:
        """Add a new server."""
        result = await self.push_screen_wait(AddServerScreen())
        if result:
            try:
                server = await self.manager.add_server(**result)
                await self.refresh_servers()
                self.notify(f"Added server: {server.name}", severity="information")
            except Exception as e:
                self.notify(f"Error adding server: {e}", severity="error")
        
    @on(Button.Pressed, "#remove-server")
    async def on_remove_server(self) -> None:
        """Remove selected server."""
        if not self.selected_server:
            self.notify("No server selected", severity="warning")
            return
            
        confirmed = await self.push_screen_wait(
            ConfirmDialog(f"Remove server '{self.selected_server.name}'?", "Confirm Removal")
        )
        
        if confirmed:
            try:
                await self.manager.remove_server(self.selected_server.name)
                await self.refresh_servers()
                self.notify(f"Removed server: {self.selected_server.name}", severity="information")
                self.selected_server = None
            except Exception as e:
                self.notify(f"Error removing server: {e}", severity="error")
            
    @on(Button.Pressed, "#enable-server")
    async def on_enable_server(self) -> None:
        """Enable selected server."""
        if not self.selected_server:
            self.notify("No server selected", severity="warning")
            return
            
        try:
            await self.manager.enable_server(self.selected_server.name)
            await self.refresh_servers()
            self.notify(f"Enabled server: {self.selected_server.name}", severity="information")
        except Exception as e:
            self.notify(f"Error enabling server: {e}", severity="error")
            
    @on(Button.Pressed, "#disable-server")
    async def on_disable_server(self) -> None:
        """Disable selected server."""
        if not self.selected_server:
            self.notify("No server selected", severity="warning")
            return
            
        try:
            await self.manager.disable_server(self.selected_server.name)
            await self.refresh_servers()
            self.notify(f"Disabled server: {self.selected_server.name}", severity="information")
        except Exception as e:
            self.notify(f"Error disabling server: {e}", severity="error")
            
    @on(Button.Pressed, "#sync-claude")
    def on_sync_claude(self) -> None:
        """Sync configuration with Claude CLI."""
        # SimpleMCPManager works directly with Claude's internal state - no sync needed
        self.notify("MCP Manager works directly with Claude's internal state - no sync needed", severity="information")
            
    @on(Button.Pressed, "#refresh")
    def on_refresh_button(self) -> None:
        """Handle refresh button."""
        self.action_refresh()
        
    @on(Button.Pressed, "#search-button")
    async def on_search_servers(self) -> None:
        """Search for available servers."""
        search_input = self.query_one("#search-input", Input)
        query = search_input.value.strip()
        
        if not query:
            self.notify("Enter a search query", severity="warning")
            return
            
        try:
            self.notify("Searching servers...", severity="information")
            results = await self.discovery.discover_servers(query=query, limit=20)
            
            # Populate discovery table
            table = self.query_one("#discovery-table", DataTable)
            table.clear()
            table.add_columns("Name", "Type", "Package", "Description")
            
            for result in results:
                desc_short = result.description[:40] + "..." if result.description and len(result.description) > 40 else result.description or ""
                table.add_row(
                    result.name,
                    result.server_type.value,
                    result.package,
                    desc_short,
                    key=result.name
                )
                
            self.notify(f"Found {len(results)} servers", severity="information")
            
        except Exception as e:
            self.notify(f"Search failed: {e}", severity="error")
            
    async def action_help(self) -> None:
        """Show help information."""
        help_text = """
# MCP Manager Help

## Keyboard Shortcuts
- **Ctrl+C / Q**: Quit application
- **Ctrl+R**: Refresh servers
- **F1**: Show this help
- **F2**: Add new server
- **F3**: Discover servers
- **F4**: System information
- **Delete**: Remove selected server
- **Space**: Toggle server enable/disable
- **Enter**: Edit selected server

## Server Management
- Use the sidebar buttons or keyboard shortcuts
- Select a server in the table first
- Changes are automatically saved
- Sync with Claude CLI to apply changes

## Discovery
- Search for available MCP servers
- Install servers from NPM or Docker
- Filter by type and keywords

## Scopes
- 🔒 **Local**: Private to your user
- 🔄 **Project**: Shared via git
- 🌐 **User**: Global configuration
        """
        await self.push_screen_wait(HelpScreen(help_text))
    
    async def edit_server(self, server: Server) -> None:
        """Edit a server."""
        server_data = {
            "name": server.name,
            "command": server.command,
            "scope": server.scope.value,
            "server_type": server.server_type.value,
            "description": server.description or "",
            "enabled": server.enabled,
        }
        
        result = await self.push_screen_wait(EditServerScreen(server_data))
        if result:
            try:
                await self.manager.remove_server(server.name)
                await self.manager.add_server(**result)
                await self.refresh_servers()
                self.notify(f"Updated server: {server.name}", severity="information")
            except Exception as e:
                self.notify(f"Error updating server: {e}", severity="error")
        
    def action_edit_server(self) -> None:
        """Edit selected server."""
        if self.selected_server:
            asyncio.create_task(self.edit_server(self.selected_server))
        else:
            self.notify("No server selected", severity="warning")


def main():
    """Main TUI entry point."""
    app = MCPManagerApp()
    app.run()


if __name__ == "__main__":
    main()