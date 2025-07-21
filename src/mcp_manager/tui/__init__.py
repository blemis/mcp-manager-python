"""
TUI (Terminal User Interface) package for MCP Manager.

Provides interactive terminal interfaces using Rich for a better user experience.
"""

from mcp_manager.tui.rich_menu import main as rich_menu_main

__all__ = ["rich_menu_main"]