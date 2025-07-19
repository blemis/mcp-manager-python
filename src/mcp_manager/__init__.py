"""
MCP Manager - Enterprise-grade MCP server management tool.

A comprehensive tool for managing MCP (Model Context Protocol) servers
with modern TUI and CLI interfaces.
"""

__version__ = "1.0.0"
__author__ = "Claude & Human Collaboration"
__email__ = "noreply@anthropic.com"
__description__ = "Enterprise-grade MCP server management tool"

# Public API
from mcp_manager.core.exceptions import MCPManagerError
from mcp_manager.core.models import Server, ServerScope, ServerStatus

__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "__description__",
    "MCPManagerError",
    "Server",
    "ServerScope", 
    "ServerStatus",
]