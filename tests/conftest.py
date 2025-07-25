"""
Pytest configuration and fixtures for MCP Manager testing.

Professional SRE-level testing infrastructure with complete test isolation.
Based on research of CLI testing best practices and pytest advanced features.
"""

import pytest
import tempfile
import shutil
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
import subprocess
import time


class TestEnvironment:
    """Isolated test environment for MCP Manager testing."""
    
    def __init__(self, temp_dir: str):
        self.temp_dir = Path(temp_dir)
        self.config_dir = self.temp_dir / "config"
        self.data_dir = self.temp_dir / "data"
        self.logs_dir = self.temp_dir / "logs"
        
        # Create directory structure
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Track created resources for cleanup
        self.created_suites = []
        self.created_servers = []
        
        # Set environment variables for isolation
        self.original_env = dict(os.environ)
        os.environ['MCP_MANAGER_CONFIG_DIR'] = str(self.config_dir)
        os.environ['MCP_MANAGER_DATA_DIR'] = str(self.data_dir)
        os.environ['MCP_MANAGER_LOG_DIR'] = str(self.logs_dir)
    
    def cleanup(self):
        """Clean up test environment and restore original state."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def add_suite(self, suite_name: str):
        """Track created suite for cleanup."""
        self.created_suites.append(suite_name)
    
    def add_server(self, server_name: str):
        """Track created server for cleanup."""
        self.created_servers.append(server_name)


class CLITestRunner:
    """Professional CLI test runner with comprehensive validation."""
    
    def __init__(self, test_env: TestEnvironment):
        self.test_env = test_env
        # Use direct CLI invocation to avoid module import issues
        self.use_direct_cli = True
    
    def _build_direct_command(self, cmd: str) -> list:
        """Build command list for direct CLI invocation."""
        # Import here to avoid circular imports
        import sys
        import shlex
        
        # Parse the command arguments
        args = shlex.split(cmd) if cmd.strip() else []
        
        # Build command as list for subprocess
        return [sys.executable, "-m", "mcp_manager.cli.main"] + args
    
    def run_command(self, cmd: str, expect_success: bool = True, 
                   timeout: int = 30, input_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Run CLI command and validate results.
        
        Args:
            cmd: Command to run (CLI arguments only)
            expect_success: Whether command should succeed
            timeout: Command timeout in seconds
            input_text: Optional stdin input
            
        Returns:
            Dictionary with command results and validation info
        """
        if self.use_direct_cli:
            # Use direct CLI invocation to avoid module import issues
            cmd_list = self._build_direct_command(cmd)
            full_cmd_str = " ".join(cmd_list)
        else:
            # Fallback to subprocess approach
            full_cmd_str = f"python -m mcp_manager.cli.main {cmd}"
            cmd_list = full_cmd_str.split()
        
        try:
            result = subprocess.run(
                cmd_list,
                shell=False,  # Use list format, no shell needed
                capture_output=True,
                text=True,
                input=input_text,
                timeout=timeout,
                cwd=str(self.test_env.temp_dir)
            )
            
            success = (result.returncode == 0) if expect_success else (result.returncode != 0)
            
            return {
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'success': success,
                'command': full_cmd_str,
                'expected_success': expect_success
            }
            
        except subprocess.TimeoutExpired:
            return {
                'returncode': -1,
                'stdout': '',
                'stderr': f'Command timed out after {timeout}s',
                'success': False,
                'command': full_cmd_str,
                'error': 'timeout'
            }
        except Exception as e:
            return {
                'returncode': -2,
                'stdout': '',
                'stderr': str(e),
                'success': False,
                'command': full_cmd_str,
                'error': str(e)
            }
    
    def validate_json_output(self, output: str) -> bool:
        """Validate that output is valid JSON."""
        try:
            json.loads(output)
            return True
        except (json.JSONDecodeError, TypeError):
            return False
    
    def validate_table_output(self, output: str) -> bool:
        """Validate table-formatted output has headers and data."""
        lines = output.strip().split('\n')
        return len(lines) >= 2 and '|' in lines[0]
    
    def assert_contains_all(self, text: str, expected_items: list) -> bool:
        """Assert text contains all expected items."""
        text_lower = text.lower()
        return all(item.lower() in text_lower for item in expected_items)
    
    def assert_output_pattern(self, output: str, pattern: str) -> bool:
        """Check if output matches expected pattern."""
        import re
        return bool(re.search(pattern, output, re.IGNORECASE))


@pytest.fixture(scope="function")
def isolated_environment():
    """Provide completely isolated test environment."""
    # Run nuke command to clean up any existing servers before each test
    import subprocess
    import sys
    
    try:
        # Clean up existing MCP servers to ensure isolation
        result = subprocess.run(
            [sys.executable, "-m", "mcp_manager.cli.main", "nuke", "--force"],
            capture_output=True,
            text=True,
            timeout=30
        )
        # Don't fail if nuke fails - just log and continue
        if result.returncode != 0:
            print(f"Warning: nuke command failed: {result.stderr}")
    except Exception as e:
        print(f"Warning: Could not run nuke command: {e}")
    
    with tempfile.TemporaryDirectory(prefix="mcp_test_") as temp_dir:
        env = TestEnvironment(temp_dir)
        try:
            yield env
        finally:
            env.cleanup()


