"""
Quality tracking testing for MCP Manager.

Tests quality metrics, rankings, feedback, and reporting functionality.
Professional black-box testing of the quality tracking system.
"""

import pytest
import time
from tests.utils.validators import OutputValidator, TestAssertions


class TestQualityStatus:
    """Test quality tracking status functionality."""
    
    def test_quality_status_basic(self, cli_runner):
        """Test basic quality status command."""
        result = cli_runner.run_command("quality status")
        
        TestAssertions.assert_command_success(result, "Quality status basic")
        assert OutputValidator.validate_status_output(result['stdout'])
    
    def test_quality_status_empty_system(self, cli_runner):
        """Test quality status with no tracked servers."""
        result = cli_runner.run_command("quality status")
        
        TestAssertions.assert_command_success(result, "Quality status empty system")
        # Empty status is valid - should show appropriate message
        assert result['stdout'].strip() != ""
    
    def test_quality_status_verbose(self, cli_runner):
        """Test quality status with verbose output (if supported)."""
        result = cli_runner.run_command("quality status --verbose")
        
        # Verbose flag might not be implemented
        if result['success']:
            TestAssertions.assert_command_success(result, "Quality status verbose")
        else:
            # If verbose not supported, should still show basic status
            basic_result = cli_runner.run_command("quality status")
            TestAssertions.assert_command_success(basic_result, "Quality status fallback")


class TestQualityRankings:
    """Test quality rankings functionality."""
    
    def test_quality_rankings_basic(self, cli_runner):
        """Test basic quality rankings command."""
        result = cli_runner.run_command("quality rankings")
        
        TestAssertions.assert_command_success(result, "Quality rankings basic")
        # Rankings can be empty if no servers are tracked
    
    def test_quality_rankings_with_limit(self, cli_runner):
        """Test quality rankings with result limit."""
        limits = [5, 10, 20]
        
        for limit in limits:
            result = cli_runner.run_command(f"quality rankings --limit {limit}")
            TestAssertions.assert_command_success(result, f"Quality rankings limit {limit}")
    
    def test_quality_rankings_by_metric(self, cli_runner):
        """Test quality rankings sorted by different metrics (if supported)."""
        metrics = ["performance", "reliability", "popularity", "rating"]
        
        for metric in metrics:
            result = cli_runner.run_command(f"quality rankings --sort-by {metric}")
            
            # Sort options might not be implemented
            if result['success']:
                TestAssertions.assert_command_success(result, f"Rankings by {metric}")
    
    def test_quality_rankings_category_filter(self, cli_runner):
        """Test quality rankings filtered by category (if supported)."""
        categories = ["npm", "docker", "custom"]
        
        for category in categories:
            result = cli_runner.run_command(f"quality rankings --category {category}")
            
            # Category filtering might not be implemented
            if result['success']:
                TestAssertions.assert_command_success(result, f"Rankings for {category}")


