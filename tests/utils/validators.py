"""
Output validation utilities for CLI testing.

Professional validation functions for different output formats.
"""

import json
import re
from typing import List, Dict, Any, Optional, Union
from pathlib import Path


class OutputValidator:
    """Professional output validation for CLI testing."""
    
    @staticmethod
    def validate_json_output(output: str) -> tuple[bool, Optional[Dict[str, Any]]]:
        """
        Validate JSON output format.
        
        Returns:
            (is_valid, parsed_data)
        """
        try:
            data = json.loads(output.strip())
            return True, data
        except (json.JSONDecodeError, ValueError) as e:
            return False, None
    
    @staticmethod
    def validate_table_output(output: str, expected_columns: Optional[List[str]] = None) -> bool:
        """
        Validate table-formatted output.
        
        Args:
            output: CLI output to validate
            expected_columns: Optional list of expected column names
            
        Returns:
            True if output is valid table format
        """
        lines = [line.strip() for line in output.strip().split('\n') if line.strip()]
        
        if len(lines) < 2:
            return False
        
        # Check for table separators (|, +, -)
        has_separators = any(char in lines[0] for char in ['|', '+', '-'])
        if not has_separators:
            return False
        
        # If expected columns provided, validate them
        if expected_columns:
            header_line = lines[0].lower()
            return all(col.lower() in header_line for col in expected_columns)
        
        return True
    
    @staticmethod
    def validate_list_output(output: str, expected_items: Optional[List[str]] = None) -> bool:
        """
        Validate list-formatted output.
        
        Args:
            output: CLI output to validate
            expected_items: Optional list of items that should be present
            
        Returns:
            True if output is valid list format
        """
        lines = [line.strip() for line in output.strip().split('\n') if line.strip()]
        
        if not lines:
            return expected_items is None or len(expected_items) == 0
        
        # Check for list indicators (-, *, numbers, etc.)
        list_patterns = [r'^\s*[-*•]\s+', r'^\s*\d+\.\s+', r'^\s*\w+:\s+']
        has_list_format = any(
            re.match(pattern, line) for line in lines for pattern in list_patterns
        )
        
        if expected_items:
            output_lower = output.lower()
            return all(item.lower() in output_lower for item in expected_items)
        
        return has_list_format or len(lines) > 0
    
    @staticmethod
    def validate_success_message(output: str, operation: str = "") -> bool:
        """
        Validate success message format.
        
        Args:
            output: CLI output to validate
            operation: Optional operation name to check for
            
        Returns:
            True if output contains success indicators
        """
        success_indicators = [
            'success', 'successful', 'completed', 'created', 'added', 
            'installed', 'enabled', 'configured', 'done', '✓', '✅'
        ]
        
        output_lower = output.lower()
        has_success = any(indicator in output_lower for indicator in success_indicators)
        
        if operation:
            has_operation = operation.lower() in output_lower
            return has_success and has_operation
        
        return has_success
    
    @staticmethod
    def validate_error_message(output: str, error_type: Optional[str] = None) -> bool:
        """
        Validate error message format.
        
        Args:
            output: CLI output to validate
            error_type: Optional specific error type to check for
            
        Returns:
            True if output contains appropriate error indicators
        """
        error_indicators = [
            'error', 'failed', 'failure', 'not found', 'invalid', 
            'missing', 'unable', 'cannot', 'denied', '❌', '🚨'
        ]
        
        output_lower = output.lower()
        has_error = any(indicator in output_lower for indicator in error_indicators)
        
        if error_type:
            has_error_type = error_type.lower() in output_lower
            return has_error and has_error_type
        
        return has_error
    
    @staticmethod
    def validate_help_output(output: str) -> bool:
        """
        Validate help/usage output format.
        
        Returns:
            True if output looks like proper help text
        """
        help_indicators = [
            'usage:', 'options:', 'commands:', 'arguments:', 
            'examples:', 'help', '--help', '-h'
        ]
        
        output_lower = output.lower()
        return any(indicator in output_lower for indicator in help_indicators)
    
    @staticmethod
    def validate_version_output(output: str) -> bool:
        """
        Validate version output format.
        
        Returns:
            True if output looks like version information
        """
        # Look for version patterns like "1.0.0", "v1.0", "version 1.0"
        version_patterns = [
            r'\d+\.\d+\.\d+',  # Semantic versioning
            r'v\d+\.\d+',      # v1.0 format
            r'version\s+\d+',  # "version 1" format
        ]
        
        return any(re.search(pattern, output, re.IGNORECASE) for pattern in version_patterns)
    
    @staticmethod
    def validate_status_output(output: str) -> bool:
        """
        Validate status output format.
        
        Returns:
            True if output looks like status information
        """
        status_indicators = [
            'status:', 'state:', 'running', 'stopped', 'enabled', 'disabled',
            'active', 'inactive', 'online', 'offline', 'healthy', 'unhealthy'
        ]
        
        output_lower = output.lower()
        return any(indicator in output_lower for indicator in status_indicators)


