"""
Suite Tree Widget - Hierarchical suite management widget.

Provides drag-and-drop functionality and context menus for suite operations.
"""

from typing import Dict, List, Optional, Any
from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QMenu, QMessageBox, QInputDialog,
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QDialogButtonBox, QComboBox, QTextEdit
)
from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QDrag, QPainter, QPixmap, QAction, QIcon

from ..services.cli_bridge import CLIBridge


class SuiteTreeWidget(QTreeWidget):
    """Tree widget for displaying and managing suites with drag-and-drop support."""
    
    suite_selected = Signal(dict)
    suite_context_menu = Signal(str, object)  # suite_name, menu_position
    server_dropped_on_suite = Signal(str, str)  # server_name, suite_name
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cli_bridge = CLIBridge()
        
        # Configure tree widget
        self.setDragDropMode(QTreeWidget.DropOnly)
        self.setAcceptDrops(True)
        self.setSelectionMode(QTreeWidget.SingleSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        
        # Set up context menu
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        # Configure appearance
        self.setAlternatingRowColors(True)
        self.setRootIsDecorated(True)
        self.setItemsExpandable(True)
        self.setExpandsOnDoubleClick(True)
        
        # Set up styling
        self.setStyleSheet("""
            QTreeWidget {
                background-color: #fafafa;
                border: 1px solid #d1d1d1;
                border-radius: 6px;
                selection-background-color: #007AFF;
            }
            
            QTreeWidget::item {
                padding: 4px;
                border-bottom: 1px solid #e5e5e5;
            }
            
            QTreeWidget::item:selected {
                background-color: #007AFF;
                color: white;
            }
            
            QTreeWidget::item:hover {
                background-color: #e8f4ff;
            }
            
            QTreeWidget::branch:has-siblings:!adjoins-item {
                border-image: url(vline.png) 0;
            }
            
            QTreeWidget::branch:has-siblings:adjoins-item {
                border-image: url(branch-more.png) 0;
            }
            
            QTreeWidget::branch:!has-children:!has-siblings:adjoins-item {
                border-image: url(branch-end.png) 0;
            }
            
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {
                border-image: none;
                image: url(branch-closed.png);
            }
            
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {
                border-image: none;
                image: url(branch-open.png);
            }
        """)
    
    def dragEnterEvent(self, event):
        """Handle drag enter events."""
        if event.mimeData().hasFormat("application/x-mcp-server"):
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dragMoveEvent(self, event):
        """Handle drag move events."""
        if event.mimeData().hasFormat("application/x-mcp-server"):
            item = self.itemAt(event.position().toPoint())
            if item and self.is_suite_item(item):
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """Handle drop events for adding servers to suites."""
        if event.mimeData().hasFormat("application/x-mcp-server"):
            server_name = event.mimeData().data("application/x-mcp-server").data().decode()
            
            item = self.itemAt(event.position().toPoint())
            if item and self.is_suite_item(item):
                suite_name = self.get_suite_name_from_item(item)
                if suite_name:
                    self.server_dropped_on_suite.emit(server_name, suite_name)
                    event.acceptProposedAction()
                    return
        
        event.ignore()
    
    def is_suite_item(self, item: QTreeWidgetItem) -> bool:
        """Check if the item represents a suite (not a category)."""
        if not item:
            return False
        
        item_data = item.data(0, Qt.UserRole)
        return item_data and item_data.get('type') == 'suite'
    
    def get_suite_name_from_item(self, item: QTreeWidgetItem) -> Optional[str]:
        """Get suite name from tree item."""
        if not self.is_suite_item(item):
            return None
        
        item_data = item.data(0, Qt.UserRole)
        return item_data.get('name') if item_data else None
    
    def show_context_menu(self, position):
        """Show context menu for tree items."""
        item = self.itemAt(position)
        if not item:
            return
        
        item_data = item.data(0, Qt.UserRole)
        if not item_data:
            return
        
        menu = QMenu(self)
        
        if item_data.get('type') == 'category':
            self.setup_category_context_menu(menu, item_data.get('name'))
        elif item_data.get('type') == 'suite':
            self.setup_suite_context_menu(menu, item_data.get('name'), item_data.get('data'))
        
        if menu.actions():
            global_pos = self.mapToGlobal(position)
            menu.exec(global_pos)
    
    def setup_category_context_menu(self, menu: QMenu, category_name: str):
        """Set up context menu for category items."""
        # Create new suite in category
        create_action = QAction(f"Create Suite in {category_name}", self)
        create_action.setIcon(QIcon(":/icons/add.svg"))
        create_action.triggered.connect(lambda: self.create_suite_in_category(category_name))
        menu.addAction(create_action)
        
        menu.addSeparator()
        
        # Expand/collapse category
        expand_action = QAction("Expand All", self)
        expand_action.triggered.connect(self.expandAll)
        menu.addAction(expand_action)
        
        collapse_action = QAction("Collapse All", self)
        collapse_action.triggered.connect(self.collapseAll)
        menu.addAction(collapse_action)
    
    def setup_suite_context_menu(self, menu: QMenu, suite_name: str, suite_data: Dict):
        """Set up context menu for suite items."""
        # View/Edit suite
        edit_action = QAction("Edit Suite", self)
        edit_action.setIcon(QIcon(":/icons/settings.svg"))
        edit_action.triggered.connect(lambda: self.edit_suite(suite_name))
        menu.addAction(edit_action)
        
        # Duplicate suite
        duplicate_action = QAction("Duplicate Suite", self)
        duplicate_action.setIcon(QIcon(":/icons/copy.svg"))
        duplicate_action.triggered.connect(lambda: self.duplicate_suite(suite_name))
        menu.addAction(duplicate_action)
        
        menu.addSeparator()
        
        # Install suite
        install_action = QAction("Install Suite", self)
        install_action.setIcon(QIcon(":/icons/download.svg"))
        install_action.triggered.connect(lambda: self.install_suite(suite_name))
        menu.addAction(install_action)
        
        # Enable/Disable suite
        servers = suite_data.get('servers', [])
        if servers:
            enable_action = QAction("Enable All Servers", self)
            enable_action.setIcon(QIcon(":/icons/server_online.svg"))
            enable_action.triggered.connect(lambda: self.enable_suite_servers(suite_name))
            menu.addAction(enable_action)
            
            disable_action = QAction("Disable All Servers", self)
            disable_action.setIcon(QIcon(":/icons/server_offline.svg"))
            disable_action.triggered.connect(lambda: self.disable_suite_servers(suite_name))
            menu.addAction(disable_action)
        
        menu.addSeparator()
        
        # Export suite
        export_action = QAction("Export Configuration", self)
        export_action.setIcon(QIcon(":/icons/export.svg"))
        export_action.triggered.connect(lambda: self.export_suite(suite_name))
        menu.addAction(export_action)
        
        menu.addSeparator()
        
        # Delete suite
        delete_action = QAction("Delete Suite", self)
        delete_action.setIcon(QIcon(":/icons/remove.svg"))
        delete_action.triggered.connect(lambda: self.delete_suite(suite_name))
        menu.addAction(delete_action)
    
    def create_suite_in_category(self, category_name: str):
        """Create a new suite in the specified category."""
        dialog = QuickCreateSuiteDialog(self, self.cli_bridge, category_name)
        if dialog.exec() == QDialog.Accepted:
            # Refresh tree after creation
            self.refresh_suites()
    
    def edit_suite(self, suite_name: str):
        """Open suite editing dialog."""
        # This would open a suite editing dialog
        # For now, just emit a signal that can be handled by parent
        self.suite_context_menu.emit(suite_name, "edit")
    
    def duplicate_suite(self, suite_name: str):
        """Duplicate an existing suite."""
        new_name, ok = QInputDialog.getText(
            self, "Duplicate Suite",
            f"Enter name for duplicate of '{suite_name}':",
            text=f"{suite_name}_copy"
        )
        
        if ok and new_name:
            # TODO: Implement suite duplication
            QMessageBox.information(self, "Duplicate Suite", 
                                   f"Would duplicate '{suite_name}' as '{new_name}'")
    
    def install_suite(self, suite_name: str):
        """Install suite servers."""
        reply = QMessageBox.question(
            self, "Install Suite",
            f"Install all servers in suite '{suite_name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        
        if reply == QMessageBox.Yes:
            # TODO: Implement suite installation
            QMessageBox.information(self, "Install Suite", 
                                   f"Would install suite '{suite_name}'")
    
    def enable_suite_servers(self, suite_name: str):
        """Enable all servers in suite."""
        # TODO: Implement enabling all suite servers
        QMessageBox.information(self, "Enable Suite", 
                               f"Would enable all servers in '{suite_name}'")
    
    def disable_suite_servers(self, suite_name: str):
        """Disable all servers in suite."""
        # TODO: Implement disabling all suite servers
        QMessageBox.information(self, "Disable Suite", 
                               f"Would disable all servers in '{suite_name}'")
    
    def export_suite(self, suite_name: str):
        """Export suite configuration."""
        # TODO: Implement suite export
        QMessageBox.information(self, "Export Suite", 
                               f"Would export configuration for '{suite_name}'")
    
    def delete_suite(self, suite_name: str):
        """Delete a suite with confirmation."""
        reply = QMessageBox.question(
            self, "Delete Suite",
            f"Are you sure you want to delete suite '{suite_name}'?\n\n"
            "This will remove the suite but not delete the individual servers.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # TODO: Implement suite deletion
            QMessageBox.information(self, "Delete Suite", 
                                   f"Would delete suite '{suite_name}'")
            # Refresh tree after deletion
            self.refresh_suites()
    
    def refresh_suites(self):
        """Refresh the suite tree display."""
        # This would be connected to the parent's refresh method
        # For now, just emit a signal
        pass
    
    def add_suite_item(self, suite_name: str, category: str, suite_data: Dict):
        """Add a suite item to the tree."""
        # Find or create category item
        category_item = None
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item.text(0) == category:
                category_item = item
                break
        
        if not category_item:
            category_item = QTreeWidgetItem([category, "", "", ""])
            category_item.setData(0, Qt.UserRole, {"type": "category", "name": category})
            self.addTopLevelItem(category_item)
            category_item.setExpanded(True)
        
        # Create suite item
        server_count = len(suite_data.get('servers', []))
        status = self.calculate_suite_status(suite_data)
        
        suite_item = QTreeWidgetItem([
            suite_name,
            category,
            str(server_count),
            status
        ])
        suite_item.setData(0, Qt.UserRole, {
            "type": "suite",
            "name": suite_name,
            "data": suite_data
        })
        
        category_item.addChild(suite_item)
        
        # Update category item server count
        total_suites = category_item.childCount()
        category_item.setText(2, f"{total_suites} suites")
    
    def calculate_suite_status(self, suite_data: Dict) -> str:
        """Calculate suite status based on server states."""
        servers = suite_data.get('servers', [])
        if not servers:
            return "Empty"
        
        # For now, return a simple status
        # This could be enhanced to check actual server states
        return f"{len(servers)} servers"


class QuickCreateSuiteDialog(QDialog):
    """Quick dialog for creating suites."""
    
    def __init__(self, parent=None, cli_bridge: CLIBridge = None, default_category: str = ""):
        super().__init__(parent)
        self.cli_bridge = cli_bridge or CLIBridge()
        
        self.setWindowTitle("Create Suite")
        self.setModal(True)
        self.resize(350, 200)
        self.setup_ui(default_category)
    
    def setup_ui(self, default_category: str):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Name
        layout.addWidget(QLabel("Suite Name:"))
        self.name_edit = QLineEdit()
        layout.addWidget(self.name_edit)
        
        # Category
        layout.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItems([
            "Development", "Production", "Testing", "Database",
            "AI/ML", "Web Services", "DevOps", "Custom"
        ])
        if default_category:
            self.category_combo.setCurrentText(default_category)
        layout.addWidget(self.category_combo)
        
        # Description
        layout.addWidget(QLabel("Description (optional):"))
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(60)
        layout.addWidget(self.description_edit)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        self.create_btn = QPushButton("Create")
        self.create_btn.clicked.connect(self.create_suite)
        self.create_btn.setEnabled(False)
        button_layout.addWidget(self.create_btn)
        
        layout.addLayout(button_layout)
        
        # Connect validation
        self.name_edit.textChanged.connect(self.validate_input)
    
    def validate_input(self):
        """Validate input and enable create button."""
        has_name = bool(self.name_edit.text().strip())
        self.create_btn.setEnabled(has_name)
    
    def create_suite(self):
        """Create the suite."""
        name = self.name_edit.text().strip()
        category = self.category_combo.currentText().strip()
        description = self.description_edit.toPlainText().strip()
        
        if not name:
            return
        
        try:
            # TODO: Implement actual suite creation via CLI bridge
            QMessageBox.information(self, "Success", f"Suite '{name}' created successfully!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create suite: {e}")