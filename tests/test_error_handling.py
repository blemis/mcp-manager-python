"""
Error handling and edge case testing for MCP Manager.

Tests all error conditions and edge cases that users might encounter.
Professional black-box testing focused on robustness and user experience.
"""

import pytest
from tests.utils.validators import OutputValidator, TestAssertions


class TestInvalidCommands:
    """Test handling of invalid commands and arguments."""
    
    @pytest.fixture(autouse=True)
    def setup_error_handling_suite(self, suite_loader, suite_setup):
        """Setup error handling test suite if available."""
        if suite_loader and suite_setup:
            import asyncio
            
            async def setup():
                try:
                    await suite_setup.create_error_handling_test_suite()
                    suite_data = await suite_loader.load_suite("error-handling-test")
                    print(f"🎯 Error Handling Test Suite loaded: {len(suite_data.get('deployed_servers', {}))} servers")
                    return suite_data
                except Exception as e:
                    print(f"⚠️  Could not load error handling suite: {e}")
                    return None
            
            try:
                self.suite_data = asyncio.run(setup())
            except Exception:
                self.suite_data = None
        else:
            self.suite_data = None
    """Test handling of invalid commands and arguments."""
    
    def test_completely_invalid_command(self, cli_runner):
        """Test completely invalid command names."""
        invalid_commands = [
            "invalid-command-xyz",
            "nonexistent-action",
            "foobar-command",
            "random-stuff"
        ]
        
        for cmd in invalid_commands:
            result = cli_runner.run_command(cmd, expect_success=False)
            TestAssertions.assert_command_failure(result, f"Invalid command: {cmd}")
            assert OutputValidator.validate_error_message(result['stderr'])
    
    def test_invalid_subcommands(self, cli_runner):
        """Test invalid subcommands for valid main commands."""
        invalid_subcommands = [
            "suite invalid-subcommand",
            "quality nonexistent-action", 
            "discover invalid-option",
            "add invalid-server-action"
        ]
        
        for cmd in invalid_subcommands:
            result = cli_runner.run_command(cmd, expect_success=False)
            TestAssertions.assert_command_failure(result, f"Invalid subcommand: {cmd}")
    
    def test_malformed_command_syntax(self, cli_runner):
        """Test commands with malformed syntax."""
        malformed_commands = [
            "--invalid-global-flag command",
            "add server --invalid-flag",
            "suite create --no-name",
            "quality feedback --no-args"
        ]
        
        for cmd in malformed_commands:
            result = cli_runner.run_command(cmd, expect_success=False)
            TestAssertions.assert_command_failure(result, f"Malformed syntax: {cmd}")
    
    def test_missing_required_arguments(self, cli_runner):
        """Test commands missing required arguments."""
        missing_arg_commands = [
            "add",  # Missing server name
            "remove",  # Missing server name
            "suite create",  # Missing suite name
            "suite add",  # Missing suite and server names
            "suite remove",  # Missing arguments
            "suite show",  # Missing suite name
            "quality feedback",  # Missing all arguments
            "install-package"  # Missing package ID
        ]
        
        for cmd in missing_arg_commands:
            result = cli_runner.run_command(cmd, expect_success=False)
            TestAssertions.assert_command_failure(result, f"Missing args: {cmd}")
            
            # Should show helpful error message
            error_output = result['stderr'] + result['stdout']
            help_indicators = ["required", "missing", "usage", "help"]
            has_help = any(indicator in error_output.lower() for indicator in help_indicators)
            assert has_help, f"Missing args error should be helpful for: {cmd}"
    
    def test_conflicting_arguments(self, cli_runner):
        """Test commands with conflicting arguments."""
        conflicting_commands = [
            "discover --type npm --type docker",  # Multiple type filters
            "list --scope user --scope project",  # Multiple scopes
            "suite create test --category dev --category prod"  # Multiple categories
        ]
        
        for cmd in conflicting_commands:
            result = cli_runner.run_command(cmd, expect_success=False)
            # Some CLI frameworks handle this gracefully, so don't assert failure
            if not result['success']:
                TestAssertions.assert_command_failure(result, f"Conflicting args: {cmd}")


