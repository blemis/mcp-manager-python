"""
Collection-Agnostic Test Suite

Tests CLI functionality without creating or depending on specific server collections.
Works with any existing collections or empty state.
"""

import pytest
from tests.fixtures.simple_test_fixture import SimpleTestHelper


class TestCollectionAgnosticCLI:
    """Test CLI commands without collection dependencies."""
    
    def test_help_command_works(self):
        """Test that help command works regardless of server state."""
        result = SimpleTestHelper.test_help_command()
        SimpleTestHelper.assert_cli_success(result, "Help command test")
    
    def test_version_command_works(self):
        """Test that version command works regardless of server state.""" 
        result = SimpleTestHelper.test_version_command()
        SimpleTestHelper.assert_cli_success(result, "Version command test")
    
    def test_list_command_works(self):
        """Test that list command works with any server configuration."""
        result = SimpleTestHelper.test_list_command()
        SimpleTestHelper.assert_cli_success(result, "List command test")
    
    def test_collection_list_works(self):
        """Test that collection list works with any collection state."""
        result = SimpleTestHelper.test_collection_list_command()
        SimpleTestHelper.assert_cli_success(result, "Collection list test")
    
    def test_status_command_works(self):
        """Test that status command works regardless of configuration."""
        result = SimpleTestHelper.run_cli_test(
            "mcp-manager status",
            expected_outputs=[],  # No specific output required
            expected_exit_code=0
        )
        SimpleTestHelper.assert_cli_success(result, "Status command test")
    
    def test_system_info_works(self):
        """Test that system-info command works independently."""
        result = SimpleTestHelper.run_cli_test(
            "mcp-manager system-info",
            expected_outputs=["System Information"],
            expected_exit_code=0
        )
        SimpleTestHelper.assert_cli_success(result, "System info test")


class TestCollectionAgnosticErrors:
    """Test error handling without collection dependencies."""
    
    def test_invalid_command_fails(self):
        """Test that invalid commands fail appropriately."""
        result = SimpleTestHelper.run_cli_test(
            "mcp-manager invalid-command-that-does-not-exist",
            expected_outputs=["No such command"],
            expected_exit_code=2  # Click exits with 2 for usage errors
        )
        # This should fail, which is the expected behavior
        assert not result['success']
        assert result['returncode'] != 0
    
    def test_invalid_option_fails(self):
        """Test that invalid options fail appropriately."""
        result = SimpleTestHelper.run_cli_test(
            "mcp-manager list --invalid-option-that-does-not-exist",
            expected_outputs=[],
            expected_exit_code=2  # Click exits with 2 for usage errors
        )
        # This should fail, which is the expected behavior
        assert not result['success']
        assert result['returncode'] != 0


# Pytest markers for categorization
pytestmark = pytest.mark.collection_agnostic


# Smoke test subset that can run without any server setup
@pytest.mark.smoke
class TestCollectionAgnosticSmoke:
    """Minimal smoke tests that work without any server configuration."""
    
    def test_application_starts(self):
        """Test that the application starts and shows help."""
        result = SimpleTestHelper.test_help_command()
        SimpleTestHelper.assert_cli_success(result, "Application startup test")
    
    def test_core_commands_available(self):
        """Test that core commands are available."""
        result = SimpleTestHelper.test_help_command()
        SimpleTestHelper.assert_cli_success(result, "Core commands availability test")
        
        # Check that important commands are listed
        output = result['stdout'].lower()
        important_commands = ['list', 'add', 'remove', 'status', 'suite']
        
        for cmd in important_commands:
            assert cmd in output, f"Command '{cmd}' not found in help output"
    
    def test_list_command_baseline(self):
        """Test that list command works (baseline functionality)."""
        result = SimpleTestHelper.test_list_command()
        SimpleTestHelper.assert_cli_success(result, "List command baseline test")
    
    def test_error_handling_works(self):
        """Test that error handling works for invalid commands."""
        result = SimpleTestHelper.run_cli_test(
            "mcp-manager nonexistent-command",
            expected_outputs=[],
            expected_exit_code=2
        )
        # Should fail with exit code 2, which is correct behavior
        assert result['returncode'] == 2