"""
Modern Main Window - Professional macOS GUI for MCP Manager.

Complete redesign with visible toolbars, bulk operations, and modern styling.
"""

import asyncio
from typing import List, Dict, Any
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QFrame, QListWidget, QListWidgetItem,
    QTextEdit, QProgressBar, QToolBar, QGroupBox, QCheckBox,
    QComboBox, QLineEdit, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QScrollArea, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtGui import (
    QAction, QIcon, QFont, QPalette, QColor, QPainter, QPixmap,
    QLinearGradient, QBrush
)

from ..services.cli_bridge import CLIBridge


class ModernServerListWidget(QTableWidget):
    """Modern server list with selection checkboxes and bulk operations."""
    
    servers_selected = Signal(list)  # List of selected server names
    server_action_requested = Signal(str, str)  # action, server_name
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cli_bridge = CLIBridge()
        self.servers_data = []
        
        self.setup_ui()
        self.setup_styling()
        
        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_servers)
        self.refresh_timer.start(5000)  # 5 seconds
        
        # Initial load
        self.refresh_servers()
    
    def setup_ui(self):
        """Set up the table structure."""
        # Configure table
        self.setColumnCount(6)
        self.setHorizontalHeaderLabels([
            "Select", "Name", "Type", "Status", "Description", "Actions"
        ])
        
        # Configure headers
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Select
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Name  
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Type
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Status
        header.setSectionResizeMode(4, QHeaderView.Stretch)           # Description
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Actions
        
        # Table settings
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.MultiSelection)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)
    
    def setup_styling(self):
        """Apply modern macOS styling."""
        self.setStyleSheet("""
            QTableWidget {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                gridline-color: #f0f0f0;
                font-size: 13px;
                selection-background-color: #007AFF;
                selection-color: white;
            }
            
            QTableWidget::item {
                padding: 8px;
                border: none;
            }
            
            QTableWidget::item:selected {
                background-color: #007AFF;
                color: white;
            }
            
            QTableWidget::item:hover {
                background-color: #f0f8ff;
            }
            
            QHeaderView::section {
                background-color: #f8f9fa;
                border: none;
                border-bottom: 1px solid #e0e0e0;
                border-right: 1px solid #e0e0e0;
                padding: 8px 12px;
                font-weight: 600;
                font-size: 12px;
                color: #333;
            }
            
            QPushButton {
                background-color: #007AFF;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 500;
                font-size: 12px;
            }
            
            QPushButton:hover {
                background-color: #0056D3;
            }
            
            QPushButton:pressed {
                background-color: #004399;
            }
            
            QPushButton.danger {
                background-color: #FF3B30;
            }
            
            QPushButton.danger:hover {
                background-color: #D32F2F;
            }
            
            QPushButton.secondary {
                background-color: #8E8E93;
            }
            
            QPushButton.secondary:hover {
                background-color: #636366;
            }
        """)
    
    def refresh_servers(self):
        """Refresh server list from CLI bridge."""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            servers = loop.run_until_complete(self.cli_bridge.get_servers())
            loop.close()
            
            self.servers_data = servers
            self.update_table()
            
        except Exception as e:
            print(f"Error refreshing servers: {e}")
    
    def update_table(self):
        """Update table with current server data."""
        self.setRowCount(len(self.servers_data))
        
        for row, server in enumerate(self.servers_data):
            # Select checkbox
            select_check = QCheckBox()
            select_check.stateChanged.connect(self.on_selection_changed)
            self.setCellWidget(row, 0, select_check)
            
            # Name
            name_item = QTableWidgetItem(server.get('name', 'Unknown'))
            name_item.setFlags(name_item.flags() ^ Qt.ItemIsEditable)
            self.setItem(row, 1, name_item)
            
            # Type
            server_type = server.get('type', 'unknown')
            type_item = QTableWidgetItem(server_type.upper())
            type_item.setFlags(type_item.flags() ^ Qt.ItemIsEditable)
            self.setItem(row, 2, type_item)
            
            # Status with color coding
            status = server.get('status', 'unknown')
            status_item = QTableWidgetItem(self.format_status(status))
            status_item.setFlags(status_item.flags() ^ Qt.ItemIsEditable)
            
            # Color code status
            if status == 'enabled':
                status_item.setBackground(QColor("#D4EDDA"))
                status_item.setForeground(QColor("#155724"))
            elif status == 'disabled':
                status_item.setBackground(QColor("#F8D7DA"))
                status_item.setForeground(QColor("#721C24"))
            else:
                status_item.setBackground(QColor("#FFF3CD"))
                status_item.setForeground(QColor("#856404"))
            
            self.setItem(row, 3, status_item)
            
            # Description
            description = server.get('description', 'No description')
            desc_item = QTableWidgetItem(description)
            desc_item.setFlags(desc_item.flags() ^ Qt.ItemIsEditable)
            self.setItem(row, 4, desc_item)
            
            # Actions
            self.create_action_buttons(row, server)
    
    def create_action_buttons(self, row: int, server: Dict):
        """Create action buttons for a server row."""
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(4, 2, 4, 2)
        actions_layout.setSpacing(4)
        
        server_name = server.get('name', '')
        status = server.get('status', 'unknown')
        
        # Enable/Disable button
        if status == 'enabled':
            toggle_btn = QPushButton("Disable")
            toggle_btn.setProperty("class", "danger")
            toggle_btn.clicked.connect(lambda: self.server_action_requested.emit("disable", server_name))
        else:
            toggle_btn = QPushButton("Enable")
            toggle_btn.clicked.connect(lambda: self.server_action_requested.emit("enable", server_name))
        
        toggle_btn.setFixedSize(60, 24)
        actions_layout.addWidget(toggle_btn)
        
        # Configure button
        config_btn = QPushButton("⚙")
        config_btn.setProperty("class", "secondary")
        config_btn.setFixedSize(24, 24)
        config_btn.setToolTip("Configure")
        config_btn.clicked.connect(lambda: self.server_action_requested.emit("configure", server_name))
        actions_layout.addWidget(config_btn)
        
        # Remove button
        remove_btn = QPushButton("✕")
        remove_btn.setProperty("class", "danger")
        remove_btn.setFixedSize(24, 24)
        remove_btn.setToolTip("Remove")
        remove_btn.clicked.connect(lambda: self.server_action_requested.emit("remove", server_name))
        actions_layout.addWidget(remove_btn)
        
        self.setCellWidget(row, 5, actions_widget)
    
    def format_status(self, status: str) -> str:
        """Format status for display."""
        status_map = {
            'enabled': '● Enabled',
            'disabled': '○ Disabled',
            'unknown': '◐ Unknown',
            'error': '✕ Error'
        }
        return status_map.get(status, f"◐ {status.title()}")
    
    def on_selection_changed(self):
        """Handle selection changes and emit selected servers."""
        selected_servers = []
        
        for row in range(self.rowCount()):
            checkbox = self.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                server_name = self.item(row, 1).text()
                selected_servers.append(server_name)
        
        self.servers_selected.emit(selected_servers)
    
    def select_all(self, checked: bool):
        """Select or deselect all servers."""
        for row in range(self.rowCount()):
            checkbox = self.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(checked)
    
    def get_selected_servers(self) -> List[str]:
        """Get list of selected server names."""
        selected = []
        for row in range(self.rowCount()):
            checkbox = self.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                selected.append(self.item(row, 1).text())
        return selected


