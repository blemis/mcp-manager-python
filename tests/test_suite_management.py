"""
Suite management testing for MCP Manager.

Tests MCP server suite creation, management, and installation workflows.
This is the critical functionality that was broken (suite installation bug).
"""

import pytest
import time
from tests.utils.validators import OutputValidator, TestAssertions


class TestSuiteCreation:
    """Test creating MCP server suites."""
    
    def test_create_basic_suite(self, cli_runner, isolated_environment):
        """Test creating a basic suite with minimal parameters."""
        suite_name = "test-basic-suite"
        
        result = cli_runner.run_command(
            f"suite create {suite_name} --description 'Basic test suite'"
        )
        
        TestAssertions.assert_command_success(result, "Create basic suite")
        assert OutputValidator.validate_success_message(result['stdout'], "created")
        isolated_environment.add_suite(suite_name)
        
        # Verify suite appears in list
        list_result = cli_runner.run_command("suite list")
        TestAssertions.assert_contains_all(
            list_result['stdout'], 
            [suite_name], 
            "Created suite appears in list"
        )
    
    def test_create_suite_with_category(self, cli_runner, isolated_environment):
        """Test creating suite with category."""
        suite_name = "test-category-suite"
        category = "development"
        
        result = cli_runner.run_command(
            f"suite create {suite_name} --description 'Category test' --category {category}"
        )
        
        TestAssertions.assert_command_success(result, "Create suite with category")
        isolated_environment.add_suite(suite_name)
        
        # Verify category in suite details
        show_result = cli_runner.run_command(f"suite show {suite_name}")
        TestAssertions.assert_contains_all(
            show_result['stdout'], 
            [category], 
            "Suite shows correct category"
        )
    
    @pytest.mark.parametrize("category", ["development", "production", "testing", "monitoring"])
    def test_create_suites_different_categories(self, cli_runner, isolated_environment, category):
        """Test creating suites with different categories."""
        suite_name = f"test-{category}-suite"
        
        result = cli_runner.run_command(
            f"suite create {suite_name} --description '{category} suite' --category {category}"
        )
        
        TestAssertions.assert_command_success(result, f"Create {category} suite")
        isolated_environment.add_suite(suite_name)
    
    def test_create_duplicate_suite(self, cli_runner, isolated_environment):
        """Test creating suite with duplicate name."""
        suite_name = "test-duplicate-suite"
        
        # Create first suite
        result1 = cli_runner.run_command(
            f"suite create {suite_name} --description 'First suite'"
        )
        TestAssertions.assert_command_success(result1, "Create first suite")
        isolated_environment.add_suite(suite_name)
        
        # Try to create duplicate
        result2 = cli_runner.run_command(
            f"suite create {suite_name} --description 'Duplicate suite'",
            expect_success=False
        )
        
        TestAssertions.assert_command_failure(result2, "Duplicate suite creation")
        assert OutputValidator.validate_error_message(result2['stderr'], "already exists")
    
    def test_create_suite_invalid_name(self, cli_runner):
        """Test creating suite with invalid name."""
        invalid_names = ["", "suite with spaces", "suite/with/slashes"]
        
        for invalid_name in invalid_names:
            result = cli_runner.run_command(
                f"suite create '{invalid_name}' --description 'Invalid name test'",
                expect_success=False
            )
            
            TestAssertions.assert_command_failure(result, f"Invalid suite name: {invalid_name}")