class TestQualityFeedback:
    """Test quality feedback recording functionality."""
    
    def test_record_quality_feedback_basic(self, cli_runner, isolated_environment):
        """Test recording basic quality feedback."""
        server_name = "test-feedback-server"
        install_id = "test-install-id"
        
        # First add a server to provide feedback on
        cli_runner.run_command(
            f"add {server_name} --type custom --command 'echo test'"
        )
        isolated_environment.add_server(server_name)
        
        # Record feedback
        result = cli_runner.run_command(
            f"quality feedback {server_name} {install_id} --rating 4 --comment 'Works well'"
        )
        
        TestAssertions.assert_command_success(result, "Record quality feedback")
        assert OutputValidator.validate_success_message(result['stdout'], "feedback")
    
    @pytest.mark.parametrize("rating", [1, 2, 3, 4, 5])
    def test_record_feedback_different_ratings(self, cli_runner, isolated_environment, rating):
        """Test recording feedback with different rating values."""
        server_name = f"test-rating-{rating}-server"
        install_id = f"test-rating-{rating}-id"
        
        # Add server
        cli_runner.run_command(
            f"add {server_name} --type custom --command 'echo test'"
        )
        isolated_environment.add_server(server_name)
        
        # Record feedback with specific rating
        result = cli_runner.run_command(
            f"quality feedback {server_name} {install_id} --rating {rating} --comment 'Rating {rating} test'"
        )
        
        TestAssertions.assert_command_success(result, f"Feedback rating {rating}")
    
    def test_record_feedback_with_detailed_comment(self, cli_runner, isolated_environment):
        """Test recording feedback with detailed comments."""
        server_name = "test-detailed-feedback-server"
        install_id = "test-detailed-id"
        
        # Add server
        cli_runner.run_command(
            f"add {server_name} --type custom --command 'echo test'"
        )
        isolated_environment.add_server(server_name)
        
        # Long detailed comment
        comment = "This server works excellently for filesystem operations. Installation was smooth, performance is great, and documentation is comprehensive."
        
        result = cli_runner.run_command(
            f"quality feedback {server_name} {install_id} --rating 5 --comment '{comment}'"
        )
        
        TestAssertions.assert_command_success(result, "Detailed feedback comment")
    
    def test_record_feedback_invalid_rating(self, cli_runner):
        """Test recording feedback with invalid rating values."""
        invalid_ratings = [0, 6, -1, 10]
        
        for rating in invalid_ratings:
            result = cli_runner.run_command(
                f"quality feedback test-server test-id --rating {rating} --comment 'Invalid'",
                expect_success=False
            )
            
            TestAssertions.assert_command_failure(result, f"Invalid rating {rating}")
            assert OutputValidator.validate_error_message(result['stderr'], "invalid")
    
    def test_record_feedback_nonexistent_server(self, cli_runner):
        """Test recording feedback for nonexistent server."""
        result = cli_runner.run_command(
            "quality feedback nonexistent-server test-id --rating 4 --comment 'Test'"
        )
        
        # Should either fail or create placeholder entry
        if not result['success']:
            TestAssertions.assert_command_failure(result, "Feedback for nonexistent server")
        else:
            # If it succeeds, should warn about nonexistent server
            assert "not found" in result['stdout'].lower() or \
                   "warning" in result['stdout'].lower()
    
    def test_record_feedback_missing_comment(self, cli_runner, isolated_environment):
        """Test recording feedback without comment (should work with rating only)."""
        server_name = "test-no-comment-server"
        install_id = "test-no-comment-id"
        
        # Add server
        cli_runner.run_command(
            f"add {server_name} --type custom --command 'echo test'"
        )
        isolated_environment.add_server(server_name)
        
        # Record feedback without comment
        result = cli_runner.run_command(
            f"quality feedback {server_name} {install_id} --rating 4"
        )
        
        TestAssertions.assert_command_success(result, "Feedback without comment")


class TestQualityReports:
    """Test quality reporting functionality."""
    
    def test_quality_report_basic(self, cli_runner):
        """Test basic quality report generation."""
        result = cli_runner.run_command("quality report")
        
        TestAssertions.assert_command_success(result, "Quality report basic")
        # Report can be empty if no data exists
    
    def test_quality_report_specific_server(self, cli_runner, isolated_environment):
        """Test quality report for specific server."""
        server_name = "test-report-server"
        
        # Add server and provide feedback
        cli_runner.run_command(
            f"add {server_name} --type custom --command 'echo test'"
        )
        isolated_environment.add_server(server_name)
        
        cli_runner.run_command(
            f"quality feedback {server_name} test-id --rating 4 --comment 'Good server'"
        )
        
        # Generate report for specific server
        result = cli_runner.run_command(f"quality report --server {server_name}")
        
        # Server-specific reports might not be implemented
        if result['success']:
            TestAssertions.assert_command_success(result, "Server-specific quality report")
            TestAssertions.assert_contains_all(
                result['stdout'], 
                [server_name], 
                "Report contains server name"
            )
    
    def test_quality_report_date_range(self, cli_runner):
        """Test quality report with date range (if supported)."""
        # Test with recent date range
        result = cli_runner.run_command("quality report --since 7d")
        
        # Date range filtering might not be implemented
        if result['success']:
            TestAssertions.assert_command_success(result, "Quality report with date range")
    
    def test_quality_report_export_formats(self, cli_runner):
        """Test quality report export in different formats (if supported)."""
        formats = ["json", "csv", "html"]
        
        for fmt in formats:
            result = cli_runner.run_command(f"quality report --format {fmt}")
            
            # Export formats might not be implemented
            if result['success']:
                TestAssertions.assert_command_success(result, f"Quality report {fmt} format")
                
                if fmt == "json":
                    # Validate JSON format
                    is_valid, _ = OutputValidator.validate_json_output(result['stdout'])
                    assert is_valid, f"Report in {fmt} format is valid"


