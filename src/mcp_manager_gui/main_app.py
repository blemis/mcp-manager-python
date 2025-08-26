"""
MCP Manager GUI - Main Application Entry Point

This module provides the main PySide6 application setup and lifecycle management
for the MCP Manager GUI application on macOS.
"""

import sys
import os
import asyncio
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QSettings, Qt
from PySide6.QtGui import QIcon, QPalette

from mcp_manager.utils.logging import get_logger
from .windows.main_window_modern import ModernMainWindow as MainWindow
from .services.cli_bridge import CLIBridge


logger = get_logger(__name__)


class MCPManagerApp(QApplication):
    """Main MCP Manager PySide6 application class."""
    
    def __init__(self, argv):
        """Initialize the MCP Manager application."""
        super().__init__(argv)
        
        # Set application metadata (fixes macOS menu to show "MCP Manager" not "Python")
        self.setApplicationName("MCP Manager")
        self.setApplicationDisplayName("MCP Manager") 
        self.setApplicationVersion("2.0.0")
        self.setOrganizationName("MCP Manager")
        self.setOrganizationDomain("mcp-manager.dev")
        
        # Fix macOS app name in menu bar
        try:
            import Foundation
            bundle = Foundation.NSBundle.mainBundle()
            info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
            if info:
                info['CFBundleName'] = 'MCP Manager'
                info['CFBundleDisplayName'] = 'MCP Manager'
        except ImportError:
            # Foundation not available on non-macOS systems
            pass
        
        # Initialize components
        self.cli_bridge: Optional[CLIBridge] = None
        self.main_window: Optional[MainWindow] = None
        self.settings = QSettings()
        
        # Setup application
        self._setup_application()
        self._setup_event_loop()
    
    def _setup_application(self) -> None:
        """Setup application-wide configuration."""
        # Set high DPI support
        self.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        self.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
        # Set application icon
        self._setup_app_icon()
        
        # Setup dark/light mode support
        self._setup_theme_support()
        
        # Create CLI bridge
        self.cli_bridge = CLIBridge()
        
        logger.info("MCP Manager GUI application initialized")
    
    def _setup_app_icon(self) -> None:
        """Setup application icon."""
        try:
            # Look for icon files in resources
            icon_dir = Path(__file__).parent / "resources" / "icons"
            icon_paths = [
                icon_dir / "mcp-manager.icns",  # macOS preferred
                icon_dir / "mcp-manager.png",   # Fallback
                icon_dir / "app-icon.icns",
                icon_dir / "app-icon.png"
            ]
            
            for icon_path in icon_paths:
                if icon_path.exists():
                    self.setWindowIcon(QIcon(str(icon_path)))
                    logger.debug(f"Application icon set from {icon_path}")
                    return
            
            logger.warning("No application icon found, using default")
            
        except Exception as e:
            logger.error(f"Error setting application icon: {e}")
    
    def _setup_theme_support(self) -> None:
        """Setup dark/light mode theme support."""
        try:
            # Check system theme preference
            palette = self.palette()
            dark_mode = palette.color(QPalette.Window).lightness() < 128
            
            # Store theme preference
            self.settings.setValue("theme/dark_mode", dark_mode)
            
            # Apply macOS native styling
            self.setStyle("macOS")  # Use native macOS style
            
            logger.debug(f"Theme setup complete, dark mode: {dark_mode}")
            
        except Exception as e:
            logger.error(f"Error setting up theme support: {e}")
    
    def _setup_event_loop(self) -> None:
        """Setup async event loop integration."""
        try:
            # Create event loop for async operations
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # Setup periodic event loop processing
            self.timer = QTimer()
            self.timer.timeout.connect(self._process_async_events)
            self.timer.start(100)  # Process every 100ms
            
            logger.debug("Async event loop integration setup complete")
            
        except Exception as e:
            logger.error(f"Error setting up event loop: {e}")
    
    def _process_async_events(self) -> None:
        """Process async events in the event loop."""
        try:
            # Process any pending async tasks
            if self.loop and self.loop.is_running():
                return
            
            # Run pending coroutines
            pending = asyncio.all_tasks(self.loop)
            if pending:
                self.loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
                
        except Exception as e:
            logger.debug(f"Error processing async events: {e}")
    
    def create_main_window(self) -> None:
        """Create and show the main application window."""
        try:
            # Create main window (ModernMainWindow creates its own CLI bridge)
            self.main_window = MainWindow()
            
            # Restore window geometry if available
            self._restore_window_state()
            
            # Show the window
            self.main_window.show()
            
            # Bring to front on macOS
            self.main_window.raise_()
            self.main_window.activateWindow()
            
            logger.info("Main window created and displayed")
            
        except Exception as e:
            logger.error(f"Error creating main window: {e}")
            raise
    
    def _restore_window_state(self) -> None:
        """Restore saved window state."""
        if not self.main_window:
            return
            
        try:
            # Restore geometry
            geometry = self.settings.value("window/geometry")
            if geometry:
                self.main_window.restoreGeometry(geometry)
            
            # Restore window state (maximized, etc.)
            state = self.settings.value("window/state")
            if state:
                self.main_window.restoreState(state)
                
            logger.debug("Window state restored")
            
        except Exception as e:
            logger.error(f"Error restoring window state: {e}")
    
    def save_window_state(self) -> None:
        """Save current window state."""
        if not self.main_window:
            return
            
        try:
            # Save geometry
            self.settings.setValue("window/geometry", self.main_window.saveGeometry())
            
            # Save window state
            self.settings.setValue("window/state", self.main_window.saveState())
            
            logger.debug("Window state saved")
            
        except Exception as e:
            logger.error(f"Error saving window state: {e}")
    
    def cleanup(self) -> None:
        """Cleanup application resources."""
        try:
            # Save window state
            self.save_window_state()
            
            # Stop async event processing
            if hasattr(self, 'timer'):
                self.timer.stop()
            
            # Close event loop
            if hasattr(self, 'loop') and self.loop:
                self.loop.close()
            
            logger.info("Application cleanup complete")
            
        except Exception as e:
            logger.error(f"Error during application cleanup: {e}")
    
    def event(self, event):
        """Handle application events."""
        # Handle macOS application events
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.ApplicationActivate:
            # Bring main window to front when app is activated
            if self.main_window:
                self.main_window.raise_()
                self.main_window.activateWindow()
        
        return super().event(event)


def main():
    """Main entry point for the MCP Manager GUI application."""
    try:
        # Set up environment
        os.environ.setdefault('QT_MAC_WANTS_LAYER', '1')  # Better macOS integration
        
        # Create application
        app = MCPManagerApp(sys.argv)
        
        # Setup signal handlers for graceful shutdown
        import signal
        
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down gracefully...")
            app.cleanup()
            app.quit()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Create and show main window
        app.create_main_window()
        
        # Run application event loop
        exit_code = app.exec()
        
        # Cleanup
        app.cleanup()
        
        logger.info(f"Application exited with code {exit_code}")
        return exit_code
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Fatal error in main application: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())