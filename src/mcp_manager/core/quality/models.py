"""
Quality tracking models for MCP server reliability assessment.

This module defines the data structures for tracking MCP server installation
success rates, health metrics, and community feedback.
"""

import time
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from pydantic import BaseModel, Field


class InstallOutcome(Enum):
    """Possible outcomes of an MCP server installation attempt."""
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    PARTIAL = "partial"  # Installed but health check failed
    CANCELLED = "cancelled"


class HealthStatus(Enum):
    """MCP server health check status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class IssueCategory(Enum):
    """Categories of common MCP server issues."""
    CONNECTION = "connection"
    CONFIGURATION = "configuration"
    DEPENDENCIES = "dependencies"
    PERFORMANCE = "performance"
    COMPATIBILITY = "compatibility"
    DOCUMENTATION = "documentation"
    MAINTENANCE = "maintenance"


@dataclass
class InstallAttempt:
    """Record of a single MCP server installation attempt."""
    server_id: str
    install_id: str
    outcome: InstallOutcome
    timestamp: float
    duration_seconds: float
    error_message: Optional[str] = None
    error_category: Optional[IssueCategory] = None
    user_agent: Optional[str] = None  # MCP Manager version
    platform: Optional[str] = None  # OS platform
    python_version: Optional[str] = None
    claude_version: Optional[str] = None
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if not hasattr(self, 'timestamp') or self.timestamp is None:
            self.timestamp = time.time()


@dataclass
class HealthCheck:
    """Record of a server health check."""
    server_id: str
    status: HealthStatus
    timestamp: float
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    connection_details: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if not hasattr(self, 'timestamp') or self.timestamp is None:
            self.timestamp = time.time()


@dataclass
class UserFeedback:
    """User feedback on MCP server quality."""
    server_id: str
    rating: int  # 1-5 stars
    timestamp: float
    comment: Optional[str] = None
    reported_issues: List[IssueCategory] = field(default_factory=list)
    recommended_alternative: Optional[str] = None
    user_hash: Optional[str] = None  # Anonymous user identifier
    
    def __post_init__(self):
        """Validate rating and set timestamp."""
        if not 1 <= self.rating <= 5:
            raise ValueError("Rating must be between 1 and 5")
        if not hasattr(self, 'timestamp') or self.timestamp is None:
            self.timestamp = time.time()


class QualityMetrics(BaseModel):
    """Aggregated quality metrics for an MCP server."""
    
    server_id: str
    install_id: str
    
    # Installation metrics
    total_install_attempts: int = 0
    successful_installs: int = 0
    failed_installs: int = 0
    success_rate: float = 0.0
    
    # Health metrics
    total_health_checks: int = 0
    healthy_checks: int = 0
    health_rate: float = 0.0
    avg_response_time_ms: Optional[float] = None
    
    # User feedback
    total_ratings: int = 0
    average_rating: float = 0.0
    rating_distribution: Dict[int, int] = Field(default_factory=dict)
    
    # Issue tracking
    common_issues: Dict[IssueCategory, int] = Field(default_factory=dict)
    error_patterns: List[str] = Field(default_factory=list)
    
    # Temporal metrics
    last_successful_install: Optional[float] = None
    last_health_check: Optional[float] = None
    first_seen: Optional[float] = None
    
    # Quality indicators
    reliability_score: float = 0.0  # Composite score 0-100
    maintenance_status: str = "unknown"  # active, stale, abandoned
    recommended_alternatives: List[str] = Field(default_factory=list)
    
    def update_success_rate(self) -> None:
        """Recalculate success rate from current data."""
        if self.total_install_attempts > 0:
            self.success_rate = self.successful_installs / self.total_install_attempts
        else:
            self.success_rate = 0.0
    
    def update_health_rate(self) -> None:
        """Recalculate health rate from current data."""
        if self.total_health_checks > 0:
            self.health_rate = self.healthy_checks / self.total_health_checks
        else:
            self.health_rate = 0.0
    
    def calculate_reliability_score(self) -> float:
        """
        Calculate composite reliability score (0-100).
        
        Factors:
        - Success rate (40%)
        - Health rate (30%) 
        - User rating (20%)
        - Recency bonus (10%)
        """
        score = 0.0
        
        # Success rate component (40%)
        score += self.success_rate * 40
        
        # Health rate component (30%)
        score += self.health_rate * 30
        
        # User rating component (20%) - scale from 1-5 to 0-1
        if self.average_rating > 0:
            normalized_rating = (self.average_rating - 1) / 4  # Scale 1-5 to 0-1
            score += normalized_rating * 20
        
        # Recency bonus (10%) - recent activity gets bonus
        if self.last_successful_install:
            days_since_success = (time.time() - self.last_successful_install) / 86400
            if days_since_success < 30:  # Active within 30 days
                recency_bonus = max(0, 1 - (days_since_success / 30))
                score += recency_bonus * 10
        
        self.reliability_score = min(100, score)
        return self.reliability_score
    
    def get_quality_tier(self) -> str:
        """Get quality tier based on reliability score."""
        if self.reliability_score >= 80:
            return "excellent"
        elif self.reliability_score >= 60:
            return "good"
        elif self.reliability_score >= 40:
            return "fair"
        elif self.reliability_score >= 20:
            return "poor"
        else:
            return "critical"
    
    def get_recommendation_status(self) -> str:
        """Get recommendation status for discovery results."""
        score = self.reliability_score
        tier = self.get_quality_tier()
        
        if tier == "excellent":
            return "✅ Highly Recommended"
        elif tier == "good":
            return "👍 Recommended"
        elif tier == "fair":
            return "⚠️  Use with Caution"
        elif tier == "poor":
            return "❗ Known Issues"
        else:
            return "❌ Not Recommended"


class QualityReport(BaseModel):
    """Comprehensive quality report for a server."""
    
    server_id: str
    install_id: str
    metrics: QualityMetrics
    
    # Detailed breakdowns
    recent_attempts: List[InstallAttempt] = Field(default_factory=list)
    recent_health_checks: List[HealthCheck] = Field(default_factory=list)
    recent_feedback: List[UserFeedback] = Field(default_factory=list)
    
    # Analysis
    trend_direction: str = "stable"  # improving, declining, stable
    confidence_level: str = "high"  # high, medium, low (based on sample size)
    
    # Recommendations
    install_recommendation: str = "neutral"
    alternative_suggestions: List[str] = Field(default_factory=list)
    troubleshooting_tips: List[str] = Field(default_factory=list)
    
    def generate_summary(self) -> str:
        """Generate human-readable quality summary."""
        m = self.metrics
        tier = m.get_quality_tier()
        status = m.get_recommendation_status()
        
        summary_parts = [
            f"Quality: {status} (Score: {m.reliability_score:.1f}/100)",
            f"Success Rate: {m.success_rate:.1%} ({m.successful_installs}/{m.total_install_attempts} installs)",
        ]
        
        if m.total_health_checks > 0:
            summary_parts.append(f"Health Rate: {m.health_rate:.1%}")
        
        if m.average_rating > 0:
            summary_parts.append(f"User Rating: {m.average_rating:.1f}/5.0 ({m.total_ratings} reviews)")
        
        if m.common_issues:
            top_issue = max(m.common_issues.items(), key=lambda x: x[1])
            summary_parts.append(f"Top Issue: {top_issue[0].value}")
        
        return " | ".join(summary_parts)


# Request/Response models for API
class QualityTrackingRequest(BaseModel):
    """Request to track installation attempt or health check."""
    server_id: str
    event_type: str  # "install_attempt", "health_check", "user_feedback"
    data: Dict[str, Any]


class QualityQueryRequest(BaseModel):
    """Request for quality information."""
    server_ids: List[str] = Field(default_factory=list)
    include_details: bool = False
    min_attempts: int = 1  # Minimum attempts to include in results
    
    
class QualityQueryResponse(BaseModel):
    """Response with quality information."""
    results: Dict[str, QualityMetrics]
    reports: Dict[str, QualityReport] = Field(default_factory=dict)
    updated_at: float = Field(default_factory=time.time)