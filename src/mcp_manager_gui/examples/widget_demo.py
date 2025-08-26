#!/usr/bin/env python3
"""
Widget Demo - Example usage of MCP Manager GUI widgets.

This demonstrates how to use the core widgets individually and together.
Run with: python -m mcp_manager_gui.examples.widget_demo
"""

import sys
import asyncio
from typing import Dict, Any

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QTabWidget
from PySide6.QtCore import QTimer

# Assuming this is run from the project root
from mcp_manager_gui.services.cli_bridge import CLIBridge
from mcp_manager_gui.widgets import ServerList, StatusMonitor, ServerCard


class WidgetDemoWindow(QMainWindow):
    """Main demo window showcasing the widgets."""
    
    def __init__(self):
        super().__init__()
        self.cli_bridge = CLIBridge()
        self.setup_ui()
        self.setup_demo_data()
        
        self.setWindowTitle("MCP Manager GUI Widget Demo")
        self.setGeometry(100, 100, 1200, 800)
    
    def setup_ui(self):
        """Set up the demo UI."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Create tab widget for different demos
        tab_widget = QTabWidget()
        
        # Server List Demo
        server_list_demo = self.create_server_list_demo()
        tab_widget.addTab(server_list_demo, "Server List")
        
        # Status Monitor Demo
        status_monitor_demo = self.create_status_monitor_demo()
        tab_widget.addTab(status_monitor_demo, "Status Monitor")
        
        # Individual Server Card Demo
        server_card_demo = self.create_server_card_demo()
        tab_widget.addTab(server_card_demo, "Server Cards")
        
        layout.addWidget(tab_widget)
    
    def create_server_list_demo(self) -> QWidget:
        """Create server list demo tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Create server list widget
        self.server_list = ServerList(self.cli_bridge, widget)
        layout.addWidget(self.server_list)
        
        return widget
    
    def create_status_monitor_demo(self) -> QWidget:
        """Create status monitor demo tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Create status monitor widget
        self.status_monitor = StatusMonitor(self.cli_bridge, widget)
        layout.addWidget(self.status_monitor)
        
        return widget
    
    def create_server_card_demo(self) -> QWidget:
        """Create server card demo tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Create sample server cards
        sample_servers = [
            {
                "name": "SQLite MCP",
                "type": "Docker Desktop",
                "claude_status": "Connected",
                "description": "SQLite database management server with query capabilities",
                "command": "docker run mcr.microsoft.com/vscode/devcontainers/sqlite",
                "tools": [{"name": "query"}, {"name": "schema"}]
            },
            {
                "name": "Filesystem MCP", 
                "type": "NPM",
                "claude_status": "Failed",
                "description": "File system operations server for reading and writing files",
                "command": "npx @modelcontextprotocol/server-filesystem",
                "tools": [{"name": "read_file"}, {"name": "write_file"}, {"name": "list_dir"}]
            },
            {
                "name": "Custom Script Server",
                "type": "Custom", 
                "claude_status": "Disabled",
                "description": "Custom Python script for specialized tasks",
                "command": "python /path/to/custom_server.py",
                "tools": []
            }
        ]
        
        self.server_cards = []
        for server_data in sample_servers:
            card = ServerCard(server_data, self.cli_bridge, widget)
            card.server_selected.connect(self.on_demo_server_selected)
            card.action_requested.connect(self.on_demo_action_requested)
            
            self.server_cards.append(card)
            layout.addWidget(card)
        
        layout.addStretch()
        
        return widget
    
    def setup_demo_data(self):
        """Set up demo data for testing widgets."""
        # This would normally come from the CLI bridge
        # For demo purposes, we'll simulate some data
        pass
    
    def on_demo_server_selected(self, server_data: Dict[str, Any]):
        """Handle demo server selection."""
        print(f"Demo: Server selected: {server_data.get('name')}")
    
    def on_demo_action_requested(self, action: str, server_name: str):
        """Handle demo action requests."""
        print(f"Demo: Action '{action}' requested for server '{server_name}'")


def main():
    """Run the widget demo."""
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("MCP Manager GUI Widget Demo")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("MCP Manager")
    
    # Create and show demo window
    demo_window = WidgetDemoWindow()
    demo_window.show()
    
    # Run the application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()