@pytest.fixture(scope="function")
def cli_runner(isolated_environment):
    """Provide CLI test runner with isolated environment."""
    return CLITestRunner(isolated_environment)


@pytest.fixture(scope="function")
def test_data_manager(isolated_environment):
    """Provide test data manager for creating test fixtures."""
    from tests.utils.test_data_manager import TestDataManager
    return TestDataManager(isolated_environment)


@pytest.fixture(scope="function")
def test_manager(isolated_environment):
    """Provide MCP manager instance for testing."""
    from mcp_manager.core.simple_manager import SimpleMCPManager
    import asyncio
    
    # Create manager with test configuration
    manager = SimpleMCPManager()
    
    yield manager
    
    # Cleanup: remove any servers that were added during testing
    async def cleanup():
        try:
            servers = await manager.list_servers()
            for server in servers:
                try:
                    await manager.remove_server(server.name, server.scope)
                except Exception:
                    pass  # Ignore cleanup errors
        except Exception:
            pass  # Ignore cleanup errors
    
    try:
        asyncio.run(cleanup())
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture(scope="function")
def suite_loader(test_manager):
    """Provide suite loader for ALL test files with verbose output."""
    try:
        from tests.fixtures.suite_loader import SuiteLoader
        return SuiteLoader(test_manager)
    except ImportError as e:
        print(f"⚠️  Suite loader not available: {e}")
        return None


@pytest.fixture(scope="function")
def suite_setup(suite_loader):
    """Provide suite setup functionality for ALL test files."""
    try:
        from tests.fixtures.test_suites_setup import TestSuitesSetup
        setup = TestSuitesSetup()
        return setup
    except ImportError as e:
        print(f"⚠️  Suite setup not available: {e}")
        return None


@pytest.fixture(scope="function")
def dynamic_suite_loader(test_manager):
    """Provide dynamic suite loader that auto-determines correct suite for each test."""
    try:
        from tests.fixtures.dynamic_suite_loader import DynamicSuiteLoader
        return DynamicSuiteLoader(test_manager)
    except ImportError as e:
        print(f"⚠️  Dynamic suite loader not available: {e}")
        return None


@pytest.fixture(scope="function")
def auto_suite_setup(request, dynamic_suite_loader):
    """Automatically load appropriate suite based on test context."""
    if not dynamic_suite_loader:
        return None
    
    # Get test instance (the 'self' of the test class)
    test_instance = request.instance
    if not test_instance:
        return None
    
    # Auto-load suite
    import asyncio
    
    async def load_suite():
        try:
            return await dynamic_suite_loader.auto_load_suite_for_test(test_instance)
        except Exception as e:
            print(f"⚠️  Auto suite loading failed: {e}")
            return None
    
    try:
        suite_data = asyncio.run(load_suite())
        # Store in test instance for access in tests
        if hasattr(test_instance, '__dict__'):
            test_instance.auto_suite_data = suite_data
        return suite_data
    except Exception as e:
        print(f"⚠️  Auto suite setup failed: {e}")
        return None


# Parametrized fixtures for comprehensive testing
@pytest.fixture(params=[
    ("npm", "npx @pkg/server", ["--arg"]),
    ("docker", "docker run server", []),
    ("custom", "python server.py", ["--config"]),
])
def server_type_data(request):
    """Parametrized server type data for testing."""
    return request.param


@pytest.fixture(params=[
    ("filesystem", 3, {"type": "npm"}),
    ("database", 5, {"type": "docker"}),
    ("*", 10, {"limit": 10}),
])
def discovery_test_data(request):
    """Parametrized discovery test data."""
    query, expected_count, filters = request.param
    return {
        'query': query,
        'expected_count': expected_count,
        'filters': filters
    }


@pytest.fixture
def sample_suite_data():
    """Sample suite data for testing."""
    return {
        'name': 'test-suite',
        'description': 'Test suite for automated testing',
        'category': 'testing',
        'servers': [
            {'name': 'filesystem', 'role': 'primary', 'priority': 90},
            {'name': 'sqlite', 'role': 'member', 'priority': 80},
            {'name': 'http', 'role': 'member', 'priority': 70}
        ]
    }


# Performance testing fixtures
@pytest.fixture
def performance_config():
    """Configuration for performance testing."""
    return {
        'max_execution_time': 30,  # seconds
        'concurrent_operations': 5,
        'large_dataset_size': 100
    }


# Error condition fixtures
@pytest.fixture(params=[
    "invalid-command",
    "nonexistent-suite",
    "malformed-json",
    "permission-denied"
])
def error_conditions(request):
    """Parametrized error conditions for testing."""
    return request.param


# Test markers for categorizing tests
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "smoke: Smoke tests")
    config.addinivalue_line("markers", "regression: Regression tests")
    config.addinivalue_line("markers", "slow: Slow running tests")


# Hook for test result reporting
def pytest_runtest_logreport(report):
    """Custom test result logging."""
    if report.when == "call":
        if report.outcome == "failed":
            # Log failed test details for debugging
            with open("test_failures.log", "a") as f:
                f.write(f"FAILED: {report.nodeid}\n")
                f.write(f"Error: {report.longrepr}\n")
                f.write("-" * 80 + "\n")