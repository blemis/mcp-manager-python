"""
CLI command modules for MCP Manager.
"""

from .discovery import discovery_commands
from .suite import suite_commands
from .ai import ai_commands  
from .analytics import analytics_commands
from .tools import tools_commands
from .system import system_commands
from .monitoring import monitoring_commands
from .ui import ui_commands

__all__ = [
    'discovery_commands',
    'suite_commands', 
    'ai_commands',
    'analytics_commands',
    'tools_commands',
    'system_commands',
    'monitoring_commands',
    'ui_commands'
]