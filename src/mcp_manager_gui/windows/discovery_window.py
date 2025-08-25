"""
Discovery Window - Server discovery and installation interface.

Provides comprehensive server discovery with search, filtering, and one-click installation.
"""

import asyncio
from typing import Dict, List, Optional, Any
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QTextEdit, QLabel, QProgressDialog, QMessageBox, QHeaderView,
    QGroupBox, QFormLayout, QSpinBox, QCheckBox, QTabWidget,
    QListWidget, QListWidgetItem, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread, QObject, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QBrush

from ..services.cli_bridge import CLIBridge


class DiscoveryWorker(QObject):
    """Background worker for server discovery operations."""
    
    discovery_completed = Signal(list)
    discovery_progress = Signal(str)  # Progress message
    error_occurred = Signal(str)
    
    def __init__(self, cli_bridge: CLIBridge):
        super().__init__()
        self.cli_bridge = cli_bridge
        self._cancelled = False
    
    def cancel(self):
        """Cancel the discovery operation."""
        self._cancelled = True
    
    async def discover_servers(self, query: str = None, server_type: str = None, 
                             limit: int = None, update_catalog: bool = False):
        """Perform server discovery."""
        try:
            if update_catalog:
                self.discovery_progress.emit("Updating server catalog...")
                await self.cli_bridge.update_discovery_catalog()
            
            if self._cancelled:
                return
            
            self.discovery_progress.emit("Searching for servers...")
            results = await self.cli_bridge.discover_servers(
                query=query,
                server_type=server_type,
                limit=limit
            )
            
            if not self._cancelled:
                self.discovery_completed.emit(results)
            
        except Exception as e:
            if not self._cancelled:
                self.error_occurred.emit(str(e))


class InstallationWorker(QObject):
    """Background worker for server installation."""
    
    installation_completed = Signal(bool, str)  # success, message
    installation_progress = Signal(str)
    error_occurred = Signal(str)
    
    def __init__(self, cli_bridge: CLIBridge):
        super().__init__()
        self.cli_bridge = cli_bridge
    
    async def install_package(self, install_id: str, server_name: str = None):
        """Install a package by install ID."""
        try:
            self.installation_progress.emit(f"Installing {install_id}...")
            
            success = await self.cli_bridge.install_package(install_id)
            
            if success:
                message = f"Successfully installed {install_id}"
                if server_name:
                    message += f" as '{server_name}'"
                self.installation_completed.emit(True, message)
            else:
                self.installation_completed.emit(False, f"Failed to install {install_id}")
                
        except Exception as e:
            self.error_occurred.emit(str(e))


