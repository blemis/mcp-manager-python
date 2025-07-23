"""
AI-powered tool recommendation service.

Uses LLM providers to analyze user queries and provide contextual
tool recommendations from the MCP tool registry.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from mcp_manager.ai import LLMConfig, create_llm_provider
from mcp_manager.core.tool_registry import SearchFilters, ToolInfo, ToolRegistryService
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class ToolRecommendation(BaseModel):
    """A single tool recommendation with reasoning."""
    
    canonical_name: str = Field(description="Tool canonical name (server/tool)")
    name: str = Field(description="Tool name")
    server_name: str = Field(description="Server providing the tool")
    server_type: str = Field(description="Server type")
    description: str = Field(description="Tool description")
    categories: List[str] = Field(default_factory=list, description="Tool categories")
    tags: List[str] = Field(default_factory=list, description="Tool tags")
    
    # Recommendation metadata
    relevance_score: float = Field(description="AI-assigned relevance score (0-1)")
    reasoning: str = Field(description="AI explanation for why this tool is recommended")
    confidence: float = Field(description="AI confidence in this recommendation (0-1)")
    usage_context: str = Field(description="Suggested usage context or example")
    
    # Tool status
    is_available: bool = Field(description="Whether tool is currently available")
    usage_count: int = Field(default=0, description="Historical usage count")
    success_rate: float = Field(default=0.0, description="Historical success rate")


class RecommendationRequest(BaseModel):
    """Request for tool recommendations."""
    
    query: str = Field(description="User query describing what they want to do")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context information")
    max_recommendations: int = Field(default=5, description="Maximum number of recommendations to return")
    include_unavailable: bool = Field(default=False, description="Include unavailable tools in recommendations")
    server_filter: Optional[str] = Field(default=None, description="Filter by specific server name")
    category_filter: Optional[List[str]] = Field(default=None, description="Filter by tool categories")


class RecommendationResponse(BaseModel):
    """Response containing tool recommendations."""
    
    query: str = Field(description="Original user query")
    recommendations: List[ToolRecommendation] = Field(description="Ordered list of tool recommendations")
    total_tools_analyzed: int = Field(description="Total number of tools analyzed")
    processing_time_ms: int = Field(description="Time taken to generate recommendations")
    llm_provider: str = Field(description="LLM provider used for recommendations")
    model_used: str = Field(description="Specific model used")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional response metadata")


class ToolRecommendationService:
    """AI-powered tool recommendation service."""
    
    def __init__(self, tool_registry: Optional[ToolRegistryService] = None, 
                 llm_config: Optional[LLMConfig] = None):
        """
        Initialize tool recommendation service.
        
        Args:
            tool_registry: Tool registry service. If None, creates a new instance.
            llm_config: LLM configuration. If None, uses defaults from environment.
        """
        self.tool_registry = tool_registry or ToolRegistryService()
        self.llm_config = llm_config or LLMConfig()
        
        # Create LLM provider
        try:
            self.llm_provider = create_llm_provider()
        except Exception as e:
            logger.error(f"Failed to initialize LLM provider: {e}")
            raise
        
        # Configuration from environment
        self.max_tools_to_analyze = int(os.getenv("MCP_RECOMMENDER_MAX_TOOLS", "50"))
        self.min_relevance_score = float(os.getenv("MCP_RECOMMENDER_MIN_SCORE", "0.3"))
        self.use_detailed_analysis = os.getenv("MCP_RECOMMENDER_DETAILED", "true").lower() == "true"
        
        logger.info("Tool recommendation service initialized", extra={
            "llm_provider": self.llm_config.provider.value,
            "model": self.llm_config.get_default_model(),
            "max_tools_analyze": self.max_tools_to_analyze,
            "min_relevance_score": self.min_relevance_score
        })
    
    async def get_recommendations(self, request: RecommendationRequest) -> RecommendationResponse:
        """
        Get AI-powered tool recommendations for a user query.
        
        Args:
            request: Recommendation request with query and filters
            
        Returns:
            RecommendationResponse with ordered recommendations
        """
        start_time = datetime.utcnow()
        
        logger.info("Generating tool recommendations", extra={
            "query": request.query[:100] + ("..." if len(request.query) > 100 else ""),
            "max_recommendations": request.max_recommendations,
            "server_filter": request.server_filter,
            "category_filter": request.category_filter
        })
        
        try:
            # Search for relevant tools in the registry
            candidate_tools = await self._find_candidate_tools(request)
            
            if not candidate_tools:
                logger.warning("No candidate tools found for query")
                return RecommendationResponse(
                    query=request.query,
                    recommendations=[],
                    total_tools_analyzed=0,
                    processing_time_ms=self._get_processing_time_ms(start_time),
                    llm_provider=self.llm_config.provider.value,
                    model_used=self.llm_config.get_default_model(),
                    metadata={"reason": "no_candidate_tools_found"}
                )
            
            # Generate AI-powered recommendations
            recommendations = await self._generate_recommendations(request, candidate_tools)
            
            # Filter and sort recommendations
            filtered_recommendations = self._filter_and_sort_recommendations(
                recommendations, request.max_recommendations, request.include_unavailable
            )
            
            processing_time = self._get_processing_time_ms(start_time)
            
            logger.info("Tool recommendations generated successfully", extra={
                "recommendations_count": len(filtered_recommendations),
                "tools_analyzed": len(candidate_tools),
                "processing_time_ms": processing_time
            })
            
            return RecommendationResponse(
                query=request.query,
                recommendations=filtered_recommendations,
                total_tools_analyzed=len(candidate_tools),
                processing_time_ms=processing_time,
                llm_provider=self.llm_config.provider.value,
                model_used=self.llm_config.get_default_model(),
                metadata={
                    "candidate_tools_found": len(candidate_tools),
                    "min_relevance_threshold": self.min_relevance_score
                }
            )
            
        except Exception as e:
            logger.error("Failed to generate tool recommendations", extra={
                "query": request.query,
                "error": str(e),
                "error_type": type(e).__name__
            })
            
            return RecommendationResponse(
                query=request.query,
                recommendations=[],
                total_tools_analyzed=0,
                processing_time_ms=self._get_processing_time_ms(start_time),
                llm_provider=self.llm_config.provider.value,
                model_used=self.llm_config.get_default_model(),
                metadata={"error": str(e)}
            )
    
    async def _find_candidate_tools(self, request: RecommendationRequest) -> List[ToolInfo]:
        """
        Find candidate tools that might be relevant to the query.
        
        Args:
            request: Recommendation request
            
        Returns:
            List of candidate tools from the registry
        """
        # Create search filters
        filters = SearchFilters(
            server_name=request.server_filter,
            categories=request.category_filter,
            available_only=not request.include_unavailable
        )
        
        # Extract keywords from the query for initial filtering
        keywords = self._extract_keywords_from_query(request.query)
        
        candidate_tools = []
        
        # Search by keywords
        for keyword in keywords:
            tools = self.tool_registry.search_tools(
                query=keyword,
                filters=filters,
                limit=self.max_tools_to_analyze
            )
            candidate_tools.extend(tools)
        
        # Also do a general search with the full query
        general_tools = self.tool_registry.search_tools(
            query=request.query,
            filters=filters,
            limit=self.max_tools_to_analyze
        )
        candidate_tools.extend(general_tools)
        
        # Remove duplicates while preserving order
        seen_names = set()
        unique_tools = []
        for tool in candidate_tools:
            if tool.canonical_name not in seen_names:
                seen_names.add(tool.canonical_name)
                unique_tools.append(tool)
        
        # Limit to max tools to analyze
        return unique_tools[:self.max_tools_to_analyze]
    
    async def _generate_recommendations(self, request: RecommendationRequest, 
                                      candidate_tools: List[ToolInfo]) -> List[ToolRecommendation]:
        """
        Use AI to analyze candidate tools and generate recommendations.
        
        Args:
            request: Original recommendation request
            candidate_tools: List of candidate tools to analyze
            
        Returns:
            List of AI-generated tool recommendations
        """
        # Prepare tools data for AI analysis
        tools_data = []
        for tool in candidate_tools:
            tools_data.append({
                "canonical_name": tool.canonical_name,
                "name": tool.name,
                "description": tool.description,
                "server_name": tool.server_name,
                "server_type": tool.server_type.value,
                "categories": tool.categories,
                "tags": tool.tags,
                "is_available": tool.is_available,
                "usage_count": tool.usage_count,
                "success_rate": tool.success_rate
            })
        
        # Create the AI prompt
        system_prompt = self._create_system_prompt()
        user_prompt = self._create_user_prompt(request, tools_data)
        
        # Define the expected response schema
        response_schema = {
            "type": "object",
            "properties": {
                "recommendations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "canonical_name": {"type": "string"},
                            "relevance_score": {"type": "number", "minimum": 0, "maximum": 1},
                            "reasoning": {"type": "string"},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "usage_context": {"type": "string"}
                        },
                        "required": ["canonical_name", "relevance_score", "reasoning", "confidence", "usage_context"]
                    }
                }
            },
            "required": ["recommendations"]
        }
        
        # Generate AI response
        llm_response = await self.llm_provider.generate_structured_response(
            prompt=user_prompt,
            schema=response_schema,
            system_prompt=system_prompt,
            temperature=0.3  # Lower temperature for more consistent recommendations
        )
        
        # Parse AI response and create recommendation objects
        try:
            ai_data = json.loads(llm_response.content)
            recommendations = []
            
            for ai_rec in ai_data.get("recommendations", []):
                canonical_name = ai_rec.get("canonical_name")
                
                # Find the corresponding tool info
                tool_info = next((t for t in candidate_tools if t.canonical_name == canonical_name), None)
                if not tool_info:
                    logger.warning(f"AI recommended unknown tool: {canonical_name}")
                    continue
                
                recommendation = ToolRecommendation(
                    canonical_name=tool_info.canonical_name,
                    name=tool_info.name,
                    server_name=tool_info.server_name,
                    server_type=tool_info.server_type.value,
                    description=tool_info.description,
                    categories=tool_info.categories,
                    tags=tool_info.tags,
                    relevance_score=ai_rec.get("relevance_score", 0.0),
                    reasoning=ai_rec.get("reasoning", ""),
                    confidence=ai_rec.get("confidence", 0.0),
                    usage_context=ai_rec.get("usage_context", ""),
                    is_available=tool_info.is_available,
                    usage_count=tool_info.usage_count,
                    success_rate=tool_info.success_rate
                )
                recommendations.append(recommendation)
            
            return recommendations
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI recommendation response: {e}")
            # Fallback to simple recommendations based on search relevance
            return self._create_fallback_recommendations(request, candidate_tools)
    
    def _create_system_prompt(self) -> str:
        """Create the system prompt for AI tool recommendation."""
        return """You are an expert assistant helping users find the right MCP (Model Context Protocol) tools for their tasks.

