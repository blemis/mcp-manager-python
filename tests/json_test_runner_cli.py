#!/usr/bin/env python3
"""
JSON Test Runner CLI - Modern test execution for MCP Manager.

Executes JSON-based test scenarios with the new dynamic architecture.
Can run alongside or replace the traditional pytest-based test runner.
"""

import sys
import argparse
import asyncio
import time
from pathlib import Path
from typing import List, Optional

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from tests.engine.json_test_runner import JsonTestRunner
from tests.ai_integration.ai_scenario_generator import AIScenarioGenerator

class JsonTestRunnerCLI:
    """CLI interface for JSON-based test execution."""
    
    def __init__(self):
        self.runner = JsonTestRunner()
        
        # Category mapping from CLI names to database category IDs
        self.category_mapping = {
            'unit': 'basic-commands',      # Unit tests map to basic-commands category
            'smoke': 'basic-commands',     # Smoke tests also use basic commands
            'server': 'server-management', # Server tests map to server-management category
            'suite': 'suite-management',   # Suite tests map to suite-management category
            'quality': 'quality-tracking', # Quality tests map to quality-tracking category
            'error': 'error-handling',     # Error tests map to error-handling category
            'workflow': 'workflows',       # Workflow tests map to workflows category
        }
    
    def map_category(self, category: str) -> str:
        """Map legacy category names to JSON category names."""
        if category in self.category_mapping:
            mapped = self.category_mapping[category]
            print(f"🔄 Mapping category '{category}' -> '{mapped}' for JSON compatibility")
            return mapped
        return category
    
    async def run_category(self, category: str, **kwargs) -> bool:
        """Run tests in a specific category using the EXISTING suite system."""
        original_category = category
        mapped_category = self.map_category(category)
        
        print(f"\n🧪 Running {original_category.upper()} JSON Tests")
        if mapped_category != original_category:
            print(f"    (Using JSON category: {mapped_category})")
        print("=" * 60)
        
        # Use the SAME suite loading system as pytest
        await self._load_suite_for_category(mapped_category)
        
        scenarios = self.runner.discover_scenarios(category=mapped_category)
        if not scenarios:
            print(f"❌ No scenarios found for category: {original_category} (mapped to: {mapped_category})")
            return False
        
        print(f"📋 Found {len(scenarios)} scenarios")
        
        results = await self.runner.run_scenarios(scenarios, **kwargs)
        
        # Print detailed results like pytest does
        self._print_detailed_test_results(results)
        
        # Save report
        report_path = self.runner.save_report(results)
        print(f"📄 Report saved to: {report_path}")
        
        return all(r.success for r in results)
    
    async def _load_suite_for_category(self, category: str):
        """Load the appropriate test suite for a category using the existing system."""
        try:
            from src.mcp_manager.core.simple_manager import SimpleMCPManager
            from tests.fixtures.dynamic_suite_loader import DynamicSuiteLoader
            import inspect
            
            # Create mock test instance to match the category (same as pytest)
            class MockTestInstance:
                def __init__(self, test_category):
                    self.category = test_category
                    self.__class__.__name__ = f"Test{test_category.title()}Tests"
                    
                    # Use the SAME file mapping as the existing system
                    file_mapping = {
                        'smoke': 'test_basic_commands.py',
                        'core': 'test_basic_commands.py',
                        'unit': 'test_basic_commands.py',
                        'server': 'test_server_management.py',
                        'integration': 'test_server_management.py',
                        'suite': 'test_suite_management.py',
                        'workflow': 'test_workflows.py',
                        'quality': 'test_quality_tracking.py',
                        'performance': 'test_quality_tracking.py',
                        'error': 'test_error_handling.py',
                        'regression': 'test_error_handling.py'
                    }
                    
                    # Mock the module to match expected patterns  
                    test_file = file_mapping.get(test_category, 'test_basic_commands.py')
                    # Create a proper mock module and assign it to sys.modules so inspect.getmodule works
                    import sys
                    module_name = f"tests.mock_{test_category}"
                    mock_module = type('MockModule', (), {
                        '__file__': f"/Users/jestes/mcp-manager/tests/{test_file}",
                        '__name__': module_name
                    })()
                    sys.modules[module_name] = mock_module
                    self.__class__.__module__ = module_name
                    
            # Initialize the SAME managers as pytest
            mcp_manager = SimpleMCPManager()
            suite_loader = DynamicSuiteLoader(mcp_manager)
            
            # Load suite using the SAME method as pytest
            mock_test = MockTestInstance(category)
            suite_data = await suite_loader.auto_load_suite_for_test(mock_test)
            
            if not suite_data:
                print(f"⚠️  No test suite found for category: {category}")
                
        except Exception as e:
            print(f"⚠️  Could not load test suite for {category}: {e}")
    
    def _print_detailed_test_results(self, results):
        """Print test results in the same format as pytest."""
        print("\n" + "=" * 80)
        
        for result in results:
            # Print each test with name and status (like pytest)
            status_color = "\033[32m" if result.success else "\033[91m"
            status_text = "PASSED" if result.success else "FAILED"
            reset_color = "\033[0m"
            
            print(f"{result.scenario_name} {status_color}{status_text}{reset_color}")
            
            if not result.success and result.error_message:
                print(f"   Error: {result.error_message}")
        
        # Print summary like pytest
        total = len(results)
        passed = sum(1 for r in results if r.success)
        failed = total - passed
        total_duration = sum(r.duration for r in results)
        
        summary_parts = []
        if passed > 0:
            summary_parts.append(f"\033[32m{passed} passed\033[0m")
        if failed > 0:
            summary_parts.append(f"\033[91m{failed} failed\033[0m")
        
        summary = ", ".join(summary_parts)
        print(f"\n\033[33m========================= {summary}\033[33m in {total_duration:.2f}s\033[0m")
    
    async def run_priority(self, priority: str, **kwargs) -> bool:
        """Run tests with specific priority."""
        print(f"\n🔥 Running {priority.upper()} Priority JSON Tests") 
        print("=" * 60)
        
        scenarios = self.runner.discover_scenarios(priority=priority)
        if not scenarios:
            print(f"❌ No scenarios found for priority: {priority}")
            return False
        
        print(f"📋 Found {len(scenarios)} scenarios")
        
        results = await self.runner.run_scenarios(scenarios, **kwargs)
        self.runner.print_summary(results)
        
        return all(r.success for r in results)
    
    async def run_categories(self, categories: List[str], **kwargs) -> bool:
        """Run tests in multiple categories."""
        if not categories:
            print("❌ No categories specified")
            return False
        
        print(f"\n🧪 Running Multiple Categories: {', '.join(cat.upper() for cat in categories)}")
        print("=" * 80)
        
        all_results = []
        overall_success = True
        
        for category in categories:
            print(f"\n📂 Processing category: {category.upper()}")
            print("-" * 40)
            
            mapped_category = self.map_category(category)
            
            # Load suite for this category (same as pytest)
            await self._load_suite_for_category(mapped_category)
            
            scenarios = self.runner.discover_scenarios(category=mapped_category)
            
            if not scenarios:
                print(f"⚠️  No scenarios found for category: {category}")
                continue
            
            print(f"📋 Found {len(scenarios)} scenarios for {category}")
            
            results = await self.runner.run_scenarios(scenarios, **kwargs)
            all_results.extend(results)
            
            category_success = all(r.success for r in results)
            if not category_success:
                overall_success = False
            
            status = "✅ PASSED" if category_success else "❌ FAILED"
            print(f"{status} Category {category.upper()}: {len([r for r in results if r.success])}/{len(results)} scenarios passed")
        
        # Print combined summary
        print(f"\n🎯 Multi-Category Execution Summary")
        print("=" * 60)
        total_scenarios = len(all_results)
        passed_scenarios = len([r for r in all_results if r.success])
        success_rate = (passed_scenarios / total_scenarios * 100) if total_scenarios > 0 else 0
        
        print(f"📊 Categories Executed: {len(categories)}")
        print(f"📊 Total Scenarios: {total_scenarios}")
        print(f"✅ Passed: {passed_scenarios}")
        print(f"❌ Failed: {total_scenarios - passed_scenarios}")
        print(f"📈 Overall Success Rate: {success_rate:.1f}%")
        
        # Save combined report
        if all_results:
            report_path = self.runner.save_report(all_results)
            print(f"📄 Combined report saved to: {report_path}")
        
        return overall_success
    
    async def run_smoke_tests(self, **kwargs) -> bool:
        """Run smoke tests."""
        print(f"\n💨 Running SMOKE Tests")
        print("=" * 60)
        
        # Run both smoke category and critical priority
        smoke_scenarios = self.runner.discover_scenarios(category="smoke")
        critical_scenarios = self.runner.discover_scenarios(priority="critical")
        
        # Combine and deduplicate
        all_smoke = {}
        for scenario in smoke_scenarios + critical_scenarios:
            all_smoke[scenario.id] = scenario
        
        scenarios = list(all_smoke.values())
        
        if not scenarios:
            print("❌ No smoke test scenarios found")
            return False
        
        print(f"📋 Found {len(scenarios)} smoke test scenarios")
        
        results = await self.runner.run_scenarios(scenarios, **kwargs)
        self.runner.print_summary(results)
        
        return all(r.success for r in results)
    
    async def run_all_tests(self, **kwargs) -> bool:
        """Run all available tests."""
        print(f"\n🎯 Running ALL JSON Tests")
        print("=" * 60)
        
        scenarios = self.runner.discover_scenarios()
        
        if not scenarios:
            print("❌ No scenarios found")
            return False
        
        print(f"📋 Found {len(scenarios)} total scenarios")
        
        # Group by category for reporting
        from tests.engine.scenario_parser import ScenarioParser
        parser = ScenarioParser()
        categories = parser.organize_scenarios_by_category(scenarios)
        
        print(f"📁 Categories: {', '.join(categories.keys())}")
        
        results = await self.runner.run_scenarios(scenarios, **kwargs)
        self.runner.print_summary(results)
        
        return all(r.success for r in results)
    
    def list_scenarios(self, category: Optional[str] = None, priority: Optional[str] = None):
        """List available scenarios."""
        print(f"\n📋 Available JSON Test Scenarios")
        print("=" * 60)
        
        scenarios = self.runner.discover_scenarios(category=category, priority=priority)
        
        if not scenarios:
            print("❌ No scenarios found matching criteria")
            return
        
        # Group by category
        from tests.engine.scenario_parser import ScenarioParser
        parser = ScenarioParser()
        categories = parser.organize_scenarios_by_category(scenarios)
        
        for cat, cat_scenarios in categories.items():
            print(f"\n📁 {cat.upper()} ({len(cat_scenarios)} scenarios)")
            for scenario in cat_scenarios[:5]:  # Show first 5
                priority_emoji = {"critical": "🔴", "high": "🟡", "medium": "🔵", "low": "⚪"}.get(scenario.priority, "⚪")
                print(f"   {priority_emoji} {scenario.name}")
                print(f"      ID: {scenario.id}")
                print(f"      Created by: {scenario.created_by}")
                if scenario.required_servers:
                    print(f"      Servers: {', '.join(scenario.required_servers)}")
            
            if len(cat_scenarios) > 5:
                print(f"   ... and {len(cat_scenarios) - 5} more scenarios")
        
        print(f"\n📊 Total: {len(scenarios)} scenarios")
    
    async def generate_scenario(self, description: str, **kwargs) -> bool:
        """Generate a new test scenario using AI."""
        print(f"\n🤖 Generating Test Scenario")
        print("=" * 60)
        print(f"Description: {description}")
        
        generator = AIScenarioGenerator()
        success, message, file_path = await generator.generate_and_save_scenario(
            description, **kwargs
        )
        
        if success:
            print(f"✅ {message}")
            print(f"📄 Saved to: {file_path}")
            
            # Validate it can be executed
            if file_path:
                scenario_data = generator.parser.load_scenario(file_path)
                if scenario_data:
                    print("🔍 Validating generated scenario...")
                    result = await self.runner.engine.execute_scenario(scenario_data)
                    if result.success:
                        print("✅ Generated scenario executed successfully")
                    else:
                        print(f"⚠️  Generated scenario failed execution: {result.error_message}")
        else:
            print(f"❌ {message}")
            return False
        
        return success

