"""
Server List Widget - Main list view for managing MCP servers.

Provides a comprehensive list view with search, filtering, status indicators,
and quick actions for server management.
"""

from typing import List, Dict, Any, Optional, Callable
import asyncio

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel, 
    QLineEdit, QComboBox, QPushButton, QFrame, QSplitter,
    QMenu, QMessageBox, QProgressBar, QGroupBox
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QAction, QFont, QPalette, QIcon

from ..services.cli_bridge import CLIBridge
from .server_card import ServerCard


class ServerListWorker(QThread):
    """Background worker for server operations to keep UI responsive."""
    
    servers_updated = Signal(list)
    operation_completed = Signal(str, bool, str)  # operation, success, message
    
    def __init__(self, cli_bridge: CLIBridge):
        super().__init__()
        self.cli_bridge = cli_bridge
        self.should_update = True
        
    def run(self):
        """Main worker thread loop."""
        while self.should_update:
            try:
                # Run async operations in this thread's event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                servers = loop.run_until_complete(self.cli_bridge.get_servers())
                self.servers_updated.emit(servers)
                
                loop.close()
                
            except Exception as e:
                print(f"Worker error: {e}")
            
            # Wait 5 seconds before next update
            self.msleep(5000)
    
    def stop(self):
        """Stop the worker thread."""
        self.should_update = False
        self.quit()
        self.wait()
    
    async def perform_server_operation(self, operation: str, server_name: str, **kwargs) -> bool:
        """Perform a server operation asynchronously."""
        try:
            if operation == "enable":
                result = await self.cli_bridge.enable_server(server_name)
            elif operation == "disable":
                result = await self.cli_bridge.disable_server(server_name)
            elif operation == "remove":
                result = await self.cli_bridge.remove_server(server_name)
            else:
                result = False
                
            message = f"Server '{server_name}' {operation}{'d' if operation != 'remove' else 'd'} successfully"
            if not result:
                message = f"Failed to {operation} server '{server_name}'"
                
            self.operation_completed.emit(operation, result, message)
            return result
            
        except Exception as e:
            message = f"Error {operation}ing server '{server_name}': {str(e)}"
            self.operation_completed.emit(operation, False, message)
            return False