class ServerPreviewWidget(QWidget):
    """Widget for displaying detailed server information."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.clear_preview()
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Server icon and name
        header_layout = QHBoxLayout()
        
        self.server_icon = QLabel()
        self.server_icon.setFixedSize(48, 48)
        self.server_icon.setStyleSheet("""
            QLabel {
                border: 2px solid #d1d1d1;
                border-radius: 8px;
                background-color: white;
            }
        """)
        header_layout.addWidget(self.server_icon)
        
        header_info = QVBoxLayout()
        self.server_name = QLabel()
        self.server_name.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_info.addWidget(self.server_name)
        
        self.server_type = QLabel()
        self.server_type.setStyleSheet("color: #666; font-size: 12px;")
        header_info.addWidget(self.server_type)
        
        header_layout.addLayout(header_info)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Tabs for different information
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Overview tab
        self.create_overview_tab()
        
        # Details tab
        self.create_details_tab()
        
        # Installation tab
        self.create_installation_tab()
    
    def create_overview_tab(self):
        """Create overview tab with basic information."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Description
        self.description_text = QTextEdit()
        self.description_text.setReadOnly(True)
        self.description_text.setMaximumHeight(100)
        layout.addWidget(QLabel("Description:"))
        layout.addWidget(self.description_text)
        
        # Key information
        info_form = QFormLayout()
        
        self.install_id_label = QLabel()
        info_form.addRow("Install ID:", self.install_id_label)
        
        self.quality_score_label = QLabel()
        info_form.addRow("Quality Score:", self.quality_score_label)
        
        self.category_label = QLabel()
        info_form.addRow("Category:", self.category_label)
        
        self.version_label = QLabel()
        info_form.addRow("Version:", self.version_label)
        
        layout.addLayout(info_form)
        
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Overview")
    
    def create_details_tab(self):
        """Create details tab with technical information."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Technical details
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        scroll_layout.addWidget(self.details_text)
        
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
        
        self.tab_widget.addTab(tab, "Details")
    
    def create_installation_tab(self):
        """Create installation tab with configuration options."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Installation options
        options_group = QGroupBox("Installation Options")
        options_layout = QFormLayout(options_group)
        
        self.custom_name_edit = QLineEdit()
        self.custom_name_edit.setPlaceholderText("Leave empty for default name")
        options_layout.addRow("Custom Name:", self.custom_name_edit)
        
        self.auto_enable_check = QCheckBox("Enable after installation")
        self.auto_enable_check.setChecked(True)
        options_layout.addRow("", self.auto_enable_check)
        
        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["user", "project", "local"])
        options_layout.addRow("Scope:", self.scope_combo)
        
        layout.addWidget(options_group)
        
        # Installation button
        self.install_button = QPushButton("Install Server")
        self.install_button.setStyleSheet("""
            QPushButton {
                background-color: #007AFF;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
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
        """)
        layout.addWidget(self.install_button)
        
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Installation")
    
    def show_server(self, server_data: Dict):
        """Display server information."""
        # Header
        name = server_data.get('name', 'Unknown')
        server_type = server_data.get('type', 'unknown')
        
        self.server_name.setText(name)
        self.server_type.setText(f"Type: {server_type.upper()}")
        
        # Set server icon based on type
        self.set_server_icon(server_type)
        
        # Overview tab
        description = server_data.get('description', 'No description available')
        self.description_text.setText(description)
        
        install_id = server_data.get('install_id', 'N/A')
        self.install_id_label.setText(install_id)
        
        quality_score = server_data.get('quality_score', 0)
        if quality_score > 0:
            self.quality_score_label.setText(f"{quality_score}/100")
        else:
            self.quality_score_label.setText("Not rated")
        
        category = server_data.get('category', 'Uncategorized')
        self.category_label.setText(category)
        
        version = server_data.get('version', 'Unknown')
        self.version_label.setText(version)
        
        # Details tab
        details = self.format_server_details(server_data)
        self.details_text.setText(details)
        
        # Store server data for installation
        self.server_data = server_data
        self.install_button.setEnabled(bool(install_id and install_id != 'N/A'))
    
    def set_server_icon(self, server_type: str):
        """Set appropriate icon for server type."""
        icon_map = {
            'npm': ':/icons/npm.svg',
            'docker': ':/icons/docker.svg',
            'docker-desktop': ':/icons/docker.svg',
            'custom': ':/icons/server_online.svg'
        }
        
        icon_path = icon_map.get(server_type, ':/icons/server_online.svg')
        
        # Create a simple colored icon if file not found
        pixmap = QPixmap(48, 48)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw colored circle based on server type
        colors = {
            'npm': '#cc3534',
            'docker': '#2496ed',
            'docker-desktop': '#2496ed',
            'custom': '#666666'
        }
        
        color = colors.get(server_type, '#666666')
        painter.setBrush(QBrush(Qt.QColor(color)))
        painter.setPen(QPen(Qt.white, 2))
        painter.drawEllipse(4, 4, 40, 40)
        
        # Add text
        painter.setPen(QPen(Qt.white))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, server_type[:3].upper())
        
        painter.end()
        
        self.server_icon.setPixmap(pixmap)
    
    def format_server_details(self, server_data: Dict) -> str:
        """Format server details for display."""
        details = []
        
        # Add all available information
        for key, value in server_data.items():
            if key in ['name', 'type', 'description', 'install_id', 'quality_score', 'category', 'version']:
                continue  # Already shown in overview
            
            if isinstance(value, (list, dict)):
                details.append(f"{key.replace('_', ' ').title()}: {value}")
            else:
                details.append(f"{key.replace('_', ' ').title()}: {value}")
        
        if not details:
            details.append("No additional technical details available.")
        
        return '\n'.join(details)
    
    def clear_preview(self):
        """Clear the preview display."""
        self.server_name.setText("Select a server to view details")
        self.server_type.setText("")
        self.description_text.clear()
        self.install_id_label.clear()
        self.quality_score_label.clear()
        self.category_label.clear()
        self.version_label.clear()
        self.details_text.clear()
        self.install_button.setEnabled(False)
        
        # Clear icon
        self.server_icon.clear()
        self.server_data = None


