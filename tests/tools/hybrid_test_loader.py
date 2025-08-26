"""
Hybrid Test Loader

Uses DB for fast queries and JSON files as authoritative source.
Automatically syncs DB when JSON files change.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import time
import os

from tests.tools.test_catalog_db import TestCatalogDB
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class HybridTestLoader:
    """Loads tests from DB with JSON file synchronization."""
    
    def __init__(self):
        """Initialize hybrid loader."""
        self.catalog = TestCatalogDB()
        self.tests_dir = Path(__file__).parent.parent / "scenarios" / "cli_tests"
        self._ensure_db_synced()
    
    def _ensure_db_synced(self):
        """Ensure DB is synced with JSON files."""
        try:
            # Check if any JSON files are newer than last DB update
            needs_sync = False
            db_mtime = 0
            
            if self.catalog.db_path.exists():
                db_mtime = self.catalog.db_path.stat().st_mtime
            
            for json_file in self.tests_dir.glob("*.json"):
                if json_file.name == "master_test_config.json":
                    continue
                
                file_mtime = json_file.stat().st_mtime
                if file_mtime > db_mtime:
                    needs_sync = True
                    break
            
            if needs_sync or not self.catalog.db_path.exists():
                logger.info("🔄 Syncing test database with JSON files...")
                self.catalog.index_all_test_files()
                logger.info("✅ Test database synced")
            
        except Exception as e:
            logger.warning(f"DB sync check failed: {e}")
    
    def get_dynamic_test_categories(self) -> Dict[str, Dict]:
        """Get test categories dynamically from DB."""
        categories = {}
        
        try:
            # Get all test suites from DB
            suites = self.catalog.search_tests()
            
            for suite in suites:
                category = suite['category']
                priority = suite['priority'].upper()
                test_count = suite['scenario_count']
                description = suite['test_suite_description']
                
                # Estimate duration
                estimated_duration = max(10, test_count * 3)
                duration_str = f"~{estimated_duration}s" if estimated_duration < 60 else f"~{estimated_duration//60}min"
                
                # Get color based on priority
                color_map = {
                    'CRITICAL': '\033[91m',  # Red
                    'HIGH': '\033[94m',      # Blue  
                    'MEDIUM': '\033[96m',    # Cyan
                    'LOW': '\033[90m'        # Gray
                }
                
                # Create full description
                full_description = f"{description} ({test_count} tests, {duration_str})"
                
                # Create friendly name
                suite_name = suite['test_suite_name']
                
                categories[category] = {
                    'name': suite_name,
                    'description': full_description,
                    'priority': priority,
                    'color': color_map.get(priority, '\033[96m'),
                    'file': suite['file_path'],
                    'test_count': test_count,
                    'is_json': True,
                    'suite_id': suite['id'],
                    'collection_type': suite['collection_type'],
                    'compatibility': {
                        'npm_servers': bool(suite['compatibility_npm']),
                        'docker_desktop_servers': bool(suite['compatibility_dd']),
                        'docker_hub_servers': bool(suite['compatibility_docker']),
                        'empty_state': bool(suite['compatibility_empty'])
                    }
                }
            
            return categories
            
        except Exception as e:
            logger.error(f"Failed to load dynamic categories from DB: {e}")
            return {}
    
    def get_tests_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all test scenarios for a category."""
        try:
            # Find suite for category
            suites = self.catalog.search_tests(category=category)
            if not suites:
                return []
            
            # Get scenarios for the first matching suite
            suite = suites[0]
            scenarios = self.catalog.get_test_scenarios(suite['id'])
            
            # Convert to test runner format
            tests = []
            for scenario in scenarios:
                test = {
                    'test_name': scenario['test_name'],
                    'description': scenario['description'],
                    'command': scenario['command'],
                    'expected_output_contains': scenario['expected_output_contains'],
                    'expected_output_not_contains': scenario['expected_output_not_contains'],
                    'expected_exit_code': scenario['expected_exit_code'],
                    'timeout': scenario['timeout'],
                    'collection_state': scenario['collection_state'],
                    'skip_if_no_servers': bool(scenario['skip_if_no_servers']),
                    'requires_specific_collection': scenario['requires_specific_collection']
                }
                tests.append(test)
            
            return tests
            
        except Exception as e:
            logger.error(f"Failed to get tests for category {category}: {e}")
            return []
    
    def search_tests(self, query: str = "", categories: List[str] = None, 
                    collection_compatible: bool = True) -> List[Dict[str, Any]]:
        """Search tests by query and filters."""
        try:
            compatibility = None
            if collection_compatible:
                # Search for collection-agnostic tests
                compatibility = {
                    'empty_state': True,
                    'npm_servers': True,
                    'docker_desktop_servers': True
                }
            
            # Search by command pattern if query provided
            command_pattern = query if query else None
            
            results = []
            for category in (categories or [None]):
                suites = self.catalog.search_tests(
                    category=category,
                    command_pattern=command_pattern,
                    compatibility=compatibility
                )
                results.extend(suites)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search tests: {e}")
            return []
    
    def get_collection_requirements(self, category: str) -> Dict[str, Any]:
        """Get collection requirements for a test category."""
        try:
            suites = self.catalog.search_tests(category=category)
            if not suites:
                return {"collection_type": "any", "min_servers": 0}
            
            suite = suites[0]
            return {
                "collection_type": suite['collection_type'],
                "min_servers": suite['min_servers'],
                "compatibility": {
                    "npm_servers": bool(suite['compatibility_npm']),
                    "docker_desktop_servers": bool(suite['compatibility_dd']),
                    "docker_hub_servers": bool(suite['compatibility_docker']),
                    "empty_state": bool(suite['compatibility_empty'])
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection requirements: {e}")
            return {"collection_type": "any", "min_servers": 0}
    
    def get_available_categories(self) -> List[str]:
        """Get list of available test categories."""
        try:
            suites = self.catalog.search_tests()
            categories = list(set(suite['category'] for suite in suites))
            return sorted(categories)
        except Exception as e:
            logger.error(f"Failed to get categories: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get test catalog statistics."""
        try:
            return self.catalog.get_statistics()
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}
    
    def refresh_catalog(self) -> bool:
        """Force refresh of the catalog from JSON files."""
        try:
            logger.info("🔄 Force refreshing test catalog...")
            success, total = self.catalog.index_all_test_files()
            logger.info(f"✅ Refreshed catalog: {success}/{total} files")
            return success > 0
        except Exception as e:
            logger.error(f"Failed to refresh catalog: {e}")
            return False
    
    def validate_test_integrity(self) -> Dict[str, Any]:
        """Validate that DB is in sync with JSON files."""
        results = {
            "in_sync": True,
            "missing_files": [],
            "modified_files": [],
            "orphaned_entries": []
        }
        
        try:
            # Check for missing or modified files
            suites = self.catalog.search_tests()
            for suite in suites:
                file_path = self.tests_dir.parent / suite['file_path']
                
                if not file_path.exists():
                    results["missing_files"].append(suite['file_path'])
                    results["in_sync"] = False
                else:
                    # Check if file hash matches
                    current_hash = self.catalog._calculate_file_hash(file_path)
                    if current_hash != suite['file_hash']:
                        results["modified_files"].append(suite['file_path'])
                        results["in_sync"] = False
            
            # Check for orphaned entries
            orphaned = self.catalog.cleanup_orphaned_entries()
            if orphaned > 0:
                results["orphaned_entries"] = orphaned
                results["in_sync"] = False
            
        except Exception as e:
            logger.error(f"Integrity check failed: {e}")
            results["error"] = str(e)
            results["in_sync"] = False
        
        return results


# Convenience function for menu integration
def get_hybrid_loader() -> HybridTestLoader:
    """Get a singleton hybrid test loader."""
    if not hasattr(get_hybrid_loader, '_instance'):
        get_hybrid_loader._instance = HybridTestLoader()
    return get_hybrid_loader._instance