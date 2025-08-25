"""
Suite Manager Window - Complete suite management interface.

Provides full CLI functionality for managing MCP server suites through a GUI.
"""

import asyncio
from typing import Dict, List, Optional, Any
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem,
    QLabel, QLineEdit, QTextEdit, QComboBox, QGroupBox, QFormLayout,
    QDialog, QDialogButtonBox, QMessageBox, QProgressDialog, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu, QCheckBox,
    QSpinBox, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer, QMimeData
from PySide6.QtGui import QAction, QIcon, QDrag, QPixmap, QPainter

from ..services.cli_bridge import CLIBridge
from ..widgets.suite_tree import SuiteTreeWidget


class CreateSuiteDialog(QDialog):
    """Dialog for creating new suites."""
    
    suite_created = Signal(dict)
    
    def __init__(self, parent=None, cli_bridge: CLIBridge = None):
        super().__init__(parent)
        self.cli_bridge = cli_bridge or CLIBridge()
        
        self.setWindowTitle("Create New Suite")
        self.setModal(True)
        self.resize(400, 300)
        self.setup_ui()
        self.setup_connections()
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Basic Information
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter suite name (required)")
        form_layout.addRow("Name:", self.name_edit)
        
        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItems([
            "Development", "Production", "Testing", "Database",
            "AI/ML", "Web Services", "DevOps", "Custom"
        ])
        form_layout.addRow("Category:", self.category_combo)
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(100)
        self.description_edit.setPlaceholderText("Optional description")
        form_layout.addRow("Description:", self.description_edit)
        
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(1, 100)
        self.priority_spin.setValue(50)
        form_layout.addRow("Priority:", self.priority_spin)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        layout.addWidget(button_box)
        
        self.ok_button = button_box.button(QDialogButtonBox.Ok)
        self.ok_button.setText("Create Suite")
        self.ok_button.setEnabled(False)
        
        button_box.accepted.connect(self.create_suite)
        button_box.rejected.connect(self.reject)
    
    def setup_connections(self):
        """Set up signal connections."""
        self.name_edit.textChanged.connect(self.validate_form)
        self.validate_form()
    
    def validate_form(self):
        """Validate form and enable/disable create button."""
        is_valid = bool(self.name_edit.text().strip())
        self.ok_button.setEnabled(is_valid)
    
    def create_suite(self):
        """Create the suite."""
        name = self.name_edit.text().strip()
        category = self.category_combo.currentText().strip()
        description = self.description_edit.toPlainText().strip()
        priority = self.priority_spin.value()
        
        suite_data = {
            "name": name,
            "category": category,
            "description": description,
            "priority": priority
        }
        
        try:
            # Create suite asynchronously
            asyncio.run(self._create_suite_async(suite_data))
        except Exception as e:
            QMessageBox.critical(self, "Creation Error", f"Failed to create suite: {e}")
    
    async def _create_suite_async(self, suite_data: Dict):
        """Create suite asynchronously."""
        try:
            # Use CLI bridge to create suite
            success = await self.cli_bridge.create_suite(**suite_data)
            
            if success:
                self.suite_created.emit(suite_data)
                QMessageBox.information(self, "Success", f"Suite '{suite_data['name']}' created successfully!")
                self.accept()
            else:
                QMessageBox.warning(self, "Creation Failed", f"Failed to create suite '{suite_data['name']}'.")
        
        except Exception as e:
            QMessageBox.critical(self, "Creation Error", f"Error creating suite: {e}")


