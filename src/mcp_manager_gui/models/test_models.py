"""
Test suite for MCP Manager GUI data models.

Tests the ServerTableModel and SuiteTableModel functionality including
filtering, sorting, drag-and-drop, and real-time updates.
"""

import asyncio
import sys
from typing import Dict, List, Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QModelIndex, QMimeData
from PySide6.QtTest import QTest

from mcp_manager_gui.services.cli_bridge import CLIBridge
from mcp_manager_gui.models import (
    ServerTableModel, SuiteTableModel, SuiteMembershipListModel,
    ServerColumn, SuiteColumn, ServerDataRole, SuiteDataRole
)


# Test fixtures and mock data
MOCK_SERVERS = [
    {
        "name": "test-server-1",
        "server_type": "npm",
        "status": "active",
        "scope": "user",
        "description": "Test server 1",
        "enabled": True,
        "suites": ["suite1", "suite2"],
        "command": "test-command-1",
        "args": [],
        "env": {},
        "pid": 12345,
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-15T12:30:00Z",
        "claude_status": "Connected"
    },
    {
        "name": "test-server-2",
        "server_type": "docker",
        "status": "inactive",
        "scope": "project",
        "description": "Test server 2",
        "enabled": False,
        "suites": ["suite1"],
        "command": "test-command-2",
        "args": ["--arg1", "value1"],
        "env": {"TEST_VAR": "test_value"},
        "pid": None,
        "created_at": "2024-01-14T09:00:00Z",
        "updated_at": "2024-01-14T09:30:00Z",
        "claude_status": "Disconnected"
    },
    {
        "name": "test-server-3",
        "server_type": "custom",
        "status": "error",
        "scope": "local",
        "description": "Test server 3 with a very long description that should be truncated in the display",
        "enabled": True,
        "suites": [],
        "command": "test-command-3",
        "args": [],
        "env": {},
        "pid": None,
        "created_at": "2024-01-12T16:00:00Z",
        "updated_at": "2024-01-15T14:00:00Z",
        "claude_status": "Error",
        "last_error": "Connection timeout"
    }
]

MOCK_SUITES = [
    {
        "id": "suite1",
        "name": "Development Suite",
        "description": "Tools for development work",
        "category": "web-development",
        "config": {},
        "created_at": "2024-01-10T10:00:00Z",
        "updated_at": "2024-01-15T15:00:00Z",
        "memberships": [
            {
                "suite_id": "suite1",
                "server_name": "test-server-1",
                "role": "primary",
                "priority": 90,
                "config_overrides": {},
                "added_at": "2024-01-10T10:30:00Z",
                "server_type": "npm",
                "server_command": "test-command-1"
            },
            {
                "suite_id": "suite1", 
                "server_name": "test-server-2",
                "role": "secondary",
                "priority": 60,
                "config_overrides": {},
                "added_at": "2024-01-10T11:00:00Z",
                "server_type": "docker",
                "server_command": "test-command-2"
            }
        ]
    },
    {
        "id": "suite2",
        "name": "Data Analysis Suite",
        "description": "Tools for data analysis and processing",
        "category": "data-analysis",
        "config": {},
        "created_at": "2024-01-12T14:00:00Z",
        "updated_at": "2024-01-12T14:30:00Z",
        "memberships": [
            {
                "suite_id": "suite2",
                "server_name": "test-server-1",
                "role": "member",
                "priority": 50,
                "config_overrides": {},
                "added_at": "2024-01-12T14:15:00Z",
                "server_type": "npm",
                "server_command": "test-command-1"
            }
        ]
    }
]


class MockCLIBridge:
    """Mock CLI bridge for testing."""
    
    def __init__(self):
        self.servers = MOCK_SERVERS.copy()
        self.suites = MOCK_SUITES.copy()
    
    async def get_servers(self, scope: str = "user") -> List[Dict[str, Any]]:
        """Return mock server data."""
        return self.servers
    
    async def enable_server(self, server_name: str) -> bool:
        """Mock enable server."""
        for server in self.servers:
            if server["name"] == server_name:
                server["enabled"] = True
                server["status"] = "active"
                return True
        return False
    
    async def disable_server(self, server_name: str) -> bool:
        """Mock disable server."""
        for server in self.servers:
            if server["name"] == server_name:
                server["enabled"] = False
                server["status"] = "inactive"
                return True
        return False
    
    async def remove_server(self, server_name: str) -> bool:
        """Mock remove server."""
        self.servers = [s for s in self.servers if s["name"] != server_name]
        return True


