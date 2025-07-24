"""
Analytics configuration management.

Handles configuration loading, validation, and defaults
for the MCP Manager analytics system.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from mcp_manager.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AnalyticsConfig:
    """Configuration for analytics system."""
    
    # Core settings
    enabled: bool = True
    db_path: Optional[Path] = None
    
    # Data retention
    retention_days: int = 90
    archive_enabled: bool = False
    archive_path: Optional[Path] = None
    archive_after_days: int = 30
    
    # Performance settings
    aggregation_interval_hours: int = 1
    batch_size: int = 1000
    vacuum_interval_days: int = 7
    
    # Privacy settings
    hash_queries: bool = True
    store_client_ips: bool = False
    anonymize_after_days: int = 7
    
    # Cleanup settings
    auto_cleanup_enabled: bool = True
    cleanup_interval_hours: int = 24
    max_database_size_mb: int = 500
    
    # Reporting settings
    trending_query_limit: int = 10
    summary_default_days: int = 7
    
    # Feature flags
    track_tool_usage: bool = True
    track_recommendations: bool = True
    track_server_analytics: bool = True
    track_api_usage: bool = True
    track_query_patterns: bool = True
    
    # Environment overrides
    environment_prefix: str = "MCP_ANALYTICS_"
    
    def __post_init__(self):
        """Validate and set defaults after initialization."""
        # Set default database path if not provided
        if self.db_path is None:
            self.db_path = self._get_default_db_path()
        
        # Set default archive path if archiving is enabled
        if self.archive_enabled and self.archive_path is None:
            self.archive_path = self._get_default_archive_path()
        
        # Validate configuration
        self._validate_config()
        
        # Apply environment overrides
        self._apply_environment_overrides()
    
    def _get_default_db_path(self) -> Path:
        """Get default database path."""
        # Check environment first
        env_path = os.getenv("MCP_MANAGER_DB_PATH")
        if env_path:
            return Path(env_path)
        
        # Default to user config directory
        config_dir = Path.home() / ".config" / "mcp-manager"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "mcp_manager.db"
    
    def _get_default_archive_path(self) -> Path:
        """Get default archive database path."""
        if self.db_path:
            return self.db_path.parent / "archives" / "mcp_manager_archive.db"
        
        config_dir = Path.home() / ".config" / "mcp-manager" / "archives"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "mcp_manager_archive.db"
    
    def _validate_config(self) -> None:
        """Validate configuration values."""
        if self.retention_days < 1:
            raise ValueError("retention_days must be at least 1")
        
        if self.aggregation_interval_hours < 1:
            raise ValueError("aggregation_interval_hours must be at least 1")
        
        if self.batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        
        if self.archive_enabled and self.archive_after_days >= self.retention_days:
            raise ValueError("archive_after_days must be less than retention_days")
        
        if self.max_database_size_mb < 1:
            raise ValueError("max_database_size_mb must be at least 1")
        
        if self.trending_query_limit < 1:
            raise ValueError("trending_query_limit must be at least 1")
    
    def _apply_environment_overrides(self) -> None:
        """Apply environment variable overrides."""
        # Boolean settings
        bool_settings = [
            "enabled", "archive_enabled", "hash_queries", "store_client_ips",
            "auto_cleanup_enabled", "track_tool_usage", "track_recommendations",
            "track_server_analytics", "track_api_usage", "track_query_patterns"
        ]
        
        for setting in bool_settings:
            env_key = f"{self.environment_prefix}{setting.upper()}"
            env_value = os.getenv(env_key)
            if env_value is not None:
                setattr(self, setting, env_value.lower() in ("true", "1", "yes", "on"))
        
        # Integer settings
        int_settings = [
            "retention_days", "archive_after_days", "aggregation_interval_hours",
            "batch_size", "vacuum_interval_days", "anonymize_after_days",
            "cleanup_interval_hours", "max_database_size_mb", "trending_query_limit",
            "summary_default_days"
        ]
        
        for setting in int_settings:
            env_key = f"{self.environment_prefix}{setting.upper()}"
            env_value = os.getenv(env_key)
            if env_value is not None:
                try:
                    setattr(self, setting, int(env_value))
                except ValueError as e:
                    logger.warning(f"Invalid integer value for {env_key}: {env_value}")
        
        # Path settings
        db_path_env = os.getenv(f"{self.environment_prefix}DB_PATH")
        if db_path_env:
            self.db_path = Path(db_path_env)
        
        archive_path_env = os.getenv(f"{self.environment_prefix}ARCHIVE_PATH")
        if archive_path_env:
            self.archive_path = Path(archive_path_env)
    
    def to_dict(self) -> Dict[str, any]:
        """Convert configuration to dictionary."""
        return {
            "enabled": self.enabled,
            "db_path": str(self.db_path) if self.db_path else None,
            "retention_days": self.retention_days,
            "archive_enabled": self.archive_enabled,
            "archive_path": str(self.archive_path) if self.archive_path else None,
            "archive_after_days": self.archive_after_days,
            "aggregation_interval_hours": self.aggregation_interval_hours,
            "batch_size": self.batch_size,
            "vacuum_interval_days": self.vacuum_interval_days,
            "hash_queries": self.hash_queries,
            "store_client_ips": self.store_client_ips,
            "anonymize_after_days": self.anonymize_after_days,
            "auto_cleanup_enabled": self.auto_cleanup_enabled,
            "cleanup_interval_hours": self.cleanup_interval_hours,
            "max_database_size_mb": self.max_database_size_mb,
            "trending_query_limit": self.trending_query_limit,
            "summary_default_days": self.summary_default_days,
            "track_tool_usage": self.track_tool_usage,
            "track_recommendations": self.track_recommendations,
            "track_server_analytics": self.track_server_analytics,
            "track_api_usage": self.track_api_usage,
            "track_query_patterns": self.track_query_patterns,
        }
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, any]) -> "AnalyticsConfig":
        """Create configuration from dictionary."""
        # Convert path strings to Path objects
        if "db_path" in config_dict and config_dict["db_path"]:
            config_dict["db_path"] = Path(config_dict["db_path"])
        
        if "archive_path" in config_dict and config_dict["archive_path"]:
            config_dict["archive_path"] = Path(config_dict["archive_path"])
        
        return cls(**config_dict)
    
    def get_feature_flags(self) -> Dict[str, bool]:
        """Get feature flag settings."""
        return {
            "tool_usage": self.track_tool_usage,
            "recommendations": self.track_recommendations,
            "server_analytics": self.track_server_analytics,
            "api_usage": self.track_api_usage,
            "query_patterns": self.track_query_patterns,
        }
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a specific feature is enabled."""
        feature_flags = self.get_feature_flags()
        return self.enabled and feature_flags.get(feature, False)
    
    def should_cleanup_now(self, last_cleanup_hours_ago: float) -> bool:
        """Determine if cleanup should run now."""
        return (
            self.auto_cleanup_enabled and 
            last_cleanup_hours_ago >= self.cleanup_interval_hours
        )
    
    def should_vacuum_now(self, last_vacuum_days_ago: float) -> bool:
        """Determine if database vacuum should run now."""
        return last_vacuum_days_ago >= self.vacuum_interval_days
    
    def should_archive_now(self, database_size_mb: float) -> bool:
        """Determine if archiving should run now."""
        return (
            self.archive_enabled and 
            database_size_mb >= self.max_database_size_mb
        )


