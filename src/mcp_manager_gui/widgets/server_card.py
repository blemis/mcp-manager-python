"""
Server Card Widget - Individual server information display card.

Provides a card-style display for individual MCP servers with status indicators,
actions, and detailed information.
"""

from typing import Dict, Any, Optional
import asyncio
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFrame, QMenu, QGraphicsDropShadowEffect, QSizePolicy,
    QMessageBox, QProgressBar, QToolTip
)
from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import QFont, QPalette, QAction, QPixmap, QPainter, QColor, QCursor

from ..services.cli_bridge import CLIBridge


class StatusIndicator(QWidget):
    """Custom status indicator widget with animated states."""
    
    def __init__(self, status: str = "Unknown", parent=None):
        super().__init__(parent)
        self.status = status
        self.setFixedSize(12, 12)
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_phase = 0
        
        if status in ["Connected", "Connecting"]:
            self.animation_timer.start(500)  # Pulse every 500ms
    
    def set_status(self, status: str):
        """Update the status and restart animation if needed."""
        self.status = status
        self.animation_timer.stop()
        
        if status in ["Connected", "Connecting"]:
            self.animation_timer.start(500)
        
        self.update()
    
    def update_animation(self):
        """Update animation phase."""
        self.animation_phase = (self.animation_phase + 1) % 4
        self.update()
    
    def paintEvent(self, event):
        """Custom paint event for status indicator."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.rect()
        center_x = rect.width() // 2
        center_y = rect.height() // 2
        radius = min(rect.width(), rect.height()) // 2 - 1
        
        # Base color based on status
        if self.status == "Connected":
            base_color = QColor("#34C759")  # Green
        elif self.status == "Connecting":
            base_color = QColor("#FF9500")  # Orange
        elif self.status == "Failed":
            base_color = QColor("#FF3B30")  # Red
        elif self.status == "Disabled":
            base_color = QColor("#8E8E93")  # Gray
        else:  # Unknown
            base_color = QColor("#C7C7CC")  # Light gray
        
        # Apply animation effects
        if self.status == "Connecting":
            # Pulsing effect
            alpha = 100 + 155 * (0.5 + 0.5 * (self.animation_phase % 2))
            base_color.setAlpha(int(alpha))
        elif self.status == "Connected":
            # Subtle glow
            painter.setBrush(QColor(base_color.red(), base_color.green(), base_color.blue(), 50))
            painter.drawEllipse(center_x - radius - 1, center_y - radius - 1, 
                              (radius + 1) * 2, (radius + 1) * 2)
        
        painter.setBrush(base_color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)


class ServerCard(QFrame):
    """Individual server card widget with status and actions."""
    
    server_selected = Signal(dict)  # Emitted when card is selected
    action_requested = Signal(str, str)  # action, server_name
    
    def __init__(self, server_data: Dict[str, Any], cli_bridge: CLIBridge, parent=None):
        super().__init__(parent)
        self.server_data = server_data
        self.cli_bridge = cli_bridge
        self.is_selected = False
        self.is_hovered = False
        
        self.setup_ui()
        self.apply_styling()
        self.setup_context_menu()
        self.setup_animations()
        
        # Update display
        self.update_display()
    
    def setup_ui(self):
        """Set up the user interface."""
        self.setFrameStyle(QFrame.Box)
        self.setLineWidth(1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(120)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        
        # Main layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)
        
        # Left section - Status and basic info
        self.setup_left_section(layout)
        
        # Middle section - Details
        self.setup_middle_section(layout)
        
        # Right section - Actions
        self.setup_right_section(layout)
    
    def setup_left_section(self, parent_layout):
        """Set up the left section with status and basic info."""
        left_frame = QFrame()
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        
        # Status indicator and name
        status_layout = QHBoxLayout()
        status_layout.setSpacing(8)
        
        self.status_indicator = StatusIndicator(
            self.server_data.get('claude_status', 'Unknown')
        )
        status_layout.addWidget(self.status_indicator)
        
        self.name_label = QLabel(self.server_data.get('name', 'Unknown'))
        name_font = QFont()
        name_font.setPointSize(14)
        name_font.setWeight(QFont.Weight.Bold)
        self.name_label.setFont(name_font)
        status_layout.addWidget(self.name_label)
        status_layout.addStretch()
        
        left_layout.addLayout(status_layout)
        
        # Server type
        self.type_label = QLabel(self.server_data.get('type', 'Custom'))
        type_font = QFont()
        type_font.setPointSize(11)
        self.type_label.setFont(type_font)
        self.type_label.setStyleSheet("QLabel { color: #8E8E93; }")
        left_layout.addWidget(self.type_label)
        
        # Status text
        status_text = self.server_data.get('claude_status', 'Unknown')
        self.status_label = QLabel(f"Status: {status_text}")
        status_font = QFont()
        status_font.setPointSize(10)
        self.status_label.setFont(status_font)
        self.status_label.setStyleSheet(f"QLabel {{ color: {self.get_status_color(status_text)}; }}")
        left_layout.addWidget(self.status_label)
        
        left_layout.addStretch()
        parent_layout.addWidget(left_frame)
    
    def setup_middle_section(self, parent_layout):
        """Set up the middle section with details."""
        middle_frame = QFrame()
        middle_layout = QVBoxLayout(middle_frame)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(4)
        
        # Description
        description = self.server_data.get('description', 'No description available')
        self.description_label = QLabel(description)
        desc_font = QFont()
        desc_font.setPointSize(11)
        self.description_label.setFont(desc_font)
        self.description_label.setStyleSheet("QLabel { color: #3C3C43; }")
        self.description_label.setWordWrap(True)
        self.description_label.setMaximumHeight(40)
        middle_layout.addWidget(self.description_label)
        
        # Command info (if available)
        command = self.server_data.get('command', '')
        if command:
            self.command_label = QLabel(f"Command: {command}")
            cmd_font = QFont()
            cmd_font.setPointSize(9)
            cmd_font.setFamily("Monaco, Menlo, Consolas, monospace")
            self.command_label.setFont(cmd_font)
            self.command_label.setStyleSheet("""
                QLabel { 
                    color: #8E8E93; 
                    background-color: #F2F2F7;
                    padding: 4px 6px;
                    border-radius: 4px;
                }
            """)
            middle_layout.addWidget(self.command_label)
        
        # Tools count (if available)
        tools = self.server_data.get('tools', [])
        if tools:
            tools_text = f"{len(tools)} tool{'s' if len(tools) != 1 else ''} available"
            self.tools_label = QLabel(tools_text)
            tools_font = QFont()
            tools_font.setPointSize(10)
            self.tools_label.setFont(tools_font)
            self.tools_label.setStyleSheet("QLabel { color: #007AFF; }")
            middle_layout.addWidget(self.tools_label)
        
        middle_layout.addStretch()
        parent_layout.addWidget(middle_frame, 1)  # Give it stretch factor
    
    def setup_right_section(self, parent_layout):
        """Set up the right section with action buttons."""
        right_frame = QFrame()
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)
        
        # Enable/Disable toggle
        self.toggle_btn = QPushButton()
        self.update_toggle_button()
        self.toggle_btn.clicked.connect(self.toggle_server)
        self.toggle_btn.setFixedSize(80, 28)
        right_layout.addWidget(self.toggle_btn)
        
        # Info button
        self.info_btn = QPushButton("Info")
        self.info_btn.clicked.connect(self.show_server_info)
        self.info_btn.setFixedSize(80, 28)
        self.info_btn.setStyleSheet("""
            QPushButton {
                background-color: #F2F2F7;
                color: #007AFF;
                border: 1px solid #D1D1D6;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #E5E5EA;
                border-color: #007AFF;
            }
            QPushButton:pressed {
                background-color: #D1D1D6;
            }
        """)
        right_layout.addWidget(self.info_btn)
        
        # More actions button
        self.more_btn = QPushButton("⋯")
        self.more_btn.clicked.connect(self.show_context_menu)
        self.more_btn.setFixedSize(80, 28)
        self.more_btn.setStyleSheet(self.info_btn.styleSheet())
        right_layout.addWidget(self.more_btn)
        
        right_layout.addStretch()
        parent_layout.addWidget(right_frame)
    
    def setup_context_menu(self):
        """Set up the context menu."""
        self.context_menu = QMenu(self)
        
        # Enable/Disable action
        self.toggle_action = QAction(self)
        self.toggle_action.triggered.connect(self.toggle_server)
        self.context_menu.addAction(self.toggle_action)
        
        self.context_menu.addSeparator()
        
        # Info action
        info_action = QAction("Show Information", self)
        info_action.triggered.connect(self.show_server_info)
        self.context_menu.addAction(info_action)
        
        # Restart action (if enabled)
        restart_action = QAction("Restart Server", self)
        restart_action.triggered.connect(lambda: self.action_requested.emit("restart", self.server_data.get('name', '')))
        self.context_menu.addAction(restart_action)
        
        self.context_menu.addSeparator()
        
        # Remove action
        remove_action = QAction("Remove Server", self)
        remove_action.triggered.connect(lambda: self.action_requested.emit("remove", self.server_data.get('name', '')))
        self.context_menu.addAction(remove_action)
        
        # Update context menu based on status
        self.update_context_menu()
    
    def setup_animations(self):
        """Set up animations for hover and selection effects."""
        # Selection animation
        self.selection_animation = QPropertyAnimation(self, b"geometry")
        self.selection_animation.setDuration(150)
        self.selection_animation.setEasingCurve(QEasingCurve.OutQuad)
        
        # Drop shadow effect for selection
        self.shadow_effect = QGraphicsDropShadowEffect()
        self.shadow_effect.setBlurRadius(8)
        self.shadow_effect.setColor(QColor(0, 122, 255, 100))
        self.shadow_effect.setOffset(0, 2)
        self.shadow_effect.setEnabled(False)
        self.setGraphicsEffect(self.shadow_effect)
    
    def update_display(self):
        """Update the card display with current server data."""
        # Update status indicator
        status = self.server_data.get('claude_status', 'Unknown')
        self.status_indicator.set_status(status)
        
        # Update labels
        self.name_label.setText(self.server_data.get('name', 'Unknown'))
        self.type_label.setText(self.server_data.get('type', 'Custom'))
        self.status_label.setText(f"Status: {status}")
        self.status_label.setStyleSheet(f"QLabel {{ color: {self.get_status_color(status)}; }}")
        
        # Update description
        description = self.server_data.get('description', 'No description available')
        self.description_label.setText(description)
        
        # Update toggle button
        self.update_toggle_button()
        self.update_context_menu()
    
    def update_toggle_button(self):
        """Update the enable/disable toggle button."""
        status = self.server_data.get('claude_status', 'Unknown')
        is_enabled = status in ['Connected', 'Connecting']
        
        if is_enabled:
            self.toggle_btn.setText("Disable")
            self.toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #FF3B30;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #E6352A;
                }
                QPushButton:pressed {
                    background-color: #CC2F24;
                }
            """)
        else:
            self.toggle_btn.setText("Enable")
            self.toggle_btn.setStyleSheet("""
                QPushButton {
                    background-color: #34C759;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #30B050;
                }
                QPushButton:pressed {
                    background-color: #2A9946;
                }
            """)
    
    def update_context_menu(self):
        """Update context menu based on current status."""
        status = self.server_data.get('claude_status', 'Unknown')
        is_enabled = status in ['Connected', 'Connecting']
        
        if is_enabled:
            self.toggle_action.setText("Disable Server")
        else:
            self.toggle_action.setText("Enable Server")
    
    def get_status_color(self, status: str) -> str:
        """Get color for status text."""
        if status == "Connected":
            return "#34C759"
        elif status == "Connecting":
            return "#FF9500"
        elif status == "Failed":
            return "#FF3B30"
        elif status == "Disabled":
            return "#8E8E93"
        else:
            return "#C7C7CC"
    
    def set_selected(self, selected: bool):
        """Set the selection state of the card."""
        if self.is_selected == selected:
            return
        
        self.is_selected = selected
        self.shadow_effect.setEnabled(selected)
        self.update_styling()
    
    def apply_styling(self):
        """Apply base styling to the card."""
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #E5E5EA;
                border-radius: 12px;
            }
            QFrame:hover {
                border-color: #C7C7CC;
                background-color: #FBFBFD;
            }
        """)
    
    def update_styling(self):
        """Update styling based on current state."""
        if self.is_selected:
            border_color = "#007AFF"
            bg_color = "#F0F8FF"
        elif self.is_hovered:
            border_color = "#C7C7CC"
            bg_color = "#FBFBFD"
        else:
            border_color = "#E5E5EA"
            bg_color = "white"
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: 12px;
            }}
        """)
    
    def mousePressEvent(self, event):
        """Handle mouse press events."""
        if event.button() == Qt.LeftButton:
            self.server_selected.emit(self.server_data)
        elif event.button() == Qt.RightButton:
            self.show_context_menu_at_cursor()
        super().mousePressEvent(event)
    
    def enterEvent(self, event):
        """Handle mouse enter events."""
        self.is_hovered = True
        self.update_styling()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Handle mouse leave events."""
        self.is_hovered = False
        self.update_styling()
        super().leaveEvent(event)
    
    def toggle_server(self):
        """Toggle server enable/disable state."""
        status = self.server_data.get('claude_status', 'Unknown')
        is_enabled = status in ['Connected', 'Connecting']
        
        action = "disable" if is_enabled else "enable"
        server_name = self.server_data.get('name', '')
        
        self.action_requested.emit(action, server_name)
    
    def show_server_info(self):
        """Show detailed server information."""
        info_dialog = ServerInfoDialog(self.server_data, self)
        info_dialog.exec()
    
    def show_context_menu(self):
        """Show context menu at button position."""
        self.show_context_menu_at_cursor()
    
    def show_context_menu_at_cursor(self):
        """Show context menu at cursor position."""
        self.context_menu.popup(QCursor.pos())


class ServerInfoDialog(QMessageBox):
    """Dialog showing detailed server information."""
    
    def __init__(self, server_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.server_data = server_data
        
        self.setWindowTitle(f"Server Information - {server_data.get('name', 'Unknown')}")
        self.setIcon(QMessageBox.Information)
        
        # Build detailed info text
        info_parts = []
        
        # Basic info
        info_parts.append(f"Name: {server_data.get('name', 'Unknown')}")
        info_parts.append(f"Type: {server_data.get('type', 'Custom')}")
        info_parts.append(f"Status: {server_data.get('claude_status', 'Unknown')}")
        
        # Description
        if server_data.get('description'):
            info_parts.append(f"Description: {server_data.get('description')}")
        
        # Command
        if server_data.get('command'):
            info_parts.append(f"Command: {server_data.get('command')}")
        
        # Arguments
        if server_data.get('args'):
            args_str = ' '.join(server_data.get('args', []))
            info_parts.append(f"Arguments: {args_str}")
        
        # Environment variables
        if server_data.get('env'):
            env_items = [f"{k}={v}" for k, v in server_data.get('env', {}).items()]
            info_parts.append(f"Environment: {', '.join(env_items)}")
        
        # Working directory
        if server_data.get('working_dir'):
            info_parts.append(f"Working Directory: {server_data.get('working_dir')}")
        
        # Tools
        tools = server_data.get('tools', [])
        if tools:
            info_parts.append(f"Available Tools: {len(tools)}")
            for i, tool in enumerate(tools[:5]):  # Show first 5 tools
                tool_name = tool.get('name', f'Tool {i+1}')
                info_parts.append(f"  • {tool_name}")
            if len(tools) > 5:
                info_parts.append(f"  ... and {len(tools) - 5} more")
        
        self.setText('\n'.join(info_parts))
        self.setStandardButtons(QMessageBox.Ok)
        
        # Apply macOS styling
        self.setStyleSheet("""
            QMessageBox {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                font-size: 13px;
            }
        """)