"""
Comprehensive usage analytics service for MCP Manager.

Tracks tool usage, server performance, query patterns, and provides
insights for optimization and user experience improvement.
"""

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mcp_manager.core.migrations.manager import MigrationManager
from mcp_manager.core.models import (
    APIUsageAnalytics,
    QueryPattern,
    RecommendationAnalytics,
    ServerAnalytics,
    ServerType,
    ToolUsageAnalytics,
)
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class UsageAnalyticsService:
    """Comprehensive service for tracking and analyzing MCP tool usage."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize usage analytics service.
        
        Args:
            db_path: Path to SQLite database. If None, uses default from environment.
        """
        if db_path is None:
            db_path = self._get_default_db_path()
        
        self.db_path = db_path
        
        # Configuration from environment
        self.analytics_enabled = os.getenv("MCP_ANALYTICS_ENABLED", "true").lower() == "true"
        self.retention_days = int(os.getenv("MCP_ANALYTICS_RETENTION_DAYS", "90"))
        self.aggregation_interval_hours = int(os.getenv("MCP_ANALYTICS_AGGREGATION_HOURS", "1"))
        
        logger.info("Usage analytics service initialized", extra={
            "db_path": str(self.db_path),
            "analytics_enabled": self.analytics_enabled,
            "retention_days": self.retention_days,
            "aggregation_interval": self.aggregation_interval_hours
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
                logger.info(f"Running {len(pending)} pending analytics migrations")
                success = migration_manager.run_pending_migrations()
                if not success:
                    raise Exception("Failed to apply analytics migrations")
            
        except Exception as e:
            logger.error(f"Analytics database initialization failed: {e}")
            raise
    
    def record_tool_usage(self, canonical_name: str, user_query: str, selected: bool,
                        success: bool, response_time_ms: int, error_details: Optional[str] = None,
                        context: Optional[Dict[str, Any]] = None, session_id: Optional[str] = None) -> bool:
        """
        Record tool usage analytics.
        
        Args:
            canonical_name: Tool canonical name (server/tool)
            user_query: Original user query
            selected: Whether tool was selected by user
            success: Whether execution was successful
            response_time_ms: Response time in milliseconds
            error_details: Error details if failed
            context: Additional context information
            session_id: User session identifier
            
        Returns:
            True if recorded successfully
        """
        if not self.analytics_enabled:
            return True
        
        try:
            # Generate session ID if not provided
            if not session_id:
                session_id = str(uuid.uuid4())
            
            usage_analytics = ToolUsageAnalytics(
                tool_canonical_name=canonical_name,
                user_query=user_query,
                selected=selected,
                success=success,
                response_time_ms=response_time_ms,
                error_details=error_details,
                context=context or {},
                session_id=session_id
            )
            
            with sqlite3.connect(str(self.db_path)) as conn:
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
            
            # Update query patterns
            self._update_query_patterns(user_query, canonical_name if selected else None, success)
            
            logger.debug("Tool usage recorded", extra={
                "tool": canonical_name,
                "selected": selected,
                "success": success,
                "response_time": response_time_ms
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to record tool usage: {e}")
            return False
    
    def record_recommendation_analytics(self, session_id: str, user_query: str,
                                      recommendations_count: int, llm_provider: str,
                                      model_used: str, processing_time_ms: int,
                                      tools_analyzed: int, user_selected_tool: Optional[str] = None,
                                      user_satisfaction_score: Optional[float] = None,
                                      context_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Record AI recommendation analytics.
        
        Args:
            session_id: Recommendation session ID
            user_query: Original user query
            recommendations_count: Number of recommendations provided
            llm_provider: LLM provider used
            model_used: Specific model used
            processing_time_ms: Total processing time
            tools_analyzed: Number of tools analyzed
            user_selected_tool: Tool user actually selected
            user_satisfaction_score: User satisfaction score (0-1)
            context_data: Request context data
            
        Returns:
            True if recorded successfully
        """
        if not self.analytics_enabled:
            return True
        
        try:
            # Infer query category
            query_category = self._categorize_query(user_query)
            
            analytics = RecommendationAnalytics(
                session_id=session_id,
                user_query=user_query,
                query_category=query_category,
                recommendations_count=recommendations_count,
                llm_provider=llm_provider,
                model_used=model_used,
                processing_time_ms=processing_time_ms,
                tools_analyzed=tools_analyzed,
                user_selected_tool=user_selected_tool,
                user_satisfaction_score=user_satisfaction_score,
                context_data=context_data or {}
            )
            
            with sqlite3.connect(str(self.db_path)) as conn:
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
                "session_id": session_id,
                "recommendations": recommendations_count,
                "provider": llm_provider,
                "processing_time": processing_time_ms
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to record recommendation analytics: {e}")
            return False
    
    def record_server_analytics(self, server_name: str, server_type: ServerType,
                              total_tools: int, active_tools: int, total_requests: int,
                              successful_requests: int, average_response_time_ms: float,
                              peak_concurrent_usage: int = 0, uptime_percentage: float = 1.0,
                              error_rate: float = 0.0, discovery_success_rate: float = 1.0) -> bool:
        """
        Record or update daily server analytics.
        
        Args:
            server_name: Server name
            server_type: Server type
            total_tools: Total tools available
            active_tools: Tools used at least once
            total_requests: Total tool requests
            successful_requests: Successful requests
            average_response_time_ms: Average response time
            peak_concurrent_usage: Peak concurrent usage
            uptime_percentage: Server uptime percentage
            error_rate: Error rate (0-1)
            discovery_success_rate: Tool discovery success rate
            
        Returns:
            True if recorded successfully
        """
        if not self.analytics_enabled:
            return True
        
        try:
            # Use today's date for daily aggregation
            date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            analytics = ServerAnalytics(
                server_name=server_name,
                server_type=server_type,
                date=date,
                total_tools=total_tools,
                active_tools=active_tools,
                total_requests=total_requests,
                successful_requests=successful_requests,
                average_response_time_ms=average_response_time_ms,
                peak_concurrent_usage=peak_concurrent_usage,
                uptime_percentage=uptime_percentage,
                error_rate=error_rate,
                discovery_success_rate=discovery_success_rate
            )
            
            with sqlite3.connect(str(self.db_path)) as conn:
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
                "server": server_name,
                "total_tools": total_tools,
                "requests": total_requests,
                "success_rate": successful_requests / max(total_requests, 1)
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to record server analytics: {e}")
            return False
    
    def record_api_usage(self, endpoint: str, method: str, success: bool,
                        response_time_ms: int, data_bytes: int = 0,
                        client_ip: Optional[str] = None, rate_limited: bool = False) -> bool:
        """
        Record API endpoint usage analytics.
        
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
        if not self.analytics_enabled:
            return True
        
        try:
            # Use hourly aggregation
            date = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
            
            with sqlite3.connect(str(self.db_path)) as conn:
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
                    # Update existing record
                    req_count, succ_count, err_count, avg_resp_time, max_resp_time, data_transferred, unique_clients, rate_limited_count = existing
                    
                    new_req_count = req_count + 1
                    new_succ_count = succ_count + (1 if success else 0)
                    new_err_count = err_count + (0 if success else 1)
                    
                    # Calculate new average response time
                    new_avg_resp_time = ((avg_resp_time * req_count) + response_time_ms) / new_req_count
                    new_max_resp_time = max(max_resp_time, response_time_ms)
                    
                    new_data_transferred = data_transferred + data_bytes
                    new_rate_limited_count = rate_limited_count + (1 if rate_limited else 0)
                    
                    # For unique clients, we'd need to track IPs separately - simplified here
                    new_unique_clients = unique_clients  # Would need proper tracking
                    
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
                        new_unique_clients, new_rate_limited_count,
                        datetime.utcnow().isoformat(),
                        endpoint, method, date.isoformat()
                    ))
                    
                else:
                    # Create new record
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
                
                conn.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to record API usage: {e}")
            return False
    
    def get_usage_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get usage summary for the specified number of days.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with usage summary statistics
        """
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # Tool usage summary
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
                
                # Recommendation summary
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
                
                # Server performance summary
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
                    "period_days": days,
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
            logger.error(f"Failed to get usage summary: {e}")
            return {"error": str(e)}
    
    def get_trending_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get trending query patterns.
        
        Args:
            limit: Maximum number of results
            
        Returns:
            List of trending query information
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT query_category, frequency, success_rate, 
                           average_recommendation_count, most_selected_tools,
                           trending_score, last_seen
                    FROM query_patterns 
                    ORDER BY trending_score DESC, frequency DESC
                    LIMIT ?
                """, (limit,))
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        "category": row[0],
                        "frequency": row[1],
                        "success_rate": row[2],
                        "avg_recommendations": row[3],
                        "popular_tools": json.loads(row[4]) if row[4] else [],
                        "trending_score": row[5],
                        "last_seen": row[6]
                    })
                
                return results
                
        except Exception as e:
            logger.error(f"Failed to get trending queries: {e}")
            return []
    
    def _update_query_patterns(self, query: str, selected_tool: Optional[str], success: bool) -> None:
        """Update query pattern analytics."""
        try:
            # Hash query for privacy
            query_hash = hashlib.sha256(query.encode()).hexdigest()
            category = self._categorize_query(query)
            keywords = self._extract_keywords(query)
            
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # Get existing pattern
                cursor.execute("""
                    SELECT frequency, success_rate, most_selected_tools, average_recommendation_count
                    FROM query_patterns WHERE query_hash = ?
                """, (query_hash,))
                
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing pattern
                    freq, succ_rate, tools_json, avg_rec = existing
                    most_tools = json.loads(tools_json) if tools_json else []
                    
                    new_freq = freq + 1
                    new_succ_rate = ((succ_rate * freq) + (1 if success else 0)) / new_freq
                    
                    # Update most selected tools
                    if selected_tool and selected_tool not in most_tools:
                        most_tools.append(selected_tool)
                        if len(most_tools) > 5:  # Keep top 5
                            most_tools = most_tools[-5:]
                    
                    # Calculate trending score (recent activity weighted)
                    trending_score = new_freq * 0.7 + new_succ_rate * 0.3
                    
                    cursor.execute("""
                        UPDATE query_patterns SET
                            frequency = ?, success_rate = ?, most_selected_tools = ?,
                            last_seen = ?, trending_score = ?
                        WHERE query_hash = ?
                    """, (
                        new_freq, new_succ_rate, json.dumps(most_tools),
                        datetime.utcnow().isoformat(), trending_score, query_hash
                    ))
                    
                else:
                    # Create new pattern
                    tools_list = [selected_tool] if selected_tool else []
                    
                    cursor.execute("""
                        INSERT INTO query_patterns (
                            query_hash, query_category, query_keywords, frequency,
                            success_rate, most_selected_tools, trending_score
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        query_hash, category, json.dumps(keywords), 1,
                        1.0 if success else 0.0, json.dumps(tools_list), 1.0
                    ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to update query patterns: {e}")
    
    def _categorize_query(self, query: str) -> str:
        """Categorize a user query."""
        query_lower = query.lower()
        
        # Simple rule-based categorization
        if any(word in query_lower for word in ["file", "directory", "folder", "path"]):
            return "filesystem"
        elif any(word in query_lower for word in ["search", "find", "lookup"]):
            return "search"
        elif any(word in query_lower for word in ["database", "sql", "query", "table"]):
            return "database"
        elif any(word in query_lower for word in ["web", "http", "api", "request"]):
            return "web"
        elif any(word in query_lower for word in ["git", "github", "repo", "commit"]):
            return "development"
        elif any(word in query_lower for word in ["automate", "script", "run", "execute"]):
            return "automation"
        else:
            return "general"
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract keywords from a query."""
        import re
        
        # Simple keyword extraction
        words = re.findall(r'\b\w+\b', query.lower())
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        return keywords[:10]  # Limit to 10 keywords
    
    def cleanup_old_data(self) -> Dict[str, int]:
        """
        Clean up old analytics data based on retention policy.
        
        Returns:
            Dictionary with cleanup statistics
        """
        if not self.analytics_enabled:
            return {"status": "disabled"}
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
            cleanup_stats = {}
            
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # Clean up old tool usage analytics
                cursor.execute("DELETE FROM tool_usage_analytics WHERE timestamp < ?", (cutoff_date.isoformat(),))
                cleanup_stats["tool_usage_deleted"] = cursor.rowcount
                
                # Clean up old recommendation analytics
                cursor.execute("DELETE FROM recommendation_analytics WHERE timestamp < ?", (cutoff_date.isoformat(),))
                cleanup_stats["recommendation_deleted"] = cursor.rowcount
                
                # Clean up old server analytics
                cursor.execute("DELETE FROM server_analytics WHERE date < ?", (cutoff_date.date().isoformat(),))
                cleanup_stats["server_analytics_deleted"] = cursor.rowcount
                
                # Clean up old API usage analytics
                cursor.execute("DELETE FROM api_usage_analytics WHERE date < ?", (cutoff_date.isoformat(),))
                cleanup_stats["api_usage_deleted"] = cursor.rowcount
                
                # Clean up unused query patterns (not seen in retention period)
                cursor.execute("DELETE FROM query_patterns WHERE last_seen < ?", (cutoff_date.isoformat(),))
                cleanup_stats["query_patterns_deleted"] = cursor.rowcount
                
                conn.commit()
            
            logger.info("Analytics data cleanup completed", extra=cleanup_stats)
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return {"error": str(e)}