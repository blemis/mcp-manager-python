"""
Server analysis orchestration for AI curation.

Coordinates server analysis using data collectors and scoring engines.
"""

from datetime import datetime
from typing import Optional

from mcp_manager.core.models import Server
from mcp_manager.utils.logging import get_logger

from ..models import ServerAnalysis
from .data_collector import DataCollector
from .scoring import ScoringEngine
from .cache_manager import AnalysisCacheManager

logger = get_logger(__name__)


class ServerAnalyzer:
    """Orchestrates comprehensive server analysis."""
    
    def __init__(self, manager):
        """Initialize server analyzer."""
        self.manager = manager
        self.data_collector = DataCollector()
        self.scoring_engine = ScoringEngine()
        self.cache_manager = AnalysisCacheManager()
    
    async def analyze_server(self, server_name: str, force_refresh: bool = False) -> Optional[ServerAnalysis]:
        """Analyze a specific MCP server for quality and suitability."""
        try:
            # Check cache first
            if not force_refresh and self.cache_manager.is_analysis_cached(server_name):
                logger.debug(f"Using cached analysis for {server_name}")
                return self.cache_manager.get_cached_analysis(server_name)
            
            # Get server details
            servers = self.manager.list_servers()
            server = next((s for s in servers if s.name == server_name), None)
            if not server:
                logger.warning(f"Server {server_name} not found")
                return None
            
            # Collect performance and compatibility data
            performance_data = await self.data_collector.collect_performance_data(server)
            compatibility_data = await self.data_collector.collect_compatibility_data(server)
            
            # Calculate all scores using scoring engine
            scores = await self.scoring_engine.calculate_all_scores(
                server, performance_data, compatibility_data
            )
            
            # Generate insights and detect conflicts
            insights = await self._generate_insights(server, performance_data, compatibility_data)
            conflicts = await self._detect_conflicts(server)
            
            # Create analysis result
            analysis = ServerAnalysis(
                server_name=server_name,
                reliability_score=scores['reliability'],
                performance_score=scores['performance'],
                compatibility_score=scores['compatibility'],
                functionality_score=scores['functionality'],
                documentation_score=scores['documentation'],
                maintenance_score=scores['maintenance'],
                overall_score=scores['overall'],
                insights=insights,
                conflicts=conflicts,
                last_analyzed=datetime.now().isoformat()
            )
            
            # Cache the analysis
            self.cache_manager.cache_analysis(server_name, analysis)
            
            logger.info(f"Completed analysis for {server_name} (score: {scores['overall']:.2f})")
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze server {server_name}: {e}")
            return None
    
    async def _generate_insights(self, server: Server, performance_data: dict, compatibility_data: dict) -> list:
        """Generate insights about the server."""
        insights = []
        
        # Performance insights
        if performance_data.get('avg_response_time', 0) > 5000:
            insights.append("Server shows slower response times (>5s average)")
        
        if performance_data.get('error_rate', 0) > 0.1:
            insights.append(f"Server has elevated error rate ({performance_data['error_rate']:.1%})")
        
        # Compatibility insights
        if compatibility_data.get('python_version_issues'):
            insights.append("May have Python version compatibility issues")
        
        if compatibility_data.get('missing_dependencies'):
            deps = compatibility_data['missing_dependencies']
            insights.append(f"Missing dependencies: {', '.join(deps[:3])}")
        
        # Server type insights
        if server.server_type.value == 'docker':
            insights.append("Docker-based server - requires Docker runtime")
        elif server.server_type.value == 'npm':
            insights.append("NPM-based server - requires Node.js runtime")
        
        return insights
    
    async def _detect_conflicts(self, server: Server) -> list:
        """Detect potential conflicts with other servers."""
        conflicts = []
        
        try:
            # Get all servers to check for conflicts
            all_servers = self.manager.list_servers()
            
            for other_server in all_servers:
                if other_server.name == server.name:
                    continue
                
                # Check for port conflicts
                if self._check_port_conflict(server, other_server):
                    conflicts.append(f"Port conflict with {other_server.name}")
                
                # Check for similar functionality
                if self._check_functionality_overlap(server, other_server):
                    conflicts.append(f"Similar functionality to {other_server.name}")
        
        except Exception as e:
            logger.warning(f"Failed to detect conflicts for {server.name}: {e}")
        
        return conflicts
    
    def _check_port_conflict(self, server1: Server, server2: Server) -> bool:
        """Check if two servers might have port conflicts."""
        # Simple heuristic - check if both servers use similar port arguments
        server1_args = ' '.join(server1.args)
        server2_args = ' '.join(server2.args)
        
        # Look for port patterns
        import re
        port_pattern = r'--port\s+(\d+)|:(\d+)'
        
        server1_ports = re.findall(port_pattern, server1_args)
        server2_ports = re.findall(port_pattern, server2_args)
        
        if server1_ports and server2_ports:
            # Flatten port tuples and filter out empty strings
            ports1 = [p for group in server1_ports for p in group if p]
            ports2 = [p for group in server2_ports for p in group if p]
            
            return bool(set(ports1) & set(ports2))
        
        return False
    
    def _check_functionality_overlap(self, server1: Server, server2: Server) -> bool:
        """Check if two servers have overlapping functionality."""
        # Simple name-based heuristic
        name1_parts = set(server1.name.lower().split('-'))
        name2_parts = set(server2.name.lower().split('-'))
        
        # Remove common words
        common_words = {'mcp', 'server', 'client', 'tool'}
        name1_parts -= common_words
        name2_parts -= common_words
        
        # Check for significant overlap
        if name1_parts and name2_parts:
            overlap = len(name1_parts & name2_parts)
            total = len(name1_parts | name2_parts)
            
            return overlap / total > 0.5
        
        return False