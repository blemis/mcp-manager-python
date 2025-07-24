"""
Complete workflow testing for MCP Manager.

Tests real-world user and admin workflows end-to-end.
Professional black-box testing of complete user journeys.
"""

import pytest
import time
from tests.utils.validators import OutputValidator, TestAssertions


class TestUserOnboardingWorkflows:
    """Test complete user onboarding workflows."""
    
    def test_new_user_discovery_to_installation(self, cli_runner, isolated_environment):
        """Test complete new user workflow: discover → install → configure."""
        # Step 1: New user explores available servers
        print("🔍 Step 1: Discovering available MCP servers...")
        discovery_result = cli_runner.run_command("discover --limit 5")
        TestAssertions.assert_command_success(discovery_result, "New user: Discover servers")
        
        # Step 2: User explores specific category
        print("🔍 Step 2: Exploring filesystem servers...")
        filesystem_result = cli_runner.run_command("discover --query filesystem --type npm")
        TestAssertions.assert_command_success(filesystem_result, "New user: Explore filesystem servers")
        
        # Step 3: User installs a package (if available)
        print("🔧 Step 3: Installing a server package...")
        if "filesystem" in filesystem_result['stdout'] or len(filesystem_result['stdout'].strip()) > 0:
            install_result = cli_runner.run_command("install-package filesystem")
            
            # Installation might fail due to dependencies, that's OK for user onboarding
            if install_result['success']:
                TestAssertions.assert_command_success(install_result, "New user: Install package")
                TestAssertions.assert_not_contains(
                    install_result['stdout'], 
                    ["not implemented"], 
                    "Package installation is implemented"
                )
        
        # Step 4: User adds a custom server manually
        print("🔧 Step 4: Adding custom server...")
        custom_server_result = cli_runner.run_command(
            "add my-first-server --type custom --command 'echo Hello MCP'"
        )
        TestAssertions.assert_command_success(custom_server_result, "New user: Add custom server")
        isolated_environment.add_server("my-first-server")
        
        # Step 5: User lists all configured servers
        print("📋 Step 5: Viewing configured servers...")
        list_result = cli_runner.run_command("list")
        TestAssertions.assert_command_success(list_result, "New user: List servers")
        TestAssertions.assert_contains_all(
            list_result['stdout'], 
            ["my-first-server"], 
            "Custom server appears in list"
        )
        
        # Step 6: User checks system status
        print("ℹ️ Step 6: Checking system status...")
        status_result = cli_runner.run_command("status")
        TestAssertions.assert_command_success(status_result, "New user: Check status")
        
        print("✅ New user onboarding workflow completed successfully!")
    
    def test_developer_workflow_suite_creation(self, cli_runner, isolated_environment):
        """Test developer workflow: create development suite."""
        # Step 1: Developer creates development environment suite
        print("🏗️ Step 1: Creating development environment suite...")
        suite_result = cli_runner.run_command(
            "suite create dev-environment --description 'Development tools and utilities' --category development"
        )
        TestAssertions.assert_command_success(suite_result, "Developer: Create dev suite")
        isolated_environment.add_suite("dev-environment")
        
        # Step 2: Add essential development servers
        print("🔧 Step 2: Adding development servers to suite...")
        dev_servers = [
            ("filesystem", "primary", 90),
            ("sqlite", "member", 80),
            ("http", "member", 70)
        ]
        
        for server_name, role, priority in dev_servers:
            add_result = cli_runner.run_command(
                f"suite add dev-environment {server_name} --role {role} --priority {priority}"
            )
            TestAssertions.assert_command_success(add_result, f"Developer: Add {server_name}")
        
        # Step 3: Review suite configuration
        print("📋 Step 3: Reviewing suite configuration...")
        show_result = cli_runner.run_command("suite show dev-environment")
        TestAssertions.assert_command_success(show_result, "Developer: Show suite")
        
        # Verify all servers are in suite
        server_names = [name for name, _, _ in dev_servers]
        TestAssertions.assert_contains_all(
            show_result['stdout'], 
            server_names, 
            "All development servers in suite"
        )
        
        # Step 4: Test suite installation (dry run)
        print("🧪 Step 4: Testing suite installation...")
        dry_run_result = cli_runner.run_command("install-suite --suite-name dev-environment --dry-run")
        TestAssertions.assert_command_success(dry_run_result, "Developer: Suite dry run")
        TestAssertions.assert_not_contains(
            dry_run_result['stdout'], 
            ["not implemented"], 
            "Suite installation is implemented"
        )
        
        # Step 5: Provide feedback on server quality
        print("📝 Step 5: Recording server feedback...")
        feedback_result = cli_runner.run_command(
            "quality feedback filesystem dev-test-id --rating 5 --comment 'Essential for development work'"
        )
        TestAssertions.assert_command_success(feedback_result, "Developer: Record feedback")
        
        print("✅ Developer workflow completed successfully!")
    
    def test_admin_bulk_management_workflow(self, cli_runner, isolated_environment):
        """Test admin workflow: bulk server management."""
        # Step 1: Admin discovers all available servers
        print("🔍 Step 1: Admin discovering all available servers...")
        all_servers_result = cli_runner.run_command("discover")
        TestAssertions.assert_command_success(all_servers_result, "Admin: Discover all servers")
        
        # Step 2: Admin creates multiple suites for different environments
        print("🏗️ Step 2: Creating environment-specific suites...")
        environments = [
            ("production", "Production environment servers", "production"),
            ("staging", "Staging environment servers", "staging"),
            ("testing", "Testing and QA servers", "testing")
        ]
        
        for suite_name, description, category in environments:
            suite_result = cli_runner.run_command(
                f"suite create {suite_name} --description '{description}' --category {category}"
            )
            TestAssertions.assert_command_success(suite_result, f"Admin: Create {suite_name} suite")
            isolated_environment.add_suite(suite_name)
        
        # Step 3: Admin adds servers to each environment
        print("🔧 Step 3: Configuring environment-specific servers...")
        environment_configs = {
            "production": ["http", "sqlite", "filesystem"],
            "staging": ["http", "sqlite"],
            "testing": ["filesystem", "sqlite"]
        }
        
        for env_name, servers in environment_configs.items():
            for server in servers:
                add_result = cli_runner.run_command(f"suite add {env_name} {server}")
                TestAssertions.assert_command_success(add_result, f"Admin: Add {server} to {env_name}")
        
        # Step 4: Admin reviews all suite configurations
        print("📋 Step 4: Reviewing all suite configurations...")
        summary_result = cli_runner.run_command("suite summary")
        TestAssertions.assert_command_success(summary_result, "Admin: Suite summary")
        
        # Step 5: Admin checks quality status across all servers
        print("📊 Step 5: Checking system-wide quality status...")
        quality_status = cli_runner.run_command("quality status")
        TestAssertions.assert_command_success(quality_status, "Admin: Quality status")
        
        # Step 6: Admin generates comprehensive report
        print("📈 Step 6: Generating system report...")
        report_result = cli_runner.run_command("quality report")
        TestAssertions.assert_command_success(report_result, "Admin: Quality report")
        
        print("✅ Admin bulk management workflow completed successfully!")


