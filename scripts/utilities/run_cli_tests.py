#!/usr/bin/env python3
"""
Convenient CLI Test Runner for MCP Manager

This script provides an easy way to run the comprehensive CLI test suite
with various filtering and execution options.

Usage Examples:
    python run_cli_tests.py                    # Run all tests
    python run_cli_tests.py --category core    # Run core tests only
    python run_cli_tests.py --smoke            # Run smoke tests
    python run_cli_tests.py --critical         # Run critical priority tests
    python run_cli_tests.py --list             # List available tests
"""

import asyncio
import argparse
import sys
from pathlib import Path
from typing import List, Optional

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from tests.engine.json_test_runner import JsonTestRunner


def setup_argument_parser() -> argparse.ArgumentParser:
    """Set up command line argument parser."""
    parser = argparse.ArgumentParser(
        description="MCP Manager CLI Test Runner - Comprehensive test execution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Run all CLI tests
  %(prog)s --category core           # Run core command tests only
  %(prog)s --category suite          # Run suite management tests
  %(prog)s --priority critical       # Run critical priority tests only
  %(prog)s --smoke                   # Run smoke tests (quick validation)
  %(prog)s --list                    # List all available test scenarios
  %(prog)s --save-report results.json # Save detailed report to file

Test Categories:
  core         - Core CLI commands (list, add, remove, enable/disable)
  discovery    - Server discovery and package installation
  suite        - Suite management and server assignment
  ai_analytics - AI curation, analytics, tools, quality
  system       - System information and configuration
  interface    - Terminal user interfaces (TUI)
  api          - API server management
  proxy        - MCP proxy management
  workflow     - Workflow operations
  test_admin   - Administrative testing tools

Priorities:
  critical     - Must-pass tests for core functionality
  high         - Important feature tests
  medium       - Standard feature tests
  low          - Nice-to-have and admin tools
        """
    )
    
    # Test selection options
    selection_group = parser.add_argument_group('Test Selection')
    selection_group.add_argument(
        '--category', 
        help='Run tests in specific category (core, discovery, suite, etc.)'
    )
    selection_group.add_argument(
        '--priority', 
        choices=['critical', 'high', 'medium', 'low'],
        help='Run tests with specific priority level'
    )
    selection_group.add_argument(
        '--tag', 
        action='append',
        help='Run tests with specific tags (can be used multiple times)'
    )
    selection_group.add_argument(
        '--smoke', 
        action='store_true',
        help='Run smoke tests only (quick validation)'
    )
    
    # Execution options
    execution_group = parser.add_argument_group('Execution Options')
    execution_group.add_argument(
        '--batch-size', 
        type=int, 
        default=5,
        help='Number of tests to run in parallel (default: 5)'
    )
    execution_group.add_argument(
        '--stop-on-failure', 
        action='store_true',
        help='Stop execution on first test failure'
    )
    execution_group.add_argument(
        '--timeout-multiplier',
        type=float,
        default=1.0,
        help='Multiply all test timeouts by this factor (default: 1.0)'
    )
    
    # Output options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument(
        '--list', 
        action='store_true',
        help='List all available test scenarios and exit'
    )
    output_group.add_argument(
        '--save-report', 
        metavar='PATH',
        help='Save detailed test report to specified file'
    )
    output_group.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    output_group.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Minimize output (only show summary)'
    )
    
    # Development options
    dev_group = parser.add_argument_group('Development Options')
    dev_group.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what tests would run without executing them'
    )
    dev_group.add_argument(
        '--init-db',
        action='store_true',
        help='Initialize database before running tests'
    )
    
    return parser


def print_test_summary(categories: dict, total_scenarios: int):
    """Print a summary of available tests."""
    print(f"\n📊 MCP Manager CLI Test Suite Summary")
    print(f"{'='*60}")
    print(f"📋 Total Test Scenarios: {total_scenarios}")
    print(f"📁 Test Categories: {len(categories)}")
    print(f"\n📂 Tests by Category:")
    
    for category, scenarios in categories.items():
        count = len(scenarios)
        priority_counts = {}
        for scenario in scenarios:
            priority = scenario.get('scenario', {}).get('priority', 'medium')
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        priority_str = ', '.join([f"{p}: {c}" for p, c in priority_counts.items()])
        print(f"   📁 {category.ljust(15)} {str(count).rjust(3)} tests ({priority_str})")


async def main():
    """Main CLI test runner."""
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    # Initialize test runner with CLI test scenarios
    scenarios_root = Path(__file__).parent / "tests" / "scenarios" / "cli_tests"
    runner = JsonTestRunner(scenarios_root)
    
    # Initialize database if requested
    if args.init_db:
        print("🚀 Initializing database...")
        import subprocess
        result = subprocess.run([sys.executable, "quick_init.py"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Database initialized successfully")
        else:
            print(f"❌ Database initialization failed: {result.stderr}")
            return 1
    
    # List available scenarios if requested
    if args.list:
        print("🔍 Discovering available test scenarios...")
        scenarios = runner.discover_scenarios()
        
        if not scenarios:
            print("❌ No test scenarios found")
            print("💡 Make sure the database is initialized with: python quick_init.py")
            return 1
        
        categories = runner.parser.organize_scenarios_by_category(scenarios)
        print_test_summary(categories, len(scenarios))
        runner.list_available_scenarios()
        return 0
    
    # Discover scenarios based on filters
    print("🔍 Discovering test scenarios...")
    scenarios = runner.discover_scenarios(
        category=args.category,
        priority=args.priority,
        tags=args.tag
    )
    
    if not scenarios:
        print("❌ No test scenarios found matching criteria")
        print("💡 Use --list to see available scenarios")
        return 1
    
    print(f"📋 Found {len(scenarios)} test scenarios")
    
    # Handle dry run
    if args.dry_run:
        print(f"\n🔍 Dry Run - Would execute {len(scenarios)} scenarios:")
        for i, scenario in enumerate(scenarios, 1):
            scenario_info = scenario.get('scenario', {})
            name = scenario_info.get('name', 'Unknown')
            category = scenario_info.get('category', 'unknown')
            priority = scenario_info.get('priority', 'medium')
            print(f"   {i:2d}. {name} [{category}/{priority}]")
        return 0
    
    # Execute the test scenarios
    try:
        if args.smoke:
            print("🏃‍♂️ Running smoke tests...")
            results = await runner.run_smoke_tests(
                batch_size=args.batch_size,
                stop_on_failure=args.stop_on_failure
            )
        elif args.category:
            print(f"🎯 Running {args.category} category tests...")
            results = await runner.run_category(
                args.category,
                batch_size=args.batch_size,
                stop_on_failure=args.stop_on_failure
            )
        elif args.priority:
            print(f"🔥 Running {args.priority} priority tests...")
            results = await runner.run_by_priority(
                args.priority,
                batch_size=args.batch_size,
                stop_on_failure=args.stop_on_failure
            )
        else:
            print("🚀 Running all discovered test scenarios...")
            results = await runner.run_scenarios(
                scenarios,
                batch_size=args.batch_size,
                stop_on_failure=args.stop_on_failure
            )
        
        # Print results based on verbosity
        if not args.quiet:
            if args.verbose:
                runner.print_detailed_results(results)
            else:
                runner.print_summary(results)
        
        # Save report if requested
        if args.save_report:
            report_path = runner.save_report(results, Path(args.save_report))
            print(f"📄 Detailed report saved to: {report_path}")
        
        # Return appropriate exit code
        if results and all(r.success for r in results):
            print("\n🎉 All tests passed!")
            return 0
        else:
            failed_count = sum(1 for r in results if not r.success)
            print(f"\n❌ {failed_count} test(s) failed!")
            return 1
            
    except KeyboardInterrupt:
        print("\n🛑 Test execution interrupted by user")
        return 130
    except Exception as e:
        print(f"\n💥 Test execution failed with error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)