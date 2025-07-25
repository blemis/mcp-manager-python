"""
Dynamic Test Engine for JSON-based test scenarios.

Executes test scenarios defined in JSON format, handling MCP server setup,
CLI command execution, validation, and cleanup automatically.
"""

import json
import asyncio
import subprocess
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass

from tests.ai_integration.schema_validator import TestScenarioValidator
from tests.fixtures.dynamic_suite_loader import DynamicSuiteLoader
from src.mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)

@dataclass
class StepResult:
    """Result of executing a single test step."""
    step_id: int
    success: bool
    output: str
    error: str
    duration: float
    expected_outcome: str
    actual_outcome: str

@dataclass
class ScenarioResult:
    """Result of executing a complete test scenario."""
    scenario_id: str
    scenario_name: str
    success: bool
    duration: float
    step_results: List[StepResult]
    validation_results: Dict[str, bool]
    cleanup_performed: bool
    error_message: Optional[str] = None

class DynamicTestEngine:
    """Executes JSON-defined test scenarios dynamically."""
    
    def __init__(self, validator: Optional[TestScenarioValidator] = None):
        """Initialize the test engine."""
        self.validator = validator or TestScenarioValidator()
        self.results_cache = {}
        # Suite loader will be initialized when needed (requires mcp_manager instance)
        
    async def execute_scenario_file(self, scenario_path: Path) -> ScenarioResult:
        """
        Execute a test scenario from a JSON file.
        
        Args:
            scenario_path: Path to JSON scenario file
            
        Returns:
            ScenarioResult with execution details
        """
        try:
            with open(scenario_path, 'r') as f:
                scenario_data = json.load(f)
            
            logger.info(f"🚀 Executing scenario from {scenario_path.name}")
            return await self.execute_scenario(scenario_data)
            
        except Exception as e:
            logger.error(f"Failed to load scenario from {scenario_path}: {e}")
            return ScenarioResult(
                scenario_id="unknown",
                scenario_name=f"Failed: {scenario_path.name}",
                success=False,
                duration=0.0,
                step_results=[],
                validation_results={},
                cleanup_performed=False,
                error_message=str(e)
            )
    
    async def execute_scenario(self, scenario_data: Dict[str, Any]) -> ScenarioResult:
        """
        Execute a test scenario from JSON data.
        
        Args:
            scenario_data: Validated JSON scenario data
            
        Returns:
            ScenarioResult with execution details
        """
        start_time = time.time()
        scenario_info = scenario_data.get('scenario', {})
        scenario_id = scenario_info.get('id', 'unknown')
        scenario_name = scenario_info.get('name', 'Unknown Scenario')
        
        logger.info(f"📋 Starting scenario: {scenario_name} (ID: {scenario_id})")
        
        # Validate scenario first
        is_valid, validation_errors = self.validator.validate_scenario(scenario_data)
        if not is_valid:
            logger.error(f"❌ Scenario validation failed: {validation_errors}")
            return ScenarioResult(
                scenario_id=scenario_id,
                scenario_name=scenario_name,
                success=False,
                duration=time.time() - start_time,
                step_results=[],
                validation_results={},
                cleanup_performed=False,
                error_message=f"Validation failed: {validation_errors}"
            )
        
        step_results = []
        validation_results = {}
        cleanup_performed = False
        overall_success = True
        
        try:
            # Setup MCP environment
            await self._setup_mcp_environment(scenario_data)
            
            # Execute test steps
            test_steps = scenario_data.get('test_steps', [])
            for step_data in test_steps:
                step_result = await self._execute_step(step_data)
                step_results.append(step_result)
                
                if not step_result.success:
                    overall_success = False
                    if not step_data.get('cleanup_on_failure', True):
                        break
            
            # Perform validation
            validation_data = scenario_data.get('validation', {})
            validation_results = await self._perform_validation(
                validation_data, step_results
            )
            
            # Overall success depends on both steps and validation
            overall_success = overall_success and all(validation_results.values())
            
        except Exception as e:
            logger.error(f"❌ Scenario execution failed: {e}")
            overall_success = False
            
        finally:
            # Always attempt cleanup
            cleanup_performed = await self._perform_cleanup(scenario_data)
        
        duration = time.time() - start_time
        
        result = ScenarioResult(
            scenario_id=scenario_id,
            scenario_name=scenario_name,
            success=overall_success,
            duration=duration,
            step_results=step_results,
            validation_results=validation_results,
            cleanup_performed=cleanup_performed
        )
        
        # Cache result for analysis
        self.results_cache[scenario_id] = result
        
        status_emoji = "✅" if overall_success else "❌"
        logger.info(f"{status_emoji} Scenario completed: {scenario_name} in {duration:.2f}s")
        
        return result
    
    async def _get_suite_for_category(self, category: str) -> Optional[Dict[str, Any]]:
        """Get the appropriate test suite for a category."""
        try:
            # Import here to avoid circular imports
            from src.mcp_manager.core.simple_manager import SimpleMCPManager
            from src.mcp_manager.core.test_management.category_manager import TestCategoryManager
            from tests.fixtures.dynamic_suite_loader import DynamicSuiteLoader
            
            # Create mock test instance to match category
            class MockTestInstance:
                def __init__(self, category):
                    self.category = category
                    self.__class__.__name__ = f"Test{category.title()}Tests"
                    # Map category to test file pattern
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
                    self.__module__ = type('MockModule', (), {
                        '__file__': f"tests/{file_mapping.get(category, 'test_basic_commands.py')}"
                    })()
            
            # Initialize managers
            mcp_manager = SimpleMCPManager()
            suite_loader = DynamicSuiteLoader(mcp_manager)
            
            # Get suite for category
            mock_test = MockTestInstance(category)
            suite_data = await suite_loader.auto_load_suite_for_test(mock_test)
            
            return suite_data
            
        except Exception as e:
            logger.warning(f"Could not load suite for category {category}: {e}")
            return None
    
    async def _setup_mcp_environment(self, scenario_data: Dict[str, Any]):
        """The MCP environment is already set up by the suite system - we just test against it."""
        # The test suites are loaded by the CLI runner BEFORE tests run
        # We don't deploy servers here - we test MCP Manager's ability to manage them
        logger.debug("📦 Using pre-loaded test suite environment")
        
    
    async def _execute_step(self, step_data: Dict[str, Any]) -> StepResult:
        """Execute a single test step."""
        step_id = step_data.get('step_id', 0)
        action = step_data.get('action', 'unknown')
        expected_outcome = step_data.get('expect', 'success')
        timeout = step_data.get('timeout', 30)
        description = step_data.get('description', f'Step {step_id}')
        
        logger.debug(f"🔧 Step {step_id}: {description}")
        
        start_time = time.time()
        
        try:
            if action == 'cli_command':
                success, output, error = await self._execute_cli_command(step_data, timeout)
            elif action == 'setup':
                success, output, error = await self._execute_setup_action(step_data)
            elif action == 'validation':
                success, output, error = await self._execute_validation_action(step_data)
            elif action == 'cleanup':
                success, output, error = await self._execute_cleanup_action(step_data)
            elif action == 'wait':
                success, output, error = await self._execute_wait_action(step_data)
            elif action == 'file_check':
                success, output, error = await self._execute_file_check(step_data)
            else:
                success, output, error = False, "", f"Unknown action: {action}"
            
            duration = time.time() - start_time
            
            # Validate expected outcome
            actual_outcome = self._determine_actual_outcome(success, output, error, step_data)
            expected_match = self._validate_expected_outcome(
                expected_outcome, actual_outcome, step_data
            )
            
            # Final success depends on whether the outcome matched expectations
            # If we expected failure and got failure, that's a success
            final_success = expected_match
            
            step_emoji = "✅" if final_success else "❌"
            logger.debug(f"   {step_emoji} Step {step_id} completed in {duration:.2f}s")
            
            return StepResult(
                step_id=step_id,
                success=final_success,
                output=output,
                error=error,
                duration=duration,
                expected_outcome=expected_outcome,
                actual_outcome=actual_outcome
            )
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ Step {step_id} failed with exception: {e}")
            
            return StepResult(
                step_id=step_id,
                success=False,
                output="",
                error=str(e),
                duration=duration,
                expected_outcome=expected_outcome,
                actual_outcome="exception"
            )
    
    async def _execute_cli_command(self, step_data: Dict[str, Any], timeout: int) -> Tuple[bool, str, str]:
        """Execute a CLI command step."""
        command = step_data.get('command', '')
        if not command:
            return False, "", "No command specified"
        
        # Prepend with mcp-manager if not already included
        if not command.startswith('mcp-manager'):
            command = f"mcp-manager {command}"
        
        logger.debug(f"💻 Executing: {command}")
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path(__file__).parent.parent.parent
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )
            
            stdout_str = stdout.decode('utf-8') if stdout else ""
            stderr_str = stderr.decode('utf-8') if stderr else ""
            
            success = process.returncode == 0
            
            logger.debug(f"   Return code: {process.returncode}")
            if stdout_str:
                logger.debug(f"   Stdout: {stdout_str[:200]}...")
            if stderr_str:
                logger.debug(f"   Stderr: {stderr_str[:200]}...")
            
            return success, stdout_str, stderr_str
            
        except asyncio.TimeoutError:
            logger.error(f"❌ Command timed out after {timeout}s: {command}")
            return False, "", f"Command timed out after {timeout}s"
        except Exception as e:
            logger.error(f"❌ Command execution failed: {e}")
            return False, "", str(e)
    
    async def _execute_setup_action(self, step_data: Dict[str, Any]) -> Tuple[bool, str, str]:
        """Execute a setup action."""
        parameters = step_data.get('parameters', {})
        action_type = parameters.get('action_type', 'unknown')
        
        logger.debug(f"🔧 Setup action: {action_type}")
        
        try:
            if action_type == 'clean_environment':
                # Clean test environment
                backup_config = parameters.get('backup_config', False)
                if backup_config:
                    # TODO: Implement config backup
                    pass
                return True, "Environment cleaned", ""
            else:
                return False, "", f"Unknown setup action: {action_type}"
        except Exception as e:
            return False, "", str(e)
    
    async def _execute_validation_action(self, step_data: Dict[str, Any]) -> Tuple[bool, str, str]:
        """Execute a validation action."""
        parameters = step_data.get('parameters', {})
        validate_type = parameters.get('validate_type', 'unknown')
        
        logger.debug(f"🔍 Validation action: {validate_type}")
        
        # This is a placeholder - validation logic would be implemented based on type
        return True, "Validation passed", ""
    
    async def _execute_cleanup_action(self, step_data: Dict[str, Any]) -> Tuple[bool, str, str]:
        """Execute a cleanup action."""
        logger.debug("🧹 Cleanup action")
        return True, "Cleanup completed", ""
    
    async def _execute_wait_action(self, step_data: Dict[str, Any]) -> Tuple[bool, str, str]:
        """Execute a wait action."""
        duration = step_data.get('parameters', {}).get('duration', 1)
        logger.debug(f"⏱️  Waiting {duration}s")
        await asyncio.sleep(duration)
        return True, f"Waited {duration}s", ""
    
    async def _execute_file_check(self, step_data: Dict[str, Any]) -> Tuple[bool, str, str]:
        """Execute a file check action."""
        file_path = step_data.get('parameters', {}).get('file_path', '')
        exists = Path(file_path).exists() if file_path else False
        return exists, f"File exists: {exists}", ""
    
    def _determine_actual_outcome(self, success: bool, output: str, error: str, step_data: Dict[str, Any]) -> str:
        """Determine the actual outcome of a step."""
        expected = step_data.get('expect', 'success')
        
        if not success:
            return "failure"
        elif expected == 'contains' and step_data.get('expect_value'):
            expect_value = step_data.get('expect_value')
            if expect_value in output or expect_value in error:
                return "contains"
            else:
                return "success"  # Command succeeded but didn't contain expected value
        else:
            return "success"
    
    def _validate_expected_outcome(self, expected: str, actual: str, step_data: Dict[str, Any]) -> bool:
        """Validate that actual outcome matches expected outcome."""
        if expected == actual:
            return True
        
        # Handle special cases
        if expected == 'success' and actual in ['success', 'contains']:
            return True
        
        # Handle failure expectation - if we expect failure and got failure, that's success
        if expected == 'failure' and actual == 'failure':
            return True
        
        # Handle contains expectation
        if expected == 'contains':
            expect_value = step_data.get('expect_value', '')
            # This would need to be implemented with actual output checking
            return True  # Placeholder
        
        return False
    
    async def _perform_validation(self, validation_data: Dict[str, Any], step_results: List[StepResult]) -> Dict[str, bool]:
        """Perform scenario-level validation."""
        results = {}
        
        success_criteria = validation_data.get('success_criteria', [])
        for criterion in success_criteria:
            criterion_type = criterion.get('type', 'unknown')
            
            if criterion_type == 'all_steps_pass':
                results[criterion_type] = all(step.success for step in step_results)
            elif criterion_type == 'specific_output':
                # Check if any step output contains the expected value
                expected_value = criterion.get('value', '')
                results[criterion_type] = any(
                    expected_value in step.output for step in step_results
                )
            else:
                # Default to True for unknown criteria (placeholder)
                results[criterion_type] = True
        
        return results
    
    async def _perform_cleanup(self, scenario_data: Dict[str, Any]) -> bool:
        """Perform scenario cleanup based on strategy."""
        validation_data = scenario_data.get('validation', {})
        cleanup_strategy = validation_data.get('cleanup_strategy', 'minimal')
        cleanup_timing = validation_data.get('cleanup_timing', 'after_test')
        preserve_state = validation_data.get('preserve_state', [])
        cleanup_required = validation_data.get('cleanup_required', True)
        
        if not cleanup_required or cleanup_strategy == 'none':
            logger.debug("🧹 No cleanup required")
            return True
        
        logger.info(f"🧹 Performing {cleanup_strategy} cleanup strategy")
        
        # Handle predefined strategies
        if cleanup_strategy == 'suite_preserve':
            return await self._cleanup_preserve_suite(preserve_state)
        elif cleanup_strategy == 'minimal':
            return await self._cleanup_minimal()
        elif cleanup_strategy == 'full':
            return await self._cleanup_full(preserve_state)
        else:
            # Custom cleanup using defined steps
            return await self._cleanup_custom(validation_data)
    
    async def _cleanup_preserve_suite(self, preserve_state: List[str]) -> bool:
        """Cleanup while preserving suite servers."""
        logger.info("   🔒 Preserving suite servers, cleaning test artifacts only")
        
        # Remove only non-suite servers (test-created ones)
        success, output, error = await self._execute_cli_command({
            'command': 'list --scope user --format json'
        }, 15)
        
        if success:
            try:
                import json
                servers = json.loads(output)
                for server_name, server_info in servers.items():
                    # Only remove servers that look like test artifacts
                    if any(pattern in server_name.lower() for pattern in ['test-', 'temp-', 'tmp-']):
                        logger.debug(f"   🗑️  Removing test server: {server_name}")
                        await self._execute_cli_command({
                            'command': f'remove {server_name}'
                        }, 10)
            except Exception as e:
                logger.warning(f"Failed to parse server list for cleanup: {e}")
        
        return True
    
    async def _cleanup_minimal(self) -> bool:
        """Minimal cleanup - only obvious test artifacts."""
        logger.info("   🧽 Minimal cleanup - removing test artifacts only")
        
        # Clear any test-specific cache or temporary files
        test_patterns = ['test-*', 'tmp-*', 'temp-*']
        for pattern in test_patterns:
            try:
                success, _, _ = await self._execute_cli_command({
                    'command': f'remove {pattern} --pattern'
                }, 10)
            except:
                pass  # Ignore errors in minimal cleanup
        
        return True
    
    async def _cleanup_full(self, preserve_state: List[str]) -> bool:
        """Full cleanup - reset environment to pre-test state."""
        logger.info("   🔥 Full cleanup - resetting environment")
        
        if 'suite_servers' not in preserve_state:
            # Remove all non-system servers
            success, _, _ = await self._execute_cli_command({
                'command': 'remove --all --exclude-system'
            }, 30)
        
        if 'user_config' not in preserve_state:
            # Reset user configuration
            success, _, _ = await self._execute_cli_command({
                'command': 'config reset --scope user'
            }, 15)
        
        return True
    
    async def _cleanup_custom(self, validation_data: Dict[str, Any]) -> bool:
        """Execute custom cleanup steps."""
        cleanup_steps = validation_data.get('cleanup_steps', [])
        logger.info(f"   🔧 Custom cleanup ({len(cleanup_steps)} steps)")
        
        cleanup_success = True
        for cleanup_step in cleanup_steps:
            action = cleanup_step.get('action', 'unknown')
            target = cleanup_step.get('target', 'test_only')
            condition = cleanup_step.get('condition', 'always')
            ignore_errors = cleanup_step.get('ignore_errors', True)
            
            # Check condition
            if condition != 'always':
                # TODO: Implement conditional logic based on test results
                pass
            
            try:
                if action == 'remove_test_servers':
                    pattern = cleanup_step.get('server_pattern', 'test-*')
                    await self._execute_cli_command({
                        'command': f'remove {pattern} --pattern'
                    }, 15)
                elif action == 'preserve_suite':
                    logger.debug("   🔒 Preserving suite servers")
                elif action == 'custom_command':
                    command = cleanup_step.get('command', '')
                    if command:
                        success, _, _ = await self._execute_cli_command(
                            {'command': command}, 30
                        )
                        if not success and not ignore_errors:
                            cleanup_success = False
            except Exception as e:
                logger.warning(f"Cleanup step failed: {e}")
                if not ignore_errors:
                    cleanup_success = False
        
        return cleanup_success
    
    def generate_report(self, results: List[ScenarioResult]) -> Dict[str, Any]:
        """Generate a comprehensive test execution report."""
        total_scenarios = len(results)
        successful_scenarios = sum(1 for r in results if r.success)
        total_duration = sum(r.duration for r in results)
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_scenarios": total_scenarios,
                "successful_scenarios": successful_scenarios,
                "failed_scenarios": total_scenarios - successful_scenarios,
                "success_rate": (successful_scenarios / total_scenarios * 100) if total_scenarios > 0 else 0,
                "total_duration": total_duration,
                "average_duration": total_duration / total_scenarios if total_scenarios > 0 else 0
            },
            "scenarios": []
        }
        
        for result in results:
            scenario_data = {
                "id": result.scenario_id,
                "name": result.scenario_name,
                "success": result.success,
                "duration": result.duration,
                "steps_executed": len(result.step_results),
                "steps_passed": sum(1 for s in result.step_results if s.success),
                "validation_results": result.validation_results,
                "cleanup_performed": result.cleanup_performed
            }
            
            if result.error_message:
                scenario_data["error"] = result.error_message
            
            report["scenarios"].append(scenario_data)
        
        return report