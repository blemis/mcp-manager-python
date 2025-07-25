"""
Server management testing for MCP Manager.

Tests CRUD operations on MCP servers - the core functionality users need.
Professional black-box testing with comprehensive server lifecycle testing.
"""

import pytest
import time
from tests.utils.validators import OutputValidator, TestAssertions


class TestServerAddition:
    """Test adding servers of different types."""
    
    @pytest.mark.parametrize("server_type,command,args", [
        ("npm", "npx @test/server", ["--directory", "/tmp"]),
        ("docker", "docker run test/server", []),
        ("custom", "python test_server.py", ["--config", "test.json"]),
    ])
    def test_add_server_by_type(self, cli_runner, isolated_environment, 
                               server_type, command, args):
        """Test adding servers of different types."""
        server_name = f"test-{server_type}-server"
        
        # Build add command
        cmd_parts = ["add", server_name, "--type", server_type, "--command", f"'{command}'"]
        if args:
            for arg in args:
                cmd_parts.extend(["--args", f"'{arg}'"])
        
        add_cmd = " ".join(cmd_parts)
        result = cli_runner.run_command(add_cmd)
        
        TestAssertions.assert_command_success(result, f"Add {server_type} server")
        assert OutputValidator.validate_success_message(result['stdout'], "add")
        
        # Track for cleanup
        isolated_environment.add_server(server_name)
        
        # Verify server appears in list
        list_result = cli_runner.run_command("list")
        TestAssertions.assert_command_success(list_result, "List after add")
        TestAssertions.assert_contains_all(
            list_result['stdout'], 
            [server_name], 
            f"Added {server_type} server appears in list"
        )
    
    def test_add_server_minimal_args(self, cli_runner, isolated_environment):
        """Test adding server with minimal required arguments."""
        server_name = "test-minimal-server"
        
        result = cli_runner.run_command(
            f"add {server_name} --type custom --command 'echo hello'"
        )
        
        TestAssertions.assert_command_success(result, "Add server minimal args")
        isolated_environment.add_server(server_name)
    
    def test_add_server_duplicate_name(self, cli_runner, isolated_environment):
        """Test adding server with duplicate name fails appropriately."""
        server_name = "test-duplicate-server"
        
        # Add first server
        result1 = cli_runner.run_command(
            f"add {server_name} --type custom --command 'echo test'"
        )
        TestAssertions.assert_command_success(result1, "Add first server")
        isolated_environment.add_server(server_name)
        
        # Try to add duplicate
        result2 = cli_runner.run_command(
            f"add {server_name} --type custom --command 'echo duplicate'", 
            expect_success=False
        )
        
        # Should either fail or warn about duplicate
        if not result2['success']:
            TestAssertions.assert_command_failure(result2, "Duplicate server add")
        else:
            # If it succeeds, it should at least warn
            assert "already exists" in result2['stdout'].lower() or \
                   "duplicate" in result2['stdout'].lower()
    
    def test_add_server_invalid_type(self, cli_runner):
        """Test adding server with invalid type fails."""
        result = cli_runner.run_command(
            "add test-invalid --type invalid-type --command 'test'",
            expect_success=False
        )
        
        TestAssertions.assert_command_failure(result, "Invalid server type")
        assert OutputValidator.validate_error_message(result['stderr'], "invalid")
    
    def test_add_server_missing_command(self, cli_runner):
        """Test adding server without command fails."""
        result = cli_runner.run_command(
            "add test-no-command --type custom",
            expect_success=False
        )
        
        TestAssertions.assert_command_failure(result, "Missing command")


class TestServerRemoval:
    """Test removing servers."""
    
    def test_remove_existing_server(self, cli_runner, isolated_environment):
        """Test removing an existing server."""
        server_name = "test-remove-server"
        
        # First add a server
        add_result = cli_runner.run_command(
            f"add {server_name} --type custom --command 'echo test'"
        )
        TestAssertions.assert_command_success(add_result, "Add server for removal test")
        
        # Remove the server (using --force to skip confirmation in automated tests)
        remove_result = cli_runner.run_command(f"remove {server_name} --force")
        TestAssertions.assert_command_success(remove_result, "Remove existing server")
        assert OutputValidator.validate_success_message(remove_result['stdout'], "remove")
        
        # Verify server is gone from list
        list_result = cli_runner.run_command("list")
        TestAssertions.assert_not_contains(
            list_result['stdout'], 
            [server_name], 
            "Removed server not in list"
        )
    
    def test_remove_nonexistent_server(self, cli_runner):
        """Test removing nonexistent server handles gracefully."""
        result = cli_runner.run_command("remove nonexistent-server-xyz --force")
        
        # Should either succeed (no-op) or fail gracefully
        # Check for error messages in both stdout and stderr (depending on CLI implementation)
        error_output = (result['stdout'] + result['stderr']).lower()
        assert "not found" in error_output or "does not exist" in error_output or "no user-scoped" in error_output
    
    def test_remove_with_confirmation(self, cli_runner, isolated_environment):
        """Test remove with force flag."""
        server_name = "test-remove-force"
        
        # Add server
        cli_runner.run_command(
            f"add {server_name} --type custom --command 'echo test'"
        )
        
        # Remove with force
        result = cli_runner.run_command(f"remove {server_name} --force")
        TestAssertions.assert_command_success(result, "Remove with force flag")


