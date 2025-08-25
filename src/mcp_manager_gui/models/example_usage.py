"""
Example usage of the MCP Manager GUI data models.

This script demonstrates how to use the ServerTableModel and SuiteTableModel
in a Qt application. This is intended for development and testing purposes.
"""

import sys
import asyncio
from typing import Dict, List, Any

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
    QWidget, QTableView, QLineEdit, QComboBox, QPushButton,
    QLabel, QSplitter, QListView, QTabWidget
)
from PySide6.QtCore import Qt, QTimer

from mcp_manager_gui.services.cli_bridge import CLIBridge
from mcp_manager_gui.models import (
    ServerTableModel, SuiteTableModel, SuiteMembershipListModel,
    ServerColumn, SuiteColumn
)


class MockCLIBridge(CLIBridge):
    """Mock CLI bridge for demonstration purposes."""
    
    def __init__(self):
        # Don't call super().__init__() to avoid real initialization
        pass
    
    async def get_servers(self, scope: str = "user") -> List[Dict[str, Any]]:
        """Return mock server data."""
        return [
            {
                "name": "filesystem-server",
                "server_type": "npm",
                "status": "active",
                "scope": "user",
                "description": "Provides file system operations",
                "enabled": True,
                "suites": ["development", "basic-tools"],
                "command": "npx @modelcontextprotocol/server-filesystem",
                "args": [],
                "env": {},
                "pid": 12345,
                "created_at": "2024-01-15T10:00:00Z",
                "updated_at": "2024-01-15T12:30:00Z",
                "claude_status": "Connected"
            },
            {
                "name": "sqlite-server",
                "server_type": "npm",
                "status": "active",
                "scope": "project",
                "description": "SQLite database operations",
                "enabled": True,
                "suites": ["data-analysis", "database"],
                "command": "npx @modelcontextprotocol/server-sqlite",
                "args": ["--db-path", "/path/to/db.sqlite"],
                "env": {},
                "pid": 12346,
                "created_at": "2024-01-15T11:00:00Z",
                "updated_at": "2024-01-15T13:00:00Z",
                "claude_status": "Connected"
            },
            {
                "name": "docker-server",
                "server_type": "docker-desktop",
                "status": "inactive",
                "scope": "user",
                "description": "Docker container management",
                "enabled": False,
                "suites": [],
                "command": "docker-mcp-server",
                "args": [],
                "env": {},
                "pid": None,
                "created_at": "2024-01-14T09:00:00Z",
                "updated_at": "2024-01-14T09:00:00Z",
                "claude_status": "Disconnected"
            },
            {
                "name": "custom-tool",
                "server_type": "custom",
                "status": "error",
                "scope": "local",
                "description": "Custom development tool",
                "enabled": True,
                "suites": ["development"],
                "command": "/usr/local/bin/my-tool",
                "args": ["--config", "config.json"],
                "env": {"API_KEY": "secret"},
                "pid": None,
                "created_at": "2024-01-12T16:00:00Z",
                "updated_at": "2024-01-15T14:00:00Z",
                "claude_status": "Error",
                "last_error": "Connection timeout"
            }
        ]


