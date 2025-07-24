"""
Data models for MCP Manager.

Defines Pydantic models for MCP servers, configurations, and other
core data structures with validation and serialization support.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class ServerScope(str, Enum):
    """MCP server configuration scope."""
    
    LOCAL = "local"      # Private to user account
    PROJECT = "project"  # Shared with team via git
    USER = "user"        # Global user configuration


class ServerStatus(str, Enum):
    """MCP server status."""
    
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    UNKNOWN = "unknown"


class ServerType(str, Enum):
    """MCP server type."""
    
    NPM = "npm"
    DOCKER = "docker"
    DOCKER_DESKTOP = "docker-desktop"
    CUSTOM = "custom"


class TaskCategory(str, Enum):
    """Task categories for AI curation and workflow management."""
    
    WEB_DEVELOPMENT = "web-development"
    DATA_ANALYSIS = "data-analysis"
    SYSTEM_ADMINISTRATION = "system-administration"
    RESEARCH = "research"
    AUTOMATION = "automation"
    TESTING = "testing"
    GENERAL = "general"


class Server(BaseModel):
    """MCP server configuration."""
    
    name: str = Field(description="Server name")
    command: str = Field(description="Command to run the server")
    scope: ServerScope = Field(description="Configuration scope")
    server_type: ServerType = Field(description="Server type")
    description: Optional[str] = Field(default=None, description="Server description")
    enabled: bool = Field(default=True, description="Whether server is enabled")
    args: List[str] = Field(default_factory=list, description="Command arguments")
    env: Dict[str, str] = Field(default_factory=dict, description="Environment variables")
    working_dir: Optional[str] = Field(default=None, description="Working directory")
    timeout: int = Field(default=30, description="Timeout in seconds")
    auto_restart: bool = Field(default=True, description="Auto-restart on failure")
    suites: List[str] = Field(default_factory=list, description="Suite tags this server belongs to")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation time")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update time")
    
    # Runtime status
    status: ServerStatus = Field(default=ServerStatus.UNKNOWN, description="Current status")
    pid: Optional[int] = Field(default=None, description="Process ID if running")
    last_started: Optional[datetime] = Field(default=None, description="Last start time")
    last_error: Optional[str] = Field(default=None, description="Last error message")
    restart_count: int = Field(default=0, description="Number of restarts")
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate server name."""
        if not v.strip():
            raise ValueError("Server name cannot be empty")
        if len(v) > 100:
            raise ValueError("Server name too long (max 100 characters)")
        return v.strip()
        
    @field_validator("command")
    @classmethod
    def validate_command(cls, v: str) -> str:
        """Validate server command."""
        if not v.strip():
            raise ValueError("Server command cannot be empty")
        return v.strip()
        
    def __str__(self) -> str:
        """String representation."""
        return f"{self.name} ({self.scope.value})"
        
    def to_claude_config(self) -> Dict[str, Any]:
        """Convert to Claude configuration format."""
        config = {
            "command": self.command,
            "args": self.args,
        }
        
        if self.env:
            config["env"] = self.env
            
        if self.working_dir:
            config["cwd"] = self.working_dir
            
        return config


class ServerCollection(BaseModel):
    """Collection of servers grouped by scope."""
    
    local: List[Server] = Field(default_factory=list, description="Local servers")
    project: List[Server] = Field(default_factory=list, description="Project servers") 
    user: List[Server] = Field(default_factory=list, description="User servers")
    
    def all_servers(self) -> List[Server]:
        """Get all servers across all scopes."""
        return self.local + self.project + self.user
        
    def get_by_name(self, name: str) -> Optional[Server]:
        """Get server by name."""
        for server in self.all_servers():
            if server.name == name:
                return server
        return None
        
    def get_by_scope(self, scope: ServerScope) -> List[Server]:
        """Get servers by scope."""
        if scope == ServerScope.LOCAL:
            return self.local
        elif scope == ServerScope.PROJECT:
            return self.project  
        elif scope == ServerScope.USER:
            return self.user
        return []
        
    def add_server(self, server: Server) -> None:
        """Add server to appropriate scope."""
        if server.scope == ServerScope.LOCAL:
            self.local.append(server)
        elif server.scope == ServerScope.PROJECT:
            self.project.append(server)
        elif server.scope == ServerScope.USER:
            self.user.append(server)
            
    def remove_server(self, name: str, scope: Optional[ServerScope] = None) -> bool:
        """Remove server by name and optional scope."""
        scopes_to_check = [scope] if scope else list(ServerScope)
        
        for check_scope in scopes_to_check:
            servers = self.get_by_scope(check_scope)
            for i, server in enumerate(servers):
                if server.name == name:
                    servers.pop(i)
                    return True
        return False