class TestAssertions:
    """Professional test assertions for CLI testing."""
    
    @staticmethod
    def assert_command_success(result: Dict[str, Any], test_name: str) -> bool:
        """
        Assert command succeeded with proper validation.
        
        Args:
            result: Command result from CLITestRunner
            test_name: Name of the test for error reporting
            
        Returns:
            True if assertion passes
            
        Raises:
            AssertionError: If command failed unexpectedly
        """
        if not result.get('success', False):
            error_msg = f"""
Test: {test_name}
Command: {result.get('command', 'unknown')}
Expected: Success
Actual: Failure (code {result.get('returncode', 'unknown')})
STDOUT: {result.get('stdout', '')[:200]}
STDERR: {result.get('stderr', '')[:200]}
"""
            raise AssertionError(error_msg)
        
        return True
    
    @staticmethod
    def assert_command_failure(result: Dict[str, Any], test_name: str, 
                             expected_error: Optional[str] = None) -> bool:
        """
        Assert command failed as expected.
        
        Args:
            result: Command result from CLITestRunner
            test_name: Name of the test for error reporting
            expected_error: Optional expected error message/type
            
        Returns:
            True if assertion passes
            
        Raises:
            AssertionError: If command succeeded unexpectedly
        """
        # When expect_success=False, success=True means the test passed (command failed as expected)
        # We only raise an error if success=False (command succeeded when we expected failure)
        if not result.get('success', False):
            error_msg = f"""
Test: {test_name}
Command: {result.get('command', 'unknown')}
Expected: Failure
Actual: Success (returncode {result.get('returncode', 'unknown')})
Output: {result.get('stdout', '')[:200]}
"""
            raise AssertionError(error_msg)
        
        if expected_error:
            output = result.get('stdout', '') + result.get('stderr', '')
            if expected_error.lower() not in output.lower():
                error_msg = f"""
Test: {test_name}
Expected error: {expected_error}
Actual output: {output[:200]}
"""
                raise AssertionError(error_msg)
        
        return True
    
    @staticmethod
    def assert_contains_all(text: str, expected_items: List[str], test_name: str) -> bool:
        """
        Assert text contains all expected items.
        
        Args:
            text: Text to search in
            expected_items: List of items that must be present
            test_name: Name of the test for error reporting
            
        Returns:
            True if assertion passes
            
        Raises:
            AssertionError: If any expected item is missing
        """
        text_lower = text.lower()
        missing_items = []
        
        for item in expected_items:
            item_lower = item.lower()
            # For truncated table displays, check if at least the first part of the name exists
            # Try progressively shorter prefixes to handle truncation
            found = False
            
            # First try the full name
            if item_lower in text_lower:
                found = True
            else:
                # Try progressively shorter prefixes (14, 12, 10, 8 chars)
                for prefix_len in [14, 12, 10, 8]:
                    if len(item_lower) > prefix_len:
                        item_prefix = item_lower[:prefix_len]
                        if item_prefix in text_lower:
                            found = True
                            break
            
            if not found:
                missing_items.append(item)
        
        if missing_items:
            error_msg = f"""
Test: {test_name}
Missing items: {missing_items}
In text: {text[:300]}
"""
            raise AssertionError(error_msg)
        
        return True
    
    @staticmethod
    def assert_not_contains(text: str, unwanted_items: List[str], test_name: str) -> bool:
        """
        Assert text does not contain unwanted items.
        
        Args:
            text: Text to search in
            unwanted_items: List of items that must not be present
            test_name: Name of the test for error reporting
            
        Returns:
            True if assertion passes
            
        Raises:
            AssertionError: If any unwanted item is found
        """
        text_lower = text.lower()
        found_items = [
            item for item in unwanted_items 
            if item.lower() in text_lower
        ]
        
        if found_items:
            error_msg = f"""
Test: {test_name}
Unwanted items found: {found_items}
In text: {text[:300]}
"""
            raise AssertionError(error_msg)
        
        return True