"""
AI-Driven MCP Suite Curation Engine.

Provides intelligent analysis and recommendations for MCP server
suites based on task requirements, compatibility, and performance.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from mcp_manager.core.ai_config import ai_config_manager, AIProvider
from mcp_manager.core.simple_manager import SimpleMCPManager
from mcp_manager.core.models import Server, ServerType
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class TaskCategory(str, Enum):
    """Categories of tasks for MCP suite recommendations."""
    WEB_DEVELOPMENT = "web_development"
    DATA_ANALYSIS = "data_analysis"
    SYSTEM_ADMIN = "system_admin"
    CONTENT_CREATION = "content_creation"
    API_DEVELOPMENT = "api_development"
    DATABASE_WORK = "database_work"
    FILE_MANAGEMENT = "file_management"
    AUTOMATION = "automation"
    RESEARCH = "research"
    TESTING = "testing"


class CurationCriteria(str, Enum):
    """Criteria for evaluating MCP server quality."""
    RELIABILITY = "reliability"
    PERFORMANCE = "performance"
    COMPATIBILITY = "compatibility"
    FUNCTIONALITY = "functionality"
    DOCUMENTATION = "documentation"
    MAINTENANCE = "maintenance"


@dataclass
class ServerAnalysis:
    """Analysis results for a specific MCP server."""
    server_name: str
    server_type: ServerType
    reliability_score: float  # 0-1 based on success rate and uptime
    performance_score: float  # 0-1 based on response times
    compatibility_score: float  # 0-1 based on integration success
    functionality_score: float  # 0-1 based on tool count and usefulness
    documentation_score: float  # 0-1 based on description quality
    maintenance_score: float  # 0-1 based on update frequency
    overall_score: float  # Weighted average of all scores
    strengths: List[str]
    weaknesses: List[str]
    recommended_for: List[TaskCategory]
    conflicts_with: List[str]  # Server names that conflict


@dataclass
class SuiteRecommendation:
    """Recommendation for a complete MCP suite."""
    task_category: TaskCategory
    primary_servers: List[str]  # Essential servers
    optional_servers: List[str]  # Nice-to-have servers
    alternative_servers: Dict[str, List[str]]  # Alternatives for each primary
    configuration_hints: Dict[str, Any]  # Configuration recommendations
    expected_conflicts: List[str]  # Known conflict warnings
    confidence_score: float  # 0-1 confidence in recommendation
    reasoning: str  # AI-generated explanation


class AICurationEngine:
    """AI-powered curation engine for MCP server analysis and recommendations."""
    
    def __init__(self, manager: Optional[SimpleMCPManager] = None):
        self.manager = manager or SimpleMCPManager()
        self.ai_config = ai_config_manager
        self._analysis_cache: Dict[str, ServerAnalysis] = {}
        self._cache_expiry: Dict[str, datetime] = {}
        self.cache_duration = timedelta(hours=6)  # Cache analysis for 6 hours
        
    async def analyze_server(self, server_name: str, force_refresh: bool = False) -> Optional[ServerAnalysis]:
        """Analyze a specific MCP server for quality and suitability."""
        try:
            # Check cache first
            if not force_refresh and self._is_analysis_cached(server_name):
                logger.debug(f"Using cached analysis for {server_name}")
                return self._analysis_cache[server_name]
            
            # Get server details
            servers = self.manager.list_servers()
            server = next((s for s in servers if s.name == server_name), None)
            if not server:
                logger.warning(f"Server {server_name} not found")
                return None
            
            # Collect performance data
            performance_data = await self._collect_performance_data(server)
            compatibility_data = await self._collect_compatibility_data(server)
            
            # Calculate scores
            reliability_score = self._calculate_reliability_score(server, performance_data)
            performance_score = self._calculate_performance_score(performance_data)
            compatibility_score = self._calculate_compatibility_score(compatibility_data)
            functionality_score = await self._calculate_functionality_score(server)
            documentation_score = self._calculate_documentation_score(server)
            maintenance_score = self._calculate_maintenance_score(server)
            
            # Calculate weighted overall score
            overall_score = (
                reliability_score * 0.25 +
                performance_score * 0.20 +
                compatibility_score * 0.20 +
                functionality_score * 0.15 +
                documentation_score * 0.10 +
                maintenance_score * 0.10
            )
            
            # Generate AI insights if available
            strengths, weaknesses, recommended_for = await self._generate_ai_insights(
                server, performance_data, compatibility_data
            )
            
            # Detect conflicts
            conflicts_with = await self._detect_server_conflicts(server)
            
            analysis = ServerAnalysis(
                server_name=server_name,
                server_type=server.server_type,
                reliability_score=reliability_score,
                performance_score=performance_score,
                compatibility_score=compatibility_score,
                functionality_score=functionality_score,
                documentation_score=documentation_score,
                maintenance_score=maintenance_score,
                overall_score=overall_score,
                strengths=strengths,
                weaknesses=weaknesses,
                recommended_for=recommended_for,
                conflicts_with=conflicts_with
            )
            
            # Cache the analysis
            self._analysis_cache[server_name] = analysis
            self._cache_expiry[server_name] = datetime.now() + self.cache_duration
            
            logger.info(f"Completed analysis for {server_name} (score: {overall_score:.2f})")
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze server {server_name}: {e}")
            return None
    
    async def recommend_suite(self, task_description: str, 
                            category: Optional[TaskCategory] = None) -> Optional[SuiteRecommendation]:
        """Generate AI-powered suite recommendation for a specific task."""
        try:
            # Classify task if category not provided
            if not category:
                category = await self._classify_task(task_description)
            
            logger.info(f"Generating suite recommendation for {category.value}")
            
            # Get all available servers
            servers = self.manager.list_servers()
            if not servers:
                logger.warning("No servers available for recommendation")
                return None
            
            # Analyze all servers
            server_analyses = {}
            for server in servers:
                analysis = await self.analyze_server(server.name)
                if analysis:
                    server_analyses[server.name] = analysis
            
            if not server_analyses:
                logger.warning("No server analyses available")
                return None
            
            # Filter servers suitable for the task category
            suitable_servers = {
                name: analysis for name, analysis in server_analyses.items()
                if category in analysis.recommended_for or analysis.overall_score > 0.7
            }
            
            # Generate AI-powered recommendation
            recommendation = await self._generate_ai_recommendation(
                task_description, category, suitable_servers, server_analyses
            )
            
            if recommendation:
                logger.info(f"Generated recommendation for {category.value} "
                           f"with {len(recommendation.primary_servers)} primary servers")
            
            return recommendation
            
        except Exception as e:
            logger.error(f"Failed to generate suite recommendation: {e}")
            return None
    
    async def curate_all_suites(self) -> Dict[TaskCategory, SuiteRecommendation]:
        """Generate recommendations for all task categories."""
        try:
            logger.info("Starting comprehensive suite curation")
            recommendations = {}
            
            # Generate standard task descriptions for each category
            task_descriptions = {
                TaskCategory.WEB_DEVELOPMENT: "Build and maintain web applications with frontend and backend components",
                TaskCategory.DATA_ANALYSIS: "Analyze datasets, create visualizations, and extract insights",
                TaskCategory.SYSTEM_ADMIN: "Manage servers, monitor systems, and automate infrastructure",
                TaskCategory.CONTENT_CREATION: "Create and edit text, images, and multimedia content",
                TaskCategory.API_DEVELOPMENT: "Design, implement, and test REST and GraphQL APIs",
                TaskCategory.DATABASE_WORK: "Design schemas, write queries, and manage database operations",
                TaskCategory.FILE_MANAGEMENT: "Organize, search, and manipulate files and directories",
                TaskCategory.AUTOMATION: "Create scripts and workflows to automate repetitive tasks",
                TaskCategory.RESEARCH: "Gather information, analyze sources, and synthesize findings",
                TaskCategory.TESTING: "Create and execute test cases for software quality assurance"
            }
            
            # Generate recommendations for each category
            for category, description in task_descriptions.items():
                try:
                    recommendation = await self.recommend_suite(description, category)
                    if recommendation:
                        recommendations[category] = recommendation
                    
                    # Small delay to avoid overwhelming AI services
                    await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Failed to generate recommendation for {category.value}: {e}")
                    continue
            
            logger.info(f"Completed curation for {len(recommendations)} categories")
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to curate all suites: {e}")
            return {}
    
    async def update_suite_database(self, recommendations: Dict[TaskCategory, SuiteRecommendation]) -> bool:
        """Update the database with suite recommendations."""
        try:
            from mcp_manager.core.suite_manager import SuiteManager
            
            suite_manager = SuiteManager()
            
            for category, recommendation in recommendations.items():
                try:
                    # Create or update suite
                    suite_id = f"ai-curated-{category.value}"
                    suite_name = f"AI Curated - {category.value.replace('_', ' ').title()}"
                    
                    # Create suite configuration
                    suite_config = {
                        "ai_generated": True,
                        "confidence_score": recommendation.confidence_score,
                        "last_updated": datetime.now().isoformat(),
                        "reasoning": recommendation.reasoning,
                        "configuration_hints": recommendation.configuration_hints,
                        "expected_conflicts": recommendation.expected_conflicts
                    }
                    
                    # Create or update the suite
                    success = await suite_manager.create_or_update_suite(
                        suite_id=suite_id,
                        name=suite_name,
                        description=f"AI-curated MCP servers for {category.value.replace('_', ' ')}",
                        category=category.value,
                        config=suite_config
                    )
                    
                    if success:
                        # Add primary servers
                        for server_name in recommendation.primary_servers:
                            await suite_manager.add_server_to_suite(
                                suite_id, server_name, role="primary", priority=90
                            )
                        
                        # Add optional servers
                        for server_name in recommendation.optional_servers:
                            await suite_manager.add_server_to_suite(
                                suite_id, server_name, role="optional", priority=50
                            )
                        
                        logger.info(f"Updated suite database for {category.value}")
                    else:
                        logger.error(f"Failed to create/update suite for {category.value}")
                
                except Exception as e:
                    logger.error(f"Failed to update suite for {category.value}: {e}")
                    continue
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update suite database: {e}")
            return False
    
    # Private helper methods
    
    def _is_analysis_cached(self, server_name: str) -> bool:
        """Check if server analysis is cached and not expired."""
        if server_name not in self._analysis_cache:
            return False
        
        expiry = self._cache_expiry.get(server_name)
        if not expiry or datetime.now() > expiry:
            # Remove expired cache
            self._analysis_cache.pop(server_name, None)
            self._cache_expiry.pop(server_name, None)
            return False
        
        return True
    
    async def _collect_performance_data(self, server: Server) -> Dict[str, Any]:
        """Collect performance metrics for a server."""
        try:
            # Try to get analytics data
            analytics_data = {}
            
            # TODO: Integrate with analytics service when available
            # For now, use basic heuristics
            
            # Simulate performance data collection
            performance_data = {
                "avg_response_time": 1000,  # ms
                "success_rate": 0.95,
                "uptime": 0.98,
                "tool_count": 0,
                "last_used": None
            }
            
            # Try to discover tools to get actual tool count
            try:
                tool_count = await self.manager.discover_and_register_server_tools(server)
                performance_data["tool_count"] = tool_count
            except Exception as e:
                logger.debug(f"Could not discover tools for {server.name}: {e}")
            
            return performance_data
            
        except Exception as e:
            logger.debug(f"Failed to collect performance data for {server.name}: {e}")
            return {}
    
    async def _collect_compatibility_data(self, server: Server) -> Dict[str, Any]:
        """Collect compatibility information for a server."""
        try:
            compatibility_data = {
                "claude_compatible": True,  # Assume compatible if running
                "installation_success": True,
                "configuration_required": False,
                "dependencies_met": True
            }
            
            # Check if server requires configuration
            if server.server_type in [ServerType.NPM, ServerType.DOCKER]:
                # These often require configuration
                compatibility_data["configuration_required"] = True
            
            return compatibility_data
            
        except Exception as e:
            logger.debug(f"Failed to collect compatibility data for {server.name}: {e}")
            return {}
    
    def _calculate_reliability_score(self, server: Server, performance_data: Dict[str, Any]) -> float:
        """Calculate reliability score based on success rate and uptime."""
        try:
            success_rate = performance_data.get("success_rate", 0.5)
            uptime = performance_data.get("uptime", 0.5)
            
            # Weight success rate more heavily
            score = (success_rate * 0.7) + (uptime * 0.3)
            return min(1.0, max(0.0, score))
            
        except Exception:
            return 0.5  # Default neutral score
    
    def _calculate_performance_score(self, performance_data: Dict[str, Any]) -> float:
        """Calculate performance score based on response times."""
        try:
            avg_response_time = performance_data.get("avg_response_time", 2000)
            
            # Score based on response time (lower is better)
            if avg_response_time < 500:
                return 1.0
            elif avg_response_time < 1000:
                return 0.8
            elif avg_response_time < 2000:
                return 0.6
            elif avg_response_time < 5000:
                return 0.4
            else:
                return 0.2
            
        except Exception:
            return 0.5
    
    def _calculate_compatibility_score(self, compatibility_data: Dict[str, Any]) -> float:
        """Calculate compatibility score."""
        try:
            score = 0.0
            
            if compatibility_data.get("claude_compatible", False):
                score += 0.4
            if compatibility_data.get("installation_success", False):
                score += 0.3
            if compatibility_data.get("dependencies_met", False):
                score += 0.2
            if not compatibility_data.get("configuration_required", True):
                score += 0.1  # Bonus for not requiring config
            
            return min(1.0, score)
            
        except Exception:
            return 0.5
    
    async def _calculate_functionality_score(self, server: Server) -> float:
        """Calculate functionality score based on available tools."""
        try:
            # Try to get tool count
            tool_count = 0
            try:
                tool_count = await self.manager.discover_and_register_server_tools(server)
            except Exception:
                pass
            
            # Score based on tool count
            if tool_count >= 20:
                return 1.0
            elif tool_count >= 10:
                return 0.8
            elif tool_count >= 5:
                return 0.6
            elif tool_count >= 1:
                return 0.4
            else:
                return 0.2
            
        except Exception:
            return 0.5
    
    def _calculate_documentation_score(self, server: Server) -> float:
        """Calculate documentation score based on description quality."""
        try:
            description = getattr(server, 'description', '') or ''
            
            # Simple heuristics for documentation quality
            if len(description) > 100:
                return 0.9
            elif len(description) > 50:
                return 0.7
            elif len(description) > 20:
                return 0.5
            elif len(description) > 0:
                return 0.3
            else:
                return 0.1
            
        except Exception:
            return 0.5
    
    def _calculate_maintenance_score(self, server: Server) -> float:
        """Calculate maintenance score based on update frequency."""
        try:
            # For now, use server type as a proxy for maintenance
            # Popular server types are likely better maintained
            if server.server_type == ServerType.DOCKER_DESKTOP:
                return 0.9  # Well maintained by Docker
            elif server.server_type == ServerType.NPM:
                return 0.7  # Community maintained
            elif server.server_type == ServerType.DOCKER:
                return 0.6  # Variable quality
            else:
                return 0.5  # Unknown
            
        except Exception:
            return 0.5
    
    async def _generate_ai_insights(self, server: Server, performance_data: Dict[str, Any], 
                                  compatibility_data: Dict[str, Any]) -> Tuple[List[str], List[str], List[TaskCategory]]:
        """Generate AI insights about server strengths, weaknesses, and use cases."""
        try:
            # Get AI provider
            primary_provider = self.ai_config.get_primary_provider()
            if not primary_provider or not self.ai_config.load_config().enabled:
                # Fallback to heuristic analysis
                return self._heuristic_insights(server, performance_data, compatibility_data)
            
            # TODO: Implement actual AI analysis when AI client is available
            # For now, use heuristic fallback
            return self._heuristic_insights(server, performance_data, compatibility_data)
            
        except Exception as e:
            logger.debug(f"Failed to generate AI insights for {server.name}: {e}")
            return self._heuristic_insights(server, performance_data, compatibility_data)
    
    def _heuristic_insights(self, server: Server, performance_data: Dict[str, Any], 
                          compatibility_data: Dict[str, Any]) -> Tuple[List[str], List[str], List[TaskCategory]]:
        """Generate insights using heuristic analysis."""
        strengths = []
        weaknesses = []
        recommended_for = []
        
        # Analyze by server name patterns and type
        name_lower = server.name.lower()
        
        # Determine strengths based on server characteristics
        if performance_data.get("success_rate", 0) > 0.9:
            strengths.append("High reliability")
        if performance_data.get("avg_response_time", 2000) < 1000:
            strengths.append("Fast response times")
        if performance_data.get("tool_count", 0) > 10:
            strengths.append("Rich functionality")
        
        # Determine weaknesses
        if performance_data.get("success_rate", 1) < 0.8:
            weaknesses.append("Reliability concerns")
        if performance_data.get("avg_response_time", 0) > 3000:
            weaknesses.append("Slow response times")
        if compatibility_data.get("configuration_required", False):
            weaknesses.append("Requires configuration")
        
        # Determine recommended use cases based on name patterns
        if any(term in name_lower for term in ["filesystem", "file", "directory"]):
            recommended_for.extend([TaskCategory.FILE_MANAGEMENT, TaskCategory.AUTOMATION])
        if any(term in name_lower for term in ["sqlite", "database", "db", "postgres"]):
            recommended_for.extend([TaskCategory.DATABASE_WORK, TaskCategory.DATA_ANALYSIS])
        if any(term in name_lower for term in ["web", "http", "browser", "playwright"]):
            recommended_for.extend([TaskCategory.WEB_DEVELOPMENT, TaskCategory.TESTING])
        if any(term in name_lower for term in ["search", "google", "brave"]):
            recommended_for.extend([TaskCategory.RESEARCH, TaskCategory.CONTENT_CREATION])
        if any(term in name_lower for term in ["git", "github"]):
            recommended_for.extend([TaskCategory.WEB_DEVELOPMENT, TaskCategory.AUTOMATION])
        if any(term in name_lower for term in ["kubernetes", "k8s", "docker"]):
            recommended_for.extend([TaskCategory.SYSTEM_ADMIN, TaskCategory.AUTOMATION])
        
        # Default recommendations if no specific patterns match
        if not recommended_for:
            if server.server_type == ServerType.DOCKER_DESKTOP:
                recommended_for.append(TaskCategory.WEB_DEVELOPMENT)
            else:
                recommended_for.append(TaskCategory.AUTOMATION)
        
        return strengths, weaknesses, recommended_for
    
    async def _detect_server_conflicts(self, server: Server) -> List[str]:
        """Detect potential conflicts with other servers."""
        conflicts = []
        
        try:
            # Get all servers
            all_servers = self.manager.list_servers()
            
            # Look for servers with similar functionality
            for other_server in all_servers:
                if other_server.name == server.name:
                    continue
                
                # Check for port conflicts (if using similar ports)
                # Check for functionality overlap
                if self._servers_have_similar_functionality(server, other_server):
                    conflicts.append(other_server.name)
            
        except Exception as e:
            logger.debug(f"Failed to detect conflicts for {server.name}: {e}")
        
        return conflicts
    
    def _servers_have_similar_functionality(self, server1: Server, server2: Server) -> bool:
        """Check if two servers have similar functionality and might conflict."""
        # Simple heuristic: servers with similar names might conflict
        name1_words = set(server1.name.lower().split('-'))
        name2_words = set(server2.name.lower().split('-'))
        
        # If they share significant word overlap, they might conflict
        overlap = name1_words.intersection(name2_words)
        return len(overlap) > 0 and any(len(word) > 3 for word in overlap)
    
    async def _classify_task(self, task_description: str) -> TaskCategory:
        """Classify a task description into a category."""
        description_lower = task_description.lower()
        
        # Simple keyword-based classification
        if any(term in description_lower for term in ["web", "html", "css", "javascript", "frontend", "backend"]):
            return TaskCategory.WEB_DEVELOPMENT
        elif any(term in description_lower for term in ["data", "analysis", "chart", "visualization", "pandas"]):
            return TaskCategory.DATA_ANALYSIS
        elif any(term in description_lower for term in ["server", "admin", "infrastructure", "deploy", "monitor"]):
            return TaskCategory.SYSTEM_ADMIN
        elif any(term in description_lower for term in ["content", "write", "edit", "document", "blog"]):
            return TaskCategory.CONTENT_CREATION
        elif any(term in description_lower for term in ["api", "rest", "graphql", "endpoint", "service"]):
            return TaskCategory.API_DEVELOPMENT
        elif any(term in description_lower for term in ["database", "sql", "query", "schema", "table"]):
            return TaskCategory.DATABASE_WORK
        elif any(term in description_lower for term in ["file", "directory", "folder", "organize", "manage"]):
            return TaskCategory.FILE_MANAGEMENT
        elif any(term in description_lower for term in ["automate", "script", "workflow", "schedule", "batch"]):
            return TaskCategory.AUTOMATION
        elif any(term in description_lower for term in ["research", "search", "information", "study", "investigate"]):
            return TaskCategory.RESEARCH
        elif any(term in description_lower for term in ["test", "testing", "qa", "quality", "verify"]):
            return TaskCategory.TESTING
        else:
            return TaskCategory.AUTOMATION  # Default fallback
    
    async def _generate_ai_recommendation(self, task_description: str, category: TaskCategory,
                                        suitable_servers: Dict[str, ServerAnalysis],
                                        all_analyses: Dict[str, ServerAnalysis]) -> Optional[SuiteRecommendation]:
        """Generate AI-powered suite recommendation."""
        try:
            if not suitable_servers:
                return None
            
            # Sort servers by overall score
            sorted_servers = sorted(
                suitable_servers.items(),
                key=lambda x: x[1].overall_score,
                reverse=True
            )
            
            # Select primary servers (top 3-5 with high scores)
            primary_servers = []
            optional_servers = []
            
            for server_name, analysis in sorted_servers:
                if analysis.overall_score > 0.8 and len(primary_servers) < 3:
                    primary_servers.append(server_name)
                elif analysis.overall_score > 0.6 and len(optional_servers) < 5:
                    optional_servers.append(server_name)
            
            # Generate alternatives for each primary server
            alternative_servers = {}
            for primary in primary_servers:
                alternatives = []
                primary_analysis = suitable_servers[primary]
                
                # Find servers with similar functionality
                for server_name, analysis in sorted_servers:
                    if (server_name not in primary_servers and 
                        server_name not in alternatives and
                        set(analysis.recommended_for).intersection(set(primary_analysis.recommended_for)) and
                        len(alternatives) < 2):
                        alternatives.append(server_name)
                
                if alternatives:
                    alternative_servers[primary] = alternatives
            
            # Generate configuration hints
            configuration_hints = self._generate_configuration_hints(primary_servers, suitable_servers)
            
            # Collect expected conflicts
            expected_conflicts = []
            for server_name in primary_servers + optional_servers:
                analysis = suitable_servers.get(server_name)
                if analysis:
                    expected_conflicts.extend(analysis.conflicts_with)
            
            # Remove duplicates
            expected_conflicts = list(set(expected_conflicts))
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(suitable_servers, primary_servers)
            
            # Generate reasoning
            reasoning = self._generate_reasoning(category, primary_servers, suitable_servers)
            
            recommendation = SuiteRecommendation(
                task_category=category,
                primary_servers=primary_servers,
                optional_servers=optional_servers,
                alternative_servers=alternative_servers,
                configuration_hints=configuration_hints,
                expected_conflicts=expected_conflicts,
                confidence_score=confidence_score,
                reasoning=reasoning
            )
            
            return recommendation
            
        except Exception as e:
            logger.error(f"Failed to generate AI recommendation: {e}")
            return None
    
    def _generate_configuration_hints(self, servers: List[str], 
                                    analyses: Dict[str, ServerAnalysis]) -> Dict[str, Any]:
        """Generate configuration hints for recommended servers."""
        hints = {}
        
        for server_name in servers:
            analysis = analyses.get(server_name)
            if not analysis:
                continue
            
            server_hints = {}
            
            # Add hints based on server name patterns
            name_lower = server_name.lower()
            if "filesystem" in name_lower:
                server_hints["directories"] = "Configure allowed directories for security"
            elif "sqlite" in name_lower or "database" in name_lower:
                server_hints["database_path"] = "Specify database file path"
            elif "browser" in name_lower or "playwright" in name_lower:
                server_hints["headless"] = "Consider headless mode for better performance"
            
            if server_hints:
                hints[server_name] = server_hints
        
        return hints
    
    def _calculate_confidence_score(self, analyses: Dict[str, ServerAnalysis], 
                                  primary_servers: List[str]) -> float:
        """Calculate confidence score for the recommendation."""
        if not primary_servers:
            return 0.0
        
        # Base confidence on average score of primary servers
        primary_scores = [
            analyses[server].overall_score 
            for server in primary_servers 
            if server in analyses
        ]
        
        if not primary_scores:
            return 0.0
        
        avg_score = sum(primary_scores) / len(primary_scores)
        
        # Adjust based on number of servers (more servers = lower confidence)
        server_count_factor = max(0.8, 1.0 - (len(primary_servers) - 3) * 0.1)
        
        return min(1.0, avg_score * server_count_factor)
    
    def _generate_reasoning(self, category: TaskCategory, servers: List[str], 
                          analyses: Dict[str, ServerAnalysis]) -> str:
        """Generate human-readable reasoning for the recommendation."""
        if not servers:
            return "No suitable servers found for this task category."
        
        reasoning_parts = [
            f"For {category.value.replace('_', ' ')} tasks, I recommend the following MCP servers:"
        ]
        
        for server in servers[:3]:  # Top 3 servers
            analysis = analyses.get(server)
            if analysis:
                score_desc = "excellent" if analysis.overall_score > 0.9 else \
                           "very good" if analysis.overall_score > 0.8 else \
                           "good" if analysis.overall_score > 0.7 else "acceptable"
                
                strengths_text = ", ".join(analysis.strengths[:2]) if analysis.strengths else "reliable functionality"
                reasoning_parts.append(f"- {server}: {score_desc} choice with {strengths_text}")
        
        reasoning_parts.append(
            f"This combination provides comprehensive coverage for {category.value.replace('_', ' ')} "
            "while minimizing conflicts and maximizing reliability."
        )
        
        return " ".join(reasoning_parts)


# Global instance for easy access
ai_curation_engine = AICurationEngine()