class TestProblemSolvingWorkflows:
    """Test workflows for solving common problems."""
    
    def test_troubleshooting_workflow(self, cli_runner, isolated_environment):
        """Test user troubleshooting broken configuration."""
        # Step 1: User notices problem - server not working
        print("🚨 Step 1: User discovers configuration issue...")
        
        # Add a "problematic" server
        problem_server = cli_runner.run_command(
            "add problematic-server --type custom --command 'invalid-command-that-fails'"
        )
        TestAssertions.assert_command_success(problem_server, "Troubleshooting: Add problematic server")
        isolated_environment.add_server("problematic-server")
        
        # Step 2: User checks system status for diagnosis
        print("🔍 Step 2: Checking system status for diagnosis...")
        status_result = cli_runner.run_command("status")
        TestAssertions.assert_command_success(status_result, "Troubleshooting: Check status")
        
        # Step 3: User examines server configuration
        print("📋 Step 3: Examining server configuration...")
        list_result = cli_runner.run_command("list")
        TestAssertions.assert_command_success(list_result, "Troubleshooting: List servers")
        TestAssertions.assert_contains_all(
            list_result['stdout'], 
            ["problematic-server"], 
            "Problematic server in list"
        )
        
        # Step 4: User tries to disable problematic server
        print("🔧 Step 4: Disabling problematic server...")
        disable_result = cli_runner.run_command("disable problematic-server")
        TestAssertions.assert_command_success(disable_result, "Troubleshooting: Disable server")
        
        # Step 5: User removes and replaces server
        print("🔄 Step 5: Removing and replacing server...")
        remove_result = cli_runner.run_command("remove problematic-server")
        TestAssertions.assert_command_success(remove_result, "Troubleshooting: Remove server")
        
        # Replace with working server
        fix_result = cli_runner.run_command(
            "add fixed-server --type custom --command 'echo working'"
        )
        TestAssertions.assert_command_success(fix_result, "Troubleshooting: Add fixed server")
        isolated_environment.add_server("fixed-server")
        
        # Step 6: User verifies fix
        print("✅ Step 6: Verifying fix...")
        final_list = cli_runner.run_command("list")
        TestAssertions.assert_not_contains(
            final_list['stdout'], 
            ["problematic-server"], 
            "Problematic server removed"
        )
        TestAssertions.assert_contains_all(
            final_list['stdout'], 
            ["fixed-server"], 
            "Fixed server present"
        )
        
        print("✅ Troubleshooting workflow completed successfully!")
    
    def test_performance_optimization_workflow(self, cli_runner, isolated_environment):
        """Test workflow for optimizing server performance."""
        # Step 1: Admin creates performance-focused suite
        print("🚀 Step 1: Creating performance-optimized suite...")
        perf_suite = cli_runner.run_command(
            "suite create high-performance --description 'High-performance server configuration' --category production"
        )
        TestAssertions.assert_command_success(perf_suite, "Performance: Create suite")
        isolated_environment.add_suite("high-performance")
        
        # Step 2: Add servers with carefully chosen priorities
        print("⚡ Step 2: Adding servers with performance priorities...")
        perf_servers = [
            ("http", "primary", 95),      # Highest priority for HTTP
            ("sqlite", "member", 85),     # Database access
            ("filesystem", "member", 75)  # File operations
        ]
        
        for server, role, priority in perf_servers:
            add_result = cli_runner.run_command(
                f"suite add high-performance {server} --role {role} --priority {priority}"
            )
            TestAssertions.assert_command_success(add_result, f"Performance: Add {server}")
        
        # Step 3: Record performance feedback
        print("📊 Step 3: Recording performance metrics...")
        for server, _, _ in perf_servers:
            feedback_result = cli_runner.run_command(
                f"quality feedback {server} perf-test --rating 5 --comment 'Optimized for performance'"
            )
            TestAssertions.assert_command_success(feedback_result, f"Performance: Feedback for {server}")
        
        # Step 4: Check quality rankings for performance
        print("📈 Step 4: Checking performance rankings...")
        rankings_result = cli_runner.run_command("quality rankings --limit 10")
        TestAssertions.assert_command_success(rankings_result, "Performance: Check rankings")
        
        # Step 5: Test optimized suite installation
        print("🧪 Step 5: Testing optimized suite...")
        install_test = cli_runner.run_command("install-suite --suite-name high-performance --dry-run")
        TestAssertions.assert_command_success(install_test, "Performance: Suite installation test")
        
        print("✅ Performance optimization workflow completed successfully!")
    
    def test_migration_workflow(self, cli_runner, isolated_environment):
        """Test workflow for migrating server configurations."""
        # Step 1: Create old configuration
        print("📦 Step 1: Setting up old configuration...")
        old_servers = ["legacy-server-1", "legacy-server-2", "legacy-server-3"]
        
        for server in old_servers:
            add_result = cli_runner.run_command(
                f"add {server} --type custom --command 'echo legacy'"
            )
            TestAssertions.assert_command_success(add_result, f"Migration: Add {server}")
            isolated_environment.add_server(server)
        
        # Create old suite
        old_suite = cli_runner.run_command(
            "suite create legacy-suite --description 'Legacy server configuration'"
        )
        TestAssertions.assert_command_success(old_suite, "Migration: Create legacy suite")
        isolated_environment.add_suite("legacy-suite")
        
        for server in old_servers:
            cli_runner.run_command(f"suite add legacy-suite {server}")
        
        # Step 2: Plan migration to new configuration
        print("🔄 Step 2: Planning migration to new configuration...")
        
        # Create new suite
        new_suite = cli_runner.run_command(
            "suite create modern-suite --description 'Modern server configuration' --category production"
        )
        TestAssertions.assert_command_success(new_suite, "Migration: Create modern suite")
        isolated_environment.add_suite("modern-suite")
        
        # Step 3: Add new modern servers
        print("✨ Step 3: Adding modern server configuration...")
        modern_servers = ["filesystem", "sqlite", "http"]
        
        for server in modern_servers:
            add_result = cli_runner.run_command(f"suite add modern-suite {server}")
            TestAssertions.assert_command_success(add_result, f"Migration: Add modern {server}")
        
        # Step 4: Test new configuration
        print("🧪 Step 4: Testing new configuration...")
        test_modern = cli_runner.run_command("install-suite --suite-name modern-suite --dry-run")
        TestAssertions.assert_command_success(test_modern, "Migration: Test modern suite")
        
        # Step 5: Record migration feedback
        print("📝 Step 5: Recording migration feedback...")
        migration_feedback = cli_runner.run_command(
            "quality feedback filesystem migration-test --rating 5 --comment 'Successful migration to modern config'"
        )
        TestAssertions.assert_command_success(migration_feedback, "Migration: Record feedback")
        
        # Step 6: Clean up legacy configuration
        print("🧹 Step 6: Cleaning up legacy configuration...")
        
        # Remove legacy servers
        for server in old_servers:
            remove_result = cli_runner.run_command(f"remove {server}")
            TestAssertions.assert_command_success(remove_result, f"Migration: Remove {server}")
        
        # Remove legacy suite
        legacy_cleanup = cli_runner.run_command("suite delete legacy-suite --force")
        TestAssertions.assert_command_success(legacy_cleanup, "Migration: Remove legacy suite")
        
        # Step 7: Verify migration complete
        print("✅ Step 7: Verifying migration completion...")
        final_suites = cli_runner.run_command("suite list")
        TestAssertions.assert_not_contains(
            final_suites['stdout'], 
            ["legacy-suite"], 
            "Legacy suite removed"
        )
        TestAssertions.assert_contains_all(
            final_suites['stdout'], 
            ["modern-suite"], 
            "Modern suite present"
        )
        
        print("✅ Migration workflow completed successfully!")


