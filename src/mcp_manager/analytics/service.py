"""
Main orchestration service for usage analytics.

Provides the primary interface for analytics functionality,
coordinating between database, cleanup, query processing, and configuration.
"""

import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp_manager.analytics.cleanup import AnalyticsCleanup
from mcp_manager.analytics.config import AnalyticsConfig, AnalyticsConfigManager
from mcp_manager.analytics.database import AnalyticsDatabase
from mcp_manager.analytics.query_processor import QueryProcessor
from mcp_manager.core.models import (
    APIUsageAnalytics,
    RecommendationAnalytics,
    ServerAnalytics,
    ServerType,
    ToolUsageAnalytics,
)
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class UsageAnalyticsService:
    """Main orchestration service for usage analytics."""
    
    def __init__(self, config: Optional[AnalyticsConfig] = None, 
                 config_path: Optional[Path] = None):
        """
        Initialize analytics service.
        
        Args:
            config: Analytics configuration (optional)
            config_path: Path to configuration file (optional)
        """
        # Load configuration
        if config:
            self.config = config
        else:
            config_manager = AnalyticsConfigManager(config_path)
            self.config = config_manager.load_config()
        
        logger.info("Analytics service initializing", extra={
            "enabled": self.config.enabled,
            "db_path": str(self.config.db_path),
            "retention_days": self.config.retention_days
        })
        
        # Initialize components if analytics is enabled
        if self.config.enabled:
            self.database = AnalyticsDatabase(self.config.db_path)
            
            # Get database connection for other components
            self.db_connection = self.database.get_connection()
            
            self.query_processor = QueryProcessor(self.db_connection)
            self.cleanup = AnalyticsCleanup(
                self.db_connection, 
                self.config.retention_days
            )
        else:
            self.database = None
            self.db_connection = None
            self.query_processor = None
            self.cleanup = None
            
            logger.info("Analytics service disabled via configuration")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close database connection."""
        if self.db_connection:
            self.db_connection.close()
    
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
        if not self.config.enabled or not self.config.is_feature_enabled("tool_usage"):
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
            
            # Record in database
            success_db = self.database.record_tool_usage(usage_analytics)
            
            # Update query patterns if enabled
            if self.config.is_feature_enabled("query_patterns"):
                self.query_processor.update_query_patterns(
                    user_query, canonical_name if selected else None, success
                )
            
            logger.debug("Tool usage recorded", extra={
                "tool": canonical_name,
                "selected": selected,
                "success": success,
                "response_time": response_time_ms
            })
            
            return success_db
            
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
        if not self.config.enabled or not self.config.is_feature_enabled("recommendations"):
            return True
        
        try:
            # Categorize query
            query_category = self.query_processor.categorize_query(user_query)
            
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
            
            success = self.database.record_recommendation_analytics(analytics)
            
            logger.debug("Recommendation analytics recorded", extra={
                "session_id": session_id,
                "recommendations": recommendations_count,
                "provider": llm_provider,
                "processing_time": processing_time_ms
            })
            
            return success
            
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
        if not self.config.enabled or not self.config.is_feature_enabled("server_analytics"):
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
            
            success = self.database.record_server_analytics(analytics)
            
            logger.debug("Server analytics recorded", extra={
                "server": server_name,
                "total_tools": total_tools,
                "requests": total_requests,
                "success_rate": successful_requests / max(total_requests, 1)
            })
            
            return success
            
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
        if not self.config.enabled or not self.config.is_feature_enabled("api_usage"):
            return True
        
        try:
            # Optionally anonymize client IP based on config
            if client_ip and not self.config.store_client_ips:
                client_ip = None
            
            success = self.database.record_api_usage(
                endpoint, method, success, response_time_ms,
                data_bytes, client_ip, rate_limited
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to record API usage: {e}")
            return False
    
    def get_usage_summary(self, days: int = None) -> Dict[str, Any]:
        """
        Get usage summary for the specified number of days.
        
        Args:
            days: Number of days to analyze (uses config default if None)
            
        Returns:
            Dictionary with usage summary statistics
        """
        if not self.config.enabled:
            return {"status": "disabled"}
        
        if days is None:
            days = self.config.summary_default_days
        
        try:
            since_date = datetime.utcnow() - timedelta(days=days)
            stats = self.database.get_usage_statistics(since_date)
            stats["period_days"] = days
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get usage summary: {e}")
            return {"error": str(e)}
    
    def get_trending_queries(self, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get trending query patterns.
        
        Args:
            limit: Maximum number of results (uses config default if None)
            
        Returns:
            List of trending query information
        """
        if not self.config.enabled or not self.config.is_feature_enabled("query_patterns"):
            return []
        
        if limit is None:
            limit = self.config.trending_query_limit
        
        try:
            return self.query_processor.get_trending_queries(limit)
            
        except Exception as e:
            logger.error(f"Failed to get trending queries: {e}")
            return []
    
    def get_query_categories(self) -> Dict[str, int]:
        """
        Get query category distribution.
        
        Returns:
            Dictionary mapping categories to frequency counts
        """
        if not self.config.enabled or not self.config.is_feature_enabled("query_patterns"):
            return {}
        
        try:
            return self.query_processor.get_query_categories()
            
        except Exception as e:
            logger.error(f"Failed to get query categories: {e}")
            return {}
    
    def cleanup_old_data(self) -> Dict[str, int]:
        """
        Clean up old analytics data based on retention policy.
        
        Returns:
            Dictionary with cleanup statistics
        """
        if not self.config.enabled:
            return {"status": "disabled"}
        
        try:
            cleanup_stats = self.cleanup.cleanup_old_data()
            
            # Optimize database after cleanup if significant data was removed
            total_deleted = sum(
                v for k, v in cleanup_stats.items() 
                if k.endswith("_deleted") and isinstance(v, int)
            )
            
            if total_deleted > 1000:  # Threshold for optimization
                optimization_stats = self.cleanup.optimize_database()
                cleanup_stats.update(optimization_stats)
            
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return {"error": str(e)}
    
    def perform_maintenance(self) -> Dict[str, Any]:
        """
        Perform comprehensive maintenance operations.
        
        Returns:
            Dictionary with maintenance statistics
        """
        if not self.config.enabled:
            return {"status": "disabled"}
        
        try:
            maintenance_stats = {}
            
            # Get database stats before maintenance
            db_stats = self.cleanup.get_database_stats()
            maintenance_stats["before"] = db_stats
            
            # Cleanup old data
            cleanup_stats = self.cleanup_old_data()
            maintenance_stats["cleanup"] = cleanup_stats
            
            # Archive data if enabled and needed
            if self.config.archive_enabled:
                db_size_mb = db_stats.get("database_size_mb", 0)
                if self.config.should_archive_now(db_size_mb):
                    archive_stats = self.cleanup.archive_old_data(
                        self.config.archive_path,
                        self.config.archive_after_days
                    )
                    maintenance_stats["archive"] = archive_stats
            
            # Optimize database
            optimization_stats = self.cleanup.optimize_database()
            maintenance_stats["optimization"] = optimization_stats
            
            # Get database stats after maintenance
            db_stats_after = self.cleanup.get_database_stats()
            maintenance_stats["after"] = db_stats_after
            
            logger.info("Analytics maintenance completed", extra=maintenance_stats)
            return maintenance_stats
            
        except Exception as e:
            logger.error(f"Failed to perform maintenance: {e}")
            return {"error": str(e)}
    
    def get_system_health(self) -> Dict[str, Any]:
        """
        Get analytics system health information.
        
        Returns:
            Dictionary with system health data
        """
        if not self.config.enabled:
            return {"status": "disabled"}
        
        try:
            health = {
                "status": "healthy",
                "config": self.config.to_dict(),
                "database": self.cleanup.get_database_stats(),
                "features": self.config.get_feature_flags(),
            }
            
            # Check for any health issues
            db_size_mb = health["database"].get("database_size_mb", 0)
            if db_size_mb > self.config.max_database_size_mb:
                health["warnings"] = health.get("warnings", [])
                health["warnings"].append(
                    f"Database size ({db_size_mb:.1f}MB) exceeds maximum ({self.config.max_database_size_mb}MB)"
                )
                
                if health["status"] == "healthy":
                    health["status"] = "warning"
            
            return health
            
        except Exception as e:
            logger.error(f"Failed to get system health: {e}")
            return {"status": "error", "error": str(e)}