Your role is to analyze user queries and recommend the most relevant tools from the available MCP tool registry. 

Key guidelines:
1. Focus on practical utility - recommend tools that directly solve the user's problem
2. Consider tool availability, usage patterns, and success rates
3. Provide clear reasoning for each recommendation
4. Include specific usage context or examples
5. Score relevance from 0.0 (not relevant) to 1.0 (highly relevant)
6. Express confidence from 0.0 (uncertain) to 1.0 (very confident)
7. Prioritize tools that are available and have good success rates
8. Consider the user's specific context and requirements

Be concise but informative in your reasoning and usage context."""
    
    def _create_user_prompt(self, request: RecommendationRequest, tools_data: List[Dict[str, Any]]) -> str:
        """Create the user prompt with query context and tool data."""
        context_info = ""
        if request.context:
            context_info = f"\nAdditional context: {json.dumps(request.context, indent=2)}"
        
        return f"""User Query: "{request.query}"{context_info}

Available MCP Tools to analyze:
{json.dumps(tools_data, indent=2)}

Please analyze these tools and recommend the most relevant ones for the user's query. Return your recommendations as a JSON object with the following structure:

{{
  "recommendations": [
    {{
      "canonical_name": "server_name/tool_name",
      "relevance_score": 0.85,
      "reasoning": "This tool is highly relevant because...",
      "confidence": 0.9,
      "usage_context": "You can use this tool to..."
    }}
  ]
}}

