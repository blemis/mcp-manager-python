"""
Simple Collection-Agnostic Test Fixture

Replaces the complex suite auto-loading system with a simple approach
that tests CLI commands without creating or modifying server collections.
"""

import pytest
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path

from mcp_manager.core.simple_manager import SimpleMCPManager
from tests.fixtures.collection_agnostic_runner import CollectionAgnosticTestRunner
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


@pytest.fixture(scope="session")
async def simple_test_environment():
    """
    Simple test environment that doesn't create or modify collections.
    
    Uses whatever collections already exist or works with empty state.
    """
    logger.info("🧪 Setting up simple collection-agnostic test environment")
    
    try:
        # Initialize MCP manager (read-only for testing)
        mcp_manager = SimpleMCPManager()
        
        # Create collection-agnostic test runner
        test_runner = CollectionAgnosticTestRunner(mcp_manager)
        
        # Setup without creating any servers
        await test_runner.setup_test_environment()
        
        logger.info("✅ Simple test environment ready (no server collection modifications)")
        
        yield {
            'mcp_manager': mcp_manager,
            'test_runner': test_runner,
            'environment_type': 'collection_agnostic'
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to setup simple test environment: {e}")
        # Still yield a basic environment for testing
        yield {
            'mcp_manager': None,
            'test_runner': None,
            'environment_type': 'minimal',
            'error': str(e)
        }
    
    finally:
        logger.info("🧹 Cleaning up simple test environment")
        try:
            if 'test_runner' in locals() and test_runner:
                await test_runner.teardown_test_environment()
        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")


class SimpleTestHelper:
    """Helper class for collection-agnostic testing."""
    
    @staticmethod
    def run_cli_test(command: str, expected_outputs: list = None, 
                     expected_exit_code: int = 0, timeout: int = 30) -> Dict[str, Any]:
        """
        Run a CLI command test without any server dependencies.
        
        Args:
            command: CLI command to test
            expected_outputs: List of expected output strings
            expected_exit_code: Expected exit code
            timeout: Command timeout
            
        Returns:
            Test result dictionary
        """
        # Create temporary test runner for this test
        mcp_manager = SimpleMCPManager()
        runner = CollectionAgnosticTestRunner(mcp_manager)
        
        # Execute command
        result = runner.run_cli_command(command, timeout)
        
        # Validate if expectations provided
        if expected_outputs is not None:
            validation = runner.validate_output(result, expected_outputs, expected_exit_code)
            result['validation'] = validation
            result['test_success'] = validation['overall_success']
        else:
            # Just check exit code
            result['test_success'] = result['returncode'] == expected_exit_code
        
        return result
    
    @staticmethod
    def assert_cli_success(result: Dict[str, Any], test_name: str = "CLI test"):
        """Assert that a CLI test was successful."""
        if not result.get('test_success', False):
            error_msg = f"""
{test_name} failed:
Command: {result.get('command', 'unknown')}
Exit code: {result.get('returncode', 'unknown')} (expected 0)
STDOUT: {result.get('stdout', '')}
STDERR: {result.get('stderr', '')}
"""
            if 'validation' in result:
                validation = result['validation']
                if validation.get('missing_output'):
                    error_msg += f"\nMissing expected output: {validation['missing_output']}"
            
            raise AssertionError(error_msg.strip())
    
    @staticmethod
    def test_help_command() -> Dict[str, Any]:
        """Test the help command (always works, server-independent)."""
        return SimpleTestHelper.run_cli_test(
            "mcp-manager --help",
            expected_outputs=["Usage:", "Commands:", "Options:"],
            expected_exit_code=0
        )
    
    @staticmethod
    def test_version_command() -> Dict[str, Any]:
        """Test the version command (always works, server-independent)."""
        return SimpleTestHelper.run_cli_test(
            "mcp-manager --version", 
            expected_outputs=["MCP Manager"],
            expected_exit_code=0
        )
    
    @staticmethod
    def test_list_command() -> Dict[str, Any]:
        """Test the list command (works with any server state)."""
        return SimpleTestHelper.run_cli_test(
            "mcp-manager list",
            expected_outputs=[],  # No specific output required
            expected_exit_code=0
        )
    
    @staticmethod
    def test_collection_list_command() -> Dict[str, Any]:
        """Test the collection list command (works with any collection state)."""
        return SimpleTestHelper.run_cli_test(
            "mcp-manager suite list",
            expected_outputs=[],  # No specific output required
            expected_exit_code=0
        )


# Pytest fixtures for backward compatibility
@pytest.fixture
def simple_test_helper():
    """Provide simple test helper for collection-agnostic testing."""
    return SimpleTestHelper()


@pytest.fixture
async def collection_agnostic_runner():
    """Provide collection-agnostic test runner."""
    mcp_manager = SimpleMCPManager()
    runner = CollectionAgnosticTestRunner(mcp_manager)
    await runner.setup_test_environment()
    
    yield runner
    
    await runner.teardown_test_environment()


# Replacement for the complex suite loading fixtures
@pytest.fixture
def no_suite_loading():
    """
    Fixture that explicitly avoids any suite/collection loading.
    
    Use this instead of suite_loader fixtures to ensure tests
    are collection-agnostic and don't create hardcoded servers.
    """
    logger.info("🚫 Suite auto-loading disabled - using collection-agnostic testing")
    return {
        'suite_loading_disabled': True,
        'test_approach': 'collection_agnostic',
        'message': 'Tests will use existing collections or work with empty state'
    }