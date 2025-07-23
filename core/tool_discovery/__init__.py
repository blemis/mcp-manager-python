"""
Tool discovery module for MCP Manager.

Provides modular tool discovery services for different server types
including NPM, Docker, Docker Desktop, and custom servers.
"""

from .aggregator import AggregatedDiscoveryResult, ToolDiscoveryAggregator
from .base import BaseToolDiscovery, DiscoveryConfig, ToolDiscoveryResult
from .docker_desktop_discovery import DockerDesktopToolDiscovery
from .docker_discovery import DockerToolDiscovery
from .npm_discovery import NPMToolDiscovery

__all__ = [
    "BaseToolDiscovery",
    "DiscoveryConfig", 
    "ToolDiscoveryResult",
    "ToolDiscoveryAggregator",
    "AggregatedDiscoveryResult",
    "NPMToolDiscovery",
    "DockerToolDiscovery", 
    "DockerDesktopToolDiscovery"
]