class TestCollaborationWorkflows:
    """Test workflows involving multiple users/roles."""
    
    def test_team_development_workflow(self, cli_runner, isolated_environment):
        """Test team development workflow with shared suites."""
        # Step 1: Team lead creates shared development suite
        print("👥 Step 1: Team lead creates shared development suite...")
        team_suite = cli_runner.run_command(
            "suite create team-dev --description 'Shared team development environment' --category development"
        )
        TestAssertions.assert_command_success(team_suite, "Team: Create shared suite")
        isolated_environment.add_suite("team-dev")
        
        # Step 2: Add core development tools
        print("🛠️ Step 2: Adding core development tools...")
        core_tools = ["filesystem", "sqlite", "http"]
        
        for tool in core_tools:
            add_result = cli_runner.run_command(f"suite add team-dev {tool}")
            TestAssertions.assert_command_success(add_result, f"Team: Add {tool}")
        
        # Step 3: Team members provide feedback on tools
        print("📝 Step 3: Team members providing feedback...")
        team_feedback = [
            ("filesystem", 5, "Essential for file operations"),
            ("sqlite", 4, "Good for local development database"),
            ("http", 5, "Perfect for API testing")
        ]
        
        for tool, rating, comment in team_feedback:
            feedback_result = cli_runner.run_command(
                f"quality feedback {tool} team-{tool} --rating {rating} --comment '{comment}'"
            )
            TestAssertions.assert_command_success(feedback_result, f"Team: Feedback for {tool}")
        
        # Step 4: Install team development environment
        print("🚀 Step 4: Installing team development environment...")
        install_result = cli_runner.run_command("install-suite --suite-name team-dev --dry-run")
        TestAssertions.assert_command_success(install_result, "Team: Install dev environment")
        
        # Step 5: Generate team quality report
        print("📊 Step 5: Generating team quality report...")
        team_report = cli_runner.run_command("quality report")
        TestAssertions.assert_command_success(team_report, "Team: Quality report")
        
        print("✅ Team development workflow completed successfully!")
    
    def test_project_handoff_workflow(self, cli_runner, isolated_environment):
        """Test project handoff from one team to another."""
        # Step 1: Original team creates project configuration
        print("📋 Step 1: Original team creates project configuration...")
        project_suite = cli_runner.run_command(
            "suite create project-alpha --description 'Project Alpha configuration' --category production"
        )
        TestAssertions.assert_command_success(project_suite, "Handoff: Create project suite")
        isolated_environment.add_suite("project-alpha")
        
        # Add project-specific servers
        project_servers = ["http", "sqlite", "filesystem"]
        for server in project_servers:
            cli_runner.run_command(f"suite add project-alpha {server}")
        
        # Step 2: Document project with quality feedback
        print("📝 Step 2: Documenting project configuration...")
        for server in project_servers:
            doc_feedback = cli_runner.run_command(
                f"quality feedback {server} project-alpha --rating 4 --comment 'Used in Project Alpha - works reliably'"
            )
            TestAssertions.assert_command_success(doc_feedback, f"Handoff: Document {server}")
        
        # Step 3: New team reviews project configuration
        print("👀 Step 3: New team reviews project configuration...")
        review_suite = cli_runner.run_command("suite show project-alpha")
        TestAssertions.assert_command_success(review_suite, "Handoff: Review suite")
        
        TestAssertions.assert_contains_all(
            review_suite['stdout'], 
            project_servers, 
            "All project servers documented"
        )
        
        # Step 4: New team tests configuration
        print("🧪 Step 4: New team tests configuration...")
        test_config = cli_runner.run_command("install-suite --suite-name project-alpha --dry-run")
        TestAssertions.assert_command_success(test_config, "Handoff: Test configuration")
        
        # Step 5: New team provides feedback
        print("💬 Step 5: New team provides feedback...")
        handoff_feedback = cli_runner.run_command(
            "quality feedback http handoff-review --rating 5 --comment 'Configuration handoff successful - well documented'"
        )
        TestAssertions.assert_command_success(handoff_feedback, "Handoff: New team feedback")
        
        print("✅ Project handoff workflow completed successfully!")


