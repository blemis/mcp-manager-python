"""
JSON Test Runner - Main interface for executing JSON-based test scenarios.

Provides a unified interface for discovering, organizing, executing, and reporting
on JSON-defined test scenarios. Integrates with existing test infrastructure.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from tests.engine.test_engine import DynamicTestEngine, ScenarioResult
from tests.engine.scenario_parser import ScenarioParser, ScenarioMetadata
from tests.ai_integration.schema_validator import TestScenarioValidator
from src.mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)

class JsonTestRunner:
    """Main test runner for JSON-based scenarios."""
    
    def __init__(self, scenarios_root: Optional[Path] = None):
        """Initialize the JSON test runner."""
        self.parser = ScenarioParser(scenarios_root)
        self.validator = TestScenarioValidator()
        self.engine = DynamicTestEngine(self.validator)
        self.results = []
    
    def discover_scenarios(self,
                          category: Optional[str] = None,
                          priority: Optional[str] = None,
                          tags: Optional[List[str]] = None,
                          created_by: Optional[str] = None) -> List[ScenarioMetadata]:
        """
        Discover scenarios matching the given criteria.
        
        Args:
            category: Filter by category (smoke, core, workflow, etc.)
            priority: Filter by priority (critical, high, medium, low)
            tags: Filter by tags (must contain all specified tags)
            created_by: Filter by creator (ai, admin, system, migration)
            
        Returns:
            List of matching scenario metadata
        """
        logger.info("🔍 Discovering test scenarios...")
        
        scenarios = self.parser.discover_scenarios(
            category_filter=category,
            priority_filter=priority,
            tag_filter=tags,
            created_by_filter=created_by
        )
        
        # Check for duplicates
        duplicates = self.parser.detect_duplicate_scenarios(scenarios)
        if duplicates:
            logger.warning(f"⚠️  Found {len(duplicates)} potential duplicate scenarios")
            for dup1, dup2 in duplicates[:3]:  # Show first 3
                logger.warning(f"   • '{dup1.name}' vs '{dup2.name}'")
        
        logger.info(f"📋 Discovered {len(scenarios)} scenarios")
        return scenarios
    
    async def run_scenarios(self, 
                           scenarios: List[ScenarioMetadata],
                           batch_size: int = 5,
                           max_batch_duration: float = 300.0,
                           stop_on_failure: bool = False) -> List[ScenarioResult]:
        """
        Execute a list of scenarios with batching and error handling.
        
        Args:
            scenarios: List of scenarios to execute
            batch_size: Maximum scenarios per batch
            max_batch_duration: Maximum duration per batch (seconds)
            stop_on_failure: Whether to stop execution on first failure
            
        Returns:
            List of scenario execution results
        """
        if not scenarios:
            logger.warning("📋 No scenarios to execute")
            return []
        
        logger.info(f"🚀 Starting execution of {len(scenarios)} scenarios")
        
        # Create optimal batches
        batches = self.parser.create_execution_batches(
            scenarios, max_batch_duration, batch_size
        )
        
        all_results = []
        start_time = datetime.now()
        
        for batch_num, batch in enumerate(batches, 1):
            logger.info(f"📦 Executing batch {batch_num}/{len(batches)} ({len(batch)} scenarios)")
            
            batch_results = []
            
            for scenario_metadata in batch:
                logger.info(f"🎯 Running: {scenario_metadata.name}")
                
                # Load the full scenario
                scenario_data = self.parser.load_scenario(scenario_metadata.file_path)
                if not scenario_data:
                    # Create a failure result for scenarios that couldn't be loaded
                    result = ScenarioResult(
                        scenario_id=scenario_metadata.id,
                        scenario_name=scenario_metadata.name,
                        success=False,
                        duration=0.0,
                        step_results=[],
                        validation_results={},
                        cleanup_performed=False,
                        error_message="Failed to load scenario data"
                    )
                    batch_results.append(result)
                    continue
                
                # Execute the scenario
                try:
                    result = await self.engine.execute_scenario(scenario_data)
                    batch_results.append(result)
                    
                    # Log result
                    status_emoji = "✅" if result.success else "❌"
                    logger.info(f"   {status_emoji} {result.scenario_name} ({result.duration:.2f}s)")
                    
                    # Stop on failure if requested
                    if not result.success and stop_on_failure:
                        logger.error("❌ Stopping execution due to failure")
                        all_results.extend(batch_results)
                        return all_results
                        
                except Exception as e:
                    logger.error(f"❌ Scenario execution failed with exception: {e}")
                    
                    result = ScenarioResult(
                        scenario_id=scenario_metadata.id,
                        scenario_name=scenario_metadata.name,
                        success=False,
                        duration=0.0,
                        step_results=[],
                        validation_results={},
                        cleanup_performed=False,
                        error_message=str(e)
                    )
                    batch_results.append(result)
                    
                    if stop_on_failure:
                        all_results.extend(batch_results)
                        return all_results
            
            all_results.extend(batch_results)
            
            # Print batch summary
            batch_success = sum(1 for r in batch_results if r.success)
            batch_total = len(batch_results)
            logger.info(f"📊 Batch {batch_num} complete: {batch_success}/{batch_total} passed")
        
        total_duration = (datetime.now() - start_time).total_seconds()
        total_success = sum(1 for r in all_results if r.success)
        total_count = len(all_results)
        
        logger.info(f"🏁 Execution complete: {total_success}/{total_count} passed in {total_duration:.2f}s")
        
        self.results = all_results
        return all_results
    
    async def run_category(self, category: str, **kwargs) -> List[ScenarioResult]:
        """Run all scenarios in a specific category."""
        scenarios = self.discover_scenarios(category=category)
        if not scenarios:
            logger.warning(f"📋 No scenarios found for category: {category}")
            return []
        
        logger.info(f"🎯 Running {len(scenarios)} scenarios in category: {category}")
        return await self.run_scenarios(scenarios, **kwargs)
    
    async def run_smoke_tests(self, **kwargs) -> List[ScenarioResult]:
        """Run all smoke test scenarios."""
        return await self.run_category("smoke", **kwargs)
    
    async def run_by_priority(self, priority: str, **kwargs) -> List[ScenarioResult]:
        """Run all scenarios with a specific priority."""
        scenarios = self.discover_scenarios(priority=priority)
        if not scenarios:
            logger.warning(f"📋 No scenarios found for priority: {priority}")
            return []
        
        logger.info(f"🔥 Running {len(scenarios)} scenarios with priority: {priority}")
        return await self.run_scenarios(scenarios, **kwargs)
    
    def generate_report(self, results: Optional[List[ScenarioResult]] = None) -> Dict[str, Any]:
        """Generate a comprehensive test execution report."""
        if results is None:
            results = self.results
        
        if not results:
            return {"error": "No test results available"}
        
        report = self.engine.generate_report(results)
        
        # Add additional analysis
        categories = {}
        priorities = {}
        
        for result in results:
            # We'd need to access scenario metadata for category/priority
            # This is a simplified version
            pass
        
        return report
    
    def save_report(self, 
                   results: Optional[List[ScenarioResult]] = None,
                   output_path: Optional[Path] = None) -> Path:
        """Save test results report to file."""
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(__file__).parent.parent / "results" / f"json_test_report_{timestamp}.json"
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        report = self.generate_report(results)
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"📄 Test report saved to: {output_path}")
        return output_path
    
    def print_detailed_results(self, results: Optional[List[ScenarioResult]] = None):
        """Print detailed test results similar to pytest format."""
        if results is None:
            results = self.results
        
        if not results:
            print("📋 No test results to display")
            return
        
        print("\n🧪 JSON Test Execution Details")
        print("=" * 80)
        
        for result in results:
            # Print test name and description
            status_icon = "✅" if result.success else "❌"
            status_text = "PASSED" if result.success else "FAILED"
            
            print(f"{result.scenario_name} ", end="")
            
            # Show MCP server deployments if any
            if result.step_results:
                setup_steps = [s for s in result.step_results if 'setup' in s.expected_outcome.lower() or 'deploy' in s.output.lower()]
                if setup_steps:
                    print(f"🎯 Auto-loading suite for {result.scenario_name}")
                    for step in setup_steps:
                        if "Successfully deployed server" in step.output:
                            server_name = step.output.split("Successfully deployed server: ")[-1].split()[0] if "Successfully deployed server: " in step.output else "test-server"
                            print(f"📦 Loading test suite: {server_name}")
                            print(f"   Description: {result.scenario_name}")
                            print(f"   ➕ Adding MCP server: {server_name}")
                            print(f"      ✅ Successfully deployed server: {server_name}")
                            print(f"✅ Suite '{server_name}' loaded successfully!")
            
            print(f"\033[32m{status_text}\033[0m" if result.success else f"\033[91m{status_text}\033[0m")
            
            # Show error details for failed tests
            if not result.success and result.error_message:
                print(f"   Error: {result.error_message}")
        
        # Print summary statistics
        total = len(results)
        passed = sum(1 for r in results if r.success)
        failed = total - passed
        total_duration = sum(r.duration for r in results)
        
        print(f"\n\033[33m========================= \033[32m{passed} passed\033[0m", end="")
        if failed > 0:
            print(f", \033[91m{failed} failed\033[0m", end="")
        print(f"\033[33m in {total_duration:.2f}s\033[0m")
    
    def print_summary(self, results: Optional[List[ScenarioResult]] = None):
        """Print a human-readable test summary."""
        if results is None:
            results = self.results
        
        if not results:
            print("📋 No test results to display")
            return
        
        total = len(results)
        passed = sum(1 for r in results if r.success)
        failed = total - passed
        total_duration = sum(r.duration for r in results)
        
        print(f"\\n🎯 JSON Test Execution Summary")
        print(f"{'='*50}")
        print(f"📊 Total Scenarios: {total}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"📈 Success Rate: {(passed/total*100):.1f}%")
        print(f"⏱️  Total Duration: {total_duration:.2f}s")
        print(f"⚡ Average Duration: {total_duration/total:.2f}s")
        
        if failed > 0:
            print(f"\\n❌ Failed Scenarios:")
            for result in results:
                if not result.success:
                    print(f"   • {result.scenario_name}")
                    if result.error_message:
                        print(f"     Error: {result.error_message}")
    
    def list_available_scenarios(self):
        """List all available scenarios with basic info."""
        scenarios = self.discover_scenarios()
        
        if not scenarios:
            print("📋 No scenarios found")
            return
        
        # Group by category
        categories = self.parser.organize_scenarios_by_category(scenarios)
        
        print(f"\\n📋 Available Test Scenarios ({len(scenarios)} total)")
        print(f"{'='*60}")
        
        for category, category_scenarios in categories.items():
            print(f"\\n📁 {category.upper()} ({len(category_scenarios)} scenarios)")
            for scenario in category_scenarios:
                priority_emoji = {"critical": "🔴", "high": "🟡", "medium": "🔵", "low": "⚪"}.get(scenario.priority, "⚪")
                print(f"   {priority_emoji} {scenario.name}")
                print(f"      ID: {scenario.id}")
                print(f"      Priority: {scenario.priority}")
                print(f"      Duration: ~{scenario.estimated_duration:.0f}s")
                if scenario.required_servers:
                    print(f"      Servers: {', '.join(scenario.required_servers)}")

async def main():
    """CLI interface for the JSON test runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="JSON Test Runner for MCP Manager")
    parser.add_argument("--category", help="Run scenarios in specific category")
    parser.add_argument("--priority", help="Run scenarios with specific priority")
    parser.add_argument("--tag", action="append", help="Run scenarios with specific tags")
    parser.add_argument("--created-by", help="Run scenarios created by specific source")
    parser.add_argument("--list", action="store_true", help="List available scenarios")
    parser.add_argument("--smoke", action="store_true", help="Run smoke tests only")
    parser.add_argument("--batch-size", type=int, default=5, help="Scenarios per batch")
    parser.add_argument("--stop-on-failure", action="store_true", help="Stop on first failure")
    parser.add_argument("--save-report", help="Save report to specified path")
    
    args = parser.parse_args()
    
    runner = JsonTestRunner()
    
    if args.list:
        runner.list_available_scenarios()
        return
    
    # Run scenarios based on arguments
    results = []
    
    if args.smoke:
        results = await runner.run_smoke_tests(
            batch_size=args.batch_size,
            stop_on_failure=args.stop_on_failure
        )
    elif args.category:
        results = await runner.run_category(
            args.category,
            batch_size=args.batch_size,
            stop_on_failure=args.stop_on_failure
        )
    elif args.priority:
        results = await runner.run_by_priority(
            args.priority,
            batch_size=args.batch_size,
            stop_on_failure=args.stop_on_failure
        )
    else:
        # Run all discovered scenarios
        scenarios = runner.discover_scenarios(
            category=args.category,
            priority=args.priority,
            tags=args.tag,
            created_by=args.created_by
        )
        results = await runner.run_scenarios(
            scenarios,
            batch_size=args.batch_size,
            stop_on_failure=args.stop_on_failure
        )
    
    # Print summary
    runner.print_summary(results)
    
    # Save report if requested
    if args.save_report:
        runner.save_report(results, Path(args.save_report))
    
    # Exit with non-zero code if any tests failed
    if results and not all(r.success for r in results):
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())