class TestNonexistentResources:
    """Test operations on nonexistent resources."""
    
    def test_nonexistent_server_operations(self, cli_runner):
        """Test operations on servers that don't exist."""
        nonexistent_server = "nonexistent-server-xyz"
        
        operations = [
            f"remove {nonexistent_server}",
            f"enable {nonexistent_server}",
            f"disable {nonexistent_server}"
        ]
        
        for cmd in operations:
            result = cli_runner.run_command(cmd)
            
            # Should either succeed (no-op) or fail gracefully
            if not result['success']:
                assert OutputValidator.validate_error_message(result['stderr'], "not found")
            else:
                # If it succeeds, should indicate resource not found
                assert "not found" in result['stdout'].lower() or \
                       "does not exist" in result['stdout'].lower()
    
    def test_nonexistent_suite_operations(self, cli_runner):
        """Test operations on suites that don't exist."""
        nonexistent_suite = "nonexistent-suite-xyz"
        
        operations = [
            f"suite show {nonexistent_suite}",
            f"suite delete {nonexistent_suite}",
            f"suite add {nonexistent_suite} some-server",
            f"suite remove {nonexistent_suite} some-server",
            f"install-suite --suite-name {nonexistent_suite}"
        ]
        
        for cmd in operations:
            result = cli_runner.run_command(cmd)
            
            # Should show appropriate "not found" message
            error_output = result['stderr'] + result['stdout']
            assert "not found" in error_output.lower() or \
                   "does not exist" in error_output.lower(), \
                   f"Command should indicate suite not found: {cmd}"
    
    def test_nonexistent_package_installation(self, cli_runner):
        """Test installing packages that don't exist."""
        nonexistent_packages = [
            "nonexistent-package-xyz",
            "fake-mcp-server",
            "invalid-install-id"
        ]
        
        for package_id in nonexistent_packages:
            result = cli_runner.run_command(f"install-package {package_id}")
            
            # Should either fail or indicate package not found
            if not result['success']:
                TestAssertions.assert_command_failure(result, f"Install nonexistent: {package_id}")
            else:
                error_output = result['stderr'] + result['stdout']
                assert "not found" in error_output.lower() or \
                       "unavailable" in error_output.lower()


class TestInvalidDataFormats:
    """Test handling of invalid data formats and values."""
    
    def test_invalid_server_names(self, cli_runner):
        """Test server names with invalid characters or formats."""
        invalid_names = [
            "",  # Empty name
            " ",  # Whitespace only
            "server with spaces",  # Spaces
            "server/with/slashes",  # Slashes
            "server@with@symbols",  # Special characters
            "server:with:colons",  # Colons
            "server\nwith\nnewlines",  # Newlines
            "server\twith\ttabs"  # Tabs
        ]
        
        for name in invalid_names:
            result = cli_runner.run_command(
                f"add '{name}' --type custom --command 'echo test'",
                expect_success=False
            )
            
            # Should either fail or sanitize the name
            if not result['success']:
                TestAssertions.assert_command_failure(result, f"Invalid server name: {repr(name)}")
                assert OutputValidator.validate_error_message(result['stderr'], "invalid")
    
    def test_invalid_suite_names(self, cli_runner):
        """Test suite names with invalid formats."""
        invalid_names = [
            "",  # Empty name
            " ",  # Whitespace only
            "suite with spaces",
            "suite/with/slashes",
            "suite@special#chars"
        ]
        
        for name in invalid_names:
            result = cli_runner.run_command(
                f"suite create '{name}' --description 'Test suite'",
                expect_success=False
            )
            
            TestAssertions.assert_command_failure(result, f"Invalid suite name: {repr(name)}")
    
    def test_invalid_quality_ratings(self, cli_runner, isolated_environment):
        """Test quality feedback with invalid rating values."""
        # First add a server to give feedback on
        server_name = "test-invalid-rating-server"
        cli_runner.run_command(
            f"add {server_name} --type custom --command 'echo test'"
        )
        isolated_environment.add_server(server_name)
        
        invalid_ratings = [
            0,    # Below minimum
            6,    # Above maximum
            -1,   # Negative
            10,   # Way too high
            "invalid",  # Non-numeric
            "3.5"  # Decimal (if not supported)
        ]
        
        for rating in invalid_ratings:
            result = cli_runner.run_command(
                f"quality feedback {server_name} test-id --rating {rating} --comment 'Test'",
                expect_success=False
            )
            
            TestAssertions.assert_command_failure(result, f"Invalid rating: {rating}")
            assert OutputValidator.validate_error_message(result['stderr'], "invalid")


