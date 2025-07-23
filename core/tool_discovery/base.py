"""
Base abstract interface for tool discovery services.

Defines the common interface and configuration for all tool discovery
implementations across different server types.
"""

import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from mcp_manager.core.models import Server, ServerType, ToolRegistry
from mcp_manager.core.tool_discovery_logger import ToolDiscoveryLogger


class DiscoveryConfig(BaseModel):
    """Configuration for tool discovery operations."""
    
    timeout_seconds: int = Field(
        default_factory=lambda: int(os.getenv("MCP_DISCOVERY_TIMEOUT", "30")),
        description="Timeout for discovery operations"
    )
    max_retries: int = Field(
        default_factory=lambda: int(os.getenv("MCP_DISCOVERY_RETRIES", "3")),
        description="Maximum number of retry attempts"
    )
    parallel_discovery: bool = Field(
        default_factory=lambda: os.getenv("MCP_PARALLEL_DISCOVERY", "true").lower() == "true",
        description="Enable parallel tool discovery"
    )
    cache_results: bool = Field(
        default_factory=lambda: os.getenv("MCP_CACHE_DISCOVERY", "true").lower() == "true",
        description="Cache discovery results"
    )
    include_schema_validation: bool = Field(
        default_factory=lambda: os.getenv("MCP_VALIDATE_SCHEMAS", "true").lower() == "true",
        description="Validate tool schemas during discovery"
    )


