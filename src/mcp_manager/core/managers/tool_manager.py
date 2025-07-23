"""
Tool Manager for tool registry operations and analytics.

Handles tool analytics, AI-powered recommendations, usage tracking,
and tool registry statistics.
"""

import os
import sqlite3
import uuid
from typing import Optional, Dict, Any, List, Callable

from mcp_manager.core.models import Server
from mcp_manager.core.tool_registry import ToolRegistryService
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ToolManager:
    """Manages tool analytics, recommendations, and registry operations."""
    
    def __init__(self, tool_registry: Optional[ToolRegistryService] = None,
                 server_list_callback: Optional[Callable[[], List[Server]]] = None):
        """Initialize tool manager with lazy loading.
        
        Args:
            tool_registry: Optional tool registry service
            server_list_callback: Optional callback to get server list
        """
        self._tool_registry = tool_registry
        self._analytics_service = None
        self.tool_recommender = None
        self._ai_recommender_initialized = False
        self._server_list_callback = server_list_callback
        
        # Configuration from environment
        self.analytics_enabled = os.getenv("MCP_ANALYTICS_ENABLED", "true").lower() == "true"
        self.ai_recommendations_enabled = os.getenv("MCP_AI_RECOMMENDATIONS", "true").lower() == "true"
        
        logger.debug("ToolManager initialized (services will be loaded on demand)")
    
    @property
    def tool_registry(self) -> ToolRegistryService:
        """Get tool registry service (lazy loading)."""
        if self._tool_registry is None:
            self._tool_registry = ToolRegistryService()
            logger.debug("ToolRegistryService initialized in ToolManager")
        return self._tool_registry
    
    @property
    def analytics_service(self) -> Optional[Any]:
        """Get analytics service (lazy loading)."""
        if not self.analytics_enabled:
            return None
            
        if self._analytics_service is None:
            try:
                from mcp_manager.analytics import UsageAnalyticsService
                self._analytics_service = UsageAnalyticsService()
                logger.debug("UsageAnalyticsService initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize analytics service: {e}")
                self.analytics_enabled = False
                return None
        
        return self._analytics_service
    
    def _initialize_ai_recommender(self) -> None:
        """Initialize the AI tool recommender service."""
        if self._ai_recommender_initialized or not self.ai_recommendations_enabled:
            return
        
        try:
            from mcp_manager.ai.tool_recommender import ToolRecommendationService
            self.tool_recommender = ToolRecommendationService()
            logger.info("AI tool recommender service initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize AI recommender: {e}")
            self.ai_recommendations_enabled = False
        
        self._ai_recommender_initialized = True
    
    def get_tool_registry_stats(self) -> Dict[str, Any]:
        """
        Get tool registry statistics.
        
        Returns:
            Dictionary with registry statistics
        """
        try:
            return self.tool_registry.get_stats()
        except Exception as e:
            logger.error(f"Failed to get tool registry stats: {e}")
            return {}
    
    async def get_ai_tool_recommendations(self, query: str, 
                                        max_recommendations: int = 5,
                                        server_filter: Optional[str] = None,
                                        include_unavailable: bool = False,
                                        context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get AI-powered tool recommendations for a user query.
        
        Args:
            query: User query or task description
            max_recommendations: Maximum number of recommendations
            server_filter: Optional server name filter
            include_unavailable: Include tools from disabled servers
            context: Additional context for recommendations
            
        Returns:
            Dictionary with recommendations and metadata
        """
        if not self.ai_recommendations_enabled:
            return {
                "recommendations": [],
                "query": query,
                "error": "AI recommendations are disabled"
            }
        
        # Initialize AI recommender if needed
        self._initialize_ai_recommender()
        
        if not self.tool_recommender:
            return {
                "recommendations": [],
                "query": query,
                "error": "AI recommender not available"
            }
        
        try:
            logger.debug(f"Getting AI tool recommendations for: {query}")
            
            # Import here to avoid circular dependencies
            from mcp_manager.ai.tool_recommender import RecommendationRequest
            
            # Create recommendation request
            request = RecommendationRequest(
                query=query,
                max_recommendations=max_recommendations,
                server_filter=server_filter,
                include_unavailable=include_unavailable,
                context=context or {}
            )
            
            # Get recommendations from AI service
            recommendations = await self.tool_recommender.get_recommendations(request)
            
            # Record analytics if available
            if self.analytics_service:
                session_id = str(uuid.uuid4())
                try:
                    self.analytics_service.record_recommendation_analytics(
                        session_id=session_id,
                        query=query,
                        recommendations_count=len(recommendations),
                        server_filter=server_filter,
                        context=context
                    )
                except Exception as e:
                    logger.warning(f"Failed to record recommendation analytics: {e}")
            
            result = {
                "recommendations": recommendations,
                "query": query,
                "session_id": session_id if self.analytics_service else None,
                "total_found": len(recommendations)
            }
            
            logger.info(f"Generated {len(recommendations)} AI tool recommendations for query: {query}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to get AI tool recommendations: {e}")
            return {
                "recommendations": [],
                "query": query,
                "error": str(e)
            }
    
    async def suggest_tools_for_task(self, task_description: str,
                                   workflow_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Suggest tools for a specific task with workflow context.
        
        Args:
            task_description: Description of the task
            workflow_context: Optional workflow context
            
        Returns:
            Dictionary with tool suggestions and workflow tips
        """
        try:
            logger.debug(f"Suggesting tools for task: {task_description}")
            
            # Get AI recommendations
            recommendations_result = await self.get_ai_tool_recommendations(
                query=task_description,
                max_recommendations=8,
                context=workflow_context
            )
            
            # Generate workflow tips based on recommendations
            workflow_tips = self._generate_workflow_tips(
                recommendations_result.get("recommendations", [])
            )
            
            result = {
                "task": task_description,
                "suggestions": recommendations_result.get("recommendations", []),
                "workflow_tips": workflow_tips,
                "session_id": recommendations_result.get("session_id"),
                "total_suggestions": len(recommendations_result.get("recommendations", []))
            }
            
            logger.info(f"Generated {len(result['suggestions'])} tool suggestions for task")
            return result
            
        except Exception as e:
            logger.error(f"Failed to suggest tools for task: {e}")
            return {
                "task": task_description,
                "suggestions": [],
                "workflow_tips": [],
                "error": str(e)
            }
    
    def _generate_workflow_tips(self, recommendations: List[Dict[str, Any]]) -> List[str]:
        """
        Generate workflow tips based on recommendations.
        
        Args:
            recommendations: List of tool recommendations
            
        Returns:
            List of workflow tips
        """
        tips = []
        
        if not recommendations:
            return tips
        
        # Analyze recommendation patterns to generate tips
        server_types = set()
        categories = set()
        
        for rec in recommendations:
            if rec.get("server_type"):
                server_types.add(rec["server_type"])
            if rec.get("categories"):
                categories.update(rec["categories"])
        
        # Generate tips based on patterns
        if "filesystem" in categories:
            tips.append("Consider using filesystem tools for file operations")
        
        if "database" in categories:
            tips.append("Database tools can help with data storage and queries")
        
        if "web" in categories:
            tips.append("Web tools are useful for fetching external data")
        
        if len(server_types) > 1:
            tips.append("Multiple server types available - choose based on your needs")
        
        return tips
    
    def record_tool_usage(self, canonical_name: str, user_query: str, 
                         selected: bool, success: bool, response_time_ms: int,
                         error_details: Optional[str] = None,
                         context: Optional[Dict[str, Any]] = None,
                         session_id: Optional[str] = None) -> bool:
        """
        Record tool usage analytics.
        
        Args:
            canonical_name: Canonical tool name (server/tool)
            user_query: User query that led to tool usage
            selected: Whether tool was selected by user
            success: Whether tool execution was successful
            response_time_ms: Response time in milliseconds
            error_details: Optional error details if failed
            context: Optional additional context
            session_id: Optional session identifier
            
        Returns:
            True if recording was successful
        """
        if not self.analytics_service:
            return False
        
        try:
            return self.analytics_service.record_tool_usage(
                canonical_name=canonical_name,
                user_query=user_query,
                selected=selected,
                success=success,
                response_time_ms=response_time_ms,
                error_details=error_details,
                context=context,
                session_id=session_id
            )
        except Exception as e:
            logger.error(f"Failed to record tool usage: {e}")
            return False
    
    def get_usage_analytics(self, days: int = 7) -> Dict[str, Any]:
        """
        Get usage analytics summary.
        
        Args:
            days: Number of days to analyze
            
        Returns:
            Dictionary with usage analytics
        """
        if not self.analytics_service:
            return {"error": "Analytics service not available"}
        
        try:
            return self.analytics_service.get_usage_summary(days=days)
        except Exception as e:
            logger.error(f"Failed to get usage analytics: {e}")
            return {"error": str(e)}
    
    def get_trending_queries(self, limit: int = 10) -> Dict[str, Any]:
        """
        Get trending query patterns.
        
        Args:
            limit: Maximum number of trending queries
            
        Returns:
            Dictionary with trending queries
        """
        if not self.analytics_service:
            return {"trending_queries": [], "error": "Analytics service not available"}
        
        try:
            return self.analytics_service.get_trending_queries(limit=limit)
        except Exception as e:
            logger.error(f"Failed to get trending queries: {e}")
            return {"trending_queries": [], "error": str(e)}
    
    def record_recommendation_feedback(self, session_id: str,
                                     selected_tool: Optional[str] = None,
                                     satisfaction_score: Optional[float] = None) -> bool:
        """
        Record user feedback on AI recommendations.
        
        Args:
            session_id: Session identifier from recommendation request
            selected_tool: Tool that was actually selected (if any)
            satisfaction_score: User satisfaction score (0.0-1.0)
            
        Returns:
            True if feedback was recorded successfully
        """
        if not self.analytics_service:
            return False
        
        try:
            # Use analytics service method if available, otherwise direct DB
            if hasattr(self.analytics_service, 'record_recommendation_feedback'):
                return self.analytics_service.record_recommendation_feedback(
                    session_id=session_id,
                    selected_tool=selected_tool,
                    satisfaction_score=satisfaction_score
                )
            else:
                # Fallback to direct database recording
                db_path = os.path.expanduser("~/.mcp-manager/analytics.db")
                with sqlite3.connect(db_path) as conn:
                    conn.execute("""
                        UPDATE recommendation_analytics 
                        SET selected_tool = ?, satisfaction_score = ?, feedback_timestamp = datetime('now')
                        WHERE session_id = ?
                    """, (selected_tool, satisfaction_score, session_id))
                    conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Failed to record recommendation feedback: {e}")
            return False
    
    async def update_server_analytics(self) -> Dict[str, Any]:
        """
        Update server analytics for all servers.
        
        Returns:
            Dictionary with update results
        """
        if not self.analytics_service:
            return {"error": "Analytics service not available"}
        
        try:
            # Get server list from callback if available
            if self._server_list_callback:
                servers = self._server_list_callback()
            else:
                logger.warning("No server list callback available for analytics update")
                return {"error": "Server list not available"}
            
            updated_count = 0
            
            for server in servers:
                try:
                    # Get tool count for this server
                    tools = self.tool_registry.get_tools_by_server(server.name)
                    tool_count = len(tools) if tools else 0
                    
                    # Update server analytics
                    self.analytics_service.update_server_stats(
                        server_name=server.name,
                        server_type=server.server_type.value,
                        enabled=server.enabled,
                        tool_count=tool_count
                    )
                    
                    updated_count += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to update analytics for server {server.name}: {e}")
            
            result = {
                "servers_updated": updated_count,
                "total_servers": len(servers),
                "success": True
            }
            
            logger.info(f"Updated analytics for {updated_count} servers")
            return result
            
        except Exception as e:
            logger.error(f"Failed to update server analytics: {e}")
            return {"error": str(e), "success": False}
    
    def cleanup_analytics_data(self) -> Dict[str, Any]:
        """
        Clean up old analytics data.
        
        Returns:
            Dictionary with cleanup results
        """
        if not self.analytics_service:
            return {"error": "Analytics service not available"}
        
        try:
            result = self.analytics_service.cleanup_old_data()
            logger.info("Analytics data cleanup completed")
            return result
        except Exception as e:
            logger.error(f"Failed to cleanup analytics data: {e}")
            return {"error": str(e)}