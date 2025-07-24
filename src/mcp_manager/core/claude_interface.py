"""
Legacy interface to Claude Code's native MCP management.

DEPRECATED: This module has been refactored into focused modules under
mcp_manager.claude. Import ClaudeInterface from there instead.

This module now serves as a compatibility layer.
"""

import warnings
from mcp_manager.claude import ClaudeInterface as NewClaudeInterface
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)

# Issue deprecation warning
warnings.warn(
    "mcp_manager.core.claude_interface is deprecated. "
    "Use mcp_manager.claude.ClaudeInterface instead.",
    DeprecationWarning,
    stacklevel=2
)


class ClaudeInterface(NewClaudeInterface):
    """Legacy Claude interface - redirects to new modular implementation."""
    
    def __init__(self, *args, **kwargs):
        """Initialize with deprecation warning."""
        logger.warning(
            "Using deprecated claude_interface. "
            "Please update imports to use mcp_manager.claude.ClaudeInterface"
        )
        super().__init__(*args, **kwargs)


