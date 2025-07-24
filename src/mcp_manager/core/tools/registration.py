"""
Tool registration operations for the MCP Manager tool registry.

Handles registration, retrieval, and modification of tool entries
in the registry database with proper error handling and logging.
"""

import json
import sqlite3
from datetime import datetime
from typing import Optional, Tuple

from mcp_manager.core.models import ServerType, ToolRegistry
from mcp_manager.core.tools.database_manager import DatabaseManager
from mcp_manager.core.tools.models import ToolNotFoundError, ToolRegistryError
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ToolRegistrationService:
    """Handles tool registration operations in the registry database."""
    
    def __init__(self, database_manager: DatabaseManager):
        """
        Initialize tool registration service.
        
        Args:
            database_manager: Database manager instance
        """
        self.db_manager = database_manager
        logger.debug("Tool registration service initialized")
    
    def register_tool(self, tool_registry: ToolRegistry) -> bool:
        """
        Register a tool in the registry.
        
        Args:
            tool_registry: Tool registry entry to store
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db_manager.get_connection() as conn:
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
            with self.db_manager.get_connection() as conn:
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
            with self.db_manager.get_connection() as conn:
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
    
    def remove_server_tools(self, server_name: str) -> int:
        """
        Remove all tools for a server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            Number of tools removed
        """
        try:
            with self.db_manager.get_connection() as conn:
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
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get current stats
                cursor.execute("""
                    SELECT usage_count, success_rate, average_response_time 
                    FROM tool_registry WHERE canonical_name = ?
                """, (canonical_name,))
                
                row = cursor.fetchone()
                if not row:
                    raise ToolNotFoundError(f"Tool not found: {canonical_name}")
                
                usage_count, success_rate, avg_response_time = row
                
                # Calculate new stats
                new_usage_count = usage_count + 1
                total_successes = int(usage_count * success_rate)
                if success:
                    total_successes += 1
                new_success_rate = total_successes / new_usage_count
                
                # Update average response time if provided
                new_avg_response_time = avg_response_time
                if response_time_ms is not None:
                    if usage_count == 0:
                        new_avg_response_time = response_time_ms
                    else:
                        new_avg_response_time = (
                            (avg_response_time * usage_count + response_time_ms) / new_usage_count
                        )
                
                # Update database
                cursor.execute("""
                    UPDATE tool_registry 
                    SET usage_count = ?, success_rate = ?, average_response_time = ?, updated_at = ?
                    WHERE canonical_name = ?
                """, (
                    new_usage_count,
                    new_success_rate,
                    new_avg_response_time,
                    datetime.utcnow().isoformat(),
                    canonical_name
                ))
                
                conn.commit()
                
                logger.debug("Tool usage updated", extra={
                    "canonical_name": canonical_name,
                    "success": success,
                    "new_usage_count": new_usage_count,
                    "new_success_rate": new_success_rate
                })
                
                return True
                
        except Exception as e:
            logger.error("Failed to update tool usage", extra={
                "canonical_name": canonical_name,
                "error": str(e)
            })
            return False
    
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