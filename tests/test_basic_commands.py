"""
Basic CLI command testing for MCP Manager.

Tests fundamental CLI functionality that every user would try first.
Professional black-box testing with no knowledge of internals.
"""

import pytest
from tests.utils.validators import OutputValidator, TestAssertions


class TestBasicCommands:
    """Test basic CLI commands every user would try."""
    
    def test_help_command(self, cli_runner):
        """Test main help command works and shows usage."""
        result = cli_runner.run_command("--help")
        
        TestAssertions.assert_command_success(result, "Main help command")
        assert OutputValidator.validate_help_output(result['stdout'])
        TestAssertions.assert_contains_all(
            result['stdout'], 
            ['Usage:', 'Commands:', 'Options:'], 
            "Help shows required sections"
        )
    
    def test_version_command(self, cli_runner):
        """Test version command (may not be implemented)."""
        result = cli_runner.run_command("--version", expect_success=False)
        
        # Version might not be implemented, either success or graceful failure is OK
        if result['success']:
            assert OutputValidator.validate_version_output(result['stdout'])
    
    @pytest.mark.parametrize("command", [
        "list",
        "list --scope user",
        "list --scope project", 
        "status",
        "system-info"
    ])
    def test_basic_info_commands(self, cli_runner, command):
        """Test basic information commands work."""
        result = cli_runner.run_command(command)
        
        TestAssertions.assert_command_success(result, f"Command: {command}")
        # These commands should always produce some output
        assert result['stdout'].strip() != "", f"Command {command} produced no output"
    
    def test_command_help_subcommands(self, cli_runner):
        """Test help for major subcommands."""
        subcommands = [
            "discover --help",
            "suite --help", 
            "quality --help",
            "add --help",
            "install --help"
        ]
        
        for cmd in subcommands:
            result = cli_runner.run_command(cmd)
            TestAssertions.assert_command_success(result, f"Help for {cmd}")
            assert OutputValidator.validate_help_output(result['stdout'])
    
    def test_invalid_command_handling(self, cli_runner):
        """Test invalid commands fail gracefully."""
        result = cli_runner.run_command("invalid-command-xyz", expect_success=False)
        
        TestAssertions.assert_command_failure(result, "Invalid command should fail")
        assert OutputValidator.validate_error_message(result['stderr'])
    
    def test_missing_arguments_handling(self, cli_runner):
        """Test commands requiring arguments fail appropriately."""
        commands_needing_args = [
            "add",  # Needs server name
            "remove",  # Needs server name
            "suite show",  # Needs suite name
            "install-package"  # Needs package ID
        ]
        
        for cmd in commands_needing_args:
            result = cli_runner.run_command(cmd, expect_success=False)
            TestAssertions.assert_command_failure(
                result, 
                f"Command '{cmd}' should fail without required arguments"
            )


class TestDiscoveryCommands:
    """Test server discovery functionality."""
    
    def test_basic_discover(self, cli_runner):
        """Test basic discover command works."""
        result = cli_runner.run_command("discover")
        
        TestAssertions.assert_command_success(result, "Basic discover")
        # Should show some discoverable servers or indicate none found
        assert result['stdout'].strip() != ""
    
    @pytest.mark.parametrize("query", ["filesystem", "sqlite", "test"])
    def test_discover_with_query(self, cli_runner, query):
        """Test discover with search queries."""
        result = cli_runner.run_command(f"discover --query {query}")
        
        TestAssertions.assert_command_success(result, f"Discover query: {query}")
        # Query results can be empty, that's valid
    
    @pytest.mark.parametrize("server_type", ["npm", "docker", "docker-desktop"])
    def test_discover_with_type_filter(self, cli_runner, server_type):
        """Test discover with type filtering."""
        result = cli_runner.run_command(f"discover --type {server_type}")
        
        TestAssertions.assert_command_success(result, f"Discover type: {server_type}")
    
    @pytest.mark.parametrize("limit", [1, 5, 10])
    def test_discover_with_limit(self, cli_runner, limit):
        """Test discover with result limits."""
        result = cli_runner.run_command(f"discover --limit {limit}")
        
        TestAssertions.assert_command_success(result, f"Discover limit: {limit}")
    
    def test_discover_update_catalog(self, cli_runner):
        """Test catalog update functionality."""
        result = cli_runner.run_command("discover --update-catalog")
        
        TestAssertions.assert_command_success(result, "Discover update catalog")
    
    def test_discover_combined_options(self, cli_runner):
        """Test discover with multiple options combined."""
        result = cli_runner.run_command("discover --query filesystem --type npm --limit 3")
        
        TestAssertions.assert_command_success(result, "Discover combined options")


class TestSystemInformation:
    """Test system information and status commands."""
    
    def test_system_info_command(self, cli_runner):
        """Test system-info command shows environment details."""
        result = cli_runner.run_command("system-info")
        
        TestAssertions.assert_command_success(result, "System info command")
        
        # Should show system information
        expected_info = ["Python", "Platform", "Dependencies"]
        # Note: Not all may be present, so we don't assert all
        output_lower = result['stdout'].lower()
        info_present = any(info.lower() in output_lower for info in expected_info)
        assert info_present, "System info should show some system details"
    
    def test_status_command(self, cli_runner):
        """Test status command shows current state."""
        result = cli_runner.run_command("status")
        
        TestAssertions.assert_command_success(result, "Status command")
        assert OutputValidator.validate_status_output(result['stdout'])
    
    def test_monitor_status_command(self, cli_runner):
        """Test monitor status quick check."""
        result = cli_runner.run_command("monitor-status")
        
        TestAssertions.assert_command_success(result, "Monitor status command")


@pytest.mark.smoke
class TestSmokeTests:
    """Smoke tests - critical functionality that must always work."""
    
    def test_application_starts(self, cli_runner):
        """Test the application starts and responds to basic commands."""
        # This is the most basic smoke test
        result = cli_runner.run_command("--help")
        TestAssertions.assert_command_success(result, "Application startup smoke test")
    
    def test_core_commands_available(self, cli_runner):
        """Test all core commands are available in help."""
        result = cli_runner.run_command("--help")
        TestAssertions.assert_command_success(result, "Core commands availability")
        
        core_commands = [
            "add", "remove", "list", "discover", "suite", "quality", 
            "install", "status", "system-info"
        ]
        
        TestAssertions.assert_contains_all(
            result['stdout'], 
            core_commands, 
            "All core commands available"
        )
    
    def test_error_handling_works(self, cli_runner):
        """Test basic error handling is functional."""
        result = cli_runner.run_command("nonexistent-command", expect_success=False)
        TestAssertions.assert_command_failure(result, "Error handling smoke test")
    
    def test_list_command_baseline(self, cli_runner):
        """Test list command as a baseline functionality test."""
        result = cli_runner.run_command("list")
        TestAssertions.assert_command_success(result, "List command baseline")
        # Empty list is OK for baseline test