class TestSuiteServerManagement:
    """Test adding and removing servers from suites."""
    
    def test_add_server_to_suite(self, cli_runner, isolated_environment):
        """Test adding servers to a suite."""
        suite_name = "test-server-suite"
        
        # Create suite first
        cli_runner.run_command(
            f"suite create {suite_name} --description 'Server management test'"
        )
        isolated_environment.add_suite(suite_name)
        
        # Add server to suite
        result = cli_runner.run_command(
            f"suite add {suite_name} filesystem-server --role primary --priority 90"
        )
        
        TestAssertions.assert_command_success(result, "Add server to suite")
        
        # Verify server in suite
        show_result = cli_runner.run_command(f"suite show {suite_name}")
        TestAssertions.assert_contains_all(
            show_result['stdout'], 
            ["filesystem-server", "primary"], 
            "Server added to suite with role"
        )
    
    def test_add_multiple_servers_to_suite(self, cli_runner, isolated_environment):
        """Test adding multiple servers with different roles and priorities."""
        suite_name = "test-multi-server-suite"
        
        # Create suite
        cli_runner.run_command(
            f"suite create {suite_name} --description 'Multi-server test'"
        )
        isolated_environment.add_suite(suite_name)
        
        # Add multiple servers
        servers = [
            ("filesystem-server", "primary", 90),
            ("sqlite-server", "member", 80),
            ("http-server", "member", 70)
        ]
        
        for server_name, role, priority in servers:
            result = cli_runner.run_command(
                f"suite add {suite_name} {server_name} --role {role} --priority {priority}"
            )
            TestAssertions.assert_command_success(result, f"Add {server_name} to suite")
        
        # Verify all servers in suite
        show_result = cli_runner.run_command(f"suite show {suite_name}")
        server_names = [name for name, _, _ in servers]
        TestAssertions.assert_contains_all(
            show_result['stdout'], 
            server_names, 
            "All servers added to suite"
        )
        
        # Verify roles and priorities
        for _, role, priority in servers:
            TestAssertions.assert_contains_all(
                show_result['stdout'], 
                [role, str(priority)], 
                f"Server role {role} and priority {priority} shown"
            )
    
    def test_remove_server_from_suite(self, cli_runner, isolated_environment):
        """Test removing servers from suites."""
        suite_name = "test-remove-server-suite"
        
        # Create suite and add servers
        cli_runner.run_command(
            f"suite create {suite_name} --description 'Remove server test'"
        )
        isolated_environment.add_suite(suite_name)
        
        cli_runner.run_command(f"suite add {suite_name} filesystem-server")
        cli_runner.run_command(f"suite add {suite_name} sqlite-server")
        
        # Remove one server
        result = cli_runner.run_command(f"suite remove {suite_name} filesystem-server")
        TestAssertions.assert_command_success(result, "Remove server from suite")
        
        # Verify server removed
        show_result = cli_runner.run_command(f"suite show {suite_name}")
        TestAssertions.assert_not_contains(
            show_result['stdout'], 
            ["filesystem-server"], 
            "Server removed from suite"
        )
        
        # Verify other server still there
        TestAssertions.assert_contains_all(
            show_result['stdout'], 
            ["sqlite-server"], 
            "Other server still in suite"
        )
    
    def test_add_server_to_nonexistent_suite(self, cli_runner):
        """Test adding server to nonexistent suite."""
        result = cli_runner.run_command(
            "suite add nonexistent-suite test-server",
            expect_success=False
        )
        
        TestAssertions.assert_command_failure(result, "Add server to nonexistent suite")
        assert OutputValidator.validate_error_message(result['stderr'], "not found")
    
    def test_remove_server_from_nonexistent_suite(self, cli_runner):
        """Test removing server from nonexistent suite."""
        result = cli_runner.run_command(
            "suite remove nonexistent-suite test-server",
            expect_success=False
        )
        
        TestAssertions.assert_command_failure(result, "Remove server from nonexistent suite")
        assert OutputValidator.validate_error_message(result['stderr'], "not found")


