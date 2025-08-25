"""
MCP Manager GUI - macOS native GUI for MCP server management.

This package provides a modern PySide6-based GUI for managing MCP servers,
built on top of the existing CLI functionality.
"""

__version__ = "1.0.0"
__author__ = "Claude & Human Collaboration"

from .main_app import MCPManagerApp, main

__all__ = ["MCPManagerApp", "main"]