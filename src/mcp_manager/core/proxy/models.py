"""
Data models for MCP Proxy Server functionality.

Defines the data structures used for proxy configuration, request routing,
and protocol translation between different MCP server implementations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ProxyMode(Enum):
    """Proxy server operation modes."""
    TRANSPARENT = "transparent"      # Pass-through with minimal modification
    AGGREGATING = "aggregating"      # Combine responses from multiple servers
    LOAD_BALANCING = "load_balancing"  # Distribute load across servers
    FAILOVER = "failover"            # Automatic failover on errors


class ProtocolVersion(Enum): 
    """MCP protocol versions supported."""
    MCP_V1 = "mcp-v1"
    MCP_V2 = "mcp-v2"
    LEGACY = "legacy"


class ServerStatus(Enum):
    """MCP server status states."""
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    INITIALIZING = "initializing"
    TIMEOUT = "timeout"


@dataclass
class ProxyServerConfig:
    """Configuration for individual MCP server in proxy."""
    
    name: str
    url: str
    protocol_version: ProtocolVersion
    weight: int = 100  # Load balancing weight
    timeout_seconds: int = 30
    max_retries: int = 3
    health_check_interval: int = 60
    
    # Authentication
    auth_method: Optional[str] = None  # "api_key", "oauth", "basic"
    auth_credentials: Optional[Dict[str, str]] = None
    
    # Protocol-specific settings
    headers: Dict[str, str] = field(default_factory=dict)
    connection_params: Dict[str, Any] = field(default_factory=dict)
    
    # Server capabilities
    supported_tools: List[str] = field(default_factory=list)
    supported_resources: List[str] = field(default_factory=list)
    supported_prompts: List[str] = field(default_factory=list)


@dataclass
class ProxyConfig:
    """Main proxy server configuration."""
    
    # Server settings
    host: str = "127.0.0.1"
    port: int = 3001
    workers: int = 4
    
    # Proxy behavior
    mode: ProxyMode = ProxyMode.TRANSPARENT
    timeout_seconds: int = 30
    max_concurrent_requests: int = 100
    
    # Routing and load balancing
    enable_load_balancing: bool = True
    enable_failover: bool = True
    health_check_enabled: bool = True
    
    # Protocol translation
    enable_protocol_translation: bool = True
    default_protocol_version: ProtocolVersion = ProtocolVersion.MCP_V1
    
    # Logging and monitoring
    enable_request_logging: bool = True
    enable_metrics: bool = True
    log_level: str = "INFO"
    
    # Server list
    servers: List[ProxyServerConfig] = field(default_factory=list)


class ProxyRequest(BaseModel):
    """Standardized proxy request format."""
    
    method: str = Field(..., description="MCP method name")
    params: Optional[Dict[str, Any]] = Field(default=None, description="Method parameters")
    id: Optional[Union[str, int]] = Field(default=None, description="Request ID")
    
    # Proxy-specific metadata
    target_server: Optional[str] = Field(default=None, description="Target server name")
    protocol_version: Optional[str] = Field(default=None, description="Required protocol version")
    timeout: Optional[int] = Field(default=None, description="Request timeout override")
    
    # Request context
    user_id: Optional[str] = Field(default=None, description="User identifier")
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ProxyResponse(BaseModel):
    """Standardized proxy response format."""
    
    id: Optional[Union[str, int]] = Field(default=None, description="Request ID")
    result: Optional[Any] = Field(default=None, description="Response result")
    error: Optional[Dict[str, Any]] = Field(default=None, description="Error information")
    
    # Proxy metadata
    server_name: Optional[str] = Field(default=None, description="Source server name")
    processing_time_ms: Optional[float] = Field(default=None, description="Processing time")
    protocol_version: Optional[str] = Field(default=None, description="Protocol version used")
    
    # Aggregated responses (for aggregating mode)
    aggregated_results: Optional[List[Dict[str, Any]]] = Field(default=None, description="Multiple server results")
    
    # Error handling
    retried: bool = Field(default=False, description="Whether request was retried")
    failover_used: bool = Field(default=False, description="Whether failover was used")


@dataclass
class ServerHealth:
    """Health status for MCP server."""
    
    name: str
    status: ServerStatus
    last_check: datetime
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    consecutive_failures: int = 0
    uptime_percentage: float = 100.0
    
    # Capabilities discovered during health check
    available_tools: List[str] = field(default_factory=list)
    available_resources: List[str] = field(default_factory=list)
    available_prompts: List[str] = field(default_factory=list)


@dataclass
class ProxyStats:
    """Proxy server statistics."""
    
    # Request statistics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    
    # Timing statistics
    average_response_time_ms: float = 0.0
    min_response_time_ms: float = 0.0
    max_response_time_ms: float = 0.0
    
    # Server statistics
    active_servers: int = 0
    total_servers: int = 0
    
    # Load balancing
    requests_per_server: Dict[str, int] = field(default_factory=dict)
    errors_per_server: Dict[str, int] = field(default_factory=dict)
    
    # Protocol translation
    protocol_translations: Dict[str, int] = field(default_factory=dict)
    
    # Time tracking
    start_time: datetime = field(default_factory=datetime.utcnow)
    last_reset: datetime = field(default_factory=datetime.utcnow)


class RouteRule(BaseModel):
    """Rules for routing requests to specific servers."""
    
    name: str = Field(..., description="Rule name")
    priority: int = Field(default=50, description="Rule priority (higher = more important)")
    
    # Matching conditions
    method_pattern: Optional[str] = Field(default=None, description="Method name pattern")
    tool_name: Optional[str] = Field(default=None, description="Specific tool name") 
    resource_pattern: Optional[str] = Field(default=None, description="Resource pattern")
    user_id: Optional[str] = Field(default=None, description="Specific user ID")
    
    # Routing target
    target_servers: List[str] = Field(..., description="Target server names")
    load_balance: bool = Field(default=True, description="Load balance among targets")
    
    # Behavior modifiers
    enable_failover: bool = Field(default=True, description="Enable failover for this rule")
    timeout_override: Optional[int] = Field(default=None, description="Timeout override")


class ProxyMetrics(BaseModel):
    """Real-time proxy metrics."""
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Current load
    active_connections: int = Field(default=0)
    pending_requests: int = Field(default=0)
    
    # Rate statistics
    requests_per_second: float = Field(default=0.0)
    errors_per_second: float = Field(default=0.0)
    
    # Server health
    server_health: Dict[str, str] = Field(default_factory=dict)  # server_name -> status
    
    # Resource usage
    memory_usage_mb: Optional[float] = Field(default=None)
    cpu_usage_percent: Optional[float] = Field(default=None)
    
    # Protocol breakdown
    protocol_usage: Dict[str, int] = Field(default_factory=dict)  # protocol -> count