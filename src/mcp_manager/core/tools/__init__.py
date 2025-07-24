"""
MCP Manager tool registry system.

A modular system for managing, discovering, and searching MCP tools with
database persistence, advanced filtering, and usage analytics.

This module provides a clean public interface to the tool registry system
while maintaining internal modularity and separation of concerns.
"""

# Main orchestration service - primary interface
from .tool_registry import ToolRegistryService

# Data models for type safety and structured operations
from .models import (
    DiscoveryResult,
    RegistryStats,
    SearchFilters,
    ToolInfo,
    ToolNotFoundError,
    ToolRegistryError,
)

# Individual services for advanced use cases
from .database_manager import DatabaseManager
from .registration import ToolRegistrationService
from .search_service import ToolSearchService

__all__ = [
    # Main service interface
    "ToolRegistryService",
    
    # Data models and exceptions
    "DiscoveryResult",
    "RegistryStats", 
    "SearchFilters",
    "ToolInfo",
    "ToolNotFoundError",
    "ToolRegistryError",
    
    # Individual service components
    "DatabaseManager",
    "ToolRegistrationService", 
    "ToolSearchService",
]

# Version information
__version__ = "1.0.0"
__author__ = "MCP Manager"
__description__ = "Modular tool registry system for MCP Manager"