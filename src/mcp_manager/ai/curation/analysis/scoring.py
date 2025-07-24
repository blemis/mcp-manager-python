"""
Scoring Module for AI Curation Analysis.

Handles all scoring calculations for MCP server analysis including reliability,
performance, compatibility, functionality, documentation, and maintenance scores.
"""

from typing import Dict, Any, List
import math

from mcp_manager.core.models import Server, ServerType
from mcp_manager.ai.curation.analysis.data_collector import PerformanceData, CompatibilityData
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ServerScorer:
    """Calculates various quality scores for MCP servers."""
    
    # Scoring weights for overall score calculation
    SCORE_WEIGHTS = {
        "reliability": 0.25,
        "performance": 0.20,
        "compatibility": 0.20,
        "functionality": 0.15,
        "documentation": 0.10,
        "maintenance": 0.10
    }
    
    def calculate_overall_score(self, scores: Dict[str, float]) -> float:
        """Calculate weighted overall score from individual scores."""
        try:
            overall = sum(
                scores.get(category, 0.5) * weight 
                for category, weight in self.SCORE_WEIGHTS.items()
            )
            return min(1.0, max(0.0, overall))
            
        except Exception as e:
            logger.error(f"Failed to calculate overall score: {e}")
            return 0.5
    
    def calculate_reliability_score(self, server: Server, performance_data: PerformanceData) -> float:
        """Calculate reliability score based on success rate and uptime."""
        try:
            success_rate = performance_data.success_rate
            uptime = performance_data.uptime
            
            # Weight success rate more heavily than uptime
            score = (success_rate * 0.7) + (uptime * 0.3)
            
            # Apply server type modifier
            score = self._apply_server_type_reliability_modifier(server, score)
            
            return min(1.0, max(0.0, score))
            
        except Exception as e:
            logger.error(f"Failed to calculate reliability score for {server.name}: {e}")
            return 0.5
    
    def calculate_performance_score(self, performance_data: PerformanceData) -> float:
        """Calculate performance score based on response times."""
        try:
            avg_response_time = performance_data.avg_response_time
            
            # Score based on response time (lower is better)
            if avg_response_time < 200:
                score = 1.0
            elif avg_response_time < 500:
                score = 0.9
            elif avg_response_time < 1000:
                score = 0.8
            elif avg_response_time < 2000:
                score = 0.6
            elif avg_response_time < 5000:
                score = 0.4
            else:
                score = 0.2
            
            # Factor in success rate for performance
            success_factor = min(1.0, performance_data.success_rate + 0.2)
            score *= success_factor
            
            return min(1.0, max(0.0, score))
            
        except Exception as e:
            logger.error(f"Failed to calculate performance score: {e}")
            return 0.5
    
    def calculate_compatibility_score(self, compatibility_data: CompatibilityData) -> float:
        """Calculate compatibility score."""
        try:
            score = 0.0
            
            # Claude compatibility is most important
            if compatibility_data.claude_compatible:
                score += 0.4
            
            # Installation success
            if compatibility_data.installation_success:
                score += 0.3
            
            # Dependencies met
            if compatibility_data.dependencies_met:
                score += 0.2
            
            # Bonus for not requiring configuration (ease of use)
            if not compatibility_data.configuration_required:
                score += 0.1
            
            return min(1.0, max(0.0, score))
            
        except Exception as e:
            logger.error(f"Failed to calculate compatibility score: {e}")
            return 0.5
    
    def calculate_functionality_score(self, server: Server, tool_count: int) -> float:
        """Calculate functionality score based on available tools and server characteristics."""
        try:
            # Base score from tool count
            if tool_count >= 25:
                base_score = 1.0
            elif tool_count >= 15:
                base_score = 0.9
            elif tool_count >= 10:
                base_score = 0.8
            elif tool_count >= 5:
                base_score = 0.6
            elif tool_count >= 1:
                base_score = 0.4
            else:
                base_score = 0.2
            
            # Apply functionality modifiers based on server name
            modifier = self._get_functionality_modifier(server)
            score = base_score * modifier
            
            return min(1.0, max(0.0, score))
            
        except Exception as e:
            logger.error(f"Failed to calculate functionality score for {server.name}: {e}")
            return 0.5
    
    def calculate_documentation_score(self, server: Server) -> float:
        """Calculate documentation score based on description quality."""
        try:
            description = getattr(server, 'description', '') or ''
            description_length = len(description.strip())
            
            # Base score from description length
            if description_length > 200:
                base_score = 1.0
            elif description_length > 100:
                base_score = 0.9
            elif description_length > 50:
                base_score = 0.7
            elif description_length > 20:
                base_score = 0.5
            elif description_length > 0:
                base_score = 0.3
            else:
                base_score = 0.1
            
            # Quality indicators in description
            quality_indicators = [
                'example', 'usage', 'configure', 'install',
                'api', 'documentation', 'guide', 'tutorial'
            ]
            
            description_lower = description.lower()
            quality_bonus = sum(0.05 for indicator in quality_indicators 
                              if indicator in description_lower)
            
            score = min(1.0, base_score + quality_bonus)
            return max(0.0, score)
            
        except Exception as e:
            logger.error(f"Failed to calculate documentation score for {server.name}: {e}")
            return 0.5
    
    def calculate_maintenance_score(self, server: Server) -> float:
        """Calculate maintenance score based on server type and characteristics."""
        try:
            # Base scores by server type (based on typical maintenance quality)
            type_scores = {
                ServerType.DOCKER_DESKTOP: 0.9,  # Well maintained by Docker
                ServerType.NPM: 0.7,  # Community maintained, variable quality
                ServerType.DOCKER: 0.6,  # Variable quality
                ServerType.CUSTOM: 0.5   # Unknown maintenance
            }
            
            base_score = type_scores.get(server.server_type, 0.5)
            
            # Modifiers based on server name (popular packages likely better maintained)
            maintenance_modifier = self._get_maintenance_modifier(server)
            score = base_score * maintenance_modifier
            
            return min(1.0, max(0.0, score))
            
        except Exception as e:
            logger.error(f"Failed to calculate maintenance score for {server.name}: {e}")
            return 0.5
    
    def calculate_confidence_score(self, primary_servers: List[str], 
                                 server_scores: Dict[str, float]) -> float:
        """Calculate confidence score for a suite recommendation."""
        try:
            if not primary_servers:
                return 0.0
            
            # Get scores for primary servers
            primary_scores = [
                server_scores.get(server, 0.5) 
                for server in primary_servers
            ]
            
            if not primary_scores:
                return 0.0
            
            # Average score of primary servers
            avg_score = sum(primary_scores) / len(primary_scores)
            
            # Confidence decreases with too many servers (complexity penalty)
            complexity_penalty = max(0.8, 1.0 - (len(primary_servers) - 3) * 0.1)
            
            # Confidence increases with consistent scores (less variance)
            if len(primary_scores) > 1:
                variance = sum((score - avg_score) ** 2 for score in primary_scores) / len(primary_scores)
                consistency_bonus = max(0.9, 1.0 - variance)
            else:
                consistency_bonus = 1.0
            
            confidence = avg_score * complexity_penalty * consistency_bonus
            return min(1.0, max(0.0, confidence))
            
        except Exception as e:
            logger.error(f"Failed to calculate confidence score: {e}")
            return 0.5
    
    def _apply_server_type_reliability_modifier(self, server: Server, score: float) -> float:
        """Apply server type-specific reliability modifiers."""
        modifiers = {
            ServerType.DOCKER_DESKTOP: 1.1,  # Generally more reliable
            ServerType.NPM: 1.0,  # Baseline
            ServerType.DOCKER: 0.95,  # Slightly less reliable
            ServerType.CUSTOM: 0.9   # Unknown reliability
        }
        
        modifier = modifiers.get(server.server_type, 1.0)
        return score * modifier
    
    def _get_functionality_modifier(self, server: Server) -> float:
        """Get functionality modifier based on server characteristics."""
        name_lower = server.name.lower()
        
        # High-functionality server indicators
        high_functionality = [
            'playwright', 'browser', 'filesystem', 'database',
            'search', 'api', 'web', 'git', 'docker'
        ]
        
        # Specialized but limited functionality
        specialized = [
            'sqlite', 'postgres', 'redis', 'mongodb'
        ]
        
        if any(term in name_lower for term in high_functionality):
            return 1.1
        elif any(term in name_lower for term in specialized):
            return 0.95
        else:
            return 1.0
    
    def _get_maintenance_modifier(self, server: Server) -> float:
        """Get maintenance modifier based on server popularity and characteristics."""
        name_lower = server.name.lower()
        
        # Well-known, likely well-maintained packages/servers
        well_maintained = [
            'playwright', 'filesystem', 'sqlite', 'postgres',
            'docker', 'kubernetes', 'git', 'search'
        ]
        
        # Less common or newer packages
        experimental = [
            'experimental', 'beta', 'alpha', 'test', 'dev'
        ]
        
        if any(term in name_lower for term in well_maintained):
            return 1.2
        elif any(term in name_lower for term in experimental):
            return 0.8
        else:
            return 1.0