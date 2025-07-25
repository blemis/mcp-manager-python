"""
Dynamic test category manager with suite mapping.
"""

import uuid
from typing import List, Optional, Dict, Any
from pathlib import Path

from .database import TestManagementDB
from .models import TestCategory, TestSuiteMapping, TestScope
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class TestCategoryManager:
    """Manages dynamic test categories and suite mappings."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """Initialize with database connection."""
        self.db = TestManagementDB(db_path)
        self._ensure_default_categories()
    
    def _ensure_default_categories(self):
        """Create default test categories if they don't exist."""
        default_categories = [
            TestCategory(
                id="server-management",
                name="Server Management",
                description="Tests for adding, removing, enabling/disabling MCP servers",
                scope=TestScope.INTEGRATION,
                test_file_pattern="test_server_management.py",
                default_suite_id="server-lifecycle-test",
                required_servers=["test-lifecycle-server", "test-npm-server"],
                test_markers=["integration"]
            ),
            TestCategory(
                id="basic-commands",
                name="Basic Commands",
                description="Tests for fundamental CLI commands (help, list, status)",
                scope=TestScope.UNIT,
                test_file_pattern="test_basic_commands.py",
                default_suite_id="basic-commands-test",
                required_servers=["test-basic-server"],
                test_markers=["unit"]
            ),
            TestCategory(
                id="suite-management",
                name="Suite Management", 
                description="Tests for creating and managing MCP server suites",
                scope=TestScope.INTEGRATION,
                test_file_pattern="test_suite_management.py",
                default_suite_id="suite-management-test",
                required_servers=["test-suite-server-1", "test-suite-server-2"],
                test_markers=["integration"]
            ),
            TestCategory(
                id="error-handling",
                name="Error Handling",
                description="Tests for error conditions and edge cases",
                scope=TestScope.ERROR_HANDLING,
                test_file_pattern="test_error_handling.py", 
                default_suite_id="error-handling-test",
                required_servers=["empty-command-server", "invalid-chars-server"],
                test_markers=["error_handling"]
            ),
            TestCategory(
                id="workflows",
                name="User Workflows",
                description="Tests for complete user workflows and journeys",
                scope=TestScope.WORKFLOW,
                test_file_pattern="test_workflows.py",
                default_suite_id="workflows-test",
                required_servers=["workflow-filesystem-server", "workflow-database-server"],
                test_markers=["workflow"]
            ),
            TestCategory(
                id="quality-tracking",
                name="Quality Tracking",
                description="Tests for quality metrics and tracking features",
                scope=TestScope.INTEGRATION,
                test_file_pattern="test_quality_tracking.py",
                default_suite_id="quality-tracking-test",
                required_servers=["high-quality-server", "low-quality-server"],
                test_markers=["integration"]
            )
        ]
        
        for category in default_categories:
            existing = self.db.get_test_category(category.id)
            if not existing:
                self.db.create_test_category(category)
                # Create default suite mapping
                if category.default_suite_id:
                    mapping = TestSuiteMapping(
                        id=f"default-{category.id}",
                        test_category_id=category.id,
                        suite_id=category.default_suite_id,
                        priority=100,  # High priority for defaults
                        created_by="system"
                    )
                    self.db.create_suite_mapping(mapping)
    
    def create_category(self, name: str, description: str, scope: TestScope,
                       test_file_pattern: str, required_servers: List[str] = None,
                       optional_servers: List[str] = None) -> Optional[TestCategory]:
        """Create a new test category."""
        category_id = f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"
        
        category = TestCategory(
            id=category_id,
            name=name,
            description=description,
            scope=scope,
            test_file_pattern=test_file_pattern,
            required_servers=required_servers or [],
            optional_servers=optional_servers or []
        )
        
        if self.db.create_test_category(category):
            logger.info(f"Created test category: {name}")
            return category
        
        return None
    
    def get_category_for_test_file(self, test_file: str) -> Optional[TestCategory]:
        """Get the appropriate test category for a test file."""
        return self.db.find_category_by_test_file(test_file)
    
    def get_suite_for_test_file(self, test_file: str) -> Optional[str]:
        """Get the appropriate suite for a test file."""
        category = self.get_category_for_test_file(test_file)
        if category:
            return self.db.get_suite_for_category(category.id)
        return None
    
    def list_categories(self, scope: Optional[TestScope] = None) -> List[TestCategory]:
        """List all test categories."""
        return self.db.list_test_categories(scope)
    
    def map_category_to_suite(self, category_id: str, suite_id: str, 
                             priority: int = 50, created_by: str = "admin") -> bool:
        """Map a test category to a specific suite."""
        mapping_id = f"{category_id}-{suite_id}-{uuid.uuid4().hex[:8]}"
        
        mapping = TestSuiteMapping(
            id=mapping_id,
            test_category_id=category_id,
            suite_id=suite_id,
            priority=priority,
            created_by=created_by
        )
        
        return self.db.create_suite_mapping(mapping)
    
    def get_category_info(self, category_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a test category."""
        category = self.db.get_test_category(category_id)
        if not category:
            return None
        
        suite_id = self.db.get_suite_for_category(category_id)
        
        return {
            "category": category,
            "suite_id": suite_id,
            "required_servers": category.required_servers,
            "optional_servers": category.optional_servers,
            "test_markers": category.test_markers
        }