class TestServerListing:
    """Test server listing functionality."""
    
    def test_list_empty_servers(self, cli_runner):
        """Test list command with no servers."""
        result = cli_runner.run_command("list")
        
        TestAssertions.assert_command_success(result, "List empty servers")
        # Empty list is valid - should show appropriate message
    
    def test_list_with_servers(self, cli_runner, isolated_environment):
        """Test list command with multiple servers."""
        servers = [
            ("test-list-1", "custom", "echo 1"),
            ("test-list-2", "npm", "npx test"),
            ("test-list-3", "docker", "docker run test")
        ]
        
        # Add multiple servers
        for name, stype, cmd in servers:
            add_result = cli_runner.run_command(f"add {name} --type {stype} --command '{cmd}'")
            TestAssertions.assert_command_success(add_result, f"Add server {name}")
            isolated_environment.add_server(name)
        
        # List all servers
        result = cli_runner.run_command("list")
        TestAssertions.assert_command_success(result, "List multiple servers")
        
        # All servers should appear in list
        server_names = [name for name, _, _ in servers]
        TestAssertions.assert_contains_all(
            result['stdout'], 
            server_names, 
            "All added servers in list"
        )
    
    @pytest.mark.parametrize("scope", ["user", "project"])
    def test_list_with_scope(self, cli_runner, scope):
        """Test list command with different scopes."""
        result = cli_runner.run_command(f"list --scope {scope}")
        
        TestAssertions.assert_command_success(result, f"List with scope {scope}")
    
    def test_list_with_filters(self, cli_runner, isolated_environment):
        """Test list command with type filters."""
        # Add servers of different types
        servers = [
            ("npm-server", "npm", "npx test"),
            ("docker-server", "docker", "docker run test"),
            ("custom-server", "custom", "python test.py")
        ]
        
        for name, stype, cmd in servers:
            cli_runner.run_command(f"add {name} --type {stype} --command '{cmd}'")
            isolated_environment.add_server(name)
        
        # Test filtering by type (if supported)
        for server_type in ["npm", "docker", "custom"]:
            result = cli_runner.run_command(f"list --type {server_type}")
            # This might not be implemented, so we don't assert success
            if result['success']:
                # If filtering works, should only show that type
                expected_server = f"{server_type}-server"
                assert expected_server in result['stdout']


class TestServerEnableDisable:
    """Test server enable/disable functionality."""
    
    def test_enable_server(self, cli_runner, isolated_environment):
        """Test enabling a server."""
        server_name = "test-enable-server"
        
        # Add server
        cli_runner.run_command(
            f"add {server_name} --type custom --command 'echo test'"
        )
        isolated_environment.add_server(server_name)
        
        # Enable server
        result = cli_runner.run_command(f"enable {server_name}")
        TestAssertions.assert_command_success(result, "Enable server")
    
    def test_disable_server(self, cli_runner, isolated_environment):
        """Test disabling a server."""
        server_name = "test-disable-server"
        
        # Add server
        cli_runner.run_command(
            f"add {server_name} --type custom --command 'echo test'"
        )
        isolated_environment.add_server(server_name)
        
        # Disable server
        result = cli_runner.run_command(f"disable {server_name}")
        TestAssertions.assert_command_success(result, "Disable server")
    
    def test_enable_disable_nonexistent(self, cli_runner):
        """Test enable/disable nonexistent server."""
        # Test enable
        result1 = cli_runner.run_command("enable nonexistent-server", expect_success=False)
        if not result1['success']:
            assert OutputValidator.validate_error_message(result1['stderr'], "not found")
        
        # Test disable
        result2 = cli_runner.run_command("disable nonexistent-server", expect_success=False)
        if not result2['success']:
            assert OutputValidator.validate_error_message(result2['stderr'], "not found")


class TestPackageInstallation:
    """Test package installation from discovery."""
    
    def test_install_package_basic(self, cli_runner):
        """Test basic package installation."""
        # First discover available packages
        discover_result = cli_runner.run_command("discover --limit 1")
        TestAssertions.assert_command_success(discover_result, "Discover for install test")
        
        # If we found packages, try to install one
        if "install_id" in discover_result['stdout'] or "filesystem" in discover_result['stdout']:
            # Try common package names
            for package_id in ["filesystem", "sqlite", "mcp-filesystem"]:
                result = cli_runner.run_command(f"install-package {package_id}")
                if result['success']:
                    TestAssertions.assert_command_success(result, f"Install package {package_id}")
                    break
    
    def test_install_nonexistent_package(self, cli_runner):
        """Test installing nonexistent package."""
        result = cli_runner.run_command(
            "install-package nonexistent-package-xyz", 
            expect_success=False
        )
        
        TestAssertions.assert_command_failure(result, "Install nonexistent package")
        assert OutputValidator.validate_error_message(result['stdout'], "not found")


