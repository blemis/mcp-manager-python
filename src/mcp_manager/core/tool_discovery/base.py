"""
Base classes for tool discovery services.

Provides abstract interfaces and configuration for tool discovery implementations.
"""

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from mcp_manager.core.models import ServerType
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class DiscoveryConfig(BaseModel):
    """Configuration for tool discovery services."""
    
    timeout_seconds: int = Field(
        default_factory=lambda: int(os.getenv("MCP_DISCOVERY_TIMEOUT", "30")),
        description="Discovery timeout in seconds"
    )
    retry_attempts: int = Field(
        default_factory=lambda: int(os.getenv("MCP_DISCOVERY_RETRIES", "3")),
        description="Number of retry attempts"
    )
    cache_ttl_hours: int = Field(
        default_factory=lambda: int(os.getenv("MCP_CACHE_TTL_HOURS", "24")),
        description="Cache TTL in hours"
    )
    max_concurrent: int = Field(
        default_factory=lambda: int(os.getenv("MCP_MAX_CONCURRENT", "5")),
        description="Maximum concurrent discoveries"
    )
    enable_caching: bool = Field(
        default_factory=lambda: os.getenv("MCP_ENABLE_DISCOVERY_CACHE", "true").lower() == "true",
        description="Enable discovery result caching"
    )


class ToolInfo(BaseModel):
    """Information about a discovered tool."""
    
    name: str = Field(description="Tool name")
    canonical_name: str = Field(description="Canonical name (server/tool)")
    description: str = Field(default="", description="Tool description")
    server_name: str = Field(description="Source server name")
    server_type: ServerType = Field(description="Server type")
    input_schema: Dict[str, Any] = Field(default_factory=dict, description="Input schema")
    output_schema: Dict[str, Any] = Field(default_factory=dict, description="Output schema")
    categories: List[str] = Field(default_factory=list, description="Tool categories")
    tags: List[str] = Field(default_factory=list, description="Tool tags")
    is_available: bool = Field(default=True, description="Whether tool is currently available")


class DiscoveryResult(BaseModel):
    """Result of a tool discovery operation."""
    
    server_name: str = Field(description="Server name")
    server_type: ServerType = Field(description="Server type")
    tools: List[ToolInfo] = Field(default_factory=list, description="Discovered tools")
    success: bool = Field(description="Whether discovery was successful")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    discovery_time_ms: int = Field(default=0, description="Discovery time in milliseconds")


class BaseToolDiscovery(ABC):
    """Abstract base class for tool discovery services."""
    
    def __init__(self, config: DiscoveryConfig):
        """
        Initialize tool discovery service.
        
        Args:
            config: Discovery configuration
        """
        self.config = config
        self.logger = get_logger(self.__class__.__name__)
    
    @abstractmethod
    async def discover_tools(self, server_name: str, **kwargs) -> DiscoveryResult:
        """
        Discover tools from a specific server.
        
        Args:
            server_name: Name of the server to discover tools from
            **kwargs: Additional server-specific parameters
            
        Returns:
            DiscoveryResult with found tools and metadata
        """
        pass
    
    @abstractmethod
    def supports_server_type(self, server_type: ServerType) -> bool:
        """
        Check if this discovery service supports the given server type.
        
        Args:
            server_type: Server type to check
            
        Returns:
            True if server type is supported
        """
        pass
    
    def _categorize_tool(self, tool_name: str, description: str, schema: Dict[str, Any]) -> List[str]:
        """
        Categorize a tool based on its name, description, and schema.
        
        Args:
            tool_name: Tool name
            description: Tool description
            schema: Tool input schema
            
        Returns:
            List of categories
        """
        categories = []
        
        # Category inference based on tool name and description
        name_desc = f"{tool_name} {description}".lower()
        
        if any(word in name_desc for word in ["file", "directory", "folder", "path", "read", "write"]):
            categories.append("filesystem")
        
        if any(word in name_desc for word in ["search", "find", "query", "lookup"]):
            categories.append("search")
        
        if any(word in name_desc for word in ["database", "sql", "table", "record"]):
            categories.append("database")
        
        if any(word in name_desc for word in ["web", "http", "api", "request", "url"]):
            categories.append("web")
        
        if any(word in name_desc for word in ["git", "github", "repository", "commit"]):
            categories.append("development")
        
        if any(word in name_desc for word in ["automate", "script", "run", "execute"]):
            categories.append("automation")
        
        # Default category if none found
        if not categories:
            categories.append("general")
        
        return categories
    
    def _extract_tags(self, tool_name: str, description: str, schema: Dict[str, Any]) -> List[str]:
        """
        Extract tags from tool information.
        
        Args:
            tool_name: Tool name
            description: Tool description
            schema: Tool input schema
            
        Returns:
            List of tags
        """
        tags = []
        
        # Extract tags from tool name
        name_parts = tool_name.replace("_", " ").replace("-", " ").split()
        tags.extend([part.lower() for part in name_parts if len(part) > 2])
        
        # Extract operation type tags
        desc_lower = description.lower()
        if any(word in desc_lower for word in ["read", "get", "fetch", "load"]):
            tags.append("read")
        if any(word in desc_lower for word in ["write", "create", "save", "store"]):
            tags.append("write")
        if any(word in desc_lower for word in ["update", "modify", "change", "edit"]):
            tags.append("update")
        if any(word in desc_lower for word in ["delete", "remove", "destroy"]):
            tags.append("delete")
        
        # Remove duplicates and return
        return list(set(tags))