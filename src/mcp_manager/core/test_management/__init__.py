"""
Test Management Module for MCP Manager.

Dynamic test category and suite management system with AI-ready architecture.
"""

from .category_manager import TestCategoryManager
from .database import TestManagementDB
from .models import TestCategory, TestSuiteMapping, TestScope

__all__ = [
    'TestCategoryManager',
    'TestManagementDB',
    'TestCategory',
    'TestSuiteMapping', 
    'TestScope'
]