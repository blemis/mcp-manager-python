"""
Core tool registry service for MCP Manager.

Provides centralized management of discovered MCP tools with caching,
search capabilities, and analytics integration.
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mcp_manager.core.migrations.manager import MigrationManager
from mcp_manager.core.models import ServerType, ToolRegistry, ToolUsageAnalytics
from mcp_manager.core.tool_discovery_logger import ToolDiscoveryLogger, performance_timer
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)

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

class ToolRegistryService:
    """Core service for managing the MCP tool registry."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize tool registry service.
        
        Args:
            db_path: Path to SQLite database. If None, uses default from environment.
        """
        if db_path is None:
            db_path = self._get_default_db_path()
        
        self.db_path = db_path
        self.discovery_logger = ToolDiscoveryLogger("tool_registry")
        
        # Configuration from environment
        self.discovery_timeout_seconds = int(os.getenv("MCP_DISCOVERY_TIMEOUT", "30"))
        self.cache_ttl_hours = int(os.getenv("MCP_CACHE_TTL_HOURS", "24"))
        
        logger.info("Tool registry service initialized", extra={
            "db_path": str(self.db_path),
            "discovery_timeout": self.discovery_timeout_seconds,
            "cache_ttl_hours": self.cache_ttl_hours
        })
        
        # Ensure database is properly migrated
        self._ensure_database_ready()
    
    def _get_default_db_path(self) -> Path:
        """Get default database path from environment or config."""
        db_path = os.getenv("MCP_MANAGER_DB_PATH")
        if db_path:
            return Path(db_path)
        
        # Default to user config directory
        config_dir = Path.home() / ".config" / "mcp-manager"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "mcp_manager.db"
    
    def _ensure_database_ready(self) -> None:
        """Ensure database exists and migrations are applied."""
        try:
            migration_manager = MigrationManager(self.db_path)
            
            # Check if we need to run migrations
            pending = migration_manager.get_pending_migrations()
            if pending:
                logger.info(f"Running {len(pending)} pending database migrations")
                success = migration_manager.run_pending_migrations()
                if not success:
                    raise ToolRegistryError("Failed to apply database migrations")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise ToolRegistryError(f"Database initialization failed: {e}")
    
    def register_tool(self, tool_registry: ToolRegistry) -> bool:
        """
        Register a tool in the registry.
        
        Args:
            tool_registry: Tool registry entry to store
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # Convert complex fields to JSON strings
                input_schema_json = json.dumps(tool_registry.input_schema)
                output_schema_json = json.dumps(tool_registry.output_schema)
                categories_json = json.dumps(tool_registry.categories)
                tags_json = json.dumps(tool_registry.tags)
                
                # Insert or update tool
                cursor.execute("""
                    INSERT OR REPLACE INTO tool_registry (
                        name, canonical_name, description, server_name, server_type,
                        input_schema, output_schema, categories, tags, last_discovered,
                        is_available, usage_count, success_rate, average_response_time,
                        created_at, updated_at, discovered_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    tool_registry.name,
                    tool_registry.canonical_name,
                    tool_registry.description,
                    tool_registry.server_name,
                    tool_registry.server_type.value if hasattr(tool_registry.server_type, 'value') else str(tool_registry.server_type),
                    input_schema_json,
                    output_schema_json,
                    categories_json,
                    tags_json,
                    tool_registry.last_discovered.isoformat(),
                    tool_registry.is_available,
                    tool_registry.usage_count,
                    tool_registry.success_rate,
                    tool_registry.average_response_time,
                    tool_registry.created_at.isoformat(),
                    datetime.utcnow().isoformat(),  # Always update updated_at
                    tool_registry.discovered_by
                ))
                
                conn.commit()
                
                logger.debug("Tool registered successfully", extra={
                    "canonical_name": tool_registry.canonical_name,
                    "server_name": tool_registry.server_name,
                    "categories": tool_registry.categories
                })
                
                return True
                
        except Exception as e:
            logger.error("Failed to register tool", extra={
                "canonical_name": tool_registry.canonical_name,
                "error": str(e),
                "error_type": type(e).__name__
            })
            return False
    
    def get_tool(self, canonical_name: str) -> Optional[ToolRegistry]:
        """
        Get a tool by its canonical name.
        
        Args:
            canonical_name: Tool canonical name (server_name/tool_name)
            
        Returns:
            ToolRegistry object if found, None otherwise
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM tool_registry WHERE canonical_name = ?
                """, (canonical_name,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                return self._row_to_tool_registry(cursor, row)
                
        except Exception as e:
            logger.error("Failed to get tool", extra={
                "canonical_name": canonical_name,
                "error": str(e)
            })
            return None
    
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
        if filters is None:
            filters = SearchFilters()
        
        with performance_timer("tool_search", self.discovery_logger):
            try:
                with sqlite3.connect(str(self.db_path)) as conn:
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
                    
                    # Apply filters
                    if filters.server_name:
                        where_conditions.append("server_name = ?")
                        params.append(filters.server_name)
                    
                    if filters.server_type:
                        where_conditions.append("server_type = ?")
                        params.append(filters.server_type.value if hasattr(filters.server_type, 'value') else str(filters.server_type))
                    
                    if filters.available_only:
                        where_conditions.append("is_available = 1")
                    
                    if filters.min_success_rate is not None:
                        where_conditions.append("success_rate >= ?")
                        params.append(filters.min_success_rate)
                    
                    # Build final query
                    sql = "SELECT * FROM tool_registry"
                    if where_conditions:
                        sql += " WHERE " + " AND ".join(where_conditions)
                    
                    sql += " ORDER BY usage_count DESC, success_rate DESC LIMIT ?"
                    params.append(limit)
                    
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
                    
                    results = []
                    for row in rows:
                        tool_registry = self._row_to_tool_registry(cursor, row)
                        if tool_registry and self._matches_filters(tool_registry, filters):
                            results.append(ToolInfo(tool_registry))
                    
                    logger.debug("Tool search completed", extra={
                        "query": query,
                        "results_count": len(results),
                        "filters_applied": bool(filters.server_name or filters.server_type)
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
    
    def remove_server_tools(self, server_name: str) -> int:
        """
        Remove all tools for a server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            Number of tools removed
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # Count tools before deletion
                cursor.execute("SELECT COUNT(*) FROM tool_registry WHERE server_name = ?", (server_name,))
                tool_count = cursor.fetchone()[0]
                
                # Delete tools
                cursor.execute("DELETE FROM tool_registry WHERE server_name = ?", (server_name,))
                conn.commit()
                
                logger.info("Server tools removed", extra={
                    "server_name": server_name,
                    "tools_removed": tool_count
                })
                
                return tool_count
                
        except Exception as e:
            logger.error("Failed to remove server tools", extra={
                "server_name": server_name,
                "error": str(e)
            })
            return 0
    
    def update_tool_availability(self, server_name: str, is_available: bool) -> int:
        """
        Update availability status for all tools from a server.
        
        Args:
            server_name: Name of the server
            is_available: New availability status
            
        Returns:
            Number of tools updated
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE tool_registry 
                    SET is_available = ?, updated_at = ?
                    WHERE server_name = ?
                """, (is_available, datetime.utcnow().isoformat(), server_name))
                
                updated_count = cursor.rowcount
                conn.commit()
                
                logger.debug("Tool availability updated", extra={
                    "server_name": server_name,
                    "is_available": is_available,
                    "tools_updated": updated_count
                })
                
                return updated_count
                
        except Exception as e:
            logger.error("Failed to update tool availability", extra={
                "server_name": server_name,
                "error": str(e)
            })
            return 0
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive registry statistics.
        
        Returns:
            Dictionary with registry statistics
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
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
                
                return {
                    "total_tools": total_tools,
                    "available_tools": available_tools,
                    "unavailable_tools": total_tools - available_tools,
                    "servers_with_tools": servers_with_tools,
                    "server_type_distribution": server_type_distribution,
                    "category_distribution": category_counts,
                    "database_path": str(self.db_path),
                    "last_updated": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error("Failed to get registry stats", extra={
                "error": str(e)
            })
            return {"error": str(e)}
    
    def _row_to_tool_registry(self, cursor: sqlite3.Cursor, row: Tuple) -> Optional[ToolRegistry]:
        """Convert database row to ToolRegistry object."""
        try:
            # Get column names
            columns = [description[0] for description in cursor.description]
            row_dict = dict(zip(columns, row))
            
            # Parse JSON fields
            input_schema = json.loads(row_dict.get("input_schema", "{}"))
            output_schema = json.loads(row_dict.get("output_schema", "{}"))
            categories = json.loads(row_dict.get("categories", "[]"))
            tags = json.loads(row_dict.get("tags", "[]"))
            
            # Parse datetime fields
            last_discovered = datetime.fromisoformat(row_dict["last_discovered"])
            created_at = datetime.fromisoformat(row_dict["created_at"])
            updated_at = datetime.fromisoformat(row_dict["updated_at"])
            
            # Parse server type
            server_type_str = row_dict["server_type"]
            server_type = ServerType(server_type_str) if server_type_str in [st.value for st in ServerType] else ServerType.CUSTOM
            
            return ToolRegistry(
                id=row_dict["id"],
                name=row_dict["name"],
                canonical_name=row_dict["canonical_name"],
                description=row_dict["description"],
                server_name=row_dict["server_name"],
                server_type=server_type,
                input_schema=input_schema,
                output_schema=output_schema,
                categories=categories,
                tags=tags,
                last_discovered=last_discovered,
                is_available=bool(row_dict["is_available"]),
                usage_count=row_dict["usage_count"],
                success_rate=row_dict["success_rate"],
                average_response_time=row_dict["average_response_time"],
                created_at=created_at,
                updated_at=updated_at,
                discovered_by=row_dict["discovered_by"]
            )
            
        except Exception as e:
            logger.error("Failed to convert database row to ToolRegistry", extra={
                "error": str(e),
                "row_data": dict(zip([desc[0] for desc in cursor.description], row)) if row else None
            })
            return None
    
    def _matches_filters(self, tool: ToolRegistry, filters: SearchFilters) -> bool:
        """Check if tool matches additional filters not handled by SQL."""
        # Check categories filter
        if filters.categories:
            if not any(cat in tool.categories for cat in filters.categories):
                return False
        
        # Check tags filter  
        if filters.tags:
            if not any(tag in tool.tags for tag in filters.tags):
                return False
        
        return True