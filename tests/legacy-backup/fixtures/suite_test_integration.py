"""
Integration layer for using test suites in actual tests.

Provides fixtures and helpers to load appropriate test suites and set up
servers in the correct scopes for comprehensive testing.
"""

import asyncio
import pytest
from pathlib import Path
from typing import Dict, Any, List

from mcp_manager.core.simple_manager import SimpleManager
from mcp_manager.core.models import Server, ServerType, ServerScope
from .test_suites_setup import TestSuitesSetup


class SuiteTestIntegration:
    """Integrates test suites with actual test execution."""
    
    def __init__(self, manager: SimpleManager):
        """Initialize with MCP manager instance."""
        self.manager = manager
        self.suite_setup = TestSuitesSetup()
        self.loaded_servers = {}
    
    async def setup_suite_for_test(self, test_name: str) -> Dict[str, Any]:
        """
        Set up test environment using appropriate suite.
        
        Args:
            test_name: Name of the test function
            
        Returns:
            Dict with suite info and created servers
        """
        # Load suite configuration
        suite_data = await self.suite_setup.load_suite_for_test(test_name)
        
        if not suite_data:
            return {"servers": {}, "suite": None}
        
        suite = suite_data["suite"]
        server_configs = suite_data["servers"]
        
        created_servers = {}
        
        # Create servers according to suite configuration
        for server_name, config in server_configs.items():
            try:
                # Skip servers marked as non-existent (for negative testing)
                if config.get("should_exist", True) is False:
                    continue
                
                server = await self._create_server_from_config(server_name, config)
                if server:
                    created_servers[server_name] = server
                    self.loaded_servers[server_name] = server
                    
            except Exception as e:
                # Log but don't fail - some servers are expected to fail
                if not config.get("expected_error"):
                    print(f"Warning: Failed to create server {server_name}: {e}")
        
        return {
            "suite": suite,
            "servers": created_servers,
            "config": server_configs
        }
    
    async def _create_server_from_config(self, server_name: str, config: Dict[str, Any]) -> Server:
        """Create a server from suite configuration."""
        # Handle name override for testing invalid names
        actual_name = config.get("test_name_override", server_name)
        
        # Convert scope string to enum
        scope_str = config.get("scope", "user")
        scope = ServerScope.USER if scope_str == "user" else ServerScope.PROJECT
        
        # Convert type string to enum  
        type_str = config.get("type", "custom")
        server_type = getattr(ServerType, type_str.upper(), ServerType.CUSTOM)
        
        # Create server object
        server = Server(
            name=actual_name,
            command=config.get("command", ""),
            args=config.get("args", []),
            env=config.get("env", {}),
            server_type=server_type,
            scope=scope,
            enabled=config.get("enabled", True),
            working_dir=config.get("working_dir"),
            description=config.get("description", f"Test server from suite")
        )
        
        # Add to manager
        success = await self.manager.add_server(
            name=server.name,
            server_type=server.server_type,
            command=server.command,
            args=server.args,
            env=server.env,
            scope=server.scope,
            working_dir=server.working_dir,
            description=server.description
        )
        
        if success:
            return server
        else:
            raise Exception(f"Failed to add server {server.name}")
    
    async def cleanup_suite_servers(self):
        """Clean up all servers created by suite setup."""
        for server_name, server in self.loaded_servers.items():
            try:
                await self.manager.remove_server(server_name, server.scope)
            except Exception as e:
                print(f"Warning: Failed to cleanup server {server_name}: {e}")
        
        self.loaded_servers.clear()
    
    def get_suite_servers_by_scope(self, scope: ServerScope) -> List[str]:
        """Get list of server names in specific scope."""
        return [
            name for name, server in self.loaded_servers.items()
            if server.scope == scope
        ]
    
    def get_expected_errors_for_test(self, test_name: str) -> Dict[str, str]:
        """Get expected errors for servers in a test suite."""
        # This would be populated from suite configuration
        # For now, return empty dict
        return {}


@pytest.fixture
async def suite_integration(test_manager):
    """Pytest fixture for suite integration."""
    integration = SuiteTestIntegration(test_manager)
    
    # Setup will be done per test
    yield integration
    
    # Cleanup after test
    await integration.cleanup_suite_servers()


def get_test_suite_name(test_function_name: str) -> str:
    """
    Map test function names to suite names.
    
    Args:
        test_function_name: Name of the test function
        
    Returns:
        Corresponding suite name
    """
    mapping = {
        "test_complete_server_lifecycle": "server-lifecycle-test",
        "test_bulk_server_operations": "bulk-operations-test",
        "test_scope_validation": "scope-validation-test", 
        "test_error_handling": "error-handling-test",
        # Lifecycle tests
        "TestServerLifecycle::test_complete_server_lifecycle": "server-lifecycle-test",
        "TestServerLifecycle::test_bulk_server_operations": "bulk-operations-test",
        # Add more mappings as needed
    }
    
    return mapping.get(test_function_name, "")


async def setup_test_environment():
    """Initialize test suites - call this in conftest.py"""
    setup = TestSuitesSetup()
    await setup.create_all_test_suites()
    return setup