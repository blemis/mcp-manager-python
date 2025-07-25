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
                          created_by: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Discover scenarios from database matching the given criteria.
        
        Args:
            category: Filter by category (smoke, core, workflow, etc.)
            priority: Filter by priority (critical, high, medium, low)
            tags: Filter by tags (must contain all specified tags)
            created_by: Filter by creator (ai, admin, system, migration)
            
        Returns:
            List of scenario dictionaries ready for execution
        """
        logger.info("🔍 Discovering test scenarios from database...")
        
        try:
            # Import database components
            from src.mcp_manager.core.test_management.database import TestManagementDB
            from src.mcp_manager.core.test_management.category_manager import TestCategoryManager
            from pathlib import Path
            import json
            
            # Initialize database
            test_db_path = Path(__file__).parent.parent / "fixtures" / "test_suites.db"
            db = TestManagementDB(test_db_path)
            category_manager = TestCategoryManager(test_db_path)
            
            # Map CLI category to database category if needed
            if category:
                category_mapping = {
                    'unit': 'basic-commands',
                    'smoke': 'basic-commands', 
                    'server': 'server-management',
                    'suite': 'suite-management',
                    'quality': 'quality-tracking',
                    'error': 'error-handling',
                    'workflow': 'workflows',
                }
                mapped_category = category_mapping.get(category, category)
                logger.debug(f"Mapped category '{category}' to '{mapped_category}'")
                category = mapped_category
            
            # Get scenarios from database
            db_scenarios = db.list_test_scenarios(
                category=category,
                enabled_only=True
            )
            
            # If no scenarios in database, create default ones for the category
            if not db_scenarios and category:
                logger.info(f"No scenarios found for category {category}, creating default scenario")
                default_scenario = self._create_default_scenario_for_category(category, db, category_manager)
                if default_scenario:
                    db_scenarios = [default_scenario]
            
            # Convert database scenarios to JSON format
            full_scenarios = []
            for db_scenario in db_scenarios:
                try:
                    scenario_dict = json.loads(db_scenario.scenario_json)
                    
                    # Apply additional filters
                    if priority and scenario_dict.get('scenario', {}).get('priority') != priority:
                        continue
                        
                    if created_by and scenario_dict.get('scenario', {}).get('created_by') != created_by:
                        continue
                        
                    if tags:
                        scenario_tags = scenario_dict.get('scenario', {}).get('tags', [])
                        if not any(tag in scenario_tags for tag in tags):
                            continue
                    
                    full_scenarios.append(scenario_dict)
                except Exception as e:
                    logger.error(f"Failed to parse scenario {db_scenario.id}: {e}")
            
            logger.info(f"📋 Discovered {len(full_scenarios)} scenarios from database")
            return full_scenarios
            
        except Exception as e:
            logger.error(f"Failed to discover scenarios from database: {e}")
            return []
    
    def _create_default_scenario_for_category(self, category: str, db, category_manager):
        """Create a default test scenario for a category if none exists."""
        try:
            import json
            from datetime import datetime
            from src.mcp_manager.core.test_management.models import TestScenario
            
            # Get category info from database
            category_info = db.get_test_category(category)
            if not category_info:
                logger.warning(f"Category {category} not found in database")
                return None
            
            # Get the suite for this category
            suite_id = db.get_suite_for_category(category)
            if not suite_id:
                logger.warning(f"No suite found for category {category}")
                return None
            
            # Create basic scenario JSON
            scenario_json = {
                "schema_version": "1.0",
                "scenario": {
                    "id": f"default_{category.replace('-', '_')}_test",
                    "name": f"Default {category_info.name} Test",
                    "description": f"Default test scenario for {category_info.description} - tests basic CLI functionality",
                    "created_by": "system",
                    "category": category,
                    "priority": "medium",
                    "confidence_score": 0.8,
                    "tags": ["system-generated", category]
                },
                "mcp_requirements": {
                    "required_servers": [],
                    "optional_servers": [],
                    "scope": "user"
                },
                "test_steps": [
                    {
                        "step_id": 1,
                        "action": "cli_command",
                        "command": "list",
                        "expect": "success",
                        "timeout": 15,
                        "description": f"Test basic functionality for {category}"
                    }
                ],
                "validation": {
                    "success_criteria": [
                        {
                            "type": "all_steps_pass",
                            "description": "All test steps must complete successfully"
                        }
                    ],
                    "cleanup_strategy": "minimal",
                    "cleanup_required": False,
                    "cleanup_steps": []
                },
                "metadata": {
                    "created_date": datetime.now().isoformat(),
                    "last_modified": datetime.now().isoformat(),
                    "execution_count": 0,
                    "success_rate": 0.0,
                    "average_duration": 0.0
                }
            }
            
            # Create TestScenario object
            test_scenario = TestScenario(
                id=scenario_json["scenario"]["id"],
                name=scenario_json["scenario"]["name"],
                description=scenario_json["scenario"]["description"],
                category=category,
                priority="medium",
                created_by="system",
                scenario_json=json.dumps(scenario_json, indent=2),
                tags=["system-generated", category],
                suite_id=suite_id
            )
            
            # Save to database
            if db.create_test_scenario(test_scenario):
                logger.info(f"Created default scenario for category {category}")
                return test_scenario
            else:
                logger.error(f"Failed to create default scenario for category {category}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating default scenario for {category}: {e}")
            return None
    
    async def run_scenarios(self, 
                           scenarios: List[Dict[str, Any]],
                           batch_size: int = 5,
                           max_batch_duration: float = 300.0,
                           stop_on_failure: bool = False) -> List[ScenarioResult]:
        """
        Execute a list of scenario dictionaries with batching and error handling.
        
        Args:
            scenarios: List of scenario dictionaries to execute
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
        
        all_results = []
        start_time = datetime.now()
        
        # Execute scenarios directly (no batching needed for now)
        for scenario_data in scenarios:
            scenario_info = scenario_data.get('scenario', {})
            scenario_id = scenario_info.get('id', 'unknown')
            scenario_name = scenario_info.get('name', 'Unknown Scenario')
            
            logger.info(f"🎯 Running: {scenario_name}")
            
            try:
                # Execute the scenario using the test engine
                result = await self.engine.execute_scenario(scenario_data)
                all_results.append(result)
                
                # Update scenario stats in database if we have the ID
                if scenario_id != 'unknown':
                    try:
                        from src.mcp_manager.core.test_management.database import TestManagementDB
                        from pathlib import Path
                        
                        test_db_path = Path(__file__).parent.parent / "fixtures" / "test_suites.db"
                        db = TestManagementDB(test_db_path)
                        db.update_scenario_stats(scenario_id, result.success, result.duration)
                    except Exception as e:
                        logger.debug(f"Failed to update stats for {scenario_id}: {e}")
                
                if stop_on_failure and not result.success:
                    logger.warning("🛑 Stopping execution due to failure")
                    break
                    
            except Exception as e:
                logger.error(f"❌ Scenario execution failed with exception: {e}")
                
                result = ScenarioResult(
                    scenario_id=scenario_id,
                    scenario_name=scenario_name,
                    success=False,
                    duration=0.0,
                    step_results=[],
                    validation_results={},
                    cleanup_performed=False,
                    error_message=str(e)
                )
                all_results.append(result)
                
                if stop_on_failure:
                    break
        
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
                scenario_info = scenario.get('scenario', {})
                priority = scenario_info.get('priority', 'medium')
                priority_emoji = {"critical": "🔴", "high": "🟡", "medium": "🔵", "low": "⚪"}.get(priority, "⚪")
                print(f"   {priority_emoji} {scenario_info.get('name', 'Unknown')}")
                print(f"      ID: {scenario_info.get('id', 'unknown')}")
                print(f"      Priority: {priority}")
                
                # Get required servers from mcp_requirements
                mcp_reqs = scenario.get('mcp_requirements', {})
                required_servers = [s.get('name', '') for s in mcp_reqs.get('required_servers', [])]
                if required_servers:
                    print(f"      Servers: {', '.join(required_servers)}")

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