class ModernMainWindow(QMainWindow):
    """Modern, professional main window for MCP Manager."""
    
    def __init__(self):
        super().__init__()
        self.cli_bridge = CLIBridge()
        self.selected_servers = []
        
        self.setup_window()
        self.setup_ui()
        self.setup_connections()
        
        # Set proper macOS app name (removes Python from menu)
        self.setWindowTitle("MCP Manager")
        
        # Apply modern styling
        self.apply_modern_styling()
    
    def setup_window(self):
        """Configure main window properties."""
        self.setWindowTitle("MCP Manager")
        self.setMinimumSize(1000, 700)
        self.resize(1400, 900)
        
        # Set window icon
        self.setWindowIcon(QIcon(":/icons/mcp_manager_app_icon.svg"))
    
    def setup_ui(self):
        """Set up the modern user interface."""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)
        
        # Create header with title and main actions
        self.create_header(main_layout)
        
        # Create main toolbar with all actions
        self.create_main_toolbar(main_layout)
        
        # Create bulk operations section
        self.create_bulk_operations(main_layout)
        
        # Create main content area
        self.create_main_content(main_layout)
        
        # Create status section
        self.create_status_section(main_layout)
    
    def create_header(self, layout):
        """Create application header with title and key actions."""
        header_frame = QFrame()
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # App title and subtitle
        title_layout = QVBoxLayout()
        
        title_label = QLabel("MCP Server Manager")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setWeight(QFont.Bold)
        title_label.setFont(title_font)
        title_layout.addWidget(title_label)
        
        subtitle_label = QLabel("Manage your Model Context Protocol servers")
        subtitle_font = QFont()
        subtitle_font.setPointSize(14)
        subtitle_label.setFont(subtitle_font)
        subtitle_label.setStyleSheet("color: #666;")
        title_layout.addWidget(subtitle_label)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        # Key action buttons
        self.add_server_btn = QPushButton("Add Server")
        self.add_server_btn.setIcon(QIcon(":/icons/add.svg"))
        self.add_server_btn.clicked.connect(self.show_add_server_dialog)
        header_layout.addWidget(self.add_server_btn)
        
        self.discover_btn = QPushButton("Discover Servers")
        self.discover_btn.setIcon(QIcon(":/icons/search.svg")) 
        self.discover_btn.clicked.connect(self.show_discovery_window)
        header_layout.addWidget(self.discover_btn)
        
        self.suite_manager_btn = QPushButton("Suite Manager")
        self.suite_manager_btn.setIcon(QIcon(":/icons/settings.svg"))
        self.suite_manager_btn.clicked.connect(self.show_suite_manager)
        header_layout.addWidget(self.suite_manager_btn)
        
        layout.addWidget(header_frame)
    
    def create_main_toolbar(self, layout):
        """Create main toolbar with all frequently used actions."""
        toolbar_frame = QFrame()
        toolbar_frame.setFrameStyle(QFrame.StyledPanel)
        toolbar_layout = QHBoxLayout(toolbar_frame)
        toolbar_layout.setContentsMargins(12, 8, 12, 8)
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setIcon(QIcon(":/icons/refresh.svg"))
        self.refresh_btn.clicked.connect(self.refresh_servers)
        toolbar_layout.addWidget(self.refresh_btn)
        
        toolbar_layout.addWidget(QLabel("|"))  # Separator
        
        # Filter controls
        toolbar_layout.addWidget(QLabel("Filter:"))
        
        self.type_filter = QComboBox()
        self.type_filter.addItems(["All Types", "NPM", "Docker", "Docker Desktop", "Custom"])
        self.type_filter.currentTextChanged.connect(self.apply_filters)
        toolbar_layout.addWidget(self.type_filter)
        
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All Status", "Enabled", "Disabled", "Unknown"])
        self.status_filter.currentTextChanged.connect(self.apply_filters)
        toolbar_layout.addWidget(self.status_filter)
        
        # Search
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search servers...")
        self.search_edit.textChanged.connect(self.apply_filters)
        toolbar_layout.addWidget(self.search_edit)
        
        toolbar_layout.addStretch()
        
        # Settings and help
        self.preferences_btn = QPushButton("Preferences")
        self.preferences_btn.setIcon(QIcon(":/icons/settings.svg"))
        self.preferences_btn.clicked.connect(self.show_preferences)
        toolbar_layout.addWidget(self.preferences_btn)
        
        layout.addWidget(toolbar_frame)
    
    def create_bulk_operations(self, layout):
        """Create bulk operations section."""
        bulk_frame = QFrame()
        bulk_frame.setFrameStyle(QFrame.StyledPanel)
        bulk_layout = QHBoxLayout(bulk_frame)
        bulk_layout.setContentsMargins(12, 8, 12, 8)
        
        # Selection controls
        self.select_all_check = QCheckBox("Select All")
        self.select_all_check.toggled.connect(self.toggle_select_all)
        bulk_layout.addWidget(self.select_all_check)
        
        self.selected_count_label = QLabel("0 selected")
        self.selected_count_label.setStyleSheet("color: #666; font-weight: bold;")
        bulk_layout.addWidget(self.selected_count_label)
        
        bulk_layout.addStretch()
        
        # Bulk action buttons
        self.bulk_enable_btn = QPushButton("Enable Selected")
        self.bulk_enable_btn.setIcon(QIcon(":/icons/server_online.svg"))
        self.bulk_enable_btn.setEnabled(False)
        self.bulk_enable_btn.clicked.connect(self.bulk_enable_servers)
        bulk_layout.addWidget(self.bulk_enable_btn)
        
        self.bulk_disable_btn = QPushButton("Disable Selected")
        self.bulk_disable_btn.setIcon(QIcon(":/icons/server_offline.svg"))
        self.bulk_disable_btn.setEnabled(False)
        self.bulk_disable_btn.clicked.connect(self.bulk_disable_servers)
        bulk_layout.addWidget(self.bulk_disable_btn)
        
        self.bulk_remove_btn = QPushButton("Remove Selected")
        self.bulk_remove_btn.setIcon(QIcon(":/icons/remove.svg"))
        self.bulk_remove_btn.setProperty("class", "danger")
        self.bulk_remove_btn.setEnabled(False)
        self.bulk_remove_btn.clicked.connect(self.bulk_remove_servers)
        bulk_layout.addWidget(self.bulk_remove_btn)
        
        layout.addWidget(bulk_frame)
    
    def create_main_content(self, layout):
        """Create main content area with server list."""
        # Server list
        self.server_list = ModernServerListWidget()
        self.server_list.servers_selected.connect(self.on_servers_selected)
        self.server_list.server_action_requested.connect(self.handle_server_action)
        
        layout.addWidget(self.server_list)
    
    def create_status_section(self, layout):
        """Create status and progress section."""
        status_frame = QFrame()
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(0, 8, 0, 0)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #333; font-size: 13px;")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        status_layout.addWidget(self.progress_bar)
        
        layout.addWidget(status_frame)
    
    def setup_connections(self):
        """Set up signal connections."""
        # Auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_servers)
        self.refresh_timer.start(10000)  # 10 seconds
    
    def apply_modern_styling(self):
        """Apply modern macOS styling to the entire window."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f7;
            }
            
            QFrame {
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            
            QPushButton {
                background-color: #007AFF;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 13px;
            }
            
            QPushButton:hover {
                background-color: #0056D3;
            }
            
            QPushButton:pressed {
                background-color: #004399;
            }
            
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            
            QPushButton[class="danger"] {
                background-color: #FF3B30;
            }
            
            QPushButton[class="danger"]:hover {
                background-color: #D32F2F;
            }
            
            QPushButton[class="secondary"] {
                background-color: #8E8E93;
            }
            
            QPushButton[class="secondary"]:hover {
                background-color: #636366;
            }
            
            QComboBox {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 13px;
            }
            
            QComboBox:hover {
                border-color: #007AFF;
            }
            
            QLineEdit {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 13px;
            }
            
            QLineEdit:focus {
                border-color: #007AFF;
                outline: none;
            }
            
            QCheckBox {
                font-size: 13px;
                color: #333;
            }
            
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                background-color: white;
            }
            
            QCheckBox::indicator:checked {
                background-color: #007AFF;
                border-color: #007AFF;
            }
            
            QLabel {
                color: #333;
                font-size: 13px;
            }
        """)
    
    def on_servers_selected(self, selected_servers):
        """Handle server selection changes."""
        self.selected_servers = selected_servers
        count = len(selected_servers)
        
        # Update UI based on selection
        self.selected_count_label.setText(f"{count} selected")
        
        has_selection = count > 0
        self.bulk_enable_btn.setEnabled(has_selection)
        self.bulk_disable_btn.setEnabled(has_selection)
        self.bulk_remove_btn.setEnabled(has_selection)
        
        # Update select all checkbox
        total_servers = self.server_list.rowCount()
        if count == 0:
            self.select_all_check.setCheckState(Qt.Unchecked)
        elif count == total_servers:
            self.select_all_check.setCheckState(Qt.Checked)
        else:
            self.select_all_check.setCheckState(Qt.PartiallyChecked)
    
    def toggle_select_all(self, checked):
        """Toggle selection of all servers."""
        self.server_list.select_all(checked)
    
    def refresh_servers(self):
        """Refresh server list."""
        self.server_list.refresh_servers()
        self.status_label.setText("Server list refreshed")
    
    def apply_filters(self):
        """Apply current filters to server list."""
        # This would implement filtering logic
        self.status_label.setText("Filters applied")
    
    def handle_server_action(self, action, server_name):
        """Handle individual server actions."""
        try:
            if action == "enable":
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success = loop.run_until_complete(self.cli_bridge.enable_server(server_name))
                loop.close()
                
                if success:
                    self.status_label.setText(f"Enabled server '{server_name}'")
                    self.server_list.refresh_servers()
                else:
                    self.status_label.setText(f"Failed to enable '{server_name}'")
            
            elif action == "disable":
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success = loop.run_until_complete(self.cli_bridge.disable_server(server_name))
                loop.close()
                
                if success:
                    self.status_label.setText(f"Disabled server '{server_name}'")
                    self.server_list.refresh_servers()
                else:
                    self.status_label.setText(f"Failed to disable '{server_name}'")
            
            elif action == "configure":
                self.configure_server(server_name)
            
            elif action == "remove":
                self.remove_server(server_name)
                
        except Exception as e:
            self.status_label.setText(f"Error: {e}")
    
    def bulk_enable_servers(self):
        """Enable all selected servers."""
        if not self.selected_servers:
            return
        
        self.show_progress("Enabling servers...")
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            success_count = 0
            for server_name in self.selected_servers:
                success = loop.run_until_complete(self.cli_bridge.enable_server(server_name))
                if success:
                    success_count += 1
            
            loop.close()
            
            self.hide_progress()
            self.status_label.setText(f"Enabled {success_count}/{len(self.selected_servers)} servers")
            self.server_list.refresh_servers()
            
        except Exception as e:
            self.hide_progress()
            self.status_label.setText(f"Error enabling servers: {e}")
    
    def bulk_disable_servers(self):
        """Disable all selected servers."""
        if not self.selected_servers:
            return
        
        self.show_progress("Disabling servers...")
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            success_count = 0
            for server_name in self.selected_servers:
                success = loop.run_until_complete(self.cli_bridge.disable_server(server_name))
                if success:
                    success_count += 1
            
            loop.close()
            
            self.hide_progress()
            self.status_label.setText(f"Disabled {success_count}/{len(self.selected_servers)} servers")
            self.server_list.refresh_servers()
            
        except Exception as e:
            self.hide_progress()
            self.status_label.setText(f"Error disabling servers: {e}")
    
    def bulk_remove_servers(self):
        """Remove all selected servers."""
        if not self.selected_servers:
            return
        
        # Confirm bulk removal
        reply = QMessageBox.question(
            self,
            "Confirm Bulk Removal",
            f"Are you sure you want to remove {len(self.selected_servers)} selected servers?\\n\\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        self.show_progress("Removing servers...")
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            success_count = 0
            for server_name in self.selected_servers:
                success = loop.run_until_complete(self.cli_bridge.remove_server(server_name))
                if success:
                    success_count += 1
            
            loop.close()
            
            self.hide_progress()
            self.status_label.setText(f"Removed {success_count}/{len(self.selected_servers)} servers")
            self.server_list.refresh_servers()
            
        except Exception as e:
            self.hide_progress()
            self.status_label.setText(f"Error removing servers: {e}")
    
    def show_progress(self, message):
        """Show progress bar with message."""
        self.status_label.setText(message)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
    
    def hide_progress(self):
        """Hide progress bar."""
        self.progress_bar.setVisible(False)
    
    # Dialog methods
    def show_add_server_dialog(self):
        """Show add server dialog."""
        from .server_detail import AddServerDialog
        dialog = AddServerDialog(self, self.cli_bridge)
        dialog.server_added.connect(self.on_server_added)
        dialog.exec()
    
    def show_discovery_window(self):
        """Show discovery window."""
        from .discovery_window import DiscoveryWindow
        discovery = DiscoveryWindow(self, self.cli_bridge)
        discovery.server_installed.connect(self.on_server_installed)
        discovery.show()
        discovery.raise_()
    
    def show_suite_manager(self):
        """Show suite manager."""
        from .suite_manager import SuiteManagerWindow
        suite_mgr = SuiteManagerWindow(self, self.cli_bridge)
        suite_mgr.show()
        suite_mgr.raise_()
    
    def show_preferences(self):
        """Show preferences dialog."""
        from .preferences import PreferencesDialog
        dialog = PreferencesDialog(self, self.cli_bridge)
        dialog.settings_changed.connect(self.on_settings_changed)
        dialog.exec()
    
    def configure_server(self, server_name):
        """Configure a specific server."""
        # Get server data and show edit dialog
        servers = self.server_list.servers_data
        server_data = next((s for s in servers if s.get('name') == server_name), None)
        
        if server_data:
            from .server_detail import EditServerDialog
            dialog = EditServerDialog(self, self.cli_bridge, server_data)
            dialog.server_updated.connect(self.on_server_updated)
            dialog.exec()
    
    def remove_server(self, server_name):
        """Remove a specific server."""
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Are you sure you want to remove server '{server_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                success = loop.run_until_complete(self.cli_bridge.remove_server(server_name))
                loop.close()
                
                if success:
                    self.status_label.setText(f"Removed server '{server_name}'")
                    self.server_list.refresh_servers()
                else:
                    self.status_label.setText(f"Failed to remove '{server_name}'")
                    
            except Exception as e:
                self.status_label.setText(f"Error removing server: {e}")
    
    # Event handlers
    def on_server_added(self, server_data):
        """Handle server addition."""
        self.status_label.setText(f"Added server '{server_data['name']}'")
        self.server_list.refresh_servers()
    
    def on_server_updated(self, server_data):
        """Handle server update."""
        self.status_label.setText(f"Updated server '{server_data['name']}'")
        self.server_list.refresh_servers()
    
    def on_server_installed(self, server_data):
        """Handle server installation."""
        self.status_label.setText("Server installed successfully")
        self.server_list.refresh_servers()
    
    def on_settings_changed(self, settings):
        """Handle settings changes."""
        self.status_label.setText("Settings updated")
        
        # Update refresh interval if changed
        if 'server_refresh_interval' in settings:
            interval = settings['server_refresh_interval'] * 1000
            self.refresh_timer.setInterval(interval)