Focus on recommending tools that best match the user's needs, explaining why each tool is useful, and providing practical usage guidance."""
    
    def _extract_keywords_from_query(self, query: str) -> List[str]:
        """Extract relevant keywords from the user query."""
        # Simple keyword extraction - can be enhanced with NLP
        import re
        
        # Remove common stop words and extract meaningful terms
        stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "can", "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them", "my", "your", "his", "her", "its", "our", "their"}
        
        # Extract words (alphanumeric sequences)
        words = re.findall(r'\b\w+\b', query.lower())
        
        # Filter out stop words and short words
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        return keywords[:10]  # Limit to top 10 keywords
    
    def _create_fallback_recommendations(self, request: RecommendationRequest, 
                                       candidate_tools: List[ToolInfo]) -> List[ToolRecommendation]:
        """Create fallback recommendations when AI analysis fails."""
        recommendations = []
        
        for tool in candidate_tools[:request.max_recommendations]:
            # Simple scoring based on usage and availability
            score = 0.5  # Base score
            if tool.is_available:
                score += 0.2
            if tool.usage_count > 0:
                score += min(0.2, tool.usage_count / 100.0)
            if tool.success_rate > 0:
                score += tool.success_rate * 0.1
            
            recommendation = ToolRecommendation(
                canonical_name=tool.canonical_name,
                name=tool.name,
                server_name=tool.server_name,
                server_type=tool.server_type.value,
                description=tool.description,
                categories=tool.categories,
                tags=tool.tags,
                relevance_score=min(score, 1.0),
                reasoning="Tool matches your search criteria and is available for use.",
                confidence=0.6,
                usage_context=f"This {tool.server_type.value} tool can help with tasks related to: {', '.join(tool.categories[:3])}",
                is_available=tool.is_available,
                usage_count=tool.usage_count,
                success_rate=tool.success_rate
            )
            recommendations.append(recommendation)
        
        return recommendations
    
    def _filter_and_sort_recommendations(self, recommendations: List[ToolRecommendation],
                                       max_count: int, include_unavailable: bool) -> List[ToolRecommendation]:
        """Filter and sort recommendations by relevance and availability."""
        # Filter by availability if requested
        if not include_unavailable:
            recommendations = [r for r in recommendations if r.is_available]
        
        # Filter by minimum relevance score
        recommendations = [r for r in recommendations if r.relevance_score >= self.min_relevance_score]
        
        # Sort by relevance score (descending), then by confidence (descending)
        recommendations.sort(key=lambda r: (r.relevance_score, r.confidence), reverse=True)
        
        # Limit to requested count
        return recommendations[:max_count]
    
    def _get_processing_time_ms(self, start_time: datetime) -> int:
        """Calculate processing time in milliseconds."""
        return int((datetime.utcnow() - start_time).total_seconds() * 1000)