class ToolDiscoveryResult(BaseModel):
    """Result of a tool discovery operation."""
    
    server_name: str = Field(description="Name of the server")
    server_type: ServerType = Field(description="Type of server")
    tools_discovered: List[ToolRegistry] = Field(default_factory=list, description="Discovered tools")
    discovery_duration_seconds: float = Field(description="Time taken for discovery")
    success: bool = Field(description="Whether discovery was successful")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")
    warnings: List[str] = Field(default_factory=list, description="Any warnings generated")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional discovery metadata")
    
    @property
    def tool_count(self) -> int:
        """Number of tools discovered."""
        return len(self.tools_discovered)
    
    @property
    def has_errors(self) -> bool:
        """Whether any errors occurred during discovery."""
        return len(self.errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        """Whether any warnings were generated."""
        return len(self.warnings) > 0


class BaseToolDiscovery(ABC):
    """Abstract base class for tool discovery services."""
    
    def __init__(self, config: Optional[DiscoveryConfig] = None):
        """
        Initialize tool discovery service.
        
        Args:
            config: Discovery configuration. If None, uses defaults from environment.
        """
        self.config = config or DiscoveryConfig()
        self.logger = ToolDiscoveryLogger(self.__class__.__name__)
        
        # Track discovery operations for performance monitoring
        self._active_operations: Dict[str, datetime] = {}
    
    @abstractmethod
    async def discover_tools(self, server: Server) -> ToolDiscoveryResult:
        """
        Discover tools from the given server.
        
        Args:
            server: Server configuration to discover tools from
            
        Returns:
            ToolDiscoveryResult with discovered tools and metadata
        """
        pass
    
    @abstractmethod
    def can_handle_server(self, server: Server) -> bool:
        """
        Check if this discovery service can handle the given server type.
        
        Args:
            server: Server to check
            
        Returns:
            True if this service can discover tools from this server
        """
        pass
    
    @abstractmethod
    async def validate_server_connection(self, server: Server) -> bool:
        """
        Validate that the server is reachable and responding.
        
        Args:
            server: Server to validate
            
        Returns:
            True if server is accessible, False otherwise
        """
        pass
    
    def create_tool_registry_entry(self, server: Server, tool_name: str,
                                 tool_description: str, tool_schema: Dict[str, Any],
                                 categories: Optional[List[str]] = None,
                                 tags: Optional[List[str]] = None) -> ToolRegistry:
        """
        Create a ToolRegistry entry from discovered tool information.
        
        Args:
            server: Server providing the tool
            tool_name: Name of the tool
            tool_description: Tool description
            tool_schema: Tool input/output schema
            categories: Optional tool categories
            tags: Optional tool tags
            
        Returns:
            ToolRegistry entry for the discovered tool
        """
        canonical_name = f"{server.name}/{tool_name}"
        
        # Extract input and output schemas
        input_schema = tool_schema.get("inputSchema", tool_schema.get("input_schema", {}))
        output_schema = tool_schema.get("outputSchema", tool_schema.get("output_schema", {}))
        
        # Generate categories and tags if not provided
        if categories is None:
            categories = self._infer_categories(tool_name, tool_description, input_schema)
        
        if tags is None:
            tags = self._infer_tags(tool_name, tool_description, input_schema)
        
        return ToolRegistry(
            name=tool_name,
            canonical_name=canonical_name,
            description=tool_description,
            server_name=server.name,
            server_type=server.server_type,
            input_schema=input_schema,
            output_schema=output_schema,
            categories=categories,
            tags=tags,
            last_discovered=datetime.utcnow(),
            is_available=True,
            usage_count=0,
            success_rate=0.0,
            average_response_time=0.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            discovered_by=f"{self.__class__.__name__}_v1.0"
        )
    
    def _infer_categories(self, tool_name: str, description: str, schema: Dict[str, Any]) -> List[str]:
        """
        Infer tool categories from name, description, and schema.
        
        Args:
            tool_name: Name of the tool
            description: Tool description
            schema: Tool schema
            
        Returns:
            List of inferred categories
        """
        categories = []
        
        # Combine text for analysis
        text = f"{tool_name} {description}".lower()
        
        # Category mapping based on keywords
        category_keywords = {
            "filesystem": ["file", "directory", "folder", "path", "read", "write", "create", "delete"],
            "web": ["http", "url", "web", "api", "request", "response", "browser"],
            "database": ["database", "db", "sql", "query", "table", "record"],
            "automation": ["automate", "script", "execute", "run", "process"],
            "search": ["search", "find", "query", "index", "lookup"],
            "notification": ["notify", "alert", "message", "send", "email"],
            "development": ["git", "github", "repo", "commit", "branch", "code"],
            "system": ["system", "process", "service", "monitor", "status"],
            "data": ["data", "json", "csv", "parse", "format", "convert"],
            "communication": ["chat", "message", "communication", "send", "receive"]
        }
        
        for category, keywords in category_keywords.items():
            if any(keyword in text for keyword in keywords):
                categories.append(category)
        
        # Analyze schema for additional clues
        if schema and "properties" in schema:
            properties = schema["properties"]
            if any("file" in prop.lower() for prop in properties.keys()):
                if "filesystem" not in categories:
                    categories.append("filesystem")
            if any("url" in prop.lower() for prop in properties.keys()):
                if "web" not in categories:
                    categories.append("web")
        
        return categories[:5]  # Limit to 5 categories max
    
    def _infer_tags(self, tool_name: str, description: str, schema: Dict[str, Any]) -> List[str]:
        """
        Infer tool tags from name, description, and schema.
        
        Args:
            tool_name: Name of the tool  
            description: Tool description
            schema: Tool schema
            
        Returns:
            List of inferred tags
        """
        tags = []
        
        # Extract action words from tool name
        name_parts = tool_name.lower().replace("_", " ").replace("-", " ").split()
        action_words = ["read", "write", "create", "delete", "update", "get", "set", "list", 
                       "search", "find", "execute", "run", "start", "stop", "send", "receive"]
        
        for part in name_parts:
            if part in action_words:
                tags.append(part)
        
        # Extract object types
        object_words = ["file", "directory", "user", "message", "data", "record", "item"]
        for part in name_parts:
            if part in object_words:
                tags.append(part)
        
        # Add complexity tags based on parameter count
        if schema and "properties" in schema:
            param_count = len(schema["properties"])
            if param_count == 0:
                tags.append("simple")
            elif param_count <= 3:
                tags.append("moderate")
            else:
                tags.append("complex")
        
        return list(set(tags))  # Remove duplicates
    
    def _validate_tool_schema(self, tool_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and normalize tool schema.
        
        Args:
            tool_schema: Raw tool schema from server
            
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "normalized_schema": tool_schema
        }
        
        # Check for required fields
        if not isinstance(tool_schema, dict):
            validation_result["valid"] = False
            validation_result["errors"].append("Schema must be a dictionary")
            return validation_result
        
        # Normalize schema structure
        normalized = {}
        
        # Handle different schema formats
        if "inputSchema" in tool_schema:
            normalized["inputSchema"] = tool_schema["inputSchema"]
        elif "input_schema" in tool_schema:
            normalized["inputSchema"] = tool_schema["input_schema"]
        elif "properties" in tool_schema:
            normalized["inputSchema"] = tool_schema
        
        if "outputSchema" in tool_schema:
            normalized["outputSchema"] = tool_schema["outputSchema"]
        elif "output_schema" in tool_schema:
            normalized["outputSchema"] = tool_schema["output_schema"]
        
        # Copy other fields
        for key, value in tool_schema.items():
            if key not in ["inputSchema", "input_schema", "outputSchema", "output_schema"]:
                normalized[key] = value
        
        validation_result["normalized_schema"] = normalized
        
        # Validate input schema structure
        input_schema = normalized.get("inputSchema", {})
        if input_schema and "properties" in input_schema:
            properties = input_schema["properties"]
            if not isinstance(properties, dict):
                validation_result["errors"].append("Input schema properties must be a dictionary")
                validation_result["valid"] = False
        
        return validation_result