"""
Server discovery module for MCP Manager.

Provides modular discovery of MCP servers from various sources.
"""

from .server_discovery import ServerDiscovery
from .cache import CacheEntry
from .npm import NPMDiscovery
from .docker import DockerDiscovery
from .similarity import SimilarityDetector
from .helpers import PatternMatcher

__all__ = [
    'ServerDiscovery', 
    'CacheEntry', 
    'NPMDiscovery', 
    'DockerDiscovery', 
    'SimilarityDetector', 
    'PatternMatcher'
]