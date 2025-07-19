"""Integration tests for MCP Manager.

These tests verify complete workflows and interactions between components.
"""

import asyncio
import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from mcp_manager.cli.main import cli
from mcp_manager.core.manager import MCPManager
from mcp_manager.core.models import MCPServer, ServerType


@pytest.mark.integration
class TestCLIWorkflows:
    """Test complete CLI workflows."""

    def test_add_enable_sync_remove_workflow(self, temp_config_dir):
        """Test the complete lifecycle of adding, enabling, syncing, and removing a server."""
        runner = CliRunner()
        config_path = temp_config_dir / "mcp-manager" / "servers.json"
        claude_config_path = temp_config_dir / "claude-code" / "mcp-servers.json"
        
        # Ensure directories exist
        config_path.parent.mkdir(parents=True, exist_ok=True)
        claude_config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Step 1: Add a server
        result = runner.invoke(cli, ['add', 'test-server', 'custom', 'echo "test"'])
        assert result.exit_code == 0
        assert "Added server 'test-server'" in result.output
        
        # Verify server was added to configuration
        assert config_path.exists()
        with open(config_path) as f:
            config = json.load(f)
        assert 'test-server' in config
        assert config['test-server']['type'] == 'custom'
        assert config['test-server']['command'] == 'echo "test"'
        assert config['test-server']['enabled'] is False
        
        # Step 2: Enable the server
        result = runner.invoke(cli, ['enable', 'test-server'])
        assert result.exit_code == 0
        assert "Enabled server 'test-server'" in result.output
        
        # Verify server was enabled
        with open(config_path) as f:
            config = json.load(f)
        assert config['test-server']['enabled'] is True
        
        # Step 3: Sync with Claude
        result = runner.invoke(cli, ['sync'])
        assert result.exit_code == 0
        assert "Synced configuration with Claude CLI" in result.output
        
        # Verify Claude config was created
        assert claude_config_path.exists()
        with open(claude_config_path) as f:
            claude_config = json.load(f)
        assert 'test-server' in claude_config
        assert claude_config['test-server']['command'] == 'echo "test"'
        
        # Step 4: Remove the server
        result = runner.invoke(cli, ['remove', 'test-server'])
        assert result.exit_code == 0
        assert "Removed server 'test-server'" in result.output
        
        # Verify server was removed
        with open(config_path) as f:
            config = json.load(f)
        assert 'test-server' not in config
        
        # Sync again to update Claude config
        result = runner.invoke(cli, ['sync'])
        assert result.exit_code == 0
        
        # Verify server was removed from Claude config
        with open(claude_config_path) as f:
            claude_config = json.load(f)
        assert 'test-server' not in claude_config

    def test_docker_server_workflow(self, temp_config_dir):
        """Test adding and managing Docker MCP servers."""
        runner = CliRunner()
        
        # Mock docker availability check
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            
            # Add Docker server
            result = runner.invoke(cli, ['add', 'docker-puppeteer', 'docker'])
            assert result.exit_code == 0
            assert "Added server 'docker-puppeteer'" in result.output
            
            # List servers to verify
            result = runner.invoke(cli, ['list'])
            assert result.exit_code == 0
            assert 'docker-puppeteer' in result.output
            assert 'docker' in result.output
            assert 'disabled' in result.output.lower()

    def test_npm_server_workflow(self, temp_config_dir):
        """Test adding and managing NPM MCP servers."""
        runner = CliRunner()
        
        # Add NPM server
        result = runner.invoke(cli, ['add', '@modelcontextprotocol/server-filesystem', 'npm'])
        assert result.exit_code == 0
        assert "Added server '@modelcontextprotocol/server-filesystem'" in result.output
        
        # Enable the server
        result = runner.invoke(cli, ['enable', '@modelcontextprotocol/server-filesystem'])
        assert result.exit_code == 0
        
        # List to verify
        result = runner.invoke(cli, ['list'])
        assert result.exit_code == 0
        assert '@modelcontextprotocol/server-filesystem' in result.output
        assert 'npm' in result.output
        assert 'enabled' in result.output.lower()

    def test_multiple_servers_management(self, temp_config_dir):
        """Test managing multiple servers simultaneously."""
        runner = CliRunner()
        
        servers = [
            ('server1', 'custom', 'echo "1"'),
            ('server2', 'custom', 'echo "2"'),
            ('server3', 'custom', 'echo "3"'),
        ]
        
        # Add multiple servers
        for name, server_type, command in servers:
            result = runner.invoke(cli, ['add', name, server_type, command])
            assert result.exit_code == 0
        
        # Enable all servers
        for name, _, _ in servers:
            result = runner.invoke(cli, ['enable', name])
            assert result.exit_code == 0
        
        # List all servers
        result = runner.invoke(cli, ['list'])
        assert result.exit_code == 0
        for name, _, _ in servers:
            assert name in result.output
            assert 'enabled' in result.output.lower()
        
        # Disable one server
        result = runner.invoke(cli, ['disable', 'server2'])
        assert result.exit_code == 0
        
        # Verify mixed states
        result = runner.invoke(cli, ['list'])
        assert result.exit_code == 0
        # Check each server's status in the output
        lines = result.output.split('\n')
        server1_line = next(line for line in lines if 'server1' in line)
        server2_line = next(line for line in lines if 'server2' in line)
        server3_line = next(line for line in lines if 'server3' in line)
        
        assert 'enabled' in server1_line.lower()
        assert 'disabled' in server2_line.lower()
        assert 'enabled' in server3_line.lower()


