#!/usr/bin/env python3
"""
Clean Test Runner for MCP Manager

Simple, reliable test execution that actually works.
Uses collection-agnostic JSON tests and validates real command output.
"""

import subprocess
import time
import json
import sys
import shlex
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass 
class TestResult:
    """Simple test result with clear pass/fail status."""
    test_name: str
    description: str
    command: str
    success: bool
    duration: float
    exit_code: int
    stdout: str
    stderr: str
    expected_exit_code: int
    expected_output: List[str]
    missing_output: List[str] = None
    error_message: str = None


class TestRunner:
    """Clean, simple test runner that actually executes commands and validates output."""
    
    def __init__(self):
        """Initialize the test runner."""
        self.results = []
        self.tests_dir = Path(__file__).parent / "scenarios" / "cli_tests"
    
    def load_test_file(self, filename: str) -> Dict[str, Any]:
        """Load a JSON test file."""
        file_path = self.tests_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"Test file not found: {filename}")
        
        with open(file_path, 'r') as f:
            return json.load(f)
    
    def get_available_categories(self) -> Dict[str, Dict]:
        """Get all available test categories from JSON files."""
        categories = {}
        
        # Scan all JSON test files
        for json_file in self.tests_dir.glob("*.json"):
            if json_file.name == "master_test_config.json":
                continue
                
            try:
                with open(json_file, 'r') as f:
                    test_data = json.load(f)
                
                category = test_data.get('category', 'unknown')
                name = test_data.get('test_suite_name', category.title())
                description = test_data.get('test_suite_description', f'Tests for {name}')
                priority = test_data.get('priority', 'medium')
                test_count = len(test_data.get('test_scenarios', []))
                
                categories[category] = {
                    'name': name,
                    'description': description,
                    'priority': priority,
                    'test_count': test_count,
                    'file': json_file.name
                }
            except Exception as e:
                logger.warning(f"Failed to load test file {json_file.name}: {e}")
        
        return categories
    
    def execute_command(self, command: str, timeout: int = 30) -> subprocess.CompletedProcess:
        """Execute a single command with proper shell handling."""
        # Check if command contains shell operators
        if any(op in command for op in ['&&', '||', '|', ';', '>', '<']):
            # Use shell=True for commands with shell operators
            return subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=project_root
            )
        else:
            # Use shlex.split() for simple commands to handle quoting properly
            return subprocess.run(
                shlex.split(command),
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=project_root
            )
    
    def execute_test(self, test_data: Dict[str, Any]) -> TestResult:
        """Execute a single test scenario with setup and cleanup."""
        test_name = test_data.get('test_name', 'unknown_test')
        description = test_data.get('description', 'No description')
        command = test_data.get('command', '')
        expected_exit_code = test_data.get('expected_exit_code', 0) 
        expected_output = test_data.get('expected_output_contains', [])
        timeout = test_data.get('timeout', 30)
        setup_commands = test_data.get('setup_commands', [])
        cleanup_commands = test_data.get('cleanup_commands', [])
        
        logger.debug(f"🎯 Executing test: {test_name}")
        
        # Execute setup commands
        for setup_cmd in setup_commands:
            logger.debug(f"🔧 Setup: {setup_cmd}")
            try:
                self.execute_command(setup_cmd, timeout)
            except Exception as e:
                logger.warning(f"Setup command failed: {setup_cmd} - {e}")
        
        start_time = time.time()
        
        try:
            # Execute the actual test command
            result = self.execute_command(command, timeout)
            
            duration = time.time() - start_time
            exit_code = result.returncode
            stdout = result.stdout
            stderr = result.stderr
            
            # Validate exit code
            exit_code_valid = (exit_code == expected_exit_code)
            
            # Validate output contains expected strings
            missing_output = []
            for expected_text in expected_output:
                if expected_text not in stdout:
                    missing_output.append(expected_text)
            
            output_valid = len(missing_output) == 0
            
            # Overall success
            success = exit_code_valid and output_valid
            
            # Build error message if failed
            error_message = None
            if not success:
                error_parts = []
                if not exit_code_valid:
                    error_parts.append(f"Exit code {exit_code} != expected {expected_exit_code}")
                if not output_valid:
                    error_parts.append(f"Missing output: {missing_output}")
                if stderr:
                    error_parts.append(f"Stderr: {stderr[:200]}")
                error_message = "; ".join(error_parts)
            
            result_obj = TestResult(
                test_name=test_name,
                description=description,
                command=command,
                success=success,
                duration=duration,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                expected_exit_code=expected_exit_code,
                expected_output=expected_output,
                missing_output=missing_output,
                error_message=error_message
            )
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            result_obj = TestResult(
                test_name=test_name,
                description=description,
                command=command,
                success=False,
                duration=duration,
                exit_code=-1,
                stdout="",
                stderr="",
                expected_exit_code=expected_exit_code,
                expected_output=expected_output,
                missing_output=expected_output,
                error_message=f"Command timed out after {timeout}s"
            )
            
        except Exception as e:
            duration = time.time() - start_time
            result_obj = TestResult(
                test_name=test_name,
                description=description,
                command=command,
                success=False,
                duration=duration,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                expected_exit_code=expected_exit_code,
                expected_output=expected_output,
                missing_output=expected_output,
                error_message=f"Execution failed: {e}"
            )
        
        # Execute cleanup commands regardless of test outcome
        for cleanup_cmd in cleanup_commands:
            logger.debug(f"🧹 Cleanup: {cleanup_cmd}")
            try:
                self.execute_command(cleanup_cmd, timeout)
            except Exception as e:
                logger.warning(f"Cleanup command failed: {cleanup_cmd} - {e}")
        
        return result_obj
    
    def run_category(self, category: str, show_progress: bool = True) -> List[TestResult]:
        """Run all tests in a category."""
        categories = self.get_available_categories()
        
        if category not in categories:
            # Try to find by name match
            for cat_key, cat_data in categories.items():
                if category.lower() in cat_key.lower():
                    category = cat_key
                    break
            else:
                raise ValueError(f"Category '{category}' not found. Available: {list(categories.keys())}")
        
        # Store category for reporting
        self._last_category = category
        
        # Load the test file
        filename = categories[category]['file']
        test_data = self.load_test_file(filename)
        test_scenarios = test_data.get('test_scenarios', [])
        
        if not test_scenarios:
            logger.warning(f"No test scenarios found in {filename}")
            return []
        
        print(f"\n🧪 Running {category.upper()} Tests")
        print("=" * 60)
        print(f"📋 Found {len(test_scenarios)} scenarios")
        
        results = []
        
        for i, scenario in enumerate(test_scenarios, 1):
            if show_progress:
                test_name = scenario.get('test_name', 'unknown_test')
                print(f"\r🔄 Running test {i}/{len(test_scenarios)}: {test_name[:50]}...", end="", flush=True)
            
            result = self.execute_test(scenario)
            results.append(result)
            
            if show_progress:
                status = "✅" if result.success else "❌"
                print(f"\r🔄 Test {i}/{len(test_scenarios)}: {result.test_name[:50]} {status}", end="", flush=True)
        
        if show_progress:
            # Clear progress line
            print(f"\r{' ' * 80}", end="")
            print(f"\r", end="")
        
        self.results = results
        return results
    
    def save_detailed_report(self, results: Optional[List[TestResult]] = None, output_file: str = None):
        """Save detailed test results to file for debugging."""
        if results is None:
            results = self.results
        
        if not results:
            return None
        
        # Generate filename if not provided
        if not output_file:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            category = getattr(self, '_last_category', 'unknown')
            output_file = f"tests/results/test_failures_{category}_{timestamp}.json"
        
        # Ensure results directory exists
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        
        # Build detailed report
        failed_tests = [r for r in results if not r.success]
        
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "category": getattr(self, '_last_category', 'unknown'),
            "summary": {
                "total_tests": len(results),
                "passed": sum(1 for r in results if r.success),
                "failed": len(failed_tests),
                "success_rate": f"{(sum(1 for r in results if r.success) / len(results) * 100):.1f}%",
                "total_duration": f"{sum(r.duration for r in results):.2f}s"
            },
            "failed_tests": [],
            "all_results": []
        }
        
        # Add detailed failure information
        for result in failed_tests:
            failure_detail = {
                "test_name": result.test_name,
                "description": result.description,
                "command": result.command,
                "error_message": result.error_message,
                "exit_code": result.exit_code,
                "expected_exit_code": result.expected_exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "expected_output": result.expected_output,
                "missing_output": result.missing_output,
                "duration": result.duration
            }
            report["failed_tests"].append(failure_detail)
        
        # Add all results for complete picture
        for result in results:
            test_detail = {
                "test_name": result.test_name,
                "description": result.description,
                "command": result.command,
                "success": result.success,
                "exit_code": result.exit_code,
                "expected_exit_code": result.expected_exit_code,
                "duration": result.duration,
                "error_message": result.error_message if not result.success else None
            }
            report["all_results"].append(test_detail)
        
        # Save to file
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        return output_file
    
    def print_results(self, results: Optional[List[TestResult]] = None):
        """Print test results in concise format."""
        if results is None:
            results = self.results
        
        if not results:
            print("📋 No test results to display")
            return
        
        print("\n" + "=" * 80)
        
        for result in results:
            status_icon = "✅" if result.success else "❌"
            status_text = "PASSED" if result.success else "FAILED"
            status_color = "\033[32m" if result.success else "\033[91m"
            
            print(f"{status_icon} {result.test_name:<30} {result.description:<40} {status_color}{status_text}\033[0m")
            
            # Show error details for failed tests
            if not result.success and result.error_message:
                print(f"   ❌ Error: {result.error_message}")
        
        # Print summary
        total = len(results)
        passed = sum(1 for r in results if r.success)
        failed = total - passed
        total_duration = sum(r.duration for r in results)
        
        print(f"\n\033[33m========================= \033[32m{passed} passed\033[0m", end="")
        if failed > 0:
            print(f", \033[91m{failed} failed\033[0m", end="")
        print(f"\033[33m in {total_duration:.2f}s\033[0m")
        
        # Save detailed report if there are failures
        if failed > 0:
            report_file = self.save_detailed_report(results)
            print(f"\n📄 Detailed failure report saved to: {report_file}")
            print(f"💡 Use this file to report bugs for fixing")
    
    def print_failure_summary(self, results: Optional[List[TestResult]] = None):
        """Print a focused summary of just the failures for easy copy-paste."""
        if results is None:
            results = self.results
        
        failed_tests = [r for r in results if not r.success]
        if not failed_tests:
            print("✅ No failures to report!")
            return
        
        print(f"\n🚨 FAILURE SUMMARY ({len(failed_tests)} failed tests):")
        print("=" * 60)
        
        for i, result in enumerate(failed_tests, 1):
            print(f"\n{i}. TEST: {result.test_name}")
            print(f"   Command: {result.command}")
            print(f"   Expected: Exit code {result.expected_exit_code}")
            print(f"   Actual: Exit code {result.exit_code}")
            
            if result.missing_output:
                print(f"   Missing output: {result.missing_output}")
            
            if result.stderr:
                print(f"   Error: {result.stderr[:200]}...")
        
        print(f"\n📋 Copy this summary to report {len(failed_tests)} bugs that need fixing.")


def main():
    """CLI interface for the test runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP Manager Test Runner")
    parser.add_argument('category', nargs='?', help='Test category to run')
    parser.add_argument('--list', action='store_true', help='List available categories')
    parser.add_argument('--summary', action='store_true', help='Show only failure summary for bug reporting')
    parser.add_argument('--save-report', metavar='FILE', help='Save detailed report to specific file')
    
    args = parser.parse_args()
    
    runner = TestRunner()
    
    if args.list:
        categories = runner.get_available_categories()
        print("📂 Available Test Categories:")
        for key, data in categories.items():
            print(f"   {key}: {data['name']} ({data['test_count']} tests)")
        return
    
    if not args.category:
        parser.print_help()
        return
    
    try:
        results = runner.run_category(args.category)
        
        if args.summary:
            # Show only failure summary for easy bug reporting
            runner.print_failure_summary(results)
        else:
            # Show full results
            runner.print_results(results)
        
        # Save custom report if requested
        if args.save_report:
            report_file = runner.save_detailed_report(results, args.save_report)
            print(f"\n📄 Detailed report saved to: {report_file}")
        
        # Exit with error code if any tests failed
        if any(not r.success for r in results):
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()