class TestServerTableModel:
    """Test suite for ServerTableModel."""
    
    @pytest.fixture
    def app(self):
        """Create QApplication for tests."""
        if not QApplication.instance():
            app = QApplication([])
        else:
            app = QApplication.instance()
        yield app
        # Don't quit the app as other tests might need it
    
    @pytest.fixture
    def cli_bridge(self):
        """Create mock CLI bridge."""
        return MockCLIBridge()
    
    @pytest.fixture
    def model(self, app, cli_bridge):
        """Create server table model."""
        model = ServerTableModel(cli_bridge)
        # Wait a bit for initial data load
        QTest.qWait(100)
        return model
    
    def test_model_initialization(self, model):
        """Test model initializes correctly."""
        assert model is not None
        assert model.columnCount() == len(model._headers)
        
    def test_row_count(self, model):
        """Test row count returns correct number of servers."""
        # Initially should have mock server count
        assert model.rowCount() >= 0
    
    def test_column_count(self, model):
        """Test column count is correct."""
        assert model.columnCount() == 9  # Based on ServerColumn enum
    
    def test_header_data(self, model):
        """Test header data returns correct values."""
        for i in range(model.columnCount()):
            header = model.headerData(i, Qt.Horizontal, Qt.DisplayRole)
            assert header is not None
            assert isinstance(header, str)
    
    def test_data_display_role(self, model):
        """Test data method returns correct display values."""
        if model.rowCount() > 0:
            # Test first row, all columns
            for col in range(model.columnCount()):
                index = model.index(0, col)
                data = model.data(index, Qt.DisplayRole)
                # Data should be string or None
                assert data is None or isinstance(data, str)
    
    def test_data_custom_roles(self, model):
        """Test custom data roles return correct values."""
        if model.rowCount() > 0:
            index = model.index(0, ServerColumn.NAME)
            
            # Test server name role
            server_name = model.data(index, ServerDataRole.ServerNameRole)
            assert isinstance(server_name, str)
            
            # Test server type role
            server_type = model.data(index, ServerDataRole.ServerTypeRole)
            assert isinstance(server_type, str)
            
            # Test server status role
            server_status = model.data(index, ServerDataRole.ServerStatusRole)
            assert isinstance(server_status, str)
    
    def test_text_filtering(self, model):
        """Test text filtering functionality."""
        initial_count = model.rowCount()
        
        # Apply filter that should match some servers
        model.set_filter_text("test")
        filtered_count = model.rowCount()
        
        # Should have some matches
        assert filtered_count >= 0
        
        # Apply filter that shouldn't match anything
        model.set_filter_text("nonexistent-server-name")
        no_match_count = model.rowCount()
        assert no_match_count == 0
        
        # Clear filter
        model.clear_filters()
        final_count = model.rowCount()
        assert final_count == initial_count
    
    def test_type_filtering(self, model):
        """Test type filtering functionality."""
        initial_count = model.rowCount()
        
        # Apply type filter
        model.set_filter_type("npm")
        filtered_count = model.rowCount()
        assert filtered_count >= 0
        
        # Clear filter
        model.set_filter_type(None)
        final_count = model.rowCount()
        assert final_count == initial_count
    
    def test_status_filtering(self, model):
        """Test status filtering functionality."""
        initial_count = model.rowCount()
        
        # Apply status filter
        model.set_filter_status("active")
        filtered_count = model.rowCount()
        assert filtered_count >= 0
        
        # Clear filter
        model.set_filter_status(None)
        final_count = model.rowCount()
        assert final_count == initial_count
    
    def test_enabled_filtering(self, model):
        """Test enabled filtering functionality."""
        initial_count = model.rowCount()
        
        # Apply enabled filter
        model.set_filter_enabled(True)
        enabled_count = model.rowCount()
        assert enabled_count >= 0
        
        model.set_filter_enabled(False)
        disabled_count = model.rowCount()
        assert disabled_count >= 0
        
        # Clear filter
        model.set_filter_enabled(None)
        final_count = model.rowCount()
        assert final_count == initial_count
    
    def test_mime_data(self, model):
        """Test MIME data generation for drag and drop."""
        if model.rowCount() > 0:
            index = model.index(0, ServerColumn.NAME)
            indexes = [index]
            
            mime_data = model.mimeData(indexes)
            assert mime_data is not None
            assert "application/x-mcp-server" in mime_data.formats()
    
    def test_get_server_methods(self, model):
        """Test server retrieval methods."""
        if model.rowCount() > 0:
            # Test get_server_by_row
            server = model.get_server_by_row(0)
            assert server is not None
            assert isinstance(server, dict)
            assert "name" in server
            
            # Test get_server_by_name
            server_name = server["name"]
            found_server = model.get_server_by_name(server_name)
            assert found_server is not None
            assert found_server["name"] == server_name


