"""
Test data management for MCP Manager testing.

Professional test data lifecycle management with proper isolation.
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional
import uuid
import time


class TestDataManager:
    """Manage test data lifecycle and isolation."""
    
    def __init__(self, test_env):
        self.test_env = test_env
        self.data_dir = test_env.data_dir
        self.created_resources = {
            'suites': [],
            'servers': [],
            'quality_data': [],
            'temp_files': []
        }
        
        # Load static test data
        self.static_data = self._load_static_data()
    
    def _load_static_data(self) -> Dict[str, Any]:
        """Load static test data from files."""
        # Create static test data structure
        return {
            'valid_servers': [
                {
                    'name': 'test-filesystem',
                    'type': 'npm',
                    'command': 'npx @modelcontextprotocol/server-filesystem',
                    'args': ['--directory', '/tmp']
                },
                {
                    'name': 'test-sqlite',
                    'type': 'npm',
                    'command': 'npx @modelcontextprotocol/server-sqlite',
                    'args': ['--db-path', '/tmp/test.db']
                },
                {
                    'name': 'test-docker',
                    'type': 'docker',
                    'command': 'docker run mcp/server',
                    'args': []
                },
                {
                    'name': 'test-custom',
                    'type': 'custom',
                    'command': 'python test_server.py',
                    'args': ['--config', 'test.json']
                }
            ],
            'invalid_servers': [
                {
                    'name': '',  # Empty name
                    'type': 'custom',
                    'command': 'invalid'
                },
                {
                    'name': 'test-malformed',
                    'type': 'invalid-type',  # Invalid type
                    'command': ''  # Empty command
                }
            ],
            'sample_suites': [
                {
                    'name': 'development',
                    'description': 'Development tools suite',
                    'category': 'development',
                    'servers': ['filesystem', 'sqlite']
                },
                {
                    'name': 'production',
                    'description': 'Production monitoring suite',
                    'category': 'monitoring',
                    'servers': ['http', 'docker']
                }
            ]
        }
    
    def create_test_suite(self, name: Optional[str] = None, 
                         servers: Optional[List[str]] = None,
                         category: str = 'testing') -> Dict[str, Any]:
        """
        Create isolated test suite.
        
        Args:
            name: Suite name (auto-generated if None)
            servers: List of server names
            category: Suite category
            
        Returns:
            Suite configuration dictionary
        """
        if name is None:
            name = f"test-suite-{uuid.uuid4().hex[:8]}"
        
        if servers is None:
            servers = ['test-filesystem', 'test-sqlite']
        
        suite_config = {
            'name': name,
            'description': f'Test suite {name}',
            'category': category,
            'servers': servers,
            'created_at': time.time(),
            'test_id': uuid.uuid4().hex
        }
        
        # Save suite configuration
        suite_file = self.data_dir / f"suite_{name}.json"
        with open(suite_file, 'w') as f:
            json.dump(suite_config, f, indent=2)
        
        self.created_resources['suites'].append(name)
        self.created_resources['temp_files'].append(suite_file)
        
        return suite_config
    
    def create_test_server(self, name: Optional[str] = None,
                          server_type: str = 'custom') -> Dict[str, Any]:
        """
        Create isolated test server configuration.
        
        Args:
            name: Server name (auto-generated if None)
            server_type: Type of server (npm, docker, custom)
            
        Returns:
            Server configuration dictionary
        """
        if name is None:
            name = f"test-server-{uuid.uuid4().hex[:8]}"
        
        server_configs = {
            'npm': {
                'command': 'npx @test/server',
                'args': ['--test-mode']
            },
            'docker': {
                'command': 'docker run test/server',
                'args': []
            },
            'custom': {
                'command': 'python test_server.py',
                'args': ['--test']
            }
        }
        
        config = server_configs.get(server_type, server_configs['custom'])
        
        server_config = {
            'name': name,
            'type': server_type,
            'command': config['command'],
            'args': config['args'],
            'created_at': time.time(),
            'test_id': uuid.uuid4().hex
        }
        
        # Save server configuration
        server_file = self.data_dir / f"server_{name}.json"
        with open(server_file, 'w') as f:
            json.dump(server_config, f, indent=2)
        
        self.created_resources['servers'].append(name)
        self.created_resources['temp_files'].append(server_file)
        
        return server_config
    
    def generate_test_servers(self, count: int = 5, 
                            server_type: str = 'custom') -> List[Dict[str, Any]]:
        """
        Generate multiple test server configurations.
        
        Args:
            count: Number of servers to generate
            server_type: Type of servers to generate
            
        Returns:
            List of server configurations
        """
        servers = []
        for i in range(count):
            server = self.create_test_server(
                name=f"bulk-test-server-{i+1}",
                server_type=server_type
            )
            servers.append(server)
        
        return servers
    
    def create_quality_test_data(self, server_name: str) -> Dict[str, Any]:
        """Create test quality tracking data for a server."""
        quality_data = {
            'server_name': server_name,
            'install_id': f"test-{server_name}",
            'metrics': {
                'install_success_rate': 0.95,
                'performance_score': 85.5,
                'reliability_score': 90.0,
                'user_rating': 4.2
            },
            'feedback': [
                {
                    'rating': 4,
                    'comment': 'Works well for testing',
                    'timestamp': time.time()
                },
                {
                    'rating': 5,
                    'comment': 'Excellent performance',
                    'timestamp': time.time() - 3600
                }
            ],
            'created_at': time.time(),
            'test_id': uuid.uuid4().hex
        }
        
        quality_file = self.data_dir / f"quality_{server_name}.json"
        with open(quality_file, 'w') as f:
            json.dump(quality_data, f, indent=2)
        
        self.created_resources['quality_data'].append(server_name)
        self.created_resources['temp_files'].append(quality_file)
        
        return quality_data
    
    def create_discovery_mock_data(self) -> Dict[str, Any]:
        """Create mock discovery data for testing."""
        discovery_data = {
            'npm_servers': [
                {
                    'name': '@modelcontextprotocol/server-filesystem',
                    'install_id': 'mcp-filesystem',
                    'description': 'Filesystem MCP server',
                    'type': 'npm'
                },
                {
                    'name': '@modelcontextprotocol/server-sqlite',
                    'install_id': 'mcp-sqlite',
                    'description': 'SQLite MCP server',
                    'type': 'npm'
                }
            ],
            'docker_servers': [
                {
                    'name': 'mcp/filesystem',
                    'install_id': 'dd-filesystem',
                    'description': 'Docker filesystem server',
                    'type': 'docker'
                }
            ],
            'created_at': time.time()
        }
        
        discovery_file = self.data_dir / "discovery_mock.json"
        with open(discovery_file, 'w') as f:
            json.dump(discovery_data, f, indent=2)
        
        self.created_resources['temp_files'].append(discovery_file)
        
        return discovery_data
    
    def get_server_by_type(self, server_type: str) -> Dict[str, Any]:
        """Get a valid server configuration by type."""
        for server in self.static_data['valid_servers']:
            if server['type'] == server_type:
                return server.copy()
        
        # Fallback to creating one
        return self.create_test_server(server_type=server_type)
    
    def get_invalid_server(self) -> Dict[str, Any]:
        """Get an invalid server configuration for error testing."""
        return self.static_data['invalid_servers'][0].copy()
    
    def cleanup_test_data(self):
        """Clean up all test artifacts."""
        # Remove temporary files
        for temp_file in self.created_resources['temp_files']:
            try:
                if isinstance(temp_file, Path) and temp_file.exists():
                    temp_file.unlink()
            except Exception:
                pass  # Ignore cleanup errors
        
        # Clear tracking
        self.created_resources = {
            'suites': [],
            'servers': [],
            'quality_data': [],
            'temp_files': []
        }
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup_test_data()