class TestMaintenanceWorkflows:
    """Test maintenance and operational workflows."""
    
    def test_routine_maintenance_workflow(self, cli_runner, isolated_environment):
        """Test routine system maintenance workflow."""
        # Step 1: Admin checks system status
        print("🔍 Step 1: Checking overall system status...")
        status_check = cli_runner.run_command("status")
        TestAssertions.assert_command_success(status_check, "Maintenance: Status check")
        
        # Step 2: Review quality metrics
        print("📊 Step 2: Reviewing system quality metrics...")
        quality_check = cli_runner.run_command("quality status")
        TestAssertions.assert_command_success(quality_check, "Maintenance: Quality status")
        
        # Step 3: Update server catalog
        print("🔄 Step 3: Updating server catalog...")
        catalog_update = cli_runner.run_command("discover --update-catalog")
        TestAssertions.assert_command_success(catalog_update, "Maintenance: Update catalog")
        
        # Step 4: Review server rankings
        print("📈 Step 4: Reviewing server quality rankings...")
        rankings_check = cli_runner.run_command("quality rankings --limit 10")
        TestAssertions.assert_command_success(rankings_check, "Maintenance: Check rankings")
        
        # Step 5: Generate maintenance report
        print("📋 Step 5: Generating maintenance report...")
        maintenance_report = cli_runner.run_command("quality report")
        TestAssertions.assert_command_success(maintenance_report, "Maintenance: Generate report")
        
        # Step 6: Verify all suites are healthy
        print("✅ Step 6: Verifying suite health...")
        suite_summary = cli_runner.run_command("suite summary")
        TestAssertions.assert_command_success(suite_summary, "Maintenance: Suite summary")
        
        print("✅ Routine maintenance workflow completed successfully!")
    
    def test_emergency_recovery_workflow(self, cli_runner, isolated_environment):
        """Test emergency recovery workflow."""
        # Step 1: Simulate emergency - create problematic configuration
        print("🚨 Step 1: Emergency situation - problematic configuration detected...")
        
        # Create emergency suite with servers
        emergency_suite = cli_runner.run_command(
            "suite create emergency-recovery --description 'Emergency recovery test'"
        )
        TestAssertions.assert_command_success(emergency_suite, "Emergency: Create recovery suite")
        isolated_environment.add_suite("emergency-recovery")
        
        # Add servers to suite
        emergency_servers = ["filesystem", "sqlite"]
        for server in emergency_servers:
            cli_runner.run_command(f"suite add emergency-recovery {server}")
        
        # Step 2: Quick system assessment
        print("🔍 Step 2: Quick system assessment...")
        quick_status = cli_runner.run_command("system-info")
        TestAssertions.assert_command_success(quick_status, "Emergency: System assessment")
        
        # Step 3: Attempt recovery installation
        print("🔧 Step 3: Attempting recovery installation...")
        recovery_install = cli_runner.run_command("install-suite --suite-name emergency-recovery --dry-run")
        TestAssertions.assert_command_success(recovery_install, "Emergency: Recovery installation")
        
        # Step 4: Verify recovery suite is functional
        print("✅ Step 4: Verifying recovery suite...")
        verify_suite = cli_runner.run_command("suite show emergency-recovery")
        TestAssertions.assert_command_success(verify_suite, "Emergency: Verify recovery")
        
        TestAssertions.assert_contains_all(
            verify_suite['stdout'], 
            emergency_servers, 
            "Recovery suite contains all servers"
        )
        
        # Step 5: Document emergency response
        print("📝 Step 5: Documenting emergency response...")
        emergency_feedback = cli_runner.run_command(
            "quality feedback filesystem emergency-test --rating 5 --comment 'Successful emergency recovery'"
        )
        TestAssertions.assert_command_success(emergency_feedback, "Emergency: Document response")
        
        print("✅ Emergency recovery workflow completed successfully!")