class DiscoveryResult(BaseModel):
    """Server discovery result."""
    
    name: str = Field(description="Server name")
    package: str = Field(description="Package name")
    version: str = Field(description="Version")
    description: Optional[str] = Field(default=None, description="Description")
    author: Optional[str] = Field(default=None, description="Author")
    homepage: Optional[str] = Field(default=None, description="Homepage URL")
    repository: Optional[str] = Field(default=None, description="Repository URL")
    keywords: List[str] = Field(default_factory=list, description="Keywords")
    server_type: ServerType = Field(description="Server type")
    install_command: str = Field(description="Installation command")
    install_args: List[str] = Field(default_factory=list, description="Installation command arguments")
    downloads: Optional[int] = Field(default=None, description="Download count")
    last_updated: Optional[datetime] = Field(default=None, description="Last update")
    
    def to_server(self, scope: ServerScope = ServerScope.USER) -> Server:
        """Convert discovery result to server configuration."""
        return Server(
            name=self.name,
            command=self.install_command,
            scope=scope,
            server_type=self.server_type,
            description=self.description,
        )


class SystemInfo(BaseModel):
    """System information and dependencies."""
    
    python_version: str = Field(description="Python version")
    platform: str = Field(description="Platform")
    claude_cli_available: bool = Field(description="Claude CLI available")
    claude_cli_version: Optional[str] = Field(default=None, description="Claude CLI version")
    npm_available: bool = Field(description="NPM available") 
    npm_version: Optional[str] = Field(default=None, description="NPM version")
    docker_available: bool = Field(description="Docker available")
    docker_version: Optional[str] = Field(default=None, description="Docker version")
    git_available: bool = Field(description="Git available")
    git_version: Optional[str] = Field(default=None, description="Git version")
    config_dir: Path = Field(description="Configuration directory")
    log_file: Optional[Path] = Field(default=None, description="Log file path")
    
    @property
    def all_dependencies_met(self) -> bool:
        """Check if all required dependencies are available."""
        return self.claude_cli_available


class ToolRegistry(BaseModel):
    """Registry entry for discovered MCP tools."""
    
    id: Optional[int] = Field(default=None, description="Database ID")
    name: str = Field(description="Tool name")
    canonical_name: str = Field(description="Canonical name (server_name/tool_name)")
    description: str = Field(default="", description="Tool description")
    server_name: str = Field(description="Source server name")
    server_type: ServerType = Field(description="Server type")
    input_schema: Dict[str, Any] = Field(default_factory=dict, description="Tool input schema")
    output_schema: Dict[str, Any] = Field(default_factory=dict, description="Tool output schema")
    categories: List[str] = Field(default_factory=list, description="Tool categories")
    tags: List[str] = Field(default_factory=list, description="Tool tags")
    last_discovered: datetime = Field(default_factory=datetime.utcnow, description="Last discovery time")
    is_available: bool = Field(default=True, description="Tool availability status")
    usage_count: int = Field(default=0, description="Usage count")
    success_rate: float = Field(default=0.0, description="Success rate (0.0-1.0)")
    average_response_time: float = Field(default=0.0, description="Average response time in seconds")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    discovered_by: str = Field(default="manual", description="Discovery method/version")
    
    @field_validator('canonical_name')
    @classmethod
    def validate_canonical_name(cls, v: str) -> str:
        """Validate canonical name format."""
        if '/' not in v:
            raise ValueError("Canonical name must include server_name/tool_name format")
        return v
    
    @field_validator('success_rate')
    @classmethod
    def validate_success_rate(cls, v: float) -> float:
        """Validate success rate is between 0.0 and 1.0."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Success rate must be between 0.0 and 1.0")
        return v


class ToolUsageAnalytics(BaseModel):
    """Analytics entry for tool usage tracking."""
    
    id: Optional[int] = Field(default=None, description="Database ID") 
    tool_canonical_name: str = Field(description="Tool canonical name")
    user_query: str = Field(default="", description="Original user query")
    selected: bool = Field(description="Whether tool was selected")
    success: bool = Field(default=False, description="Whether execution was successful")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Usage timestamp")
    context: Dict[str, Any] = Field(default_factory=dict, description="Usage context")
    response_time_ms: int = Field(default=0, description="Response time in milliseconds")
    error_details: Optional[str] = Field(default=None, description="Error details if failed")
    session_id: Optional[str] = Field(default=None, description="User session identifier")
    
    @field_validator('tool_canonical_name')
    @classmethod
    def validate_canonical_name(cls, v: str) -> str:
        """Validate tool canonical name format."""
        if '/' not in v:
            raise ValueError("Tool canonical name must include server_name/tool_name format")
        return v
    
    @field_validator('response_time_ms')
    @classmethod
    def validate_response_time(cls, v: int) -> int:
        """Validate response time is non-negative."""
        if v < 0:
            raise ValueError("Response time must be non-negative")
        return v


class RecommendationAnalytics(BaseModel):
    """Analytics for AI-powered tool recommendations."""
    
    id: Optional[int] = Field(default=None, description="Database ID")
    session_id: str = Field(description="Recommendation session ID")
    user_query: str = Field(description="Original user query")
    query_category: Optional[str] = Field(default=None, description="Inferred query category")
    recommendations_count: int = Field(description="Number of recommendations provided")
    llm_provider: str = Field(description="LLM provider used")
    model_used: str = Field(description="Specific model used")
    processing_time_ms: int = Field(description="Total processing time")
    tools_analyzed: int = Field(description="Number of tools analyzed")
    user_selected_tool: Optional[str] = Field(default=None, description="Tool user actually selected")
    user_satisfaction_score: Optional[float] = Field(default=None, description="User satisfaction (0-1)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Recommendation timestamp")
    context_data: Dict[str, Any] = Field(default_factory=dict, description="Request context")
    
    @field_validator('user_satisfaction_score')
    @classmethod
    def validate_satisfaction(cls, v: Optional[float]) -> Optional[float]:
        """Validate satisfaction score is between 0.0 and 1.0."""
        if v is not None and not 0.0 <= v <= 1.0:
            raise ValueError("Satisfaction score must be between 0.0 and 1.0")
        return v


class ServerAnalytics(BaseModel):
    """Analytics for MCP server performance and usage."""
    
    id: Optional[int] = Field(default=None, description="Database ID")
    server_name: str = Field(description="Server name")
    server_type: ServerType = Field(description="Server type")
    date: datetime = Field(description="Analytics date (daily aggregation)")
    total_tools: int = Field(default=0, description="Total tools available")
    active_tools: int = Field(default=0, description="Tools used at least once")
    total_requests: int = Field(default=0, description="Total tool requests")
    successful_requests: int = Field(default=0, description="Successful requests")
    average_response_time_ms: float = Field(default=0.0, description="Average response time")
    peak_concurrent_usage: int = Field(default=0, description="Peak concurrent usage")
    uptime_percentage: float = Field(default=100.0, description="Server uptime percentage")
    error_rate: float = Field(default=0.0, description="Error rate (0-1)")
    discovery_success_rate: float = Field(default=1.0, description="Tool discovery success rate")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    @field_validator('uptime_percentage', 'error_rate', 'discovery_success_rate')
    @classmethod
    def validate_percentage(cls, v: float) -> float:
        """Validate percentage values are between 0.0 and 1.0."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Percentage values must be between 0.0 and 1.0")
        return v


