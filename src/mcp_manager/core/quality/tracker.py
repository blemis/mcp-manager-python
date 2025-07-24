"""
MCP Server Quality Tracking Service.

This service handles collection, analysis, and reporting of MCP server quality
metrics including installation success rates, health monitoring, and user feedback.
"""

import hashlib
import json
import platform
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from contextlib import contextmanager

from mcp_manager.core.quality.models import (
    InstallAttempt, HealthCheck, UserFeedback, QualityMetrics, QualityReport,
    InstallOutcome, HealthStatus, IssueCategory
)
from mcp_manager.utils.config import get_config
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class QualityTracker:
    """
    Tracks and analyzes MCP server quality metrics.
    
    Provides methods to record installation attempts, health checks, and user
    feedback, then aggregates this data to provide quality assessments.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize quality tracker.
        
        Args:
            db_path: Path to SQLite database. If None, uses default location.
        """
        if db_path is None:
            config_dir = Path.home() / ".config" / "mcp-manager"
            config_dir.mkdir(parents=True, exist_ok=True)
            db_path = config_dir / "quality_tracking.db"
        
        self.db_path = db_path
        self._init_database()
        
        # System information for context
        self.system_info = {
            "platform": platform.system(),
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
            "user_agent": "mcp-manager/1.0.0"  # Could get from __version__
        }
        
        logger.info("QualityTracker initialized", extra={"db_path": str(db_path)})
    
    def _init_database(self) -> None:
        """Initialize SQLite database with required tables."""
        with self._get_connection() as conn:
            # Install attempts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS install_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_id TEXT NOT NULL,
                    install_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    duration_seconds REAL NOT NULL,
                    error_message TEXT,
                    error_category TEXT,
                    user_agent TEXT,
                    platform TEXT,
                    python_version TEXT,
                    claude_version TEXT,
                    UNIQUE(server_id, timestamp, outcome) ON CONFLICT IGNORE
                )
            """)
            
            # Health checks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS health_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    response_time_ms REAL,
                    error_message TEXT,
                    connection_details TEXT,
                    UNIQUE(server_id, timestamp, status) ON CONFLICT IGNORE
                )
            """)
            
            # User feedback table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_id TEXT NOT NULL,
                    rating INTEGER NOT NULL,
                    timestamp REAL NOT NULL,
                    comment TEXT,
                    reported_issues TEXT,
                    recommended_alternative TEXT,
                    user_hash TEXT,
                    UNIQUE(server_id, user_hash, timestamp) ON CONFLICT IGNORE
                )
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_install_server_time ON install_attempts(server_id, timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_health_server_time ON health_checks(server_id, timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_server ON user_feedback(server_id)")
            
            conn.commit()
            logger.debug("Quality tracking database initialized")
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper error handling."""
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=10.0)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def record_install_attempt(
        self,
        server_id: str,
        install_id: str,
        outcome: InstallOutcome,
        duration_seconds: float,
        error_message: Optional[str] = None,
        error_category: Optional[IssueCategory] = None,
        claude_version: Optional[str] = None
    ) -> None:
        """
        Record an installation attempt.
        
        Args:
            server_id: Server identifier
            install_id: Unique install ID for the server
            outcome: Installation outcome
            duration_seconds: Time taken for installation
            error_message: Error message if failed
            error_category: Category of error if failed
            claude_version: Claude Code version if available
        """
        attempt = InstallAttempt(
            server_id=server_id,
            install_id=install_id,
            outcome=outcome,
            timestamp=time.time(),
            duration_seconds=duration_seconds,
            error_message=error_message,
            error_category=error_category,
            user_agent=self.system_info["user_agent"],
            platform=self.system_info["platform"],
            python_version=self.system_info["python_version"],
            claude_version=claude_version
        )
        
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO install_attempts 
                    (server_id, install_id, outcome, timestamp, duration_seconds,
                     error_message, error_category, user_agent, platform, 
                     python_version, claude_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    attempt.server_id, attempt.install_id, attempt.outcome.value,
                    attempt.timestamp, attempt.duration_seconds, attempt.error_message,
                    attempt.error_category.value if attempt.error_category else None,
                    attempt.user_agent, attempt.platform, attempt.python_version,
                    attempt.claude_version
                ))
                conn.commit()
                
            logger.info(f"Recorded install attempt for {server_id}: {outcome.value}")
            
        except Exception as e:
            logger.error(f"Failed to record install attempt: {e}")
    
    def record_health_check(
        self,
        server_id: str,
        status: HealthStatus,
        response_time_ms: Optional[float] = None,
        error_message: Optional[str] = None,
        connection_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record a health check result.
        
        Args:
            server_id: Server identifier
            status: Health status result
            response_time_ms: Response time in milliseconds
            error_message: Error message if unhealthy
            connection_details: Additional connection information
        """
        health_check = HealthCheck(
            server_id=server_id,
            status=status,
            timestamp=time.time(),
            response_time_ms=response_time_ms,
            error_message=error_message,
            connection_details=connection_details or {}
        )
        
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO health_checks 
                    (server_id, status, timestamp, response_time_ms, error_message, connection_details)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    health_check.server_id, health_check.status.value,
                    health_check.timestamp, health_check.response_time_ms,
                    health_check.error_message, json.dumps(health_check.connection_details)
                ))
                conn.commit()
                
            logger.debug(f"Recorded health check for {server_id}: {status.value}")
            
        except Exception as e:
            logger.error(f"Failed to record health check: {e}")
    
    def record_user_feedback(
        self,
        server_id: str,
        rating: int,
        comment: Optional[str] = None,
        reported_issues: Optional[List[IssueCategory]] = None,
        recommended_alternative: Optional[str] = None,
        user_identifier: Optional[str] = None
    ) -> None:
        """
        Record user feedback.
        
        Args:
            server_id: Server identifier
            rating: User rating (1-5)
            comment: Optional comment
            reported_issues: List of issue categories
            recommended_alternative: Alternative server recommendation
            user_identifier: Anonymous user identifier
        """
        # Create anonymous user hash
        user_hash = None
        if user_identifier:
            user_hash = hashlib.sha256(user_identifier.encode()).hexdigest()[:16]
        
        feedback = UserFeedback(
            server_id=server_id,
            rating=rating,
            timestamp=time.time(),
            comment=comment,
            reported_issues=reported_issues or [],
            recommended_alternative=recommended_alternative,
            user_hash=user_hash
        )
        
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO user_feedback 
                    (server_id, rating, timestamp, comment, reported_issues, 
                     recommended_alternative, user_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    feedback.server_id, feedback.rating, feedback.timestamp,
                    feedback.comment, json.dumps([i.value for i in feedback.reported_issues]),
                    feedback.recommended_alternative, feedback.user_hash
                ))
                conn.commit()
                
            logger.info(f"Recorded user feedback for {server_id}: {rating}/5")
            
        except Exception as e:
            logger.error(f"Failed to record user feedback: {e}")
    
    def get_quality_metrics(self, server_id: str, install_id: str) -> QualityMetrics:
        """
        Get aggregated quality metrics for a server.
        
        Args:
            server_id: Server identifier
            install_id: Install ID for the server
            
        Returns:
            QualityMetrics object with aggregated data
        """
        metrics = QualityMetrics(server_id=server_id, install_id=install_id)
        
        try:
            with self._get_connection() as conn:
                # Install attempt metrics
                install_stats = conn.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) as successful,
                        SUM(CASE WHEN outcome != 'success' THEN 1 ELSE 0 END) as failed,
                        MAX(timestamp) as last_success_ts,
                        MIN(timestamp) as first_seen_ts
                    FROM install_attempts 
                    WHERE server_id = ?
                """, (server_id,)).fetchone()
                
                if install_stats and install_stats['total'] > 0:
                    metrics.total_install_attempts = install_stats['total']
                    metrics.successful_installs = install_stats['successful']
                    metrics.failed_installs = install_stats['failed']
                    metrics.last_successful_install = install_stats['last_success_ts']
                    metrics.first_seen = install_stats['first_seen_ts']
                    metrics.update_success_rate()
                
                # Health check metrics
                health_stats = conn.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'healthy' THEN 1 ELSE 0 END) as healthy,
                        AVG(response_time_ms) as avg_response_time,
                        MAX(timestamp) as last_check
                    FROM health_checks 
                    WHERE server_id = ?
                """, (server_id,)).fetchone()
                
                if health_stats and health_stats['total'] > 0:
                    metrics.total_health_checks = health_stats['total']
                    metrics.healthy_checks = health_stats['healthy']
                    metrics.avg_response_time_ms = health_stats['avg_response_time']
                    metrics.last_health_check = health_stats['last_check']
                    metrics.update_health_rate()
                
                # User feedback metrics
                feedback_stats = conn.execute("""
                    SELECT 
                        COUNT(*) as total,
                        AVG(rating) as avg_rating,
                        rating,
                        COUNT(rating) as rating_count
                    FROM user_feedback 
                    WHERE server_id = ?
                    GROUP BY rating
                """, (server_id,)).fetchall()
                
                if feedback_stats:
                    total_ratings = sum(row['rating_count'] for row in feedback_stats)
                    if total_ratings > 0:
                        weighted_sum = sum(row['rating'] * row['rating_count'] for row in feedback_stats)
                        metrics.total_ratings = total_ratings
                        metrics.average_rating = weighted_sum / total_ratings
                        metrics.rating_distribution = {
                            row['rating']: row['rating_count'] for row in feedback_stats
                        }
                
                # Common issues
                issue_stats = conn.execute("""
                    SELECT error_category, COUNT(*) as count
                    FROM install_attempts 
                    WHERE server_id = ? AND error_category IS NOT NULL
                    GROUP BY error_category
                    ORDER BY count DESC
                """, (server_id,)).fetchall()
                
                for row in issue_stats:
                    try:
                        category = IssueCategory(row['error_category'])
                        metrics.common_issues[category] = row['count']
                    except ValueError:
                        # Skip unknown categories
                        pass
                
                # Calculate reliability score
                metrics.calculate_reliability_score()
                
                # Determine maintenance status
                if metrics.last_successful_install:
                    days_since_success = (time.time() - metrics.last_successful_install) / 86400
                    if days_since_success < 7:
                        metrics.maintenance_status = "active"
                    elif days_since_success < 30:
                        metrics.maintenance_status = "recent"
                    elif days_since_success < 90:
                        metrics.maintenance_status = "stale"
                    else:
                        metrics.maintenance_status = "abandoned"
                
        except Exception as e:
            logger.error(f"Failed to get quality metrics for {server_id}: {e}")
        
        return metrics
    
    def get_quality_report(self, server_id: str, install_id: str) -> QualityReport:
        """
        Get detailed quality report for a server.
        
        Args:
            server_id: Server identifier
            install_id: Install ID for the server
            
        Returns:
            QualityReport with detailed analysis
        """
        metrics = self.get_quality_metrics(server_id, install_id)
        report = QualityReport(server_id=server_id, install_id=install_id, metrics=metrics)
        
        try:
            with self._get_connection() as conn:
                # Recent install attempts (last 10)
                recent_attempts = conn.execute("""
                    SELECT * FROM install_attempts 
                    WHERE server_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT 10
                """, (server_id,)).fetchall()
                
                for row in recent_attempts:
                    attempt = InstallAttempt(
                        server_id=row['server_id'],
                        install_id=row['install_id'],
                        outcome=InstallOutcome(row['outcome']),
                        timestamp=row['timestamp'],
                        duration_seconds=row['duration_seconds'],
                        error_message=row['error_message'],
                        error_category=IssueCategory(row['error_category']) if row['error_category'] else None,
                        user_agent=row['user_agent'],
                        platform=row['platform'],
                        python_version=row['python_version'],
                        claude_version=row['claude_version']
                    )
                    report.recent_attempts.append(attempt)
                
                # Generate recommendations
                report.install_recommendation = self._generate_install_recommendation(metrics)
                report.alternative_suggestions = self._get_alternative_suggestions(server_id, metrics)
                report.troubleshooting_tips = self._get_troubleshooting_tips(metrics)
                
        except Exception as e:
            logger.error(f"Failed to generate quality report for {server_id}: {e}")
        
        return report
    
    def _generate_install_recommendation(self, metrics: QualityMetrics) -> str:
        """Generate install recommendation based on metrics."""
        if metrics.total_install_attempts < 3:
            return "insufficient_data"
        
        if metrics.reliability_score >= 80:
            return "recommended"
        elif metrics.reliability_score >= 60:
            return "acceptable"
        elif metrics.reliability_score >= 40:
            return "caution"
        else:
            return "not_recommended"
    
    def _get_alternative_suggestions(self, server_id: str, metrics: QualityMetrics) -> List[str]:
        """Get alternative server suggestions."""
        # This could be enhanced to query similar servers with better metrics
        alternatives = []
        
        # Simple heuristics for now
        if "filesystem" in server_id.lower():
            if server_id != "dd-filesystem":
                alternatives.append("dd-filesystem")
        
        return alternatives
    
    def _get_troubleshooting_tips(self, metrics: QualityMetrics) -> List[str]:
        """Generate troubleshooting tips based on common issues."""
        tips = []
        
        for issue_category, count in metrics.common_issues.items():
            if issue_category == IssueCategory.CONNECTION:
                tips.append("Check that Claude Code is running and accessible")
                tips.append("Verify network connectivity and firewall settings")
            elif issue_category == IssueCategory.CONFIGURATION:
                tips.append("Review server configuration parameters")
                tips.append("Check directory permissions and paths")
            elif issue_category == IssueCategory.DEPENDENCIES:
                tips.append("Ensure all required dependencies are installed")
                tips.append("Try updating Node.js or Python versions")
        
        return tips
    
    def get_server_rankings(self, server_type: Optional[str] = None, limit: int = 50) -> List[Tuple[str, QualityMetrics]]:
        """
        Get servers ranked by quality.
        
        Args:
            server_type: Filter by server type (optional)
            limit: Maximum number of results
            
        Returns:
            List of (server_id, metrics) tuples sorted by reliability score
        """
        rankings = []
        
        try:
            with self._get_connection() as conn:
                # Get all servers with at least some data
                servers = conn.execute("""
                    SELECT DISTINCT server_id 
                    FROM install_attempts 
                    WHERE server_id IS NOT NULL
                """).fetchall()
                
                for row in servers:
                    server_id = row['server_id']
                    # For now, use server_id as install_id (could be improved)
                    metrics = self.get_quality_metrics(server_id, server_id)
                    
                    # Only include servers with meaningful data
                    if metrics.total_install_attempts >= 1:
                        rankings.append((server_id, metrics))
                
                # Sort by reliability score (descending)
                rankings.sort(key=lambda x: x[1].reliability_score, reverse=True)
                rankings = rankings[:limit]
                
        except Exception as e:
            logger.error(f"Failed to get server rankings: {e}")
        
        return rankings
    
    def cleanup_old_data(self, days_to_keep: int = 90) -> None:
        """
        Clean up old tracking data.
        
        Args:
            days_to_keep: Number of days of data to retain
        """
        cutoff_time = time.time() - (days_to_keep * 86400)
        
        try:
            with self._get_connection() as conn:
                # Clean up old install attempts
                result = conn.execute("""
                    DELETE FROM install_attempts 
                    WHERE timestamp < ?
                """, (cutoff_time,))
                install_deleted = result.rowcount
                
                # Clean up old health checks  
                result = conn.execute("""
                    DELETE FROM health_checks 
                    WHERE timestamp < ?
                """, (cutoff_time,))
                health_deleted = result.rowcount
                
                conn.commit()
                
                logger.info(f"Cleaned up old quality data: {install_deleted} install attempts, {health_deleted} health checks")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")