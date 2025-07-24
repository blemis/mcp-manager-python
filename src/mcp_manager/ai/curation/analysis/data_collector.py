"""
Data Collection Module for AI Curation Analysis.

Handles performance and compatibility data collection for MCP server analysis.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass

from mcp_manager.core.models import Server, ServerType
from mcp_manager.core.simple_manager import SimpleMCPManager
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceData:
    """Performance metrics for a server."""
    avg_response_time: float  # milliseconds
    success_rate: float  # 0-1
    uptime: float  # 0-1
    tool_count: int
    last_used: Optional[str]


@dataclass
class CompatibilityData:
    """Compatibility information for a server."""
    claude_compatible: bool
    installation_success: bool
    configuration_required: bool
    dependencies_met: bool


class DataCollector:
    """Collects performance and compatibility data for MCP servers."""
    
    def __init__(self, manager: Optional[SimpleMCPManager] = None):
        self.manager = manager or SimpleMCPManager()
    
    async def collect_performance_data(self, server: Server) -> PerformanceData:
        """Collect performance metrics for a server."""
        try:
            logger.debug(f"Collecting performance data for {server.name}")
            
            # Initialize with default values
            performance_data = PerformanceData(
                avg_response_time=1000.0,  # Default 1 second
                success_rate=0.95,
                uptime=0.98,
                tool_count=0,
                last_used=None
            )
            
            # Try to get actual tool count
            try:
                tool_count = await self.manager.discover_and_register_server_tools(server)
                performance_data.tool_count = tool_count
                logger.debug(f"Discovered {tool_count} tools for {server.name}")
            except Exception as e:
                logger.debug(f"Could not discover tools for {server.name}: {e}")
            
            # TODO: Integrate with analytics service when available
            # For now, use performance heuristics based on server type
            performance_data = self._apply_server_type_heuristics(server, performance_data)
            
            return performance_data
            
        except Exception as e:
            logger.error(f"Failed to collect performance data for {server.name}: {e}")
            return self._get_default_performance_data()
    
    async def collect_compatibility_data(self, server: Server) -> CompatibilityData:
        """Collect compatibility information for a server."""
        try:
            logger.debug(f"Collecting compatibility data for {server.name}")
            
            compatibility_data = CompatibilityData(
                claude_compatible=True,  # Assume compatible if server is running
                installation_success=True,
                configuration_required=False,
                dependencies_met=True
            )
            
            # Determine configuration requirements based on server type
            compatibility_data.configuration_required = self._requires_configuration(server)
            
            # Check for known compatibility issues
            compatibility_data = self._check_compatibility_issues(server, compatibility_data)
            
            return compatibility_data
            
        except Exception as e:
            logger.error(f"Failed to collect compatibility data for {server.name}: {e}")
            return self._get_default_compatibility_data()
    
    def _apply_server_type_heuristics(self, server: Server, data: PerformanceData) -> PerformanceData:
        """Apply performance heuristics based on server type."""
        try:
            # Docker Desktop servers are typically well-optimized
            if server.server_type == ServerType.DOCKER_DESKTOP:
                data.avg_response_time = min(data.avg_response_time, 800.0)
                data.success_rate = max(data.success_rate, 0.97)
                data.uptime = max(data.uptime, 0.99)
            
            # NPM servers can vary in quality
            elif server.server_type == ServerType.NPM:
                # Popular NPM packages might perform better
                if any(term in server.name.lower() for term in ["playwright", "filesystem", "sqlite"]):
                    data.success_rate = max(data.success_rate, 0.95)
                else:
                    data.avg_response_time *= 1.2  # Slightly slower for unknown packages
            
            # Docker Hub servers are variable quality
            elif server.server_type == ServerType.DOCKER:
                data.avg_response_time *= 1.3  # Generally slower startup
                data.success_rate *= 0.95  # Slightly less reliable
            
        except Exception as e:
            logger.debug(f"Failed to apply heuristics for {server.name}: {e}")
        
        return data
    
    def _requires_configuration(self, server: Server) -> bool:
        """Determine if a server typically requires configuration."""
        # NPM and Docker servers often need configuration
        if server.server_type in [ServerType.NPM, ServerType.DOCKER]:
            return True
        
        # Check server name for configuration indicators
        name_lower = server.name.lower()
        config_indicators = [
            "api", "key", "token", "auth", "config",
            "database", "db", "postgres", "mysql",
            "filesystem", "directory", "path"
        ]
        
        return any(indicator in name_lower for indicator in config_indicators)
    
    def _check_compatibility_issues(self, server: Server, data: CompatibilityData) -> CompatibilityData:
        """Check for known compatibility issues."""
        try:
            name_lower = server.name.lower()
            
            # Servers that might have dependency issues
            dependency_sensitive = [
                "postgres", "mysql", "mongodb",
                "elasticsearch", "redis",
                "tensorflow", "pytorch"
            ]
            
            if any(dep in name_lower for dep in dependency_sensitive):
                data.dependencies_met = False
                data.configuration_required = True
            
            # Servers that are known to work well with Claude
            claude_optimized = [
                "filesystem", "sqlite", "browser",
                "playwright", "search", "git"
            ]
            
            if any(opt in name_lower for opt in claude_optimized):
                data.claude_compatible = True
            
        except Exception as e:
            logger.debug(f"Failed to check compatibility for {server.name}: {e}")
        
        return data
    
    def _get_default_performance_data(self) -> PerformanceData:
        """Get default performance data for fallback."""
        return PerformanceData(
            avg_response_time=2000.0,
            success_rate=0.5,
            uptime=0.5,
            tool_count=0,
            last_used=None
        )
    
    def _get_default_compatibility_data(self) -> CompatibilityData:
        """Get default compatibility data for fallback."""
        return CompatibilityData(
            claude_compatible=False,
            installation_success=False,
            configuration_required=True,
            dependencies_met=False
        )
    
    async def get_analytics_data(self, server: Server) -> Dict[str, Any]:
        """Get analytics data from external services (placeholder for future integration)."""
        try:
            # TODO: Integrate with actual analytics service
            # This is a placeholder for future analytics integration
            analytics_data = {
                "usage_count": 0,
                "error_rate": 0.05,
                "last_error": None,
                "performance_trend": "stable"
            }
            
            logger.debug(f"Retrieved analytics data for {server.name}")
            return analytics_data
            
        except Exception as e:
            logger.debug(f"Failed to get analytics data for {server.name}: {e}")
            return {}