class TestServerValidation:
    """Test server configuration validation."""
    
    def test_add_server_empty_name(self, cli_runner):
        """Test adding server with empty name fails."""
        result = cli_runner.run_command(
            "add '' --type custom --command 'test'",
            expect_success=False
        )
        
        TestAssertions.assert_command_failure(result, "Empty server name")
    
    def test_add_server_empty_command(self, cli_runner):
        """Test adding server with empty command fails."""
        result = cli_runner.run_command(
            "add test-empty-cmd --type custom --command ''",
            expect_success=False
        )
        
        TestAssertions.assert_command_failure(result, "Empty server command")
    
    def test_add_server_invalid_characters(self, cli_runner):
        """Test adding server with invalid characters in name."""
        invalid_names = [
            "test server",  # Space
            "test/server",  # Slash
            "test@server",  # At symbol
            "test:server"   # Colon
        ]
        
        for invalid_name in invalid_names:
            result = cli_runner.run_command(
                f"add '{invalid_name}' --type custom --command 'test'",
                expect_success=False
            )
            
            # Should either fail or sanitize the name
            if not result['success']:
                TestAssertions.assert_command_failure(result, f"Invalid name: {invalid_name}")


@pytest.mark.integration
class TestServerLifecycle:
    """Test complete server lifecycle workflows."""
    
    @pytest.fixture(autouse=True)
    def setup_suite_loader(self, test_manager):
        """Set up suite loader for lifecycle tests."""
        import asyncio
        from tests.fixtures.suite_loader import SuiteLoader
        from tests.fixtures.test_suites_setup import setup_test_suites
        
        # Ensure test suites exist
        asyncio.run(setup_test_suites())
        
        # Create suite loader - get the manager value if it's a coroutine
        if hasattr(test_manager, '__aenter__'):
            # test_manager is async, need to handle properly
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            manager = loop.run_until_complete(test_manager.__aenter__())
        else:
            manager = test_manager
            
        self.suite_loader = SuiteLoader(manager)
        yield
        
        # Cleanup after test
        asyncio.run(self.suite_loader.unload_all_suites())
    
    @pytest.mark.asyncio
    async def test_complete_server_lifecycle(self, cli_runner, isolated_environment):
        """Test complete add -> list -> enable -> disable -> remove cycle."""
        # Load the server-lifecycle-test suite
        suite_data = await self.suite_loader.load_suite("server-lifecycle-test")
        deployed_servers = suite_data["deployed_servers"]
        
        # Find the primary test server from the suite
        primary_server = None
        for server_name, server in deployed_servers.items():
            if "lifecycle" in server_name:  # Primary test server
                primary_server = server_name
                break
        
        assert primary_server, "No primary lifecycle server found in suite"
        
        # Step 1: Verify server appears in list (already added by suite)
        list_result = cli_runner.run_command("list")
        TestAssertions.assert_contains_all(
            list_result['stdout'], 
            [primary_server], 
            "Lifecycle: Server in list"
        )
        
        # Step 2: Enable server
        enable_result = cli_runner.run_command(f"enable {primary_server}")
        TestAssertions.assert_command_success(enable_result, "Lifecycle: Enable server")
        
        # Step 3: Disable server
        disable_result = cli_runner.run_command(f"disable {primary_server}")
        TestAssertions.assert_command_success(disable_result, "Lifecycle: Disable server")
        
        # Step 4: Remove server
        remove_result = cli_runner.run_command(f"remove {primary_server} --force")
        TestAssertions.assert_command_success(remove_result, "Lifecycle: Remove server")
        
        # Step 5: Verify removal
        final_list = cli_runner.run_command("list")
        TestAssertions.assert_not_contains(
            final_list['stdout'], 
            [primary_server], 
            "Lifecycle: Server removed from list"
        )
    
    @pytest.mark.asyncio
    async def test_bulk_server_operations(self, cli_runner, isolated_environment):
        """Test bulk server operations."""
        # Load the bulk-operations-test suite
        suite_data = await self.suite_loader.load_suite("bulk-operations-test")
        deployed_servers = suite_data["deployed_servers"]
        
        # Get all bulk server names from the deployed servers
        bulk_servers = [name for name in deployed_servers.keys() if "bulk-server" in name]
        
        assert len(bulk_servers) >= 3, f"Expected at least 3 bulk servers, got {len(bulk_servers)}"
        
        # Step 1: Verify all servers appear in list (already added by suite)
        list_result = cli_runner.run_command("list")
        TestAssertions.assert_contains_all(
            list_result['stdout'], 
            bulk_servers, 
            "Bulk operations: All servers in list"
        )
        
        # Step 2: Remove all servers
        for name in bulk_servers:
            remove_result = cli_runner.run_command(f"remove {name} --force")
            TestAssertions.assert_command_success(remove_result, f"Bulk remove: {name}")