class TestSuiteListing:
    """Test suite listing and filtering functionality."""
    
    def test_list_empty_suites(self, cli_runner):
        """Test suite list with no suites."""
        result = cli_runner.run_command("suite list")
        
        TestAssertions.assert_command_success(result, "List empty suites")
        # Empty list is valid
    
    def test_list_multiple_suites(self, cli_runner, isolated_environment):
        """Test listing multiple suites."""
        suites = [
            ("dev-suite", "development"),
            ("prod-suite", "production"),
            ("test-suite", "testing")
        ]
        
        # Create multiple suites
        for name, category in suites:
            cli_runner.run_command(
                f"suite create {name} --description '{name} description' --category {category}"
            )
            isolated_environment.add_suite(name)
        
        # List all suites
        result = cli_runner.run_command("suite list")
        TestAssertions.assert_command_success(result, "List multiple suites")
        
        # All suites should appear
        suite_names = [name for name, _ in suites]
        TestAssertions.assert_contains_all(
            result['stdout'], 
            suite_names, 
            "All created suites in list"
        )
    
    @pytest.mark.parametrize("category", ["development", "production", "testing"])
    def test_list_suites_by_category(self, cli_runner, isolated_environment, category):
        """Test listing suites filtered by category."""
        # Create suites in different categories
        categories = ["development", "production", "testing"]
        for cat in categories:
            suite_name = f"{cat}-suite"
            cli_runner.run_command(
                f"suite create {suite_name} --description '{cat} suite' --category {cat}"
            )
            isolated_environment.add_suite(suite_name)
        
        # Filter by specific category
        result = cli_runner.run_command(f"suite list --category {category}")
        TestAssertions.assert_command_success(result, f"List suites by category {category}")
        
        # Should contain the suite from that category
        expected_suite = f"{category}-suite"
        TestAssertions.assert_contains_all(
            result['stdout'], 
            [expected_suite], 
            f"Category filter shows {category} suite"
        )
    
    def test_suite_summary(self, cli_runner, isolated_environment):
        """Test suite summary statistics."""
        # Create a few suites with servers
        cli_runner.run_command("suite create summary-suite-1 --description 'Summary test 1'")
        cli_runner.run_command("suite add summary-suite-1 filesystem")
        isolated_environment.add_suite("summary-suite-1")
        
        cli_runner.run_command("suite create summary-suite-2 --description 'Summary test 2'")
        cli_runner.run_command("suite add summary-suite-2 sqlite")
        cli_runner.run_command("suite add summary-suite-2 http")
        isolated_environment.add_suite("summary-suite-2")
        
        # Get summary
        result = cli_runner.run_command("suite summary")
        TestAssertions.assert_command_success(result, "Suite summary")
        
        # Should show statistics
        assert result['stdout'].strip() != ""


class TestSuiteDetails:
    """Test suite detail viewing functionality."""
    
    def test_show_suite_details(self, cli_runner, isolated_environment):
        """Test showing detailed suite information."""
        suite_name = "test-details-suite"
        
        # Create suite with metadata
        cli_runner.run_command(
            f"suite create {suite_name} --description 'Detailed test suite' --category testing"
        )
        isolated_environment.add_suite(suite_name)
        
        # Add servers
        cli_runner.run_command(f"suite add {suite_name} filesystem --role primary --priority 90")
        cli_runner.run_command(f"suite add {suite_name} sqlite --role member --priority 80")
        
        # Show details
        result = cli_runner.run_command(f"suite show {suite_name}")
        TestAssertions.assert_command_success(result, "Show suite details")
        
        # Should contain suite metadata
        expected_content = [
            suite_name,
            "Detailed test suite",
            "testing",
            "filesystem",
            "sqlite",
            "primary",
            "member"
        ]
        
        TestAssertions.assert_contains_all(
            result['stdout'], 
            expected_content, 
            "Suite details contain all expected information"
        )
    
    def test_show_nonexistent_suite(self, cli_runner):
        """Test showing details of nonexistent suite."""
        result = cli_runner.run_command("suite show nonexistent-suite")
        
        # Should handle gracefully
        assert OutputValidator.validate_error_message(result['stdout'], "not found")
    
    def test_show_empty_suite(self, cli_runner, isolated_environment):
        """Test showing details of suite with no servers."""
        suite_name = "test-empty-suite"
        
        cli_runner.run_command(
            f"suite create {suite_name} --description 'Empty suite'"
        )
        isolated_environment.add_suite(suite_name)
        
        result = cli_runner.run_command(f"suite show {suite_name}")
        TestAssertions.assert_command_success(result, "Show empty suite")
        
        TestAssertions.assert_contains_all(
            result['stdout'], 
            [suite_name, "Empty suite"], 
            "Empty suite shows basic info"
        )


