"""
Data analysis and processing for analytics.

Processes collected analytics data to generate insights and reports.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class AnalyticsAnalyzer:
    """Analyzes collected analytics data."""
    
    def __init__(self, database, query_processor):
        """Initialize analyzer with database and query processor."""
        self.database = database
        self.query_processor = query_processor
    
    def get_usage_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get usage summary for the specified number of days."""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Tool usage summary
            tool_usage = self.database.execute_query("""
                SELECT tool_name, COUNT(*) as usage_count, 
                       AVG(CASE WHEN response_time IS NOT NULL THEN response_time END) as avg_response_time,
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate
                FROM tool_usage 
                WHERE timestamp > ?
                GROUP BY tool_name
                ORDER BY usage_count DESC
            """, [cutoff_date])
            
            # Server analytics summary
            server_analytics = self.database.execute_query("""
                SELECT server_name, action, COUNT(*) as count,
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as success_rate
                FROM server_analytics 
                WHERE timestamp > ?
                GROUP BY server_name, action
                ORDER BY count DESC
            """, [cutoff_date])
            
            # Recommendation analytics
            recommendation_stats = self.database.execute_query("""
                SELECT recommendation_type, COUNT(*) as count,
                       AVG(CASE WHEN feedback_score IS NOT NULL THEN feedback_score END) as avg_feedback
                FROM recommendations 
                WHERE timestamp > ?
                GROUP BY recommendation_type
                ORDER BY count DESC
            """, [cutoff_date])
            
            # API usage summary
            api_usage = self.database.execute_query("""
                SELECT endpoint, method, COUNT(*) as request_count,
                       AVG(response_time) as avg_response_time,
                       AVG(CASE WHEN status_code < 400 THEN 1.0 ELSE 0.0 END) * 100 as success_rate
                FROM api_usage 
                WHERE timestamp > ?
                GROUP BY endpoint, method
                ORDER BY request_count DESC
            """, [cutoff_date])
            
            # Overall statistics
            total_sessions = self.database.execute_query("""
                SELECT COUNT(DISTINCT session_id) as unique_sessions
                FROM (
                    SELECT session_id FROM tool_usage WHERE timestamp > ?
                    UNION
                    SELECT session_id FROM server_analytics WHERE timestamp > ?
                    UNION 
                    SELECT session_id FROM recommendations WHERE timestamp > ?
                    UNION
                    SELECT session_id FROM api_usage WHERE timestamp > ?
                )
            """, [cutoff_date, cutoff_date, cutoff_date, cutoff_date])
            
            summary = {
                'period_days': days,
                'start_date': cutoff_date,
                'end_date': datetime.now().isoformat(),
                'unique_sessions': total_sessions[0]['unique_sessions'] if total_sessions else 0,
                'tool_usage': [dict(row) for row in tool_usage],
                'server_analytics': [dict(row) for row in server_analytics],
                'recommendation_stats': [dict(row) for row in recommendation_stats],
                'api_usage': [dict(row) for row in api_usage]
            }
            
            logger.info(f"Generated usage summary for {days} days")
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate usage summary: {e}")
            return {
                'error': str(e),
                'period_days': days,
                'unique_sessions': 0,
                'tool_usage': [],
                'server_analytics': [],
                'recommendation_stats': [],
                'api_usage': []
            }
    
    def get_trending_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get trending user queries with categorization."""
        try:
            # Get recent queries with frequency
            recent_queries = self.database.execute_query("""
                SELECT user_query, COUNT(*) as frequency,
                       AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) * 100 as success_rate,
                       MAX(timestamp) as last_seen
                FROM tool_usage 
                WHERE user_query IS NOT NULL 
                AND user_query != ''
                AND timestamp > ?
                GROUP BY LOWER(user_query)
                ORDER BY frequency DESC, last_seen DESC
                LIMIT ?
            """, [(datetime.now() - timedelta(days=30)).isoformat(), limit])
            
            trending = []
            for row in recent_queries:
                query_dict = dict(row)
                
                # Add categorization
                category = self.query_processor.categorize_query(query_dict['user_query'])
                keywords = self.query_processor.extract_keywords(query_dict['user_query'])
                
                query_dict['category'] = category
                query_dict['keywords'] = keywords
                
                trending.append(query_dict)
            
            # Update query patterns for future analysis
            self._update_query_patterns(trending)
            
            logger.debug(f"Found {len(trending)} trending queries")
            return trending
            
        except Exception as e:
            logger.error(f"Failed to get trending queries: {e}")
            return []
    
    def get_performance_metrics(self, days: int = 7) -> Dict[str, Any]:
        """Get system performance metrics."""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Response time analysis
            response_times = self.database.execute_query("""
                SELECT 
                    AVG(response_time) as avg_response_time,
                    MIN(response_time) as min_response_time,
                    MAX(response_time) as max_response_time,
                    COUNT(*) as total_requests
                FROM (
                    SELECT response_time FROM tool_usage WHERE response_time IS NOT NULL AND timestamp > ?
                    UNION ALL
                    SELECT response_time FROM api_usage WHERE timestamp > ?
                )
            """, [cutoff_date, cutoff_date])
            
            # Error rate analysis
            error_rates = self.database.execute_query("""
                SELECT 
                    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as overall_error_rate,
                    COUNT(*) as total_operations
                FROM (
                    SELECT success FROM tool_usage WHERE timestamp > ?
                    UNION ALL
                    SELECT CASE WHEN status_code < 400 THEN 1 ELSE 0 END as success 
                    FROM api_usage WHERE timestamp > ?
                )
            """, [cutoff_date, cutoff_date])
            
            metrics = {
                'period_days': days,
                'response_times': dict(response_times[0]) if response_times else {},
                'error_rates': dict(error_rates[0]) if error_rates else {}
            }
            
            logger.debug(f"Generated performance metrics for {days} days")
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}")
            return {'error': str(e), 'period_days': days}
    
    def _update_query_patterns(self, trending_queries: List[Dict[str, Any]]) -> None:
        """Update query patterns for machine learning and trend analysis."""
        try:
            # This is a placeholder for more sophisticated pattern analysis
            # In a full implementation, this could update ML models or pattern databases
            
            patterns = {}
            for query_data in trending_queries:
                category = query_data.get('category', 'unknown')
                keywords = query_data.get('keywords', [])
                
                if category not in patterns:
                    patterns[category] = {
                        'count': 0,
                        'keywords': set()
                    }
                
                patterns[category]['count'] += query_data['frequency']
                patterns[category]['keywords'].update(keywords)
            
            # Convert sets to lists for JSON serialization
            for category in patterns:
                patterns[category]['keywords'] = list(patterns[category]['keywords'])
            
            logger.debug(f"Updated query patterns for {len(patterns)} categories")
            
        except Exception as e:
            logger.warning(f"Failed to update query patterns: {e}")
    
    def get_user_behavior_insights(self, days: int = 30) -> Dict[str, Any]:
        """Generate insights about user behavior patterns."""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Peak usage hours
            hourly_usage = self.database.execute_query("""
                SELECT 
                    strftime('%H', timestamp) as hour,
                    COUNT(*) as usage_count
                FROM tool_usage 
                WHERE timestamp > ?
                GROUP BY strftime('%H', timestamp)
                ORDER BY usage_count DESC
            """, [cutoff_date])
            
            # Most common tool sequences
            tool_sequences = self.database.execute_query("""
                SELECT tool_name, COUNT(*) as usage_count
                FROM tool_usage 
                WHERE timestamp > ?
                GROUP BY tool_name
                ORDER BY usage_count DESC
                LIMIT 10
            """, [cutoff_date])
            
            insights = {
                'period_days': days,
                'peak_hours': [dict(row) for row in hourly_usage[:5]],
                'popular_tools': [dict(row) for row in tool_sequences],
                'total_sessions': len(set(row['session_id'] for row in self.database.execute_query(
                    "SELECT DISTINCT session_id FROM tool_usage WHERE timestamp > ?", [cutoff_date]
                )))
            }
            
            return insights
            
        except Exception as e:
            logger.error(f"Failed to generate user behavior insights: {e}")
            return {'error': str(e), 'period_days': days}