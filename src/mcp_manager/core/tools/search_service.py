"""
Advanced search service for the MCP Manager tool registry.

Provides sophisticated search capabilities with filtering, ranking,
and performance optimization for tool discovery.
"""

import json
import sqlite3
from typing import Any, Dict, List

from mcp_manager.core.tool_discovery_logger import ToolDiscoveryLogger, performance_timer
from mcp_manager.core.tools.database_manager import DatabaseManager
from mcp_manager.core.tools.models import SearchFilters, ToolInfo, RegistryStats
from mcp_manager.core.tools.registration import ToolRegistrationService
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ToolSearchService:
    """Handles advanced search operations for the tool registry."""
    
    def __init__(self, database_manager: DatabaseManager, 
                 registration_service: ToolRegistrationService):
        """
        Initialize tool search service.
        
        Args:
            database_manager: Database manager instance
            registration_service: Tool registration service instance
        """
        self.db_manager = database_manager
        self.registration_service = registration_service
        self.discovery_logger = ToolDiscoveryLogger("tool_search")
        logger.debug("Tool search service initialized")
    
    def search_tools(self, query: str, filters: SearchFilters = None,
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
        if filters is None:
            filters = SearchFilters()
        
        with performance_timer("tool_search", self.discovery_logger):
            try:
                with self.db_manager.get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Build dynamic query
                    where_conditions = []
                    params = []
                    
                    # Text search across name, description, categories, tags
                    if query.strip():
                        where_conditions.append("""
                            (name LIKE ? OR description LIKE ? OR 
                             categories LIKE ? OR tags LIKE ?)
                        """)
                        search_pattern = f"%{query}%"
                        params.extend([search_pattern] * 4)
                    
                    # Apply SQL-level filters
                    where_conditions, params = self._apply_sql_filters(
                        where_conditions, params, filters
                    )
                    
                    # Build final query
                    sql = self._build_search_query(where_conditions, limit)
                    params.append(limit)
                    
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
                    
                    # Convert to ToolInfo objects and apply additional filters
                    results = []
                    for row in rows:
                        tool_registry = self.registration_service._row_to_tool_registry(cursor, row)
                        if tool_registry and self._matches_additional_filters(tool_registry, filters):
                            results.append(ToolInfo(tool_registry))
                    
                    logger.debug("Tool search completed", extra={
                        "query": query,
                        "results_count": len(results),
                        "filters_applied": filters.has_filters()
                    })
                    
                    return results
                    
            except Exception as e:
                logger.error("Tool search failed", extra={
                    "query": query,
                    "error": str(e)
                })
                return []
    
    def get_tools_by_server(self, server_name: str) -> List[ToolInfo]:
        """
        Get all tools for a specific server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            List of ToolInfo objects for the server
        """
        filters = SearchFilters(server_name=server_name)
        return self.search_tools("", filters, limit=1000)  # High limit for server listing
    
    def get_popular_tools(self, limit: int = 20) -> List[ToolInfo]:
        """
        Get most popular tools based on usage statistics.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of ToolInfo objects sorted by popularity
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM tool_registry 
                    WHERE is_available = 1
                    ORDER BY usage_count DESC, success_rate DESC
                    LIMIT ?
                """, (limit,))
                
                rows = cursor.fetchall()
                results = []
                
                for row in rows:
                    tool_registry = self.registration_service._row_to_tool_registry(cursor, row)
                    if tool_registry:
                        results.append(ToolInfo(tool_registry))
                
                logger.debug(f"Retrieved {len(results)} popular tools")
                return results
                
        except Exception as e:
            logger.error(f"Failed to get popular tools: {e}")
            return []
    
    def get_tools_by_category(self, category: str, limit: int = 50) -> List[ToolInfo]:
        """
        Get tools by category.
        
        Args:
            category: Category to search for
            limit: Maximum number of results
            
        Returns:
            List of ToolInfo objects in the category
        """
        filters = SearchFilters(categories=[category])
        return self.search_tools("", filters, limit)
    
    def get_registry_stats(self) -> RegistryStats:
        """
        Get comprehensive registry statistics.
        
        Returns:
            RegistryStats object with registry statistics
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Basic counts
                cursor.execute("SELECT COUNT(*) FROM tool_registry")
                total_tools = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM tool_registry WHERE is_available = 1")
                available_tools = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(DISTINCT server_name) FROM tool_registry")
                servers_with_tools = cursor.fetchone()[0]
                
                # Server type distribution
                cursor.execute("""
                    SELECT server_type, COUNT(*) 
                    FROM tool_registry 
                    GROUP BY server_type
                """)
                server_type_distribution = dict(cursor.fetchall())
                
                # Category distribution
                category_distribution = self._calculate_category_distribution(cursor)
                
                return RegistryStats(
                    total_tools=total_tools,
                    available_tools=available_tools,
                    servers_with_tools=servers_with_tools,
                    server_type_distribution=server_type_distribution,
                    category_distribution=category_distribution,
                    database_path=str(self.db_manager.db_path)
                )
                
        except Exception as e:
            logger.error("Failed to get registry stats", extra={
                "error": str(e)
            })
            # Return empty stats on error
            return RegistryStats(0, 0, 0, {}, {}, str(self.db_manager.db_path))
    
    def _apply_sql_filters(self, where_conditions: List[str], params: List, 
                          filters: SearchFilters) -> tuple:
        """Apply filters that can be handled at SQL level."""
        # Server name filter
        if filters.server_name:
            where_conditions.append("server_name = ?")
            params.append(filters.server_name)
        
        # Server type filter
        if filters.server_type:
            where_conditions.append("server_type = ?")
            params.append(filters.server_type.value if hasattr(filters.server_type, 'value') else str(filters.server_type))
        
        # Availability filter
        if filters.available_only:
            where_conditions.append("is_available = 1")
        
        # Success rate filter
        if filters.min_success_rate is not None:
            where_conditions.append("success_rate >= ?")
            params.append(filters.min_success_rate)
        
        return where_conditions, params
    
    def _build_search_query(self, where_conditions: List[str], limit: int) -> str:
        """Build the final SQL search query."""
        sql = "SELECT * FROM tool_registry"
        
        if where_conditions:
            sql += " WHERE " + " AND ".join(where_conditions)
        
        # Order by relevance and performance
        sql += " ORDER BY usage_count DESC, success_rate DESC LIMIT ?"
        
        return sql
    
    def _matches_additional_filters(self, tool_registry, filters: SearchFilters) -> bool:
        """Check if tool matches additional filters not handled by SQL."""
        # Check categories filter (requires JSON parsing)
        if filters.categories:
            if not any(cat in tool_registry.categories for cat in filters.categories):
                return False
        
        # Check tags filter (requires JSON parsing)
        if filters.tags:
            if not any(tag in tool_registry.tags for tag in filters.tags):
                return False
        
        return True
    
    def _calculate_category_distribution(self, cursor: sqlite3.Cursor) -> Dict[str, int]:
        """Calculate the distribution of tools across categories."""
        cursor.execute("SELECT categories FROM tool_registry WHERE categories != '[]'")
        all_categories = []
        
        for row in cursor.fetchall():
            try:
                categories = json.loads(row[0])
                all_categories.extend(categories)
            except (json.JSONDecodeError, TypeError):
                continue
        
        # Count category frequency
        category_counts = {}
        for category in all_categories:
            category_counts[category] = category_counts.get(category, 0) + 1
        
        return category_counts
    
    def suggest_similar_tools(self, canonical_name: str, limit: int = 5) -> List[ToolInfo]:
        """
        Suggest tools similar to the given tool.
        
        Args:
            canonical_name: Canonical name of the reference tool
            limit: Maximum number of suggestions
            
        Returns:
            List of similar ToolInfo objects
        """
        try:
            # Get the reference tool
            reference_tool = self.registration_service.get_tool(canonical_name)
            if not reference_tool:
                return []
            
            # Search for tools with similar categories or tags
            similar_tools = []
            
            # Search by categories
            if reference_tool.categories:
                for category in reference_tool.categories[:2]:  # Use top 2 categories
                    category_tools = self.get_tools_by_category(category, limit=10)
                    similar_tools.extend([t for t in category_tools if t.canonical_name != canonical_name])
            
            # Remove duplicates and sort by usage
            seen = set()
            unique_tools = []
            for tool in similar_tools:
                if tool.canonical_name not in seen:
                    seen.add(tool.canonical_name)
                    unique_tools.append(tool)
            
            # Sort by usage count and success rate
            unique_tools.sort(key=lambda t: (t.usage_count, t.success_rate), reverse=True)
            
            return unique_tools[:limit]
            
        except Exception as e:
            logger.error("Failed to suggest similar tools", extra={
                "canonical_name": canonical_name,
                "error": str(e)
            })
            return []