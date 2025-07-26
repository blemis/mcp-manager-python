"""
JSON Schema validator for AI-generated test scenarios.

Validates test scenarios against the official schema and provides detailed
error reporting for debugging invalid scenarios.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import jsonschema
from jsonschema import validate, ValidationError, Draft7Validator

from src.mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)

class TestScenarioValidator:
    """Validates test scenarios against the JSON schema."""
    
    def __init__(self, schema_path: Optional[Path] = None):
        """Initialize validator with schema file."""
        if schema_path is None:
            schema_path = Path(__file__).parent.parent / "schemas" / "test_scenario_schema.json"
        
        self.schema_path = schema_path
        self.schema = self._load_schema()
        self.validator = Draft7Validator(self.schema)
    
    def _load_schema(self) -> Dict[str, Any]:
        """Load the JSON schema from file."""
        try:
            with open(self.schema_path, 'r') as f:
                schema = json.load(f)
            logger.debug(f"Loaded schema from {self.schema_path}")
            return schema
        except Exception as e:
            logger.error(f"Failed to load schema from {self.schema_path}: {e}")
            raise
    
    def validate_scenario(self, scenario: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate a single test scenario.
        
        Args:
            scenario: Test scenario dictionary to validate
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        try:
            # Basic schema validation
            validate(instance=scenario, schema=self.schema)
            
            # Additional business logic validation
            business_errors = self._validate_business_logic(scenario)
            errors.extend(business_errors)
            
            is_valid = len(errors) == 0
            
            if is_valid:
                logger.debug(f"Scenario '{scenario.get('scenario', {}).get('id', 'unknown')}' passed validation")
            else:
                logger.warning(f"Scenario validation failed with {len(errors)} errors")
                
            return is_valid, errors
            
        except ValidationError as e:
            errors.append(f"Schema validation error: {e.message}")
            if e.path:
                errors.append(f"  Path: {' -> '.join(str(p) for p in e.path)}")
            return False, errors
        except Exception as e:
            errors.append(f"Unexpected validation error: {str(e)}")
            return False, errors
    
    def _validate_business_logic(self, scenario: Dict[str, Any]) -> List[str]:
        """Additional validation beyond schema requirements."""
        errors = []
        
        # Validate scenario metadata
        scenario_info = scenario.get('scenario', {})
        
        # Check confidence score reasonableness
        confidence = scenario_info.get('confidence_score', 0)
        if confidence < 0.5:
            errors.append(f"Low confidence score ({confidence}) - consider improving scenario quality")
        
        # Validate MCP requirements
        mcp_reqs = scenario.get('mcp_requirements', {})
        required_servers = mcp_reqs.get('required_servers', [])
        
        # Check for reasonable server requirements
        if len(required_servers) > 5:
            errors.append("Too many required servers (>5) - consider splitting scenario")
        
        # Validate test steps
        test_steps = scenario.get('test_steps', [])
        
        # Check step sequence
        step_ids = [step.get('step_id') for step in test_steps]
        expected_ids = list(range(1, len(test_steps) + 1))
        if step_ids != expected_ids:
            errors.append(f"Test step IDs not sequential: got {step_ids}, expected {expected_ids}")
        
        # Check for reasonable timeouts
        for step in test_steps:
            timeout = step.get('timeout', 30)
            if timeout > 300:  # 5 minutes
                errors.append(f"Step {step.get('step_id')} has excessive timeout ({timeout}s)")
        
        # Validate CLI commands
        for step in test_steps:
            if step.get('action') == 'cli_command':
                command = step.get('command', '')
                if not command.strip():
                    errors.append(f"Step {step.get('step_id')} has empty CLI command")
                
                # Check for dangerous commands
                dangerous_patterns = ['rm -rf', 'sudo', 'format', 'delete']
                if any(pattern in command.lower() for pattern in dangerous_patterns):
                    errors.append(f"Step {step.get('step_id')} contains potentially dangerous command: {command}")
        
        # Validate cleanup requirements
        validation_info = scenario.get('validation', {})
        cleanup_required = validation_info.get('cleanup_required', True)
        if cleanup_required and not validation_info.get('cleanup_steps'):
            errors.append("Cleanup required but no cleanup steps defined")
        
        return errors
    
    def validate_scenario_file(self, file_path: Path) -> Tuple[bool, List[str]]:
        """
        Validate a scenario from a JSON file.
        
        Args:
            file_path: Path to JSON scenario file
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        try:
            with open(file_path, 'r') as f:
                scenario = json.load(f)
            
            logger.debug(f"Validating scenario file: {file_path}")
            return self.validate_scenario(scenario)
            
        except json.JSONDecodeError as e:
            return False, [f"Invalid JSON in {file_path}: {e}"]
        except Exception as e:
            return False, [f"Error reading {file_path}: {e}"]
    
    def validate_directory(self, directory_path: Path) -> Dict[str, Tuple[bool, List[str]]]:
        """
        Validate all JSON scenario files in a directory.
        
        Args:
            directory_path: Path to directory containing scenario files
            
        Returns:
            Dictionary mapping file paths to validation results
        """
        results = {}
        
        if not directory_path.exists():
            logger.error(f"Directory does not exist: {directory_path}")
            return results
        
        json_files = list(directory_path.glob("**/*.json"))
        logger.info(f"Validating {len(json_files)} scenario files in {directory_path}")
        
        for file_path in json_files:
            is_valid, errors = self.validate_scenario_file(file_path)
            results[str(file_path)] = (is_valid, errors)
        
        return results
    
    def get_validation_report(self, results: Dict[str, Tuple[bool, List[str]]]) -> Dict[str, Any]:
        """
        Generate a comprehensive validation report.
        
        Args:
            results: Validation results from validate_directory
            
        Returns:
            Formatted validation report
        """
        total_files = len(results)
        valid_files = sum(1 for is_valid, _ in results.values() if is_valid)
        invalid_files = total_files - valid_files
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_files": total_files,
                "valid_files": valid_files,
                "invalid_files": invalid_files,
                "success_rate": (valid_files / total_files * 100) if total_files > 0 else 0
            },
            "details": {}
        }
        
        for file_path, (is_valid, errors) in results.items():
            report["details"][file_path] = {
                "valid": is_valid,
                "errors": errors,
                "error_count": len(errors)
            }
        
        return report
    
    def print_validation_summary(self, results: Dict[str, Tuple[bool, List[str]]]):
        """Print a human-readable validation summary."""
        report = self.get_validation_report(results)
        summary = report["summary"]
        
        print(f"\n🔍 Test Scenario Validation Report")
        print(f"{'='*50}")
        print(f"📁 Total Files: {summary['total_files']}")
        print(f"✅ Valid: {summary['valid_files']}")
        print(f"❌ Invalid: {summary['invalid_files']}")
        print(f"📊 Success Rate: {summary['success_rate']:.1f}%")
        
        if summary['invalid_files'] > 0:
            print(f"\n❌ Invalid Files:")
            for file_path, (is_valid, errors) in results.items():
                if not is_valid:
                    print(f"\n📄 {Path(file_path).name}:")
                    for error in errors[:3]:  # Show first 3 errors
                        print(f"   • {error}")
                    if len(errors) > 3:
                        print(f"   ... and {len(errors) - 3} more errors")

def validate_ai_scenarios(directory_path: str) -> bool:
    """
    Convenience function to validate AI-generated scenarios.
    
    Args:
        directory_path: Path to scenarios directory
        
    Returns:
        True if all scenarios are valid, False otherwise
    """
    validator = TestScenarioValidator()
    results = validator.validate_directory(Path(directory_path))
    
    validator.print_validation_summary(results)
    
    # Return True only if all scenarios are valid
    return all(is_valid for is_valid, _ in results.values())

if __name__ == "__main__":
    # Example usage
    scenarios_dir = Path(__file__).parent.parent / "scenarios"
    validator = TestScenarioValidator()
    results = validator.validate_directory(scenarios_dir)
    validator.print_validation_summary(results)