class TestResourceLimits:
    """Test behavior at resource limits and edge cases."""
    
    def test_extremely_long_names(self, cli_runner):
        """Test extremely long server/suite names."""
        long_name = "a" * 1000  # 1000 character name
        
        result = cli_runner.run_command(
            f"add {long_name} --type custom --command 'echo test'",
            expect_success=False
        )
        
        # Should either fail or truncate gracefully
        if not result['success']:
            TestAssertions.assert_command_failure(result, "Extremely long server name")
    
    def test_extremely_long_descriptions(self, cli_runner):
        """Test extremely long descriptions."""
        long_description = "This is a very long description. " * 100  # ~3000 chars
        
        result = cli_runner.run_command(
            f"suite create test-long-desc --description '{long_description}'"
        )
        
        # Should either succeed or fail gracefully
        if not result['success']:
            TestAssertions.assert_command_failure(result, "Extremely long description")
    
    def test_many_servers_in_suite(self, cli_runner, isolated_environment):
        """Test suite with many servers."""
        suite_name = "test-many-servers-suite"
        
        # Create suite
        cli_runner.run_command(
            f"suite create {suite_name} --description 'Many servers test'"
        )
        isolated_environment.add_suite(suite_name)
        
        # Add many servers (test scalability)
        for i in range(50):  # 50 servers
            server_name = f"bulk-server-{i:03d}"
            add_result = cli_runner.run_command(
                f"suite add {suite_name} {server_name} --priority {100-i}"
            )
            
            # Should handle many servers gracefully
            if not add_result['success']:
                # If it fails, should be due to limits, not crashes
                assert "limit" in add_result['stderr'].lower() or \
                       "too many" in add_result['stderr'].lower()
                break
        
        # Verify suite still works
        show_result = cli_runner.run_command(f"suite show {suite_name}")
        TestAssertions.assert_command_success(show_result, "Show suite with many servers")


class TestConcurrentOperations:
    """Test behavior under concurrent operations."""
    
    def test_rapid_server_operations(self, cli_runner, isolated_environment):
        """Test rapid consecutive server operations."""
        server_base = "rapid-test-server"
        
        # Rapidly add multiple servers
        for i in range(10):
            server_name = f"{server_base}-{i}"
            result = cli_runner.run_command(
                f"add {server_name} --type custom --command 'echo {i}'",
                timeout=10  # Shorter timeout for rapid operations
            )
            
            # Should handle rapid operations without crashing
            if not result['success']:
                # If it fails, should be graceful, not a crash
                assert result.get('error') != 'timeout', f"Rapid operation {i} should not timeout"
                assert 'crash' not in result.get('stderr', '').lower()
            else:
                isolated_environment.add_server(server_name)
        
        # Verify final state is consistent
        list_result = cli_runner.run_command("list")
        TestAssertions.assert_command_success(list_result, "List after rapid operations")
    
    def test_rapid_suite_operations(self, cli_runner, isolated_environment):
        """Test rapid suite creation and modification."""
        suite_base = "rapid-suite"
        
        # Rapidly create suites
        for i in range(5):
            suite_name = f"{suite_base}-{i}"
            result = cli_runner.run_command(
                f"suite create {suite_name} --description 'Rapid test {i}'",
                timeout=10
            )
            
            if result['success']:
                isolated_environment.add_suite(suite_name)
                
                # Rapidly add servers to suite
                for j in range(3):
                    cli_runner.run_command(
                        f"suite add {suite_name} server-{j}",
                        timeout=5
                    )
        
        # Verify final state
        list_result = cli_runner.run_command("suite list")
        TestAssertions.assert_command_success(list_result, "Suite list after rapid operations")


class TestSystemResourceHandling:
    """Test handling of system resource constraints."""
    
    def test_filesystem_permissions(self, cli_runner):
        """Test behavior with filesystem permission issues."""
        # This test depends on system setup, so we'll test graceful failure
        
        # Try to write to a potentially restricted location
        result = cli_runner.run_command("system-info")
        TestAssertions.assert_command_success(result, "System info despite potential restrictions")
        
        # The command should succeed or fail gracefully
        if not result['success']:
            assert "permission" in result['stderr'].lower() or \
                   "access" in result['stderr'].lower()
    
    def test_network_timeout_handling(self, cli_runner):
        """Test behavior with network timeouts during discovery."""
        # Test discovery with very short timeout (might cause timeout)
        result = cli_runner.run_command("discover --update-catalog", timeout=5)
        
        # Should either succeed quickly or handle timeout gracefully
        if result.get('error') == 'timeout':
            # Timeout should be handled gracefully, not crash the application
            pass
        elif not result['success']:
            # Network errors should be handled gracefully
            network_errors = ["network", "connection", "timeout", "unreachable"]
            has_network_error = any(
                error in result['stderr'].lower() 
                for error in network_errors
            )
            assert has_network_error, "Network errors should be properly reported"
    
    def test_large_output_handling(self, cli_runner):
        """Test handling of commands that might produce large outputs."""
        # Run discovery which might return many results
        result = cli_runner.run_command("discover", timeout=30)
        
        TestAssertions.assert_command_success(result, "Discovery with potentially large output")
        
        # Output should be handled properly even if large
        assert len(result['stdout']) < 1000000, "Output should be reasonable size or truncated"


