"""
Data models for MCP Manager.

Defines Pydantic models for MCP servers, configurations, and other
core data structures with validation and serialization support.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


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
    CUSTOM = "custom"


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
    created_at: datetime = Field(default_factory=datetime.now, description="Creation time")
    updated_at: datetime = Field(default_factory=datetime.now, description="Last update time")
    
    # Runtime status
    status: ServerStatus = Field(default=ServerStatus.UNKNOWN, description="Current status")
    pid: Optional[int] = Field(default=None, description="Process ID if running")
    last_started: Optional[datetime] = Field(default=None, description="Last start time")
    last_error: Optional[str] = Field(default=None, description="Last error message")
    restart_count: int = Field(default=0, description="Number of restarts")
    
    @validator("name")
    def validate_name(cls, v: str) -> str:
        """Validate server name."""
        if not v.strip():
            raise ValueError("Server name cannot be empty")
        if len(v) > 100:
            raise ValueError("Server name too long (max 100 characters)")
        return v.strip()
        
    @validator("command")  
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