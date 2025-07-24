"""
API models for MCP Manager REST endpoints.

Defines request/response models and validation schemas for all API endpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class APIResponse(BaseModel):
    """Base API response model."""
    
    success: bool = Field(description="Request success status")
    message: str = Field(description="Response message")
    data: Optional[Any] = Field(default=None, description="Response data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")


class ErrorResponse(APIResponse):
    """API error response model."""
    
    success: bool = Field(default=False, description="Always false for errors")
    error_code: str = Field(description="Error code identifier")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Error details")


class AnalyticsQueryRequest(BaseModel):
    """Request model for analytics queries."""
    
    query_type: str = Field(description="Type of analytics query")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Query filters")
    date_range: Optional[Dict[str, str]] = Field(default=None, description="Date range filter")
    limit: int = Field(default=100, ge=1, le=10000, description="Result limit")
    offset: int = Field(default=0, ge=0, description="Result offset")
    
    @validator('query_type')
    def validate_query_type(cls, v):
        allowed_types = [
            'usage_summary', 'tool_usage', 'server_analytics', 'recommendations',
            'api_usage', 'trending_queries', 'performance_metrics'
        ]
        if v not in allowed_types:
            raise ValueError(f"query_type must be one of: {allowed_types}")
        return v


class AnalyticsDataResponse(APIResponse):
    """Response model for analytics data."""
    
    query_type: str = Field(description="Type of query performed")
    total_count: int = Field(description="Total number of results")
    results: List[Dict[str, Any]] = Field(description="Query results")
    aggregations: Optional[Dict[str, Any]] = Field(default=None, description="Aggregated data")


class ToolSearchRequest(BaseModel):
    """Request model for tool search."""
    
    query: str = Field(description="Search query")
    categories: Optional[List[str]] = Field(default=None, description="Category filters")
    server_types: Optional[List[str]] = Field(default=None, description="Server type filters")
    limit: int = Field(default=50, ge=1, le=500, description="Result limit")
    include_unavailable: bool = Field(default=False, description="Include unavailable tools")


class ToolInfoResponse(APIResponse):
    """Response model for tool information."""
    
    canonical_name: str = Field(description="Tool canonical name")
    name: str = Field(description="Tool display name")
    description: str = Field(description="Tool description")
    server_name: str = Field(description="Source server name")
    server_type: str = Field(description="Server type")
    categories: List[str] = Field(description="Tool categories")
    tags: List[str] = Field(description="Tool tags")
    input_schema: Dict[str, Any] = Field(description="Input parameters schema")
    output_schema: Dict[str, Any] = Field(description="Output schema")
    usage_stats: Dict[str, Any] = Field(description="Usage statistics")


class ServerListResponse(APIResponse):
    """Response model for server listing."""
    
    servers: List[Dict[str, Any]] = Field(description="List of servers")
    total_count: int = Field(description="Total server count")
    by_type: Dict[str, int] = Field(description="Server count by type")


class AuthTokenRequest(BaseModel):
    """Request model for authentication token."""
    
    username: Optional[str] = Field(default=None, description="Username")
    api_key: Optional[str] = Field(default=None, description="API key")
    scope: List[str] = Field(default_factory=list, description="Requested scopes")


class AuthTokenResponse(APIResponse):
    """Response model for authentication token."""
    
    token: str = Field(description="JWT access token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(description="Token expiration in seconds")
    scope: List[str] = Field(description="Granted scopes")


class HealthCheckResponse(APIResponse):
    """Response model for health check."""
    
    status: str = Field(description="Health status")
    version: str = Field(description="API version")
    uptime_seconds: float = Field(description="API uptime in seconds")
    database_status: str = Field(description="Database connection status")
    analytics_status: str = Field(description="Analytics service status")
    servers_available: int = Field(description="Number of available servers")


class ExportRequest(BaseModel):
    """Request model for data export."""
    
    export_type: str = Field(description="Type of data to export")
    format: str = Field(default="json", description="Export format")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Export filters")
    
    @validator('format')
    def validate_format(cls, v):
        allowed_formats = ['json', 'csv', 'yaml', 'xml', 'xlsx']
        if v not in allowed_formats:
            raise ValueError(f"format must be one of: {allowed_formats}")
        return v
    
    @validator('export_type')
    def validate_export_type(cls, v):
        allowed_types = [
            'analytics', 'tools', 'servers', 'usage_history', 'configurations'
        ]
        if v not in allowed_types:
            raise ValueError(f"export_type must be one of: {allowed_types}")
        return v


class ConfigurationRequest(BaseModel):
    """Request model for configuration updates."""
    
    section: str = Field(description="Configuration section")
    updates: Dict[str, Any] = Field(description="Configuration updates")
    validate_only: bool = Field(default=False, description="Only validate without applying")


class ConfigurationResponse(APIResponse):
    """Response model for configuration operations."""
    
    section: str = Field(description="Configuration section")
    current_config: Dict[str, Any] = Field(description="Current configuration")
    validation_errors: List[str] = Field(default_factory=list, description="Validation errors")