class ModelDemoWindow(QMainWindow):
    """Demo window showing the data models in action."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MCP Manager GUI Models Demo")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create mock CLI bridge
        self.cli_bridge = MockCLIBridge()
        
        # Create models
        self.server_model = ServerTableModel(self.cli_bridge)
        self.suite_model = SuiteTableModel(self.cli_bridge)
        self.membership_model = SuiteMembershipListModel()
        
        # Setup UI
        self.setup_ui()
        self.connect_signals()
        
        # Start event loop integration
        self.async_timer = QTimer()
        self.async_timer.timeout.connect(self.process_async_events)
        self.async_timer.start(100)  # Process async events every 100ms
    
    def setup_ui(self):
        """Setup the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Create tab widget for different views
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)
        
        # Server management tab
        server_tab = self.create_server_tab()
        tab_widget.addTab(server_tab, "Servers")
        
        # Suite management tab
        suite_tab = self.create_suite_tab()
        tab_widget.addTab(suite_tab, "Suites")
    
    def create_server_tab(self) -> QWidget:
        """Create the server management tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Filter controls
        filter_layout = QHBoxLayout()
        layout.addLayout(filter_layout)
        
        # Text filter
        filter_layout.addWidget(QLabel("Filter:"))
        self.server_text_filter = QLineEdit()
        self.server_text_filter.setPlaceholderText("Search servers...")
        filter_layout.addWidget(self.server_text_filter)
        
        # Type filter
        filter_layout.addWidget(QLabel("Type:"))
        self.server_type_filter = QComboBox()
        self.server_type_filter.addItems(["All", "npm", "docker", "docker-desktop", "custom"])
        filter_layout.addWidget(self.server_type_filter)
        
        # Status filter
        filter_layout.addWidget(QLabel("Status:"))
        self.server_status_filter = QComboBox()
        self.server_status_filter.addItems(["All", "active", "inactive", "error", "unknown"])
        filter_layout.addWidget(self.server_status_filter)
        
        # Enabled filter
        filter_layout.addWidget(QLabel("Enabled:"))
        self.server_enabled_filter = QComboBox()
        self.server_enabled_filter.addItems(["All", "Yes", "No"])
        filter_layout.addWidget(self.server_enabled_filter)
        
        # Clear filters button
        clear_button = QPushButton("Clear Filters")
        clear_button.clicked.connect(self.clear_server_filters)
        filter_layout.addWidget(clear_button)
        
        filter_layout.addStretch()
        
        # Refresh button
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.server_model.refresh_now)
        filter_layout.addWidget(refresh_button)
        
        # Server table
        self.server_table = QTableView()
        self.server_table.setModel(self.server_model)
        self.server_table.setAlternatingRowColors(True)
        self.server_table.setSelectionBehavior(QTableView.SelectRows)
        self.server_table.setSortingEnabled(True)
        self.server_table.setDragEnabled(True)  # Enable drag for servers
        layout.addWidget(self.server_table)
        
        # Resize columns to content
        self.server_table.resizeColumnsToContents()
        
        return widget
    
    def create_suite_tab(self) -> QWidget:
        """Create the suite management tab."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        # Left side - suite list and controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Suite filter controls
        suite_filter_layout = QHBoxLayout()
        left_layout.addLayout(suite_filter_layout)
        
        suite_filter_layout.addWidget(QLabel("Filter:"))
        self.suite_text_filter = QLineEdit()
        self.suite_text_filter.setPlaceholderText("Search suites...")
        suite_filter_layout.addWidget(self.suite_text_filter)
        
        suite_filter_layout.addWidget(QLabel("Category:"))
        self.suite_category_filter = QComboBox()
        self.suite_category_filter.addItems([
            "All", "web-development", "data-analysis", "system-administration",
            "research", "automation", "testing", "general"
        ])
        suite_filter_layout.addWidget(self.suite_category_filter)
        
        clear_suite_button = QPushButton("Clear")
        clear_suite_button.clicked.connect(self.clear_suite_filters)
        suite_filter_layout.addWidget(clear_suite_button)
        
        # Suite table
        self.suite_table = QTableView()
        self.suite_table.setModel(self.suite_model)
        self.suite_table.setAlternatingRowColors(True)
        self.suite_table.setSelectionBehavior(QTableView.SelectRows)
        self.suite_table.setSortingEnabled(True)
        self.suite_table.setAcceptDrops(True)  # Enable drop for servers onto suites
        left_layout.addWidget(self.suite_table)
        
        # Right side - suite membership details
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        right_layout.addWidget(QLabel("Suite Membership:"))
        
        self.membership_list = QListView()
        self.membership_list.setModel(self.membership_model)
        right_layout.addWidget(self.membership_list)
        
        # Create splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([800, 400])  # Give more space to suite table
        
        layout.addWidget(splitter)
        
        return widget
    
    def connect_signals(self):
        """Connect model and UI signals."""
        # Server model signals
        self.server_model.serverAdded.connect(self.on_server_added)
        self.server_model.serverRemoved.connect(self.on_server_removed)
        self.server_model.serverStatusChanged.connect(self.on_server_status_changed)
        self.server_model.dataRefreshed.connect(self.on_servers_refreshed)
        
        # Suite model signals
        self.suite_model.suiteAdded.connect(self.on_suite_added)
        self.suite_model.suiteRemoved.connect(self.on_suite_removed)
        self.suite_model.serverAddedToSuite.connect(self.on_server_added_to_suite)
        
        # Filter controls
        self.server_text_filter.textChanged.connect(self.update_server_filters)
        self.server_type_filter.currentTextChanged.connect(self.update_server_filters)
        self.server_status_filter.currentTextChanged.connect(self.update_server_filters)
        self.server_enabled_filter.currentTextChanged.connect(self.update_server_filters)
        
        self.suite_text_filter.textChanged.connect(self.update_suite_filters)
        self.suite_category_filter.currentTextChanged.connect(self.update_suite_filters)
        
        # Suite selection for membership view
        self.suite_table.selectionModel().currentRowChanged.connect(self.on_suite_selection_changed)
    
    def update_server_filters(self):
        """Update server model filters based on UI controls."""
        # Text filter
        text = self.server_text_filter.text()
        self.server_model.set_filter_text(text)
        
        # Type filter
        type_text = self.server_type_filter.currentText()
        server_type = None if type_text == "All" else type_text
        self.server_model.set_filter_type(server_type)
        
        # Status filter
        status_text = self.server_status_filter.currentText()
        status = None if status_text == "All" else status_text
        self.server_model.set_filter_status(status)
        
        # Enabled filter
        enabled_text = self.server_enabled_filter.currentText()
        enabled = None
        if enabled_text == "Yes":
            enabled = True
        elif enabled_text == "No":
            enabled = False
        self.server_model.set_filter_enabled(enabled)
    
    def update_suite_filters(self):
        """Update suite model filters based on UI controls."""
        text = self.suite_text_filter.text()
        self.suite_model.set_filter_text(text)
        
        category_text = self.suite_category_filter.currentText()
        category = None if category_text == "All" else category_text
        self.suite_model.set_filter_category(category)
    
    def clear_server_filters(self):
        """Clear all server filters."""
        self.server_text_filter.clear()
        self.server_type_filter.setCurrentText("All")
        self.server_status_filter.setCurrentText("All")
        self.server_enabled_filter.setCurrentText("All")
        self.server_model.clear_filters()
    
    def clear_suite_filters(self):
        """Clear all suite filters."""
        self.suite_text_filter.clear()
        self.suite_category_filter.setCurrentText("All")
        self.suite_model.clear_filters()
    
    def on_suite_selection_changed(self, current, previous):
        """Handle suite selection change to update membership view."""
        if current.isValid():
            suite_data = self.suite_model.get_suite_by_row(current.row())
            self.membership_model.set_suite(suite_data)
        else:
            self.membership_model.set_suite(None)
    
    # Signal handlers for demonstration
    def on_server_added(self, server_name: str):
        print(f"Server added: {server_name}")
    
    def on_server_removed(self, server_name: str):
        print(f"Server removed: {server_name}")
    
    def on_server_status_changed(self, server_name: str, new_status: str):
        print(f"Server {server_name} status changed to: {new_status}")
    
    def on_servers_refreshed(self):
        print("Servers refreshed")
        # Resize columns after data refresh
        self.server_table.resizeColumnsToContents()
    
    def on_suite_added(self, suite_id: str):
        print(f"Suite added: {suite_id}")
    
    def on_suite_removed(self, suite_id: str):
        print(f"Suite removed: {suite_id}")
    
    def on_server_added_to_suite(self, suite_id: str, server_name: str):
        print(f"Server {server_name} added to suite {suite_id}")
    
    def process_async_events(self):
        """Process pending async events."""
        # This is needed to handle asyncio tasks in Qt event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Process ready tasks
                loop._ready.rotate()  # Process one ready task
        except RuntimeError:
            pass


def main():
    """Run the demo application."""
    app = QApplication(sys.argv)
    
    # Create and show the demo window
    window = ModelDemoWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()