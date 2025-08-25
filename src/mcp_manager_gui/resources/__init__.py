"""
MCP Manager GUI Resources

This module provides utilities for loading and managing GUI resources including
stylesheets, icons, and other assets used throughout the application.
"""

import os
import sys
from pathlib import Path
from typing import Optional
from PyQt6.QtCore import QFile, QTextStream, QDir
from PyQt6.QtGui import QIcon, QPixmap

# Resource directory path
RESOURCES_DIR = Path(__file__).parent


class ResourceManager:
    """Manages loading and access to GUI resources."""
    
    _instance: Optional['ResourceManager'] = None
    _stylesheet_cache: dict[str, str] = {}
    _icon_cache: dict[str, QIcon] = {}
    
    def __new__(cls) -> 'ResourceManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the resource manager."""
        self.resources_dir = RESOURCES_DIR
        self.styles_dir = self.resources_dir / "styles"
        self.icons_dir = self.resources_dir / "icons"
        
        # Ensure resource directories exist
        self.styles_dir.mkdir(exist_ok=True)
        self.icons_dir.mkdir(exist_ok=True)
    
    def load_stylesheet(self, name: str = "main.qss") -> str:
        """
        Load a QSS stylesheet file.
        
        Args:
            name: Name of the stylesheet file
            
        Returns:
            The stylesheet content as a string
        """
        if name in self._stylesheet_cache:
            return self._stylesheet_cache[name]
        
        stylesheet_path = self.styles_dir / name
        
        if not stylesheet_path.exists():
            raise FileNotFoundError(f"Stylesheet not found: {stylesheet_path}")
        
        try:
            with open(stylesheet_path, 'r', encoding='utf-8') as file:
                stylesheet_content = file.read()
                
            # Cache the stylesheet
            self._stylesheet_cache[name] = stylesheet_content
            return stylesheet_content
            
        except Exception as e:
            raise RuntimeError(f"Failed to load stylesheet {name}: {e}")
    
    def load_icon(self, name: str) -> QIcon:
        """
        Load an icon file.
        
        Args:
            name: Name of the icon file (with or without extension)
            
        Returns:
            QIcon object
        """
        # Add .svg extension if not present
        if not name.endswith(('.svg', '.png', '.jpg', '.jpeg')):
            name += '.svg'
        
        if name in self._icon_cache:
            return self._icon_cache[name]
        
        icon_path = self.icons_dir / name
        
        if not icon_path.exists():
            # Return empty icon instead of raising error
            return QIcon()
        
        try:
            icon = QIcon(str(icon_path))
            
            # Cache the icon
            self._icon_cache[name] = icon
            return icon
            
        except Exception:
            # Return empty icon on error
            return QIcon()
    
    def load_pixmap(self, name: str, size: Optional[tuple[int, int]] = None) -> QPixmap:
        """
        Load a pixmap from an icon file.
        
        Args:
            name: Name of the icon file
            size: Optional size tuple (width, height)
            
        Returns:
            QPixmap object
        """
        icon = self.load_icon(name)
        
        if size:
            return icon.pixmap(size[0], size[1])
        else:
            return icon.pixmap(16, 16)  # Default size
    
    def get_icon_path(self, name: str) -> Path:
        """
        Get the full path to an icon file.
        
        Args:
            name: Name of the icon file
            
        Returns:
            Path object to the icon file
        """
        if not name.endswith(('.svg', '.png', '.jpg', '.jpeg')):
            name += '.svg'
            
        return self.icons_dir / name
    
    def clear_cache(self):
        """Clear the resource caches."""
        self._stylesheet_cache.clear()
        self._icon_cache.clear()
    
    def preload_common_icons(self):
        """Preload commonly used icons for better performance."""
        common_icons = [
            'server_online.svg',
            'server_offline.svg', 
            'server_error.svg',
            'search.svg',
            'add.svg',
            'remove.svg',
            'settings.svg',
            'refresh.svg',
            'info.svg',
            'warning.svg',
            'error.svg',
            'success.svg'
        ]
        
        for icon_name in common_icons:
            self.load_icon(icon_name)


# Global resource manager instance
resource_manager = ResourceManager()


# Convenience functions for easy access
def load_stylesheet(name: str = "main.qss") -> str:
    """Load a stylesheet file."""
    return resource_manager.load_stylesheet(name)


def load_icon(name: str) -> QIcon:
    """Load an icon file.""" 
    return resource_manager.load_icon(name)


def load_pixmap(name: str, size: Optional[tuple[int, int]] = None) -> QPixmap:
    """Load a pixmap from an icon file."""
    return resource_manager.load_pixmap(name, size)


def get_icon_path(name: str) -> Path:
    """Get the full path to an icon file."""
    return resource_manager.get_icon_path(name)


def apply_theme(widget, theme: str = "light"):
    """
    Apply a theme to a widget by setting appropriate properties.
    
    Args:
        widget: The widget to apply the theme to
        theme: Theme name ("light" or "dark")
    """
    widget.setProperty("theme", theme)
    
    # Refresh the widget's style to apply new property
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def setup_app_resources():
    """
    Initialize application resources.
    Should be called once during application startup.
    """
    # Preload common resources
    resource_manager.preload_common_icons()
    
    # Load main stylesheet
    resource_manager.load_stylesheet("main.qss")


# Icon name constants for easy reference
class Icons:
    """Constants for icon names."""
    
    # Application
    APP_ICON = "app_icon"
    
    # Status
    SERVER_ONLINE = "server_online" 
    SERVER_OFFLINE = "server_offline"
    SERVER_ERROR = "server_error"
    
    # UI Controls
    SEARCH = "search"
    CHEVRON_DOWN = "chevron-down"
    ARROW_RIGHT = "arrow-right"
    ARROW_DOWN = "arrow-down"
    CHECKMARK = "checkmark"
    RADIO_DOT = "radio-dot"
    
    # Window Controls
    CLOSE = "close"
    RESTORE = "restore"
    
    # Actions
    ADD = "add"
    REMOVE = "remove"
    SETTINGS = "settings"
    REFRESH = "refresh"
    
    # Status Indicators
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"
    
    # Services
    DOCKER = "docker"
    NPM = "npm"
    CLAUDE = "claude"


# Style property constants
class Themes:
    """Constants for theme names."""
    LIGHT = "light"
    DARK = "dark"


class Styles:
    """Constants for style properties."""
    
    # Button styles
    BUTTON_PRIMARY = "primary"
    BUTTON_SECONDARY = "secondary"
    BUTTON_DESTRUCTIVE = "destructive"
    BUTTON_ICON = "icon"
    
    # Frame styles
    FRAME_CARD = "card"
    FRAME_SIDEBAR = "sidebar"
    
    # Widget types
    WIDGET_SERVER_CARD = "serverCard"
    WIDGET_DISCOVERY_CARD = "discoveryCard"
    
    # Status types
    STATUS_SUCCESS = "success"
    STATUS_WARNING = "warning"
    STATUS_ERROR = "error"
    STATUS_INFO = "info"
    
    # Badge styles
    BADGE_TRUE = "true"
    BADGE_SUCCESS = "success"
    BADGE_WARNING = "warning"
    BADGE_ERROR = "error"