class AnalyticsConfigManager:
    """Manages analytics configuration loading and updates."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to configuration file (optional)
        """
        self.config_path = config_path
        self._config: Optional[AnalyticsConfig] = None
    
    def load_config(self) -> AnalyticsConfig:
        """
        Load analytics configuration.
        
        Returns:
            Analytics configuration instance
        """
        if self._config is None:
            self._config = self._load_from_sources()
        
        return self._config
    
    def _load_from_sources(self) -> AnalyticsConfig:
        """Load configuration from various sources."""
        # Start with defaults
        config = AnalyticsConfig()
        
        # Override with any configuration file settings
        if self.config_path and self.config_path.exists():
            try:
                import toml
                file_config = toml.load(self.config_path)
                analytics_config = file_config.get("analytics", {})
                
                # Update config with file values
                for key, value in analytics_config.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
                
                logger.debug("Loaded analytics config from file", extra={
                    "config_path": str(self.config_path)
                })
                
            except Exception as e:
                logger.warning(f"Failed to load config file: {e}")
        
        # Environment overrides are applied in __post_init__
        return config
    
    def reload_config(self) -> AnalyticsConfig:
        """
        Reload configuration from sources.
        
        Returns:
            Reloaded analytics configuration
        """
        self._config = None
        return self.load_config()
    
    def update_config(self, updates: Dict[str, any]) -> AnalyticsConfig:
        """
        Update configuration with new values.
        
        Args:
            updates: Dictionary of configuration updates
            
        Returns:
            Updated configuration
        """
        current_config = self.load_config()
        config_dict = current_config.to_dict()
        config_dict.update(updates)
        
        self._config = AnalyticsConfig.from_dict(config_dict)
        return self._config
    
    def save_config(self, config: AnalyticsConfig) -> bool:
        """
        Save configuration to file.
        
        Args:
            config: Configuration to save
            
        Returns:
            True if saved successfully
        """
        if not self.config_path:
            logger.warning("No config path specified, cannot save")
            return False
        
        try:
            import toml
            
            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Load existing config file if it exists
            existing_config = {}
            if self.config_path.exists():
                existing_config = toml.load(self.config_path)
            
            # Update analytics section
            existing_config["analytics"] = config.to_dict()
            
            # Write back to file
            with open(self.config_path, 'w') as f:
                toml.dump(existing_config, f)
            
            logger.info("Analytics configuration saved", extra={
                "config_path": str(self.config_path)
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False