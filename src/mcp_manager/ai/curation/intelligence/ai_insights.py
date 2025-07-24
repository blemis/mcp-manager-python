"""
AI Insights Module for AI Curation Intelligence.

Provides AI-powered insights about server strengths, weaknesses, and use cases
with fallback to heuristic analysis when AI services are unavailable.
"""

from typing import List, Tuple, Dict, Any, Optional

from mcp_manager.core.models import Server, ServerType
from mcp_manager.core.ai_config import ai_config_manager
from mcp_manager.ai.curation.models import TaskCategory
from mcp_manager.ai.curation.analysis.data_collector import PerformanceData, CompatibilityData
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class AIInsightsGenerator:
    """Generates AI-powered insights about MCP servers."""
    
    def __init__(self):
        self.ai_config = ai_config_manager
    
    async def generate_insights(self, server: Server, performance_data: PerformanceData, 
                              compatibility_data: CompatibilityData) -> Tuple[List[str], List[str], List[TaskCategory]]:
        """Generate AI insights about server strengths, weaknesses, and use cases."""
        try:
            # Try AI-powered analysis first
            if self._is_ai_available():
                return await self._generate_ai_insights(server, performance_data, compatibility_data)
            else:
                logger.debug(f"AI not available, using heuristic analysis for {server.name}")
                return self._generate_heuristic_insights(server, performance_data, compatibility_data)
                
        except Exception as e:
            logger.error(f"Failed to generate insights for {server.name}: {e}")
            return self._generate_fallback_insights(server)
    
    async def generate_suite_reasoning(self, category: TaskCategory, servers: List[str], 
                                     analyses: Dict[str, Any]) -> str:
        """Generate human-readable reasoning for suite recommendations."""
        try:
            if not servers:
                return "No suitable servers found for this task category."
            
            # Try AI-powered reasoning first
            if self._is_ai_available():
                return await self._generate_ai_reasoning(category, servers, analyses)
            else:
                return self._generate_heuristic_reasoning(category, servers, analyses)
                
        except Exception as e:
            logger.error(f"Failed to generate reasoning for {category.value}: {e}")
            return self._generate_fallback_reasoning(category, servers)
    
    def _is_ai_available(self) -> bool:
        """Check if AI services are available and enabled."""
        try:
            config = self.ai_config.load_config()
            primary_provider = self.ai_config.get_primary_provider()
            return config.enabled and primary_provider is not None
        except Exception:
            return False
    
    async def _generate_ai_insights(self, server: Server, performance_data: PerformanceData, 
                                  compatibility_data: CompatibilityData) -> Tuple[List[str], List[str], List[TaskCategory]]:
        """Generate insights using AI services (placeholder for future implementation)."""
        try:
            # TODO: Implement actual AI analysis when AI client is available
            # This would involve:
            # 1. Prepare structured prompt with server data
            # 2. Call AI service for analysis
            # 3. Parse AI response into strengths, weaknesses, categories
            
            logger.debug(f"AI insights not yet implemented, falling back to heuristics for {server.name}")
            return self._generate_heuristic_insights(server, performance_data, compatibility_data)
            
        except Exception as e:
            logger.error(f"AI insights generation failed for {server.name}: {e}")
            return self._generate_heuristic_insights(server, performance_data, compatibility_data)
    
    async def _generate_ai_reasoning(self, category: TaskCategory, servers: List[str], 
                                   analyses: Dict[str, Any]) -> str:
        """Generate reasoning using AI services (placeholder for future implementation)."""
        try:
            # TODO: Implement actual AI reasoning when AI client is available
            logger.debug(f"AI reasoning not yet implemented, falling back to heuristics for {category.value}")
            return self._generate_heuristic_reasoning(category, servers, analyses)
            
        except Exception as e:
            logger.error(f"AI reasoning generation failed for {category.value}: {e}")
            return self._generate_fallback_reasoning(category, servers)
    
    def _generate_heuristic_insights(self, server: Server, performance_data: PerformanceData, 
                                   compatibility_data: CompatibilityData) -> Tuple[List[str], List[str], List[TaskCategory]]:
        """Generate insights using heuristic analysis."""
        strengths = []
        weaknesses = []
        recommended_for = []
        
        name_lower = server.name.lower()
        
        # Analyze performance-based strengths
        if performance_data.success_rate > 0.95:
            strengths.append("Exceptional reliability")
        elif performance_data.success_rate > 0.90:
            strengths.append("High reliability")
        
        if performance_data.avg_response_time < 500:
            strengths.append("Fast response times")
        elif performance_data.avg_response_time < 1000:
            strengths.append("Good response times")
        
        if performance_data.tool_count > 15:
            strengths.append("Rich functionality")
        elif performance_data.tool_count > 10:
            strengths.append("Good functionality")
        elif performance_data.tool_count > 5:
            strengths.append("Moderate functionality")
        
        # Analyze performance-based weaknesses
        if performance_data.success_rate < 0.80:
            weaknesses.append("Reliability concerns")
        elif performance_data.success_rate < 0.90:
            weaknesses.append("Occasional reliability issues")
        
        if performance_data.avg_response_time > 3000:
            weaknesses.append("Slow response times")
        elif performance_data.avg_response_time > 2000:
            weaknesses.append("Moderate response times")
        
        if performance_data.tool_count < 3:
            weaknesses.append("Limited functionality")
        
        # Analyze compatibility-based characteristics
        if compatibility_data.configuration_required:
            weaknesses.append("Requires configuration")
        else:
            strengths.append("Easy to set up")
        
        if not compatibility_data.dependencies_met:
            weaknesses.append("Complex dependencies")
        
        if compatibility_data.claude_compatible:
            strengths.append("Claude optimized")
        
        # Determine recommended use cases based on name patterns and characteristics
        recommended_for = self._categorize_by_name_patterns(name_lower)
        
        # Add categories based on server type if no patterns matched
        if not recommended_for:
            recommended_for = self._categorize_by_server_type(server.server_type)
        
        return strengths, weaknesses, recommended_for
    
    def _categorize_by_name_patterns(self, name_lower: str) -> List[TaskCategory]:
        """Categorize server based on name patterns."""
        categories = []
        
        # File system related
        if any(term in name_lower for term in ["filesystem", "file", "directory", "folder"]):
            categories.extend([TaskCategory.FILE_MANAGEMENT, TaskCategory.AUTOMATION])
        
        # Database related
        if any(term in name_lower for term in ["sqlite", "database", "db", "postgres", "mysql", "mongo"]):
            categories.extend([TaskCategory.DATABASE_WORK, TaskCategory.DATA_ANALYSIS])
        
        # Web and browser related
        if any(term in name_lower for term in ["web", "http", "browser", "playwright", "chrome", "firefox"]):
            categories.extend([TaskCategory.WEB_DEVELOPMENT, TaskCategory.TESTING])
        
        # Search and research related
        if any(term in name_lower for term in ["search", "google", "brave", "bing"]):
            categories.extend([TaskCategory.RESEARCH, TaskCategory.CONTENT_CREATION])
        
        # Version control related
        if any(term in name_lower for term in ["git", "github", "gitlab", "svn"]):
            categories.extend([TaskCategory.WEB_DEVELOPMENT, TaskCategory.AUTOMATION])
        
        # Infrastructure and DevOps
        if any(term in name_lower for term in ["kubernetes", "k8s", "docker", "aws", "terraform"]):
            categories.extend([TaskCategory.SYSTEM_ADMIN, TaskCategory.AUTOMATION])
        
        # API related
        if any(term in name_lower for term in ["api", "rest", "graphql", "endpoint"]):
            categories.extend([TaskCategory.API_DEVELOPMENT, TaskCategory.WEB_DEVELOPMENT])
        
        # Testing related
        if any(term in name_lower for term in ["test", "testing", "qa", "selenium"]):
            categories.extend([TaskCategory.TESTING, TaskCategory.WEB_DEVELOPMENT])
        
        # Content and documentation
        if any(term in name_lower for term in ["content", "document", "markdown", "pdf"]):
            categories.extend([TaskCategory.CONTENT_CREATION, TaskCategory.FILE_MANAGEMENT])
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(categories))
    
    def _categorize_by_server_type(self, server_type: ServerType) -> List[TaskCategory]:
        """Provide default categories based on server type."""
        type_categories = {
            ServerType.DOCKER_DESKTOP: [TaskCategory.WEB_DEVELOPMENT, TaskCategory.AUTOMATION],
            ServerType.NPM: [TaskCategory.WEB_DEVELOPMENT, TaskCategory.AUTOMATION],
            ServerType.DOCKER: [TaskCategory.SYSTEM_ADMIN, TaskCategory.AUTOMATION],
            ServerType.CUSTOM: [TaskCategory.AUTOMATION]
        }
        
        return type_categories.get(server_type, [TaskCategory.AUTOMATION])
    
    def _generate_heuristic_reasoning(self, category: TaskCategory, servers: List[str], 
                                    analyses: Dict[str, Any]) -> str:
        """Generate human-readable reasoning using heuristic analysis."""
        try:
            if not servers:
                return f"No suitable servers found for {category.value.replace('_', ' ')} tasks."
            
            reasoning_parts = [
                f"For {category.value.replace('_', ' ')} tasks, I recommend the following MCP servers:"
            ]
            
            # Analyze top servers (limit to 3 for readability)
            top_servers = servers[:3]
            
            for i, server_name in enumerate(top_servers, 1):
                analysis = analyses.get(server_name)
                if analysis:
                    score = getattr(analysis, 'overall_score', 0.5)
                    strengths = getattr(analysis, 'strengths', [])
                    
                    # Describe score quality
                    if score > 0.9:
                        quality = "excellent"
                    elif score > 0.8:
                        quality = "very good"
                    elif score > 0.7:
                        quality = "good"
                    else:
                        quality = "acceptable"
                    
                    # Use top strengths for description
                    strength_text = ", ".join(strengths[:2]) if strengths else "reliable functionality"
                    
                    reasoning_parts.append(f"{i}. {server_name}: {quality} choice offering {strength_text}")
            
            # Add summary
            reasoning_parts.append(
                f"This combination provides comprehensive coverage for {category.value.replace('_', ' ')} "
                "tasks while maintaining good performance and compatibility."
            )
            
            return " ".join(reasoning_parts)
            
        except Exception as e:
            logger.error(f"Failed to generate heuristic reasoning: {e}")
            return self._generate_fallback_reasoning(category, servers)
    
    def _generate_fallback_insights(self, server: Server) -> Tuple[List[str], List[str], List[TaskCategory]]:
        """Generate minimal fallback insights when all other methods fail."""
        strengths = ["Functional server"]
        weaknesses = ["Limited analysis available"]
        recommended_for = [TaskCategory.AUTOMATION]  # Safe default
        
        return strengths, weaknesses, recommended_for
    
    def _generate_fallback_reasoning(self, category: TaskCategory, servers: List[str]) -> str:
        """Generate minimal fallback reasoning when analysis fails."""
        if not servers:
            return f"No servers available for {category.value.replace('_', ' ')} tasks."
        
        server_list = ", ".join(servers[:3])
        return (f"Based on available servers ({server_list}), "
                f"this selection should provide basic functionality for {category.value.replace('_', ' ')} tasks.")