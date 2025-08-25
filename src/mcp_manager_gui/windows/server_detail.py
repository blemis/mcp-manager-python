"""
Server Detail Windows - Add Server and Edit Server dialogs.

Comprehensive dialogs for creating and configuring MCP servers with full CLI functionality.
"""

import asyncio
from typing import Dict, List, Optional, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QComboBox, QPushButton, QTextEdit, QSpinBox, QCheckBox, QGroupBox,
    QTabWidget, QWidget, QScrollArea, QMessageBox, QProgressDialog,
    QListWidget, QListWidgetItem, QSplitter, QFrame
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread, QObject
from PySide6.QtGui import QFont, QIcon

from ..services.cli_bridge import CLIBridge


class ServerDiscoveryWorker(QObject):
    """Background worker for server discovery."""
    
    discovery_completed = Signal(list)
    error_occurred = Signal(str)
    
    def __init__(self, cli_bridge: CLIBridge):
        super().__init__()
        self.cli_bridge = cli_bridge
    
    async def discover_servers(self, server_type: str = None):
        """Discover available servers."""
        try:
            results = await self.cli_bridge.discover_servers(server_type=server_type)
            self.discovery_completed.emit(results)
        except Exception as e:
            self.error_occurred.emit(str(e))


class AddServerDialog(QDialog):
    """Comprehensive Add Server dialog with full CLI functionality."""
    
    server_added = Signal(dict)
    
    def __init__(self, parent=None, cli_bridge: CLIBridge = None):
        super().__init__(parent)
        self.cli_bridge = cli_bridge or CLIBridge()
        self.discovery_worker = None
        self.discovery_thread = None
        
        self.setWindowTitle("Add MCP Server")
        self.setModal(True)
        self.resize(800, 600)
        self.setup_ui()
        self.setup_connections()
    
    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Create tab widget for different input methods
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Tab 1: Manual Configuration
        self.setup_manual_tab()
        
        # Tab 2: Discover & Install
        self.setup_discovery_tab()
        
        # Tab 3: Import from File
        self.setup_import_tab()
        
        # Buttons
        self.setup_buttons(layout)
    
    def setup_manual_tab(self):
        """Set up manual server configuration tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Server Type Selection
        type_group = QGroupBox("Server Type")
        type_layout = QVBoxLayout(type_group)
        
        self.server_type = QComboBox()
        self.server_type.addItems([
            "npm", "docker", "docker-desktop", "custom"
        ])
        self.server_type.setCurrentText("npm")
        type_layout.addWidget(self.server_type)
        layout.addWidget(type_group)
        
        # Create scrollable area for form
        scroll = QScrollArea()
        scroll_widget = QWidget()
        self.form_layout = QFormLayout(scroll_widget)
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
        
        # Basic Information
        basic_group = QGroupBox("Basic Information")
        basic_layout = QFormLayout(basic_group)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Enter server name (required)")
        basic_layout.addRow("Name:", self.name_edit)
        
        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Optional description")
        basic_layout.addRow("Description:", self.description_edit)
        
        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["user", "project", "local"])
        self.scope_combo.setCurrentText("user")
        basic_layout.addRow("Scope:", self.scope_combo)
        
        self.form_layout.addRow(basic_group)
        
        # Type-specific configuration containers
        self.npm_config = self.create_npm_config()
        self.docker_config = self.create_docker_config()
        self.docker_desktop_config = self.create_docker_desktop_config()
        self.custom_config = self.create_custom_config()
        
        # Add all configs to layout (will show/hide based on type)
        self.form_layout.addRow(self.npm_config)
        self.form_layout.addRow(self.docker_config)
        self.form_layout.addRow(self.docker_desktop_config)
        self.form_layout.addRow(self.custom_config)
        
        # Advanced Options
        self.setup_advanced_options()
        
        self.tab_widget.addTab(tab, "Manual Configuration")
        
        # Connect type change to update form
        self.server_type.currentTextChanged.connect(self.update_form_for_type)
        self.update_form_for_type("npm")
    
    def create_npm_config(self):
        """Create NPM server configuration section."""
        group = QGroupBox("NPM Package Configuration")
        layout = QFormLayout(group)
        
        self.npm_package = QLineEdit()
        self.npm_package.setPlaceholderText("e.g., @playwright/mcp")
        layout.addRow("Package Name:", self.npm_package)
        
        self.npm_version = QLineEdit()
        self.npm_version.setPlaceholderText("latest")
        layout.addRow("Version:", self.npm_version)
        
        self.npm_args = QTextEdit()
        self.npm_args.setMaximumHeight(80)
        self.npm_args.setPlaceholderText("Additional arguments (one per line)")
        layout.addRow("Arguments:", self.npm_args)
        
        return group
    
    def create_docker_config(self):
        """Create Docker server configuration section."""
        group = QGroupBox("Docker Container Configuration")
        layout = QFormLayout(group)
        
        self.docker_image = QLineEdit()
        self.docker_image.setPlaceholderText("e.g., mcp/playwright:latest")
        layout.addRow("Image:", self.docker_image)
        
        self.docker_pull_always = QCheckBox("Always pull latest image")
        self.docker_pull_always.setChecked(True)
        layout.addRow("Pull Policy:", self.docker_pull_always)
        
        self.docker_ports = QLineEdit()
        self.docker_ports.setPlaceholderText("e.g., 8080:80,3000:3000")
        layout.addRow("Port Mapping:", self.docker_ports)
        
        self.docker_volumes = QTextEdit()
        self.docker_volumes.setMaximumHeight(80)
        self.docker_volumes.setPlaceholderText("/host/path:/container/path (one per line)")
        layout.addRow("Volume Mounts:", self.docker_volumes)
        
        self.docker_interactive = QCheckBox("Interactive mode (-i)")
        self.docker_interactive.setChecked(True)
        layout.addRow("", self.docker_interactive)
        
        self.docker_remove = QCheckBox("Remove after exit (--rm)")
        self.docker_remove.setChecked(True)
        layout.addRow("", self.docker_remove)
        
        return group
    
    def create_docker_desktop_config(self):
        """Create Docker Desktop server configuration section."""
        group = QGroupBox("Docker Desktop Server")
        layout = QFormLayout(group)
        
        self.dd_server_list = QComboBox()
        self.dd_server_list.addItems([
            "filesystem", "sqlite", "http", "search", "k8s", "terraform", "aws"
        ])
        layout.addRow("Available Server:", self.dd_server_list)
        
        self.dd_refresh_btn = QPushButton("Refresh Available Servers")
        layout.addRow("", self.dd_refresh_btn)
        
        return group
    
    def create_custom_config(self):
        """Create custom server configuration section."""
        group = QGroupBox("Custom Server Configuration")
        layout = QFormLayout(group)
        
        self.custom_command = QLineEdit()
        self.custom_command.setPlaceholderText("e.g., python, node, ./my-server")
        layout.addRow("Command:", self.custom_command)
        
        self.custom_args = QTextEdit()
        self.custom_args.setMaximumHeight(80)
        self.custom_args.setPlaceholderText("Command arguments (one per line)")
        layout.addRow("Arguments:", self.custom_args)
        
        self.custom_working_dir = QLineEdit()
        self.custom_working_dir.setPlaceholderText("Working directory (optional)")
        layout.addRow("Working Directory:", self.custom_working_dir)
        
        return group
    
    def setup_advanced_options(self):
        """Set up advanced configuration options."""
        advanced_group = QGroupBox("Advanced Options")
        layout = QFormLayout(advanced_group)
        
        # Environment Variables
        self.env_vars = QTextEdit()
        self.env_vars.setMaximumHeight(100)
        self.env_vars.setPlaceholderText("KEY=value (one per line)")
        layout.addRow("Environment Variables:", self.env_vars)
        
        # Auto-enable server
        self.auto_enable = QCheckBox("Enable server after creation")
        self.auto_enable.setChecked(True)
        layout.addRow("", self.auto_enable)
        
        # Preview area
        preview_label = QLabel("Command Preview:")
        preview_label.setFont(QFont("SF Mono", 10))
        layout.addRow(preview_label)
        
        self.command_preview = QTextEdit()
        self.command_preview.setMaximumHeight(60)
        self.command_preview.setReadOnly(True)
        self.command_preview.setStyleSheet("background-color: #f5f5f5; color: #333;")
        layout.addRow(self.command_preview)
        
        self.form_layout.addRow(advanced_group)
        
        # Connect inputs to update preview
        self.setup_preview_connections()
    
    def setup_discovery_tab(self):
        """Set up server discovery tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Search controls
        search_layout = QHBoxLayout()
        
        self.search_query = QLineEdit()
        self.search_query.setPlaceholderText("Search for servers...")
        search_layout.addWidget(self.search_query)
        
        self.search_type_filter = QComboBox()
        self.search_type_filter.addItems(["all", "npm", "docker", "docker-desktop"])
        search_layout.addWidget(self.search_type_filter)
        
        self.search_btn = QPushButton("Search")
        search_layout.addWidget(self.search_btn)
        
        layout.addLayout(search_layout)
        
        # Results display
        splitter = QSplitter(Qt.Horizontal)
        
        # Left side - results list
        self.discovery_list = QListWidget()
        splitter.addWidget(self.discovery_list)
        
        # Right side - server details
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        
        self.server_details = QTextEdit()
        self.server_details.setReadOnly(True)
        details_layout.addWidget(self.server_details)
        
        self.install_from_discovery_btn = QPushButton("Install Selected Server")
        self.install_from_discovery_btn.setEnabled(False)
        details_layout.addWidget(self.install_from_discovery_btn)
        
        splitter.addWidget(details_widget)
        splitter.setSizes([300, 400])
        
        layout.addWidget(splitter)
        
        self.tab_widget.addTab(tab, "Discover & Install")
    
    def setup_import_tab(self):
        """Set up configuration import tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        info_label = QLabel("Import server configuration from JSON or TOML file")
        layout.addWidget(info_label)
        
        # File selection
        file_layout = QHBoxLayout()
        self.import_file_path = QLineEdit()
        self.import_file_path.setPlaceholderText("Select configuration file...")
        file_layout.addWidget(self.import_file_path)
        
        self.browse_file_btn = QPushButton("Browse...")
        file_layout.addWidget(self.browse_file_btn)
        layout.addLayout(file_layout)
        
        # Preview imported config
        self.import_preview = QTextEdit()
        self.import_preview.setReadOnly(True)
        layout.addWidget(self.import_preview)
        
        # Import button
        self.import_config_btn = QPushButton("Import Configuration")
        self.import_config_btn.setEnabled(False)
        layout.addWidget(self.import_config_btn)
        
        self.tab_widget.addTab(tab, "Import from File")
    
    def setup_buttons(self, layout):
        """Set up dialog buttons."""
        button_layout = QHBoxLayout()
        
        self.test_connection_btn = QPushButton("Test Configuration")
        self.test_connection_btn.setEnabled(False)
        button_layout.addWidget(self.test_connection_btn)
        
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        button_layout.addWidget(self.cancel_btn)
        
        self.create_btn = QPushButton("Create Server")
        self.create_btn.setEnabled(False)
        button_layout.addWidget(self.create_btn)
        
        layout.addLayout(button_layout)
    
    def setup_connections(self):
        """Set up signal connections."""
        self.cancel_btn.clicked.connect(self.reject)
        self.create_btn.clicked.connect(self.create_server)
        self.test_connection_btn.clicked.connect(self.test_configuration)
        
        # Form validation
        self.name_edit.textChanged.connect(self.validate_form)
        self.npm_package.textChanged.connect(self.validate_form)
        self.docker_image.textChanged.connect(self.validate_form)
        self.custom_command.textChanged.connect(self.validate_form)
        
        # Discovery tab
        self.search_btn.clicked.connect(self.perform_discovery)
        self.discovery_list.itemSelectionChanged.connect(self.show_server_details)
        self.install_from_discovery_btn.clicked.connect(self.install_from_discovery)
        
        # Initial validation
        self.validate_form()
    
    def setup_preview_connections(self):
        """Connect all inputs to update command preview."""
        inputs = [
            self.name_edit, self.server_type, self.npm_package, self.docker_image,
            self.custom_command, self.custom_args, self.env_vars
        ]
        
        for input_widget in inputs:
            if hasattr(input_widget, 'textChanged'):
                input_widget.textChanged.connect(self.update_command_preview)
            elif hasattr(input_widget, 'currentTextChanged'):
                input_widget.currentTextChanged.connect(self.update_command_preview)
        
        self.update_command_preview()
    
    def update_form_for_type(self, server_type: str):
        """Update form visibility based on server type."""
        # Hide all type-specific configs
        configs = [
            self.npm_config, self.docker_config, 
            self.docker_desktop_config, self.custom_config
        ]
        
        for config in configs:
            config.hide()
        
        # Show relevant config
        if server_type == "npm":
            self.npm_config.show()
        elif server_type == "docker":
            self.docker_config.show()
        elif server_type == "docker-desktop":
            self.docker_desktop_config.show()
        elif server_type == "custom":
            self.custom_config.show()
        
        self.validate_form()
        self.update_command_preview()
    
    def validate_form(self):
        """Validate form inputs and enable/disable buttons."""
        is_valid = False
        
        # Name is always required
        if not self.name_edit.text().strip():
            self.create_btn.setEnabled(False)
            self.test_connection_btn.setEnabled(False)
            return
        
        server_type = self.server_type.currentText()
        
        if server_type == "npm":
            is_valid = bool(self.npm_package.text().strip())
        elif server_type == "docker":
            is_valid = bool(self.docker_image.text().strip())
        elif server_type == "docker-desktop":
            is_valid = True  # Dropdown selection is always valid
        elif server_type == "custom":
            is_valid = bool(self.custom_command.text().strip())
        
        self.create_btn.setEnabled(is_valid)
        self.test_connection_btn.setEnabled(is_valid)
    
    def update_command_preview(self):
        """Update the command preview based on current inputs."""
        try:
            server_type = self.server_type.currentText()
            name = self.name_edit.text().strip()
            
            if not name:
                self.command_preview.setText("Enter server name to see command preview")
                return
            
            # Build command based on type
            cmd_parts = ["mcp-manager", "add", name]
            
            if server_type == "npm":
                package = self.npm_package.text().strip()
                if package:
                    cmd_parts.extend(["--type", "npm", "--command", "npx"])
                    cmd_parts.extend(["--args", "-y", "--args", package, "--args", "--"])
            
            elif server_type == "docker":
                image = self.docker_image.text().strip()
                if image:
                    cmd_parts.extend(["--type", "docker", "--command", "docker"])
                    cmd_parts.extend(["--args", "run"])
                    
                    if self.docker_interactive.isChecked():
                        cmd_parts.extend(["--args", "-i"])
                    if self.docker_remove.isChecked():
                        cmd_parts.extend(["--args", "--rm"])
                    if self.docker_pull_always.isChecked():
                        cmd_parts.extend(["--args", "--pull", "--args", "always"])
                    
                    cmd_parts.extend(["--args", image])
            
            elif server_type == "docker-desktop":
                server_name = self.dd_server_list.currentText()
                cmd_parts.extend(["--type", "docker-desktop"])
                cmd_parts.extend(["--command", "docker"])
                cmd_parts.extend(["--args", "mcp", "--args", "gateway", "--args", "run"])
                cmd_parts.extend(["--args", "--servers", "--args", server_name])
            
            elif server_type == "custom":
                command = self.custom_command.text().strip()
                if command:
                    cmd_parts.extend(["--type", "custom", "--command", command])
            
            # Add description if provided
            desc = self.description_edit.text().strip()
            if desc:
                cmd_parts.extend(["--description", f'"{desc}"'])
            
            # Add scope
            scope = self.scope_combo.currentText()
            if scope != "user":
                cmd_parts.extend(["--scope", scope])
            
            self.command_preview.setText(" ".join(cmd_parts))
            
        except Exception as e:
            self.command_preview.setText(f"Error generating preview: {e}")
    
    def perform_discovery(self):
        """Perform server discovery."""
        if self.discovery_worker:
            return  # Already running
        
        query = self.search_query.text().strip()
        server_type = self.search_type_filter.currentText()
        if server_type == "all":
            server_type = None
        
        # Create and start discovery worker
        self.discovery_thread = QThread()
        self.discovery_worker = ServerDiscoveryWorker(self.cli_bridge)
        self.discovery_worker.moveToThread(self.discovery_thread)
        
        # Connect signals
        self.discovery_worker.discovery_completed.connect(self.handle_discovery_results)
        self.discovery_worker.error_occurred.connect(self.handle_discovery_error)
        self.discovery_thread.started.connect(
            lambda: asyncio.run(self.discovery_worker.discover_servers(server_type))
        )
        
        # Start discovery
        self.discovery_thread.start()
        self.search_btn.setText("Searching...")
        self.search_btn.setEnabled(False)
    
    def handle_discovery_results(self, results: List[Dict]):
        """Handle discovery results."""
        self.discovery_list.clear()
        
        for server in results[:50]:  # Limit results
            item = QListWidgetItem(f"{server.get('name', 'Unknown')} ({server.get('type', 'unknown')})")
            item.setData(Qt.UserRole, server)
            self.discovery_list.addItem(item)
        
        self.cleanup_discovery_worker()
    
    def handle_discovery_error(self, error: str):
        """Handle discovery error."""
        QMessageBox.warning(self, "Discovery Error", f"Failed to discover servers: {error}")
        self.cleanup_discovery_worker()
    
    def cleanup_discovery_worker(self):
        """Clean up discovery worker and thread."""
        self.search_btn.setText("Search")
        self.search_btn.setEnabled(True)
        
        if self.discovery_thread:
            self.discovery_thread.quit()
            self.discovery_thread.wait()
            self.discovery_thread = None
        
        self.discovery_worker = None
    
    def show_server_details(self):
        """Show details for selected server."""
        current_item = self.discovery_list.currentItem()
        if not current_item:
            self.server_details.clear()
            self.install_from_discovery_btn.setEnabled(False)
            return
        
        server_data = current_item.data(Qt.UserRole)
        if not server_data:
            return
        
        # Format server details
        details = []
        details.append(f"Name: {server_data.get('name', 'Unknown')}")
        details.append(f"Type: {server_data.get('type', 'unknown')}")
        details.append(f"Description: {server_data.get('description', 'No description')}")
        details.append(f"Install ID: {server_data.get('install_id', 'N/A')}")
        
        if 'quality_score' in server_data:
            details.append(f"Quality Score: {server_data['quality_score']}/100")
        
        self.server_details.setText("\n".join(details))
        self.install_from_discovery_btn.setEnabled(True)
    
    def install_from_discovery(self):
        """Install server from discovery results."""
        current_item = self.discovery_list.currentItem()
        if not current_item:
            return
        
        server_data = current_item.data(Qt.UserRole)
        install_id = server_data.get('install_id')
        
        if not install_id:
            QMessageBox.warning(self, "Installation Error", "No install ID available for this server.")
            return
        
        # Show progress dialog
        progress = QProgressDialog("Installing server...", "Cancel", 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        
        # Install server (this should be async in real implementation)
        asyncio.run(self._install_package_async(install_id, progress))
    
    async def _install_package_async(self, install_id: str, progress: QProgressDialog):
        """Install package asynchronously."""
        try:
            success = await self.cli_bridge.install_package(install_id)
            progress.close()
            
            if success:
                QMessageBox.information(self, "Success", f"Server '{install_id}' installed successfully!")
                self.accept()
            else:
                QMessageBox.warning(self, "Installation Failed", f"Failed to install server '{install_id}'.")
        
        except Exception as e:
            progress.close()
            QMessageBox.critical(self, "Installation Error", f"Error installing server: {e}")
    
    def test_configuration(self):
        """Test the current server configuration."""
        # This would test the server configuration without actually creating it
        QMessageBox.information(self, "Test Configuration", 
                               "Configuration test functionality will validate the server setup.")
    
    def create_server(self):
        """Create the server with current configuration."""
        try:
            server_type = self.server_type.currentText()
            name = self.name_edit.text().strip()
            description = self.description_edit.text().strip()
            scope = self.scope_combo.currentText()
            
            # Build server configuration
            config = {
                "name": name,
                "server_type": server_type,
                "description": description,
                "scope": scope
            }
            
            # Type-specific configuration
            if server_type == "npm":
                package = self.npm_package.text().strip()
                config["command"] = "npx"
                config["args"] = ["-y", package, "--"]
                
                # Add additional args
                extra_args = [line.strip() for line in self.npm_args.toPlainText().split('\n') if line.strip()]
                config["args"].extend(extra_args)
            
            elif server_type == "docker":
                image = self.docker_image.text().strip()
                config["command"] = "docker"
                config["args"] = ["run"]
                
                if self.docker_interactive.isChecked():
                    config["args"].append("-i")
                if self.docker_remove.isChecked():
                    config["args"].append("--rm")
                if self.docker_pull_always.isChecked():
                    config["args"].extend(["--pull", "always"])
                
                config["args"].append(image)
            
            elif server_type == "docker-desktop":
                server_name = self.dd_server_list.currentText()
                config["command"] = "docker"
                config["args"] = ["mcp", "gateway", "run", "--servers", server_name]
            
            elif server_type == "custom":
                command = self.custom_command.text().strip()
                config["command"] = command
                
                # Add custom args
                args = [line.strip() for line in self.custom_args.toPlainText().split('\n') if line.strip()]
                config["args"] = args
                
                working_dir = self.custom_working_dir.text().strip()
                if working_dir:
                    config["working_dir"] = working_dir
            
            # Environment variables
            env_text = self.env_vars.toPlainText().strip()
            if env_text:
                env_vars = {}
                for line in env_text.split('\n'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
                config["env"] = env_vars
            
            # Create server asynchronously
            asyncio.run(self._create_server_async(config))
            
        except Exception as e:
            QMessageBox.critical(self, "Creation Error", f"Failed to create server: {e}")
    
    async def _create_server_async(self, config: Dict[str, Any]):
        """Create server asynchronously."""
        try:
            success = await self.cli_bridge.add_server(**config)
            
            if success:
                # Auto-enable if requested
                if self.auto_enable.isChecked():
                    await self.cli_bridge.enable_server(config["name"])
                
                self.server_added.emit(config)
                QMessageBox.information(self, "Success", f"Server '{config['name']}' created successfully!")
                self.accept()
            else:
                QMessageBox.warning(self, "Creation Failed", f"Failed to create server '{config['name']}'.")
        
        except Exception as e:
            QMessageBox.critical(self, "Creation Error", f"Error creating server: {e}")


class EditServerDialog(AddServerDialog):
    """Dialog for editing existing servers."""
    
    server_updated = Signal(dict)
    
    def __init__(self, parent=None, cli_bridge: CLIBridge = None, server_data: Dict = None):
        self.server_data = server_data or {}
        super().__init__(parent, cli_bridge)
        
        self.setWindowTitle(f"Edit Server: {self.server_data.get('name', 'Unknown')}")
        self.create_btn.setText("Update Server")
        
        # Populate form with existing data
        self.populate_form()
    
    def populate_form(self):
        """Populate form with existing server data."""
        if not self.server_data:
            return
        
        # Basic information
        self.name_edit.setText(self.server_data.get('name', ''))
        self.name_edit.setEnabled(False)  # Can't change name of existing server
        
        self.description_edit.setText(self.server_data.get('description', ''))
        
        server_type = self.server_data.get('type', 'custom')
        type_index = self.server_type.findText(server_type)
        if type_index >= 0:
            self.server_type.setCurrentIndex(type_index)
        
        # Populate type-specific data
        self.update_form_for_type(server_type)
        
        # Environment variables
        env_vars = self.server_data.get('env', {})
        if env_vars:
            env_text = '\n'.join([f"{k}={v}" for k, v in env_vars.items()])
            self.env_vars.setText(env_text)
    
    async def _create_server_async(self, config: Dict[str, Any]):
        """Update server instead of creating new one."""
        try:
            # For editing, we would need an update_server method in CLI bridge
            # For now, remove and re-add (not ideal but functional)
            old_name = self.server_data.get('name')
            
            if old_name and old_name != config['name']:
                await self.cli_bridge.remove_server(old_name)
            
            success = await self.cli_bridge.add_server(**config)
            
            if success:
                self.server_updated.emit(config)
                QMessageBox.information(self, "Success", f"Server '{config['name']}' updated successfully!")
                self.accept()
            else:
                QMessageBox.warning(self, "Update Failed", f"Failed to update server '{config['name']}'.")
        
        except Exception as e:
            QMessageBox.critical(self, "Update Error", f"Error updating server: {e}")