"""
Custom widgets for MCP Manager TUI.

Provides specialized widgets for server management, system information,
and other domain-specific functionality.
"""

from typing import Any, Dict, List, Optional

from rich.text import Text
from textual import on
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import (
    Button, DataTable, Input, Label, Select, Static, 
    Switch, TextArea
)

from mcp_manager.core.manager import MCPManager
from mcp_manager.core.models import Server, ServerScope, ServerType, SystemInfo
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ServerDetailWidget(Widget):
    """Widget for displaying and editing server details."""
    
    def __init__(self, server: Optional[Server] = None, **kwargs):
        super().__init__(**kwargs)
        self.server = server
        
    def compose(self):
        """Create the server detail layout."""
        with Vertical():
            yield Label("Server Details", classes="widget-title")
            
            with Horizontal():
                yield Label("Name:", classes="field-label")
                yield Input(
                    value=self.server.name if self.server else "",
                    placeholder="Server name",
                    id="server-name"
                )
                
            with Horizontal():
                yield Label("Command:", classes="field-label")
                yield Input(
                    value=self.server.command if self.server else "",
                    placeholder="Command to run server",
                    id="server-command"
                )
                
            with Horizontal():
                yield Label("Scope:", classes="field-label")
                yield Select(
                    [(scope.value.title(), scope.value) for scope in ServerScope],
                    value=self.server.scope.value if self.server else ServerScope.USER.value,
                    id="server-scope"
                )
                
            with Horizontal():
                yield Label("Type:", classes="field-label")
                yield Select(
                    [(stype.value.title(), stype.value) for stype in ServerType],
                    value=self.server.server_type.value if self.server else ServerType.CUSTOM.value,
                    id="server-type"
                )
                
            with Horizontal():
                yield Label("Description:", classes="field-label")
                yield Input(
                    value=self.server.description if self.server and self.server.description else "",
                    placeholder="Optional description",
                    id="server-description"
                )
                
            with Horizontal():
                yield Label("Enabled:", classes="field-label")
                yield Switch(
                    value=self.server.enabled if self.server else True,
                    id="server-enabled"
                )
                
            with Horizontal():
                yield Label("Environment Variables:", classes="field-label")
                yield TextArea(
                    text=self._format_env_vars(),
                    id="server-env"
                )
                
            with Horizontal():
                yield Button("Save", id="save-server", classes="-primary")
                yield Button("Cancel", id="cancel-server", classes="-secondary")
                
    def _format_env_vars(self) -> str:
        """Format environment variables for display."""
        if not self.server or not self.server.env:
            return ""
            
        return "\n".join(f"{key}={value}" for key, value in self.server.env.items())
        
    def get_server_data(self) -> Dict[str, Any]:
        """Get server data from form inputs."""
        name_input = self.query_one("#server-name", Input)
        command_input = self.query_one("#server-command", Input)
        scope_select = self.query_one("#server-scope", Select)
        type_select = self.query_one("#server-type", Select)
        desc_input = self.query_one("#server-description", Input)
        enabled_switch = self.query_one("#server-enabled", Switch)
        env_textarea = self.query_one("#server-env", TextArea)
        
        # Parse environment variables
        env_dict = {}
        env_text = env_textarea.text.strip()
        if env_text:
            for line in env_text.split("\n"):
                line = line.strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_dict[key.strip()] = value.strip()
                    
        return {
            "name": name_input.value.strip(),
            "command": command_input.value.strip(),
            "scope": ServerScope(scope_select.value),
            "server_type": ServerType(type_select.value),
            "description": desc_input.value.strip() or None,
            "enabled": enabled_switch.value,
            "env": env_dict,
        }


