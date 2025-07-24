"""
Main orchestration module for the MCP Manager tool registry system.

Provides a unified interface for all tool registry operations by coordinating
between the database manager, registration service, and search service.
"""

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp_manager.core.models import ToolRegistry
from mcp_manager.core.tools.database_manager import DatabaseManager
from mcp_manager.core.tools.models import DiscoveryResult, SearchFilters, ToolInfo, RegistryStats
from mcp_manager.core.tools.registration import ToolRegistrationService
from mcp_manager.core.tools.search_service import ToolSearchService
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ToolRegistryService:
    """
    Main orchestration service for the MCP tool registry.
    
    Provides a unified interface for tool registration, search, and management
    operations by coordinating between specialized service components.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize tool registry service.
        
        Args:
            db_path: Path to SQLite database. If None, uses default from environment.
        """
        # Initialize core components
        self.db_manager = DatabaseManager(db_path)
        self.registration_service = ToolRegistrationService(self.db_manager)
        self.search_service = ToolSearchService(self.db_manager, self.registration_service)
        
        # Configuration from environment
        self.discovery_timeout_seconds = int(os.getenv("MCP_DISCOVERY_TIMEOUT", "30"))
        self.cache_ttl_hours = int(os.getenv("MCP_CACHE_TTL_HOURS", "24"))
        
        logger.info("Tool registry service initialized", extra={
            "db_path": str(self.db_manager.db_path),
            "discovery_timeout": self.discovery_timeout_seconds,
            "cache_ttl_hours": self.cache_ttl_hours
        })
    
    # ========== Tool Registration Operations ==========
    
    def register_tool(self, tool_registry: ToolRegistry) -> bool:
        """
        Register a tool in the registry.
        
        Args:
            tool_registry: Tool registry entry to store
            
        Returns:
            True if successful, False otherwise
        """
        return self.registration_service.register_tool(tool_registry)
    
    def register_tools_batch(self, tools: List[ToolRegistry]) -> DiscoveryResult:
        """
        Register multiple tools in a batch operation.
        
        Args:
            tools: List of tool registry entries to store
            
        Returns:
            DiscoveryResult with batch operation results
        """
        start_time = time.time()
        successful_registrations = 0
        errors = []
        
        for tool in tools:
            try:
                if self.register_tool(tool):
                    successful_registrations += 1
                else:
                    errors.append(f"Failed to register tool: {tool.canonical_name}")
            except Exception as e:
                errors.append(f"Error registering {tool.canonical_name}: {str(e)}")
        
        duration = time.time() - start_time
        server_name = tools[0].server_name if tools else "unknown"
        
        return DiscoveryResult(
            server_name=server_name,
            tools_discovered=successful_registrations,
            duration_seconds=duration,
            errors=errors
        )
    
    def get_tool(self, canonical_name: str) -> Optional[ToolRegistry]:
        """
        Get a tool by its canonical name.
        
        Args:
            canonical_name: Tool canonical name (server_name/tool_name)
            
        Returns:
            ToolRegistry object if found, None otherwise
        """
        return self.registration_service.get_tool(canonical_name)
    
    def update_tool_availability(self, server_name: str, is_available: bool) -> int:
        """
        Update availability status for all tools from a server.
        
        Args:
            server_name: Name of the server
            is_available: New availability status
            
        Returns:
            Number of tools updated
        """
        return self.registration_service.update_tool_availability(server_name, is_available)
    
    def remove_server_tools(self, server_name: str) -> int:
        """
        Remove all tools for a server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            Number of tools removed
        """
        return self.registration_service.remove_server_tools(server_name)
    
    def update_tool_usage(self, canonical_name: str, success: bool, 
                         response_time_ms: Optional[float] = None) -> bool:
        """
        Update tool usage statistics.
        
        Args:
            canonical_name: Tool canonical name
            success: Whether the tool call was successful
            response_time_ms: Response time in milliseconds
            
        Returns:
            True if updated successfully, False otherwise
        """
        return self.registration_service.update_tool_usage(
            canonical_name, success, response_time_ms
        )
    
    # ========== Search Operations ==========
    
    def search_tools(self, query: str, filters: Optional[SearchFilters] = None,
                    limit: int = 50) -> List[ToolInfo]:
        """
        Search tools by query with optional filters.
        
        Args:
            query: Search query (searches name, description, tags)
            filters: Optional search filters
            limit: Maximum number of results
            
        Returns:
            List of matching ToolInfo objects
        """
        return self.search_service.search_tools(query, filters, limit)
    
    def get_tools_by_server(self, server_name: str) -> List[ToolInfo]:
        """
        Get all tools for a specific server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            List of ToolInfo objects for the server
        """
        return self.search_service.get_tools_by_server(server_name)
    
    def get_popular_tools(self, limit: int = 20) -> List[ToolInfo]:
        """
        Get most popular tools based on usage statistics.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of ToolInfo objects sorted by popularity
        """
        return self.search_service.get_popular_tools(limit)
    
    def get_tools_by_category(self, category: str, limit: int = 50) -> List[ToolInfo]:
        """
        Get tools by category.
        
        Args:
            category: Category to search for
            limit: Maximum number of results
            
        Returns:
            List of ToolInfo objects in the category
        """
        return self.search_service.get_tools_by_category(category, limit)
    
    def suggest_similar_tools(self, canonical_name: str, limit: int = 5) -> List[ToolInfo]:
        """
        Suggest tools similar to the given tool.
        
        Args:
            canonical_name: Canonical name of the reference tool
            limit: Maximum number of suggestions
            
        Returns:
            List of similar ToolInfo objects
        """
        return self.search_service.suggest_similar_tools(canonical_name, limit)
    
    # ========== Statistics and Analytics ==========
    
    def get_registry_stats(self) -> RegistryStats:
        """
        Get comprehensive registry statistics.
        
        Returns:
            RegistryStats object with registry statistics
        """
        return self.search_service.get_registry_stats()
    
    def get_server_summary(self) -> Dict[str, Any]:
        """
        Get summary of all servers and their tool counts.
        
        Returns:
            Dictionary mapping server names to tool information
        """
        try:
            stats = self.get_registry_stats()
            server_summary = {}
            
            # Get tools for each server
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT server_name, server_type, COUNT(*) as tool_count,
                           SUM(CASE WHEN is_available = 1 THEN 1 ELSE 0 END) as available_count,
                           AVG(success_rate) as avg_success_rate,
                           MAX(last_discovered) as last_discovered
                    FROM tool_registry 
                    GROUP BY server_name, server_type
                    ORDER BY tool_count DESC
                """)
                
                for row in cursor.fetchall():
                    server_name, server_type, tool_count, available_count, avg_success_rate, last_discovered = row
                    server_summary[server_name] = {
                        "server_type": server_type,
                        "total_tools": tool_count,
                        "available_tools": available_count,
                        "unavailable_tools": tool_count - available_count,
                        "average_success_rate": round(avg_success_rate or 0, 3),
                        "last_discovered": last_discovered
                    }
            
            return server_summary
            
        except Exception as e:
            logger.error(f"Failed to get server summary: {e}")
            return {}
    
    # ========== Database Management ==========
    
    def backup_database(self, backup_path: Optional[Path] = None) -> Path:
        """
        Create a backup of the database.
        
        Args:
            backup_path: Path for backup file. If None, generates timestamp-based name.
            
        Returns:
            Path to the created backup file
        """
        return self.db_manager.backup_database(backup_path)
    
    def get_database_info(self) -> Dict[str, Any]:
        """
        Get information about the database.
        
        Returns:
            Dictionary with database information
        """
        return self.db_manager.get_database_info()
    
    def vacuum_database(self) -> bool:
        """
        Vacuum the database to reclaim space and optimize.
        
        Returns:
            True if successful, False otherwise
        """
        return self.db_manager.vacuum_database()
    
    # ========== Cleanup and Maintenance ==========
    
    def cleanup_stale_tools(self, max_age_days: int = 30) -> int:
        """
        Remove tools that haven't been discovered recently.
        
        Args:
            max_age_days: Maximum age in days before considering tools stale
            
        Returns:
            Number of tools removed
        """
        try:
            from datetime import datetime, timedelta
            
            cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
            
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Count stale tools
                cursor.execute("""
                    SELECT COUNT(*) FROM tool_registry 
                    WHERE last_discovered < ?
                """, (cutoff_date.isoformat(),))
                stale_count = cursor.fetchone()[0]
                
                # Remove stale tools
                cursor.execute("""
                    DELETE FROM tool_registry 
                    WHERE last_discovered < ?
                """, (cutoff_date.isoformat(),))
                
                conn.commit()
                
                logger.info(f"Cleaned up {stale_count} stale tools older than {max_age_days} days")
                return stale_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup stale tools: {e}")
            return 0
    
    def close(self):
        """Clean up registry service resources."""
        self.db_manager.close()
        logger.debug("Tool registry service closed")