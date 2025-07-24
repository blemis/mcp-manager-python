"""
Analytics module for MCP Manager.

Provides comprehensive usage tracking, performance analytics,
and insights for tool usage optimization.
"""

from .service import UsageAnalyticsService
from .collector import AnalyticsCollector
from .analyzer import AnalyticsAnalyzer
from .query_processor import QueryProcessor
from .config import AnalyticsConfig

# Backward compatibility
from .usage_analytics import UsageAnalyticsService as LegacyUsageAnalyticsService

__all__ = [
    'UsageAnalyticsService',
    'AnalyticsCollector',
    'AnalyticsAnalyzer', 
    'QueryProcessor',
    'AnalyticsConfig',
    'LegacyUsageAnalyticsService',  # For backward compatibility
]