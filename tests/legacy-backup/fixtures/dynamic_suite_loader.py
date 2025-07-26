"""
Dynamic suite loader that automatically determines the right suite for each test.
"""

import asyncio
import inspect
from typing import Optional, Dict, Any
from pathlib import Path

from mcp_manager.core.test_management.category_manager import TestCategoryManager
from tests.fixtures.suite_loader import SuiteLoader
from tests.fixtures.test_suites_setup import TestSuitesSetup
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class DynamicSuiteLoader:
    """Dynamically loads appropriate test suites based on test context."""
    
    def __init__(self, mcp_manager, test_db_path: Optional[Path] = None):
        """Initialize with managers."""
        self.mcp_manager = mcp_manager
        self.category_manager = TestCategoryManager(test_db_path)
        self.suite_loader = SuiteLoader(mcp_manager)
        self.suite_setup = TestSuitesSetup()
        self.loaded_suites: Dict[str, Any] = {}
    
    async def auto_load_suite_for_test(self, test_instance) -> Optional[Dict[str, Any]]:
        """
        Automatically determine and load the appropriate suite for a test.
        
        Args:
            test_instance: The test class instance
            
        Returns:
            Dict with suite data if successful, None otherwise
        """
        try:
            # Get test file path from test instance
            test_file = self._get_test_file_from_instance(test_instance)
            if not test_file:
                print(f"⚠️  Could not determine test file for {test_instance.__class__.__name__}")
                return None
            
            # Find matching test category
            category = self.category_manager.get_category_for_test_file(test_file)
            if not category:
                print(f"⚠️  No test category found for {test_file}")
                return None
            
            # Get mapped suite
            suite_id = self.category_manager.get_suite_for_test_file(test_file)
            if not suite_id:
                print(f"⚠️  No suite mapped for category {category.id}")
                return None
            
            # Check if suite is already loaded
            if suite_id in self.loaded_suites:
                print(f"🔄 Reusing loaded suite: {suite_id}")
                return self.loaded_suites[suite_id]
            
            # Create suite if it doesn't exist
            await self._ensure_suite_exists(suite_id, category)
            
            # Load the suite
            print(f"🎯 Auto-loading suite for {category.name} tests: {suite_id}")
            suite_data = await self.suite_loader.load_suite(suite_id)
            
            if suite_data:
                self.loaded_suites[suite_id] = suite_data
                print(f"✅ {category.name} Test Suite loaded: {len(suite_data.get('deployed_servers', {}))} servers")
                return suite_data
            else:
                print(f"❌ Failed to load suite: {suite_id}")
                return None
                
        except Exception as e:
            print(f"❌ Error loading suite for test: {e}")
            logger.error(f"Error in auto_load_suite_for_test: {e}")
            return None
    
    def _get_test_file_from_instance(self, test_instance) -> Optional[str]:
        """Extract test file name from test instance."""
        try:
            # Get the module of the test class
            module = inspect.getmodule(test_instance.__class__)
            if module and hasattr(module, '__file__'):
                file_path = Path(module.__file__)
                return file_path.name
        except Exception as e:
            logger.debug(f"Could not get test file from instance: {e}")
        
        return None
    
    async def _ensure_suite_exists(self, suite_id: str, category) -> bool:
        """Ensure the test suite exists, create if necessary."""
        try:
            # Try to get the suite first
            existing_suite = await self.suite_setup.suite_manager.get_suite(suite_id)
            if existing_suite:
                return True
            
            # Create suite based on category
            print(f"📦 Creating missing suite: {suite_id}")
            
            # Map category IDs to suite creation methods
            suite_creators = {
                "server-management": self.suite_setup.create_server_lifecycle_test_suite,
                "basic-commands": self.suite_setup.create_basic_commands_test_suite,
                "suite-management": self.suite_setup.create_suite_management_test_suite,
                "error-handling": self.suite_setup.create_error_handling_test_suite,
                "workflows": self.suite_setup.create_workflows_test_suite,
                "quality-tracking": self.suite_setup.create_quality_tracking_test_suite
            }
            
            creator_method = suite_creators.get(category.id)
            if creator_method:
                await creator_method()
                print(f"✅ Created suite: {suite_id}")
                return True
            else:
                print(f"⚠️  No creator method for category: {category.id}")
                return False
                
        except Exception as e:
            print(f"❌ Error ensuring suite exists: {e}")
            logger.error(f"Error in _ensure_suite_exists: {e}")
            return False
    
    async def cleanup_loaded_suites(self):
        """Clean up all loaded suites."""
        try:
            print("🧹 Cleaning up dynamically loaded suites...")
            await self.suite_loader.unload_all_suites()
            self.loaded_suites.clear()
            print("✅ Suite cleanup completed")
        except Exception as e:
            print(f"⚠️  Error during suite cleanup: {e}")
            logger.error(f"Error in cleanup_loaded_suites: {e}")