"""
FastAPI server for MCP Manager API.

Provides REST API server with authentication, rate limiting, and comprehensive endpoints.
"""

import time
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer

from mcp_manager.api.auth import AuthenticationManager
from mcp_manager.api.endpoints import APIEndpoints
from mcp_manager.api.middleware import (
    AuthenticationMiddleware, ErrorHandlingMiddleware,
    RateLimitMiddleware, RequestLoggingMiddleware, SecurityMiddleware
)
from mcp_manager.api.models import (
    AnalyticsDataResponse, AnalyticsQueryRequest, APIResponse,
    AuthTokenRequest, AuthTokenResponse, ExportRequest,
    HealthCheckResponse, ServerListResponse, ToolSearchRequest
)
from mcp_manager.utils.config import get_config
from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class APIServer:
    """MCP Manager API server."""
    
    def __init__(self, config=None):
        """Initialize API server."""
        self.config = config or get_config()
        self.auth_manager = AuthenticationManager()
        self.endpoints = APIEndpoints()
        self.security = HTTPBearer(auto_error=False)
        
        # Track server start time
        self._start_time = time.time()
        self.endpoints._start_time = self._start_time
        
        # Create FastAPI app
        self.app = self._create_app()
        
        logger.info("API server initialized", extra={
            "api_enabled": getattr(self.config, 'enable_api', True),
            "auth_enabled": True
        })
    
    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        """Manage application lifespan."""
        # Startup
        logger.info("API server starting up")
        yield
        # Shutdown
        logger.info("API server shutting down")
    
    def _create_app(self) -> FastAPI:
        """Create and configure FastAPI application."""
        app = FastAPI(
            title="MCP Manager API",
            description="REST API for MCP Manager - Tool Registry and Analytics",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc",
            lifespan=self.lifespan
        )
        
        # Add middleware
        self._add_middleware(app)
        
        # Add routes
        self._add_routes(app)
        
        return app
    
    def _add_middleware(self, app: FastAPI):
        """Add middleware stack to FastAPI app."""
        # Error handling (outermost)
        app.add_middleware(ErrorHandlingMiddleware)
        
        # Request logging
        app.add_middleware(RequestLoggingMiddleware)
        
        # Security headers and CORS
        app.add_middleware(SecurityMiddleware, allowed_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000"
        ])
        
        # Rate limiting
        requests_per_minute = getattr(self.config, 'api_rate_limit_per_minute', 60)
        requests_per_hour = getattr(self.config, 'api_rate_limit_per_hour', 1000)
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour
        )
        
        # CORS (handled by SecurityMiddleware, but can add explicit CORS here if needed)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )
    
    def _add_routes(self, app: FastAPI):
        """Add API routes to FastAPI app."""
        auth_middleware = AuthenticationMiddleware()
        
        # Health check (no auth required)
        @app.get("/health", response_model=HealthCheckResponse)
        async def health_check():
            """Health check endpoint."""
            return await self.endpoints.health_check()
        
        # Authentication endpoints
        @app.post("/auth/token", response_model=AuthTokenResponse)
        async def create_auth_token(request: AuthTokenRequest):
            """Create authentication token."""
            try:
                # Validate API key if provided
                if request.api_key:
                    api_key = self.auth_manager.validate_api_key(request.api_key)
                    if not api_key:
                        raise HTTPException(status_code=401, detail="Invalid API key")
                    
                    # Create JWT token
                    token = self.auth_manager.create_jwt_token(
                        user_id=api_key.key_id,
                        scopes=request.scope or api_key.scopes
                    )
                    
                    return AuthTokenResponse(
                        success=True,
                        message="Token created",
                        token=token,
                        expires_in=24 * 3600,  # 24 hours
                        scope=request.scope or api_key.scopes
                    )
                
                # For now, require API key authentication
                raise HTTPException(status_code=401, detail="API key required")
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error("Token creation failed", extra={"error": str(e)})
                raise HTTPException(status_code=500, detail="Token creation failed")
        
        # Analytics endpoints
        @app.post("/analytics/query", response_model=AnalyticsDataResponse)
        async def query_analytics(
            request: AnalyticsQueryRequest,
            current_user: Optional[Dict] = Depends(auth_middleware.get_current_user)
        ):
            """Query analytics data."""
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            if not self.auth_manager.check_permission(current_user['scopes'], 'analytics:read'):
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            
            return await self.endpoints.query_analytics(request, current_user)
        
        @app.get("/analytics/categories")
        async def get_analytics_categories(
            current_user: Optional[Dict] = Depends(auth_middleware.get_current_user)
        ):
            """Get available analytics categories."""
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            return APIResponse(
                success=True,
                message="Analytics categories retrieved",
                data={
                    "categories": [
                        "usage_summary", "tool_usage", "server_analytics",
                        "recommendations", "api_usage", "trending_queries",
                        "performance_metrics"
                    ]
                }
            )
        
        # Tools endpoints
        @app.post("/tools/search")
        async def search_tools(
            request: ToolSearchRequest,
            current_user: Optional[Dict] = Depends(auth_middleware.get_current_user)
        ):
            """Search for tools."""
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            if not self.auth_manager.check_permission(current_user['scopes'], 'tools:read'):
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            
            return await self.endpoints.search_tools(request, current_user)
        
        @app.get("/tools/categories")
        async def get_tool_categories(
            current_user: Optional[Dict] = Depends(auth_middleware.get_current_user)
        ):
            """Get available tool categories."""
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            return await self.endpoints.get_tool_categories(current_user)
        
        # Servers endpoints
        @app.get("/servers", response_model=ServerListResponse)
        async def list_servers(
            current_user: Optional[Dict] = Depends(auth_middleware.get_current_user),
            status: Optional[str] = None,
            server_type: Optional[str] = None
        ):
            """List MCP servers."""
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            if not self.auth_manager.check_permission(current_user['scopes'], 'servers:read'):
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            
            return await self.endpoints.list_servers(current_user, status, server_type)
        
        # Export endpoints
        @app.post("/export")
        async def export_data(
            request: ExportRequest,
            current_user: Optional[Dict] = Depends(auth_middleware.get_current_user)
        ):
            """Export data in various formats."""
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            if not self.auth_manager.check_permission(current_user['scopes'], 'analytics:export'):
                raise HTTPException(status_code=403, detail="Insufficient permissions")
            
            return await self.endpoints.export_data(request, current_user)
        
        # Admin endpoints
        @app.get("/admin/api-keys")
        async def list_api_keys(
            current_user: Optional[Dict] = Depends(auth_middleware.get_current_user)
        ):
            """List API keys (admin only)."""
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            if not self.auth_manager.check_permission(current_user['scopes'], 'admin:full'):
                raise HTTPException(status_code=403, detail="Admin access required")
            
            keys = self.auth_manager.list_api_keys()
            return APIResponse(
                success=True,
                message="API keys retrieved",
                data={
                    "api_keys": [key.dict() for key in keys],
                    "stats": self.auth_manager.get_api_key_stats()
                }
            )
        
        @app.post("/admin/api-keys")
        async def create_api_key(
            name: str,
            scopes: List[str],
            expires_days: Optional[int] = None,
            current_user: Optional[Dict] = Depends(auth_middleware.get_current_user)
        ):
            """Create new API key (admin only)."""
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            if not self.auth_manager.check_permission(current_user['scopes'], 'admin:full'):
                raise HTTPException(status_code=403, detail="Admin access required")
            
            try:
                api_key = self.auth_manager.create_api_key(name, scopes, expires_days)
                
                return APIResponse(
                    success=True,
                    message="API key created",
                    data={
                        "key_id": api_key.key_id,
                        "name": api_key.name,
                        "scopes": api_key.scopes,
                        "api_key": getattr(api_key, 'raw_key', None),  # Only shown once
                        "expires_at": api_key.expires_at.isoformat() if api_key.expires_at else None
                    }
                )
                
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        
        @app.get("/admin/stats")
        async def get_api_stats(
            current_user: Optional[Dict] = Depends(auth_middleware.get_current_user)
        ):
            """Get API usage statistics."""
            if not current_user:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            return await self.endpoints.get_api_stats(current_user)
    
    def run(self, host: str = "127.0.0.1", port: int = 8000):
        """Run the API server."""
        import uvicorn
        
        logger.info("Starting API server", extra={
            "host": host,
            "port": port,
            "docs_url": f"http://{host}:{port}/docs"
        })
        
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level="info"
        )


def create_api_server(config=None) -> APIServer:
    """Factory function to create API server."""
    return APIServer(config)