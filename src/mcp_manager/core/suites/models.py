"""
Data models for MCP Suite Management System.

Provides dataclass models for Suite and SuiteMembership entities.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Any


@dataclass
class SuiteMembership:
    """Represents a server's membership in a suite."""
    suite_id: str
    server_name: str
    role: str  # 'primary', 'secondary', 'optional', 'member'
    priority: int  # 1-100, higher = more important
    config_overrides: Dict[str, Any]
    added_at: datetime


@dataclass
class Suite:
    """Represents an MCP server suite."""
    id: str
    name: str
    description: str
    category: str
    config: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    memberships: List[SuiteMembership]