class QueryPattern(BaseModel):
    """Analytics for user query patterns and trends."""
    
    id: Optional[int] = Field(default=None, description="Database ID")
    query_hash: str = Field(description="Hashed query for privacy")
    query_category: str = Field(description="Categorized query type")
    query_keywords: List[str] = Field(default_factory=list, description="Extracted keywords")
    frequency: int = Field(default=1, description="Query frequency count")
    success_rate: float = Field(default=0.0, description="Query success rate")
    average_recommendation_count: float = Field(default=0.0, description="Average recommendations provided")
    most_selected_tools: List[str] = Field(default_factory=list, description="Most commonly selected tools")
    first_seen: datetime = Field(default_factory=datetime.utcnow, description="First occurrence")
    last_seen: datetime = Field(default_factory=datetime.utcnow, description="Last occurrence")
    trending_score: float = Field(default=0.0, description="Trending score based on recent activity")
    
    @field_validator('success_rate')
    @classmethod
    def validate_success_rate(cls, v: float) -> float:
        """Validate success rate is between 0.0 and 1.0."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Success rate must be between 0.0 and 1.0")
        return v


class APIUsageAnalytics(BaseModel):
    """Analytics for API endpoint usage and performance."""
    
    id: Optional[int] = Field(default=None, description="Database ID")
    endpoint: str = Field(description="API endpoint path")
    method: str = Field(description="HTTP method")
    date: datetime = Field(description="Usage date (hourly aggregation)")
    request_count: int = Field(default=0, description="Number of requests")
    success_count: int = Field(default=0, description="Successful requests")
    error_count: int = Field(default=0, description="Error requests")
    average_response_time_ms: float = Field(default=0.0, description="Average response time")
    max_response_time_ms: int = Field(default=0, description="Maximum response time")
    data_transferred_bytes: int = Field(default=0, description="Total data transferred")
    unique_clients: int = Field(default=0, description="Number of unique client IPs")
    rate_limited_requests: int = Field(default=0, description="Rate limited requests")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.request_count == 0:
            return 0.0
        return self.success_count / self.request_count
    
    @property
    def error_rate(self) -> float:
        """Calculate error rate.""" 
        if self.request_count == 0:
            return 0.0
        return self.error_count / self.request_count