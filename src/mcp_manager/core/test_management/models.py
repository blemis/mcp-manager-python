"""
Data models for test category and suite management.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime


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


@dataclass
class TestScenario:
    """Represents a JSON test scenario stored in the database."""
    
    id: str
    name: str
    description: str
    category: str
    priority: str
    created_by: str  # "ai", "admin", "system", "migration"
    scenario_json: str  # The full JSON scenario as string
    tags: List[str] = None
    confidence_score: float = 0.0
    ai_reasoning: Optional[str] = None
    suite_id: Optional[str] = None  # Which suite this scenario belongs to
    execution_count: int = 0
    success_rate: float = 0.0
    average_duration: float = 0.0
    created_date: Optional[datetime] = None
    last_modified: Optional[datetime] = None
    last_executed: Optional[datetime] = None
    enabled: bool = True
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.created_date is None:
            self.created_date = datetime.now()
        if self.last_modified is None:
            self.last_modified = datetime.now()