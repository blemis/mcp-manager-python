"""
MCP Suite Management System.

Provides database-backed management of MCP server suites with
many-to-many relationships and metadata tracking.
"""

from .models import Suite, SuiteMembership
from .database import SuiteDatabase
from .crud_operations import SuiteCRUDOperations
from .membership import MembershipManager
from .suite_manager import SuiteManager, suite_manager

__all__ = [
    'Suite',
    'SuiteMembership', 
    'SuiteDatabase',
    'SuiteCRUDOperations',
    'MembershipManager',
    'SuiteManager',
    'suite_manager'
]