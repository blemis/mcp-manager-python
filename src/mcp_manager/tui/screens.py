"""
TUI Screens for MCP Manager.

Additional screens for server management, help, and configuration.
"""

from typing import Any, Dict, List, Optional

from textual import on
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Button, Input, Label, Markdown, Select, Static, Switch, TextArea
)

from mcp_manager.core.models import ServerScope, ServerType
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class HelpScreen(ModalScreen[None]):
    """Help screen showing keyboard shortcuts and usage information."""
    
    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    
    .help-container {
        width: 80;
        height: 25;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }
    
    .help-buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }
    """
    
    def __init__(self, help_text: str):
        super().__init__()
        self.help_text = help_text
        
    def compose(self) -> ComposeResult:
        """Create the help screen layout."""
        with Container(classes="help-container"):
            yield Markdown(self.help_text)
            with Horizontal(classes="help-buttons"):
                yield Button("Close", id="close-help", classes="-primary")
                
    @on(Button.Pressed, "#close-help")
    def close_help(self) -> None:
        """Close the help screen."""
        self.dismiss()


class AddServerScreen(ModalScreen[Optional[Dict[str, Any]]]):
    """Screen for adding a new MCP server."""
    
    DEFAULT_CSS = """
    AddServerScreen {
        align: center middle;
    }
    
    .form-container {
        width: 70;
        height: 20;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }
    
    .form-field {
        margin: 1 0;
    }
    
    .form-buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }
    
    Input {
        width: 100%;
    }
    
    Select {
        width: 100%;
    }
    """
    
    def compose(self) -> ComposeResult:
        """Create the add server form."""
        with Container(classes="form-container"):
            yield Label("Add New MCP Server", classes="form-title")
            
            with Vertical(classes="form-fields"):
                with Horizontal(classes="form-field"):
                    yield Label("Name:", classes="field-label")
                    yield Input(placeholder="server-name", id="server-name")
                    
                with Horizontal(classes="form-field"):
                    yield Label("Command:", classes="field-label")
                    yield Input(placeholder="npx @example/mcp-server", id="server-command")
                    
                with Horizontal(classes="form-field"):
                    yield Label("Scope:", classes="field-label")
                    yield Select(
                        [(scope.value.title(), scope.value) for scope in ServerScope],
                        value=ServerScope.USER.value,
                        id="server-scope"
                    )
                    
                with Horizontal(classes="form-field"):
                    yield Label("Type:", classes="field-label")
                    yield Select(
                        [(stype.value.title(), stype.value) for stype in ServerType],
                        value=ServerType.CUSTOM.value,
                        id="server-type"
                    )
                    
                with Horizontal(classes="form-field"):
                    yield Label("Description:", classes="field-label")
                    yield Input(placeholder="Optional description", id="server-description")
                    
            with Horizontal(classes="form-buttons"):
                yield Button("Add Server", id="add-server-submit", classes="-success")
                yield Button("Cancel", id="add-server-cancel", classes="-secondary")
                
    @on(Button.Pressed, "#add-server-submit")
    def submit_server(self) -> None:
        """Submit the new server."""
        try:
            name = self.query_one("#server-name", Input).value.strip()
            command = self.query_one("#server-command", Input).value.strip()
            scope = self.query_one("#server-scope", Select).value
            server_type = self.query_one("#server-type", Select).value
            description = self.query_one("#server-description", Input).value.strip()
            
            if not name:
                self.notify("Server name is required", severity="error")
                return
                
            if not command:
                self.notify("Server command is required", severity="error")
                return
                
            result = {
                "name": name,
                "command": command,
                "scope": ServerScope(scope),
                "server_type": ServerType(server_type),
                "description": description if description else None,
            }
            
            self.dismiss(result)
            
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")
            
    @on(Button.Pressed, "#add-server-cancel")
    def cancel_add(self) -> None:
        """Cancel adding server."""
        self.dismiss(None)


class EditServerScreen(ModalScreen[Optional[Dict[str, Any]]]):
    """Screen for editing an existing MCP server."""
    
    DEFAULT_CSS = """
    EditServerScreen {
        align: center middle;
    }
    
    .form-container {
        width: 70;
        height: 22;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }
    
    .form-field {
        margin: 1 0;
    }
    
    .form-buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }
    
    Input {
        width: 100%;
    }
    
    Select {
        width: 100%;
    }
    
    Switch {
        margin: 1 0;
    }
    """
    
    def __init__(self, server_data: Dict[str, Any]):
        super().__init__()
        self.server_data = server_data
        
    def compose(self) -> ComposeResult:
        """Create the edit server form."""
        with Container(classes="form-container"):
            yield Label(f"Edit Server: {self.server_data['name']}", classes="form-title")
            
            with Vertical(classes="form-fields"):
                with Horizontal(classes="form-field"):
                    yield Label("Command:", classes="field-label")
                    yield Input(
                        value=self.server_data["command"],
                        id="server-command"
                    )
                    
                with Horizontal(classes="form-field"):
                    yield Label("Scope:", classes="field-label")
                    yield Select(
                        [(scope.value.title(), scope.value) for scope in ServerScope],
                        value=self.server_data["scope"],
                        id="server-scope"
                    )
                    
                with Horizontal(classes="form-field"):
                    yield Label("Type:", classes="field-label")
                    yield Select(
                        [(stype.value.title(), stype.value) for stype in ServerType],
                        value=self.server_data["server_type"],
                        id="server-type"
                    )
                    
                with Horizontal(classes="form-field"):
                    yield Label("Description:", classes="field-label")
                    yield Input(
                        value=self.server_data.get("description", ""),
                        placeholder="Optional description",
                        id="server-description"
                    )
                    
                with Horizontal(classes="form-field"):
                    yield Label("Enabled:", classes="field-label")
                    yield Switch(
                        value=self.server_data["enabled"],
                        id="server-enabled"
                    )
                    
            with Horizontal(classes="form-buttons"):
                yield Button("Save Changes", id="edit-server-submit", classes="-success")
                yield Button("Cancel", id="edit-server-cancel", classes="-secondary")
                
    @on(Button.Pressed, "#edit-server-submit")
    def submit_changes(self) -> None:
        """Submit the server changes."""
        try:
            command = self.query_one("#server-command", Input).value.strip()
            scope = self.query_one("#server-scope", Select).value
            server_type = self.query_one("#server-type", Select).value
            description = self.query_one("#server-description", Input).value.strip()
            enabled = self.query_one("#server-enabled", Switch).value
            
            if not command:
                self.notify("Server command is required", severity="error")
                return
                
            result = {
                "name": self.server_data["name"],
                "command": command,
                "scope": ServerScope(scope),
                "server_type": ServerType(server_type),
                "description": description if description else None,
                "enabled": enabled,
            }
            
            self.dismiss(result)
            
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")
            
    @on(Button.Pressed, "#edit-server-cancel")
    def cancel_edit(self) -> None:
        """Cancel editing server."""
        self.dismiss(None)


class ConfirmDialog(ModalScreen[bool]):
    """Confirmation dialog for destructive operations."""
    
    DEFAULT_CSS = """
    ConfirmDialog {
        align: center middle;
    }
    
    .dialog-container {
        width: 50;
        height: 10;
        background: $surface;
        border: solid $error;
        padding: 1;
    }
    
    .dialog-buttons {
        dock: bottom;
        height: 3;
        align: center middle;
    }
    
    .dialog-message {
        text-align: center;
        margin: 1 0;
    }
    """
    
    def __init__(self, message: str, title: str = "Confirm"):
        super().__init__()
        self.message = message
        self.title = title
        
    def compose(self) -> ComposeResult:
        """Create the confirmation dialog."""
        with Container(classes="dialog-container"):
            yield Label(self.title, classes="dialog-title")
            yield Label(self.message, classes="dialog-message")
            
            with Horizontal(classes="dialog-buttons"):
                yield Button("Yes", id="confirm-yes", classes="-error")
                yield Button("No", id="confirm-no", classes="-secondary")
                
    @on(Button.Pressed, "#confirm-yes")
    def confirm_yes(self) -> None:
        """Confirm the operation."""
        self.dismiss(True)
        
    @on(Button.Pressed, "#confirm-no")
    def confirm_no(self) -> None:
        """Cancel the operation."""
        self.dismiss(False)