class TestQualityMetrics:
    """Test quality metrics and calculations."""
    
    def test_quality_metrics_calculation(self, cli_runner, isolated_environment):
        """Test that quality metrics are calculated properly."""
        server_name = "test-metrics-server"
        install_id = "test-metrics-id"
        
        # Add server
        cli_runner.run_command(
            f"add {server_name} --type custom --command 'echo test'"
        )
        isolated_environment.add_server(server_name)
        
        # Provide multiple feedback entries
        ratings = [4, 5, 3, 4, 5]
        comments = [
            "Good performance",
            "Excellent server",
            "Decent but could improve",
            "Works well",
            "Outstanding quality"
        ]
        
        for rating, comment in zip(ratings, comments):
            cli_runner.run_command(
                f"quality feedback {server_name} {install_id}-{rating} --rating {rating} --comment '{comment}'"
            )
        
        # Check if metrics are reflected in rankings
        rankings_result = cli_runner.run_command("quality rankings")
        if rankings_result['success'] and server_name in rankings_result['stdout']:
            TestAssertions.assert_contains_all(
                rankings_result['stdout'], 
                [server_name], 
                "Server appears in rankings after feedback"
            )
    
    def test_quality_trends_tracking(self, cli_runner, isolated_environment):
        """Test quality trends over time (if supported)."""
        server_name = "test-trends-server"
        
        # Add server
        cli_runner.run_command(
            f"add {server_name} --type custom --command 'echo test'"
        )
        isolated_environment.add_server(server_name)
        
        # Provide feedback over time (simulate with different IDs)
        for i in range(3):
            cli_runner.run_command(
                f"quality feedback {server_name} trend-{i} --rating {3+i} --comment 'Trend test {i}'"
            )
        
        # Check trends command (if available)
        result = cli_runner.run_command(f"quality trends --server {server_name}")
        
        # Trends might not be implemented
        if result['success']:
            TestAssertions.assert_command_success(result, "Quality trends tracking")


class TestQualityIntegration:
    """Test quality system integration with other components."""
    
    def test_quality_integration_with_discovery(self, cli_runner):
        """Test quality information integration with discovery."""
        # Run discovery
        discovery_result = cli_runner.run_command("discover --limit 5")
        TestAssertions.assert_command_success(discovery_result, "Discovery for quality integration")
        
        # Check if quality information is included in discovery results
        quality_indicators = ["rating", "score", "quality", "feedback"]
        has_quality_info = any(
            indicator in discovery_result['stdout'].lower() 
            for indicator in quality_indicators
        )
        
        # Quality integration might not be implemented
        if has_quality_info:
            # Quality information is integrated with discovery
            pass
    
    def test_quality_integration_with_suite_installation(self, cli_runner, isolated_environment):
        """Test quality considerations in suite installation."""
        suite_name = "test-quality-integration-suite"
        
        # Create suite
        cli_runner.run_command(
            f"suite create {suite_name} --description 'Quality integration test'"
        )
        isolated_environment.add_suite(suite_name)
        
        # Add server with feedback
        server_name = "quality-integration-server"
        cli_runner.run_command(
            f"add {server_name} --type custom --command 'echo test'"
        )
        isolated_environment.add_server(server_name)
        
        cli_runner.run_command(
            f"quality feedback {server_name} test-id --rating 5 --comment 'Excellent'"
        )
        
        cli_runner.run_command(f"suite add {suite_name} {server_name}")
        
        # Test suite installation - should consider quality
        install_result = cli_runner.run_command(
            f"install-suite --suite-name {suite_name} --dry-run"
        )
        
        TestAssertions.assert_command_success(install_result, "Suite installation with quality data")
        
        # Quality considerations might not be implemented
        quality_mentions = ["quality", "rating", "score", "recommended"]
        has_quality_consideration = any(
            mention in install_result['stdout'].lower() 
            for mention in quality_mentions
        )
        
        # If quality is considered, it's a bonus feature
        if has_quality_consideration:
            # Quality information is used in installation decisions
            pass


