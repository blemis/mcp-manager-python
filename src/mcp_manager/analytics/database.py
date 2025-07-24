"""
Database operations for usage analytics.

Handles database connections, migrations, and core data operations
for the MCP Manager analytics system.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mcp_manager.core.migrations.manager import MigrationManager
from mcp_manager.core.models import (
    APIUsageAnalytics,
    RecommendationAnalytics,
    ServerAnalytics,
    ServerType,
    ToolUsageAnalytics,
)
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class AnalyticsDatabase:
    """Handles database operations for analytics data."""
    
    def __init__(self, db_path: Path):
        """
        Initialize analytics database handler.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_database_ready()
    
    def _ensure_database_ready(self) -> None:
        """Ensure database exists and migrations are applied."""
        try:
            # Ensure parent directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            migration_manager = MigrationManager(self.db_path)
            
            # Check if we need to run migrations
            pending = migration_manager.get_pending_migrations()
            if pending:
                logger.info(f"Running {len(pending)} pending analytics migrations")
                success = migration_manager.run_pending_migrations()
                if not success:
                    raise Exception("Failed to apply analytics migrations")
            
            logger.debug("Analytics database ready", extra={
                "db_path": str(self.db_path)
            })
            
        except Exception as e:
            logger.error(f"Analytics database initialization failed: {e}")
            raise
    
    def get_connection(self) -> sqlite3.Connection:
        """
        Get a database connection.
        
        Returns:
            SQLite connection object
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            # Enable foreign keys and optimize for analytics workload
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to analytics database: {e}")
            raise
    
    def record_tool_usage(self, usage_analytics: ToolUsageAnalytics) -> bool:
        """
        Record tool usage analytics.
        
        Args:
            usage_analytics: Tool usage analytics data
            
        Returns:
            True if recorded successfully
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO tool_usage_analytics (
                        tool_canonical_name, user_query, selected, success, 
                        timestamp, context, response_time_ms, error_details, session_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    usage_analytics.tool_canonical_name,
                    usage_analytics.user_query,
                    usage_analytics.selected,
                    usage_analytics.success,
                    usage_analytics.timestamp.isoformat(),
                    json.dumps(usage_analytics.context),
                    usage_analytics.response_time_ms,
                    usage_analytics.error_details,
                    usage_analytics.session_id
                ))
                
                conn.commit()
            
            logger.debug("Tool usage recorded", extra={
                "tool": usage_analytics.tool_canonical_name,
                "selected": usage_analytics.selected,
                "success": usage_analytics.success
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to record tool usage: {e}")
            return False
    
    def record_recommendation_analytics(self, analytics: RecommendationAnalytics) -> bool:
        """
        Record AI recommendation analytics.
        
        Args:
            analytics: Recommendation analytics data
            
        Returns:
            True if recorded successfully
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO recommendation_analytics (
                        session_id, user_query, query_category, recommendations_count,
                        llm_provider, model_used, processing_time_ms, tools_analyzed,
                        user_selected_tool, user_satisfaction_score, timestamp, context_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    analytics.session_id,
                    analytics.user_query,
                    analytics.query_category,
                    analytics.recommendations_count,
                    analytics.llm_provider,
                    analytics.model_used,
                    analytics.processing_time_ms,
                    analytics.tools_analyzed,
                    analytics.user_selected_tool,
                    analytics.user_satisfaction_score,
                    analytics.timestamp.isoformat(),
                    json.dumps(analytics.context_data)
                ))
                
                conn.commit()
            
            logger.debug("Recommendation analytics recorded", extra={
                "session_id": analytics.session_id,
                "recommendations": analytics.recommendations_count,
                "provider": analytics.llm_provider
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to record recommendation analytics: {e}")
            return False
    
    def record_server_analytics(self, analytics: ServerAnalytics) -> bool:
        """
        Record or update daily server analytics.
        
        Args:
            analytics: Server analytics data
            
        Returns:
            True if recorded successfully
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Use INSERT OR REPLACE for daily aggregation
                cursor.execute("""
                    INSERT OR REPLACE INTO server_analytics (
                        server_name, server_type, date, total_tools, active_tools,
                        total_requests, successful_requests, average_response_time_ms,
                        peak_concurrent_usage, uptime_percentage, error_rate,
                        discovery_success_rate, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    analytics.server_name,
                    analytics.server_type.value,
                    analytics.date.isoformat(),
                    analytics.total_tools,
                    analytics.active_tools,
                    analytics.total_requests,
                    analytics.successful_requests,
                    analytics.average_response_time_ms,
                    analytics.peak_concurrent_usage,
                    analytics.uptime_percentage,
                    analytics.error_rate,
                    analytics.discovery_success_rate,
                    analytics.last_updated.isoformat()
                ))
                
                conn.commit()
            
            logger.debug("Server analytics recorded", extra={
                "server": analytics.server_name,
                "total_tools": analytics.total_tools,
                "requests": analytics.total_requests
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to record server analytics: {e}")
            return False
    
    def record_api_usage(self, endpoint: str, method: str, success: bool,
                        response_time_ms: int, data_bytes: int = 0,
                        client_ip: Optional[str] = None, 
                        rate_limited: bool = False) -> bool:
        """
        Record API endpoint usage analytics with hourly aggregation.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method
            success: Whether request was successful
            response_time_ms: Response time in milliseconds
            data_bytes: Data transferred in bytes
            client_ip: Client IP address (for unique client tracking)
            rate_limited: Whether request was rate limited
            
        Returns:
            True if recorded successfully
        """
        try:
            # Use hourly aggregation
            date = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get existing record for this hour
                cursor.execute("""
                    SELECT request_count, success_count, error_count, 
                           average_response_time_ms, max_response_time_ms,
                           data_transferred_bytes, unique_clients, rate_limited_requests
                    FROM api_usage_analytics 
                    WHERE endpoint = ? AND method = ? AND date = ?
                """, (endpoint, method, date.isoformat()))
                
                existing = cursor.fetchone()
                
                if existing:
                    self._update_api_usage_record(
                        cursor, endpoint, method, date, existing,
                        success, response_time_ms, data_bytes, rate_limited
                    )
                else:
                    self._create_api_usage_record(
                        cursor, endpoint, method, date, success,
                        response_time_ms, data_bytes, client_ip, rate_limited
                    )
                
                conn.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to record API usage: {e}")
            return False
    
    def _update_api_usage_record(self, cursor: sqlite3.Cursor, endpoint: str,
                               method: str, date: datetime, existing: tuple,
                               success: bool, response_time_ms: int,
                               data_bytes: int, rate_limited: bool) -> None:
        """Update existing API usage record."""
        (req_count, succ_count, err_count, avg_resp_time, max_resp_time,
         data_transferred, unique_clients, rate_limited_count) = existing
        
        new_req_count = req_count + 1
        new_succ_count = succ_count + (1 if success else 0)
        new_err_count = err_count + (0 if success else 1)
        
        # Calculate new average response time
        new_avg_resp_time = ((avg_resp_time * req_count) + response_time_ms) / new_req_count
        new_max_resp_time = max(max_resp_time, response_time_ms)
        
        new_data_transferred = data_transferred + data_bytes
        new_rate_limited_count = rate_limited_count + (1 if rate_limited else 0)
        
        cursor.execute("""
            UPDATE api_usage_analytics SET
                request_count = ?, success_count = ?, error_count = ?,
                average_response_time_ms = ?, max_response_time_ms = ?,
                data_transferred_bytes = ?, unique_clients = ?,
                rate_limited_requests = ?, last_updated = ?
            WHERE endpoint = ? AND method = ? AND date = ?
        """, (
            new_req_count, new_succ_count, new_err_count,
            new_avg_resp_time, new_max_resp_time, new_data_transferred,
            unique_clients, new_rate_limited_count,
            datetime.utcnow().isoformat(),
            endpoint, method, date.isoformat()
        ))
    
    def _create_api_usage_record(self, cursor: sqlite3.Cursor, endpoint: str,
                               method: str, date: datetime, success: bool,
                               response_time_ms: int, data_bytes: int,
                               client_ip: Optional[str], rate_limited: bool) -> None:
        """Create new API usage record."""
        cursor.execute("""
            INSERT INTO api_usage_analytics (
                endpoint, method, date, request_count, success_count, error_count,
                average_response_time_ms, max_response_time_ms, data_transferred_bytes,
                unique_clients, rate_limited_requests, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            endpoint, method, date.isoformat(),
            1, 1 if success else 0, 0 if success else 1,
            float(response_time_ms), response_time_ms, data_bytes,
            1 if client_ip else 0, 1 if rate_limited else 0,
            datetime.utcnow().isoformat()
        ))
    
    def get_usage_statistics(self, since_date: datetime) -> Dict[str, any]:
        """
        Get comprehensive usage statistics since the given date.
        
        Args:
            since_date: Start date for statistics
            
        Returns:
            Dictionary with usage statistics
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Tool usage statistics
                cursor.execute("""
                    SELECT COUNT(*) as total_usage,
                           COUNT(CASE WHEN selected = 1 THEN 1 END) as tools_selected,
                           COUNT(CASE WHEN success = 1 THEN 1 END) as successful_usage,
                           AVG(response_time_ms) as avg_response_time,
                           COUNT(DISTINCT tool_canonical_name) as unique_tools_used,
                           COUNT(DISTINCT session_id) as unique_sessions
                    FROM tool_usage_analytics 
                    WHERE timestamp >= ?
                """, (since_date.isoformat(),))
                
                tool_stats = cursor.fetchone()
                
                # Recommendation statistics
                cursor.execute("""
                    SELECT COUNT(*) as total_recommendations,
                           AVG(recommendations_count) as avg_recommendations_per_query,
                           AVG(processing_time_ms) as avg_processing_time,
                           COUNT(DISTINCT llm_provider) as providers_used,
                           COUNT(CASE WHEN user_selected_tool IS NOT NULL THEN 1 END) as selections_made
                    FROM recommendation_analytics 
                    WHERE timestamp >= ?
                """, (since_date.isoformat(),))
                
                rec_stats = cursor.fetchone()
                
                # Server performance statistics
                cursor.execute("""
                    SELECT COUNT(DISTINCT server_name) as active_servers,
                           AVG(uptime_percentage) as avg_uptime,
                           AVG(error_rate) as avg_error_rate,
                           SUM(total_requests) as total_server_requests
                    FROM server_analytics 
                    WHERE date >= ?
                """, (since_date.date().isoformat(),))
                
                server_stats = cursor.fetchone()
                
                return {
                    "tool_usage": {
                        "total_usage": tool_stats[0] or 0,
                        "tools_selected": tool_stats[1] or 0,
                        "successful_usage": tool_stats[2] or 0,
                        "success_rate": (tool_stats[2] or 0) / max(tool_stats[0] or 1, 1),
                        "avg_response_time_ms": tool_stats[3] or 0,
                        "unique_tools_used": tool_stats[4] or 0,
                        "unique_sessions": tool_stats[5] or 0
                    },
                    "recommendations": {
                        "total_recommendations": rec_stats[0] or 0,
                        "avg_recommendations_per_query": rec_stats[1] or 0,
                        "avg_processing_time_ms": rec_stats[2] or 0,
                        "providers_used": rec_stats[3] or 0,
                        "selection_rate": (rec_stats[4] or 0) / max(rec_stats[0] or 1, 1)
                    },
                    "servers": {
                        "active_servers": server_stats[0] or 0,
                        "avg_uptime_percentage": server_stats[1] or 1.0,
                        "avg_error_rate": server_stats[2] or 0.0,
                        "total_requests": server_stats[3] or 0
                    }
                }
                
        except Exception as e:
            logger.error(f"Failed to get usage statistics: {e}")
            return {"error": str(e)}
    
    def vacuum_database(self) -> bool:
        """
        Vacuum the database to optimize performance.
        
        Returns:
            True if vacuum was successful
        """
        try:
            with self.get_connection() as conn:
                conn.execute("VACUUM")
                conn.commit()
            
            logger.info("Database vacuum completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to vacuum database: {e}")
            return False