class DiscoveryWindow(QMainWindow):
    """Main window for server discovery and installation."""
    
    server_installed = Signal(dict)
    
    def __init__(self, parent=None, cli_bridge: CLIBridge = None):
        super().__init__(parent)
        self.cli_bridge = cli_bridge or CLIBridge()
        
        self.setWindowTitle("MCP Server Discovery")
        self.resize(1200, 800)
        
        # Workers
        self.discovery_worker = None
        self.discovery_thread = None
        self.installation_worker = None
        self.installation_thread = None
        
        # Data
        self.current_results = []
        self.selected_servers = []
        
        self.setup_ui()
        self.setup_connections()
        
        # Perform initial discovery
        self.perform_discovery()
    
    def setup_ui(self):
        """Set up the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Search and filter controls
        self.create_search_controls(layout)
        
        # Main content splitter
        main_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(main_splitter)
        
        # Left side - search results
        self.create_results_panel(main_splitter)
        
        # Right side - server preview
        self.preview_widget = ServerPreviewWidget()
        main_splitter.addWidget(self.preview_widget)
        
        # Set splitter proportions
        main_splitter.setSizes([700, 500])
        
        # Status bar
        self.statusBar().showMessage("Ready")
    
    def create_search_controls(self, layout):
        """Create search and filter controls."""
        controls_frame = QFrame()
        controls_frame.setFrameStyle(QFrame.StyledPanel)
        controls_layout = QVBoxLayout(controls_frame)
        
        # Search row
        search_row = QHBoxLayout()
        
        search_row.addWidget(QLabel("Search:"))
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search for servers by name, description, or functionality...")
        search_row.addWidget(self.search_edit)
        
        self.search_button = QPushButton("Search")
        self.search_button.setIcon(QIcon(":/icons/search.svg"))
        search_row.addWidget(self.search_button)
        
        controls_layout.addLayout(search_row)
        
        # Filter row
        filter_row = QHBoxLayout()
        
        filter_row.addWidget(QLabel("Type:"))
        self.type_filter = QComboBox()
        self.type_filter.addItems(["all", "npm", "docker", "docker-desktop", "custom"])
        filter_row.addWidget(self.type_filter)
        
        filter_row.addWidget(QLabel("Limit:"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(10, 500)
        self.limit_spin.setValue(50)
        filter_row.addWidget(self.limit_spin)
        
        self.update_catalog_check = QCheckBox("Update catalog")
        filter_row.addWidget(self.update_catalog_check)
        
        filter_row.addStretch()
        
        # Bulk actions
        self.bulk_install_button = QPushButton("Install Selected")
        self.bulk_install_button.setEnabled(False)
        filter_row.addWidget(self.bulk_install_button)
        
        controls_layout.addLayout(filter_row)
        
        layout.addWidget(controls_frame)
    
    def create_results_panel(self, parent):
        """Create results panel with server list."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Results header
        header_layout = QHBoxLayout()
        
        self.results_label = QLabel("Search Results (0)")
        self.results_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(self.results_label)
        
        header_layout.addStretch()
        
        self.select_all_check = QCheckBox("Select All")
        header_layout.addWidget(self.select_all_check)
        
        layout.addLayout(header_layout)
        
        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(6)
        self.results_table.setHorizontalHeaderLabels([
            "Select", "Name", "Type", "Description", "Quality", "Install ID"
        ])
        
        # Configure table
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Select
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Name
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Type
        header.setSectionResizeMode(3, QHeaderView.Stretch)           # Description
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Quality
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Install ID
        
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(True)
        
        layout.addWidget(self.results_table)
        
        parent.addWidget(panel)
    
    def setup_connections(self):
        """Set up signal connections."""
        # Search controls
        self.search_button.clicked.connect(self.perform_discovery)
        self.search_edit.returnPressed.connect(self.perform_discovery)
        self.type_filter.currentTextChanged.connect(self.perform_discovery)
        
        # Results table
        self.results_table.itemSelectionChanged.connect(self.on_selection_changed)
        self.select_all_check.toggled.connect(self.toggle_select_all)
        
        # Bulk actions
        self.bulk_install_button.clicked.connect(self.bulk_install_selected)
        
        # Preview widget
        self.preview_widget.install_button.clicked.connect(self.install_current_server)
    
    def perform_discovery(self):
        """Perform server discovery with current search criteria."""
        if self.discovery_worker:
            self.discovery_worker.cancel()
            return
        
        # Get search parameters
        query = self.search_edit.text().strip() or None
        server_type = self.type_filter.currentText()
        if server_type == "all":
            server_type = None
        
        limit = self.limit_spin.value()
        update_catalog = self.update_catalog_check.isChecked()
        
        # Create and start discovery worker
        self.discovery_thread = QThread()
        self.discovery_worker = DiscoveryWorker(self.cli_bridge)
        self.discovery_worker.moveToThread(self.discovery_thread)
        
        # Connect signals
        self.discovery_worker.discovery_completed.connect(self.handle_discovery_results)
        self.discovery_worker.discovery_progress.connect(self.handle_discovery_progress)
        self.discovery_worker.error_occurred.connect(self.handle_discovery_error)
        self.discovery_thread.finished.connect(self.cleanup_discovery_worker)
        
        # Start discovery
        self.discovery_thread.started.connect(
            lambda: asyncio.run(self.discovery_worker.discover_servers(
                query, server_type, limit, update_catalog
            ))
        )
        
        self.discovery_thread.start()
        
        # Update UI
        self.search_button.setText("Cancel")
        self.statusBar().showMessage("Searching for servers...")
    
    def handle_discovery_results(self, results: List[Dict]):
        """Handle discovery results."""
        self.current_results = results
        self.update_results_table()
        
        self.results_label.setText(f"Search Results ({len(results)})")
        self.statusBar().showMessage(f"Found {len(results)} servers")
    
    def handle_discovery_progress(self, message: str):
        """Handle discovery progress updates."""
        self.statusBar().showMessage(message)
    
    def handle_discovery_error(self, error: str):
        """Handle discovery errors."""
        QMessageBox.warning(self, "Discovery Error", f"Failed to discover servers: {error}")
        self.statusBar().showMessage("Discovery failed")
    
    def cleanup_discovery_worker(self):
        """Clean up discovery worker and thread."""
        self.search_button.setText("Search")
        
        if self.discovery_thread:
            self.discovery_thread.quit()
            self.discovery_thread.wait()
            self.discovery_thread = None
        
        self.discovery_worker = None
    
    def update_results_table(self):
        """Update the results table with current data."""
        self.results_table.setRowCount(len(self.current_results))
        
        for row, server in enumerate(self.current_results):
            # Select checkbox
            select_check = QCheckBox()
            self.results_table.setCellWidget(row, 0, select_check)
            select_check.toggled.connect(self.on_item_selection_changed)
            
            # Name
            name_item = QTableWidgetItem(server.get('name', 'Unknown'))
            self.results_table.setItem(row, 1, name_item)
            
            # Type
            server_type = server.get('type', 'unknown')
            type_item = QTableWidgetItem(server_type.upper())
            self.results_table.setItem(row, 2, type_item)
            
            # Description
            description = server.get('description', 'No description')
            if len(description) > 100:
                description = description[:97] + "..."
            desc_item = QTableWidgetItem(description)
            desc_item.setToolTip(server.get('description', 'No description'))
            self.results_table.setItem(row, 3, desc_item)
            
            # Quality score
            quality = server.get('quality_score', 0)
            if quality > 0:
                quality_text = f"{quality}/100"
            else:
                quality_text = "N/A"
            quality_item = QTableWidgetItem(quality_text)
            self.results_table.setItem(row, 4, quality_item)
            
            # Install ID
            install_id = server.get('install_id', 'N/A')
            install_item = QTableWidgetItem(install_id)
            self.results_table.setItem(row, 5, install_item)
        
        # Clear selection
        self.results_table.clearSelection()
        self.preview_widget.clear_preview()
    
    def on_selection_changed(self):
        """Handle table selection changes."""
        selected_rows = set()
        for item in self.results_table.selectedItems():
            selected_rows.add(item.row())
        
        if len(selected_rows) == 1:
            row = list(selected_rows)[0]
            if row < len(self.current_results):
                server_data = self.current_results[row]
                self.preview_widget.show_server(server_data)
        else:
            self.preview_widget.clear_preview()
    
    def on_item_selection_changed(self):
        """Handle individual item selection changes."""
        selected_count = 0
        for row in range(self.results_table.rowCount()):
            checkbox = self.results_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                selected_count += 1
        
        self.bulk_install_button.setEnabled(selected_count > 0)
        self.bulk_install_button.setText(f"Install Selected ({selected_count})")
    
    def toggle_select_all(self, checked: bool):
        """Toggle selection of all items."""
        for row in range(self.results_table.rowCount()):
            checkbox = self.results_table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(checked)
    
    def get_selected_servers(self) -> List[Dict]:
        """Get list of selected servers."""
        selected = []
        for row in range(self.results_table.rowCount()):
            checkbox = self.results_table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                if row < len(self.current_results):
                    selected.append(self.current_results[row])
        return selected
    
    def install_current_server(self):
        """Install the currently previewed server."""
        if not hasattr(self.preview_widget, 'server_data') or not self.preview_widget.server_data:
            return
        
        server_data = self.preview_widget.server_data
        install_id = server_data.get('install_id')
        
        if not install_id or install_id == 'N/A':
            QMessageBox.warning(self, "Installation Error", 
                               "This server does not have a valid install ID.")
            return
        
        # Get installation options
        custom_name = self.preview_widget.custom_name_edit.text().strip()
        
        self.install_server(install_id, custom_name or None)
    
    def bulk_install_selected(self):
        """Install all selected servers."""
        selected = self.get_selected_servers()
        if not selected:
            return
        
        valid_servers = [s for s in selected if s.get('install_id') and s.get('install_id') != 'N/A']
        
        if not valid_servers:
            QMessageBox.warning(self, "Installation Error", 
                               "None of the selected servers have valid install IDs.")
            return
        
        reply = QMessageBox.question(
            self, "Bulk Installation",
            f"Install {len(valid_servers)} selected servers?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            for server in valid_servers:
                self.install_server(server.get('install_id'), server.get('name'))
    
    def install_server(self, install_id: str, custom_name: str = None):
        """Install a server by install ID."""
        if self.installation_worker:
            QMessageBox.information(self, "Installation in Progress", 
                                   "Another installation is already in progress.")
            return
        
        # Create and start installation worker
        self.installation_thread = QThread()
        self.installation_worker = InstallationWorker(self.cli_bridge)
        self.installation_worker.moveToThread(self.installation_thread)
        
        # Connect signals
        self.installation_worker.installation_completed.connect(self.handle_installation_completed)
        self.installation_worker.installation_progress.connect(self.handle_installation_progress)
        self.installation_worker.error_occurred.connect(self.handle_installation_error)
        self.installation_thread.finished.connect(self.cleanup_installation_worker)
        
        # Start installation
        self.installation_thread.started.connect(
            lambda: asyncio.run(self.installation_worker.install_package(install_id, custom_name))
        )
        
        self.installation_thread.start()
        
        # Update UI
        self.statusBar().showMessage(f"Installing {install_id}...")
    
    def handle_installation_completed(self, success: bool, message: str):
        """Handle installation completion."""
        if success:
            QMessageBox.information(self, "Installation Success", message)
            # Emit signal for parent to refresh server list
            self.server_installed.emit({"install_id": message})
        else:
            QMessageBox.warning(self, "Installation Failed", message)
        
        self.statusBar().showMessage("Ready")
    
    def handle_installation_progress(self, message: str):
        """Handle installation progress updates."""
        self.statusBar().showMessage(message)
    
    def handle_installation_error(self, error: str):
        """Handle installation errors."""
        QMessageBox.critical(self, "Installation Error", f"Installation failed: {error}")
        self.statusBar().showMessage("Ready")
    
    def cleanup_installation_worker(self):
        """Clean up installation worker and thread."""
        if self.installation_thread:
            self.installation_thread.quit()
            self.installation_thread.wait()
            self.installation_thread = None
        
        self.installation_worker = None
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Cancel any running operations
        if self.discovery_worker:
            self.discovery_worker.cancel()
        
        # Wait for threads to finish
        if self.discovery_thread:
            self.discovery_thread.quit()
            self.discovery_thread.wait()
        
        if self.installation_thread:
            self.installation_thread.quit()
            self.installation_thread.wait()
        
        event.accept()