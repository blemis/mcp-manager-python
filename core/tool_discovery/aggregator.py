"""
Tool discovery aggregator service.

Orchestrates tool discovery across all server types using the appropriate
discovery services and provides unified results with conflict resolution.
"""

import asyncio
import os
from typing import Any, Dict, List, Optional, Set

from mcp_manager.core.models import Server, ServerType
from mcp_manager.core.tool_discovery.base import BaseToolDiscovery, DiscoveryConfig, ToolDiscoveryResult
from mcp_manager.core.tool_discovery.docker_desktop_discovery import DockerDesktopToolDiscovery
from mcp_manager.core.tool_discovery.docker_discovery import DockerToolDiscovery  
from mcp_manager.core.tool_discovery.npm_discovery import NPMToolDiscovery
from mcp_manager.core.tool_discovery_logger import ToolDiscoveryLogger, performance_timer
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class AggregatedDiscoveryResult:
    """Result of aggregated tool discovery across multiple servers."""
    
    def __init__(self):
        self.server_results: List[ToolDiscoveryResult] = []
        self.total_tools_discovered = 0
        self.total_discovery_duration_seconds = 0.0
        self.successful_servers = 0
        self.failed_servers = 0
        self.warnings: List[str] = []
        self.conflicts_detected: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}
    
    @property
    def success_rate(self) -> float:
        """Calculate overall success rate."""
        total_servers = len(self.server_results)
        if total_servers == 0:
            return 0.0
        return self.successful_servers / total_servers
    
    @property
    def average_discovery_time(self) -> float:
        """Calculate average discovery time per server."""
        if len(self.server_results) == 0:
            return 0.0
        return self.total_discovery_duration_seconds / len(self.server_results)
    
    def add_server_result(self, result: ToolDiscoveryResult) -> None:
        """Add a server discovery result to the aggregated results."""
        self.server_results.append(result)
        self.total_tools_discovered += len(result.tools_discovered)
        self.total_discovery_duration_seconds += result.discovery_duration_seconds
        
        if result.success:
            self.successful_servers += 1
        else:
            self.failed_servers += 1
            
        # Propagate warnings
        if result.warnings:
            self.warnings.extend([f"{result.server_name}: {w}" for w in result.warnings])


