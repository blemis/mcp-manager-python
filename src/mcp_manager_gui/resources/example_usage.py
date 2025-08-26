#!/usr/bin/env python3
"""
Example usage of the MCP Manager GUI resource system.

This file demonstrates how to use the resource manager to load
stylesheets, icons, and apply themes to widgets.
"""

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QWidget, QListWidget, 
    QLineEdit, QComboBox, QCheckBox
)
from PyQt6.QtCore import Qt

# Import the resource system
from . import (
    load_stylesheet, load_icon, apply_theme,
    setup_app_resources, Icons, Themes, Styles
)


class ExampleWindow(QMainWindow):
    """Example window showcasing the resource system."""
    
    def __init__(self):
        super().__init__()
        self.current_theme = Themes.LIGHT
        self.init_ui()
        self.apply_styling()
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("MCP Manager Resource Example")
        self.setGeometry(100, 100, 800, 600)
        
        # Set window icon
        self.setWindowIcon(load_icon(Icons.APP_ICON))
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        layout = QVBoxLayout(central_widget)
        
        # Theme toggle
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Theme:")
        self.theme_button = QPushButton("Switch to Dark")
        self.theme_button.clicked.connect(self.toggle_theme)
        theme_layout.addWidget(theme_label)
        theme_layout.addWidget(self.theme_button)
        theme_layout.addStretch()
        layout.addLayout(theme_layout)
        
        # Button examples
        button_frame = QFrame()
        button_frame.setProperty("frameStyle", Styles.FRAME_CARD)
        button_layout = QHBoxLayout(button_frame)
        
        # Primary button
        primary_btn = QPushButton("Primary Action")
        primary_btn.setProperty("buttonStyle", Styles.BUTTON_PRIMARY)
        primary_btn.setIcon(load_icon(Icons.ADD))
        button_layout.addWidget(primary_btn)
        
        # Secondary button
        secondary_btn = QPushButton("Secondary")
        secondary_btn.setProperty("buttonStyle", Styles.BUTTON_SECONDARY)
        secondary_btn.setIcon(load_icon(Icons.SETTINGS))
        button_layout.addWidget(secondary_btn)
        
        # Destructive button
        destructive_btn = QPushButton("Delete")
        destructive_btn.setProperty("buttonStyle", Styles.BUTTON_DESTRUCTIVE)
        destructive_btn.setIcon(load_icon(Icons.REMOVE))
        button_layout.addWidget(destructive_btn)
        
        # Icon button
        icon_btn = QPushButton()
        icon_btn.setProperty("buttonStyle", Styles.BUTTON_ICON)
        icon_btn.setIcon(load_icon(Icons.REFRESH))
        icon_btn.setToolTip("Refresh")
        button_layout.addWidget(icon_btn)
        
        layout.addWidget(button_frame)
        
        # Status examples
        status_frame = QFrame()
        status_frame.setProperty("frameStyle", Styles.FRAME_CARD)
        status_layout = QVBoxLayout(status_frame)
        
        status_label = QLabel("Status Examples")
        status_label.setProperty("class", "text-lg font-semibold")
        status_layout.addWidget(status_label)
        
        # Status indicators
        status_row = QHBoxLayout()
        
        success_label = QLabel("Success")
        success_label.setProperty("statusType", Styles.STATUS_SUCCESS)
        status_row.addWidget(load_icon(Icons.SUCCESS).pixmap(16, 16))
        status_row.addWidget(success_label)
        
        warning_label = QLabel("Warning")
        warning_label.setProperty("statusType", Styles.STATUS_WARNING)
        status_row.addWidget(QLabel())
        status_row.addWidget(warning_label)
        
        error_label = QLabel("Error") 
        error_label.setProperty("statusType", Styles.STATUS_ERROR)
        status_row.addWidget(QLabel())
        status_row.addWidget(error_label)
        
        status_row.addStretch()
        status_layout.addLayout(status_row)
        
        # Server status cards
        server_row = QHBoxLayout()
        
        # Online server
        online_card = QFrame()
        online_card.setProperty("widgetType", Styles.WIDGET_SERVER_CARD)
        online_layout = QVBoxLayout(online_card)
        online_icon = QLabel()
        online_icon.setPixmap(load_icon(Icons.SERVER_ONLINE).pixmap(24, 24))
        online_layout.addWidget(online_icon)
        online_layout.addWidget(QLabel("Server Online"))
        server_row.addWidget(online_card)
        
        # Offline server
        offline_card = QFrame()
        offline_card.setProperty("widgetType", Styles.WIDGET_SERVER_CARD)
        offline_layout = QVBoxLayout(offline_card)
        offline_icon = QLabel()
        offline_icon.setPixmap(load_icon(Icons.SERVER_OFFLINE).pixmap(24, 24))
        offline_layout.addWidget(offline_icon)
        offline_layout.addWidget(QLabel("Server Offline"))
        server_row.addWidget(offline_card)
        
        # Error server
        error_card = QFrame()
        error_card.setProperty("widgetType", Styles.WIDGET_SERVER_CARD)
        error_layout = QVBoxLayout(error_card)
        error_icon = QLabel()
        error_icon.setPixmap(load_icon(Icons.SERVER_ERROR).pixmap(24, 24))
        error_layout.addWidget(error_icon)
        error_layout.addWidget(QLabel("Server Error"))
        server_row.addWidget(error_card)
        
        status_layout.addLayout(server_row)
        layout.addWidget(status_frame)
        
        # Input examples
        input_frame = QFrame()
        input_frame.setProperty("frameStyle", Styles.FRAME_CARD)
        input_layout = QVBoxLayout(input_frame)
        
        input_label = QLabel("Input Controls")
        input_label.setProperty("class", "text-lg font-semibold")
        input_layout.addWidget(input_label)
        
        # Search field
        search_field = QLineEdit()
        search_field.setPlaceholderText("Search servers...")
        search_field.setProperty("searchField", True)
        input_layout.addWidget(search_field)
        
        # Combo box
        combo = QComboBox()
        combo.addItems(["Docker", "NPM", "Custom"])
        input_layout.addWidget(combo)
        
        # Checkbox
        checkbox = QCheckBox("Enable auto-discovery")
        input_layout.addWidget(checkbox)
        
        layout.addWidget(input_frame)
        
        # List widget
        list_widget = QListWidget()
        list_widget.addItems([
            "Docker Desktop SQLite",
            "NPM Filesystem Server",
            "Custom Python Server",
            "Docker Hub Server"
        ])
        layout.addWidget(list_widget)
        
        layout.addStretch()
    
    def apply_styling(self):
        """Apply the stylesheet to the application."""
        try:
            stylesheet = load_stylesheet("main.qss")
            self.setStyleSheet(stylesheet)
        except Exception as e:
            print(f"Failed to load stylesheet: {e}")
    
    def toggle_theme(self):
        """Toggle between light and dark themes."""
        if self.current_theme == Themes.LIGHT:
            self.current_theme = Themes.DARK
            self.theme_button.setText("Switch to Light")
        else:
            self.current_theme = Themes.LIGHT
            self.theme_button.setText("Switch to Dark")
        
        # Apply theme to all widgets recursively
        self.apply_theme_recursive(self, self.current_theme)
    
    def apply_theme_recursive(self, widget, theme):
        """Apply theme to widget and all its children."""
        apply_theme(widget, theme)
        
        for child in widget.findChildren(QWidget):
            apply_theme(child, theme)


def main():
    """Run the example application."""
    app = QApplication(sys.argv)
    
    # Setup resources
    setup_app_resources()
    
    # Create and show window
    window = ExampleWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())