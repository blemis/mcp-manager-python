"""
Simplified MCP Manager that works directly with Claude Code's internal state.

This manager is now a thin orchestration layer that delegates to specialized managers.
"""

import asyncio
import os
import threading
import time
from typing import List, Optional, Dict, Any

from mcp_manager.core.claude_interface import ClaudeInterface
from mcp_manager.core.exceptions import MCPManagerError
from mcp_manager.core.models import Server, ServerType, ServerScope
from mcp_manager.utils.config import get_config
from mcp_manager.utils.logging import get_logger

# Lazy imports for managers
from mcp_manager.core.managers.sync_manager import SyncCheckResult

logger = get_logger(__name__)


class SimpleMCPManager:
    """Simplified MCP Manager that delegates to specialized managers."""
    
    def __init__(self):
        """Initialize the manager with lazy loading for all managers."""
        self.claude = ClaudeInterface()
        
        # Lazy initialization - only create managers when needed
        self._server_manager = None
        self._discovery_manager = None
        self._tool_manager = None
        self._sync_manager = None
        self._mode_manager = None
        
        logger.debug("SimpleMCPManager initialized (managers will be loaded on demand)")
    
    @property
    def server_manager(self):
        """Get server manager (lazy loading)."""
        if self._server_manager is None:
            from mcp_manager.core.managers.server_manager import ServerManager
            self._server_manager = ServerManager(self.claude)
            logger.debug("ServerManager loaded")
        return self._server_manager
    
    @property
    def discovery_manager(self):
        """Get discovery manager (lazy loading)."""
        if self._discovery_manager is None:
            from mcp_manager.core.managers.discovery_manager import DiscoveryManager
            self._discovery_manager = DiscoveryManager()
            logger.debug("DiscoveryManager loaded")
        return self._discovery_manager
    
    @property
    def tool_manager(self):
        """Get tool manager (lazy loading)."""
        if self._tool_manager is None:
            from mcp_manager.core.managers.tool_manager import ToolManager
            self._tool_manager = ToolManager(
                tool_registry=self.discovery_manager.tool_registry,
                server_list_callback=self.list_servers_fast
            )
            logger.debug("ToolManager loaded")
        return self._tool_manager
    
    @property
    def sync_manager(self):
        """Get sync manager (lazy loading)."""
        if self._sync_manager is None:
            from mcp_manager.core.managers.sync_manager import SyncManager
            self._sync_manager = SyncManager(
                claude_interface=self.claude,
                server_list_callback=self.list_servers_fast
            )
            logger.debug("SyncManager loaded")
        return self._sync_manager
    
    @property
    def mode_manager(self):
        """Get mode manager (lazy loading)."""
        if self._mode_manager is None:
            from mcp_manager.core.managers.mode_manager import ModeManager
            self._mode_manager = ModeManager(self.claude)
            logger.debug("ModeManager loaded")
        return self._mode_manager
    
    # Server Management Methods (delegate to ServerManager)
    async def add_server(self, name: str, server_type: ServerType, command: str,
                   description: Optional[str] = None, env: Optional[dict] = None,
                   args: Optional[List[str]] = None, scope: ServerScope = ServerScope.USER,
                   working_dir: Optional[str] = None) -> Server:
        """Add a new MCP server (CLI-compatible signature)."""
        # Use the server manager to add the server
        success = self.server_manager.add_server(
            name=name, command=command, args=args, env=env,
            working_dir=working_dir, server_type=server_type, scope=scope
        )
        
        if success:
            # Return the server object that was created
            server = Server(
                name=name,
                command=command,
                args=args or [],
                env=env or {},
                working_dir=working_dir,
                server_type=server_type,
                scope=scope,
                enabled=True
            )
            return server
        else:
            raise MCPManagerError(f"Failed to add server {name}")
    
    def remove_server(self, name: str, scope: ServerScope = ServerScope.USER) -> bool:
        """Remove an MCP server."""
        return self.server_manager.remove_server(name, scope)
    
    def enable_server(self, name: str, scope: ServerScope = ServerScope.USER) -> bool:
        """Enable an MCP server."""
        return self.server_manager.enable_server(name, scope)
    
    def disable_server(self, name: str, scope: ServerScope = ServerScope.USER) -> bool:
        """Disable an MCP server."""
        return self.server_manager.disable_server(name, scope)
    
    def list_servers(self) -> List[Server]:
        """List all MCP servers, expanding docker-gateway to individual servers."""
        base_servers = self.server_manager.list_servers()
        expanded_servers = []
        
        for server in base_servers:
            if server.name == "docker-gateway":
                # Expand docker-gateway into individual servers
                individual_servers = self.mode_manager.expand_docker_gateway(server)
                expanded_servers.extend(individual_servers)
            else:
                expanded_servers.append(server)
        
        return expanded_servers
    
    def list_servers_fast(self) -> List[Server]:
        """List all MCP servers using fast cached method."""
        base_servers = self.server_manager.list_servers_fast()
        expanded_servers = []
        
        for server in base_servers:
            if server.name == "docker-gateway":
                # Expand docker-gateway into individual servers
                individual_servers = self.mode_manager.expand_docker_gateway(server)
                expanded_servers.extend(individual_servers)
            else:
                expanded_servers.append(server)
        
        return expanded_servers
    
    def get_server(self, name: str) -> Optional[Server]:
        """Get a specific server by name."""
        return self.server_manager.get_server(name)
    
    def server_exists(self, name: str) -> bool:
        """Check if a server exists."""
        return self.server_manager.server_exists(name)
    
    async def get_server_details(self, server_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific server including its tools."""
        try:
            servers = self.list_servers()
            server = next((s for s in servers if s.name == server_name), None)
            
            if not server:
                return None
            
            details = {
                "name": server.name,
                "type": server.server_type.value,
                "scope": server.scope.value if server.scope else "unknown",
                "status": "enabled" if server.enabled else "disabled",
                "command": server.command,
                "args": server.args,
                "env": server.env,
                "tools": [],
                "description": getattr(server, 'description', ''),
            }
            
            # Try to get tool information
            try:
                tool_count = await self.discover_and_register_server_tools(server)
                details["tool_count"] = tool_count
                
                # Get tools from registry
                tools = self.search_tools(server_name=server_name)
                details["tools"] = tools[:10]  # Limit to first 10 tools for display
            except Exception as e:
                logger.debug(f"Failed to get tools for {server_name}: {e}")
                details["tool_count"] = 0
            
            return details
            
        except Exception as e:
            logger.warning(f"Failed to get server details for {server_name}: {e}")
            return None
    
    # Discovery Methods (delegate to DiscoveryManager)
    async def discover_and_register_server_tools(self, server: Server) -> int:
        """Discover and register tools from a server."""
        return await self.discovery_manager.discover_and_register_server_tools(server)
    
    async def discover_all_tools(self, servers: Optional[List[Server]] = None) -> Dict[str, int]:
        """Discover and register tools from all enabled servers."""
        if servers is None:
            servers = self.list_servers_fast()
        return await self.discovery_manager.discover_all_tools(servers)
    
    def search_tools(self, query: Optional[str] = None,
                    server_name: Optional[str] = None,
                    category: Optional[str] = None,
                    limit: int = 50) -> List[Dict[str, Any]]:
        """Search for tools in the registry."""
        return self.discovery_manager.search_tools(query, server_name, category, limit)
    
    # Tool Management Methods (delegate to ToolManager)
    def get_tool_registry_stats(self) -> Dict[str, Any]:
        """Get tool registry statistics."""
        return self.tool_manager.get_tool_registry_stats()
    
    async def get_ai_tool_recommendations(self, query: str,
                                        max_recommendations: int = 5,
                                        server_filter: Optional[str] = None,
                                        include_unavailable: bool = False,
                                        context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get AI-powered tool recommendations."""
        return await self.tool_manager.get_ai_tool_recommendations(
            query, max_recommendations, server_filter, include_unavailable, context
        )
    
    async def suggest_tools_for_task(self, task_description: str,
                                   workflow_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Suggest tools for a specific task."""
        return await self.tool_manager.suggest_tools_for_task(task_description, workflow_context)
    
    def record_tool_usage(self, canonical_name: str, user_query: str,
                         selected: bool, success: bool, response_time_ms: int,
                         error_details: Optional[str] = None,
                         context: Optional[Dict[str, Any]] = None,
                         session_id: Optional[str] = None) -> bool:
        """Record tool usage analytics."""
        return self.tool_manager.record_tool_usage(
            canonical_name, user_query, selected, success, response_time_ms,
            error_details, context, session_id
        )
    
    def get_usage_analytics(self, days: int = 7) -> Dict[str, Any]:
        """Get usage analytics summary."""
        return self.tool_manager.get_usage_analytics(days)
    
    def get_trending_queries(self, limit: int = 10) -> Dict[str, Any]:
        """Get trending query patterns."""
        return self.tool_manager.get_trending_queries(limit)
    
    def record_recommendation_feedback(self, session_id: str,
                                     selected_tool: Optional[str] = None,
                                     satisfaction_score: Optional[float] = None) -> bool:
        """Record user feedback on AI recommendations."""
        return self.tool_manager.record_recommendation_feedback(
            session_id, selected_tool, satisfaction_score
        )
    
    async def update_server_analytics(self) -> Dict[str, Any]:
        """Update server analytics for all servers."""
        return await self.tool_manager.update_server_analytics()
    
    def cleanup_analytics_data(self) -> Dict[str, Any]:
        """Clean up old analytics data."""
        return self.tool_manager.cleanup_analytics_data()
    
    # Sync Methods (delegate to SyncManager)
    @classmethod
    def is_sync_safe(cls) -> bool:
        """Check if it's safe to perform sync operations."""
        from mcp_manager.core.managers.sync_manager import SyncManager
        return SyncManager.is_sync_safe()
    
    def check_sync_status(self) -> SyncCheckResult:
        """Check synchronization status between mcp-manager and Claude Code."""
        return self.sync_manager.check_sync_status()
    
    async def refresh_docker_gateway(self) -> bool:
        """Refresh docker-gateway configuration."""
        return await self.sync_manager.refresh_docker_gateway()
    
    # Mode Management Methods (delegate to ModeManager)
    def get_current_mode(self):
        """Get current operation mode."""
        return self.mode_manager.get_current_mode()
    
    def switch_to_proxy_mode(self) -> bool:
        """Switch to proxy mode using docker-gateway."""
        return self.mode_manager.switch_to_proxy_mode()
    
    def switch_to_direct_mode(self) -> bool:
        """Switch to direct mode by removing docker-gateway.""" 
        return self.mode_manager.switch_to_direct_mode()
    
    def get_mode_status(self) -> Dict[str, Any]:
        """Get comprehensive mode status information."""
        return self.mode_manager.get_mode_status()
    
    def test_docker_gateway(self) -> Dict[str, Any]:
        """Test Docker gateway functionality."""
        return self.mode_manager.test_docker_gateway()
    
    def validate_mode_consistency(self) -> Dict[str, Any]:
        """Validate consistency between detected mode and configuration."""
        return self.mode_manager.validate_mode_consistency()
    
    # System Information Methods (keeping minimal system info)
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        try:
            config = get_config()
            servers = self.list_servers_fast()
            
            return {
                "version": getattr(config, 'version', '1.0.0'),
                "server_count": len(servers),
                "enabled_servers": len([s for s in servers if s.enabled]),
                "claude_available": self.claude.is_claude_cli_available(),
                "docker_available": self.claude.is_docker_available(),
                "current_mode": self.get_current_mode().value if hasattr(self.get_current_mode(), 'value') else str(self.get_current_mode()),
                "analytics_enabled": os.getenv("MCP_ANALYTICS_ENABLED", "true").lower() == "true",
                "auto_discover_tools": os.getenv("MCP_AUTO_DISCOVER_TOOLS", "true").lower() == "true"
            }
            
        except Exception as e:
            logger.error(f"Failed to get system info: {e}")
            return {"error": str(e)}
    
    # Cleanup and Maintenance Methods
    def cleanup(self) -> Dict[str, Any]:
        """Clean up old data and configurations."""
        try:
            results = {}
            
            # Clean up analytics data
            if hasattr(self, '_tool_manager') and self._tool_manager:
                results['analytics_cleanup'] = self.cleanup_analytics_data()
            
            # Additional cleanup could be added to other managers
            
            logger.info("Cleanup completed", extra=results)
            return results
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return {"error": str(e)}
    
    # Discovery Methods (additional compatibility methods) 
    async def check_for_similar_servers(self, name: str, server_type: ServerType,
                                      command: str, args: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Check for servers with similar functionality (CLI compatibility method)."""
        try:
            # This is a simplified version - in the full implementation this would
            # use the discovery manager to find similar servers from catalogs
            # For now, return empty list asynchronously
            await asyncio.sleep(0)  # Make it properly async
            return []  # Return empty list for now to fix CLI compatibility
        except Exception as e:
            logger.error(f"Failed to check for similar servers: {e}")
            return []

    # Utility methods for backwards compatibility
    def wait_for_sync_cooldown(self) -> None:
        """Wait for sync cooldown period after operations."""
        self.server_manager.wait_for_sync_cooldown()