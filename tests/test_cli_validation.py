"""Tests for enhanced CLI command validation."""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, AsyncMock

from mcp_manager.cli.main import cli
from mcp_manager.core.models import Server, ServerType, ServerScope


class TestCLIValidation:
    """Test CLI command validation."""

    def test_add_invalid_server_name(self, temp_config_dir):
        """Test adding server with invalid name."""
        runner = CliRunner()
        
        # Test empty name
        result = runner.invoke(cli, ['add', '', 'custom', 'echo test'])
        assert result.exit_code != 0
        
        # Test name with invalid characters
        result = runner.invoke(cli, ['add', 'server!@#$', 'custom', 'echo test'])
        assert result.exit_code != 0
        assert "Server name can only contain" in result.output
        
        # Test reserved name
        result = runner.invoke(cli, ['add', 'null', 'custom', 'echo test'])
        assert result.exit_code != 0
        assert "reserved name" in result.output

    def test_add_invalid_command(self, temp_config_dir):
        """Test adding server with invalid command."""
        runner = CliRunner()
        
        # Test empty command
        result = runner.invoke(cli, ['add', 'test-server', 'custom', ''])
        assert result.exit_code != 0
        
        # Test dangerous command pattern
        result = runner.invoke(cli, ['add', 'test-server', 'custom', 'echo test; rm -rf /'])
        assert result.exit_code != 0
        assert "dangerous pattern" in result.output
        
        # Test Docker command without docker prefix
        result = runner.invoke(cli, ['add', 'test-server', '--type', 'docker', 'run ubuntu'])
        assert result.exit_code != 0
        assert "must start with 'docker'" in result.output

    def test_add_with_validation_suggestions(self, temp_config_dir):
        """Test add command provides helpful suggestions."""
        runner = CliRunner()
        
        # Test invalid name with suggestion
        with patch('mcp_manager.cli.enhanced_commands.Confirm.ask', return_value=False):
            result = runner.invoke(cli, ['add', 'test server!', 'custom', 'echo test'])
            assert result.exit_code != 0
            assert "Did you mean:" in result.output
            assert "test-server" in result.output

    def test_remove_with_confirmation(self, temp_config_dir):
        """Test remove command asks for confirmation."""
        runner = CliRunner()
        
        # First add a server
        result = runner.invoke(cli, ['add', 'test-server', 'custom', 'echo test'])
        assert result.exit_code == 0
        
        # Try to remove without force flag - should ask confirmation
        with patch('mcp_manager.cli.enhanced_commands.Confirm.ask', return_value=False):
            result = runner.invoke(cli, ['remove', 'test-server'])
            assert result.exit_code != 0
            assert "About to remove server" in result.output
            assert "Cancelled" in result.output
        
        # Remove with force flag - should not ask
        result = runner.invoke(cli, ['remove', 'test-server', '--force'])
        assert result.exit_code == 0
        assert "Removed server" in result.output

    def test_remove_nonexistent_server(self, temp_config_dir):
        """Test removing non-existent server provides suggestions."""
        runner = CliRunner()
        
        # Add some servers first
        runner.invoke(cli, ['add', 'test-server-1', 'custom', 'echo 1'])
        runner.invoke(cli, ['add', 'test-server-2', 'custom', 'echo 2'])
        
        # Try to remove non-existent but similar
        result = runner.invoke(cli, ['remove', 'test-srv'])
        assert result.exit_code != 0
        assert "not found" in result.output
        assert "Did you mean one of these?" in result.output
        assert "test-server-1" in result.output
        assert "test-server-2" in result.output

    def test_enable_with_dependency_check(self, temp_config_dir):
        """Test enable command checks dependencies."""
        runner = CliRunner()
        
        # Add a Docker server
        result = runner.invoke(cli, ['add', 'docker-test', '--type', 'docker', 'docker run -i test'])
        assert result.exit_code == 0
        
        # Mock Docker not available
        with patch('shutil.which', return_value=None):
            result = runner.invoke(cli, ['enable', 'docker-test'])
            assert result.exit_code != 0
            assert "Docker is not installed" in result.output

    def test_enable_nonexistent_server(self, temp_config_dir):
        """Test enabling non-existent server."""
        runner = CliRunner()
        
        result = runner.invoke(cli, ['enable', 'nonexistent'])
        assert result.exit_code != 0
        assert "not found" in result.output

    def test_enable_already_enabled(self, temp_config_dir):
        """Test enabling already enabled server."""
        runner = CliRunner()
        
        # Add and enable a server
        runner.invoke(cli, ['add', 'test-server', 'custom', 'echo test'])
        runner.invoke(cli, ['enable', 'test-server'])
        
        # Try to enable again
        result = runner.invoke(cli, ['enable', 'test-server'])
        assert result.exit_code == 0
        assert "already enabled" in result.output

    def test_disable_nonexistent_server(self, temp_config_dir):
        """Test disabling non-existent server."""
        runner = CliRunner()
        
        result = runner.invoke(cli, ['disable', 'nonexistent'])
        assert result.exit_code != 0
        assert "not found" in result.output

    def test_disable_already_disabled(self, temp_config_dir):
        """Test disabling already disabled server."""
        runner = CliRunner()
        
        # Add a server (disabled by default)
        runner.invoke(cli, ['add', 'test-server', 'custom', 'echo test'])
        
        # Try to disable
        result = runner.invoke(cli, ['disable', 'test-server'])
        assert result.exit_code == 0
        assert "already disabled" in result.output

    def test_environment_variable_validation(self, temp_config_dir):
        """Test environment variable format validation."""
        runner = CliRunner()
        
        # Invalid format
        result = runner.invoke(cli, ['add', 'test-server', 'custom', 'echo test', '--env', 'INVALID'])
        assert result.exit_code != 0
        assert "Invalid environment variable format" in result.output
        assert "Expected format: KEY=VALUE" in result.output
        
        # Valid format
        result = runner.invoke(cli, ['add', 'test-server', 'custom', 'echo test', '--env', 'KEY=value'])
        assert result.exit_code == 0

    def test_helpful_next_steps(self, temp_config_dir):
        """Test commands provide helpful next steps."""
        runner = CliRunner()
        
        # Add server shows next steps
        result = runner.invoke(cli, ['add', 'test-server', 'custom', 'echo test'])
        assert result.exit_code == 0
        assert "Next steps:" in result.output
        assert "Enable the server:" in result.output
        assert "Sync with Claude:" in result.output
        
        # Enable server reminds to sync
        result = runner.invoke(cli, ['enable', 'test-server'])
        assert result.exit_code == 0
        assert "Don't forget to sync" in result.output

    def test_npm_package_name_validation(self, temp_config_dir):
        """Test NPM package name validation."""
        runner = CliRunner()
        
        # Valid scoped package
        result = runner.invoke(cli, ['add', '@modelcontextprotocol/server-test', '--type', 'npm', 'npx @modelcontextprotocol/server-test'])
        assert result.exit_code == 0
        
        # Invalid scoped package format
        with patch('mcp_manager.cli.enhanced_commands.Confirm.ask', return_value=False):
            result = runner.invoke(cli, ['add', '@invalid@package', '--type', 'npm', 'npx test'])
            assert result.exit_code != 0