class SystemInfoWidget(Widget):
    """Widget for displaying system information and dependencies."""
    
    def __init__(self, manager: MCPManager, **kwargs):
        super().__init__(**kwargs)
        self.manager = manager
        self.system_info: Optional[SystemInfo] = None
        
    def compose(self):
        """Create the system info layout."""
        with Vertical():
            yield Label("System Information", classes="widget-title")
            yield DataTable(id="system-table", classes="system-table")
            
            with Horizontal():
                yield Button("Refresh", id="refresh-system", classes="-secondary")
                yield Button("Check Dependencies", id="check-deps", classes="-primary")
                
    async def on_mount(self) -> None:
        """Initialize the widget."""
        await self.refresh_system_info()
        
    async def refresh_system_info(self) -> None:
        """Refresh system information."""
        self.system_info = self.manager.get_system_info()
        self._populate_table()
        
    def _populate_table(self) -> None:
        """Populate the system info table."""
        if not self.system_info:
            return
            
        table = self.query_one("#system-table", DataTable)
        table.clear()
        table.add_columns("Component", "Status", "Version/Info")
        
        # System information
        table.add_row("Python", "✅", self.system_info.python_version)
        table.add_row("Platform", "✅", self.system_info.platform)
        
        # Dependencies
        deps = [
            ("Claude CLI", self.system_info.claude_cli_available, self.system_info.claude_cli_version),
            ("NPM", self.system_info.npm_available, self.system_info.npm_version),
            ("Docker", self.system_info.docker_available, self.system_info.docker_version),
            ("Git", self.system_info.git_available, self.system_info.git_version),
        ]
        
        for name, available, version in deps:
            status = "✅" if available else "❌"
            version_text = version or "Not available"
            table.add_row(name, status, version_text)
            
        # Paths
        table.add_row("Config Directory", "📁", str(self.system_info.config_dir))
        if self.system_info.log_file:
            table.add_row("Log File", "📄", str(self.system_info.log_file))
            
    @on(Button.Pressed, "#refresh-system")
    async def on_refresh_system(self) -> None:
        """Handle refresh button."""
        await self.refresh_system_info()
        
    @on(Button.Pressed, "#check-deps")
    def on_check_deps(self) -> None:
        """Check dependencies and show status."""
        if not self.system_info:
            return
            
        missing_deps = []
        if not self.system_info.claude_cli_available:
            missing_deps.append("Claude CLI")
        if not self.system_info.npm_available:
            missing_deps.append("NPM")
        if not self.system_info.docker_available:
            missing_deps.append("Docker")
            
        if missing_deps:
            self.app.notify(
                f"Missing dependencies: {', '.join(missing_deps)}",
                severity="warning"
            )
        else:
            self.app.notify("All dependencies available", severity="information")


class ServerStatsWidget(Widget):
    """Widget for displaying server statistics."""
    
    def __init__(self, manager: MCPManager, **kwargs):
        super().__init__(**kwargs)
        self.manager = manager
        
    def compose(self):
        """Create the stats layout."""
        with Vertical():
            yield Label("Server Statistics", classes="widget-title")
            yield self._create_stats_display()
            
    def _create_stats_display(self) -> Static:
        """Create the statistics display."""
        servers = self.manager.list_servers()
        
        # Calculate statistics
        total_servers = len(servers)
        enabled_servers = len([s for s in servers if s.enabled])
        disabled_servers = total_servers - enabled_servers
        
        # Count by scope
        local_count = len([s for s in servers if s.scope == ServerScope.LOCAL])
        project_count = len([s for s in servers if s.scope == ServerScope.PROJECT])
        user_count = len([s for s in servers if s.scope == ServerScope.USER])
        
        # Count by type
        npm_count = len([s for s in servers if s.server_type == ServerType.NPM])
        docker_count = len([s for s in servers if s.server_type == ServerType.DOCKER])
        custom_count = len([s for s in servers if s.server_type == ServerType.CUSTOM])
        
        stats_text = f"""
📊 **Server Overview**
Total Servers: {total_servers}
✅ Enabled: {enabled_servers}
❌ Disabled: {disabled_servers}

🏷️ **By Scope**
🔒 Local: {local_count}
🔄 Project: {project_count}
🌐 User: {user_count}

📦 **By Type**
📦 NPM: {npm_count}
🐳 Docker: {docker_count}
🔧 Custom: {custom_count}
        """
        
        return Static(stats_text)


class DiscoveryResultWidget(Widget):
    """Widget for displaying discovery results."""
    
    def __init__(self, results: List[Any], **kwargs):
        super().__init__(**kwargs)
        self.results = results
        
    def compose(self):
        """Create the discovery results layout."""
        with Vertical():
            yield Label(f"Discovery Results ({len(self.results)} found)", classes="widget-title")
            yield DataTable(id="results-table", classes="results-table")
            
            with Horizontal():
                yield Button("Install Selected", id="install-selected", classes="-success")
                yield Button("View Details", id="view-details", classes="-primary")
                yield Button("Clear Results", id="clear-results", classes="-secondary")
                
    def on_mount(self) -> None:
        """Initialize the widget."""
        self._populate_results()
        
    def _populate_results(self) -> None:
        """Populate the results table."""
        table = self.query_one("#results-table", DataTable)
        table.add_columns("Name", "Type", "Package", "Description", "Downloads")
        
        for result in self.results:
            downloads = str(result.downloads) if result.downloads else "N/A"
            desc_short = result.description[:40] + "..." if result.description and len(result.description) > 40 else result.description or ""
            
            table.add_row(
                result.name,
                result.server_type.value,
                result.package,
                desc_short,
                downloads,
                key=result.name
            )