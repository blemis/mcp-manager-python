"""
Test suite setup for comprehensive MCP server testing.

Creates and manages test suites with servers in multiple scopes for thorough testing.
"""

import asyncio
from pathlib import Path
from typing import Dict, Any

from mcp_manager.core.suites.suite_manager import SuiteManager
from mcp_manager.core.models import Server, ServerType, ServerScope


class TestSuitesSetup:
    """Manages test suites for comprehensive testing scenarios."""
    
    def __init__(self):
        """Initialize with test database."""
        test_db_path = Path(__file__).parent / "test_suites.db"
        self.suite_manager = SuiteManager(test_db_path)
    
    async def create_basic_commands_test_suite(self):
        """Create suite for testing basic CLI commands."""
        suite_id = "basic-commands-test"
        await self.suite_manager.create_or_update_suite(
            suite_id=suite_id,
            name="Basic Commands Test Suite",
            description="Servers for testing basic CLI commands: list, status, help",
            category="basic-testing"
        )
        
        # Add a few basic servers for command testing
        await self.suite_manager.add_server_to_suite(
            suite_id, "test-basic-server",
            role="primary", priority=90,
            config_overrides={
                "scope": "user",
                "type": "custom",
                "command": "echo basic",
                "description": "Basic test server for CLI commands"
            }
        )
        
        await self.suite_manager.add_server_to_suite(
            suite_id, "test-list-server",
            role="secondary", priority=70,
            config_overrides={
                "scope": "project", 
                "type": "custom",
                "command": "python -c 'print(\"list test\")'",
                "description": "Server for testing list commands"
            }
        )

    async def create_suite_management_test_suite(self):
        """Create suite for testing suite management functionality."""
        suite_id = "suite-management-test"
        await self.suite_manager.create_or_update_suite(
            suite_id=suite_id,
            name="Suite Management Test Suite",
            description="Servers for testing suite creation, modification, and deletion",
            category="suite-testing"
        )
        
        # Add servers for suite testing
        await self.suite_manager.add_server_to_suite(
            suite_id, "test-suite-server-1",
            role="primary", priority=90,
            config_overrides={
                "scope": "user",
                "type": "custom",
                "command": "echo suite-test-1",
                "description": "First suite test server"
            }
        )
        
        await self.suite_manager.add_server_to_suite(
            suite_id, "test-suite-server-2",
            role="secondary", priority=70,
            config_overrides={
                "scope": "project", 
                "type": "custom",
                "command": "echo suite-test-2",
                "description": "Second suite test server"
            }
        )

    async def create_quality_tracking_test_suite(self):
        """Create suite for testing quality tracking functionality."""
        suite_id = "quality-tracking-test"
        await self.suite_manager.create_or_update_suite(
            suite_id=suite_id,
            name="Quality Tracking Test Suite",
            description="Servers for testing quality metrics, recommendations, and analytics",
            category="quality-testing"
        )
        
        # Add servers with different quality characteristics
        await self.suite_manager.add_server_to_suite(
            suite_id, "high-quality-server",
            role="primary", priority=95,
            config_overrides={
                "scope": "user",
                "type": "npm",
                "command": "npx @high-quality/server",
                "description": "High quality server for metrics testing",
                "quality_score": 95
            }
        )
        
        await self.suite_manager.add_server_to_suite(
            suite_id, "low-quality-server",
            role="secondary", priority=30,
            config_overrides={
                "scope": "user", 
                "type": "custom",
                "command": "echo low-quality",
                "description": "Low quality server for comparison testing",
                "quality_score": 30
            }
        )

    async def create_workflows_test_suite(self):
        """Create suite for testing complete user workflows."""
        suite_id = "workflows-test"
        await self.suite_manager.create_or_update_suite(
            suite_id=suite_id,
            name="Workflows Test Suite",
            description="Servers for testing complete user workflows and journeys",
            category="workflow-testing"
        )
        
        # Add servers for different workflow scenarios
        await self.suite_manager.add_server_to_suite(
            suite_id, "workflow-filesystem-server",
            role="primary", priority=90,
            config_overrides={
                "scope": "user",
                "type": "npm",
                "command": "npx @mcp/filesystem",
                "description": "Filesystem server for workflow testing"
            }
        )
        
        await self.suite_manager.add_server_to_suite(
            suite_id, "workflow-database-server",
            role="secondary", priority=80,
            config_overrides={
                "scope": "project", 
                "type": "docker",
                "command": "docker run mcp/database",
                "description": "Database server for workflow testing"
            }
        )
        
        await self.suite_manager.add_server_to_suite(
            suite_id, "workflow-custom-server",
            role="optional", priority=60,
            config_overrides={
                "scope": "user",
                "type": "custom",
                "command": "python workflow_server.py",
                "description": "Custom server for workflow testing"
            }
        )

    async def create_all_test_suites(self):
        """Create all test suites needed for comprehensive testing."""
        await self.create_server_lifecycle_test_suite()
        await self.create_bulk_operations_test_suite()
        await self.create_scope_validation_test_suite()
        await self.create_error_handling_test_suite()
        await self.create_basic_commands_test_suite()
        await self.create_suite_management_test_suite()
        await self.create_quality_tracking_test_suite()
        await self.create_workflows_test_suite()
    
    async def create_server_lifecycle_test_suite(self):
        """
        Create suite for testing complete server lifecycle.
        
        Contains:
        - Valid servers in user scope (for normal operations)
        - Valid servers in project scope (for scope testing)
        - Servers with different types (npm, docker, custom)
        - Enabled and disabled servers
        """
        suite_id = "server-lifecycle-test"
        
        await self.suite_manager.create_or_update_suite(
            suite_id=suite_id,
            name="Server Lifecycle Test Suite",
            description="Servers for testing complete lifecycle: add -> list -> enable -> disable -> remove",
            category="testing",
            config={
                "purpose": "lifecycle_testing",
                "scopes": ["user", "project"],
                "test_scenarios": ["normal_flow", "scope_switching", "type_validation"]
            }
        )
        
        # User scope servers - normal operations
        await self.suite_manager.add_server_to_suite(
            suite_id, "test-lifecycle-server", 
            role="primary", priority=100,
            config_overrides={
                "scope": "user",
                "type": "custom",
                "command": "echo lifecycle",
                "enabled": True
            }
        )
        
        await self.suite_manager.add_server_to_suite(
            suite_id, "test-npm-server", 
            role="secondary", priority=80,
            config_overrides={
                "scope": "user", 
                "type": "npm",
                "command": "npx @test/server",
                "enabled": True
            }
        )
        
        # Project scope servers - scope testing
        await self.suite_manager.add_server_to_suite(
            suite_id, "test-project-server",
            role="secondary", priority=70,
            config_overrides={
                "scope": "project",
                "type": "custom", 
                "command": "python test_server.py",
                "enabled": True
            }
        )
        
        # Disabled server - enable/disable testing
        await self.suite_manager.add_server_to_suite(
            suite_id, "test-disabled-server",
            role="optional", priority=30,
            config_overrides={
                "scope": "user",
                "type": "custom",
                "command": "echo disabled",
                "enabled": False
            }
        )
    
    async def create_bulk_operations_test_suite(self):
        """
        Create suite for testing bulk server operations.
        
        Contains:
        - Multiple servers across different scopes
        - Mix of server types for comprehensive testing
        - Servers with similar names (edge case testing)
        """
        suite_id = "bulk-operations-test"
        
        await self.suite_manager.create_or_update_suite(
            suite_id=suite_id,
            name="Bulk Operations Test Suite", 
            description="Multiple servers for testing bulk add/remove operations",
            category="testing",
            config={
                "purpose": "bulk_testing",
                "server_count": 6,
                "scopes": ["user", "project"],
                "test_scenarios": ["bulk_add", "bulk_remove", "mixed_scopes"]
            }
        )
        
        # Bulk servers in user scope
        for i in range(1, 4):
            await self.suite_manager.add_server_to_suite(
                suite_id, f"bulk-server-{i}",
                role="member", priority=50,
                config_overrides={
                    "scope": "user",
                    "type": "custom",
                    "command": f"echo bulk-{i}",
                    "enabled": True
                }
            )
        
        # Bulk servers in project scope
        for i in range(4, 7):
            await self.suite_manager.add_server_to_suite(
                suite_id, f"bulk-server-{i}",
                role="member", priority=50,
                config_overrides={
                    "scope": "project", 
                    "type": "custom",
                    "command": f"echo bulk-{i}",
                    "enabled": True
                }
            )
        
        # Edge case: similar names
        await self.suite_manager.add_server_to_suite(
            suite_id, "bulk-server-similar",
            role="optional", priority=20,
            config_overrides={
                "scope": "user",
                "type": "custom", 
                "command": "echo similar",
                "enabled": True
            }
        )
        
        await self.suite_manager.add_server_to_suite(
            suite_id, "bulk-server-similar-2", 
            role="optional", priority=20,
            config_overrides={
                "scope": "project",
                "type": "custom",
                "command": "echo similar-2", 
                "enabled": True
            }
        )
    
    async def create_scope_validation_test_suite(self):
        """
        Create suite for testing scope validation and edge cases.
        
        Contains:
        - Servers that exist in one scope but not another
        - Servers with identical names in different scopes  
        - Missing/non-existent servers for negative testing
        """
        suite_id = "scope-validation-test"
        
        await self.suite_manager.create_or_update_suite(
            suite_id=suite_id,
            name="Scope Validation Test Suite",
            description="Servers for testing scope-specific operations and edge cases",
            category="testing", 
            config={
                "purpose": "scope_validation",
                "test_scenarios": ["scope_conflicts", "missing_servers", "cross_scope_operations"],
                "negative_tests": True
            }
        )
        
        # Same name in different scopes - conflict testing
        await self.suite_manager.add_server_to_suite(
            suite_id, "conflicted-server",
            role="primary", priority=90,
            config_overrides={
                "scope": "user",
                "type": "custom",
                "command": "echo user-conflict",
                "enabled": True
            }
        )
        
        await self.suite_manager.add_server_to_suite(
            suite_id, "conflicted-server-project",  # Different name to avoid DB conflicts
            role="primary", priority=90, 
            config_overrides={
                "scope": "project",
                "name_override": "conflicted-server",  # Same logical name, different DB entry
                "type": "custom",
                "command": "echo project-conflict",
                "enabled": True
            }
        )
        
        # User-only server
        await self.suite_manager.add_server_to_suite(
            suite_id, "user-only-server",
            role="secondary", priority=70,
            config_overrides={
                "scope": "user",
                "type": "npm", 
                "command": "npx @user/only",
                "enabled": True
            }
        )
        
        # Project-only server  
        await self.suite_manager.add_server_to_suite(
            suite_id, "project-only-server",
            role="secondary", priority=70,
            config_overrides={
                "scope": "project",
                "type": "docker",
                "command": "docker run test/project",
                "enabled": True
            }
        )
        
        # Placeholder for non-existent server (for negative testing)
        await self.suite_manager.add_server_to_suite(
            suite_id, "nonexistent-server-placeholder",
            role="optional", priority=10,
            config_overrides={
                "scope": "user",
                "type": "custom",
                "command": "echo placeholder",
                "enabled": False,
                "test_purpose": "negative_testing",
                "should_exist": False
            }
        )
    
    async def create_error_handling_test_suite(self):
        """
        Create suite for testing error handling scenarios.
        
        Contains:
        - Servers with invalid configurations
        - Servers with problematic commands
        - Servers that simulate various failure modes
        """
        suite_id = "error-handling-test"
        
        await self.suite_manager.create_or_update_suite(
            suite_id=suite_id,
            name="Error Handling Test Suite",
            description="Servers with problematic configs for testing error handling",
            category="testing",
            config={
                "purpose": "error_testing", 
                "test_scenarios": ["invalid_commands", "missing_dependencies", "permission_errors"],
                "negative_tests": True,
                "expect_failures": True
            }
        )
        
        # Server with empty command
        await self.suite_manager.add_server_to_suite(
            suite_id, "empty-command-server",
            role="optional", priority=20,
            config_overrides={
                "scope": "user",
                "type": "custom",
                "command": "",
                "enabled": True,
                "expected_error": "empty_command"
            }
        )
        
        # Server with invalid characters in name (will be renamed for testing)
        await self.suite_manager.add_server_to_suite(
            suite_id, "invalid-chars-server",
            role="optional", priority=20,
            config_overrides={
                "scope": "user", 
                "type": "custom",
                "command": "echo invalid",
                "enabled": True,
                "test_name_override": "invalid:name with spaces",
                "expected_error": "invalid_characters"
            }
        )
        
        # Server with missing executable
        await self.suite_manager.add_server_to_suite(
            suite_id, "missing-executable-server", 
            role="optional", priority=20,
            config_overrides={
                "scope": "user",
                "type": "custom",
                "command": "/nonexistent/path/to/server",
                "enabled": True,
                "expected_error": "missing_executable"
            }
        )
        
        # Server that times out
        await self.suite_manager.add_server_to_suite(
            suite_id, "timeout-server",
            role="optional", priority=20,
            config_overrides={
                "scope": "user",
                "type": "custom", 
                "command": "sleep 60",  # Will timeout in tests
                "enabled": True,
                "expected_error": "timeout"
            }
        )
    
    async def load_suite_for_test(self, test_name: str) -> Dict[str, Any]:
        """
        Load appropriate test suite based on test name.
        
        Args:
            test_name: Name of the test function
            
        Returns:
            Dict containing suite info and server configurations
        """
        suite_mapping = {
            "test_complete_server_lifecycle": "server-lifecycle-test",
            "test_bulk_server_operations": "bulk-operations-test", 
            "test_scope_validation": "scope-validation-test",
            "test_error_handling": "error-handling-test",
            # Add more mappings as needed
        }
        
        suite_id = suite_mapping.get(test_name)
        if not suite_id:
            return {}
        
        suite = await self.suite_manager.get_suite(suite_id)
        if not suite:
            return {}
        
        return {
            "suite": suite,
            "servers": {
                membership.server_name: membership.config_overrides 
                for membership in suite.memberships
            }
        }
    
    async def cleanup_test_data(self):
        """Clean up test database and temporary files."""
        # Remove test database
        test_db_path = Path(__file__).parent / "test_suites.db"
        if test_db_path.exists():
            test_db_path.unlink()


# Helper function for test setup
async def setup_test_suites():
    """Setup all test suites - call this in test configuration."""
    setup = TestSuitesSetup()
    await setup.create_all_test_suites()
    return setup


if __name__ == "__main__":
    # Create test suites when run directly
    asyncio.run(setup_test_suites())