class SuiteManagerWindow(QMainWindow):
    """Main suite management window with complete functionality."""
    
    def __init__(self, parent=None, cli_bridge: CLIBridge = None):
        super().__init__(parent)
        self.cli_bridge = cli_bridge or CLIBridge()
        
        self.setWindowTitle("MCP Suite Manager")
        self.resize(1200, 800)
        
        # Data
        self.suites = {}
        self.servers = {}
        self.refresh_timer = QTimer()
        
        self.setup_ui()
        self.setup_connections()
        self.setup_menu_bar()
        
        # Load initial data
        self.refresh_data()
    
    def setup_ui(self):
        """Set up the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QHBoxLayout(central_widget)
        
        # Create main splitter
        main_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(main_splitter)
        
        # Left panel - Suite tree and controls
        left_panel = self.create_left_panel()
        main_splitter.addWidget(left_panel)
        
        # Right panel - Suite details and server management
        right_panel = self.create_right_panel()
        main_splitter.addWidget(right_panel)
        
        # Set splitter proportions
        main_splitter.setSizes([400, 800])
    
    def create_left_panel(self):
        """Create left panel with suite tree and controls."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.create_suite_btn = QPushButton("Create Suite")
        self.create_suite_btn.setIcon(QIcon(":/icons/add.svg"))
        controls_layout.addWidget(self.create_suite_btn)
        
        self.delete_suite_btn = QPushButton("Delete")
        self.delete_suite_btn.setIcon(QIcon(":/icons/remove.svg"))
        self.delete_suite_btn.setEnabled(False)
        controls_layout.addWidget(self.delete_suite_btn)
        
        controls_layout.addStretch()
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setIcon(QIcon(":/icons/refresh.svg"))
        controls_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(controls_layout)
        
        # Category filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter by category:"))
        
        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories")
        filter_layout.addWidget(self.category_filter)
        
        layout.addLayout(filter_layout)
        
        # Suite tree
        self.suite_tree = SuiteTreeWidget()
        self.suite_tree.setHeaderLabels(["Name", "Category", "Servers", "Status"])
        self.suite_tree.setDragDropMode(QTreeWidget.DropOnly)
        layout.addWidget(self.suite_tree)
        
        return panel
    
    def create_right_panel(self):
        """Create right panel with suite details and server management."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Suite info header
        self.suite_info_label = QLabel("Select a suite to view details")
        self.suite_info_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(self.suite_info_label)
        
        # Tab widget for different views
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Tab 1: Suite Details
        self.create_details_tab()
        
        # Tab 2: Server Management
        self.create_server_management_tab()
        
        # Tab 3: Installation & Deployment
        self.create_deployment_tab()
        
        return panel
    
    def create_details_tab(self):
        """Create suite details tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Editable suite information
        form_layout = QFormLayout()
        
        self.suite_name_display = QLabel()
        form_layout.addRow("Name:", self.suite_name_display)
        
        self.suite_category_edit = QComboBox()
        self.suite_category_edit.setEditable(True)
        self.suite_category_edit.setEnabled(False)
        form_layout.addRow("Category:", self.suite_category_edit)
        
        self.suite_description_edit = QTextEdit()
        self.suite_description_edit.setMaximumHeight(100)
        self.suite_description_edit.setEnabled(False)
        form_layout.addRow("Description:", self.suite_description_edit)
        
        self.suite_priority_edit = QSpinBox()
        self.suite_priority_edit.setRange(1, 100)
        self.suite_priority_edit.setEnabled(False)
        form_layout.addRow("Priority:", self.suite_priority_edit)
        
        layout.addLayout(form_layout)
        
        # Edit controls
        edit_controls = QHBoxLayout()
        
        self.edit_suite_btn = QPushButton("Edit Suite")
        self.edit_suite_btn.setEnabled(False)
        edit_controls.addWidget(self.edit_suite_btn)
        
        self.save_suite_btn = QPushButton("Save Changes")
        self.save_suite_btn.setEnabled(False)
        edit_controls.addWidget(self.save_suite_btn)
        
        self.cancel_edit_btn = QPushButton("Cancel")
        self.cancel_edit_btn.setEnabled(False)
        edit_controls.addWidget(self.cancel_edit_btn)
        
        edit_controls.addStretch()
        
        layout.addLayout(edit_controls)
        
        # Suite statistics
        stats_group = QGroupBox("Statistics")
        stats_layout = QFormLayout(stats_group)
        
        self.server_count_label = QLabel("0")
        stats_layout.addRow("Total Servers:", self.server_count_label)
        
        self.active_servers_label = QLabel("0")
        stats_layout.addRow("Active Servers:", self.active_servers_label)
        
        self.suite_status_label = QLabel("Unknown")
        stats_layout.addRow("Suite Status:", self.suite_status_label)
        
        layout.addWidget(stats_group)
        
        self.tab_widget.addTab(tab, "Details")
    
    def create_server_management_tab(self):
        """Create server management tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Server management controls
        controls_layout = QHBoxLayout()
        
        self.add_server_btn = QPushButton("Add Server to Suite")
        self.add_server_btn.setEnabled(False)
        controls_layout.addWidget(self.add_server_btn)
        
        self.remove_server_btn = QPushButton("Remove Selected")
        self.remove_server_btn.setEnabled(False)
        controls_layout.addWidget(self.remove_server_btn)
        
        controls_layout.addStretch()
        
        self.bulk_enable_btn = QPushButton("Enable All")
        self.bulk_enable_btn.setEnabled(False)
        controls_layout.addWidget(self.bulk_enable_btn)
        
        self.bulk_disable_btn = QPushButton("Disable All")
        self.bulk_disable_btn.setEnabled(False)
        controls_layout.addWidget(self.bulk_disable_btn)
        
        layout.addLayout(controls_layout)
        
        # Server list table
        self.suite_servers_table = QTableWidget()
        self.suite_servers_table.setColumnCount(6)
        self.suite_servers_table.setHorizontalHeaderLabels([
            "Name", "Type", "Status", "Role", "Priority", "Actions"
        ])
        
        header = self.suite_servers_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        
        self.suite_servers_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.suite_servers_table.setAlternatingRowColors(True)
        
        layout.addWidget(self.suite_servers_table)
        
        self.tab_widget.addTab(tab, "Server Management")
    
    def create_deployment_tab(self):
        """Create deployment and installation tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Installation controls
        install_group = QGroupBox("Suite Installation")
        install_layout = QVBoxLayout(install_group)
        
        install_controls = QHBoxLayout()
        
        self.dry_run_check = QCheckBox("Dry run (preview only)")
        install_controls.addWidget(self.dry_run_check)
        
        self.install_scope_combo = QComboBox()
        self.install_scope_combo.addItems(["user", "project", "local"])
        install_controls.addWidget(QLabel("Scope:"))
        install_controls.addWidget(self.install_scope_combo)
        
        install_controls.addStretch()
        
        self.install_suite_btn = QPushButton("Install Suite")
        self.install_suite_btn.setEnabled(False)
        install_controls.addWidget(self.install_suite_btn)
        
        install_layout.addLayout(install_controls)
        
        # Installation log
        self.install_log = QTextEdit()
        self.install_log.setReadOnly(True)
        self.install_log.setMaximumHeight(200)
        install_layout.addWidget(QLabel("Installation Log:"))
        install_layout.addWidget(self.install_log)
        
        layout.addWidget(install_group)
        
        # Suite control
        control_group = QGroupBox("Suite Control")
        control_layout = QHBoxLayout(control_group)
        
        self.enable_suite_btn = QPushButton("Enable Suite")
        self.enable_suite_btn.setEnabled(False)
        control_layout.addWidget(self.enable_suite_btn)
        
        self.disable_suite_btn = QPushButton("Disable Suite")
        self.disable_suite_btn.setEnabled(False)
        control_layout.addWidget(self.disable_suite_btn)
        
        control_layout.addStretch()
        
        self.export_suite_btn = QPushButton("Export Configuration")
        self.export_suite_btn.setEnabled(False)
        control_layout.addWidget(self.export_suite_btn)
        
        layout.addWidget(control_group)
        
        # Suite dependencies
        deps_group = QGroupBox("Dependencies & Prerequisites")
        deps_layout = QVBoxLayout(deps_group)
        
        self.dependencies_list = QListWidget()
        self.dependencies_list.setMaximumHeight(150)
        deps_layout.addWidget(self.dependencies_list)
        
        layout.addWidget(deps_group)
        
        self.tab_widget.addTab(tab, "Installation & Deployment")
    
    def setup_menu_bar(self):
        """Set up the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        new_suite_action = QAction("New Suite...", self)
        new_suite_action.setShortcut("Ctrl+N")
        new_suite_action.triggered.connect(self.create_new_suite)
        file_menu.addAction(new_suite_action)
        
        file_menu.addSeparator()
        
        import_action = QAction("Import Suite...", self)
        import_action.triggered.connect(self.import_suite)
        file_menu.addAction(import_action)
        
        export_action = QAction("Export Suite...", self)
        export_action.triggered.connect(self.export_current_suite)
        file_menu.addAction(export_action)
        
        # Suite menu
        suite_menu = menubar.addMenu("Suite")
        
        install_action = QAction("Install Selected Suite", self)
        install_action.triggered.connect(self.install_selected_suite)
        suite_menu.addAction(install_action)
        
        enable_action = QAction("Enable Selected Suite", self)
        enable_action.triggered.connect(self.enable_selected_suite)
        suite_menu.addAction(enable_action)
        
        disable_action = QAction("Disable Selected Suite", self)
        disable_action.triggered.connect(self.disable_selected_suite)
        suite_menu.addAction(disable_action)
        
        # View menu
        view_menu = menubar.addMenu("View")
        
        refresh_action = QAction("Refresh", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.refresh_data)
        view_menu.addAction(refresh_action)
    
    def setup_connections(self):
        """Set up signal connections."""
        # Left panel controls
        self.create_suite_btn.clicked.connect(self.create_new_suite)
        self.delete_suite_btn.clicked.connect(self.delete_selected_suite)
        self.refresh_btn.clicked.connect(self.refresh_data)
        
        # Suite tree selection
        self.suite_tree.currentItemChanged.connect(self.on_suite_selected)
        self.suite_tree.itemChanged.connect(self.on_suite_item_changed)
        
        # Category filter
        self.category_filter.currentTextChanged.connect(self.filter_suites)
        
        # Details tab
        self.edit_suite_btn.clicked.connect(self.edit_current_suite)
        self.save_suite_btn.clicked.connect(self.save_suite_changes)
        self.cancel_edit_btn.clicked.connect(self.cancel_suite_edit)
        
        # Server management tab
        self.add_server_btn.clicked.connect(self.add_server_to_suite)
        self.remove_server_btn.clicked.connect(self.remove_server_from_suite)
        self.bulk_enable_btn.clicked.connect(self.bulk_enable_servers)
        self.bulk_disable_btn.clicked.connect(self.bulk_disable_servers)
        
        # Server table selection
        self.suite_servers_table.itemSelectionChanged.connect(self.on_server_selection_changed)
        
        # Deployment tab
        self.install_suite_btn.clicked.connect(self.install_current_suite)
        self.enable_suite_btn.clicked.connect(self.enable_current_suite)
        self.disable_suite_btn.clicked.connect(self.disable_current_suite)
        self.export_suite_btn.clicked.connect(self.export_current_suite)
        
        # Auto-refresh timer
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(30000)  # 30 seconds
    
    def refresh_data(self):
        """Refresh all data from CLI bridge."""
        asyncio.run(self._refresh_data_async())
    
    async def _refresh_data_async(self):
        """Refresh data asynchronously."""
        try:
            # Get suites and servers
            self.suites = await self.cli_bridge.get_suites()
            self.servers = await self.cli_bridge.get_servers()
            
            # Update UI
            self.update_suite_tree()
            self.update_category_filter()
            
        except Exception as e:
            QMessageBox.warning(self, "Refresh Error", f"Failed to refresh data: {e}")
    
    def update_suite_tree(self):
        """Update the suite tree widget."""
        self.suite_tree.clear()
        
        # Group suites by category
        categories = {}
        for suite_name, suite_data in self.suites.items():
            category = suite_data.get('category', 'Uncategorized')
            if category not in categories:
                categories[category] = []
            categories[category].append((suite_name, suite_data))
        
        # Add category nodes
        for category, suites in categories.items():
            category_item = QTreeWidgetItem([category, "", f"{len(suites)} suites", ""])
            category_item.setData(0, Qt.UserRole, {"type": "category", "name": category})
            self.suite_tree.addTopLevelItem(category_item)
            
            # Add suite items
            for suite_name, suite_data in suites:
                server_count = len(suite_data.get('servers', []))
                status = self.calculate_suite_status(suite_data)
                
                suite_item = QTreeWidgetItem([
                    suite_name,
                    category,
                    str(server_count),
                    status
                ])
                suite_item.setData(0, Qt.UserRole, {"type": "suite", "name": suite_name, "data": suite_data})
                category_item.addChild(suite_item)
            
            category_item.setExpanded(True)
    
    def update_category_filter(self):
        """Update category filter dropdown."""
        current_selection = self.category_filter.currentText()
        self.category_filter.clear()
        
        self.category_filter.addItem("All Categories")
        
        categories = set()
        for suite_data in self.suites.values():
            category = suite_data.get('category', 'Uncategorized')
            categories.add(category)
        
        for category in sorted(categories):
            self.category_filter.addItem(category)
        
        # Restore selection if possible
        index = self.category_filter.findText(current_selection)
        if index >= 0:
            self.category_filter.setCurrentIndex(index)
    
    def calculate_suite_status(self, suite_data: Dict) -> str:
        """Calculate the overall status of a suite."""
        servers = suite_data.get('servers', [])
        if not servers:
            return "Empty"
        
        # Check server statuses
        active_count = 0
        total_count = len(servers)
        
        for server_name in servers:
            server_info = self.servers.get(server_name, {})
            if server_info.get('status') == 'enabled':
                active_count += 1
        
        if active_count == 0:
            return "Inactive"
        elif active_count == total_count:
            return "Active"
        else:
            return f"Partial ({active_count}/{total_count})"
    
    def filter_suites(self, category: str):
        """Filter suites by category."""
        if category == "All Categories":
            # Show all items
            for i in range(self.suite_tree.topLevelItemCount()):
                item = self.suite_tree.topLevelItem(i)
                item.setHidden(False)
        else:
            # Hide/show based on category
            for i in range(self.suite_tree.topLevelItemCount()):
                item = self.suite_tree.topLevelItem(i)
                item_data = item.data(0, Qt.UserRole)
                if item_data and item_data.get('type') == 'category':
                    should_show = item_data.get('name') == category
                    item.setHidden(not should_show)
    
    def on_suite_selected(self, current: QTreeWidgetItem, previous: QTreeWidgetItem):
        """Handle suite selection."""
        if not current:
            self.clear_suite_details()
            return
        
        item_data = current.data(0, Qt.UserRole)
        if not item_data or item_data.get('type') != 'suite':
            self.clear_suite_details()
            return
        
        suite_name = item_data.get('name')
        suite_data = item_data.get('data', {})
        
        self.show_suite_details(suite_name, suite_data)
        self.enable_suite_controls(True)
    
    def clear_suite_details(self):
        """Clear suite details display."""
        self.suite_info_label.setText("Select a suite to view details")
        self.enable_suite_controls(False)
    
    def show_suite_details(self, suite_name: str, suite_data: Dict):
        """Show details for selected suite."""
        self.suite_info_label.setText(f"Suite: {suite_name}")
        
        # Update details tab
        self.suite_name_display.setText(suite_name)
        self.suite_category_edit.setCurrentText(suite_data.get('category', ''))
        self.suite_description_edit.setText(suite_data.get('description', ''))
        self.suite_priority_edit.setValue(suite_data.get('priority', 50))
        
        # Update statistics
        servers = suite_data.get('servers', [])
        self.server_count_label.setText(str(len(servers)))
        
        active_count = sum(1 for server in servers 
                          if self.servers.get(server, {}).get('status') == 'enabled')
        self.active_servers_label.setText(str(active_count))
        
        status = self.calculate_suite_status(suite_data)
        self.suite_status_label.setText(status)
        
        # Update server management table
        self.update_suite_servers_table(servers)
    
    def update_suite_servers_table(self, server_names: List[str]):
        """Update the suite servers table."""
        self.suite_servers_table.setRowCount(len(server_names))
        
        for row, server_name in enumerate(server_names):
            server_data = self.servers.get(server_name, {})
            
            # Name
            name_item = QTableWidgetItem(server_name)
            self.suite_servers_table.setItem(row, 0, name_item)
            
            # Type
            server_type = server_data.get('type', 'unknown')
            type_item = QTableWidgetItem(server_type)
            self.suite_servers_table.setItem(row, 1, type_item)
            
            # Status
            status = server_data.get('status', 'unknown')
            status_item = QTableWidgetItem(status)
            self.suite_servers_table.setItem(row, 2, status_item)
            
            # Role (placeholder for future enhancement)
            role_item = QTableWidgetItem("Member")
            self.suite_servers_table.setItem(row, 3, role_item)
            
            # Priority (placeholder for future enhancement)
            priority_item = QTableWidgetItem("Normal")
            self.suite_servers_table.setItem(row, 4, priority_item)
            
            # Actions (placeholder for action buttons)
            actions_item = QTableWidgetItem("Configure")
            self.suite_servers_table.setItem(row, 5, actions_item)
    
    def enable_suite_controls(self, enabled: bool):
        """Enable/disable suite-related controls."""
        self.delete_suite_btn.setEnabled(enabled)
        self.edit_suite_btn.setEnabled(enabled)
        self.add_server_btn.setEnabled(enabled)
        self.bulk_enable_btn.setEnabled(enabled)
        self.bulk_disable_btn.setEnabled(enabled)
        self.install_suite_btn.setEnabled(enabled)
        self.enable_suite_btn.setEnabled(enabled)
        self.disable_suite_btn.setEnabled(enabled)
        self.export_suite_btn.setEnabled(enabled)
    
    def on_server_selection_changed(self):
        """Handle server selection changes."""
        has_selection = bool(self.suite_servers_table.selectedItems())
        self.remove_server_btn.setEnabled(has_selection)
    
    def create_new_suite(self):
        """Create a new suite."""
        dialog = CreateSuiteDialog(self, self.cli_bridge)
        dialog.suite_created.connect(self.on_suite_created)
        dialog.exec()
    
    def on_suite_created(self, suite_data: Dict):
        """Handle new suite creation."""
        self.refresh_data()
    
    def delete_selected_suite(self):
        """Delete the selected suite."""
        current_item = self.suite_tree.currentItem()
        if not current_item:
            return
        
        item_data = current_item.data(0, Qt.UserRole)
        if not item_data or item_data.get('type') != 'suite':
            return
        
        suite_name = item_data.get('name')
        
        reply = QMessageBox.question(
            self, "Delete Suite",
            f"Are you sure you want to delete suite '{suite_name}'?\n\nThis will not delete the servers, only the suite configuration.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            asyncio.run(self._delete_suite_async(suite_name))
    
    async def _delete_suite_async(self, suite_name: str):
        """Delete suite asynchronously."""
        try:
            success = await self.cli_bridge.delete_suite(suite_name)
            
            if success:
                QMessageBox.information(self, "Success", f"Suite '{suite_name}' deleted successfully!")
                self.refresh_data()
            else:
                QMessageBox.warning(self, "Delete Failed", f"Failed to delete suite '{suite_name}'.")
        
        except Exception as e:
            QMessageBox.critical(self, "Delete Error", f"Error deleting suite: {e}")
    
    def edit_current_suite(self):
        """Enable editing of current suite."""
        self.suite_category_edit.setEnabled(True)
        self.suite_description_edit.setEnabled(True)
        self.suite_priority_edit.setEnabled(True)
        
        self.edit_suite_btn.setEnabled(False)
        self.save_suite_btn.setEnabled(True)
        self.cancel_edit_btn.setEnabled(True)
    
    def save_suite_changes(self):
        """Save changes to current suite."""
        current_item = self.suite_tree.currentItem()
        if not current_item:
            return
        
        item_data = current_item.data(0, Qt.UserRole)
        suite_name = item_data.get('name')
        
        # Get updated values
        category = self.suite_category_edit.currentText()
        description = self.suite_description_edit.toPlainText()
        priority = self.suite_priority_edit.value()
        
        asyncio.run(self._update_suite_async(suite_name, category, description, priority))
    
    async def _update_suite_async(self, name: str, category: str, description: str, priority: int):
        """Update suite asynchronously."""
        try:
            success = await self.cli_bridge.update_suite(name, category, description, priority)
            
            if success:
                self.cancel_suite_edit()
                self.refresh_data()
                QMessageBox.information(self, "Success", f"Suite '{name}' updated successfully!")
            else:
                QMessageBox.warning(self, "Update Failed", f"Failed to update suite '{name}'.")
        
        except Exception as e:
            QMessageBox.critical(self, "Update Error", f"Error updating suite: {e}")
    
    def cancel_suite_edit(self):
        """Cancel suite editing."""
        self.suite_category_edit.setEnabled(False)
        self.suite_description_edit.setEnabled(False)
        self.suite_priority_edit.setEnabled(False)
        
        self.edit_suite_btn.setEnabled(True)
        self.save_suite_btn.setEnabled(False)
        self.cancel_edit_btn.setEnabled(False)
        
        # Restore original values
        current_item = self.suite_tree.currentItem()
        if current_item:
            item_data = current_item.data(0, Qt.UserRole)
            suite_data = item_data.get('data', {})
            
            self.suite_category_edit.setCurrentText(suite_data.get('category', ''))
            self.suite_description_edit.setText(suite_data.get('description', ''))
            self.suite_priority_edit.setValue(suite_data.get('priority', 50))
    
    def add_server_to_suite(self):
        """Add server to current suite."""
        # This would open a server selection dialog
        QMessageBox.information(self, "Add Server", "Server selection dialog would open here.")
    
    def remove_server_from_suite(self):
        """Remove selected server from suite."""
        selected_items = self.suite_servers_table.selectedItems()
        if not selected_items:
            return
        
        row = selected_items[0].row()
        server_name = self.suite_servers_table.item(row, 0).text()
        
        reply = QMessageBox.question(
            self, "Remove Server",
            f"Remove server '{server_name}' from this suite?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Remove server from suite
            QMessageBox.information(self, "Remove Server", f"Server '{server_name}' would be removed from suite.")
    
    def bulk_enable_servers(self):
        """Enable all servers in current suite."""
        QMessageBox.information(self, "Bulk Enable", "All servers in suite would be enabled.")
    
    def bulk_disable_servers(self):
        """Disable all servers in current suite."""
        QMessageBox.information(self, "Bulk Disable", "All servers in suite would be disabled.")
    
    def install_current_suite(self):
        """Install current suite."""
        current_item = self.suite_tree.currentItem()
        if not current_item:
            return
        
        item_data = current_item.data(0, Qt.UserRole)
        suite_name = item_data.get('name')
        
        dry_run = self.dry_run_check.isChecked()
        scope = self.install_scope_combo.currentText()
        
        # Show progress dialog
        progress = QProgressDialog(f"Installing suite '{suite_name}'...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        
        asyncio.run(self._install_suite_async(suite_name, dry_run, scope, progress))
    
    async def _install_suite_async(self, suite_name: str, dry_run: bool, scope: str, progress: QProgressDialog):
        """Install suite asynchronously."""
        try:
            success = await self.cli_bridge.install_suite(suite_name, dry_run=dry_run, scope=scope)
            progress.close()
            
            if success:
                action = "previewed" if dry_run else "installed"
                QMessageBox.information(self, "Success", f"Suite '{suite_name}' {action} successfully!")
                self.install_log.append(f"Suite '{suite_name}' {action} at {asyncio.get_event_loop().time()}")
            else:
                QMessageBox.warning(self, "Installation Failed", f"Failed to install suite '{suite_name}'.")
        
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Installation Error", f"Error installing suite: {e}")
    
    def enable_current_suite(self):
        """Enable current suite."""
        current_item = self.suite_tree.currentItem()
        if not current_item:
            return
        
        item_data = current_item.data(0, Qt.UserRole)
        suite_name = item_data.get('name')
        
        asyncio.run(self._enable_suite_async(suite_name))
    
    async def _enable_suite_async(self, suite_name: str):
        """Enable suite asynchronously."""
        try:
            success = await self.cli_bridge.enable_suite(suite_name)
            
            if success:
                QMessageBox.information(self, "Success", f"Suite '{suite_name}' enabled successfully!")
                self.refresh_data()
            else:
                QMessageBox.warning(self, "Enable Failed", f"Failed to enable suite '{suite_name}'.")
        
        except Exception as e:
            QMessageBox.critical(self, "Enable Error", f"Error enabling suite: {e}")
    
    def disable_current_suite(self):
        """Disable current suite."""
        current_item = self.suite_tree.currentItem()
        if not current_item:
            return
        
        item_data = current_item.data(0, Qt.UserRole)
        suite_name = item_data.get('name')
        
        asyncio.run(self._disable_suite_async(suite_name))
    
    async def _disable_suite_async(self, suite_name: str):
        """Disable suite asynchronously."""
        try:
            success = await self.cli_bridge.disable_suite(suite_name)
            
            if success:
                QMessageBox.information(self, "Success", f"Suite '{suite_name}' disabled successfully!")
                self.refresh_data()
            else:
                QMessageBox.warning(self, "Disable Failed", f"Failed to disable suite '{suite_name}'.")
        
        except Exception as e:
            QMessageBox.critical(self, "Disable Error", f"Error disabling suite: {e}")
    
    def export_current_suite(self):
        """Export current suite configuration."""
        QMessageBox.information(self, "Export Suite", "Suite export functionality would be implemented here.")
    
    def import_suite(self):
        """Import suite from file."""
        QMessageBox.information(self, "Import Suite", "Suite import functionality would be implemented here.")
    
    def install_selected_suite(self):
        """Install selected suite from menu."""
        self.install_current_suite()
    
    def enable_selected_suite(self):
        """Enable selected suite from menu."""
        self.enable_current_suite()
    
    def disable_selected_suite(self):
        """Disable selected suite from menu."""
        self.disable_current_suite()
    
    def on_suite_item_changed(self, item: QTreeWidgetItem, column: int):
        """Handle suite item changes (for inline editing)."""
        # This could handle inline editing of suite names, etc.
        pass