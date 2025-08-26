"""
MCP Manager Database Module

Provides async SQLite + WAL database access with modular architecture.
Includes hybrid server state management implementation.
"""

from .schema import MCPDatabaseSchema, initialize_mcp_database
from .connection import DatabaseConnection, get_database_connection
from .registry import MCPServerRegistry
from .suites import MCPSuiteManager
from .migrations import DatabaseMigrator

# Hybrid architecture components
from .server_state import MCPServerStateManager, ServerInfo, ServerStatus, ServerType
from .migration import run_migration, ServerStateMigration

__all__ = [
    'MCPDatabaseSchema',
    'initialize_mcp_database', 
    'DatabaseConnection',
    'get_database_connection',
    'MCPServerRegistry',
    'MCPSuiteManager',
    'DatabaseMigrator',
    # Hybrid architecture
    'MCPServerStateManager',
    'ServerInfo', 
    'ServerStatus',
    'ServerType',
    'run_migration',
    'ServerStateMigration'
]