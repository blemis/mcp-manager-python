"""
MCP Suite Management System - Backwards Compatibility Layer.

This module provides backward compatibility by re-exporting the modular
suite management system. All new code should import directly from 
mcp_manager.core.suites instead of this module.
"""

from .suites import (
    Suite,
    SuiteMembership, 
    SuiteManager,
    suite_manager
)

# Re-export for backward compatibility
__all__ = [
    'Suite',
    'SuiteMembership',
    'SuiteManager', 
    'suite_manager'
]