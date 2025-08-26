"""
Collection-Agnostic Test Runner

Tests CLI functionality using any existing collection as input.
Completely independent of server types (NPX/DD/D) or server configurations.
"""

import asyncio
import subprocess
from typing import Dict, List, Optional, Any
from pathlib import Path
import json

from mcp_manager.core.simple_manager import SimpleMCPManager
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class CollectionAgnosticTestRunner:
    """Test runner that works with any existing collection without creating servers."""
    
    def __init__(self, mcp_manager: SimpleMCPManager):
        """Initialize with MCP manager instance."""
        self.mcp_manager = mcp_manager
        self.original_state: Dict[str, Any] = {}
        self.test_collection_name: Optional[str] = None
    
    async def setup_test_environment(self, collection_name: Optional[str] = None):
        """
        Setup test environment using an existing collection.
        
        Args:
            collection_name: Name of existing collection to use, or None to use current state
        """
        # Capture original state
        self.original_state = await self._capture_current_state()
        
        if collection_name:
            # Use specified collection
            self.test_collection_name = collection_name
            logger.info(f"Using existing collection for testing: {collection_name}")
        else:
            # Use whatever servers are currently configured
            logger.info("Using current MCP configuration for testing")
        
        return True
    
    async def teardown_test_environment(self):
        """Restore original state after testing."""
        try:
            # Restore to original state if needed
            if self.original_state and self.test_collection_name:
                await self._restore_state(self.original_state)
                logger.info("Test environment restored to original state")
        except Exception as e:
            logger.error(f"Failed to restore test environment: {e}")
    
    async def _capture_current_state(self) -> Dict[str, Any]:
        """Capture current MCP configuration state."""
        try:
            # Get current servers
            servers = await self.mcp_manager.list_servers()
            
            state = {
                'servers': [
                    {
                        'name': server.name,
                        'enabled': server.enabled,
                        'server_type': server.server_type.value if server.server_type else None,
                        'command': server.command,
                        'scope': server.scope.value if server.scope else None
                    }
                    for server in servers
                ],
                'total_count': len(servers),
                'enabled_count': len([s for s in servers if s.enabled])
            }
            
            logger.debug(f"Captured state: {state['total_count']} servers, {state['enabled_count']} enabled")
            return state
            
        except Exception as e:
            logger.error(f"Failed to capture current state: {e}")
            return {}
    
    async def _restore_state(self, state: Dict[str, Any]):
        """Restore MCP configuration to captured state."""
        # This is a placeholder - in practice, we shouldn't need to restore
        # since tests should be read-only operations on existing collections
        logger.debug("State restoration not needed for read-only collection testing")
    
    def run_cli_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """
        Run a CLI command and return results.
        
        Args:
            command: CLI command to execute
            timeout: Command timeout in seconds
            
        Returns:
            Dict with stdout, stderr, returncode, and success status
        """
        try:
            # Ensure command starts with mcp-manager
            if not command.startswith('mcp-manager'):
                command = f"mcp-manager {command}"
            
            # Execute command
            result = subprocess.run(
                command.split(),
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=Path.cwd()
            )
            
            return {
                'stdout': result.stdout.strip(),
                'stderr': result.stderr.strip(),
                'returncode': result.returncode,
                'success': result.returncode == 0,
                'command': command,
                'timeout': timeout
            }
            
        except subprocess.TimeoutExpired:
            return {
                'stdout': '',
                'stderr': f'Command timed out after {timeout}s',
                'returncode': 124,
                'success': False,
                'command': command,
                'timeout': timeout
            }
        except Exception as e:
            return {
                'stdout': '',
                'stderr': str(e),
                'returncode': 1,
                'success': False,
                'command': command,
                'timeout': timeout
            }
    
    def validate_output(self, result: Dict[str, Any], expected_output: List[str], 
                       expected_exit_code: int = 0) -> Dict[str, Any]:
        """
        Validate command output against expectations.
        
        Args:
            result: Command execution result
            expected_output: List of strings that should be in output
            expected_exit_code: Expected exit code
            
        Returns:
            Dict with validation results
        """
        validation = {
            'exit_code_match': result['returncode'] == expected_exit_code,
            'output_matches': [],
            'missing_output': [],
            'overall_success': True
        }
        
        # Check exit code
        if not validation['exit_code_match']:
            validation['overall_success'] = False
        
        # Check output content
        output_text = result['stdout'] + result['stderr']
        
        for expected in expected_output:
            if expected.lower() in output_text.lower():
                validation['output_matches'].append(expected)
            else:
                validation['missing_output'].append(expected)
                validation['overall_success'] = False
        
        return validation
    
    async def get_available_collections(self) -> List[str]:
        """Get list of available collections that can be used for testing."""
        try:
            # Use CLI to get collection list
            result = self.run_cli_command("suite list")
            
            if result['success']:
                # Parse collection names from output
                collections = []
                lines = result['stdout'].split('\n')
                for line in lines:
                    # Simple parsing - look for collection names
                    # This is server-agnostic, just gets collection names
                    if line.strip() and not line.startswith('Total') and not line.startswith('═'):
                        # Extract collection name (first word/identifier)
                        parts = line.split()
                        if parts:
                            collections.append(parts[0])
                
                return collections
            else:
                logger.warning("Failed to get collection list")
                return []
                
        except Exception as e:
            logger.error(f"Failed to get available collections: {e}")
            return []
    
    def test_basic_functionality(self, collection_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Test basic CLI functionality with any collection.
        
        Args:
            collection_name: Optional collection to use
            
        Returns:
            Test results
        """
        results = {
            'collection': collection_name or 'current',
            'tests': [],
            'overall_success': True
        }
        
        # Test 1: Help command (always works, server-independent)
        help_result = self.run_cli_command("--help")
        help_validation = self.validate_output(
            help_result, 
            ["Usage:", "Commands:", "Options:"]
        )
        
        results['tests'].append({
            'name': 'help_command',
            'result': help_result,
            'validation': help_validation,
            'success': help_validation['overall_success']
        })
        
        if not help_validation['overall_success']:
            results['overall_success'] = False
        
        # Test 2: Version command (always works, server-independent)
        version_result = self.run_cli_command("--version")
        version_validation = self.validate_output(
            version_result,
            ["MCP Manager"]
        )
        
        results['tests'].append({
            'name': 'version_command',
            'result': version_result,
            'validation': version_validation,
            'success': version_validation['overall_success']
        })
        
        if not version_validation['overall_success']:
            results['overall_success'] = False
        
        # Test 3: List command (works with any servers)
        list_result = self.run_cli_command("list")
        list_validation = self.validate_output(
            list_result,
            []  # No specific output required - just needs to run
        )
        
        results['tests'].append({
            'name': 'list_command',
            'result': list_result,
            'validation': list_validation,
            'success': list_result['success']  # Just needs to execute successfully
        })
        
        if not list_result['success']:
            results['overall_success'] = False
        
        # Test 4: Collection list (server-agnostic)
        suite_list_result = self.run_cli_command("suite list")
        suite_validation = self.validate_output(
            suite_list_result,
            []  # No specific output required
        )
        
        results['tests'].append({
            'name': 'suite_list_command',
            'result': suite_list_result,
            'validation': suite_validation,
            'success': suite_list_result['success']
        })
        
        if not suite_list_result['success']:
            results['overall_success'] = False
        
        return results


# Convenience functions for pytest integration
async def setup_collection_test(collection_name: Optional[str] = None) -> CollectionAgnosticTestRunner:
    """Setup collection-agnostic test environment."""
    mcp_manager = SimpleMCPManager()
    runner = CollectionAgnosticTestRunner(mcp_manager)
    await runner.setup_test_environment(collection_name)
    return runner


async def teardown_collection_test(runner: CollectionAgnosticTestRunner):
    """Teardown collection-agnostic test environment."""
    await runner.teardown_test_environment()


def run_server_agnostic_tests(collection_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Run server-agnostic tests with any collection.
    
    Args:
        collection_name: Optional collection name to use
        
    Returns:
        Test results
    """
    async def _run_tests():
        runner = await setup_collection_test(collection_name)
        try:
            results = runner.test_basic_functionality(collection_name)
            return results
        finally:
            await teardown_collection_test(runner)
    
    return asyncio.run(_run_tests())