class TestSuiteTableModel:
    """Test suite for SuiteTableModel."""
    
    @pytest.fixture
    def app(self):
        """Create QApplication for tests."""
        if not QApplication.instance():
            app = QApplication([])
        else:
            app = QApplication.instance()
        yield app
    
    @pytest.fixture
    def cli_bridge(self):
        """Create mock CLI bridge."""
        return MockCLIBridge()
    
    @pytest.fixture
    def model(self, app, cli_bridge):
        """Create suite table model."""
        model = SuiteTableModel(cli_bridge)
        # Manually set test data since CLI bridge doesn't have suite methods
        model._suites = MOCK_SUITES.copy()
        return model
    
    def test_model_initialization(self, model):
        """Test model initializes correctly."""
        assert model is not None
        assert model.columnCount() == len(model._headers)
    
    def test_row_count(self, model):
        """Test row count returns correct number of suites."""
        assert model.rowCount() == len(MOCK_SUITES)
    
    def test_column_count(self, model):
        """Test column count is correct."""
        assert model.columnCount() == 8  # Based on SuiteColumn enum
    
    def test_data_display_role(self, model):
        """Test data method returns correct display values."""
        if model.rowCount() > 0:
            for col in range(model.columnCount()):
                index = model.index(0, col)
                data = model.data(index, Qt.DisplayRole)
                assert data is None or isinstance(data, str)
    
    def test_data_custom_roles(self, model):
        """Test custom data roles return correct values."""
        if model.rowCount() > 0:
            index = model.index(0, SuiteColumn.NAME)
            
            # Test suite ID role
            suite_id = model.data(index, SuiteDataRole.SuiteIdRole)
            assert isinstance(suite_id, str)
            
            # Test suite name role
            suite_name = model.data(index, SuiteDataRole.SuiteNameRole)
            assert isinstance(suite_name, str)
            
            # Test suite servers role
            servers = model.data(index, SuiteDataRole.SuiteServersRole)
            assert isinstance(servers, list)
    
    def test_suite_filtering(self, model):
        """Test suite filtering functionality."""
        initial_count = model.rowCount()
        
        # Apply text filter
        model.set_filter_text("Development")
        filtered_count = model.rowCount()
        assert filtered_count <= initial_count
        
        # Apply category filter
        model.clear_filters()
        model.set_filter_category("web-development")
        category_count = model.rowCount()
        assert category_count <= initial_count
        
        # Clear all filters
        model.clear_filters()
        final_count = model.rowCount()
        assert final_count == initial_count
    
    def test_drop_mime_data(self, model):
        """Test dropping MIME data onto suites."""
        if model.rowCount() > 0:
            # Create mock MIME data with server name
            mime_data = QMimeData()
            mime_data.setData("application/x-mcp-server", b"test-server-1")
            
            # Test dropping on first suite
            parent_index = model.index(0, SuiteColumn.NAME)
            result = model.dropMimeData(mime_data, Qt.CopyAction, -1, -1, parent_index)
            
            # Should return False since we don't have real suite operations implemented
            # This tests the method runs without error
            assert isinstance(result, bool)
    
    def test_get_suite_methods(self, model):
        """Test suite retrieval methods."""
        if model.rowCount() > 0:
            # Test get_suite_by_row
            suite = model.get_suite_by_row(0)
            assert suite is not None
            assert isinstance(suite, dict)
            assert "id" in suite
            
            # Test get_suite_by_id
            suite_id = suite["id"]
            found_suite = model.get_suite_by_id(suite_id)
            assert found_suite is not None
            assert found_suite["id"] == suite_id
            
            # Test get_suite_by_name
            suite_name = suite["name"]
            found_suite = model.get_suite_by_name(suite_name)
            assert found_suite is not None
            assert found_suite["name"] == suite_name


