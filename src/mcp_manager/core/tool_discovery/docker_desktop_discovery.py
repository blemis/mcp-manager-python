"""
Docker Desktop MCP server tool discovery.

Discovers tools from Docker Desktop MCP servers via docker-gateway using the 
`docker mcp tools` API. Docker Desktop runs all MCP servers under docker-gateway
as a unified proxy, so we parse tools from the gateway's unified interface.
"""

import asyncio
import json
import subprocess
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from mcp_manager.core.models import ServerType
from mcp_manager.core.tool_discovery.base import BaseToolDiscovery, DiscoveryConfig, DiscoveryResult, ToolInfo
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class DockerDesktopToolDiscovery(BaseToolDiscovery):
    """
    Tool discovery service for Docker Desktop MCP servers.
    
    Architecture: Docker Desktop runs all MCP servers under docker-gateway.
    From Claude's perspective, docker-gateway is the single MCP server that 
    provides tools from multiple underlying servers (SQLite, GitHub, etc.).
    """
    
    def __init__(self, config: DiscoveryConfig):
        """Initialize Docker Desktop tool discovery service."""
        super().__init__(config)
        self._tool_cache: Optional[List[Dict]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = timedelta(minutes=5)  # 5-minute cache for performance
    
    def supports_server_type(self, server_type: ServerType) -> bool:
        """Check if this service supports the given server type."""
        return server_type == ServerType.DOCKER_DESKTOP
    
    async def discover_tools(self, server_name: str, **kwargs) -> DiscoveryResult:
        """
        Discover tools from Docker Desktop MCP servers via docker-gateway.
        
        Note: All Docker Desktop servers appear as docker-gateway to Claude Code,
        but internally they're composed of multiple underlying servers.
        
        Args:
            server_name: Name of the Docker Desktop server (usually 'docker-gateway')
            **kwargs: Additional arguments (command, args, env, working_dir)
            
        Returns:
            DiscoveryResult with tools from all enabled Docker Desktop servers
        """
        start_time = datetime.utcnow()
        
        try:
            logger.info(f"Discovering Docker Desktop tools for {server_name}")
            
            # Get all tools from Docker Desktop's unified interface
            all_tools_data = await self._get_docker_desktop_tools_cached()
            
            if not all_tools_data:
                logger.warning(f"No tools found for Docker Desktop server: {server_name}")
                return DiscoveryResult(
                    server_name=server_name,
                    server_type=ServerType.DOCKER_DESKTOP,
                    tools=[],
                    success=True,
                    discovery_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000)
                )
            
            # Convert raw tool data to ToolInfo objects
            tools = []
            server_tool_counts = {}
            
            for tool_data in all_tools_data:
                try:
                    tool_info = await self._parse_docker_tool(tool_data, server_name)
                    if tool_info:
                        tools.append(tool_info)
                        
                        # Track per-server tool counts (for logging)
                        source_server = self._infer_source_server(tool_data)
                        server_tool_counts[source_server] = server_tool_counts.get(source_server, 0) + 1
                        
                except Exception as e:
                    logger.warning(f"Failed to parse Docker tool {tool_data.get('name', 'unknown')}: {e}")
                    continue
            
            discovery_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            logger.info(f"Docker Desktop tool discovery completed for {server_name}", extra={
                "server_name": server_name,
                "total_tools": len(tools),
                "server_breakdown": server_tool_counts,
                "discovery_time_ms": discovery_time_ms
            })
            
            return DiscoveryResult(
                server_name=server_name,
                server_type=ServerType.DOCKER_DESKTOP,
                tools=tools,
                success=True,
                discovery_time_ms=discovery_time_ms
            )
            
        except Exception as e:
            discovery_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            logger.error(f"Docker Desktop tool discovery failed for {server_name}: {e}")
            
            return DiscoveryResult(
                server_name=server_name,
                server_type=ServerType.DOCKER_DESKTOP,
                success=False,
                error_message=str(e),
                discovery_time_ms=discovery_time_ms
            )
    
    async def _get_docker_desktop_tools_cached(self) -> List[Dict]:
        """
        Get Docker Desktop tools with caching for performance.
        
        Returns:
            List of tool data dictionaries from docker mcp tools API
        """
        # Check cache validity
        if (self._tool_cache is not None and 
            self._cache_timestamp is not None and 
            datetime.utcnow() - self._cache_timestamp < self._cache_ttl):
            logger.debug("Using cached Docker Desktop tools data")
            return self._tool_cache
        
        # Cache miss - fetch fresh data
        logger.debug("Fetching fresh Docker Desktop tools data")
        tools_data = await self._fetch_docker_tools()
        
        # Update cache
        self._tool_cache = tools_data
        self._cache_timestamp = datetime.utcnow()
        
        return tools_data
    
    async def _fetch_docker_tools(self) -> List[Dict]:
        """
        Fetch tools from Docker Desktop using docker mcp tools API.
        
        Returns:
            List of tool data dictionaries
        """
        try:
            # Find docker executable
            docker_path = shutil.which("docker")
            if not docker_path:
                # Fallback to common locations
                for path in ["/opt/homebrew/bin/docker", "/usr/local/bin/docker", "/usr/bin/docker"]:
                    if Path(path).exists():
                        docker_path = path
                        break
            
            if not docker_path:
                logger.error("Docker command not found - cannot discover Docker Desktop tools")
                return []
            
            # Execute docker mcp tools list command
            logger.debug("Executing: docker mcp tools list --verbose --format json")
            
            process = await asyncio.create_subprocess_exec(
                docker_path, "mcp", "tools", "list", "--verbose", "--format", "json",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60.0)
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"Docker MCP tools command failed: {error_msg}")
                return []
            
            # Parse JSON output
            try:
                tools_data = json.loads(stdout.decode())
                if not isinstance(tools_data, list):
                    logger.error(f"Unexpected Docker tools output format: {type(tools_data)}")
                    return []
                
                logger.debug(f"Successfully parsed {len(tools_data)} tools from Docker Desktop")
                return tools_data
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Docker tools JSON output: {e}")
                return []
                
        except asyncio.TimeoutError:
            logger.error("Docker MCP tools command timed out")
            return []
        except Exception as e:
            logger.error(f"Failed to fetch Docker Desktop tools: {e}")
            return []
    
    async def _parse_docker_tool(self, tool_data: Dict, server_name: str) -> Optional[ToolInfo]:
        """
        Parse a single tool from Docker MCP tools output into ToolInfo.
        
        Args:
            tool_data: Raw tool data from docker mcp tools command
            server_name: Name of the Docker Desktop server (docker-gateway)
            
        Returns:
            ToolInfo object or None if parsing fails
        """
        try:
            tool_name = tool_data.get("name")
            if not tool_name:
                logger.warning("Tool missing name field")
                return None
            
            # Extract basic tool information
            description = tool_data.get("description", f"Docker Desktop tool: {tool_name}")
            input_schema = tool_data.get("inputSchema", {})
            
            # Infer categories and tags from tool name and description
            categories = self._infer_tool_categories(tool_name, description)
            tags = self._infer_tool_tags(tool_name, description, input_schema)
            
            # Create canonical name (server_name/tool_name)
            canonical_name = f"{server_name}/{tool_name}"
            
            return ToolInfo(
                name=tool_name,
                canonical_name=canonical_name,
                description=description,
                server_name=server_name,
                server_type=ServerType.DOCKER_DESKTOP,
                input_schema=input_schema,
                output_schema=tool_data.get("outputSchema", {}),
                categories=categories,
                tags=tags,
                last_discovered=datetime.utcnow(),
                is_available=True,
                usage_count=0,
                success_rate=1.0,
                average_response_time=0.0
            )
            
        except Exception as e:
            logger.error(f"Failed to parse Docker tool {tool_data.get('name', 'unknown')}: {e}")
            return None
    
    def _infer_source_server(self, tool_data: Dict) -> str:
        """
        Infer which underlying server a tool comes from based on tool characteristics.
        
        Args:
            tool_data: Raw tool data
            
        Returns:
            Inferred source server name
        """
        tool_name = tool_data.get("name", "").lower()
        description = tool_data.get("description", "").lower()
        
        # GitHub tools
        if any(keyword in tool_name for keyword in ["github", "issue", "pull", "repo", "commit", "branch"]):
            return "github"
        
        # SQLite tools  
        if any(keyword in tool_name for keyword in ["sql", "query", "database", "table"]) or \
           any(keyword in description for keyword in ["sqlite", "database", "sql"]):
            return "sqlite"
        
        # AWS diagram tools
        if any(keyword in tool_name for keyword in ["diagram", "aws"]) or \
           "diagram" in description:
            return "aws-diagram"
        
        # Filesystem tools
        if any(keyword in tool_name for keyword in ["file", "dir", "read", "write", "list"]) or \
           "filesystem" in description:
            return "filesystem"
        
        return "unknown"
    
    def _infer_tool_categories(self, tool_name: str, description: str) -> List[str]:
        """
        Infer tool categories based on name and description.
        
        Args:
            tool_name: Tool name
            description: Tool description
            
        Returns:
            List of inferred categories
        """
        categories = []
        name_lower = tool_name.lower()
        desc_lower = description.lower()
        
        # GitHub/SCM categories
        if any(kw in name_lower for kw in ["github", "issue", "pull", "repo", "commit", "branch"]):
            categories.extend(["development", "scm", "github"])
        
        # Database categories
        if any(kw in name_lower for kw in ["sql", "query", "database", "table"]):
            categories.extend(["database", "data"])
        
        # Filesystem categories
        if any(kw in name_lower for kw in ["file", "dir", "read", "write", "list"]):
            categories.extend(["filesystem", "file-management"])
        
        # Diagram/visualization categories
        if any(kw in name_lower for kw in ["diagram", "chart", "visual"]):
            categories.extend(["visualization", "diagram"])
        
        # AWS categories
        if "aws" in name_lower or "aws" in desc_lower:
            categories.append("aws")
        
        # Default category if none found
        if not categories:
            categories.append("general")
        
        return list(set(categories))  # Remove duplicates
    
    def _infer_tool_tags(self, tool_name: str, description: str, input_schema: Dict) -> List[str]:
        """
        Infer tool tags based on name, description, and input schema.
        
        Args:
            tool_name: Tool name
            description: Tool description  
            input_schema: Tool input schema
            
        Returns:
            List of inferred tags
        """
        tags = ["docker-desktop"]
        name_lower = tool_name.lower()
        desc_lower = description.lower()
        
        # Add operation type tags
        if any(op in name_lower for op in ["create", "add", "make", "generate"]):
            tags.append("create")
        if any(op in name_lower for op in ["read", "get", "list", "fetch", "show"]):
            tags.append("read")
        if any(op in name_lower for op in ["update", "edit", "modify", "change"]):
            tags.append("update")
        if any(op in name_lower for op in ["delete", "remove", "drop"]):
            tags.append("delete")
        
        # Add parameter-based tags
        if input_schema and isinstance(input_schema, dict):
            properties = input_schema.get("properties", {})
            if "owner" in properties and "repo" in properties:
                tags.append("github-api")
            if any(param in properties for param in ["sql", "query", "table"]):
                tags.append("sql")
        
        return tags
    
    def invalidate_cache(self) -> None:
        """Invalidate the tool cache to force fresh discovery."""
        self._tool_cache = None
        self._cache_timestamp = None
        logger.debug("Docker Desktop tool cache invalidated")