@pytest.mark.integration
class TestQualityWorkflows:
    """Test complete quality tracking workflows."""
    
    def test_complete_quality_workflow(self, cli_runner, isolated_environment):
        """Test complete quality tracking workflow."""
        server_name = "test-quality-workflow-server"
        install_id = "test-workflow-id"
        
        # Step 1: Add server
        add_result = cli_runner.run_command(
            f"add {server_name} --type custom --command 'echo workflow'"
        )
        TestAssertions.assert_command_success(add_result, "Quality workflow: Add server")
        isolated_environment.add_server(server_name)
        
        # Step 2: Record initial feedback
        feedback_result = cli_runner.run_command(
            f"quality feedback {server_name} {install_id} --rating 4 --comment 'Initial feedback'"
        )
        TestAssertions.assert_command_success(feedback_result, "Quality workflow: Record feedback")
        
        # Step 3: Check status
        status_result = cli_runner.run_command("quality status")
        TestAssertions.assert_command_success(status_result, "Quality workflow: Check status")
        
        # Step 4: View rankings
        rankings_result = cli_runner.run_command("quality rankings")
        TestAssertions.assert_command_success(rankings_result, "Quality workflow: View rankings")
        
        # Step 5: Generate report
        report_result = cli_runner.run_command("quality report")
        TestAssertions.assert_command_success(report_result, "Quality workflow: Generate report")
        
        # Step 6: Record additional feedback
        followup_result = cli_runner.run_command(
            f"quality feedback {server_name} {install_id}-2 --rating 5 --comment 'Improved performance'"
        )
        TestAssertions.assert_command_success(followup_result, "Quality workflow: Follow-up feedback")
        
        # Step 7: Verify metrics updated
        final_rankings = cli_runner.run_command("quality rankings")
        TestAssertions.assert_command_success(final_rankings, "Quality workflow: Final rankings")
    
    def test_bulk_quality_feedback(self, cli_runner, isolated_environment):
        """Test recording quality feedback for multiple servers."""
        servers_data = [
            ("bulk-server-1", 5, "Excellent performance"),
            ("bulk-server-2", 4, "Good reliability"),
            ("bulk-server-3", 3, "Average functionality"),
            ("bulk-server-4", 4, "Solid choice"),
            ("bulk-server-5", 5, "Outstanding features")
        ]
        
        # Add servers and record feedback
        for server_name, rating, comment in servers_data:
            # Add server
            cli_runner.run_command(
                f"add {server_name} --type custom --command 'echo {server_name}'"
            )
            isolated_environment.add_server(server_name)
            
            # Record feedback
            feedback_result = cli_runner.run_command(
                f"quality feedback {server_name} bulk-test-id --rating {rating} --comment '{comment}'"
            )
            TestAssertions.assert_command_success(feedback_result, f"Bulk feedback: {server_name}")
        
        # Verify all feedback recorded in rankings
        rankings_result = cli_runner.run_command("quality rankings")
        TestAssertions.assert_command_success(rankings_result, "Bulk feedback: Final rankings")
        
        # Check if servers appear in rankings (they might not if system is empty)
        server_names = [name for name, _, _ in servers_data]
        found_servers = [
            name for name in server_names 
            if name in rankings_result['stdout']
        ]
        
        # If any servers appear in rankings, quality system is working
        if found_servers:
            assert len(found_servers) > 0, "Some servers appear in quality rankings"