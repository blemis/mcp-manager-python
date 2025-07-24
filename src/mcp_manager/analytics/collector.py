"""
Data collection module for analytics.

Handles recording of all types of analytics data.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import uuid4

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class AnalyticsCollector:
    """Collects and records analytics data."""
    
    def __init__(self, database, config):
        """Initialize collector with database and config."""
        self.database = database
        self.config = config
    
    def record_tool_usage(
        self,
        tool_name: str,
        action: str,
        user_query: Optional[str] = None,
        success: bool = True,
        response_time: Optional[float] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Record tool usage analytics."""
        if not self.config.analytics_enabled:
            return ""
        
        try:
            session_id = str(uuid4())
            timestamp = datetime.now().isoformat()
            
            # Insert the tool usage record
            self.database.execute_insert(
                'tool_usage',
                {
                    'session_id': session_id,
                    'timestamp': timestamp,
                    'tool_name': tool_name,
                    'action': action,
                    'user_query': user_query,
                    'success': success,
                    'response_time': response_time,
                    'context': str(context) if context else None
                }
            )
            
            logger.debug(f"Recorded tool usage: {tool_name}/{action}")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to record tool usage: {e}")
            return ""
    
    def record_recommendation_analytics(
        self,
        recommendation_type: str,
        query: str,
        recommendations: List[str],
        user_action: Optional[str] = None,
        feedback_score: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Record recommendation analytics."""
        if not self.config.analytics_enabled:
            return ""
        
        try:
            session_id = str(uuid4())
            timestamp = datetime.now().isoformat()
            
            self.database.execute_insert(
                'recommendations',
                {
                    'session_id': session_id,
                    'timestamp': timestamp,
                    'recommendation_type': recommendation_type,
                    'query': query,
                    'recommendations': ','.join(recommendations),
                    'user_action': user_action,
                    'feedback_score': feedback_score,
                    'context': str(context) if context else None
                }
            )
            
            logger.debug(f"Recorded recommendation: {recommendation_type}")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to record recommendation analytics: {e}")
            return ""
    
    def record_server_analytics(
        self,
        server_name: str,
        action: str,
        success: bool = True,
        error_message: Optional[str] = None,
        performance_metrics: Optional[Dict[str, Any]] = None
    ) -> str:
        """Record server analytics."""
        if not self.config.analytics_enabled:
            return ""
        
        try:
            session_id = str(uuid4())
            timestamp = datetime.now().isoformat()
            
            self.database.execute_insert(
                'server_analytics',
                {
                    'session_id': session_id,
                    'timestamp': timestamp,
                    'server_name': server_name,
                    'action': action,
                    'success': success,
                    'error_message': error_message,
                    'performance_metrics': str(performance_metrics) if performance_metrics else None
                }
            )
            
            logger.debug(f"Recorded server analytics: {server_name}/{action}")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to record server analytics: {e}")
            return ""
    
    def record_api_usage(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        response_time: float,
        request_size: Optional[int] = None,
        response_size: Optional[int] = None,
        user_agent: Optional[str] = None
    ) -> str:
        """Record API usage analytics."""
        if not self.config.analytics_enabled:
            return ""
        
        try:
            session_id = str(uuid4())
            timestamp = datetime.now().isoformat()
            
            self.database.execute_insert(
                'api_usage',
                {
                    'session_id': session_id,
                    'timestamp': timestamp,
                    'endpoint': endpoint,
                    'method': method,
                    'status_code': status_code,
                    'response_time': response_time,
                    'request_size': request_size,
                    'response_size': response_size,
                    'user_agent': user_agent
                }
            )
            
            logger.debug(f"Recorded API usage: {method} {endpoint}")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to record API usage: {e}")
            return ""