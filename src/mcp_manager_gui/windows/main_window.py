"""
MCP Manager GUI - Main Window

This module provides the primary application window with native macOS layout,
including sidebar for server list, main panel for details, and status bar.
"""

import asyncio
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter, 
    QListWidget, QListWidgetItem, QStackedWidget, QStatusBar,
    QMenuBar, QMenu, QLabel, QPushButton, QFrame, QHeaderView,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QGroupBox,
    QProgressBar, QMessageBox, QDialog, QDialogButtonBox,
    QFormLayout, QLineEdit, QComboBox, QCheckBox, QSpinBox
)
from PySide6.QtCore import (
    Qt, QTimer, QThread, Signal, QSize, QSettings,
    QPropertyAnimation, QEasingCurve, QRect
)
from PySide6.QtGui import (
    QAction, QIcon, QPixmap, QPainter, QFont, QKeySequence,
    QPalette, QColor
)

from mcp_manager.utils.logging import get_logger
from ..services.cli_bridge import CLIBridge


logger = get_logger(__name__)


class ServerStatusIndicator(QWidget):
    """Visual indicator for server status."""
    
    def __init__(self, status: str = "unknown", parent=None):
        super().__init__(parent)
        self.status = status
        self.setFixedSize(12, 12)
        self.setToolTip(f"Status: {status.title()}")
    
    def paintEvent(self, event):
        """Paint the status indicator."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Status colors
        colors = {
            "connected": QColor(52, 199, 89),    # Green
            "disconnected": QColor(255, 69, 58),  # Red
            "disabled": QColor(142, 142, 147),    # Gray
            "unknown": QColor(255, 149, 0),      # Orange
            "syncing": QColor(0, 122, 255)       # Blue
        }
        
        color = colors.get(self.status.lower(), colors["unknown"])
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(1, 1, 10, 10)
    
    def set_status(self, status: str):
        """Update the status and repaint."""
        self.status = status
        self.setToolTip(f"Status: {status.title()}")
        self.update()


class ServerListWidget(QListWidget):
    """Custom list widget for displaying MCP servers."""
    
    serverSelected = Signal(str)  # Emitted when a server is selected
    serverToggled = Signal(str, bool)  # Emitted when server is enabled/disabled
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.servers: List[Dict[str, Any]] = []
        
        # Setup list appearance
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QListWidget.SingleSelection)
        self.setMinimumWidth(250)
        
        # Connect signals
        self.itemClicked.connect(self._on_item_clicked)
        
    def add_server(self, server_data: Dict[str, Any]):
        """Add a server to the list."""
        item = QListWidgetItem()
        widget = self._create_server_widget(server_data)
        
        item.setSizeHint(widget.sizeHint())
        self.addItem(item)
        self.setItemWidget(item, widget)
        
        # Store server data
        item.setData(Qt.UserRole, server_data)
    
    def _create_server_widget(self, server_data: Dict[str, Any]) -> QWidget:
        """Create a widget for displaying server information."""
        widget = QFrame()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(8, 4, 8, 4)
        
        # Status indicator
        status = server_data.get('claude_status', 'unknown').lower()
        indicator = ServerStatusIndicator(status)
        layout.addWidget(indicator)
        
        # Server info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(0)
        
        # Server name
        name_label = QLabel(server_data.get('name', 'Unknown'))
        name_font = QFont()
        name_font.setBold(True)
        name_label.setFont(name_font)
        info_layout.addWidget(name_label)
        
        # Server type and description
        type_text = server_data.get('server_type', 'custom')
        desc_text = server_data.get('description', '')
        if desc_text:
            subtitle = f"{type_text} • {desc_text[:30]}..."
        else:
            subtitle = type_text
            
        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet("color: gray; font-size: 11px;")
        info_layout.addWidget(subtitle_label)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        # Enable/disable toggle
        enabled = server_data.get('enabled', False)
        toggle_btn = QPushButton("●" if enabled else "○")
        toggle_btn.setFixedSize(24, 24)
        toggle_btn.setFlat(True)
        toggle_btn.setToolTip("Enable/Disable Server")
        toggle_btn.setStyleSheet(
            f"color: {'#34C759' if enabled else '#8E8E93'}; font-size: 16px; border: none;"
        )
        
        # Store reference for updates
        toggle_btn.clicked.connect(
            lambda: self.serverToggled.emit(server_data['name'], not enabled)
        )
        
        layout.addWidget(toggle_btn)
        
        return widget
    
    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle item selection."""
        server_data = item.data(Qt.UserRole)
        if server_data:
            self.serverSelected.emit(server_data['name'])
    
    def update_servers(self, servers: List[Dict[str, Any]]):
        """Update the server list."""
        self.clear()
        self.servers = servers
        
        for server in servers:
            self.add_server(server)
    
    def update_server_status(self, server_name: str, status: str):
        """Update the status of a specific server."""
        for i in range(self.count()):
            item = self.item(i)
            server_data = item.data(Qt.UserRole)
            
            if server_data and server_data.get('name') == server_name:
                server_data['claude_status'] = status
                item.setData(Qt.UserRole, server_data)
                
                # Update the widget
                widget = self.itemWidget(item)
                if widget:
                    # Find and update status indicator
                    indicator = widget.findChild(ServerStatusIndicator)
                    if indicator:
                        indicator.set_status(status)
                break


