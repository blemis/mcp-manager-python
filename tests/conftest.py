"""
Test configuration and fixtures for MCP Manager tests.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

from mcp_manager.utils.config import Config
from mcp_manager.core.manager import MCPManager


@pytest.fixture
def temp_config_dir():
    """Create a temporary configuration directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def test_config(temp_config_dir):
    """Create a test configuration."""
    config = Config(config_dir=str(temp_config_dir))
    return config


@pytest.fixture
def manager(test_config):
    """Create a test MCP manager with isolated configuration."""
    return MCPManager(config=test_config)


@pytest.fixture(autouse=True)
def isolate_tests(temp_config_dir):
    """Ensure tests are isolated from real configuration."""
    with patch.dict(os.environ, {'MCP_MANAGER_CONFIG_DIR': str(temp_config_dir)}):
        yield