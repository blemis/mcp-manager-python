"""
Data models for test category and suite management.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum


class TestScope(Enum):
    """Test execution scope."""
    UNIT = "unit"
    INTEGRATION = "integration"
    WORKFLOW = "workflow"
    PERFORMANCE = "performance"
    ERROR_HANDLING = "error_handling"


@dataclass
class TestCategory:
    """Represents a test category with dynamic configuration."""
    
    id: str
    name: str
    description: str
    scope: TestScope
    test_file_pattern: str  # e.g., "test_server_*.py"
    default_suite_id: Optional[str] = None
    required_servers: List[str] = None
    optional_servers: List[str] = None
    test_markers: List[str] = None
    config: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.required_servers is None:
            self.required_servers = []
        if self.optional_servers is None:
            self.optional_servers = []
        if self.test_markers is None:
            self.test_markers = []
        if self.config is None:
            self.config = {}


@dataclass 
class TestSuiteMapping:
    """Maps test categories to specific suites."""
    
    id: str
    test_category_id: str
    suite_id: str
    priority: int  # Higher = preferred
    conditions: Dict[str, Any] = None  # Optional conditions for mapping
    created_by: str = "system"
    
    def __post_init__(self):
        if self.conditions is None:
            self.conditions = {}


@dataclass
class TestExecution:
    """Tracks test execution with suite loading."""
    
    id: str
    test_category_id: str
    suite_id: str
    test_file: str
    test_class: Optional[str] = None
    status: str = "pending"
    suite_loaded: bool = False
    servers_deployed: List[str] = None
    execution_time: Optional[float] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.servers_deployed is None:
            self.servers_deployed = []