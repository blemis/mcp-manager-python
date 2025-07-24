"""
Data models for the MCP Manager tool registry system.

Provides data classes for discovery results, search filters, and tool information
to support type-safe operations across the tool registry system.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from mcp_manager.core.models import ServerType, ToolRegistry


class ToolRegistryError(Exception):
    """Base exception for tool registry operations."""
    pass


class ToolNotFoundError(ToolRegistryError):
    """Raised when a requested tool is not found in the registry."""
    pass


class DiscoveryResult:
    """Result of a tool discovery operation."""
    
    def __init__(self, server_name: str, tools_discovered: int, 
                 duration_seconds: float, errors: List[str] = None):
        self.server_name = server_name
        self.tools_discovered = tools_discovered
        self.duration_seconds = duration_seconds
        self.errors = errors or []
        self.success = len(self.errors) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "server_name": self.server_name,
            "tools_discovered": self.tools_discovered,
            "duration_seconds": self.duration_seconds,
            "errors": self.errors,
            "success": self.success
        }


class SearchFilters:
    """Filters for tool search operations."""
    
    def __init__(self, server_name: Optional[str] = None,
                 server_type: Optional[ServerType] = None,
                 categories: Optional[List[str]] = None,
                 tags: Optional[List[str]] = None,
                 available_only: bool = True,
                 min_success_rate: Optional[float] = None):
        self.server_name = server_name
        self.server_type = server_type
        self.categories = categories or []
        self.tags = tags or []
        self.available_only = available_only
        self.min_success_rate = min_success_rate

    def has_filters(self) -> bool:
        """Check if any filters are set."""
        return bool(
            self.server_name or
            self.server_type or
            self.categories or
            self.tags or
            not self.available_only or
            self.min_success_rate is not None
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "server_name": self.server_name,
            "server_type": self.server_type.value if self.server_type else None,
            "categories": self.categories,
            "tags": self.tags,
            "available_only": self.available_only,
            "min_success_rate": self.min_success_rate
        }


class ToolInfo:
    """Comprehensive tool information for search results."""
    
    def __init__(self, registry_entry: ToolRegistry):
        self.canonical_name = registry_entry.canonical_name
        self.name = registry_entry.name
        self.description = registry_entry.description
        self.server_name = registry_entry.server_name
        self.server_type = registry_entry.server_type
        self.categories = registry_entry.categories
        self.tags = registry_entry.tags
        self.usage_count = registry_entry.usage_count
        self.success_rate = registry_entry.success_rate
        self.average_response_time = registry_entry.average_response_time
        self.last_discovered = registry_entry.last_discovered
        self.is_available = registry_entry.is_available
        self.input_schema = registry_entry.input_schema

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "canonical_name": self.canonical_name,
            "name": self.name,
            "description": self.description,
            "server_name": self.server_name,
            "server_type": self.server_type.value if hasattr(self.server_type, 'value') else str(self.server_type),
            "categories": self.categories,
            "tags": self.tags,
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "average_response_time": self.average_response_time,
            "last_discovered": self.last_discovered.isoformat() if self.last_discovered else None,
            "is_available": self.is_available,
            "input_schema": self.input_schema
        }

    def matches_categories(self, categories: List[str]) -> bool:
        """Check if tool matches any of the specified categories."""
        return any(cat in self.categories for cat in categories)

    def matches_tags(self, tags: List[str]) -> bool:
        """Check if tool matches any of the specified tags."""
        return any(tag in self.tags for tag in tags)

    def matches_query(self, query: str) -> bool:
        """Check if tool matches a text search query."""
        query_lower = query.lower()
        return (
            query_lower in self.name.lower() or
            query_lower in self.description.lower() or
            any(query_lower in cat.lower() for cat in self.categories) or
            any(query_lower in tag.lower() for tag in self.tags)
        )


class RegistryStats:
    """Statistics about the tool registry."""
    
    def __init__(self, total_tools: int, available_tools: int, 
                 servers_with_tools: int, server_type_distribution: Dict[str, int],
                 category_distribution: Dict[str, int], database_path: str):
        self.total_tools = total_tools
        self.available_tools = available_tools
        self.unavailable_tools = total_tools - available_tools
        self.servers_with_tools = servers_with_tools
        self.server_type_distribution = server_type_distribution
        self.category_distribution = category_distribution
        self.database_path = database_path
        self.last_updated = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_tools": self.total_tools,
            "available_tools": self.available_tools,
            "unavailable_tools": self.unavailable_tools,
            "servers_with_tools": self.servers_with_tools,
            "server_type_distribution": self.server_type_distribution,
            "category_distribution": self.category_distribution,
            "database_path": self.database_path,
            "last_updated": self.last_updated.isoformat()
        }