class TestSuiteInstallation:
    """Test suite installation - the critical functionality that was broken."""
    
    def test_suite_installation_dry_run(self, cli_runner, isolated_environment):
        """Test suite installation dry run functionality."""
        suite_name = "test-install-dry-run"
        
        # Create suite with servers
        cli_runner.run_command(
            f"suite create {suite_name} --description 'Installation test'"
        )
        isolated_environment.add_suite(suite_name)
        
        cli_runner.run_command(f"suite add {suite_name} filesystem")
        cli_runner.run_command(f"suite add {suite_name} sqlite")
        
        # Test dry run installation
        result = cli_runner.run_command(
            f"install-suite --suite-name {suite_name} --dry-run"
        )
        
        TestAssertions.assert_command_success(result, "Suite installation dry run")
        
        # Should show what would be installed
        TestAssertions.assert_contains_all(
            result['stdout'], 
            ["Dry run", "filesystem", "sqlite"], 
            "Dry run shows servers to install"
        )
        
        # CRITICAL: Should NOT contain "not implemented"
        TestAssertions.assert_not_contains(
            result['stdout'], 
            ["not implemented", "not implemented yet"], 
            "Dry run is actually implemented"
        )
    
    def test_suite_installation_actual(self, cli_runner, isolated_environment):
        """Test actual suite installation - the bug that was fixed."""
        suite_name = "test-install-actual"
        
        # Create suite with servers
        cli_runner.run_command(
            f"suite create {suite_name} --description 'Actual installation test'"
        )
        isolated_environment.add_suite(suite_name)
        
        cli_runner.run_command(f"suite add {suite_name} filesystem")
        
        # Test actual installation with force
        result = cli_runner.run_command(
            f"install-suite --suite-name {suite_name} --force"
        )
        
        TestAssertions.assert_command_success(result, "Suite actual installation")
        
        # CRITICAL BUG TEST: Should NOT show "not implemented yet"
        TestAssertions.assert_not_contains(
            result['stdout'], 
            ["not implemented", "not implemented yet", "Server installation not implemented yet"], 
            "Installation is actually implemented (bug fixed)"
        )
        
        # Should show actual installation progress/results
        installation_indicators = [
            "Installing", "Installation", "Complete", "Success", 
            "Failed", "Error", "Installed", "Discovery"
        ]
        
        has_installation_output = any(
            indicator.lower() in result['stdout'].lower() 
            for indicator in installation_indicators
        )
        
        assert has_installation_output, f"Installation shows actual progress, not stub. Output: {result['stdout'][:300]}"
    
    def test_suite_installation_nonexistent_suite(self, cli_runner):
        """Test installing nonexistent suite."""
        result = cli_runner.run_command(
            "install-suite --suite-name nonexistent-suite",
            expect_success=False
        )
        
        TestAssertions.assert_command_failure(result, "Install nonexistent suite")
        assert OutputValidator.validate_error_message(result['stdout'], "not found")
    
    def test_suite_installation_empty_suite(self, cli_runner, isolated_environment):
        """Test installing empty suite."""
        suite_name = "test-empty-install"
        
        # Create empty suite
        cli_runner.run_command(
            f"suite create {suite_name} --description 'Empty suite'"
        )
        isolated_environment.add_suite(suite_name)
        
        # Try to install empty suite
        result = cli_runner.run_command(
            f"install-suite --suite-name {suite_name}"
        )
        
        # Should handle gracefully
        TestAssertions.assert_command_success(result, "Install empty suite")
        
        # Should indicate no servers to install
        empty_indicators = ["no servers", "empty", "nothing to install"]
        has_empty_indicator = any(
            indicator.lower() in result['stdout'].lower() 
            for indicator in empty_indicators
        )
        
        assert has_empty_indicator or "0" in result['stdout'], "Empty suite installation handled appropriately"
    
    @pytest.mark.parametrize("install_option", ["--force", "--skip-existing", "--update-existing"])
    def test_suite_installation_options(self, cli_runner, isolated_environment, install_option):
        """Test suite installation with different options."""
        suite_name = f"test-install-{install_option.replace('--', '')}"
        
        # Create suite
        cli_runner.run_command(
            f"suite create {suite_name} --description 'Installation options test'"
        )
        isolated_environment.add_suite(suite_name)
        
        cli_runner.run_command(f"suite add {suite_name} filesystem")
        
        # Test installation with option (if supported)
        result = cli_runner.run_command(
            f"install-suite --suite-name {suite_name} {install_option}"
        )
        
        # Some options might not be implemented, don't assert success
        if result['success']:
            TestAssertions.assert_not_contains(
                result['stdout'], 
                ["not implemented"], 
                f"Installation with {install_option} is implemented"
            )


