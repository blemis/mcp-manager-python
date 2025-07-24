"""
AI Curation module for MCP Manager.

Provides intelligent analysis and recommendations for MCP server
suites based on task requirements, compatibility, and performance.
"""

from .models import TaskCategory, CurationCriteria, ServerAnalysis, SuiteRecommendation
from .analysis.server_analyzer import ServerAnalyzer
from .intelligence.ai_insights import AIInsightsGenerator
from .intelligence.task_classifier import TaskClassifier

# Main interfaces - to be implemented
# from .curation_engine import AICurationEngine

__all__ = [
    'TaskCategory',
    'CurationCriteria', 
    'ServerAnalysis',
    'SuiteRecommendation',
    'ServerAnalyzer',
    'AIInsightsGenerator',
    'TaskClassifier',
    # 'AICurationEngine',
]