class ToolDiscoveryAggregator:
    """
    Aggregates tool discovery across all server types with conflict resolution.
    
    Manages multiple discovery services and provides unified results with
    duplicate detection and performance optimization.
    """
    
    def __init__(self, config: Optional[DiscoveryConfig] = None):
        """
        Initialize tool discovery aggregator.
        
        Args:
            config: Discovery configuration. If None, uses defaults from environment.
        """
        self.config = config or DiscoveryConfig()
        self.logger = ToolDiscoveryLogger("aggregator")
        
        # Initialize discovery services
        self.discovery_services: List[BaseToolDiscovery] = [
            NPMToolDiscovery(self.config),
            DockerToolDiscovery(self.config),
            DockerDesktopToolDiscovery(self.config)
        ]
        
        # Configuration from environment
        self.max_concurrent_discoveries = int(os.getenv("MCP_MAX_CONCURRENT_DISCOVERIES", "5"))
        self.conflict_resolution_enabled = os.getenv("MCP_CONFLICT_RESOLUTION", "true").lower() == "true"
        self.duplicate_threshold = float(os.getenv("MCP_DUPLICATE_THRESHOLD", "0.8"))
        
        logger.info("Tool discovery aggregator initialized", extra={
            "discovery_services": [service.__class__.__name__ for service in self.discovery_services],
            "max_concurrent": self.max_concurrent_discoveries,
            "conflict_resolution": self.conflict_resolution_enabled
        })
    
    async def discover_all_tools(self, servers: List[Server]) -> AggregatedDiscoveryResult:
        """
        Discover tools from all provided servers using appropriate discovery services.
        
        Args:
            servers: List of servers to discover tools from
            
        Returns:
            AggregatedDiscoveryResult with all discovered tools and metadata
        """
        operation_id = f"aggregate_discovery_{int(asyncio.get_event_loop().time() * 1000)}"
        
        logger.info("Starting aggregated tool discovery", extra={
            "operation_id": operation_id,
            "server_count": len(servers),
            "parallel_discovery": self.config.parallel_discovery
        })
        
        result = AggregatedDiscoveryResult()
        
        try:
            with performance_timer("aggregated_discovery", self.logger) as timing:
                # Group servers by discovery service capability
                server_groups = self._group_servers_by_service(servers)
                
                # Discover tools from each group
                if self.config.parallel_discovery:
                    discovery_tasks = []
                    
                    for service, service_servers in server_groups.items():
                        if service_servers:
                            task = self._discover_from_servers_concurrent(service, service_servers)
                            discovery_tasks.append(task)
                    
                    # Execute all discovery tasks concurrently
                    if discovery_tasks:
                        all_results = await asyncio.gather(*discovery_tasks, return_exceptions=True)
                        
                        for task_results in all_results:
                            if isinstance(task_results, Exception):
                                logger.error(f"Discovery task failed: {task_results}")
                                result.warnings.append(f"Discovery service failed: {task_results}")
                            else:
                                for server_result in task_results:
                                    result.add_server_result(server_result)
                else:
                    # Sequential discovery
                    for service, service_servers in server_groups.items():
                        if service_servers:
                            service_results = await self._discover_from_servers_sequential(service, service_servers)
                            for server_result in service_results:
                                result.add_server_result(server_result)
                
                # Post-process results
                if self.conflict_resolution_enabled:
                    conflicts = self._detect_tool_conflicts(result.server_results)
                    result.conflicts_detected = conflicts
                    
                    if conflicts:
                        logger.warning(f"Detected {len(conflicts)} tool conflicts", extra={
                            "operation_id": operation_id,
                            "conflicts": [c["canonical_names"] for c in conflicts]
                        })
                
                # Add aggregated metadata
                result.metadata = {
                    "operation_id": operation_id,
                    "discovery_method": "aggregated",
                    "parallel_execution": self.config.parallel_discovery,
                    "services_used": list(server_groups.keys()),
                    "discovery_duration_seconds": timing.get("duration_seconds", 0.0),
                    "tools_per_second": result.total_tools_discovered / max(timing.get("duration_seconds", 0.001), 0.001),
                    "conflict_resolution_enabled": self.conflict_resolution_enabled,
                    "conflicts_detected": len(result.conflicts_detected)
                }
                
                logger.info("Aggregated tool discovery completed", extra={
                    "operation_id": operation_id,
                    "total_tools": result.total_tools_discovered,
                    "successful_servers": result.successful_servers,
                    "failed_servers": result.failed_servers,
                    "conflicts_detected": len(result.conflicts_detected),
                    "duration_seconds": timing.get("duration_seconds", 0.0)
                })
        
        except Exception as e:
            logger.error("Aggregated discovery failed", extra={
                "operation_id": operation_id,
                "error": str(e),
                "error_type": type(e).__name__
            })
            result.warnings.append(f"Aggregated discovery failed: {e}")
        
        return result
    
    async def discover_from_server(self, server: Server) -> ToolDiscoveryResult:
        """
        Discover tools from a single server using the appropriate discovery service.
        
        Args:
            server: Server to discover tools from
            
        Returns:
            ToolDiscoveryResult for the server
        """
        # Find appropriate discovery service
        discovery_service = self._get_discovery_service_for_server(server)
        
        if not discovery_service:
            result = ToolDiscoveryResult(
                server_name=server.name,
                server_type=server.server_type,
                discovery_duration_seconds=0.0,
                success=False
            )
            result.errors.append(f"No discovery service available for server type: {server.server_type}")
            return result
        
        logger.debug(f"Using {discovery_service.__class__.__name__} for server {server.name}")
        return await discovery_service.discover_tools(server)
    
    def _group_servers_by_service(self, servers: List[Server]) -> Dict[str, List[Server]]:
        """
        Group servers by their appropriate discovery service.
        
        Args:
            servers: List of servers to group
            
        Returns:
            Dictionary mapping service names to lists of servers
        """
        server_groups: Dict[str, List[Server]] = {}
        
        for server in servers:
            service = self._get_discovery_service_for_server(server)
            if service:
                service_name = service.__class__.__name__
                if service_name not in server_groups:
                    server_groups[service_name] = []
                server_groups[service_name].append(server)
            else:
                logger.warning(f"No discovery service found for server: {server.name} (type: {server.server_type})")
        
        return server_groups
    
    def _get_discovery_service_for_server(self, server: Server) -> Optional[BaseToolDiscovery]:
        """
        Get the appropriate discovery service for a server.
        
        Args:
            server: Server to find service for
            
        Returns:
            Discovery service instance or None if no suitable service found
        """
        for service in self.discovery_services:
            if service.can_handle_server(server):
                return service
        return None
    
    async def _discover_from_servers_concurrent(self, service: BaseToolDiscovery, 
                                              servers: List[Server]) -> List[ToolDiscoveryResult]:
        """
        Discover tools from multiple servers concurrently using the same service.
        
        Args:
            service: Discovery service to use
            servers: List of servers to discover from
            
        Returns:
            List of discovery results
        """
        # Create semaphore to limit concurrent discoveries
        semaphore = asyncio.Semaphore(self.max_concurrent_discoveries)
        
        async def discover_with_semaphore(server: Server) -> ToolDiscoveryResult:
            async with semaphore:
                return await service.discover_tools(server)
        
        tasks = [discover_with_semaphore(server) for server in servers]
        return await asyncio.gather(*tasks, return_exceptions=False)
    
    async def _discover_from_servers_sequential(self, service: BaseToolDiscovery,
                                              servers: List[Server]) -> List[ToolDiscoveryResult]:
        """
        Discover tools from multiple servers sequentially using the same service.
        
        Args:
            service: Discovery service to use
            servers: List of servers to discover from
            
        Returns:
            List of discovery results
        """
        results = []
        for server in servers:
            try:
                result = await service.discover_tools(server)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to discover tools from {server.name}: {e}")
                failed_result = ToolDiscoveryResult(
                    server_name=server.name,
                    server_type=server.server_type,
                    discovery_duration_seconds=0.0,
                    success=False
                )
                failed_result.errors.append(str(e))
                results.append(failed_result)
        
        return results
    
    def _detect_tool_conflicts(self, server_results: List[ToolDiscoveryResult]) -> List[Dict[str, Any]]:
        """
        Detect potential conflicts between tools from different servers.
        
        Args:
            server_results: List of discovery results to analyze
            
        Returns:
            List of detected conflicts with details
        """
        conflicts = []
        
        # Build a map of tool names to their canonical names
        tool_name_map: Dict[str, List[str]] = {}
        tool_description_map: Dict[str, List[str]] = {}
        
        for result in server_results:
            for tool in result.tools_discovered:
                # Group by tool name
                tool_name = tool.name.lower()
                if tool_name not in tool_name_map:
                    tool_name_map[tool_name] = []
                tool_name_map[tool_name].append(tool.canonical_name)
                
                # Group by similar descriptions
                description = tool.description.lower()[:100]  # First 100 chars
                if description not in tool_description_map:
                    tool_description_map[description] = []
                tool_description_map[description].append(tool.canonical_name)
        
        # Find conflicts by name
        for tool_name, canonical_names in tool_name_map.items():
            if len(canonical_names) > 1:
                conflicts.append({
                    "type": "name_conflict",
                    "tool_name": tool_name,
                    "canonical_names": canonical_names,
                    "conflict_count": len(canonical_names),
                    "similarity_score": 1.0  # Exact name match
                })
        
        # Find conflicts by similar descriptions (if enabled)
        if self.conflict_resolution_enabled:
            for description, canonical_names in tool_description_map.items():
                if len(canonical_names) > 1 and description.strip():
                    # Check if these aren't already flagged as name conflicts
                    existing_conflict = any(
                        set(canonical_names).intersection(set(c["canonical_names"]))
                        for c in conflicts if c["type"] == "name_conflict"
                    )
                    
                    if not existing_conflict:
                        conflicts.append({
                            "type": "description_conflict",
                            "description_preview": description[:50] + "..." if len(description) > 50 else description,
                            "canonical_names": canonical_names,
                            "conflict_count": len(canonical_names),
                            "similarity_score": self.duplicate_threshold
                        })
        
        return conflicts
    
    def get_supported_server_types(self) -> Set[ServerType]:
        """
        Get all server types supported by available discovery services.
        
        Returns:
            Set of supported ServerType values
        """
        supported_types = set()
        
        # Test each server type with each service
        for server_type in ServerType:
            test_server = Server(
                name="test", 
                command="test", 
                server_type=server_type
            )
            
            for service in self.discovery_services:
                if service.can_handle_server(test_server):
                    supported_types.add(server_type)
                    break
        
        return supported_types