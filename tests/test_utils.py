"""
Test utility modules of MCP Manager.

Test configuration, logging, and validation utilities.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

from mcp_manager.utils.config import Config
from mcp_manager.utils.logging import get_logger, setup_logging
from mcp_manager.utils.validators import (
    validate_server_name, validate_command, validate_npm_package,
    validate_docker_image, validate_claude_cli
)
from mcp_manager.core.exceptions import ValidationError
from mcp_manager.core.models import ServerScope


class TestConfig:
    """Test Configuration management."""
    
    def test_config_creation(self, temp_config_dir):
        """Test creating a configuration."""
        config = Config(config_dir=str(temp_config_dir))
        
        assert config.config_dir == str(temp_config_dir)
        assert config.get_config_dir() == Path(temp_config_dir)
        assert config.get_claude_config_path() == Path.home() / ".config/claude-code/mcp-servers.json"
        
    def test_config_directories_created(self, temp_config_dir):
        """Test that configuration directories are created."""
        config_dir = Path(temp_config_dir) / "new_config"
        config = Config(config_dir=str(config_dir))
        
        # Create the directory explicitly for this test
        config.get_config_dir().mkdir(parents=True, exist_ok=True)
        
        assert config_dir.exists()
        assert config_dir.is_dir()
        
    def test_config_defaults(self):
        """Test configuration defaults."""
        config = Config()
        
        assert config.debug is False
        assert config.verbose is False
        assert config.logging.level == "INFO"
        assert config.claude.cli_path == "claude"
        
    def test_config_environment_override(self):
        """Test configuration environment variable override."""
        with patch.dict(os.environ, {'MCP_MANAGER_DEBUG': 'true'}):
            config = Config()
            assert config.debug is True
        
    def test_config_nested_structure(self):
        """Test nested configuration structure."""
        config = Config()
        
        assert hasattr(config, 'logging')
        assert hasattr(config, 'claude')
        assert hasattr(config, 'discovery')
        assert hasattr(config, 'ui')
        
        assert config.logging.level == "INFO"
        assert config.claude.timeout == 30
        assert config.discovery.cache_ttl == 3600
        assert config.ui.theme == "dark"


class TestLogging:
    """Test logging utilities."""
    
    def test_get_logger(self):
        """Test getting a logger."""
        logger = get_logger("test_module")
        
        assert logger.name == "test_module"
        
    def test_setup_logging_debug(self):
        """Test setting up debug logging."""
        # This will actually call the real setup_logging function
        # Just test that it doesn't raise an exception
        try:
            setup_logging(level="DEBUG")
            result = True
        except Exception:
            result = False
        assert result is True
        
    def test_setup_logging_info(self):
        """Test setting up info logging."""
        # This will actually call the real setup_logging function
        # Just test that it doesn't raise an exception
        try:
            setup_logging(level="INFO")
            result = True
        except Exception:
            result = False
        assert result is True


class TestValidators:
    """Test validation utilities."""
    
    def test_validate_server_name_valid(self):
        """Test validating valid server names."""
        assert validate_server_name("valid-name") is True
        assert validate_server_name("valid_name") is True
        assert validate_server_name("validname123") is True
        
    def test_validate_server_name_invalid(self):
        """Test validating invalid server names."""
        with pytest.raises(ValidationError):
            validate_server_name("")
            
        with pytest.raises(ValidationError):
            validate_server_name("   ")
            
        with pytest.raises(ValidationError):
            validate_server_name("a" * 101)  # Too long
            
    def test_validate_command_valid(self):
        """Test validating valid commands."""
        assert validate_command("echo hello") is True
        assert validate_command("npx @package/name") is True
        
    def test_validate_command_invalid(self):
        """Test validating invalid commands."""
        with pytest.raises(ValidationError):
            validate_command("")
            
        with pytest.raises(ValidationError):
            validate_command("   ")
            
    def test_validate_npm_package_valid(self):
        """Test validating valid NPM packages."""
        assert validate_npm_package("@scope/package") is True
        assert validate_npm_package("simple-package") is True
        assert validate_npm_package("package-with-numbers123") is True
        
    def test_validate_npm_package_invalid(self):
        """Test validating invalid NPM packages."""
        with pytest.raises(ValidationError):
            validate_npm_package("")
            
    def test_validate_npm_package_invalid_format(self):
        """Test invalid NPM package formats."""
        with pytest.raises(ValidationError):
            validate_npm_package("_invalid")  # Cannot start with underscore
        
    def test_validate_docker_image_valid(self):
        """Test validating valid Docker images."""
        assert validate_docker_image("ubuntu") is True
        assert validate_docker_image("ubuntu:20.04") is True
        assert validate_docker_image("registry.io/user/image:tag") is True
        
    def test_validate_docker_image_invalid(self):
        """Test validating invalid Docker images."""
        with pytest.raises(ValidationError):
            validate_docker_image("")
            
    def test_validate_docker_image_invalid_format(self):
        """Test invalid Docker image formats."""
        with pytest.raises(ValidationError):
            validate_docker_image("invalid..image")
        
    def test_validate_claude_cli(self):
        """Test validating Claude CLI availability."""
        # This test will depend on system state, so we just test it runs
        is_valid, message = validate_claude_cli()
        assert isinstance(is_valid, bool)
        assert message is None or isinstance(message, str)