"""
Test core functionality of MCP Manager.

Basic unit tests for core classes and functionality.
"""

import pytest
from unittest.mock import MagicMock, patch

from mcp_manager.core.exceptions import ServerError
from mcp_manager.core.manager import MCPManager
from mcp_manager.core.models import Server, ServerScope, ServerType
from mcp_manager.utils.config import Config


class TestMCPManager:
    """Test MCPManager class."""
        
    def test_add_server(self, manager):
        """Test adding a server."""
        server = manager.add_server(
            name="test-server",
            command="echo test",
            scope=ServerScope.USER,
            server_type=ServerType.CUSTOM,
        )
        
        assert server.name == "test-server"
        assert server.command == "echo test"
        assert server.scope == ServerScope.USER
        assert server.server_type == ServerType.CUSTOM
        
    def test_add_duplicate_server(self, manager):
        """Test adding duplicate server raises error."""
        manager.add_server(
            name="test-server",
            command="echo test",
            scope=ServerScope.USER,
            server_type=ServerType.CUSTOM,
        )
        
        with pytest.raises(ServerError):
            manager.add_server(
                name="test-server",
                command="echo test2",
                scope=ServerScope.USER,
                server_type=ServerType.CUSTOM,
            )
            
    def test_list_servers(self, manager):
        """Test listing servers."""
        manager.add_server("server1", "cmd1", ServerScope.USER, server_type=ServerType.CUSTOM)
        manager.add_server("server2", "cmd2", ServerScope.LOCAL, server_type=ServerType.CUSTOM)
        
        all_servers = manager.list_servers()
        assert len(all_servers) == 2
        
        user_servers = manager.list_servers(ServerScope.USER)
        assert len(user_servers) == 1
        assert user_servers[0].name == "server1"
        
    def test_enable_disable_server(self, manager):
        """Test enabling and disabling servers."""
        server = manager.add_server("test", "cmd", ServerScope.USER, server_type=ServerType.CUSTOM)
        assert server.enabled is True
        
        disabled = manager.disable_server("test")
        assert disabled.enabled is False
        
        enabled = manager.enable_server("test")
        assert enabled.enabled is True
        
    def test_remove_server(self, manager):
        """Test removing a server."""
        manager.add_server("test", "cmd", ServerScope.USER, server_type=ServerType.CUSTOM)
        
        result = manager.remove_server("test")
        assert result is True
        
        servers = manager.list_servers()
        assert len(servers) == 0
        
    def test_remove_nonexistent_server(self, manager):
        """Test removing nonexistent server raises error."""
        with pytest.raises(ServerError):
            manager.remove_server("nonexistent")


class TestServer:
    """Test Server model."""
    
    def test_server_creation(self):
        """Test creating a server."""
        server = Server(
            name="test",
            command="echo test",
            scope=ServerScope.USER,
            server_type=ServerType.NPM,
        )
        
        assert server.name == "test"
        assert server.command == "echo test"
        assert server.scope == ServerScope.USER
        assert server.server_type == ServerType.NPM
        assert server.enabled is True
        
    def test_server_validation(self):
        """Test server validation."""
        with pytest.raises(ValueError):
            Server(
                name="",  # Empty name should fail
                command="echo test",
                scope=ServerScope.USER,
                server_type=ServerType.NPM,
            )
            
    def test_to_claude_config(self):
        """Test converting to Claude configuration."""
        server = Server(
            name="test",
            command="npx test",
            scope=ServerScope.USER,
            server_type=ServerType.NPM,
            args=["--arg1", "--arg2"],
            env={"VAR1": "value1"},
            working_dir="/tmp",
        )
        
        config = server.to_claude_config()
        
        assert config["command"] == "npx test"
        assert config["args"] == ["--arg1", "--arg2"]
        assert config["env"] == {"VAR1": "value1"}
        assert config["cwd"] == "/tmp"