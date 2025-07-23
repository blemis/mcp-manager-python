"""
Proxy mode configuration for MCP Manager.

Provides configuration models and validation for optional proxy mode operation.
Proxy mode allows MCP Manager to act as a unified endpoint for all MCP servers.
"""

import os
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class LoadBalanceStrategy(str, Enum):
    """Load balancing strategies for identical servers."""
    
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    LEAST_RESPONSE_TIME = "least_response_time"
    RANDOM = "random"


class ProxyModeConfig(BaseModel):
    """Configuration for MCP proxy mode operation."""
    
    # Core proxy settings
    enabled: bool = Field(
        default_factory=lambda: os.getenv("MCP_PROXY_MODE", "false").lower() == "true",
        description="Enable proxy mode operation"
    )
    port: int = Field(
        default_factory=lambda: int(os.getenv("MCP_PROXY_PORT", "3000")),
        description="Proxy server port"
    )
    host: str = Field(
        default_factory=lambda: os.getenv("MCP_PROXY_HOST", "localhost"),
        description="Proxy server host"  
    )
    
    # Authentication settings
    enable_auth: bool = Field(
        default_factory=lambda: os.getenv("MCP_PROXY_AUTH", "false").lower() == "true",
        description="Enable proxy authentication"
    )
    auth_token: Optional[str] = Field(
        default_factory=lambda: os.getenv("MCP_PROXY_TOKEN"),
        description="Authentication token for proxy access"
    )
    allowed_clients: List[str] = Field(
        default_factory=lambda: os.getenv("MCP_PROXY_ALLOWED_CLIENTS", "").split(",") if os.getenv("MCP_PROXY_ALLOWED_CLIENTS") else [],
        description="List of allowed client IPs or hostnames"
    )
    
    # Performance settings
    enable_caching: bool = Field(
        default_factory=lambda: os.getenv("MCP_PROXY_CACHE", "true").lower() == "true",
        description="Enable response caching"
    )
    cache_ttl_seconds: int = Field(
        default_factory=lambda: int(os.getenv("MCP_PROXY_CACHE_TTL", "300")),
        description="Cache TTL in seconds"
    )
    max_concurrent_requests: int = Field(
        default_factory=lambda: int(os.getenv("MCP_PROXY_MAX_CONCURRENT", "50")),
        description="Maximum concurrent requests"
    )
    request_timeout_seconds: int = Field(
        default_factory=lambda: int(os.getenv("MCP_PROXY_TIMEOUT", "30")),
        description="Request timeout in seconds"
    )
    
    # Load balancing for identical servers
    enable_load_balancing: bool = Field(
        default_factory=lambda: os.getenv("MCP_PROXY_LOAD_BALANCE", "false").lower() == "true",
        description="Enable load balancing for identical servers"
    )
    load_balance_strategy: LoadBalanceStrategy = Field(
        default_factory=lambda: LoadBalanceStrategy(os.getenv("MCP_PROXY_LB_STRATEGY", "round_robin")),
        description="Load balancing strategy"
    )
    
    # Analytics integration
    enable_proxy_analytics: bool = Field(
        default_factory=lambda: os.getenv("MCP_PROXY_ANALYTICS", "true").lower() == "true",
        description="Enable proxy analytics tracking"
    )
    log_all_requests: bool = Field(
        default_factory=lambda: os.getenv("MCP_PROXY_LOG_REQUESTS", "false").lower() == "true",
        description="Log all proxy requests (may impact performance)"
    )
    
    # Rate limiting
    enable_rate_limiting: bool = Field(
        default_factory=lambda: os.getenv("MCP_PROXY_RATE_LIMIT", "false").lower() == "true",
        description="Enable rate limiting"
    )
    rate_limit_requests_per_minute: int = Field(
        default_factory=lambda: int(os.getenv("MCP_PROXY_RATE_LIMIT_RPM", "100")),
        description="Rate limit: requests per minute per client"
    )
    
    # Server selection and routing
    prefer_local_servers: bool = Field(
        default_factory=lambda: os.getenv("MCP_PROXY_PREFER_LOCAL", "true").lower() == "true",
        description="Prefer local servers over remote ones for performance"
    )
    server_health_check_interval: int = Field(
        default_factory=lambda: int(os.getenv("MCP_PROXY_HEALTH_CHECK_INTERVAL", "30")),
        description="Server health check interval in seconds"
    )
    
    @field_validator('port')
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate port number is in valid range."""
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v
    
    @field_validator('cache_ttl_seconds', 'request_timeout_seconds', 'server_health_check_interval')
    @classmethod
    def validate_positive_int(cls, v: int) -> int:
        """Validate integer values are positive."""
        if v <= 0:
            raise ValueError("Value must be positive")
        return v
    
    @field_validator('max_concurrent_requests', 'rate_limit_requests_per_minute')
    @classmethod
    def validate_positive_nonzero_int(cls, v: int) -> int:
        """Validate integer values are positive and non-zero."""
        if v < 1:
            raise ValueError("Value must be at least 1")
        return v
    
    @field_validator('host')
    @classmethod
    def validate_host(cls, v: str) -> str:
        """Validate host is not empty."""
        if not v.strip():
            raise ValueError("Host cannot be empty")
        return v.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return self.model_dump()
    
    def get_proxy_endpoint(self) -> str:
        """Get the full proxy endpoint URL."""
        return f"http://{self.host}:{self.port}"
    
    def get_mcp_endpoint(self) -> str:
        """Get the MCP-specific endpoint URL."""
        return f"{self.get_proxy_endpoint()}/mcp/v1/rpc"
    
    def is_authentication_required(self) -> bool:
        """Check if authentication is properly configured."""
        return self.enable_auth and bool(self.auth_token)
    
    def get_performance_settings(self) -> Dict[str, Any]:
        """Get performance-related settings."""
        return {
            "max_concurrent_requests": self.max_concurrent_requests,
            "request_timeout_seconds": self.request_timeout_seconds,
            "enable_caching": self.enable_caching,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "enable_load_balancing": self.enable_load_balancing,
            "load_balance_strategy": self.load_balance_strategy.value
        }
    
    def get_monitoring_settings(self) -> Dict[str, Any]:
        """Get monitoring and analytics settings."""
        return {
            "enable_proxy_analytics": self.enable_proxy_analytics,
            "log_all_requests": self.log_all_requests,
            "enable_rate_limiting": self.enable_rate_limiting,
            "rate_limit_rpm": self.rate_limit_requests_per_minute
        }


class ValidationResult(BaseModel):
    """Result of proxy configuration validation."""
    
    valid: bool = Field(description="Whether configuration is valid")
    issues: List[str] = Field(default_factory=list, description="Configuration issues")
    warnings: List[str] = Field(default_factory=list, description="Configuration warnings")
    recommendations: List[str] = Field(default_factory=list, description="Configuration recommendations")
    
    @property
    def has_issues(self) -> bool:
        """Check if there are any validation issues."""
        return len(self.issues) > 0
    
    @property
    def has_warnings(self) -> bool:
        """Check if there are any validation warnings."""
        return len(self.warnings) > 0
    
    def add_issue(self, message: str) -> None:
        """Add a validation issue."""
        self.issues.append(message)
        self.valid = False
    
    def add_warning(self, message: str) -> None:
        """Add a validation warning."""
        self.warnings.append(message)
    
    def add_recommendation(self, message: str) -> None:
        """Add a configuration recommendation."""
        self.recommendations.append(message)