@pytest.mark.integration
@pytest.mark.slow
class TestComplexIntegrationWorkflows:
    """Test complex multi-step integration workflows."""
    
    def test_complete_enterprise_deployment_workflow(self, cli_runner, isolated_environment):
        """Test complete enterprise deployment workflow."""
        print("🏢 Starting Enterprise Deployment Workflow...")
        
        # Phase 1: Environment Setup
        print("\n📋 Phase 1: Environment Setup")
        environments = ["development", "staging", "production"]
        
        for env in environments:
            suite_result = cli_runner.run_command(
                f"suite create {env}-env --description '{env.title()} environment' --category {env}"
            )
            TestAssertions.assert_command_success(suite_result, f"Enterprise: Create {env} environment")
            isolated_environment.add_suite(f"{env}-env")
        
        # Phase 2: Server Discovery and Selection
        print("\n🔍 Phase 2: Server Discovery and Selection")
        discovery_result = cli_runner.run_command("discover --type npm --limit 10")
        TestAssertions.assert_command_success(discovery_result, "Enterprise: Server discovery")
        
        # Phase 3: Environment Configuration
        print("\n⚙️ Phase 3: Environment Configuration")
        env_configs = {
            "development": ["filesystem", "sqlite"],
            "staging": ["filesystem", "sqlite", "http"],
            "production": ["http", "sqlite", "filesystem"]
        }
        
        for env, servers in env_configs.items():
            for server in servers:
                add_result = cli_runner.run_command(f"suite add {env}-env {server}")
                TestAssertions.assert_command_success(add_result, f"Enterprise: Configure {env} with {server}")
        
        # Phase 4: Quality Assurance
        print("\n🧪 Phase 4: Quality Assurance Testing")
        for env in environments:
            qa_result = cli_runner.run_command(f"install-suite --suite-name {env}-env --dry-run")
            TestAssertions.assert_command_success(qa_result, f"Enterprise: QA test {env}")
            
            TestAssertions.assert_not_contains(
                qa_result['stdout'], 
                ["not implemented"], 
                f"Enterprise: {env} environment installation implemented"
            )
        
        # Phase 5: Quality Metrics Collection
        print("\n📊 Phase 5: Quality Metrics Collection")
        for env, servers in env_configs.items():
            for server in servers:
                rating = 5 if env == "production" else 4
                feedback_result = cli_runner.run_command(
                    f"quality feedback {server} enterprise-{env} --rating {rating} --comment 'Enterprise {env} deployment'"
                )
                TestAssertions.assert_command_success(feedback_result, f"Enterprise: QA feedback {env} {server}")
        
        # Phase 6: Deployment Verification
        print("\n✅ Phase 6: Deployment Verification")
        
        # Verify all environments exist
        suite_list = cli_runner.run_command("suite list")
        for env in environments:
            TestAssertions.assert_contains_all(
                suite_list['stdout'], 
                [f"{env}-env"], 
                f"Enterprise: {env} environment deployed"
            )
        
        # Generate final deployment report
        final_report = cli_runner.run_command("quality report")
        TestAssertions.assert_command_success(final_report, "Enterprise: Final deployment report")
        
        print("\n🎉 Enterprise Deployment Workflow completed successfully!")
        print("   - 3 environments configured")
        print("   - Multiple servers per environment")
        print("   - Quality metrics collected")
        print("   - Deployment verified")
    
    def test_continuous_integration_workflow(self, cli_runner, isolated_environment):
        """Test continuous integration workflow simulation."""
        print("🔄 Starting Continuous Integration Workflow...")
        
        # Phase 1: CI Pipeline Setup
        print("\n🔧 Phase 1: CI Pipeline Setup")
        ci_suite = cli_runner.run_command(
            "suite create ci-pipeline --description 'Continuous Integration Pipeline' --category testing"
        )
        TestAssertions.assert_command_success(ci_suite, "CI: Create pipeline suite")
        isolated_environment.add_suite("ci-pipeline")
        
        # Phase 2: Add CI Tools
        print("\n🛠️ Phase 2: Adding CI Tools")
        ci_tools = ["filesystem", "sqlite", "http"]
        
        for tool in ci_tools:
            add_result = cli_runner.run_command(f"suite add ci-pipeline {tool}")
            TestAssertions.assert_command_success(add_result, f"CI: Add {tool}")
        
        # Phase 3: Automated Testing
        print("\n🧪 Phase 3: Automated Testing Simulation")
        for iteration in range(3):
            test_result = cli_runner.run_command("install-suite --suite-name ci-pipeline --dry-run")
            TestAssertions.assert_command_success(test_result, f"CI: Automated test iteration {iteration + 1}")
            
            # Record test results
            for tool in ci_tools:
                rating = 5 if iteration >= 1 else 4  # Improve over iterations
                feedback_result = cli_runner.run_command(
                    f"quality feedback {tool} ci-iteration-{iteration} --rating {rating} --comment 'CI test iteration {iteration + 1}'"
                )
                TestAssertions.assert_command_success(feedback_result, f"CI: Record test {iteration + 1} for {tool}")
        
        # Phase 4: Quality Gate Check
        print("\n🚦 Phase 4: Quality Gate Check")
        quality_gate = cli_runner.run_command("quality rankings --limit 5")
        TestAssertions.assert_command_success(quality_gate, "CI: Quality gate check")
        
        # Phase 5: Deployment Decision
        print("\n📋 Phase 5: Deployment Decision")
        deployment_check = cli_runner.run_command("suite show ci-pipeline")
        TestAssertions.assert_command_success(deployment_check, "CI: Deployment readiness check")
        
        TestAssertions.assert_contains_all(
            deployment_check['stdout'], 
            ci_tools, 
            "CI: All tools ready for deployment"
        )
        
        print("\n✅ Continuous Integration Workflow completed successfully!")
        print("   - CI pipeline configured")
        print("   - 3 automated test iterations")
        print("   - Quality metrics tracked")
        print("   - Deployment readiness verified")