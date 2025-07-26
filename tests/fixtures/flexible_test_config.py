"""
Flexible Test Configuration System

Provides input-driven test collections with positive/negative/mixed MCP servers.
Tests accept collection specifications rather than hardcoding server configurations.
"""

from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass
from pathlib import Path
import json

TestServerType = Literal["positive", "negative", "mixed"]


@dataclass
class TestServerSpec:
    """Specification for a test MCP server."""
    name: str
    server_type: str  # "docker-desktop", "npm", "custom", etc.
    command: str
    test_type: TestServerType  # positive, negative, mixed
    description: str
    scope: str = "user"
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    expected_behavior: str = "working"  # "working", "fails", "timeout", etc.


@dataclass
class TestCollectionSpec:
    """Specification for a test collection (suite) of MCP servers."""
    collection_id: str
    name: str
    description: str
    category: str
    servers: List[TestServerSpec]
    test_scenarios: List[str]  # Which test scenarios this collection supports


class FlexibleTestConfig:
    """Manages flexible test configurations with positive/negative server combinations."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize with configuration file path."""
        self.config_path = config_path or Path(__file__).parent / "test_collections.json"
        self.collections: Dict[str, TestCollectionSpec] = {}
        self._load_collections()
    
    def _load_collections(self):
        """Load test collections from configuration file."""
        if not self.config_path.exists():
            self._create_default_collections()
            return
        
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
            
            for collection_data in data.get('test_collections', []):
                servers = [
                    TestServerSpec(**server_data) 
                    for server_data in collection_data.get('servers', [])
                ]
                
                collection = TestCollectionSpec(
                    collection_id=collection_data['collection_id'],
                    name=collection_data['name'],
                    description=collection_data['description'],
                    category=collection_data['category'],
                    servers=servers,
                    test_scenarios=collection_data.get('test_scenarios', [])
                )
                
                self.collections[collection.collection_id] = collection
                
        except Exception as e:
            print(f"Warning: Failed to load test collections: {e}")
            self._create_default_collections()
    
    def _create_default_collections(self):
        """Create default test collections with positive/negative/mixed servers."""
        # Positive servers collection - all working
        self.collections['positive-basic'] = TestCollectionSpec(
            collection_id='positive-basic',
            name='Basic Positive Collection',
            description='Working MCP servers for positive functionality testing',
            category='functionality',
            servers=[
                TestServerSpec(
                    name='test-filesystem',
                    server_type='docker-desktop',
                    command='docker-desktop://filesystem',
                    test_type='positive',
                    description='Working filesystem server',
                    expected_behavior='working'
                ),
                TestServerSpec(
                    name='test-sqlite',
                    server_type='docker-desktop', 
                    command='docker-desktop://SQLite',
                    test_type='positive',
                    description='Working SQLite server',
                    expected_behavior='working'
                )
            ],
            test_scenarios=['list', 'enable', 'disable', 'status']
        )
        
        # Negative servers collection - broken/invalid
        self.collections['negative-basic'] = TestCollectionSpec(
            collection_id='negative-basic',
            name='Basic Negative Collection',
            description='Broken MCP servers for error handling testing',
            category='error-handling',
            servers=[
                TestServerSpec(
                    name='test-invalid-command',
                    server_type='custom',
                    command='/nonexistent/command',
                    test_type='negative',
                    description='Server with invalid command',
                    expected_behavior='fails'
                ),
                TestServerSpec(
                    name='test-bad-args',
                    server_type='custom',
                    command='echo',
                    test_type='negative',
                    description='Server with problematic arguments',
                    args=['--invalid-flag'],
                    expected_behavior='fails'
                )
            ],
            test_scenarios=['add-failure', 'error-handling', 'cleanup']
        )
        
        # Mixed collection - combination of working and broken
        self.collections['mixed-comprehensive'] = TestCollectionSpec(
            collection_id='mixed-comprehensive',
            name='Mixed Comprehensive Collection',
            description='Mix of working and broken servers for comprehensive testing',
            category='comprehensive',
            servers=[
                TestServerSpec(
                    name='test-working-ref',
                    server_type='docker-desktop',
                    command='docker-desktop://Ref',
                    test_type='positive',
                    description='Working reference server',
                    expected_behavior='working'
                ),
                TestServerSpec(
                    name='test-failing-custom',
                    server_type='custom',
                    command='/bad/path/server',
                    test_type='negative', 
                    description='Intentionally failing server',
                    expected_behavior='fails'
                ),
                TestServerSpec(
                    name='test-timeout-server',
                    server_type='custom',
                    command='sleep',
                    test_type='negative',
                    description='Server that times out',
                    args=['30'],
                    expected_behavior='timeout'
                )
            ],
            test_scenarios=['mixed-operations', 'partial-success', 'error-recovery']
        )
        
        # Save default collections
        self._save_collections()
    
    def _save_collections(self):
        """Save collections to configuration file."""
        try:
            data = {
                'test_collections': [
                    {
                        'collection_id': collection.collection_id,
                        'name': collection.name,
                        'description': collection.description,
                        'category': collection.category,
                        'servers': [
                            {
                                'name': server.name,
                                'server_type': server.server_type,
                                'command': server.command,
                                'test_type': server.test_type,
                                'description': server.description,
                                'scope': server.scope,
                                'args': server.args,
                                'env': server.env,
                                'expected_behavior': server.expected_behavior
                            }
                            for server in collection.servers
                        ],
                        'test_scenarios': collection.test_scenarios
                    }
                    for collection in self.collections.values()
                ]
            }
            
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"Warning: Failed to save test collections: {e}")
    
    def get_collection(self, collection_id: str) -> Optional[TestCollectionSpec]:
        """Get a specific test collection."""
        return self.collections.get(collection_id)
    
    def get_collections_by_type(self, test_type: TestServerType) -> List[TestCollectionSpec]:
        """Get collections containing servers of a specific type."""
        result = []
        for collection in self.collections.values():
            if any(server.test_type == test_type for server in collection.servers):
                result.append(collection)
        return result
    
    def get_collections_by_category(self, category: str) -> List[TestCollectionSpec]:
        """Get collections by category."""
        return [
            collection for collection in self.collections.values() 
            if collection.category == category
        ]
    
    def list_available_collections(self) -> List[str]:
        """List all available collection IDs."""
        return list(self.collections.keys())
    
    def add_custom_collection(self, collection: TestCollectionSpec):
        """Add a custom test collection."""
        self.collections[collection.collection_id] = collection
        self._save_collections()
    
    def remove_collection(self, collection_id: str) -> bool:
        """Remove a test collection."""
        if collection_id in self.collections:
            del self.collections[collection_id]
            self._save_collections()
            return True
        return False


# Convenience functions
def get_positive_collection() -> TestCollectionSpec:
    """Get a collection with only working servers."""
    config = FlexibleTestConfig()
    return config.get_collection('positive-basic')


def get_negative_collection() -> TestCollectionSpec:
    """Get a collection with only broken servers."""
    config = FlexibleTestConfig()
    return config.get_collection('negative-basic')


def get_mixed_collection() -> TestCollectionSpec:
    """Get a collection with both working and broken servers."""
    config = FlexibleTestConfig()
    return config.get_collection('mixed-comprehensive')


def get_collection_for_test_scenario(scenario_name: str) -> Optional[TestCollectionSpec]:
    """Get the most appropriate collection for a test scenario."""
    config = FlexibleTestConfig()
    
    # Simple mapping of test scenarios to collection types
    scenario_mappings = {
        'help': 'positive-basic',
        'list': 'positive-basic', 
        'version': 'positive-basic',
        'add': 'mixed-comprehensive',
        'remove': 'mixed-comprehensive',
        'error-handling': 'negative-basic',
        'comprehensive': 'mixed-comprehensive'
    }
    
    collection_id = scenario_mappings.get(scenario_name.lower(), 'positive-basic')
    return config.get_collection(collection_id)