async def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="JSON Test Runner for MCP Manager",
        epilog="Examples:\n"
               "  %(prog)s smoke                    # Run smoke tests\n"
               "  %(prog)s --category core          # Run core tests\n"
               "  %(prog)s --priority high          # Run high priority tests\n"
               "  %(prog)s --list                   # List available scenarios\n"
               "  %(prog)s --generate 'Test filesystem operations'\n",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Test execution modes
    group = parser.add_mutually_exclusive_group()
    group.add_argument("categories", nargs="*", 
                      choices=["smoke", "unit", "server", "suite", "quality", "error", "workflow", "integration", "regression", "performance", "security", "core", "all"],
                      help="Test categories to run (can specify multiple)")
    group.add_argument("--priority", choices=["critical", "high", "medium", "low"],
                      help="Run tests with specific priority")
    group.add_argument("--list", action="store_true", help="List available scenarios")
    group.add_argument("--generate", help="Generate new scenario from description")
    
    # Filtering options
    parser.add_argument("--created-by", choices=["ai", "admin", "system", "migration"],
                       help="Filter by scenario creator")
    parser.add_argument("--tags", nargs="+", help="Filter by tags")
    
    # Execution options
    parser.add_argument("--batch-size", type=int, default=5, help="Scenarios per batch")
    parser.add_argument("--stop-on-failure", action="store_true", help="Stop on first failure")
    parser.add_argument("--timeout", type=int, default=300, help="Max execution time per batch")
    
    # AI generation options
    parser.add_argument("--ai-category", help="Category for AI-generated scenario")
    parser.add_argument("--ai-priority", help="Priority for AI-generated scenario")
    parser.add_argument("--ai-servers", nargs="+", help="Required servers for AI-generated scenario")
    
    args = parser.parse_args()
    
    cli = JsonTestRunnerCLI()
    
    # Execution options
    exec_kwargs = {
        "batch_size": args.batch_size,
        "stop_on_failure": args.stop_on_failure,
        "max_batch_duration": args.timeout
    }
    
    success = True
    
    try:
        if args.list:
            cli.list_scenarios(
                category=args.category,
                priority=args.priority
            )
        elif args.generate:
            ai_kwargs = {}
            if args.ai_category:
                ai_kwargs["category"] = args.ai_category
            if args.ai_priority:
                ai_kwargs["priority"] = args.ai_priority
            if args.ai_servers:
                ai_kwargs["required_servers"] = args.ai_servers
            
            success = await cli.generate_scenario(args.generate, **ai_kwargs)
        elif args.categories:
            if len(args.categories) == 1:
                category = args.categories[0]
                if category == "all":
                    success = await cli.run_all_tests(**exec_kwargs)
                else:
                    # Always use run_category to get proper suite loading
                    success = await cli.run_category(category, **exec_kwargs)
            else:
                # Multiple categories
                success = await cli.run_categories(args.categories, **exec_kwargs)
        elif args.priority:
            success = await cli.run_priority(args.priority, **exec_kwargs)
        else:
            # Default: run smoke tests using run_category for proper suite loading
            success = await cli.run_category("smoke", **exec_kwargs)
        
    except KeyboardInterrupt:
        print("\n⏹️  Test execution interrupted by user")
        success = False
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")
        success = False
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())