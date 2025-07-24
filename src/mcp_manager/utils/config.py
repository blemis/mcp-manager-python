"""
Configuration management for MCP Manager.

Provides hierarchical configuration loading with validation using Pydantic.
Supports multiple configuration sources and environment variable overrides.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import toml
from pydantic import BaseModel, Field, field_validator
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)

# Import proxy config with lazy loading to avoid circular imports
def _get_proxy_config_class():
    """Lazy import of ProxyModeConfig to avoid circular imports."""
    try:
        from mcp_manager.core.config.proxy_config import ProxyModeConfig
        return ProxyModeConfig
    except ImportError:
        # Return a dummy class if proxy config is not available
        class DummyProxyConfig(BaseModel):
            enabled: bool = False
        return DummyProxyConfig


class LoggingConfig(BaseModel):
    """Logging configuration."""
    
    enabled: bool = Field(default=True, description="Enable logging completely")
    level: str = Field(default="INFO", description="File logging level")
    console_level: str = Field(default="WARNING", description="Console logging level")
    format_type: str = Field(default="text", description="Log format (text/json)")
    file: Optional[str] = Field(default="mcp-manager.log", description="Log file path")
    enable_rich: bool = Field(default=True, description="Enable Rich console output")
    max_bytes: int = Field(default=10 * 1024 * 1024, description="Max log file size")
    backup_count: int = Field(default=5, description="Number of backup files")
    suppress_http: bool = Field(default=False, description="Suppress HTTP request logging")
    
    @field_validator("level", "console_level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate logging level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}")
        return v.upper()
        
    @field_validator("format_type")
    @classmethod
    def validate_format_type(cls, v: str) -> str:
        """Validate format type."""
        if v not in ["text", "json"]:
            raise ValueError(f"Invalid format type: {v}")
        return v


class ClaudeConfig(BaseModel):
    """Claude CLI configuration."""
    
    cli_path: str = Field(default="claude", description="Path to Claude CLI")
    config_path: str = Field(
        default="~/.config/claude-code/mcp-servers.json",
        description="Path to Claude MCP configuration"
    )
    timeout: int = Field(default=30, description="Command timeout in seconds")


class DiscoveryConfig(BaseModel):
    """Server discovery configuration."""
    
    npm_registry: str = Field(
        default="https://registry.npmjs.org",
        description="NPM registry URL"
    )
    docker_registry: str = Field(
        default="docker.io",
        description="Docker registry URL"
    )
    cache_ttl: int = Field(default=3600, description="Cache TTL in seconds")
    max_results: int = Field(default=100, description="Maximum search results")


class UIConfig(BaseModel):
    """User interface configuration."""
    
    theme: str = Field(default="dark", description="UI theme")
    animations: bool = Field(default=True, description="Enable animations")
    confirm_destructive: bool = Field(
        default=True,
        description="Confirm destructive operations"
    )
    auto_refresh: int = Field(
        default=5,
        description="Auto-refresh interval in seconds"
    )
    
    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v: str) -> str:
        """Validate theme."""
        if v not in ["dark", "light"]:
            raise ValueError(f"Invalid theme: {v}")
        return v


class ChangeDetectionConfig(BaseModel):
    """Configuration for external change detection and monitoring."""
    
    enabled: bool = Field(default=True, description="Enable change detection")
    check_interval: int = Field(default=60, description="Check interval in seconds")
    auto_sync: bool = Field(default=False, description="Automatically sync detected changes")
    notifications_enabled: bool = Field(default=True, description="Enable change notifications")
    max_history: int = Field(default=1000, description="Maximum change history to keep")
    watch_docker_config: bool = Field(default=True, description="Watch Docker MCP configuration")
    watch_claude_configs: bool = Field(default=True, description="Watch Claude configurations")
    ignored_servers: List[str] = Field(default_factory=list, description="Servers to ignore during detection")
    sync_on_startup: bool = Field(default=False, description="Sync changes on startup")
    
    @field_validator("check_interval")
    @classmethod
    def validate_check_interval(cls, v: int) -> int:
        """Validate check interval."""
        if v < 10:
            raise ValueError("Check interval must be at least 10 seconds")
        return v


class Config(BaseSettings):
    """Main configuration class."""
    
    # Core settings
    debug: bool = Field(default=False, description="Enable debug mode")
    verbose: bool = Field(default=False, description="Enable verbose output")
    config_dir: str = Field(
        default="~/.config/mcp-manager",
        description="Configuration directory"
    )
    
    # Component configurations
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    claude: ClaudeConfig = Field(default_factory=ClaudeConfig)
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    change_detection: ChangeDetectionConfig = Field(default_factory=ChangeDetectionConfig)
    
    # Proxy configuration (initialized lazily)
    _proxy: Optional[Any] = None
    
    def __init__(self, **data):
        # Initialize proxy config lazily
        super().__init__(**data)
        self._init_proxy_config()
    
    def _init_proxy_config(self):
        """Initialize proxy configuration."""
        if self._proxy is None:
            ProxyConfig = _get_proxy_config_class()
            self._proxy = ProxyConfig()
    
    @property
    def proxy(self):
        """Get proxy configuration with lazy loading."""
        if self._proxy is None:
            self._init_proxy_config()
        return self._proxy
    
    @proxy.setter
    def proxy(self, value):
        """Set proxy configuration."""
        self._proxy = value
    
    model_config = {
        "env_prefix": "MCP_MANAGER_",
        "env_nested_delimiter": "__",
        "case_sensitive": False,
    }
        
    def get_config_dir(self) -> Path:
        """Get configuration directory path."""
        return Path(os.path.expanduser(self.config_dir))
        
    def get_log_file(self) -> Optional[Path]:
        """Get log file path."""
        if self.logging.file:
            log_path = Path(os.path.expanduser(self.logging.file))
            if not log_path.is_absolute():
                log_path = self.get_config_dir() / log_path
            return log_path
        return None
        
    def get_claude_config_path(self) -> Path:
        """Get Claude configuration path."""
        return Path(os.path.expanduser(self.claude.config_path))
    
    @property
    def database_path(self) -> Path:
        """Get database path."""
        db_path = os.getenv("MCP_MANAGER_DB_PATH")
        if db_path:
            return Path(os.path.expanduser(db_path))
        
        config_dir = self.get_config_dir()
        return config_dir / "mcp_manager.db"


class ConfigManager:
    """Configuration manager with hierarchical loading."""
    
    def __init__(self):
        self._config: Optional[Config] = None
        
    def load_config(
        self,
        config_files: Optional[List[Union[str, Path]]] = None,
        **overrides: Any,
    ) -> Config:
        """
        Load configuration from multiple sources.
        
        Args:
            config_files: List of configuration files to load
            **overrides: Configuration overrides
            
        Returns:
            Loaded configuration
        """
        if self._config is not None:
            return self._config
            
        # Default configuration files
        if config_files is None:
            config_files = [
                "/etc/mcp-manager/config.toml",
                "~/.config/mcp-manager/config.toml",
                "./.mcp-manager.toml",
            ]
            
        # Load configuration data
        config_data = {}
        
        for config_file in config_files:
            file_path = Path(os.path.expanduser(str(config_file)))
            if file_path.exists():
                try:
                    file_data = toml.load(file_path)
                    config_data.update(file_data)
                    logger.debug(f"Loaded configuration from {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to load config from {file_path}: {e}")
                    
        # Apply overrides
        config_data.update(overrides)
        
        # Create configuration instance
        self._config = Config(**config_data)
        
        return self._config
        
    def get_config(self) -> Config:
        """Get current configuration."""
        if self._config is None:
            return self.load_config()
        return self._config
        
    def reload_config(self, **overrides: Any) -> Config:
        """Reload configuration."""
        self._config = None
        return self.load_config(**overrides)


# Global configuration manager
_config_manager = ConfigManager()

# Convenience functions
load_config = _config_manager.load_config
get_config = _config_manager.get_config
reload_config = _config_manager.reload_config