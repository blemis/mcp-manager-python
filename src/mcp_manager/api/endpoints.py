"""
REST API endpoints for MCP Manager.

Provides comprehensive API access to analytics data, tool information,
server management, and configuration.
"""

import io
import json
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
from fastapi import Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from mcp_manager.analytics import UsageAnalyticsService
from mcp_manager.api.auth import AuthenticationManager
from mcp_manager.api.middleware import AuthenticationMiddleware
from mcp_manager.api.models import (
    AnalyticsDataResponse, AnalyticsQueryRequest, APIResponse,
    ExportRequest, HealthCheckResponse, ServerListResponse,
    ToolInfoResponse, ToolSearchRequest
)
from mcp_manager.core.discovery import ServerDiscovery
from mcp_manager.core.simple_manager import SimpleMCPManager
from mcp_manager.core.tools import ToolRegistryService
from mcp_manager.utils.config import get_config
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class APIEndpoints:
    """Main API endpoints controller."""
    
    def __init__(self):
        """Initialize API endpoints."""
        self.config = get_config()
        self.auth_middleware = AuthenticationMiddleware()
        self.logger = logger
        
        # Initialize services
        self.analytics_service = UsageAnalyticsService()
        self.discovery_service = ServerDiscovery()
        self.manager = SimpleMCPManager()
        self.tool_registry = ToolRegistryService()
        
        logger.info("API endpoints initialized")
    
    async def health_check(self) -> HealthCheckResponse:
        """Health check endpoint."""
        try:
            # Check database connectivity
            db_status = "healthy"
            try:
                await self.analytics_service.get_usage_summary(days=1)
            except Exception as e:
                db_status = f"error: {str(e)}"
            
            # Check analytics service
            analytics_status = "healthy"
            try:
                if not self.analytics_service.config.enabled:
                    analytics_status = "disabled"
            except Exception as e:
                analytics_status = f"error: {str(e)}"
            
            # Check available servers
            servers_available = 0
            try:
                servers = await self.manager.list_servers()
                servers_available = len([s for s in servers if s.get('status') == 'running'])
            except Exception:
                pass
            
            return HealthCheckResponse(
                success=True,
                message="API is healthy",
                status="healthy",
                version="1.0.0",
                uptime_seconds=time.time() - getattr(self, '_start_time', time.time()),
                database_status=db_status,
                analytics_status=analytics_status,
                servers_available=servers_available
            )
            
        except Exception as e:
            logger.error("Health check failed", extra={"error": str(e)})
            return HealthCheckResponse(
                success=False,
                message=f"Health check failed: {str(e)}",
                status="unhealthy",
                version="1.0.0",
                uptime_seconds=0,
                database_status="unknown",
                analytics_status="unknown", 
                servers_available=0
            )
    
    @AuthenticationMiddleware().require_scopes(["analytics:read"])
    async def query_analytics(
        self, 
        request: AnalyticsQueryRequest,
        current_user: Dict = Depends(AuthenticationMiddleware().get_current_user)
    ) -> AnalyticsDataResponse:
        """Query analytics data."""
        try:
            logger.info("Analytics query requested", extra={
                "query_type": request.query_type,
                "user": current_user.get('user_id'),
                "filters": request.filters
            })
            
            results = []
            total_count = 0
            aggregations = {}
            
            if request.query_type == "usage_summary":
                days = request.filters.get('days', 7)
                summary = await self.analytics_service.get_usage_summary(days=days)
                results = [summary]
                total_count = 1
                
            elif request.query_type == "tool_usage":
                # Get tool usage statistics
                tool_usage = await self.analytics_service.get_tool_usage_stats(
                    limit=request.limit,
                    offset=request.offset
                )
                results = tool_usage
                total_count = len(tool_usage)
                
            elif request.query_type == "trending_queries":
                trending = await self.analytics_service.get_trending_queries(
                    limit=request.limit
                )
                results = trending
                total_count = len(trending)
                
            elif request.query_type == "performance_metrics":
                metrics = await self.analytics_service.get_performance_metrics()
                results = [metrics]
                total_count = 1
                
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported query type: {request.query_type}"
                )
            
            return AnalyticsDataResponse(
                success=True,
                message="Analytics query completed",
                query_type=request.query_type,
                total_count=total_count,
                results=results,
                aggregations=aggregations
            )
            
        except Exception as e:
            logger.error("Analytics query failed", extra={
                "query_type": request.query_type,
                "error": str(e)
            })
            raise HTTPException(status_code=500, detail=str(e))
    
    @AuthenticationMiddleware().require_scopes(["tools:read"])
    async def search_tools(
        self,
        request: ToolSearchRequest,
        current_user: Dict = Depends(AuthenticationMiddleware().get_current_user)
    ) -> List[ToolInfoResponse]:
        """Search for tools."""
        try:
            logger.info("Tool search requested", extra={
                "query": request.query,
                "user": current_user.get('user_id'),
                "categories": request.categories
            })
            
            # Use tool registry service
            search_results = await self.tool_registry.search_tools(
                query=request.query,
                categories=request.categories,
                server_types=request.server_types,
                limit=request.limit,
                include_unavailable=request.include_unavailable
            )
            
            # Convert to response format
            tools = []
            for tool in search_results:
                tool_info = ToolInfoResponse(
                    success=True,
                    message="Tool found",
                    canonical_name=tool.get('canonical_name', ''),
                    name=tool.get('name', ''),
                    description=tool.get('description', ''),
                    server_name=tool.get('server_name', ''),
                    server_type=tool.get('server_type', ''),
                    categories=tool.get('categories', []),
                    tags=tool.get('tags', []),
                    input_schema=tool.get('input_schema', {}),
                    output_schema=tool.get('output_schema', {}),
                    usage_stats=tool.get('usage_stats', {})
                )
                tools.append(tool_info)
            
            return tools
            
        except Exception as e:
            logger.error("Tool search failed", extra={
                "query": request.query,
                "error": str(e)
            })
            raise HTTPException(status_code=500, detail=str(e))
    
    @AuthenticationMiddleware().require_scopes(["servers:read"])
    async def list_servers(
        self,
        current_user: Dict = Depends(AuthenticationMiddleware().get_current_user),
        status: Optional[str] = Query(None, description="Filter by status"),
        server_type: Optional[str] = Query(None, description="Filter by type")
    ) -> ServerListResponse:
        """List all MCP servers."""
        try:
            logger.info("Server list requested", extra={
                "user": current_user.get('user_id'),
                "filters": {"status": status, "type": server_type}
            })
            
            servers = await self.manager.list_servers()
            
            # Apply filters
            if status:
                servers = [s for s in servers if s.get('status') == status]
            if server_type:
                servers = [s for s in servers if s.get('server_type') == server_type]
            
            # Count by type
            by_type = {}
            for server in servers:
                stype = server.get('server_type', 'unknown')
                by_type[stype] = by_type.get(stype, 0) + 1
            
            return ServerListResponse(
                success=True,
                message="Servers listed",
                servers=servers,
                total_count=len(servers),
                by_type=by_type
            )
            
        except Exception as e:
            logger.error("Server list failed", extra={"error": str(e)})
            raise HTTPException(status_code=500, detail=str(e))
    
    @AuthenticationMiddleware().require_scopes(["analytics:export"])
    async def export_data(
        self,
        request: ExportRequest,
        current_user: Dict = Depends(AuthenticationMiddleware().get_current_user)
    ) -> StreamingResponse:
        """Export data in various formats."""
        try:
            logger.info("Data export requested", extra={
                "export_type": request.export_type,
                "format": request.format,
                "user": current_user.get('user_id')
            })
            
            # Get data based on export type
            data = []
            filename = f"mcp_manager_{request.export_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            if request.export_type == "analytics":
                summary = await self.analytics_service.get_usage_summary(days=30)
                data = [summary]
                
            elif request.export_type == "tools":
                tools = await self.tool_registry.search_tools("", limit=1000)
                data = tools
                
            elif request.export_type == "servers":
                servers = await self.manager.list_servers()
                data = servers
                
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported export type: {request.export_type}"
                )
            
            # Generate export content
            if request.format == "json":
                content = json.dumps(data, indent=2, default=str)
                media_type = "application/json"
                filename += ".json"
                
            elif request.format == "csv":
                if data:
                    df = pd.DataFrame(data)
                    output = io.StringIO()
                    df.to_csv(output, index=False)
                    content = output.getvalue()
                else:
                    content = ""
                media_type = "text/csv"
                filename += ".csv"
                
            elif request.format == "yaml":
                import yaml
                content = yaml.dump(data, default_flow_style=False)
                media_type = "application/x-yaml"
                filename += ".yaml"
                
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported format: {request.format}"
                )
            
            # Create streaming response
            def generate():
                yield content.encode('utf-8')
            
            return StreamingResponse(
                generate(),
                media_type=media_type,
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
            
        except Exception as e:
            logger.error("Data export failed", extra={
                "export_type": request.export_type,
                "format": request.format,
                "error": str(e)
            })
            raise HTTPException(status_code=500, detail=str(e))
    
    @AuthenticationMiddleware().require_scopes(["tools:read"])
    async def get_tool_categories(
        self,
        current_user: Dict = Depends(AuthenticationMiddleware().get_current_user)
    ) -> APIResponse:
        """Get available tool categories."""
        try:
            categories = await self.tool_registry.get_tool_categories()
            
            return APIResponse(
                success=True,
                message="Tool categories retrieved",
                data={
                    "categories": categories,
                    "total_count": len(categories)
                }
            )
            
        except Exception as e:
            logger.error("Get tool categories failed", extra={"error": str(e)})
            raise HTTPException(status_code=500, detail=str(e))
    
    @AuthenticationMiddleware().require_scopes(["analytics:read"])
    async def get_api_stats(
        self,
        current_user: Dict = Depends(AuthenticationMiddleware().get_current_user)
    ) -> APIResponse:
        """Get API usage statistics."""
        try:
            # This would be tracked by analytics middleware in production
            stats = {
                "total_requests": 0,
                "requests_by_endpoint": {},
                "avg_response_time_ms": 0,
                "error_rate": 0,
                "active_users": 1  # Current user
            }
            
            return APIResponse(
                success=True,
                message="API statistics retrieved",
                data=stats
            )
            
        except Exception as e:
            logger.error("Get API stats failed", extra={"error": str(e)})
            raise HTTPException(status_code=500, detail=str(e))