@pytest.mark.integration
class TestConfigurationPersistence:
    """Test configuration file persistence across operations."""

    async def test_config_persistence_across_restarts(self, temp_config_dir):
        """Test that configuration persists across manager instances."""
        # Create first manager instance
        manager1 = MCPManager(config_dir=temp_config_dir)
        
        # Add servers
        await manager1.add_server("persistent-server", ServerType.CUSTOM, "echo test")
        await manager1.enable_server("persistent-server")
        
        # Get current state
        servers1 = await manager1.list_servers()
        assert len(servers1) == 1
        assert servers1[0].name == "persistent-server"
        assert servers1[0].enabled is True
        
        # Create second manager instance (simulating restart)
        manager2 = MCPManager(config_dir=temp_config_dir)
        
        # Verify state persisted
        servers2 = await manager2.list_servers()
        assert len(servers2) == 1
        assert servers2[0].name == "persistent-server"
        assert servers2[0].enabled is True
        assert servers2[0].command == "echo test"

    def test_project_override_persistence(self, temp_config_dir):
        """Test project-level configuration overrides."""
        runner = CliRunner()
        
        with runner.isolated_filesystem():
            # Add a server globally
            result = runner.invoke(cli, ['add', 'test-server', 'custom', 'echo "global"'])
            assert result.exit_code == 0
            
            # Enable globally
            result = runner.invoke(cli, ['enable', 'test-server'])
            assert result.exit_code == 0
            
            # Create project override to disable
            project_config = {
                "test-server": {
                    "enabled": False
                }
            }
            with open('.mcp-config.json', 'w') as f:
                json.dump(project_config, f)
            
            # List should show disabled (project override)
            result = runner.invoke(cli, ['list'])
            assert result.exit_code == 0
            assert 'test-server' in result.output
            assert 'disabled' in result.output.lower()
            assert 'project override' in result.output.lower()


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling and recovery scenarios."""

    def test_invalid_server_operations(self, temp_config_dir):
        """Test handling of invalid server operations."""
        runner = CliRunner()
        
        # Try to enable non-existent server
        result = runner.invoke(cli, ['enable', 'non-existent'])
        assert result.exit_code != 0
        assert "Server 'non-existent' not found" in result.output
        
        # Try to remove non-existent server
        result = runner.invoke(cli, ['remove', 'non-existent'])
        assert result.exit_code != 0
        assert "Server 'non-existent' not found" in result.output
        
        # Add server with invalid type
        result = runner.invoke(cli, ['add', 'test', 'invalid-type', 'echo test'])
        assert result.exit_code != 0
        assert "Invalid value for 'TYPE'" in result.output

    def test_corrupted_config_recovery(self, temp_config_dir):
        """Test recovery from corrupted configuration files."""
        runner = CliRunner()
        config_path = temp_config_dir / "mcp-manager" / "servers.json"
        
        # Create corrupted config
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            f.write("{ invalid json }")
        
        # Try to list servers (should handle gracefully)
        result = runner.invoke(cli, ['list'])
        assert result.exit_code == 0  # Should recover and show empty list
        
        # Add a server (should recreate valid config)
        result = runner.invoke(cli, ['add', 'recovery-test', 'custom', 'echo test'])
        assert result.exit_code == 0
        
        # Verify config is now valid
        with open(config_path) as f:
            config = json.load(f)  # Should not raise
        assert 'recovery-test' in config


@pytest.mark.integration
class TestConcurrentOperations:
    """Test concurrent operations and thread safety."""

    async def test_concurrent_server_operations(self, temp_config_dir):
        """Test concurrent add/enable/disable operations."""
        manager = MCPManager(config_dir=temp_config_dir)
        
        # Define concurrent operations
        async def add_server(name: str):
            await manager.add_server(name, ServerType.CUSTOM, f"echo {name}")
        
        async def enable_disable_server(name: str):
            await manager.enable_server(name)
            await asyncio.sleep(0.01)  # Small delay
            await manager.disable_server(name)
        
        # Run operations concurrently
        server_names = [f"concurrent-{i}" for i in range(5)]
        
        # Add all servers concurrently
        await asyncio.gather(*[add_server(name) for name in server_names])
        
        # Verify all were added
        servers = await manager.list_servers()
        assert len(servers) == 5
        
        # Enable/disable concurrently
        await asyncio.gather(*[enable_disable_server(name) for name in server_names])
        
        # Verify final state (all should be disabled)
        servers = await manager.list_servers()
        for server in servers:
            assert server.enabled is False


@pytest.mark.integration
class TestClaudeIntegration:
    """Test integration with Claude CLI configuration."""

    def test_claude_config_sync(self, temp_config_dir):
        """Test syncing with Claude CLI configuration."""
        runner = CliRunner()
        claude_config_path = temp_config_dir / "claude-code" / "mcp-servers.json"
        
        # Add multiple servers with different states
        servers = [
            ('enabled-server', 'custom', 'echo "enabled"', True),
            ('disabled-server', 'custom', 'echo "disabled"', False),
            ('docker-server', 'docker', None, True),
        ]
        
        for name, server_type, command, should_enable in servers:
            if command:
                result = runner.invoke(cli, ['add', name, server_type, command])
            else:
                result = runner.invoke(cli, ['add', name, server_type])
            assert result.exit_code == 0
            
            if should_enable:
                result = runner.invoke(cli, ['enable', name])
                assert result.exit_code == 0
        
        # Sync with Claude
        result = runner.invoke(cli, ['sync'])
        assert result.exit_code == 0
        
        # Verify Claude config only has enabled servers
        assert claude_config_path.exists()
        with open(claude_config_path) as f:
            claude_config = json.load(f)
        
        assert 'enabled-server' in claude_config
        assert 'docker-server' in claude_config
        assert 'disabled-server' not in claude_config
        
        # Verify commands are correct
        assert claude_config['enabled-server']['command'] == 'echo "enabled"'
        assert 'docker' in claude_config['docker-server']['command']

    def test_claude_config_backup(self, temp_config_dir):
        """Test that existing Claude config is backed up before sync."""
        runner = CliRunner()
        claude_config_path = temp_config_dir / "claude-code" / "mcp-servers.json"
        
        # Create existing Claude config
        claude_config_path.parent.mkdir(parents=True, exist_ok=True)
        existing_config = {"existing-server": {"command": "existing command"}}
        with open(claude_config_path, 'w') as f:
            json.dump(existing_config, f)
        
        # Add and enable a new server
        result = runner.invoke(cli, ['add', 'new-server', 'custom', 'new command'])
        assert result.exit_code == 0
        result = runner.invoke(cli, ['enable', 'new-server'])
        assert result.exit_code == 0
        
        # Sync
        result = runner.invoke(cli, ['sync'])
        assert result.exit_code == 0
        
        # Verify backup was created
        backup_files = list(claude_config_path.parent.glob("mcp-servers.json.backup.*"))
        assert len(backup_files) > 0
        
        # Verify backup contains original content
        with open(backup_files[0]) as f:
            backup_config = json.load(f)
        assert backup_config == existing_config