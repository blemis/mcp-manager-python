"""
Data maintenance and retention for usage analytics.

Handles cleanup of old analytics data, database optimization,
and retention policy enforcement for the MCP Manager analytics system.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class AnalyticsCleanup:
    """Handles data cleanup and retention for analytics database."""
    
    def __init__(self, db_connection: sqlite3.Connection, retention_days: int = 90):
        """
        Initialize analytics cleanup handler.
        
        Args:
            db_connection: SQLite database connection
            retention_days: Number of days to retain data
        """
        self.db_connection = db_connection
        self.retention_days = retention_days
    
    def cleanup_old_data(self) -> Dict[str, int]:
        """
        Clean up old analytics data based on retention policy.
        
        Returns:
            Dictionary with cleanup statistics
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
            cleanup_stats = {}
            
            cursor = self.db_connection.cursor()
            
            # Clean up old tool usage analytics
            deleted_tool_usage = self._cleanup_tool_usage_analytics(cursor, cutoff_date)
            cleanup_stats["tool_usage_deleted"] = deleted_tool_usage
            
            # Clean up old recommendation analytics
            deleted_recommendations = self._cleanup_recommendation_analytics(cursor, cutoff_date)
            cleanup_stats["recommendation_deleted"] = deleted_recommendations
            
            # Clean up old server analytics
            deleted_server = self._cleanup_server_analytics(cursor, cutoff_date)
            cleanup_stats["server_analytics_deleted"] = deleted_server
            
            # Clean up old API usage analytics
            deleted_api = self._cleanup_api_usage_analytics(cursor, cutoff_date)
            cleanup_stats["api_usage_deleted"] = deleted_api
            
            # Clean up unused query patterns
            deleted_patterns = self._cleanup_query_patterns(cursor, cutoff_date)
            cleanup_stats["query_patterns_deleted"] = deleted_patterns
            
            self.db_connection.commit()
            
            logger.info("Analytics data cleanup completed", extra=cleanup_stats)
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            self.db_connection.rollback()
            return {"error": str(e)}
    
    def _cleanup_tool_usage_analytics(self, cursor: sqlite3.Cursor, 
                                    cutoff_date: datetime) -> int:
        """Clean up old tool usage analytics."""
        cursor.execute(
            "DELETE FROM tool_usage_analytics WHERE timestamp < ?",
            (cutoff_date.isoformat(),)
        )
        deleted_count = cursor.rowcount
        
        logger.debug(f"Cleaned up {deleted_count} old tool usage records")
        return deleted_count
    
    def _cleanup_recommendation_analytics(self, cursor: sqlite3.Cursor,
                                        cutoff_date: datetime) -> int:
        """Clean up old recommendation analytics."""
        cursor.execute(
            "DELETE FROM recommendation_analytics WHERE timestamp < ?",
            (cutoff_date.isoformat(),)
        )
        deleted_count = cursor.rowcount
        
        logger.debug(f"Cleaned up {deleted_count} old recommendation records")
        return deleted_count
    
    def _cleanup_server_analytics(self, cursor: sqlite3.Cursor,
                                cutoff_date: datetime) -> int:
        """Clean up old server analytics."""
        cursor.execute(
            "DELETE FROM server_analytics WHERE date < ?",
            (cutoff_date.date().isoformat(),)
        )
        deleted_count = cursor.rowcount
        
        logger.debug(f"Cleaned up {deleted_count} old server analytics records")
        return deleted_count
    
    def _cleanup_api_usage_analytics(self, cursor: sqlite3.Cursor,
                                   cutoff_date: datetime) -> int:
        """Clean up old API usage analytics."""
        cursor.execute(
            "DELETE FROM api_usage_analytics WHERE date < ?",
            (cutoff_date.isoformat(),)
        )
        deleted_count = cursor.rowcount
        
        logger.debug(f"Cleaned up {deleted_count} old API usage records")
        return deleted_count
    
    def _cleanup_query_patterns(self, cursor: sqlite3.Cursor,
                              cutoff_date: datetime) -> int:
        """Clean up unused query patterns."""
        cursor.execute(
            "DELETE FROM query_patterns WHERE last_seen < ?",
            (cutoff_date.isoformat(),)
        )
        deleted_count = cursor.rowcount
        
        logger.debug(f"Cleaned up {deleted_count} old query patterns")
        return deleted_count
    
    def archive_old_data(self, archive_path: Path, 
                        archive_cutoff_days: int = 30) -> Dict[str, int]:
        """
        Archive old data to separate database before cleanup.
        
        Args:
            archive_path: Path to archive database
            archive_cutoff_days: Days of data to archive
            
        Returns:
            Dictionary with archive statistics
        """
        try:
            archive_cutoff = datetime.utcnow() - timedelta(days=archive_cutoff_days)
            archive_stats = {}
            
            # Create archive database connection
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            archive_conn = sqlite3.connect(str(archive_path))
            
            # Copy schema to archive database
            self._copy_schema_to_archive(archive_conn)
            
            # Archive each table
            archived_tool_usage = self._archive_tool_usage(archive_conn, archive_cutoff)
            archive_stats["tool_usage_archived"] = archived_tool_usage
            
            archived_recommendations = self._archive_recommendations(archive_conn, archive_cutoff)
            archive_stats["recommendations_archived"] = archived_recommendations
            
            archived_server = self._archive_server_analytics(archive_conn, archive_cutoff)
            archive_stats["server_analytics_archived"] = archived_server
            
            archived_api = self._archive_api_usage(archive_conn, archive_cutoff)
            archive_stats["api_usage_archived"] = archived_api
            
            archive_conn.commit()
            archive_conn.close()
            
            logger.info("Data archiving completed", extra=archive_stats)
            return archive_stats
            
        except Exception as e:
            logger.error(f"Failed to archive old data: {e}")
            return {"error": str(e)}
    
    def _copy_schema_to_archive(self, archive_conn: sqlite3.Connection) -> None:
        """Copy database schema to archive database."""
        cursor = self.db_connection.cursor()
        archive_cursor = archive_conn.cursor()
        
        # Get table creation statements
        cursor.execute("""
            SELECT sql FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        
        for (sql,) in cursor.fetchall():
            if sql:
                archive_cursor.execute(sql)
    
    def _archive_tool_usage(self, archive_conn: sqlite3.Connection,
                          cutoff_date: datetime) -> int:
        """Archive old tool usage data."""
        cursor = self.db_connection.cursor()
        archive_cursor = archive_conn.cursor()
        
        # Get old records
        cursor.execute("""
            SELECT * FROM tool_usage_analytics 
            WHERE timestamp < ?
        """, (cutoff_date.isoformat(),))
        
        rows = cursor.fetchall()
        if not rows:
            return 0
        
        # Insert into archive
        archive_cursor.executemany("""
            INSERT INTO tool_usage_analytics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        
        return len(rows)
    
    def _archive_recommendations(self, archive_conn: sqlite3.Connection,
                               cutoff_date: datetime) -> int:
        """Archive old recommendation data."""
        cursor = self.db_connection.cursor()
        archive_cursor = archive_conn.cursor()
        
        cursor.execute("""
            SELECT * FROM recommendation_analytics 
            WHERE timestamp < ?
        """, (cutoff_date.isoformat(),))
        
        rows = cursor.fetchall()
        if not rows:
            return 0
        
        archive_cursor.executemany("""
            INSERT INTO recommendation_analytics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        
        return len(rows)
    
    def _archive_server_analytics(self, archive_conn: sqlite3.Connection,
                                cutoff_date: datetime) -> int:
        """Archive old server analytics data."""
        cursor = self.db_connection.cursor()
        archive_cursor = archive_conn.cursor()
        
        cursor.execute("""
            SELECT * FROM server_analytics 
            WHERE date < ?
        """, (cutoff_date.date().isoformat(),))
        
        rows = cursor.fetchall()
        if not rows:
            return 0
        
        archive_cursor.executemany("""
            INSERT INTO server_analytics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        
        return len(rows)
    
    def _archive_api_usage(self, archive_conn: sqlite3.Connection,
                         cutoff_date: datetime) -> int:
        """Archive old API usage data."""
        cursor = self.db_connection.cursor()
        archive_cursor = archive_conn.cursor()
        
        cursor.execute("""
            SELECT * FROM api_usage_analytics 
            WHERE date < ?
        """, (cutoff_date.isoformat(),))
        
        rows = cursor.fetchall()
        if not rows:
            return 0
        
        archive_cursor.executemany("""
            INSERT INTO api_usage_analytics VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        
        return len(rows)
    
    def optimize_database(self) -> Dict[str, any]:
        """
        Optimize database performance with various maintenance operations.
        
        Returns:
            Dictionary with optimization statistics
        """
        try:
            cursor = self.db_connection.cursor()
            optimization_stats = {}
            
            # Get database size before optimization
            cursor.execute("PRAGMA page_count")
            pages_before = cursor.fetchone()[0]
            
            # Analyze query patterns for index recommendations
            index_recommendations = self._analyze_index_needs(cursor)
            optimization_stats["index_recommendations"] = index_recommendations
            
            # Update table statistics
            cursor.execute("ANALYZE")
            
            # Rebuild indexes
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type = 'index' AND sql IS NOT NULL
            """)
            
            indexes_rebuilt = 0
            for (index_name,) in cursor.fetchall():
                cursor.execute(f"REINDEX {index_name}")
                indexes_rebuilt += 1
            
            optimization_stats["indexes_rebuilt"] = indexes_rebuilt
            
            # Vacuum database
            cursor.execute("VACUUM")
            
            # Get database size after optimization
            cursor.execute("PRAGMA page_count")
            pages_after = cursor.fetchone()[0]
            
            optimization_stats["pages_freed"] = pages_before - pages_after
            optimization_stats["space_saved_percent"] = (
                (pages_before - pages_after) / pages_before * 100 
                if pages_before > 0 else 0
            )
            
            self.db_connection.commit()
            
            logger.info("Database optimization completed", extra=optimization_stats)
            return optimization_stats
            
        except Exception as e:
            logger.error(f"Failed to optimize database: {e}")
            return {"error": str(e)}
    
    def _analyze_index_needs(self, cursor: sqlite3.Cursor) -> List[str]:
        """Analyze and recommend indexes based on query patterns."""
        recommendations = []
        
        try:
            # Check for missing indexes on frequently queried columns
            
            # Tool usage analytics - often queried by timestamp and tool name
            cursor.execute("""
                SELECT COUNT(*) FROM tool_usage_analytics 
                WHERE timestamp > datetime('now', '-7 days')
            """)
            recent_tool_usage = cursor.fetchone()[0]
            
            if recent_tool_usage > 1000:
                recommendations.append(
                    "CREATE INDEX IF NOT EXISTS idx_tool_usage_timestamp ON tool_usage_analytics(timestamp)"
                )
                recommendations.append(
                    "CREATE INDEX IF NOT EXISTS idx_tool_usage_tool_name ON tool_usage_analytics(tool_canonical_name)"
                )
            
            # Recommendation analytics - often queried by session and timestamp
            cursor.execute("""
                SELECT COUNT(*) FROM recommendation_analytics 
                WHERE timestamp > datetime('now', '-7 days')
            """)
            recent_recommendations = cursor.fetchone()[0]
            
            if recent_recommendations > 500:
                recommendations.append(
                    "CREATE INDEX IF NOT EXISTS idx_recommendation_timestamp ON recommendation_analytics(timestamp)"
                )
                recommendations.append(
                    "CREATE INDEX IF NOT EXISTS idx_recommendation_session ON recommendation_analytics(session_id)"
                )
            
            # Create recommended indexes
            for index_sql in recommendations:
                cursor.execute(index_sql)
            
        except Exception as e:
            logger.warning(f"Index analysis failed: {e}")
        
        return recommendations
    
    def get_database_stats(self) -> Dict[str, any]:
        """
        Get comprehensive database statistics.
        
        Returns:
            Dictionary with database statistics
        """
        try:
            cursor = self.db_connection.cursor()
            stats = {}
            
            # Table row counts
            tables = [
                "tool_usage_analytics",
                "recommendation_analytics", 
                "server_analytics",
                "api_usage_analytics",
                "query_patterns"
            ]
            
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[f"{table}_count"] = cursor.fetchone()[0]
            
            # Database size information
            cursor.execute("PRAGMA page_count")
            page_count = cursor.fetchone()[0]
            
            cursor.execute("PRAGMA page_size")
            page_size = cursor.fetchone()[0]
            
            stats["database_size_bytes"] = page_count * page_size
            stats["database_size_mb"] = round((page_count * page_size) / (1024 * 1024), 2)
            
            # Data freshness
            cursor.execute("""
                SELECT MAX(timestamp) FROM tool_usage_analytics
            """)
            latest_usage = cursor.fetchone()[0]
            stats["latest_tool_usage"] = latest_usage
            
            cursor.execute("""
                SELECT MIN(timestamp) FROM tool_usage_analytics
            """)
            earliest_usage = cursor.fetchone()[0]
            stats["earliest_tool_usage"] = earliest_usage
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {"error": str(e)}