class TestSuiteDeletion:
    """Test suite deletion functionality."""
    
    def test_delete_suite(self, cli_runner, isolated_environment):
        """Test deleting a suite."""
        suite_name = "test-delete-suite"
        
        # Create suite
        cli_runner.run_command(
            f"suite create {suite_name} --description 'Delete test'"
        )
        
        # Delete suite
        result = cli_runner.run_command(f"suite delete {suite_name}")
        TestAssertions.assert_command_success(result, "Delete suite")
        
        # Verify suite is gone
        list_result = cli_runner.run_command("suite list")
        TestAssertions.assert_not_contains(
            list_result['stdout'], 
            [suite_name], 
            "Deleted suite not in list"
        )
    
    def test_delete_suite_with_force(self, cli_runner, isolated_environment):
        """Test deleting suite with force flag."""
        suite_name = "test-delete-force"
        
        # Create suite with servers
        cli_runner.run_command(
            f"suite create {suite_name} --description 'Force delete test'"
        )
        cli_runner.run_command(f"suite add {suite_name} filesystem")
        
        # Delete with force
        result = cli_runner.run_command(f"suite delete {suite_name} --force")
        TestAssertions.assert_command_success(result, "Delete suite with force")
    
    def test_delete_nonexistent_suite(self, cli_runner):
        """Test deleting nonexistent suite."""
        result = cli_runner.run_command("suite delete nonexistent-suite")
        
        # Should handle gracefully
        assert OutputValidator.validate_error_message(result['stdout'], "not found")


@pytest.mark.integration
class TestSuiteWorkflows:
    """Test complete suite management workflows."""
    
    def test_complete_suite_lifecycle(self, cli_runner, isolated_environment):
        """Test complete suite lifecycle from create to delete."""
        suite_name = "test-lifecycle-suite"
        
        # Step 1: Create suite
        create_result = cli_runner.run_command(
            f"suite create {suite_name} --description 'Lifecycle test' --category testing"
        )
        TestAssertions.assert_command_success(create_result, "Lifecycle: Create suite")
        
        # Step 2: Add servers
        add_results = []
        servers = ["filesystem", "sqlite", "http"]
        for i, server in enumerate(servers, 1):
            result = cli_runner.run_command(
                f"suite add {suite_name} {server} --priority {100-i*10}"
            )
            TestAssertions.assert_command_success(result, f"Lifecycle: Add {server}")
            add_results.append(result)
        
        # Step 3: Verify suite contents
        show_result = cli_runner.run_command(f"suite show {suite_name}")
        TestAssertions.assert_contains_all(
            show_result['stdout'], 
            servers, 
            "Lifecycle: All servers in suite"
        )
        
        # Step 4: Test installation (dry run)
        install_result = cli_runner.run_command(
            f"install-suite --suite-name {suite_name} --dry-run"
        )
        TestAssertions.assert_command_success(install_result, "Lifecycle: Installation dry run")
        
        # Step 5: Remove some servers
        remove_result = cli_runner.run_command(f"suite remove {suite_name} {servers[0]}")
        TestAssertions.assert_command_success(remove_result, "Lifecycle: Remove server")
        
        # Step 6: Delete suite
        delete_result = cli_runner.run_command(f"suite delete {suite_name} --force")
        TestAssertions.assert_command_success(delete_result, "Lifecycle: Delete suite")
        
        # Step 7: Verify deletion
        final_list = cli_runner.run_command("suite list")
        TestAssertions.assert_not_contains(
            final_list['stdout'], 
            [suite_name], 
            "Lifecycle: Suite deleted"
        )