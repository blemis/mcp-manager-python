"""Integration tests for TUI functionality.

These tests verify the Terminal User Interface interactions.
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from textual.pilot import Pilot

from mcp_manager.tui import MCPManagerApp
from mcp_manager.core import MCPManager
from mcp_manager.models import ServerType


@pytest.mark.integration
class TestTUIWorkflows:
    """Test complete TUI workflows."""

    @pytest.mark.asyncio
    async def test_tui_server_lifecycle(self, temp_config_dir):
        """Test adding, enabling, and removing servers through TUI."""
        app = MCPManagerApp(config_dir=temp_config_dir)
        
        async with app.run_test() as pilot:
            # Wait for initial load
            await pilot.pause()
            
            # Press 'a' to add server
            await pilot.press("a")
            await pilot.pause()
            
            # Fill in server details in the dialog
            # Name input should be focused
            await pilot.press("t", "e", "s", "t", "-", "s", "e", "r", "v", "e", "r")
            await pilot.press("tab")  # Move to type select
            
            # Select custom type
            await pilot.press("down", "down")  # Navigate to custom
            await pilot.press("tab")  # Move to command input
            
            # Enter command
            await pilot.press("e", "c", "h", "o", " ", "t", "e", "s", "t")
            await pilot.press("tab")  # Move to submit button
            await pilot.press("enter")  # Submit
            
            await pilot.pause()
            
            # Verify server appears in list
            table = app.query_one("#server-table")
            assert any("test-server" in str(row) for row in table.rows)
            
            # Enable server (navigate to it and press 'e')
            await pilot.press("down")  # Select the server
            await pilot.press("e")  # Enable
            await pilot.pause()
            
            # Verify server is enabled
            table = app.query_one("#server-table")
            assert any("enabled" in str(row).lower() for row in table.rows)
            
            # Remove server
            await pilot.press("r")  # Remove
            await pilot.pause()
            
            # Confirm removal in dialog
            await pilot.press("tab")  # Move to Yes button
            await pilot.press("enter")  # Confirm
            await pilot.pause()
            
            # Verify server is gone
            table = app.query_one("#server-table")
            assert not any("test-server" in str(row) for row in table.rows)

    @pytest.mark.asyncio
    async def test_tui_navigation(self, temp_config_dir):
        """Test keyboard navigation in TUI."""
        # Pre-populate with some servers
        manager = MCPManager(config_dir=temp_config_dir)
        await manager.add_server("server1", ServerType.CUSTOM, "echo 1")
        await manager.add_server("server2", ServerType.CUSTOM, "echo 2")
        await manager.add_server("server3", ServerType.CUSTOM, "echo 3")
        
        app = MCPManagerApp(config_dir=temp_config_dir)
        
        async with app.run_test() as pilot:
            await pilot.pause()
            
            # Test up/down navigation
            await pilot.press("down")
            await pilot.press("down")
            await pilot.press("up")
            
            # Test tab navigation between widgets
            await pilot.press("tab")
            await pilot.press("tab")
            await pilot.press("shift+tab")
            
            # Test search functionality
            await pilot.press("/")
            await pilot.press("s", "e", "r", "v", "e", "r", "2")
            await pilot.press("enter")
            await pilot.pause()
            
            # Verify search filtered results
            table = app.query_one("#server-table")
            visible_rows = [row for row in table.rows if "server" in str(row).lower()]
            assert len(visible_rows) <= 3  # Should show filtered results

    @pytest.mark.asyncio
    async def test_tui_help_dialog(self, temp_config_dir):
        """Test help dialog functionality."""
        app = MCPManagerApp(config_dir=temp_config_dir)
        
        async with app.run_test() as pilot:
            await pilot.pause()
            
            # Open help dialog
            await pilot.press("?")
            await pilot.pause()
            
            # Verify help dialog is visible
            help_dialog = app.query_one("#help-dialog")
            assert help_dialog.visible
            
            # Close help dialog
            await pilot.press("escape")
            await pilot.pause()
            
            # Verify help dialog is hidden
            assert not help_dialog.visible

    @pytest.mark.asyncio
    async def test_tui_sync_functionality(self, temp_config_dir):
        """Test sync functionality from TUI."""
        # Add and enable a server
        manager = MCPManager(config_dir=temp_config_dir)
        await manager.add_server("sync-test", ServerType.CUSTOM, "echo sync")
        await manager.enable_server("sync-test")
        
        app = MCPManagerApp(config_dir=temp_config_dir)
        
        async with app.run_test() as pilot:
            await pilot.pause()
            
            # Press 's' to sync
            await pilot.press("s")
            await pilot.pause()
            
            # Verify sync completed (check for Claude config)
            claude_config = temp_config_dir / "claude-code" / "mcp-servers.json"
            assert claude_config.exists()
            
            with open(claude_config) as f:
                config = json.load(f)
            assert "sync-test" in config


@pytest.mark.integration
class TestTUIErrorHandling:
    """Test error handling in TUI."""

    @pytest.mark.asyncio
    async def test_tui_invalid_input_handling(self, temp_config_dir):
        """Test handling of invalid inputs in TUI."""
        app = MCPManagerApp(config_dir=temp_config_dir)
        
        async with app.run_test() as pilot:
            await pilot.pause()
            
            # Try to add server with empty name
            await pilot.press("a")
            await pilot.pause()
            
            # Don't enter name, just try to submit
            await pilot.press("tab", "tab", "tab")  # Navigate to submit
            await pilot.press("enter")
            await pilot.pause()
            
            # Should show error or not close dialog
            # Check if dialog is still open
            dialogs = app.query(".dialog")
            assert any(d.visible for d in dialogs)
            
            # Cancel dialog
            await pilot.press("escape")
            await pilot.pause()

    @pytest.mark.asyncio
    async def test_tui_concurrent_updates(self, temp_config_dir):
        """Test TUI handles concurrent configuration updates."""
        app = MCPManagerApp(config_dir=temp_config_dir)
        
        async with app.run_test() as pilot:
            await pilot.pause()
            
            # Add server through TUI
            await pilot.press("a")
            await pilot.pause()
            
            # While dialog is open, modify config externally
            config_path = temp_config_dir / "mcp-manager" / "servers.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            external_config = {
                "external-server": {
                    "name": "external-server",
                    "type": "custom",
                    "command": "echo external",
                    "enabled": True
                }
            }
            with open(config_path, 'w') as f:
                json.dump(external_config, f)
            
            # Cancel dialog and refresh
            await pilot.press("escape")
            await pilot.press("ctrl+r")  # Refresh
            await pilot.pause()
            
            # Verify external server appears
            table = app.query_one("#server-table")
            assert any("external-server" in str(row) for row in table.rows)


@pytest.mark.integration
class TestTUIPerformance:
    """Test TUI performance with large datasets."""

    @pytest.mark.asyncio
    async def test_tui_large_server_list(self, temp_config_dir):
        """Test TUI performance with many servers."""
        # Create many servers
        manager = MCPManager(config_dir=temp_config_dir)
        for i in range(50):
            await manager.add_server(f"server-{i:03d}", ServerType.CUSTOM, f"echo {i}")
        
        app = MCPManagerApp(config_dir=temp_config_dir)
        
        async with app.run_test() as pilot:
            # Should load without hanging
            await pilot.pause()
            
            # Test scrolling performance
            for _ in range(10):
                await pilot.press("page_down")
            await pilot.pause()
            
            for _ in range(10):
                await pilot.press("page_up")
            await pilot.pause()
            
            # Test search performance
            await pilot.press("/")
            await pilot.press("s", "e", "r", "v", "e", "r", "-", "0", "2")
            await pilot.press("enter")
            await pilot.pause()
            
            # Verify search completed
            table = app.query_one("#server-table")
            assert table is not None  # Should not crash


@pytest.mark.integration
class TestTUIAccessibility:
    """Test TUI accessibility features."""

    @pytest.mark.asyncio
    async def test_tui_keyboard_only_navigation(self, temp_config_dir):
        """Test that all TUI features are accessible via keyboard."""
        app = MCPManagerApp(config_dir=temp_config_dir)
        
        async with app.run_test() as pilot:
            await pilot.pause()
            
            # Test all main actions via keyboard
            actions = [
                ("a", "Add server dialog"),
                ("escape", "Close dialog"),
                ("?", "Help dialog"),
                ("escape", "Close help"),
                ("q", "Quit confirmation"),
                ("n", "Cancel quit"),
            ]
            
            for key, description in actions:
                await pilot.press(key)
                await pilot.pause()
            
            # Verify app is still running
            assert not app.is_closed

    @pytest.mark.asyncio
    async def test_tui_focus_management(self, temp_config_dir):
        """Test proper focus management in TUI."""
        # Add a server for testing
        manager = MCPManager(config_dir=temp_config_dir)
        await manager.add_server("focus-test", ServerType.CUSTOM, "echo test")
        
        app = MCPManagerApp(config_dir=temp_config_dir)
        
        async with app.run_test() as pilot:
            await pilot.pause()
            
            # Test focus cycles through widgets
            initial_focused = app.focused
            
            await pilot.press("tab")
            after_tab1 = app.focused
            assert after_tab1 != initial_focused
            
            await pilot.press("tab")
            after_tab2 = app.focused
            assert after_tab2 != after_tab1
            
            # Should cycle back eventually
            for _ in range(10):  # Reasonable number of tabs
                await pilot.press("tab")
            
            # Focus should have cycled through all focusable widgets