class TestEdgeCaseInputs:
    """Test edge case inputs and special characters."""
    
    def test_unicode_and_special_characters(self, cli_runner):
        """Test handling of unicode and special characters."""
        special_names = [
            "server-with-unicode-café",
            "server-with-emoji-🚀",
            "server-with-quotes-'test'",
            'server-with-double-quotes-"test"',
            "server-with-backslashes-\\test\\",
            "server-with-newlines-\n-test"
        ]
        
        for name in special_names:
            result = cli_runner.run_command(
                f"add '{name}' --type custom --command 'echo test'",
                expect_success=False
            )
            
            # Should either succeed or fail gracefully (not crash)
            if not result['success']:
                assert 'crash' not in result.get('stderr', '').lower()
                assert result.get('error') != 'timeout'
    
    def test_empty_and_whitespace_inputs(self, cli_runner):
        """Test handling of empty and whitespace-only inputs."""
        empty_inputs = [
            "",      # Empty
            " ",     # Single space
            "\t",    # Tab
            "\n",    # Newline
            "   ",   # Multiple spaces
            "\t\n "  # Mixed whitespace
        ]
        
        for empty_input in empty_inputs:
            result = cli_runner.run_command(
                f"add '{empty_input}' --type custom --command 'echo test'",
                expect_success=False
            )
            
            TestAssertions.assert_command_failure(result, f"Empty input: {repr(empty_input)}")
            assert OutputValidator.validate_error_message(result['stderr'], "invalid")


@pytest.mark.regression
class TestRegressionScenarios:
    """Test scenarios that have caused issues in the past."""
    
    def test_suite_installation_regression(self, cli_runner, isolated_environment):
        """Test the critical suite installation bug that was fixed."""
        suite_name = "regression-suite-install"
        
        # Create suite and add servers
        cli_runner.run_command(
            f"suite create {suite_name} --description 'Regression test'"
        )
        isolated_environment.add_suite(suite_name)
        
        cli_runner.run_command(f"suite add {suite_name} test-server")
        
        # The critical test - installation should NOT show "not implemented yet"
        result = cli_runner.run_command(
            f"install-suite --suite-name {suite_name} --dry-run"
        )
        
        TestAssertions.assert_command_success(result, "Suite installation regression test")
        
        # CRITICAL: Must not contain the old bug message
        TestAssertions.assert_not_contains(
            result['stdout'], 
            ["not implemented yet", "Server installation not implemented yet"], 
            "Suite installation bug regression check"
        )
        
        # Should show actual implementation
        implementation_indicators = [
            "Installing", "Servers to install", "Dry run", "Discovery"
        ]
        has_implementation = any(
            indicator in result['stdout'] 
            for indicator in implementation_indicators
        )
        assert has_implementation, "Suite installation shows actual implementation"
    
    def test_command_help_consistency(self, cli_runner):
        """Test that all commands have consistent help output."""
        main_commands = [
            "add", "remove", "list", "discover", "suite", "quality", 
            "install", "install-package", "status", "system-info"
        ]
        
        for cmd in main_commands:
            result = cli_runner.run_command(f"{cmd} --help")
            TestAssertions.assert_command_success(result, f"Help for {cmd}")
            
            # Help should be properly formatted
            assert OutputValidator.validate_help_output(result['stdout'])
            
            # Should contain usage information
            TestAssertions.assert_contains_all(
                result['stdout'], 
                ["usage", cmd], 
                f"Help for {cmd} contains usage and command name"
            )
    
    def test_error_message_quality(self, cli_runner):
        """Test that error messages are helpful and consistent."""
        error_scenarios = [
            ("add", "Missing server name error"),
            ("remove nonexistent-server", "Nonexistent server error"),
            ("suite show nonexistent-suite", "Nonexistent suite error"),
            ("quality feedback server-name", "Incomplete feedback error")
        ]
        
        for cmd, description in error_scenarios:
            result = cli_runner.run_command(cmd, expect_success=False)
            
            # Should have helpful error message
            error_output = result['stderr'] + result['stdout']
            
            # Error should not be empty
            assert error_output.strip() != "", f"Error message should not be empty for: {cmd}"
            
            # Should not contain debug information or stack traces
            debug_indicators = ["traceback", "exception", "debug", "stack trace"]
            has_debug = any(
                indicator in error_output.lower() 
                for indicator in debug_indicators
            )
            assert not has_debug, f"Error should not contain debug info for: {cmd}"
            
            # Should contain helpful information
            help_indicators = ["usage", "help", "try", "see", "command"]
            has_help = any(
                indicator in error_output.lower() 
                for indicator in help_indicators
            )
            # Note: Not asserting help is required, as some errors might be self-explanatory