"""
Tool discovery aggregator for orchestrating discovery across multiple server types.

Manages parallel and sequential discovery operations with conflict detection and resolution.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Set

from mcp_manager.core.models import Server, ServerType
from mcp_manager.core.tool_discovery.base import BaseToolDiscovery, DiscoveryConfig, DiscoveryResult, ToolInfo
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ConflictInfo:
    """Information about tool name conflicts."""
    
    def __init__(self, tool_name: str, servers: List[str]):
        self.tool_name = tool_name
        self.servers = servers
        self.canonical_names = [f"{server}/{tool_name}" for server in servers]


class ToolDiscoveryAggregator:
    """Aggregates tool discovery from multiple sources and server types."""
    
    def __init__(self, config: Optional[DiscoveryConfig] = None):
        """
        Initialize discovery aggregator.
        
        Args:
            config: Discovery configuration
        """
        self.config = config or DiscoveryConfig()
        self.logger = get_logger(__name__)
        self.discovery_services: Dict[ServerType, BaseToolDiscovery] = {}
        
        # Initialize discovery services for different server types
        self._initialize_discovery_services()
    
    def _initialize_discovery_services(self) -> None:
        """Initialize discovery services for supported server types."""
        try:
            # Import and initialize discovery services
            # Note: These imports are conditional to avoid circular dependencies
            
            # NPM discovery service
            try:
                from .npm_discovery import NPMToolDiscovery
                self.discovery_services[ServerType.NPM] = NPMToolDiscovery(self.config)
                logger.debug("Initialized NPM tool discovery service")
            except ImportError as e:
                logger.warning(f"NPM discovery service not available: {e}")
            
            # Docker discovery service
            try:
                from .docker_discovery import DockerToolDiscovery
                self.discovery_services[ServerType.DOCKER] = DockerToolDiscovery(self.config)
                logger.debug("Initialized Docker tool discovery service")
            except ImportError as e:
                logger.warning(f"Docker discovery service not available: {e}")
            
            # Docker Desktop discovery service
            try:
                from .docker_desktop_discovery import DockerDesktopToolDiscovery
                self.discovery_services[ServerType.DOCKER_DESKTOP] = DockerDesktopToolDiscovery(self.config)
                logger.debug("Initialized Docker Desktop tool discovery service")
            except ImportError as e:
                logger.warning(f"Docker Desktop discovery service not available: {e}")
            
            logger.info(f"Initialized {len(self.discovery_services)} discovery services")
            
        except Exception as e:
            logger.error(f"Failed to initialize discovery services: {e}")
    
    async def discover_all_tools(self, servers: List[Server], 
                                parallel: bool = True) -> Dict[str, DiscoveryResult]:
        """
        Discover tools from all provided servers.
        
        Args:
            servers: List of servers to discover tools from
            parallel: Whether to run discoveries in parallel
            
        Returns:
            Dictionary mapping server names to discovery results
        """
        start_time = datetime.utcnow()
        
        logger.info(f"Starting tool discovery for {len(servers)} servers", extra={
            "server_count": len(servers),
            "parallel": parallel,
            "discovery_services": len(self.discovery_services)
        })
        
        results = {}
        
        if parallel:
            results = await self._discover_parallel(servers)
        else:
            results = await self._discover_sequential(servers)
        
        # Calculate overall statistics
        total_tools = sum(len(result.tools) for result in results.values())
        successful_discoveries = sum(1 for result in results.values() if result.success)
        discovery_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        logger.info("Tool discovery completed", extra={
            "total_servers": len(servers),
            "successful_discoveries": successful_discoveries,
            "total_tools_found": total_tools,
            "discovery_time_ms": discovery_time_ms
        })
        
        return results
    
    async def _discover_parallel(self, servers: List[Server]) -> Dict[str, DiscoveryResult]:
        """Discover tools from servers in parallel."""
        # Create semaphore to limit concurrent discoveries
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        async def discover_with_semaphore(server: Server) -> tuple[str, DiscoveryResult]:
            async with semaphore:
                return server.name, await self._discover_server_tools(server)
        
        # Execute all discoveries concurrently
        tasks = [discover_with_semaphore(server) for server in servers]
        completed_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle exceptions
        results = {}
        for result in completed_results:
            if isinstance(result, Exception):
                logger.error(f"Discovery task failed: {result}")
                continue
            
            server_name, discovery_result = result
            results[server_name] = discovery_result
        
        return results
    
    async def _discover_sequential(self, servers: List[Server]) -> Dict[str, DiscoveryResult]:
        """Discover tools from servers sequentially."""
        results = {}
        
        for server in servers:
            try:
                result = await self._discover_server_tools(server)
                results[server.name] = result
            except Exception as e:
                logger.error(f"Discovery failed for server {server.name}: {e}")
                results[server.name] = DiscoveryResult(
                    server_name=server.name,
                    server_type=server.server_type,
                    success=False,
                    error_message=str(e)
                )
        
        return results
    
    async def _discover_server_tools(self, server: Server) -> DiscoveryResult:
        """
        Discover tools from a single server.
        
        Args:
            server: Server to discover tools from
            
        Returns:
            DiscoveryResult with discovered tools
        """
        start_time = datetime.utcnow()
        
        # Check if we have a discovery service for this server type
        discovery_service = self.discovery_services.get(server.server_type)
        if not discovery_service:
            logger.warning(f"No discovery service available for server type: {server.server_type}")
            return DiscoveryResult(
                server_name=server.name,
                server_type=server.server_type,
                success=False,
                error_message=f"No discovery service available for {server.server_type.value}"
            )
        
        try:
            logger.debug(f"Discovering tools for server: {server.name} ({server.server_type.value})")
            
            # Perform tool discovery
            result = await discovery_service.discover_tools(
                server_name=server.name,
                command=server.command,
                args=server.args,
                env=server.env,
                working_dir=server.working_dir
            )
            
            # Calculate discovery time
            discovery_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            result.discovery_time_ms = discovery_time_ms
            
            logger.debug(f"Tool discovery completed for {server.name}", extra={
                "server_name": server.name,
                "tools_found": len(result.tools),
                "success": result.success,
                "discovery_time_ms": discovery_time_ms
            })
            
            return result
            
        except Exception as e:
            discovery_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            logger.error(f"Tool discovery failed for {server.name}: {e}")
            
            return DiscoveryResult(
                server_name=server.name,
                server_type=server.server_type,
                success=False,
                error_message=str(e),
                discovery_time_ms=discovery_time_ms
            )
    
    def detect_tool_conflicts(self, discovery_results: Dict[str, DiscoveryResult]) -> List[ConflictInfo]:
        """
        Detect tool name conflicts across servers.
        
        Args:
            discovery_results: Results from tool discovery
            
        Returns:
            List of conflict information
        """
        tool_servers: Dict[str, Set[str]] = {}
        
        # Collect all tools and their servers
        for server_name, result in discovery_results.items():
            if result.success:
                for tool in result.tools:
                    if tool.name not in tool_servers:
                        tool_servers[tool.name] = set()
                    tool_servers[tool.name].add(server_name)
        
        # Find conflicts (tools available from multiple servers)
        conflicts = []
        for tool_name, servers in tool_servers.items():
            if len(servers) > 1:
                conflicts.append(ConflictInfo(tool_name, list(servers)))
        
        if conflicts:
            logger.info(f"Detected {len(conflicts)} tool name conflicts", extra={
                "conflict_count": len(conflicts),
                "conflicting_tools": [c.tool_name for c in conflicts]
            })
        
        return conflicts
    
    def get_all_tools(self, discovery_results: Dict[str, DiscoveryResult]) -> List[ToolInfo]:
        """
        Get all discovered tools from discovery results.
        
        Args:
            discovery_results: Results from tool discovery
            
        Returns:
            List of all discovered tools
        """
        all_tools = []
        
        for result in discovery_results.values():
            if result.success:
                all_tools.extend(result.tools)
        
        return all_tools
    
    def get_discovery_statistics(self, discovery_results: Dict[str, DiscoveryResult]) -> Dict[str, any]:
        """
        Generate statistics from discovery results.
        
        Args:
            discovery_results: Results from tool discovery
            
        Returns:
            Dictionary with discovery statistics
        """
        total_servers = len(discovery_results)
        successful_servers = sum(1 for r in discovery_results.values() if r.success)
        total_tools = sum(len(r.tools) for r in discovery_results.values() if r.success)
        total_discovery_time = sum(r.discovery_time_ms for r in discovery_results.values())
        
        # Tools by server type
        tools_by_type = {}
        for result in discovery_results.values():
            if result.success:
                server_type = result.server_type.value
                if server_type not in tools_by_type:
                    tools_by_type[server_type] = 0
                tools_by_type[server_type] += len(result.tools)
        
        # Tool categories
        category_counts = {}
        for result in discovery_results.values():
            if result.success:
                for tool in result.tools:
                    for category in tool.categories:
                        category_counts[category] = category_counts.get(category, 0) + 1
        
        return {
            "total_servers": total_servers,
            "successful_servers": successful_servers,
            "failed_servers": total_servers - successful_servers,
            "success_rate": successful_servers / total_servers if total_servers > 0 else 0,
            "total_tools": total_tools,
            "average_tools_per_server": total_tools / successful_servers if successful_servers > 0 else 0,
            "total_discovery_time_ms": total_discovery_time,
            "average_discovery_time_ms": total_discovery_time / total_servers if total_servers > 0 else 0,
            "tools_by_server_type": tools_by_type,
            "tools_by_category": category_counts
        }