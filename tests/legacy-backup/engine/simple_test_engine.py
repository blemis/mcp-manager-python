#!/usr/bin/env python3
"""
Simple Test Engine for MCP Manager

Clean, straightforward test execution that actually works.
Executes collection-agnostic JSON test scenarios and validates results.
"""

import subprocess
import time
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path

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


class SimpleTestEngine:
    """Clean, simple test engine that actually executes commands and validates output."""
    
    def __init__(self):
        """Initialize the simple test engine."""
        self.results = []
    
    async def execute_test(self, test_data: Dict[str, Any]) -> TestResult:
        """
        Execute a single test scenario.
        
        Args:
            test_data: Collection-agnostic test scenario data
            
        Returns:
            TestResult with execution details
        """
        test_name = test_data.get('test_name', 'unknown_test')
        description = test_data.get('description', 'No description')
        command = test_data.get('command', '')
        expected_exit_code = test_data.get('expected_exit_code', 0) 
        expected_output = test_data.get('expected_output_contains', [])
        timeout = test_data.get('timeout', 30)
        
        logger.debug(f"🎯 Executing test: {test_name}")
        logger.debug(f"   Command: {command}")
        logger.debug(f"   Expected exit code: {expected_exit_code}")
        logger.debug(f"   Expected output contains: {expected_output}")
        
        start_time = time.time()
        
        try:
            # Execute the actual command
            result = subprocess.run(
                command.split(),
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=Path.cwd()
            )
            
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
                error_message = "; ".join(error_parts)
            
            return TestResult(
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
            return TestResult(
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
            return TestResult(
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
    
    async def execute_tests(self, test_scenarios: List[Dict[str, Any]], show_progress: bool = True) -> List[TestResult]:
        """
        Execute a list of test scenarios.
        
        Args:
            test_scenarios: List of collection-agnostic test scenarios
            show_progress: Whether to show progress indicators
            
        Returns:
            List of TestResults
        """
        results = []
        total_tests = len(test_scenarios)
        
        for i, test_data in enumerate(test_scenarios, 1):
            if show_progress:
                test_name = test_data.get('test_name', 'unknown_test')
                print(f"\r🔄 Running test {i}/{total_tests}: {test_name[:50]}...", end="", flush=True)
            
            result = await self.execute_test(test_data)
            results.append(result)
            
            if show_progress:
                status = "✅" if result.success else "❌"
                print(f"\r🔄 Test {i}/{total_tests}: {result.test_name[:50]} {status}", end="", flush=True)
        
        if show_progress:
            # Clear progress line
            print(f"\r{' ' * 80}", end="")
            print(f"\r", end="")
        
        self.results = results
        return results
    
    def print_results(self, results: Optional[List[TestResult]] = None):
        """Print test results in concise format."""
        if results is None:
            results = self.results
        
        if not results:
            print("📋 No test results to display")
            return
        
        print("\n🧪 Test Results")
        print("=" * 60)
        
        for result in results:
            status_icon = "✅" if result.success else "❌"
            status_text = "PASSED" if result.success else "FAILED"
            status_color = "\033[32m" if result.success else "\033[91m"
            
            print(f"{status_icon} {result.test_name:<30} {result.description:<40} {status_color}{status_text}\033[0m")
            
            # Show error details for failed tests
            if not result.success and result.error_message:
                print(f"   ❌ Error: {result.error_message}")
                if result.stderr:
                    print(f"   📝 Stderr: {result.stderr[:100]}...")
        
        # Print summary
        total = len(results)
        passed = sum(1 for r in results if r.success)
        failed = total - passed
        total_duration = sum(r.duration for r in results)
        
        print(f"\n\033[33m========================= \033[32m{passed} passed\033[0m", end="")
        if failed > 0:
            print(f", \033[91m{failed} failed\033[0m", end="")
        print(f"\033[33m in {total_duration:.2f}s\033[0m")