"""
Test CLI functionality of MCP Manager.

Test the command-line interface components.
"""

import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner

from mcp_manager.cli.main import cli
from mcp_manager.core.models import Server, ServerScope, ServerType


class TestCLI:
    """Test CLI commands."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        
    @patch('mcp_manager.cli.main.cli_context')
    def test_list_command(self, mock_context):
        """Test list command."""
        mock_manager = MagicMock()
        mock_context.get_manager.return_value = mock_manager
        
        # Mock server data
        server = Server(
            name="test-server",
            command="echo test",
            scope=ServerScope.USER,
            server_type=ServerType.CUSTOM
        )
        mock_manager.list_servers.return_value = [server]
        
        result = self.runner.invoke(cli, ['list'])
        
        assert result.exit_code == 0
        assert "test-server" in result.output
        mock_manager.list_servers.assert_called_once()
        
    @patch('mcp_manager.cli.main.cli_context')
    def test_add_command(self, mock_context):
        """Test add command."""
        mock_manager = MagicMock()
        mock_context.get_manager.return_value = mock_manager
        
        server = Server(
            name="new-server",
            command="echo new",
            scope=ServerScope.USER,
            server_type=ServerType.CUSTOM
        )
        mock_manager.add_server.return_value = server
        
        result = self.runner.invoke(cli, [
            'add', 'new-server', 'echo new',
            '--scope', 'user',
            '--type', 'custom'
        ])
        
        assert result.exit_code == 0
        mock_manager.add_server.assert_called_once()
        
    @patch('mcp_manager.cli.main.cli_context')
    def test_enable_command(self, mock_context):
        """Test enable command."""
        mock_manager = MagicMock()
        mock_context.get_manager.return_value = mock_manager
        
        server = Server(
            name="test-server",
            command="echo test",
            scope=ServerScope.USER,
            server_type=ServerType.CUSTOM,
            enabled=True
        )
        mock_manager.enable_server.return_value = server
        
        result = self.runner.invoke(cli, ['enable', 'test-server'])
        
        assert result.exit_code == 0
        mock_manager.enable_server.assert_called_once_with('test-server')
        
    @patch('mcp_manager.cli.main.cli_context')
    def test_disable_command(self, mock_context):
        """Test disable command."""
        mock_manager = MagicMock()
        mock_context.get_manager.return_value = mock_manager
        
        server = Server(
            name="test-server",
            command="echo test",
            scope=ServerScope.USER,
            server_type=ServerType.CUSTOM,
            enabled=False
        )
        mock_manager.disable_server.return_value = server
        
        result = self.runner.invoke(cli, ['disable', 'test-server'])
        
        assert result.exit_code == 0
        mock_manager.disable_server.assert_called_once_with('test-server')
        
    @patch('mcp_manager.cli.main.cli_context')
    def test_remove_command(self, mock_context):
        """Test remove command."""
        mock_manager = MagicMock()
        mock_context.get_manager.return_value = mock_manager
        
        mock_manager.remove_server.return_value = True
        
        result = self.runner.invoke(cli, ['remove', 'test-server'], input='y\n')
        
        assert result.exit_code == 0
        mock_manager.remove_server.assert_called_once_with('test-server')
        
    @patch('mcp_manager.cli.main.cli_context')
    def test_sync_command(self, mock_context):
        """Test sync command."""
        mock_manager = MagicMock()
        mock_context.get_manager.return_value = mock_manager
        
        mock_manager.sync_with_claude.return_value = None
        
        result = self.runner.invoke(cli, ['sync'])
        
        assert result.exit_code == 0
        mock_manager.sync_with_claude.assert_called_once()


class TestCLIHelpers:
    """Test CLI helper functions."""
    
    def test_version_option(self):
        """Test version option."""
        runner = CliRunner()
        result = runner.invoke(cli, ['--version'])
        
        assert result.exit_code == 0
        assert "version" in result.output.lower()
        
    def test_help_option(self):
        """Test help option."""
        runner = CliRunner()
        result = runner.invoke(cli, ['--help'])
        
        assert result.exit_code == 0
        assert "Usage:" in result.output