class ServerDetailWidget(QStackedWidget):
    """Widget for displaying detailed server information."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_server: Optional[str] = None
        
        # Create default (empty) view
        self._create_empty_view()
        
        # Create server detail view
        self._create_detail_view()
    
    def _create_empty_view(self):
        """Create the empty state view."""
        empty_widget = QWidget()
        layout = QVBoxLayout(empty_widget)
        layout.setAlignment(Qt.AlignCenter)
        
        # Empty state message
        label = QLabel("Select a server to view details")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: gray; font-size: 14px;")
        layout.addWidget(label)
        
        self.addWidget(empty_widget)
        self.empty_index = 0
    
    def _create_detail_view(self):
        """Create the server detail view."""
        detail_widget = QWidget()
        layout = QVBoxLayout(detail_widget)
        
        # Server header
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.StyledPanel)
        header_layout = QHBoxLayout(header_frame)
        
        self.server_name_label = QLabel("Server Name")
        header_font = QFont()
        header_font.setBold(True)
        header_font.setPointSize(16)
        self.server_name_label.setFont(header_font)
        header_layout.addWidget(self.server_name_label)
        
        header_layout.addStretch()
        
        self.status_indicator = ServerStatusIndicator()
        header_layout.addWidget(self.status_indicator)
        
        layout.addWidget(header_frame)
        
        # Server information tabs/sections
        info_splitter = QSplitter(Qt.Vertical)
        
        # Basic information
        basic_group = QGroupBox("Basic Information")
        basic_layout = QFormLayout(basic_group)
        
        self.type_label = QLabel()
        self.command_label = QLabel()
        self.description_label = QLabel()
        
        basic_layout.addRow("Type:", self.type_label)
        basic_layout.addRow("Command:", self.command_label)
        basic_layout.addRow("Description:", self.description_label)
        
        info_splitter.addWidget(basic_group)
        
        # Tools/Capabilities
        tools_group = QGroupBox("Available Tools")
        tools_layout = QVBoxLayout(tools_group)
        
        self.tools_tree = QTreeWidget()
        self.tools_tree.setHeaderLabels(["Tool Name", "Description"])
        self.tools_tree.header().setSectionResizeMode(QHeaderView.ResizeToContents)
        
        tools_layout.addWidget(self.tools_tree)
        info_splitter.addWidget(tools_group)
        
        # Configuration
        config_group = QGroupBox("Configuration")
        config_layout = QVBoxLayout(config_group)
        
        self.config_text = QTextEdit()
        self.config_text.setFont(QFont("Monaco", 11))  # Monospace font
        self.config_text.setMaximumHeight(150)
        
        config_layout.addWidget(self.config_text)
        info_splitter.addWidget(config_group)
        
        # Action buttons
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        button_layout.addStretch()
        
        self.enable_btn = QPushButton("Enable")
        self.disable_btn = QPushButton("Disable")
        self.remove_btn = QPushButton("Remove")
        self.configure_btn = QPushButton("Configure")
        
        # Style buttons
        self.enable_btn.setStyleSheet("QPushButton { background-color: #34C759; color: white; }")
        self.disable_btn.setStyleSheet("QPushButton { background-color: #FF3B30; color: white; }")
        self.remove_btn.setStyleSheet("QPushButton { background-color: #FF9500; color: white; }")
        
        button_layout.addWidget(self.configure_btn)
        button_layout.addWidget(self.enable_btn)
        button_layout.addWidget(self.disable_btn)
        button_layout.addWidget(self.remove_btn)
        
        layout.addWidget(info_splitter)
        layout.addWidget(button_frame)
        
        self.addWidget(detail_widget)
        self.detail_index = 1
    
    def show_server_details(self, server_data: Dict[str, Any]):
        """Display details for the selected server."""
        self.current_server = server_data.get('name')
        
        # Update header
        self.server_name_label.setText(server_data.get('name', 'Unknown'))
        status = server_data.get('claude_status', 'unknown')
        self.status_indicator.set_status(status)
        
        # Update basic information
        self.type_label.setText(server_data.get('server_type', 'N/A'))
        self.command_label.setText(server_data.get('command', 'N/A'))
        self.description_label.setText(server_data.get('description', 'N/A'))
        
        # Update tools
        self.tools_tree.clear()
        tools = server_data.get('tools', [])
        for tool in tools:
            item = QTreeWidgetItem([
                tool.get('name', 'Unknown'),
                tool.get('description', 'No description')
            ])
            self.tools_tree.addTopLevelItem(item)
        
        if not tools:
            item = QTreeWidgetItem(['No tools available', ''])
            item.setDisabled(True)
            self.tools_tree.addTopLevelItem(item)
        
        # Update configuration
        config_text = f"Name: {server_data.get('name', 'N/A')}\n"
        config_text += f"Type: {server_data.get('server_type', 'N/A')}\n"
        config_text += f"Command: {server_data.get('command', 'N/A')}\n"
        
        if server_data.get('args'):
            config_text += f"Arguments: {', '.join(server_data['args'])}\n"
        
        if server_data.get('env'):
            config_text += "Environment:\n"
            for key, value in server_data['env'].items():
                config_text += f"  {key} = {value}\n"
        
        self.config_text.setPlainText(config_text)
        
        # Update button states
        enabled = server_data.get('enabled', False)
        self.enable_btn.setEnabled(not enabled)
        self.disable_btn.setEnabled(enabled)
        
        # Show detail view
        self.setCurrentIndex(self.detail_index)
    
    def show_empty_state(self):
        """Show the empty state view."""
        self.current_server = None
        self.setCurrentIndex(self.empty_index)


class MainWindow(QMainWindow):
    """Main application window for MCP Manager GUI."""
    
    def __init__(self, cli_bridge: CLIBridge, parent=None):
        super().__init__(parent)
        
        self.cli_bridge = cli_bridge
        self.settings = QSettings()
        
        # Setup UI
        self._setup_ui()
        self._setup_menu_bar()
        self._setup_status_bar()
        self._setup_connections()
        
        # Setup periodic updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._refresh_servers)
        self.update_timer.start(5000)  # Refresh every 5 seconds
        
        # Initial data load
        self._refresh_servers()
    
    def _setup_ui(self):
        """Setup the main user interface."""
        # Set window properties
        self.setWindowTitle("MCP Manager")
        self.setMinimumSize(900, 600)
        self.resize(1200, 800)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create main splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        
        # Left sidebar (server list)
        sidebar_frame = QFrame()
        sidebar_frame.setFrameStyle(QFrame.StyledPanel)
        sidebar_frame.setMinimumWidth(280)
        sidebar_frame.setMaximumWidth(400)
        
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setContentsMargins(4, 4, 4, 4)
        
        # Sidebar header
        header_layout = QHBoxLayout()
        servers_label = QLabel("MCP Servers")
        servers_font = QFont()
        servers_font.setBold(True)
        servers_font.setPointSize(14)
        servers_label.setFont(servers_font)
        header_layout.addWidget(servers_label)
        
        header_layout.addStretch()
        
        # Add server button
        add_btn = QPushButton("+")
        add_btn.setFixedSize(24, 24)
        add_btn.setToolTip("Add Server")
        add_btn.clicked.connect(self._show_add_server_dialog)
        header_layout.addWidget(add_btn)
        
        # Refresh button
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(24, 24)
        refresh_btn.setToolTip("Refresh")
        refresh_btn.clicked.connect(self._refresh_servers)
        header_layout.addWidget(refresh_btn)
        
        sidebar_layout.addLayout(header_layout)
        
        # Server list
        self.server_list = ServerListWidget()
        sidebar_layout.addWidget(self.server_list)
        
        splitter.addWidget(sidebar_frame)
        
        # Right panel (server details)
        self.server_detail = ServerDetailWidget()
        splitter.addWidget(self.server_detail)
        
        # Set splitter proportions
        splitter.setSizes([300, 700])
        
        main_layout.addWidget(splitter)
    
    def _setup_menu_bar(self):
        """Setup native macOS menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        add_server_action = QAction("Add Server...", self)
        add_server_action.setShortcut(QKeySequence("Cmd+N"))
        add_server_action.triggered.connect(self._show_add_server_dialog)
        file_menu.addAction(add_server_action)
        
        file_menu.addSeparator()
        
        refresh_action = QAction("Refresh", self)
        refresh_action.setShortcut(QKeySequence("Cmd+R"))
        refresh_action.triggered.connect(self._refresh_servers)
        file_menu.addAction(refresh_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("Tools")
        
        discover_action = QAction("Discover Servers...", self)
        discover_action.setShortcut(QKeySequence("Cmd+D"))
        discover_action.triggered.connect(self._show_discovery_window)
        tools_menu.addAction(discover_action)
        
        cleanup_action = QAction("Cleanup Configuration", self)
        cleanup_action.triggered.connect(self._cleanup_config)
        tools_menu.addAction(cleanup_action)
        
        tools_menu.addSeparator()
        
        suite_manager_action = QAction("Suite Manager...", self)
        suite_manager_action.setShortcut(QKeySequence("Cmd+Shift+S"))
        suite_manager_action.triggered.connect(self._show_suite_manager)
        tools_menu.addAction(suite_manager_action)
        
        preferences_action = QAction("Preferences...", self)
        preferences_action.setShortcut(QKeySequence("Cmd+,"))
        preferences_action.triggered.connect(self._show_preferences)
        tools_menu.addAction(preferences_action)
        
        # Window menu
        window_menu = menubar.addMenu("Window")
        
        minimize_action = QAction("Minimize", self)
        minimize_action.setShortcut(QKeySequence("Cmd+M"))
        minimize_action.triggered.connect(self.showMinimized)
        window_menu.addAction(minimize_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About MCP Manager", self)
        about_action.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_action)
    
    def _setup_status_bar(self):
        """Setup status bar."""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        
        # Server count label
        self.server_count_label = QLabel("0 servers")
        status_bar.addWidget(self.server_count_label)
        
        status_bar.addPermanentWidget(QLabel("Ready"))
        
        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        status_bar.addPermanentWidget(self.progress_bar)
    
    def _setup_connections(self):
        """Setup signal connections."""
        self.server_list.serverSelected.connect(self._on_server_selected)
        self.server_list.serverToggled.connect(self._on_server_toggled)
        
        # Connect detail buttons
        self.server_detail.enable_btn.clicked.connect(self._enable_current_server)
        self.server_detail.disable_btn.clicked.connect(self._disable_current_server)
        self.server_detail.remove_btn.clicked.connect(self._remove_current_server)
        self.server_detail.configure_btn.clicked.connect(self._configure_current_server)
    
    def _refresh_servers(self):
        """Refresh the server list."""
        try:
            # Run async operation
            loop = asyncio.get_event_loop()
            servers = loop.run_until_complete(self.cli_bridge.get_servers())
            
            # Update UI
            self.server_list.update_servers(servers)
            self.server_count_label.setText(f"{len(servers)} servers")
            
            logger.debug(f"Refreshed server list: {len(servers)} servers")
            
        except Exception as e:
            logger.error(f"Error refreshing servers: {e}")
            self.statusBar().showMessage(f"Error: {e}", 3000)
    
    def _on_server_selected(self, server_name: str):
        """Handle server selection."""
        try:
            # Get server details
            loop = asyncio.get_event_loop()
            server_data = loop.run_until_complete(
                self.cli_bridge.get_server_details(server_name)
            )
            
            if server_data:
                self.server_detail.show_server_details(server_data)
            else:
                self.server_detail.show_empty_state()
                
        except Exception as e:
            logger.error(f"Error getting server details: {e}")
            self.server_detail.show_empty_state()
    
    def _on_server_toggled(self, server_name: str, enable: bool):
        """Handle server enable/disable toggle."""
        try:
            loop = asyncio.get_event_loop()
            if enable:
                success = loop.run_until_complete(
                    self.cli_bridge.enable_server(server_name)
                )
            else:
                success = loop.run_until_complete(
                    self.cli_bridge.disable_server(server_name)
                )
            
            if success:
                self.statusBar().showMessage(
                    f"Server '{server_name}' {'enabled' if enable else 'disabled'}", 
                    2000
                )
                # Refresh to update status
                self._refresh_servers()
            else:
                self.statusBar().showMessage(
                    f"Failed to {'enable' if enable else 'disable'} server '{server_name}'", 
                    3000
                )
                
        except Exception as e:
            logger.error(f"Error toggling server: {e}")
            self.statusBar().showMessage(f"Error: {e}", 3000)
    
    def _enable_current_server(self):
        """Enable the currently selected server."""
        if self.server_detail.current_server:
            self._on_server_toggled(self.server_detail.current_server, True)
    
    def _disable_current_server(self):
        """Disable the currently selected server."""
        if self.server_detail.current_server:
            self._on_server_toggled(self.server_detail.current_server, False)
    
    def _remove_current_server(self):
        """Remove the currently selected server."""
        if not self.server_detail.current_server:
            return
        
        # Confirm removal
        reply = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Are you sure you want to remove server '{self.server_detail.current_server}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                loop = asyncio.get_event_loop()
                success = loop.run_until_complete(
                    self.cli_bridge.remove_server(self.server_detail.current_server)
                )
                
                if success:
                    self.statusBar().showMessage(
                        f"Server '{self.server_detail.current_server}' removed", 2000
                    )
                    self.server_detail.show_empty_state()
                    self._refresh_servers()
                else:
                    self.statusBar().showMessage(
                        f"Failed to remove server '{self.server_detail.current_server}'", 3000
                    )
                    
            except Exception as e:
                logger.error(f"Error removing server: {e}")
                self.statusBar().showMessage(f"Error: {e}", 3000)
    
    def _configure_current_server(self):
        """Configure the currently selected server."""
        if not hasattr(self.main_panel, 'current_server') or not self.main_panel.current_server:
            QMessageBox.warning(
                self,
                "No Selection",
                "Please select a server to configure."
            )
            return
        
        server_data = self.main_panel.current_server
        
        from .server_detail import EditServerDialog
        dialog = EditServerDialog(self, self.cli_bridge, server_data)
        dialog.server_updated.connect(self._on_server_updated)
        dialog.exec()
    
    def _show_add_server_dialog(self):
        """Show the add server dialog."""
        from .server_detail import AddServerDialog
        dialog = AddServerDialog(self, self.cli_bridge)
        dialog.server_added.connect(self._on_server_added)
        dialog.exec()
    
    def _show_discovery_window(self):
        """Show the server discovery window."""
        from .discovery_window import DiscoveryWindow
        
        # Create discovery window as a separate window
        discovery_window = DiscoveryWindow(self, self.cli_bridge)
        discovery_window.server_installed.connect(self._on_server_installed)
        discovery_window.show()
        discovery_window.raise_()
        discovery_window.activateWindow()
    
    def _on_server_added(self, server_data):
        """Handle server addition."""
        try:
            self.statusBar().showMessage(f"Server '{server_data['name']}' added successfully", 3000)
            # Refresh server list
            asyncio.run(self._refresh_server_list())
        except Exception as e:
            logger.error(f"Error handling server addition: {e}")
    
    def _on_server_updated(self, server_data):
        """Handle server update."""
        try:
            self.statusBar().showMessage(f"Server '{server_data['name']}' updated successfully", 3000)
            # Refresh server list
            asyncio.run(self._refresh_server_list())
        except Exception as e:
            logger.error(f"Error handling server update: {e}")
    
    def _on_server_installed(self, server_data):
        """Handle server installation from discovery."""
        try:
            self.statusBar().showMessage(f"Server installed successfully", 3000)
            # Refresh server list
            asyncio.run(self._refresh_server_list())
        except Exception as e:
            logger.error(f"Error handling server installation: {e}")
    
    def _cleanup_config(self):
        """Cleanup configuration."""
        try:
            loop = asyncio.get_event_loop()
            success = loop.run_until_complete(self.cli_bridge.cleanup_config())
            
            if success:
                QMessageBox.information(
                    self, 
                    "Cleanup Complete", 
                    "Configuration cleanup completed successfully."
                )
                self._refresh_servers()
            else:
                QMessageBox.warning(
                    self, 
                    "Cleanup Failed", 
                    "Configuration cleanup failed. Check logs for details."
                )
                
        except Exception as e:
            logger.error(f"Error during config cleanup: {e}")
            QMessageBox.critical(self, "Error", f"Cleanup error: {e}")
    
    def _show_about_dialog(self):
        """Show the about dialog."""
        about_text = """
        <h2>MCP Manager</h2>
        <p>Version 2.0.0</p>
        <p>A professional macOS application for managing MCP (Model Context Protocol) servers.</p>
        <p>Built with PySide6 and modern macOS design principles.</p>
        <p><a href="https://mcp-manager.dev">mcp-manager.dev</a></p>
        """
        
        QMessageBox.about(self, "About MCP Manager", about_text)
    
    def _show_suite_manager(self):
        """Show the suite manager window."""
        from .suite_manager import SuiteManagerWindow
        
        # Create suite manager as a separate window
        suite_manager = SuiteManagerWindow(self, self.cli_bridge)
        suite_manager.show()
        suite_manager.raise_()
        suite_manager.activateWindow()
    
    def _show_preferences(self):
        """Show the preferences dialog."""
        from .preferences import PreferencesDialog
        
        dialog = PreferencesDialog(self, self.cli_bridge)
        dialog.settings_changed.connect(self._on_settings_changed)
        dialog.exec()
    
    def _on_settings_changed(self, settings):
        """Handle settings changes."""
        try:
            # Apply any immediate UI changes based on settings
            self.statusBar().showMessage("Settings applied successfully", 2000)
            
            # Update refresh intervals if they changed
            if 'server_refresh_interval' in settings:
                interval = settings['server_refresh_interval'] * 1000  # Convert to milliseconds
                self.refresh_timer.setInterval(interval)
            
        except Exception as e:
            logger.error(f"Error applying settings: {e}")
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Save window state
        settings = QSettings()
        settings.setValue("window/geometry", self.saveGeometry())
        settings.setValue("window/state", self.saveState())
        
        # Stop timers
        self.update_timer.stop()
        
        # Accept close
        event.accept()
        logger.info("Main window closed")