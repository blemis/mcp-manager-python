"""
Discovery Manager for tool discovery operations.

Handles all aspects of tool discovery including MCP protocol communication,
Docker Desktop integration, NPM package analysis, and AI-powered recommendations.
"""

import asyncio
import json
import os
import subprocess
import tempfile
from typing import List, Optional, Dict, Any, Tuple

from mcp_manager.core.models import Server, ServerType
from mcp_manager.core.tool_discovery import ToolDiscoveryAggregator
from mcp_manager.core.tool_registry import ToolRegistryService
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class DiscoveryManager:
    """Manages tool discovery operations across different server types."""
    
    def __init__(self):
        """Initialize discovery manager with lazy loading."""
        self._tool_registry = None
        self._tool_discovery = None
        self.auto_discover_tools = os.getenv("MCP_AUTO_DISCOVER_TOOLS", "true").lower() == "true"
        self.background_discovery = os.getenv("MCP_BACKGROUND_DISCOVERY", "false").lower() == "true"
        logger.debug("DiscoveryManager initialized (services will be loaded on demand)")
    
    @property
    def tool_registry(self) -> ToolRegistryService:
        """Get tool registry service (lazy loading)."""
        if self._tool_registry is None:
            self._tool_registry = ToolRegistryService()
            logger.debug("ToolRegistryService initialized")
        return self._tool_registry
    
    @property
    def tool_discovery(self) -> ToolDiscoveryAggregator:
        """Get tool discovery aggregator (lazy loading)."""
        if self._tool_discovery is None:
            self._tool_discovery = ToolDiscoveryAggregator()
            logger.debug("ToolDiscoveryAggregator initialized")
        return self._tool_discovery
    
    async def discover_and_register_server_tools(self, server: Server) -> int:
        """
        Discover and register tools from a server in the tool registry.
        
        Args:
            server: Server to discover tools from
            
        Returns:
            Number of tools discovered and registered
        """
        try:
            logger.debug(f"Discovering tools for server: {server.name}")
            
            # Use the tool discovery aggregator to find tools
            result = await self.tool_discovery.discover_from_server(server)
            
            if result.success and result.tools:
                # Register discovered tools in the registry
                registered_count = 0
                for tool in result.tools:
                    # Convert ToolInfo to ToolRegistry model
                    from mcp_manager.core.models import ToolRegistry
                    from datetime import datetime
                    
                    tool_registry = ToolRegistry(
                        id=0,  # Will be set by database
                        name=tool.name,
                        canonical_name=tool.canonical_name,
                        description=tool.description,
                        server_name=tool.server_name,
                        server_type=tool.server_type,
                        input_schema=tool.input_schema,
                        output_schema=tool.output_schema,
                        categories=tool.categories,
                        tags=tool.tags,
                        last_discovered=tool.last_discovered,
                        is_available=tool.is_available,
                        usage_count=tool.usage_count,
                        success_rate=tool.success_rate,
                        average_response_time=tool.average_response_time,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                        discovered_by="mcp-manager-discovery"
                    )
                    
                    if self.tool_registry.register_tool(tool_registry):
                        registered_count += 1
                    else:
                        logger.warning(f"Failed to register tool {tool.canonical_name}")
                
                logger.info(f"Discovered {len(result.tools)} tools and registered {registered_count} for {server.name}")
                return registered_count
            else:
                if result.error_message:
                    logger.warning(f"Tool discovery failed for {server.name}: {result.error_message}")
                return 0
                
        except Exception as e:
            logger.error(f"Failed to discover tools for {server.name}: {e}")
            return 0
    
    async def discover_all_tools(self, servers: List[Server]) -> Dict[str, int]:
        """
        Discover and register tools from all enabled servers.
        
        Args:
            servers: List of servers to discover tools from
            
        Returns:
            Dictionary mapping server names to tool counts
        """
        if not self.auto_discover_tools:
            logger.debug("Auto tool discovery is disabled")
            return {}
        
        logger.info(f"Starting tool discovery for {len(servers)} servers")
        
        # Discover tools from all servers
        tool_counts = {}
        for server in servers:
            if server.enabled:
                count = await self.discover_and_register_server_tools(server)
                tool_counts[server.name] = count
        
        total_tools = sum(tool_counts.values())
        logger.info(f"Tool discovery completed. Discovered {total_tools} tools across {len(servers)} servers")
        
        return tool_counts
    
    def get_tool_registry_stats(self) -> Dict[str, Any]:
        """
        Get tool registry statistics.
        
        Returns:
            Dictionary with registry statistics
        """
        try:
            return self.tool_registry.get_stats()
        except Exception as e:
            logger.error(f"Failed to get tool registry stats: {e}")
            return {}
    
    def search_tools(self, query: Optional[str] = None, 
                    server_name: Optional[str] = None,
                    category: Optional[str] = None,
                    limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search for tools in the registry.
        
        Args:
            query: Search query for tool names/descriptions
            server_name: Filter by server name
            category: Filter by category
            limit: Maximum number of results
            
        Returns:
            List of matching tools
        """
        try:
            # Use the tool registry service for searching with correct signature
            from mcp_manager.core.tool_registry import SearchFilters
            
            filters = SearchFilters()
            if server_name:
                filters.server_name = server_name
            if category:
                filters.categories = [category]
                
            results = self.tool_registry.search_tools(query or "", filters, limit)
            
            # Convert ToolInfo results to dictionaries 
            return [
                {
                    "name": tool.name,
                    "canonical_name": tool.canonical_name,  
                    "description": tool.description,
                    "server_name": tool.server_name,
                    "server_type": tool.server_type.value if hasattr(tool.server_type, 'value') else str(tool.server_type),
                    "categories": tool.categories,
                    "tags": tool.tags,
                    "is_available": tool.is_available,
                    "usage_count": tool.usage_count
                }
                for tool in results
            ]
            
        except Exception as e:
            logger.error(f"Failed to search tools: {e}")
            return []
    
    async def get_docker_desktop_server_tools(self, server_name: str) -> Tuple[int, Dict[str, Any]]:
        """
        Get tool info for Docker Desktop MCP servers.
        
        Args:
            server_name: Name of the Docker Desktop server
            
        Returns:
            Tuple of (tool_count, tool_info_dict)
        """
        try:
            logger.debug(f"Getting Docker Desktop tools for server: {server_name}")
            
            # Use docker mcp tools command to get tool information
            result = subprocess.run(
                ["docker", "mcp", "tools", server_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.warning(f"Failed to get Docker Desktop tools for {server_name}: {result.stderr}")
                return 0, {}
            
            # Parse the output to extract tool information
            tools_info = {}
            tool_count = 0
            
            # Simple parsing - in practice you'd want more robust parsing
            lines = result.stdout.strip().split('\n')
            for line in lines:
                if line.strip():
                    tool_count += 1
                    # Store basic tool info - could be enhanced with more detailed parsing
                    tools_info[f"tool_{tool_count}"] = {
                        "name": line.strip(),
                        "server": server_name,
                        "type": "docker_desktop"
                    }
            
            logger.debug(f"Found {tool_count} tools for Docker Desktop server {server_name}")
            return tool_count, tools_info
            
        except Exception as e:
            logger.error(f"Failed to get Docker Desktop tools for {server_name}: {e}")
            return 0, {}
    
    async def get_all_docker_tools(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all tools mapped by server using Docker Desktop's tools command.
        
        Returns:
            Dictionary mapping server names to their tools
        """
        try:
            logger.debug("Getting all Docker Desktop tools")
            
            # Use docker mcp tools list command
            result = subprocess.run(
                ["docker", "mcp", "tools", "list", "--verbose", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                logger.warning(f"Failed to get all Docker tools: {result.stderr}")
                return {}
            
            # Parse JSON output
            try:
                tools_data = json.loads(result.stdout)
                logger.debug(f"Successfully retrieved Docker tools data")
                return tools_data
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Docker tools JSON: {e}")
                return {}
                
        except Exception as e:
            logger.error(f"Failed to get all Docker tools: {e}")
            return {}
    
    async def discover_mcp_tools_via_stdio(self, server: Server) -> List[Dict[str, Any]]:
        """
        Discover tools by communicating with server via stdio using MCP protocol.
        
        Args:
            server: Server to discover tools from
            
        Returns:
            List of discovered tools
        """
        try:
            logger.debug(f"Discovering tools via MCP protocol for {server.name}")
            
            # Create temporary file for MCP communication
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                # Send initialize request
                init_request = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {}
                        },
                        "clientInfo": {
                            "name": "mcp-manager",
                            "version": "1.0.0"
                        }
                    }
                }
                
                json.dump(init_request, f)
                f.flush()
                
                # Run the server command with the request
                proc = subprocess.Popen(
                    [server.command] + server.args,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=dict(os.environ, **(server.env or {})),
                    cwd=server.working_dir
                )
                
                # Send the request and get response
                stdout, stderr = proc.communicate(
                    input=json.dumps(init_request) + '\n' + 
                          json.dumps({
                              "jsonrpc": "2.0",
                              "id": 2,
                              "method": "tools/list"
                          }) + '\n',
                    timeout=30
                )
                
                # Parse responses
                tools = []
                for line in stdout.strip().split('\n'):
                    if line.strip():
                        try:
                            response = json.loads(line)
                            if response.get("method") == "tools/list" and "result" in response:
                                tools.extend(response["result"].get("tools", []))
                        except json.JSONDecodeError:
                            continue
                
                logger.debug(f"Discovered {len(tools)} tools via MCP protocol for {server.name}")
                return tools
                
        except Exception as e:
            logger.error(f"Failed to discover tools via MCP protocol for {server.name}: {e}")
            return []
    
    def predict_tools_from_package_name(self, package_name: str) -> List[Dict[str, Any]]:
        """
        Predict likely tools based on NPM package name patterns.
        
        Args:
            package_name: NPM package name
            
        Returns:
            List of predicted tools
        """
        tools = []
        
        # Common patterns for MCP servers
        if "filesystem" in package_name.lower():
            tools.append({
                "name": "read_file",
                "description": "Read file contents",
                "predicted": True
            })
            tools.append({
                "name": "write_file", 
                "description": "Write file contents",
                "predicted": True
            })
            tools.append({
                "name": "list_directory",
                "description": "List directory contents", 
                "predicted": True
            })
        
        if "sqlite" in package_name.lower() or "database" in package_name.lower():
            tools.append({
                "name": "execute_query",
                "description": "Execute SQL query",
                "predicted": True
            })
            tools.append({
                "name": "list_tables",
                "description": "List database tables",
                "predicted": True
            })
        
        if "search" in package_name.lower():
            tools.append({
                "name": "search",
                "description": "Search for information",
                "predicted": True
            })
        
        if "web" in package_name.lower() or "http" in package_name.lower():
            tools.append({
                "name": "fetch_url",
                "description": "Fetch web content",
                "predicted": True
            })
        
        logger.debug(f"Predicted {len(tools)} tools for package {package_name}")
        return tools
    
    def predict_docker_tools_from_image_name(self, image_name: str) -> List[Dict[str, Any]]:
        """
        Predict likely tools based on Docker image name patterns.
        
        Args:
            image_name: Docker image name
            
        Returns:
            List of predicted tools
        """
        tools = []
        image_lower = image_name.lower()
        
        # Common MCP server patterns
        if "filesystem" in image_lower:
            tools.extend([
                {"name": "read_file", "description": "Read file contents", "predicted": True},
                {"name": "write_file", "description": "Write file contents", "predicted": True},
                {"name": "list_directory", "description": "List directory contents", "predicted": True}
            ])
        
        if "sqlite" in image_lower or "database" in image_lower:
            tools.extend([
                {"name": "execute_query", "description": "Execute SQL query", "predicted": True},
                {"name": "list_tables", "description": "List database tables", "predicted": True}
            ])
        
        if "search" in image_lower:
            tools.append({
                "name": "search",
                "description": "Search for information", 
                "predicted": True
            })
        
        if "web" in image_lower or "http" in image_lower:
            tools.append({
                "name": "fetch_url",
                "description": "Fetch web content",
                "predicted": True
            })
        
        logger.debug(f"Predicted {len(tools)} tools for Docker image {image_name}")
        return tools