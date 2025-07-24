"""
MCP Server Quality Tracking System.

This module provides comprehensive quality tracking for MCP servers including:
- Installation success/failure tracking
- Health monitoring and performance metrics  
- User feedback and ratings
- Community-driven quality assessments
- Quality-aware discovery and recommendations

The system helps users make informed decisions about which MCP servers
to install and use based on real community data.
"""

from .models import (
    InstallAttempt,
    HealthCheck, 
    UserFeedback,
    QualityMetrics,
    QualityReport,
    InstallOutcome,
    HealthStatus,
    IssueCategory
)

from .tracker import QualityTracker
from .discovery_integration import QualityAwareDiscovery, create_quality_aware_discovery

__all__ = [
    # Models
    "InstallAttempt",
    "HealthCheck", 
    "UserFeedback",
    "QualityMetrics",
    "QualityReport",
    "InstallOutcome",
    "HealthStatus", 
    "IssueCategory",
    
    # Core classes
    "QualityTracker",
    "QualityAwareDiscovery",
    
    # Factory functions
    "create_quality_aware_discovery"
]