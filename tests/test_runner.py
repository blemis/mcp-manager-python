#!/usr/bin/env python3
"""
Professional test runner for MCP Manager.

Master SRE-level test execution with comprehensive reporting.
Run different test categories with proper configuration and reporting.
"""

import sys
import subprocess
import argparse
import time
from pathlib import Path
from typing import List, Dict, Any, Optional


class ProfessionalTestRunner:
    """Professional test runner with comprehensive reporting."""
    
    def __init__(self):
        self.start_time = time.time()
        self.results = {}
        
    def run_test_category(self, category: str, files: Optional[List[str]] = None, 
                         markers: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Run a specific test category with professional reporting.
        
        Args:
            category: Test category name
            files: Specific test files to run
            markers: Pytest markers to filter tests
            
        Returns:
            Test results dictionary
        """
        print(f"\n🧪 Running {category.upper()} Tests")
        print("=" * 60)
        
        # Build pytest command
        cmd = ["python", "-m", "pytest"]
        
        # Add files or default test pattern
        if files:
            cmd.extend(files)
            print(f"📁 Test Files: {', '.join(files)}")
        else:
            cmd.append("tests/")
            print(f"📁 Test Pattern: tests/")
        
        # Add markers
        if markers:
            for marker in markers:
                cmd.extend(["-m", marker])
            print(f"🏷️  Markers: {', '.join(markers)}")
        
        # Add reporting options
        cmd.extend([
            "--verbose",
            "--tb=short",
            "--durations=10",
            f"--junitxml=test-results-{category.lower().replace(' ', '-')}.xml",
            "--color=yes",
            "-s"  # Don't capture output, show prints in real-time
        ])
        
        print(f"🚀 Command: {' '.join(cmd)}")
        print("-" * 60)
        
        # Run tests with live output
        start_time = time.time()
        try:
            # Use Popen for real-time output streaming
            import subprocess
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            stdout_lines = []
            
            # Stream output in real-time
            for line in iter(process.stdout.readline, ''):
                print(line, end='')  # Show live output
                stdout_lines.append(line)
            
            process.wait(timeout=1800)  # 30 minute timeout
            stdout = ''.join(stdout_lines)
            
            duration = time.time() - start_time
            
            print(f"\n⏱️  {category} completed in {duration:.1f}s")
            
            return {
                'category': category,
                'success': process.returncode == 0,
                'returncode': process.returncode,
                'duration': duration,
                'stdout': stdout,
                'stderr': '',
                'command': ' '.join(cmd)
            }
            
        except subprocess.TimeoutExpired:
            if 'process' in locals():
                process.kill()
            return {
                'category': category,
                'success': False,
                'returncode': -1,
                'duration': time.time() - start_time,
                'error': 'timeout',
                'command': ' '.join(cmd)
            }
        except Exception as e:
            return {
                'category': category,
                'success': False,
                'returncode': -2,
                'duration': time.time() - start_time,
                'error': str(e),
                'command': ' '.join(cmd)
            }
    
    def run_smoke_tests(self) -> Dict[str, Any]:
        """Run critical smoke tests."""
        return self.run_test_category(
            "Smoke Tests",
            files=["tests/test_basic_commands.py::TestSmokeTests"],
            markers=["smoke"]
        )
    
    def run_unit_tests(self) -> Dict[str, Any]:
        """Run fast unit tests."""
        return self.run_test_category(
            "Unit Tests",
            files=[
                "tests/test_basic_commands.py::TestBasicCommands",
                "tests/test_basic_commands.py::TestDiscoveryCommands",
                "tests/test_basic_commands.py::TestSystemInformation"
            ],
            markers=["unit"]
        )
    
    def run_server_tests(self) -> Dict[str, Any]:
        """Run server management tests."""
        return self.run_test_category(
            "Server Management",
            files=["tests/test_server_management.py"]
        )
    
    def run_suite_tests(self) -> Dict[str, Any]:
        """Run suite management tests (including critical bug tests)."""
        return self.run_test_category(
            "Suite Management",
            files=["tests/test_suite_management.py"]
        )
    
    def run_quality_tests(self) -> Dict[str, Any]:
        """Run quality tracking tests."""
        return self.run_test_category(
            "Quality Tracking",
            files=["tests/test_quality_tracking.py"]
        )
    
    def run_error_tests(self) -> Dict[str, Any]:
        """Run error handling and edge case tests."""
        return self.run_test_category(
            "Error Handling",
            files=["tests/test_error_handling.py"]
        )
    
    def run_workflow_tests(self) -> Dict[str, Any]:
        """Run complete workflow tests."""
        return self.run_test_category(
            "User Workflows",
            files=["tests/test_workflows.py"]
        )
    
    def run_integration_tests(self) -> Dict[str, Any]:
        """Run integration tests."""
        return self.run_test_category(
            "Integration Tests",
            markers=["integration"]
        )
    
    def run_regression_tests(self) -> Dict[str, Any]:
        """Run regression tests for known bugs."""
        return self.run_test_category(
            "Regression Tests",
            markers=["regression"]
        )
    
    def run_all_tests(self) -> List[Dict[str, Any]]:
        """Run all test categories in the recommended order."""
        print("🚀 COMPREHENSIVE MCP MANAGER TEST SUITE")
        print("Professional SRE-level testing with 100+ test combinations")
        print("=" * 80)
        
        # Test execution order (smoke tests first, slow tests last)
        test_categories = [
            ("Smoke Tests", self.run_smoke_tests),
            ("Unit Tests", self.run_unit_tests),
            ("Server Management", self.run_server_tests),
            ("Suite Management", self.run_suite_tests),
            ("Quality Tracking", self.run_quality_tests),
            ("Error Handling", self.run_error_tests),
            ("Regression Tests", self.run_regression_tests),
            ("Integration Tests", self.run_integration_tests),
            ("User Workflows", self.run_workflow_tests)
        ]
        
        results = []
        total_categories = len(test_categories)
        
        for i, (category_name, test_func) in enumerate(test_categories, 1):
            print(f"\n📋 [{i}/{total_categories}] {category_name}")
            print("-" * 60)
            
            # Show progress and what we're about to test
            remaining = total_categories - i
            print(f"🎯 Progress: {i}/{total_categories} ({(i/total_categories)*100:.0f}%) | {remaining} remaining")
            
            try:
                print(f"🔄 Starting {category_name}...")
                result = test_func()
                results.append(result)
                
                # Show immediate results with more context
                if result['success']:
                    print(f"\n✅ {category_name}: PASSED ({result['duration']:.1f}s)")
                    print(f"   All tests in this category completed successfully")
                else:
                    print(f"\n❌ {category_name}: FAILED ({result['duration']:.1f}s)")
                    print(f"   Return code: {result['returncode']}")
                    if 'error' in result:
                        print(f"   Error: {result['error']}")
                    else:
                        print(f"   Some tests failed - check detailed output above")
                
                # Show cumulative progress
                passed_so_far = sum(1 for r in results if r['success'])
                print(f"📊 Running Total: {passed_so_far}/{i} categories passed so far")
                
            except Exception as e:
                print(f"💥 {category_name}: CRASHED ({str(e)})")
                results.append({
                    'category': category_name,
                    'success': False,
                    'error': f'Test category crashed: {str(e)}',
                    'duration': 0
                })
            
            # Add separator between categories for clarity
            if i < total_categories:
                print(f"\n{'='*80}")
                print(f"🔄 Moving to next category...")
                print(f"{'='*80}")
        
        return results
    
    def generate_report(self, results: List[Dict[str, Any]]) -> None:
        """Generate comprehensive test report."""
        total_time = time.time() - self.start_time
        
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE TEST RESULTS")
        print("=" * 80)
        
        # Summary statistics
        total_categories = len(results)
        passed_categories = sum(1 for r in results if r['success'])
        failed_categories = total_categories - passed_categories
        success_rate = (passed_categories / total_categories * 100) if total_categories > 0 else 0
        
        print(f"📈 Overall Statistics:")
        print(f"   Total Categories: {total_categories}")
        print(f"   Passed: {passed_categories}")
        print(f"   Failed: {failed_categories}")
        print(f"   Success Rate: {success_rate:.1f}%")
        print(f"   Total Time: {total_time:.1f}s")
        
        # Detailed results
        print(f"\n📋 Detailed Results:")
        for result in results:
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            duration = result.get('duration', 0)
            category = result['category']
            
            print(f"   {status} {category:20} ({duration:5.1f}s)")
            
            if not result['success']:
                if 'error' in result:
                    print(f"      Error: {result['error']}")
                elif result.get('returncode', 0) != 0:
                    print(f"      Exit code: {result['returncode']}")
        
        # Critical issues
        critical_failures = [r for r in results if not r['success'] and 'smoke' in r.get('category', '').lower()]
        if critical_failures:
            print(f"\n🚨 CRITICAL FAILURES:")
            for failure in critical_failures:
                print(f"   - {failure['category']}: {failure.get('error', 'Failed')}")
        
        # Performance insights
        slow_categories = [r for r in results if r.get('duration', 0) > 60]
        if slow_categories:
            print(f"\n⏱️  PERFORMANCE NOTES:")
            for slow in slow_categories:
                print(f"   - {slow['category']}: {slow['duration']:.1f}s (consider optimization)")
        
        # Final assessment
        print(f"\n" + "=" * 80)
        if failed_categories == 0:
            print("🎉 ALL TESTS PASSED!")
            print("MCP Manager is working flawlessly across all user scenarios")
            print("Ready for production deployment ✨")
        elif critical_failures:
            print("🚨 CRITICAL ISSUES FOUND!")
            print("Core functionality is broken - immediate attention required")
            print("DO NOT DEPLOY until critical issues are resolved")
        else:
            print(f"⚠️  {failed_categories} NON-CRITICAL ISSUES FOUND")
            print("Core functionality works but some edge cases need attention")
            print("Review failed tests and fix issues for production readiness")
        
        print("=" * 80)
        
        # Save results to file
        import json
        with open('test-results-summary.json', 'w') as f:
            json.dump({
                'total_time': total_time,
                'total_categories': total_categories,
                'passed_categories': passed_categories,
                'failed_categories': failed_categories,
                'success_rate': success_rate,
                'results': results
            }, f, indent=2)
        
        print("📁 Detailed results saved to: test-results-summary.json")
        print("📄 Individual XML reports: test-results-*.xml")
        print()
        print("🔗 Share these files:")
        print(f"   📊 Summary: {Path.cwd()}/test-results-summary.json")
        for result in results:
            category_safe = result['category'].lower().replace(' ', '-')
            xml_file = f"test-results-{category_safe}.xml"
            if Path(xml_file).exists():
                print(f"   📄 {result['category']}: {Path.cwd()}/{xml_file}")


def main():
    """Main test runner entry point."""
    parser = argparse.ArgumentParser(
        description="Professional MCP Manager Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Test Categories:
  smoke       - Critical functionality that must work
  unit        - Fast isolated tests  
  server      - Server management functionality
  suite       - Suite management (includes critical bug tests)
  quality     - Quality tracking system
  error       - Error handling and edge cases
  workflow    - Complete user workflows
  integration - Component integration tests
  regression  - Known bug prevention tests
  all         - Run all test categories (recommended)

Examples:
  python tests/test_runner.py smoke                    # Quick smoke test
  python tests/test_runner.py suite                   # Test suite functionality
  python tests/test_runner.py all                     # Full comprehensive testing
  python tests/test_runner.py server quality          # Multiple categories
        """
    )
    
    parser.add_argument(
        'categories',
        nargs='*',
        default=['all'],
        choices=['smoke', 'unit', 'server', 'suite', 'quality', 'error', 
                'workflow', 'integration', 'regression', 'all'],
        help='Test categories to run (default: all)'
    )
    
    parser.add_argument(
        '--no-report',
        action='store_true',
        help='Skip comprehensive report generation'
    )
    
    args = parser.parse_args()
    
    runner = ProfessionalTestRunner()
    
    if 'all' in args.categories:
        # Run comprehensive test suite
        results = runner.run_all_tests()
    else:
        # Run specific categories
        results = []
        category_map = {
            'smoke': runner.run_smoke_tests,
            'unit': runner.run_unit_tests,
            'server': runner.run_server_tests,
            'suite': runner.run_suite_tests,
            'quality': runner.run_quality_tests,
            'error': runner.run_error_tests,
            'workflow': runner.run_workflow_tests,
            'integration': runner.run_integration_tests,
            'regression': runner.run_regression_tests
        }
        
        for category in args.categories:
            if category in category_map:
                print(f"\n🧪 Running {category.upper()} tests...")
                result = category_map[category]()
                results.append(result)
    
    # Generate report
    if not args.no_report:
        runner.generate_report(results)
    
    # Exit with appropriate code
    failed_tests = sum(1 for r in results if not r['success'])
    sys.exit(0 if failed_tests == 0 else 1)


if __name__ == "__main__":
    main()