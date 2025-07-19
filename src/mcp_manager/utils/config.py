"""
Configuration management for MCP Manager.

Provides hierarchical configuration loading with validation using Pydantic.
Supports multiple configuration sources and environment variable overrides.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import toml
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


class LoggingConfig(BaseModel):
    """Logging configuration."""
    
    level: str = Field(default="INFO", description="Logging level")
    format_type: str = Field(default="text", description="Log format (text/json)")
    file: Optional[str] = Field(default=None, description="Log file path")
    enable_rich: bool = Field(default=True, description="Enable Rich console output")
    max_bytes: int = Field(default=10 * 1024 * 1024, description="Max log file size")
    backup_count: int = Field(default=5, description="Number of backup files")
    
    @validator("level")
    def validate_level(cls, v: str) -> str:
        """Validate logging level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}")
        return v.upper()
        
    @validator("format_type")
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
    
    @validator("theme")
    def validate_theme(cls, v: str) -> str:
        """Validate theme."""
        if v not in ["dark", "light"]:
            raise ValueError(f"Invalid theme: {v}")
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
    
    class Config:
        """Pydantic configuration."""
        env_prefix = "MCP_MANAGER_"
        env_nested_delimiter = "__"
        case_sensitive = False
        
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