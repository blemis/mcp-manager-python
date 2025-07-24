"""
Data models and enums for AI curation functionality.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any


class TaskCategory(str, Enum):
    """Categories of tasks for MCP suite recommendations."""
    WEB_DEVELOPMENT = "web_development"
    DATA_ANALYSIS = "data_analysis"
    SYSTEM_ADMIN = "system_admin"
    CONTENT_CREATION = "content_creation"
    API_DEVELOPMENT = "api_development"
    DATABASE_WORK = "database_work"
    FILE_MANAGEMENT = "file_management"
    AUTOMATION = "automation"
    RESEARCH = "research"
    TESTING = "testing"


class CurationCriteria(str, Enum):
    """Criteria for evaluating MCP server quality."""
    RELIABILITY = "reliability"
    PERFORMANCE = "performance"
    COMPATIBILITY = "compatibility"
    FUNCTIONALITY = "functionality"
    DOCUMENTATION = "documentation"
    MAINTENANCE = "maintenance"


@dataclass
class ServerAnalysis:
    """Analysis results for a specific MCP server."""
    server_name: str
    reliability_score: float
    performance_score: float
    compatibility_score: float
    functionality_score: float
    documentation_score: float
    maintenance_score: float
    overall_score: float
    insights: List[str]
    conflicts: List[str]
    last_analyzed: str


@dataclass
class SuiteRecommendation:
    """Recommendation for an MCP server suite."""
    task_category: TaskCategory
    servers: List[str]
    confidence_score: float
    reasoning: str
    alternatives: List[str]
    configuration_hints: Dict[str, Any]