class ServerList(QWidget):
    """Main server list widget with search, filtering, and management capabilities."""
    
    server_selected = Signal(dict)  # Emitted when a server is selected
    server_action_requested = Signal(str, str)  # action, server_name
    refresh_requested = Signal()  # Emitted when refresh is requested
    
    def __init__(self, cli_bridge: CLIBridge, parent=None):
        super().__init__(parent)
        self.cli_bridge = cli_bridge
        self.servers_data: List[Dict[str, Any]] = []
        self.filtered_servers: List[Dict[str, Any]] = []
        self.server_cards: List[ServerCard] = []
        self.selected_server: Optional[Dict[str, Any]] = None
        
        self.setup_ui()
        self.setup_worker()
        self.apply_macos_styling()
        
        # Start periodic updates
        self.start_auto_refresh()
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Header section
        self.setup_header(layout)
        
        # Toolbar section
        self.setup_toolbar(layout)
        
        # Main content area
        self.setup_content_area(layout)
        
        # Status bar
        self.setup_status_bar(layout)
    
    def setup_header(self, parent_layout):
        """Set up the header section."""
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.NoFrame)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 8)
        
        # Title
        title = QLabel("MCP Servers")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setWeight(QFont.Weight.Bold)
        title.setFont(title_font)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Server count badge
        self.server_count_label = QLabel("0 servers")
        self.server_count_label.setStyleSheet("""
            QLabel {
                background-color: #007AFF;
                color: white;
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 500;
            }
        """)
        header_layout.addWidget(self.server_count_label)
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_servers)
        header_layout.addWidget(self.refresh_btn)
        
        parent_layout.addWidget(header_frame)
    
    def setup_toolbar(self, parent_layout):
        """Set up the toolbar with search and filters."""
        toolbar_frame = QFrame()
        toolbar_frame.setFrameStyle(QFrame.StyledPanel)
        toolbar_frame.setStyleSheet("QFrame { background-color: #F5F5F7; border-radius: 8px; }")
        toolbar_layout = QHBoxLayout(toolbar_frame)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        
        # Search field
        search_label = QLabel("Search:")
        toolbar_layout.addWidget(search_label)
        
        self.search_field = QLineEdit()
        self.search_field.setPlaceholderText("Search servers by name, type, or description...")
        self.search_field.textChanged.connect(self.filter_servers)
        self.search_field.setStyleSheet("""
            QLineEdit {
                padding: 6px 12px;
                border: 1px solid #D1D1D6;
                border-radius: 6px;
                background-color: white;
                font-size: 13px;
            }
            QLineEdit:focus {
                border-color: #007AFF;
            }
        """)
        toolbar_layout.addWidget(self.search_field)
        
        # Status filter
        status_label = QLabel("Status:")
        toolbar_layout.addWidget(status_label)
        
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Connected", "Failed", "Disabled", "Unknown"])
        self.status_filter.currentTextChanged.connect(self.filter_servers)
        self.status_filter.setStyleSheet("""
            QComboBox {
                padding: 6px 12px;
                border: 1px solid #D1D1D6;
                border-radius: 6px;
                background-color: white;
                font-size: 13px;
                min-width: 80px;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
            }
        """)
        toolbar_layout.addWidget(self.status_filter)
        
        # Type filter
        type_label = QLabel("Type:")
        toolbar_layout.addWidget(type_label)
        
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All", "Docker Desktop", "NPM", "Docker Hub", "Custom"])
        self.type_filter.currentTextChanged.connect(self.filter_servers)
        self.type_filter.setStyleSheet(self.status_filter.styleSheet())
        toolbar_layout.addWidget(self.type_filter)
        
        toolbar_layout.addStretch()
        
        # Quick actions
        self.enable_all_btn = QPushButton("Enable All")
        self.enable_all_btn.clicked.connect(self.enable_all_servers)
        self.enable_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #34C759;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 6px;
                font-weight: 500;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #30B050;
            }
            QPushButton:pressed {
                background-color: #2A9946;
            }
        """)
        toolbar_layout.addWidget(self.enable_all_btn)
        
        self.disable_all_btn = QPushButton("Disable All")
        self.disable_all_btn.clicked.connect(self.disable_all_servers)
        self.disable_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF3B30;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 6px;
                font-weight: 500;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #E6352A;
            }
            QPushButton:pressed {
                background-color: #CC2F24;
            }
        """)
        toolbar_layout.addWidget(self.disable_all_btn)
        
        parent_layout.addWidget(toolbar_frame)
    
    def setup_content_area(self, parent_layout):
        """Set up the main scrollable content area."""
        # Scroll area for server cards
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        
        # Container widget for server cards
        self.server_container = QWidget()
        self.server_layout = QVBoxLayout(self.server_container)
        self.server_layout.setSpacing(8)
        self.server_layout.setContentsMargins(0, 0, 0, 0)
        
        # Empty state label
        self.empty_label = QLabel("No servers found")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("""
            QLabel {
                color: #8E8E93;
                font-size: 16px;
                font-weight: 500;
                padding: 40px;
            }
        """)
        self.server_layout.addWidget(self.empty_label)
        
        self.scroll_area.setWidget(self.server_container)
        parent_layout.addWidget(self.scroll_area, 1)  # Give it stretch factor
    
    def setup_status_bar(self, parent_layout):
        """Set up the status bar."""
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.NoFrame)
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 8, 0, 0)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("QLabel { color: #8E8E93; font-size: 12px; }")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #D1D1D6;
                border-radius: 4px;
                text-align: center;
                font-size: 11px;
                height: 16px;
            }
            QProgressBar::chunk {
                background-color: #007AFF;
                border-radius: 3px;
            }
        """)
        status_layout.addWidget(self.progress_bar)
        
        parent_layout.addWidget(status_frame)
    
    def setup_worker(self):
        """Set up background worker thread."""
        self.worker = ServerListWorker(self.cli_bridge)
        self.worker.servers_updated.connect(self.update_servers)
        self.worker.operation_completed.connect(self.handle_operation_completed)
    
    def start_auto_refresh(self):
        """Start automatic refresh of server data."""
        self.worker.start()
    
    def stop_auto_refresh(self):
        """Stop automatic refresh."""
        if hasattr(self, 'worker'):
            self.worker.stop()
    
    def update_servers(self, servers_data: List[Dict[str, Any]]):
        """Update the server list with new data."""
        self.servers_data = servers_data
        self.filter_servers()
        self.update_server_count()
        self.update_status("Last updated: now")
    
    def filter_servers(self):
        """Filter servers based on search and filter criteria."""
        search_text = self.search_field.text().lower()
        status_filter = self.status_filter.currentText()
        type_filter = self.type_filter.currentText()
        
        self.filtered_servers = []
        
        for server in self.servers_data:
            # Apply search filter
            if search_text:
                server_text = f"{server.get('name', '')} {server.get('type', '')} {server.get('description', '')}".lower()
                if search_text not in server_text:
                    continue
            
            # Apply status filter
            if status_filter != "All":
                server_status = server.get('claude_status', 'Unknown')
                if status_filter != server_status:
                    continue
            
            # Apply type filter
            if type_filter != "All":
                server_type = server.get('type', 'Custom')
                if type_filter != server_type:
                    continue
            
            self.filtered_servers.append(server)
        
        self.rebuild_server_cards()
    
    def rebuild_server_cards(self):
        """Rebuild the server card widgets."""
        # Clear existing cards
        for card in self.server_cards:
            card.setParent(None)
            card.deleteLater()
        self.server_cards.clear()
        
        # Remove empty label
        self.empty_label.setVisible(False)
        
        if not self.filtered_servers:
            # Show empty state
            self.empty_label.setVisible(True)
            return
        
        # Create new cards
        for server_data in self.filtered_servers:
            card = ServerCard(server_data, self.cli_bridge, self)
            card.server_selected.connect(self.on_server_selected)
            card.action_requested.connect(self.on_server_action_requested)
            
            self.server_cards.append(card)
            self.server_layout.addWidget(card)
        
        # Add stretch at the end
        self.server_layout.addStretch()
    
    def update_server_count(self):
        """Update the server count badge."""
        total = len(self.servers_data)
        filtered = len(self.filtered_servers)
        
        if total == filtered:
            text = f"{total} server{'s' if total != 1 else ''}"
        else:
            text = f"{filtered} of {total} servers"
        
        self.server_count_label.setText(text)
    
    def update_status(self, message: str):
        """Update the status bar message."""
        self.status_label.setText(message)
    
    def show_progress(self, show: bool, message: str = ""):
        """Show or hide progress bar."""
        self.progress_bar.setVisible(show)
        if show:
            self.progress_bar.setRange(0, 0)  # Indeterminate progress
            self.update_status(message)
    
    def on_server_selected(self, server_data: Dict[str, Any]):
        """Handle server selection."""
        self.selected_server = server_data
        
        # Update card selection states
        for card in self.server_cards:
            card.set_selected(card.server_data.get('name') == server_data.get('name'))
        
        self.server_selected.emit(server_data)
    
    def on_server_action_requested(self, action: str, server_name: str):
        """Handle server action requests."""
        if action == "remove":
            # Confirm removal
            reply = QMessageBox.question(
                self,
                "Confirm Removal",
                f"Are you sure you want to remove server '{server_name}'?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        
        self.show_progress(True, f"{action.capitalize()}ing server '{server_name}'...")
        self.server_action_requested.emit(action, server_name)
        
        # Perform action in worker thread
        asyncio.create_task(
            self.worker.perform_server_operation(action, server_name)
        )
    
    def handle_operation_completed(self, operation: str, success: bool, message: str):
        """Handle completion of server operations."""
        self.show_progress(False)
        
        if success:
            self.update_status(message)
            # Refresh server list
            self.refresh_servers()
        else:
            QMessageBox.warning(self, "Operation Failed", message)
            self.update_status("Operation failed")
    
    def refresh_servers(self):
        """Manually refresh server data."""
        self.show_progress(True, "Refreshing server list...")
        self.refresh_requested.emit()
        
        # The worker will automatically update the list
        QTimer.singleShot(1000, lambda: self.show_progress(False))
    
    def enable_all_servers(self):
        """Enable all visible servers."""
        if not self.filtered_servers:
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Enable All",
            f"Enable all {len(self.filtered_servers)} visible servers?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        
        self.show_progress(True, "Enabling all servers...")
        
        for server in self.filtered_servers:
            if server.get('claude_status') != 'Connected':
                asyncio.create_task(
                    self.worker.perform_server_operation("enable", server.get('name', ''))
                )
    
    def disable_all_servers(self):
        """Disable all visible servers."""
        if not self.filtered_servers:
            return
        
        reply = QMessageBox.question(
            self,
            "Confirm Disable All",
            f"Disable all {len(self.filtered_servers)} visible servers?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        
        self.show_progress(True, "Disabling all servers...")
        
        for server in self.filtered_servers:
            if server.get('claude_status') == 'Connected':
                asyncio.create_task(
                    self.worker.perform_server_operation("disable", server.get('name', ''))
                )
    
    def apply_macos_styling(self):
        """Apply macOS-specific styling."""
        self.setStyleSheet("""
            QWidget {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background-color: #FFFFFF;
            }
            
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            
            QScrollBar:vertical {
                background-color: transparent;
                width: 8px;
                border-radius: 4px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #C7C7CC;
                border-radius: 4px;
                min-height: 20px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #A1A1A6;
            }
            
            QPushButton {
                background-color: #007AFF;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 8px;
                font-weight: 500;
                font-size: 13px;
            }
            
            QPushButton:hover {
                background-color: #0056CC;
            }
            
            QPushButton:pressed {
                background-color: #004999;
            }
        """)
    
    def closeEvent(self, event):
        """Clean up when widget is closed."""
        self.stop_auto_refresh()
        event.accept()