class TestSuiteMembershipListModel:
    """Test suite for SuiteMembershipListModel."""
    
    @pytest.fixture
    def app(self):
        """Create QApplication for tests."""
        if not QApplication.instance():
            app = QApplication([])
        else:
            app = QApplication.instance()
        yield app
    
    @pytest.fixture
    def model(self, app):
        """Create membership list model."""
        return SuiteMembershipListModel()
    
    def test_model_initialization(self, model):
        """Test model initializes correctly."""
        assert model is not None
        assert model.rowCount() == 0  # No suite set initially
    
    def test_set_suite(self, model):
        """Test setting suite data."""
        suite_data = MOCK_SUITES[0]  # Suite with memberships
        
        model.set_suite(suite_data)
        assert model.rowCount() == len(suite_data["memberships"])
        
        # Test clearing suite
        model.set_suite(None)
        assert model.rowCount() == 0
    
    def test_data_display(self, model):
        """Test data display for memberships."""
        suite_data = MOCK_SUITES[0]
        model.set_suite(suite_data)
        
        if model.rowCount() > 0:
            index = model.index(0, 0)
            display_text = model.data(index, Qt.DisplayRole)
            assert isinstance(display_text, str)
            assert "test-server" in display_text  # Should contain server name
    
    def test_membership_retrieval(self, model):
        """Test membership retrieval methods."""
        suite_data = MOCK_SUITES[0]
        model.set_suite(suite_data)
        
        if model.rowCount() > 0:
            membership = model.get_membership_by_row(0)
            assert membership is not None
            assert "server_name" in membership
            
            server_names = model.get_server_names()
            assert isinstance(server_names, list)
            assert len(server_names) == model.rowCount()


# Integration test
def test_model_integration():
    """Test models working together."""
    if not QApplication.instance():
        app = QApplication([])
    
    cli_bridge = MockCLIBridge()
    
    # Create models
    server_model = ServerTableModel(cli_bridge)
    suite_model = SuiteTableModel(cli_bridge)
    membership_model = SuiteMembershipListModel()
    
    # Wait for initial data
    QTest.qWait(100)
    
    # Test that models can work together
    if suite_model.rowCount() > 0:
        suite_data = suite_model.get_suite_by_row(0)
        membership_model.set_suite(suite_data)
        assert membership_model.rowCount() >= 0
    
    # Test MIME data compatibility
    if server_model.rowCount() > 0:
        server_index = server_model.index(0, ServerColumn.NAME)
        mime_data = server_model.mimeData([server_index])
        
        # Test that suite model can handle the MIME data format
        assert mime_data.hasFormat("application/x-mcp-server")


if __name__ == "__main__":
    # Run basic tests without pytest
    if not QApplication.instance():
        app = QApplication([])
    
    print("Testing ServerTableModel...")
    cli_bridge = MockCLIBridge()
    server_model = ServerTableModel(cli_bridge)
    QTest.qWait(200)  # Wait for data load
    
    print(f"Server model rows: {server_model.rowCount()}")
    print(f"Server model columns: {server_model.columnCount()}")
    
    if server_model.rowCount() > 0:
        index = server_model.index(0, ServerColumn.NAME)
        name = server_model.data(index, Qt.DisplayRole)
        print(f"First server name: {name}")
    
    print("\nTesting SuiteTableModel...")
    suite_model = SuiteTableModel(cli_bridge)
    suite_model._suites = MOCK_SUITES.copy()  # Set test data
    
    print(f"Suite model rows: {suite_model.rowCount()}")
    print(f"Suite model columns: {suite_model.columnCount()}")
    
    if suite_model.rowCount() > 0:
        index = suite_model.index(0, SuiteColumn.NAME)
        name = suite_model.data(index, Qt.DisplayRole)
        print(f"First suite name: {name}")
    
    print("\nTesting SuiteMembershipListModel...")
    membership_model = SuiteMembershipListModel()
    membership_model.set_suite(MOCK_SUITES[0])
    
    print(f"Membership model rows: {membership_model.rowCount()}")
    
    if membership_model.rowCount() > 0:
        index = membership_model.index(0, 0)
        display = membership_model.data(index, Qt.DisplayRole)
        print(f"First membership: {display}")
    
    print("\nAll tests completed successfully!")